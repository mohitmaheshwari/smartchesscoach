"""
Message Decision Engine
========================

The ruthless selector. One move → max one message.

Pipeline:
  Phase A: Compute structured signals (facts only, no messages)
  Phase B: Generate candidate messages from signals
  Phase C: Score candidates with penalties
  Phase D: Select ONE winner (or silence)

Kill switch: ENABLE_DECISION_ENGINE = True/False

Every decision is logged for debugging.
"""

import chess
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)

# ─── KILL SWITCH ──────────────────────────────────────────────────

ENABLE_DECISION_ENGINE = True

# ─── THRESHOLDS ───────────────────────────────────────────────────

THRESHOLDS = {
    "critical_interrupt": 80,
    "pattern_repeat": 78,
    "turning_point": 74,
    "reinforcement": 70,
    "consequence_warning": 68,
    "coach_move_explanation": 66,
    "opening_principle": 64,
    "endgame_conversion": 70,
}

# ─── DATA STRUCTURES ─────────────────────────────────────────────


@dataclass
class MoveSignals:
    """Phase A output: structured facts about a move. No messages."""
    move_index: int
    fen_before: str
    fen_after: str
    move_san: str
    side_to_move: str  # "white" or "black"
    is_user_move: bool
    move_number: int

    # Core evals
    eval_before: float = 0.0
    eval_after: float = 0.0
    cp_loss: int = 0
    move_quality: str = "good"  # blunder / mistake / inaccuracy / good
    best_move: str = ""

    # Phase
    is_opening_phase: bool = False

    # Tactical awareness
    hung_piece: Optional[Dict] = None  # {piece, square, value}
    missed_threat: Optional[Dict] = None  # {piece, square, threat_type}
    ignored_capture: Optional[Dict] = None  # {piece, square, value}

    # Game flow
    is_first_major_swing: bool = False
    lost_winning_position: bool = False
    is_strong_move: bool = False
    is_non_obvious: bool = False

    # Pattern
    recurring_pattern_match: Optional[str] = None  # pattern_key
    pattern_count: int = 0

    # Coach move specifics
    coach_creates_threat: Optional[Dict] = None  # {threat_type, target_square, target_piece}


@dataclass
class MessageCandidate:
    """Phase B output: a candidate message with metadata."""
    move_index: int
    message_type: str  # critical_interrupt, pattern_repeat, turning_point, etc.
    priority_base: int
    severity: str  # high, medium, low
    concept_key: str
    message: str
    question: Optional[str] = None  # Specific Socratic question
    requires_response: bool = False  # Phase 1: always optional
    expires_after_move: int = 0  # 0 = only this move

    # Scoring (filled in Phase C)
    final_score: float = 0.0
    suppression_reason: Optional[str] = None


@dataclass
class SessionMemory:
    """Tracks what's been shown this session. Prevents spam."""
    concepts_shown: Dict[str, int] = field(default_factory=dict)  # concept_key -> count
    last_shown_move: Dict[str, int] = field(default_factory=dict)  # concept_key -> move_index
    messages_by_move: Dict[int, int] = field(default_factory=dict)  # move_index -> message_count
    total_messages: int = 0
    praise_count: int = 0
    interrupt_count: int = 0
    last_message_move: int = -10  # move_index of last message shown
    template_hashes: set = field(default_factory=set)  # prevent exact same message text

    def messages_in_last_n_moves(self, current_move: int, n: int = 3) -> int:
        """Count messages shown in the last N moves."""
        return sum(
            count for move_idx, count in self.messages_by_move.items()
            if current_move - n <= move_idx <= current_move
        )

    def record_message(self, move_index: int, concept_key: str, message_type: str, message_hash: str):
        """Record that a message was shown."""
        self.concepts_shown[concept_key] = self.concepts_shown.get(concept_key, 0) + 1
        self.last_shown_move[concept_key] = move_index
        self.messages_by_move[move_index] = self.messages_by_move.get(move_index, 0) + 1
        self.total_messages += 1
        self.last_message_move = move_index
        self.template_hashes.add(message_hash)
        if message_type == "reinforcement":
            self.praise_count += 1
        if message_type == "critical_interrupt":
            self.interrupt_count += 1


# ─── PHASE A: COMPUTE SIGNALS ────────────────────────────────────

def compute_signals(
    move_index: int,
    fen_before: str,
    fen_after: str,
    move_san: str,
    is_user_move: bool,
    user_color: str,
    move_number: int,
    eval_before: float,
    eval_after: float,
    best_move: str,
    user_rating: int = 1200,
    session_evals: List[Dict] = None,
    user_patterns: List[str] = None,
) -> MoveSignals:
    """Compute structured facts about a move. No messages generated here."""

    board_before = chess.Board(fen_before)
    board_after = chess.Board(fen_after)
    color = chess.WHITE if user_color == "white" else chess.BLACK

    # Basic classification
    if user_color == "white":
        cp_loss = max(0, int((eval_before - eval_after) * 100))
    else:
        cp_loss = max(0, int((eval_after - eval_before) * 100))

    if cp_loss >= 250:
        quality = "blunder"
    elif cp_loss >= 100:
        quality = "mistake"
    elif cp_loss >= 50:
        quality = "inaccuracy"
    else:
        quality = "good"

    signals = MoveSignals(
        move_index=move_index,
        fen_before=fen_before,
        fen_after=fen_after,
        move_san=move_san,
        side_to_move=user_color if is_user_move else ("black" if user_color == "white" else "white"),
        is_user_move=is_user_move,
        move_number=move_number,
        eval_before=eval_before,
        eval_after=eval_after,
        cp_loss=cp_loss,
        move_quality=quality,
        best_move=best_move or "",
        is_opening_phase=move_number <= 12,
    )

    if is_user_move:
        # Detect hung piece after user's move
        signals.hung_piece = _detect_hung_piece(board_after, color)

        # Detect missed threat (opponent was threatening something user ignored)
        signals.missed_threat = _detect_missed_threat(board_before, board_after, move_san, color)

        # Detect ignored capture (free piece user didn't take)
        signals.ignored_capture = _detect_ignored_capture(board_before, color, move_san)

        # Game flow signals
        signals.is_first_major_swing = _is_first_major_swing(
            eval_before, eval_after, user_color, session_evals or []
        )
        signals.lost_winning_position = _lost_winning_position(eval_before, eval_after, user_color)

        # Strong non-obvious move
        if quality == "good" and move_san == best_move:
            signals.is_strong_move = True
            signals.is_non_obvious = _is_non_obvious(board_before, move_san, color)

        # Pattern match
        if user_patterns and quality in ("blunder", "mistake"):
            pattern = _match_pattern(signals, user_patterns)
            if pattern:
                signals.recurring_pattern_match = pattern
                signals.pattern_count = 1  # Will be enriched by session memory
    else:
        # Coach move: detect if it creates a threat worth explaining
        signals.coach_creates_threat = _detect_coach_threat(board_before, board_after, move_san)

    return signals


def _detect_hung_piece(board: chess.Board, user_color: chess.Color) -> Optional[Dict]:
    """Find user's piece that is attacked and undefended after their move.
    Skips pieces where all attackers are pinned."""
    opponent = not user_color
    worst = None
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != user_color or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(opponent, sq)
        defenders = board.attackers(user_color, sq)
        if attackers and not defenders:
            # Skip if all attackers are pinned
            real_attackers = [a for a in attackers if not board.is_pinned(opponent, a)]
            if not real_attackers:
                continue
            val = _piece_value(piece.piece_type)
            if worst is None or val > worst["value"]:
                worst = {
                    "piece": _piece_name(piece.piece_type),
                    "square": chess.square_name(sq),
                    "value": val,
                }
    return worst


def _detect_missed_threat(
    board_before: chess.Board, board_after: chess.Board,
    move_san: str, user_color: chess.Color
) -> Optional[Dict]:
    """Did the opponent have a threat that the user ignored?"""
    opponent = not user_color
    # Check if opponent was attacking any user piece before the move
    for sq in chess.SQUARES:
        piece = board_before.piece_at(sq)
        if piece is None or piece.color != user_color or piece.piece_type == chess.KING:
            continue
        attackers = board_before.attackers(opponent, sq)
        defenders = board_before.attackers(user_color, sq)
        if attackers and not defenders:
            # This piece was hanging BEFORE the move. Did user address it?
            piece_after = board_after.piece_at(sq)
            if piece_after and piece_after.color == user_color:
                # Still there and still undefended?
                attackers_after = board_after.attackers(opponent, sq)
                defenders_after = board_after.attackers(user_color, sq)
                if attackers_after and not defenders_after:
                    return {
                        "piece": _piece_name(piece.piece_type),
                        "square": chess.square_name(sq),
                        "threat_type": "hanging",
                    }
    return None


def _detect_ignored_capture(
    board: chess.Board, user_color: chess.Color, move_san: str
) -> Optional[Dict]:
    """Was there a free piece the user could have captured but didn't?"""
    opponent = not user_color
    try:
        move = board.parse_san(move_san)
    except (ValueError, chess.InvalidMoveError):
        return None

    # Check all opponent pieces that are hanging
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != opponent or piece.piece_type == chess.KING:
            continue
        # Is it undefended?
        attackers = board.attackers(user_color, sq)
        defenders = board.attackers(opponent, sq)
        if attackers and not defenders and _piece_value(piece.piece_type) >= 3:
            # User could capture but didn't
            if move.to_square != sq:
                return {
                    "piece": _piece_name(piece.piece_type),
                    "square": chess.square_name(sq),
                    "value": _piece_value(piece.piece_type),
                }
    return None


def _is_first_major_swing(
    eval_before: float, eval_after: float,
    user_color: str, session_evals: List[Dict]
) -> bool:
    """Is this the first time the position swung significantly against the user?"""
    if user_color == "white":
        swing = eval_before - eval_after
    else:
        swing = eval_after - eval_before

    if swing < 1.5:  # Need 1.5+ pawn swing
        return False

    # Check if there was already a major swing before
    for ev in session_evals:
        prev_before = ev.get("eval_before", 0)
        prev_after = ev.get("eval_after", 0)
        if user_color == "white":
            prev_swing = prev_before - prev_after
        else:
            prev_swing = prev_after - prev_before
        if prev_swing >= 1.5:
            return False  # Already had a swing

    return True


def _lost_winning_position(eval_before: float, eval_after: float, user_color: str) -> bool:
    """Was the user winning and now they're not?"""
    if user_color == "white":
        was_winning = eval_before >= 1.5
        now_not = eval_after < 0.5
    else:
        was_winning = eval_before <= -1.5
        now_not = eval_after > -0.5
    return was_winning and now_not


def _is_non_obvious(board: chess.Board, move_san: str, color: chess.Color) -> bool:
    """Is the move non-obvious? (not a recapture, not a check, not basic development)"""
    try:
        move = board.parse_san(move_san)
    except (ValueError, chess.InvalidMoveError):
        return False

    # Recapture = obvious
    if board.is_capture(move) and board.move_stack:
        last = board.peek()
        if last.to_square == move.to_square:
            return False  # Recapture

    # Check = somewhat obvious
    board_copy = board.copy()
    board_copy.push(move)
    if board_copy.is_check():
        return False

    # Basic opening development = obvious
    piece = board.piece_at(move.from_square)
    if piece and board.fullmove_number <= 10:
        back_rank = 0 if color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank:
            return False  # Developing from back rank

    return True


def _detect_coach_threat(
    board_before: chess.Board, board_after: chess.Board, move_san: str
) -> Optional[Dict]:
    """Does the coach's move create a meaningful threat?"""
    try:
        move = board_before.parse_san(move_san)
    except (ValueError, chess.InvalidMoveError):
        return None

    to_sq = move.to_square
    piece = board_before.piece_at(move.from_square)
    if not piece:
        return None

    # What does the moved piece now attack?
    attacks = board_after.attacks(to_sq)
    threats = []
    target_color = piece.color  # Coach's color — we want to find what it attacks of the OTHER color
    for sq in attacks:
        target = board_after.piece_at(sq)
        if target and target.color != piece.color and target.piece_type != chess.KING:
            val = _piece_value(target.piece_type)
            if val >= 3:  # Only report meaningful targets
                threats.append({
                    "target_piece": _piece_name(target.piece_type),
                    "target_square": chess.square_name(sq),
                    "value": val,
                })

    # Is it a check?
    if board_after.is_check():
        return {"threat_type": "check", "target_square": "", "target_piece": "king"}

    if threats:
        best = max(threats, key=lambda t: t["value"])
        return {
            "threat_type": "attack",
            "target_square": best["target_square"],
            "target_piece": best["target_piece"],
        }

    return None


def _match_pattern(signals: MoveSignals, user_patterns: List[str]) -> Optional[str]:
    """Match the current mistake to a known user pattern."""
    if signals.hung_piece and "piece_safety" in user_patterns:
        return "piece_safety"
    if signals.missed_threat and "ignored_threat" in user_patterns:
        return "ignored_threat"
    if signals.ignored_capture and "missed_tactic" in user_patterns:
        return "missed_tactic"
    if signals.lost_winning_position and "threw_winning" in user_patterns:
        return "threw_winning"
    return None


# ─── PHASE B: GENERATE CANDIDATES ────────────────────────────────

def generate_candidates(signals: MoveSignals, memory: SessionMemory) -> List[MessageCandidate]:
    """Generate candidate messages from signals. Dumb producers, smart engine."""
    candidates = []

    if signals.is_user_move:
        # Tier 1: Critical interrupt
        if signals.hung_piece:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="critical_interrupt",
                priority_base=100,
                severity="high",
                concept_key="hung_piece",
                message=f"Stop. Your {signals.hung_piece['piece']} on {signals.hung_piece['square']} is undefended.",
                question="Before moving, did you check if all your pieces are protected?",
            ))

        if signals.missed_threat:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="critical_interrupt",
                priority_base=98,
                severity="high",
                concept_key="ignored_threat",
                message=f"You moved without responding to the threat on your {signals.missed_threat['piece']}.",
                question="What was your opponent threatening with their last move?",
            ))

        if signals.move_quality == "blunder" and not signals.hung_piece and not signals.missed_threat:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="critical_interrupt",
                priority_base=95,
                severity="high",
                concept_key="blunder",
                message=f"{signals.move_san} loses significant ground. Did you calculate your opponent's reply?",
                question="What can your opponent do after this move?",
            ))

        if signals.lost_winning_position:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="turning_point",
                priority_base=93,
                severity="high",
                concept_key="conversion_failure",
                message="You were winning. This move let the advantage slip. In winning positions, keep it simple — don't create complications you don't need.",
            ))

        # Tier 2: Pattern repeat
        if signals.recurring_pattern_match:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="pattern_repeat",
                priority_base=90,
                severity="high",
                concept_key=signals.recurring_pattern_match,
                message=_pattern_message(signals.recurring_pattern_match, signals),
                question=_pattern_question(signals.recurring_pattern_match),
            ))

        # Tier 3: Turning point
        if signals.is_first_major_swing and not signals.lost_winning_position:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="turning_point",
                priority_base=84,
                severity="medium",
                concept_key="game_shift",
                message="This is where the game shifted. Until now the position was manageable.",
            ))

        # Tier 4: Reinforcement (non-obvious good move)
        if signals.is_strong_move and signals.is_non_obvious:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="reinforcement",
                priority_base=72,
                severity="low",
                concept_key="strong_move",
                message=_reinforcement_message(signals),
            ))

        # Tier 5: Opening principle (only if no tactical urgency)
        if signals.is_opening_phase and signals.move_quality in ("inaccuracy",) and not signals.hung_piece:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="opening_principle",
                priority_base=58,
                severity="low",
                concept_key="opening_deviation",
                message=_opening_principle_message(signals),
            ))

        # Ignored capture
        if signals.ignored_capture and signals.ignored_capture["value"] >= 3:
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="critical_interrupt",
                priority_base=92,
                severity="high",
                concept_key="ignored_capture",
                message=f"Your opponent's {signals.ignored_capture['piece']} on {signals.ignored_capture['square']} was free to take.",
                question="Did you check for captures before choosing your move?",
            ))

    else:
        # Coach move: only if it creates a teachable threat
        if signals.coach_creates_threat:
            threat = signals.coach_creates_threat
            if threat["threat_type"] == "check":
                msg = f"Check. How will you get your king safe?"
            else:
                msg = f"My piece now targets your {threat['target_piece']}. How will you deal with that pressure?"
            candidates.append(MessageCandidate(
                move_index=signals.move_index,
                message_type="coach_move_explanation",
                priority_base=52,
                severity="low",
                concept_key="coach_threat",
                message=msg,
                question=f"What is my piece threatening right now?",
            ))

    return candidates


# ─── PHASE C: SCORE CANDIDATES ───────────────────────────────────

def score_candidates(
    candidates: List[MessageCandidate],
    memory: SessionMemory,
    move_index: int,
    user_patterns: List[str] = None,
) -> List[MessageCandidate]:
    """Score candidates. Apply bonuses and penalties."""

    for c in candidates:
        score = float(c.priority_base)

        # Severity weight
        if c.severity == "high":
            score += 5
        elif c.severity == "medium":
            score += 0
        else:
            score -= 3

        # Pattern repeat bonus (user's known leak)
        if user_patterns and c.concept_key in user_patterns:
            score += 12

        # Novelty bonus (concept not shown recently)
        if c.concept_key not in memory.concepts_shown:
            score += 8
        elif memory.last_shown_move.get(c.concept_key, -99) < move_index - 10:
            score += 4

        # Duplicate penalty (same concept in last 6 plies)
        last_shown = memory.last_shown_move.get(c.concept_key, -99)
        if move_index - last_shown <= 6:
            score -= 40
            c.suppression_reason = "duplicate_concept_within_6_plies"

        # Same message text in this game
        msg_hash = hash(c.message[:60])
        if msg_hash in memory.template_hashes:
            score -= 50
            c.suppression_reason = "exact_duplicate_message"

        # Recent spam penalty
        recent_msgs = memory.messages_in_last_n_moves(move_index, 3)
        if recent_msgs >= 2:
            score -= 25
            if not c.suppression_reason:
                c.suppression_reason = "spam_burst_3_moves"

        # Filler penalty (reinforcement when too much praise already)
        if c.message_type == "reinforcement" and memory.praise_count >= 5:
            score -= 15

        # Opening noise penalty
        if c.message_type == "opening_principle" and memory.concepts_shown.get("opening_deviation", 0) >= 3:
            score -= 20
            if not c.suppression_reason:
                c.suppression_reason = "opening_spam"

        c.final_score = score

    return candidates


# ─── PHASE D: SELECT WINNER ──────────────────────────────────────

def select_winner(
    candidates: List[MessageCandidate],
    move_index: int,
) -> List[MessageCandidate]:
    """Pick the ONE winner. Silence if nothing passes threshold."""

    # Filter by threshold
    survivors = []
    for c in candidates:
        threshold = THRESHOLDS.get(c.message_type, 70)
        if c.final_score >= threshold:
            survivors.append(c)

    if not survivors:
        return []

    # Pick highest score
    winner = max(survivors, key=lambda c: c.final_score)
    result = [winner]

    # Allow second message ONLY if winner is critical AND second is a direct follow-up
    if winner.message_type == "critical_interrupt" and winner.question:
        # The question is embedded in the winner, no need for second message
        pass

    return result


# ─── MAIN ENTRY POINT ────────────────────────────────────────────

def decide_message(
    signals: MoveSignals,
    memory: SessionMemory,
    user_patterns: List[str] = None,
) -> Dict:
    """
    The ruthless selector.

    Returns:
        {
            "show_message": bool,
            "message": {...} or None,
            "debug_log": {...}
        }
    """
    start = time.time()

    # Phase B: Generate candidates
    candidates = generate_candidates(signals, memory)

    # Phase C: Score
    scored = score_candidates(candidates, memory, signals.move_index, user_patterns)

    # Phase D: Select
    winners = select_winner(scored, signals.move_index)

    # Build debug log
    debug_log = {
        "move_index": signals.move_index,
        "move_san": signals.move_san,
        "is_user_move": signals.is_user_move,
        "move_quality": signals.move_quality,
        "cp_loss": signals.cp_loss,
        "candidates_generated": len(candidates),
        "candidates_after_threshold": len([c for c in scored if c.final_score >= THRESHOLDS.get(c.message_type, 70)]),
        "winner": winners[0].message_type if winners else None,
        "winner_score": round(winners[0].final_score, 1) if winners else None,
        "suppressed": [
            {"type": c.message_type, "concept": c.concept_key, "score": round(c.final_score, 1),
             "reason": c.suppression_reason or "below_threshold"}
            for c in scored if c not in winners and c.final_score > 0
        ],
        "processing_ms": round((time.time() - start) * 1000, 1),
    }

    logger.info(f"[MDE] move={signals.move_index} {signals.move_san}: "
                f"candidates={len(candidates)}, winner={debug_log['winner']}, "
                f"score={debug_log['winner_score']}")

    if not winners:
        return {"show_message": False, "message": None, "debug_log": debug_log}

    winner = winners[0]

    # Record in memory
    memory.record_message(
        move_index=signals.move_index,
        concept_key=winner.concept_key,
        message_type=winner.message_type,
        message_hash=str(hash(winner.message[:60])),
    )

    message_doc = {
        "move_index": signals.move_index,
        "fen_before": signals.fen_before,
        "message_type": winner.message_type,
        "concept_key": winner.concept_key,
        "severity": winner.severity,
        "message": winner.message,
        "question": winner.question,
        "requires_response": winner.requires_response,
        "priority_score": round(winner.final_score, 1),
    }

    return {"show_message": True, "message": message_doc, "debug_log": debug_log}


# ─── MESSAGE TEMPLATES ────────────────────────────────────────────

def _pattern_message(pattern_key: str, signals: MoveSignals) -> str:
    templates = {
        "piece_safety": "Same problem again. You are leaving pieces undefended before looking for your own ideas.",
        "ignored_threat": "This is your pattern — you are moving before checking what your opponent's last move changed.",
        "missed_tactic": "You are missing free pieces. Before choosing your move, scan for captures.",
        "threw_winning": "You were ahead and gave it back. In winning positions, keep it simple.",
    }
    return templates.get(pattern_key, f"This pattern keeps showing up: {pattern_key}.")


def _pattern_question(pattern_key: str) -> str:
    questions = {
        "piece_safety": "Which of your pieces is least protected right now?",
        "ignored_threat": "What did your opponent's last move threaten?",
        "missed_tactic": "Is there anything you can capture for free right now?",
        "threw_winning": "When you're winning, what should your priority be?",
    }
    return questions.get(pattern_key, "What went wrong here?")


def _reinforcement_message(signals: MoveSignals) -> str:
    templates = [
        "Good. You improved your position without creating weaknesses.",
        "Solid. That move was the right priority.",
        "Good choice. You addressed the real problem in the position.",
    ]
    return random.choice(templates)


def _opening_principle_message(signals: MoveSignals) -> str:
    templates = [
        "In the opening, finish development and get your king safe before starting action.",
        "Your pieces aren't all coordinated yet. Complete development before attacking.",
        "The center is not ready to open. Build your position first.",
    ]
    return random.choice(templates)


# ─── HELPERS ──────────────────────────────────────────────────────

def _piece_value(piece_type: int) -> int:
    return {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}.get(piece_type, 0)


def _piece_name(piece_type: int) -> str:
    return {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
            chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}.get(piece_type, "piece")
