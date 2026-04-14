"""
Teaching Evaluator — score candidate moves against a specific intent.

Each intent has its own scoring function that analyzes the RESULTING position
(after the candidate move is played). The score reflects how well the resulting
position serves the teaching intent.

Scoring formula:
    final = intent_score * 0.72 + engine_quality * 0.23 + variety * 0.05
"""

import chess
import random
import logging
from typing import List, Optional

from .types import (
    TeachingIntent, CandidateMove, PositionFeatures,
    IntentScore, PIECE_VALUES,
)
from .pattern_detectors import analyze_position

logger = logging.getLogger(__name__)

# Minimum intent score for feasibility — if no candidate scores above this,
# the intent is not feasible for this position.
MIN_FEASIBILITY_SCORE = 0.3


def score_candidate(
    board: chess.Board,
    candidate: CandidateMove,
    intent: TeachingIntent,
    coach_color: chess.Color,
    best_eval_cp: int,
    max_eval_drop: int = 150,
) -> IntentScore:
    """
    Score a single candidate move against a specific teaching intent.

    Args:
        board: Position BEFORE the candidate move
        candidate: The move to evaluate
        intent: What we're trying to teach
        coach_color: The color the coach is playing
        best_eval_cp: Best engine eval among all candidates (for normalization)
        max_eval_drop: Maximum eval drop for engine quality normalization

    Returns:
        IntentScore with full breakdown
    """
    # 1. Simulate the position after the move
    board_after = board.copy()
    board_after.push(candidate.move)

    # 2. Analyze the resulting position
    features = analyze_position(board_after, coach_color)

    # 3. Score based on intent
    if intent == TeachingIntent.HANGING_PIECE_PUNISHMENT:
        raw_score, sub_scores, explanation = _score_hanging_piece(
            board, board_after, features, candidate, coach_color
        )
    elif intent == TeachingIntent.FORK_OPPORTUNITY:
        raw_score, sub_scores, explanation = _score_fork(
            board, board_after, features, candidate, coach_color
        )
    elif intent == TeachingIntent.THREAT_AWARENESS:
        raw_score, sub_scores, explanation = _score_threat_awareness(
            board, board_after, features, candidate, coach_color
        )
    else:
        raw_score, sub_scores, explanation = 0.0, {}, "Unknown intent"

    # 4. Engine quality: how close is this to the best move?
    eval_drop = best_eval_cp - candidate.eval_cp
    engine_quality = max(0.0, 1.0 - eval_drop / max_eval_drop) if max_eval_drop > 0 else 1.0

    # 5. Small variety factor
    variety = random.uniform(0.0, 1.0)

    # 6. Final score
    final = raw_score * 0.72 + engine_quality * 0.23 + variety * 0.05

    return IntentScore(
        intent=intent,
        raw_score=raw_score,
        sub_scores=sub_scores,
        engine_quality=engine_quality,
        final_score=final,
        explanation=explanation,
    )


def score_all_candidates(
    board: chess.Board,
    candidates: List[CandidateMove],
    intent: TeachingIntent,
    coach_color: chess.Color,
    max_eval_drop: int = 150,
) -> List[IntentScore]:
    """
    Score all candidates against an intent. Returns scores in same order as candidates.
    """
    if not candidates:
        return []

    best_eval = candidates[0].eval_cp  # candidates are sorted best-first

    return [
        score_candidate(board, c, intent, coach_color, best_eval, max_eval_drop)
        for c in candidates
    ]


def is_intent_feasible(scores: List[IntentScore]) -> bool:
    """
    Check if any candidate scores above the feasibility threshold for this intent.
    """
    return any(s.raw_score >= MIN_FEASIBILITY_SCORE for s in scores)


# ─── INTENT-SPECIFIC SCORERS ────────────────────────────────────


def _score_hanging_piece(
    board_before: chess.Board,
    board_after: chess.Board,
    features: PositionFeatures,
    candidate: CandidateMove,
    coach_color: chess.Color,
) -> tuple:
    """
    Score: does this move leave the student's pieces hanging?

    The coach wants to create positions where the student has
    undefended or underdefended pieces that the coach threatens.

    After this coach move, the student needs to notice their hanging piece
    and defend it (or lose material).
    """
    sub_scores = {}

    # Score based on student's hanging pieces in the resulting position
    # Weight: undefended piece is worth more than underdefended
    undefended_score = 0.0
    for hp in features.opponent_hanging:
        undefended_score += hp.piece_value * 0.3  # e.g., hanging knight = 0.9
    sub_scores["undefended"] = min(undefended_score, 2.0)

    underdefended_score = 0.0
    for hp in features.opponent_underdefended:
        underdefended_score += hp.piece_value * 0.15
    sub_scores["underdefended"] = min(underdefended_score, 1.0)

    # Bonus: did THIS move create the hanging situation?
    # Compare before vs after — new hanging pieces are more instructive
    student_color = not coach_color
    before_hanging = _count_hanging(board_before, student_color)
    after_hanging = len(features.opponent_hanging) + len(features.opponent_underdefended)
    new_threats = max(0, after_hanging - before_hanging)
    sub_scores["new_threats_created"] = min(new_threats * 0.4, 1.0)

    raw_score = sub_scores["undefended"] + sub_scores["underdefended"] + sub_scores["new_threats_created"]
    raw_score = min(raw_score, 3.0)  # Cap

    # Build explanation
    parts = []
    if features.opponent_hanging:
        names = [chess.piece_name(h.piece_type) for h in features.opponent_hanging]
        parts.append(f"leaves opponent's {', '.join(names)} hanging")
    if features.opponent_underdefended:
        names = [chess.piece_name(h.piece_type) for h in features.opponent_underdefended]
        parts.append(f"makes opponent's {', '.join(names)} underdefended")
    explanation = "; ".join(parts) if parts else "no hanging pieces created"

    return raw_score, sub_scores, explanation


def _score_fork(
    board_before: chess.Board,
    board_after: chess.Board,
    features: PositionFeatures,
    candidate: CandidateMove,
    coach_color: chess.Color,
) -> tuple:
    """
    Score: does this move create a fork (or fork threat)?

    A fork is one piece attacking 2+ valuable targets. The student
    must recognize the double attack and save the more valuable piece.
    """
    sub_scores = {}

    # Direct forks in resulting position
    fork_score = 0.0
    best_fork = None
    for fork in features.fork_opportunities:
        # Higher value targets = more instructive fork
        value = fork.total_target_value * 0.15
        # Knight forks are the most instructive (hardest to see)
        if fork.forker_type == chess.KNIGHT:
            value *= 1.5
        fork_score = max(fork_score, value)
        if best_fork is None or value > best_fork[1]:
            best_fork = (fork, value)
    sub_scores["fork_value"] = min(fork_score, 2.5)

    # Did THIS move create the fork? (vs fork already existed)
    forks_before = _count_forks(board_before, coach_color)
    forks_after = len(features.fork_opportunities)
    new_forks = max(0, forks_after - forks_before)
    sub_scores["new_forks_created"] = min(new_forks * 0.5, 1.0)

    raw_score = sub_scores["fork_value"] + sub_scores["new_forks_created"]
    raw_score = min(raw_score, 3.0)

    # Explanation
    if best_fork:
        fork_info = best_fork[0]
        forker = chess.piece_name(fork_info.forker_type)
        targets = [chess.piece_name(t) for t in fork_info.target_types[:2]]
        explanation = f"coach's {forker} forks opponent's {' and '.join(targets)}"
    else:
        explanation = "no fork created"

    return raw_score, sub_scores, explanation


def _score_threat_awareness(
    board_before: chess.Board,
    board_after: chess.Board,
    features: PositionFeatures,
    candidate: CandidateMove,
    coach_color: chess.Color,
) -> tuple:
    """
    Score: does this move create threats the student must notice?

    Threat awareness means the student must look at what the coach's
    move does BEFORE playing their own move. We want positions where
    the coach creates checks, captures, or attacks on high-value pieces.

    The student needs to ask: "What is my opponent threatening?"
    """
    sub_scores = {}

    # Checks available (most forcing — student MUST respond)
    sub_scores["checks"] = min(features.checks_available * 0.5, 1.0)

    # Captures available (coach threatens to take something)
    sub_scores["captures"] = min(features.captures_available * 0.2, 1.0)

    # Attacks on high-value pieces (queen/rook under threat)
    sub_scores["high_value_attacks"] = min(features.high_value_attacks * 0.4, 1.0)

    # Did this move create NEW threats vs what existed before?
    before_checks, before_captures, before_hv = _count_forcing(board_before, coach_color)
    new_checks = max(0, features.checks_available - before_checks)
    new_captures = max(0, features.captures_available - before_captures)
    sub_scores["new_forcing_moves"] = min((new_checks * 0.4 + new_captures * 0.15), 1.0)

    raw_score = (
        sub_scores["checks"]
        + sub_scores["captures"]
        + sub_scores["high_value_attacks"]
        + sub_scores["new_forcing_moves"]
    )
    raw_score = min(raw_score, 3.0)

    # Explanation
    parts = []
    if features.checks_available:
        parts.append(f"{features.checks_available} checks available")
    if features.high_value_attacks:
        parts.append(f"attacks on {features.high_value_attacks} high-value pieces")
    if features.captures_available:
        parts.append(f"{features.captures_available} captures possible")
    explanation = "; ".join(parts) if parts else "no immediate threats"

    return raw_score, sub_scores, explanation


# ─── HELPERS ────────────────────────────────────────────────────


def _count_hanging(board: chess.Board, victim_color: chess.Color) -> int:
    """Quick count of hanging + underdefended pieces for delta comparison."""
    count = 0
    attacker_color = not victim_color
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != victim_color or piece.piece_type in (chess.KING, chess.PAWN):
            continue
        attackers = list(board.attackers(attacker_color, sq))
        if not attackers:
            continue
        defenders = list(board.attackers(victim_color, sq))
        if len(defenders) == 0:
            count += 1
        elif len(attackers) > len(defenders):
            cheapest = min(
                (PIECE_VALUES.get(board.piece_at(a).piece_type, 0)
                 for a in attackers if board.piece_at(a)),
                default=99,
            )
            if cheapest < PIECE_VALUES.get(piece.piece_type, 0):
                count += 1
    return count


def _count_forks(board: chess.Board, forker_color: chess.Color) -> int:
    """Quick count of fork patterns for delta comparison."""
    count = 0
    opp = not forker_color
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != forker_color or piece.piece_type == chess.KING:
            continue
        attacks = board.attacks(sq)
        targets = 0
        for t_sq in attacks:
            t = board.piece_at(t_sq)
            if t and t.color == opp and t.piece_type != chess.PAWN:
                targets += 1
        if targets >= 2:
            count += 1
    return count


def _count_forcing(board: chess.Board, side: chess.Color) -> tuple:
    """Quick count of meaningful forcing moves for delta comparison.
    Uses the same filtered logic as pattern_detectors.count_forcing_moves."""
    from .pattern_detectors import count_forcing_moves
    return count_forcing_moves(board, side)
