"""
Punishment Puzzle service.

When the coach plays an exploitable move during Coach Play, instead of
narrating it ("Pawn to e5 — fighting for the middle"), pause the
session and turn it into a guided puzzle:

  Observation: "My e5 pawn is only defended by my queen."
  Challenge:   "Can you find a move that wins it?"
  Reveal:      "Bxe5 wins the pawn — your bishop attacks e5 and your
                knight on c6 protects the bishop."

The user's next move is evaluated against the engine's top responses
and classified solved / close / missed. The user's actual move is
ALWAYS played; we never undo their choice. Only the coaching layer
adapts.

Design constraints (from product memory):
  - Concept + consequence rule: every text slot must use concrete
    pieces / squares / consequences a 1200 player can verify by
    looking at the board. No chess jargon without explanation.
  - Confidence-gated: only fire when the punishment is mechanically
    derivable. Otherwise fall back to current narration. Better
    silent than vague.
  - Frequency cap: 2-3 puzzles per game (configurable). Reset per
    session.

MVP detector set (in priority order):
  1. mate_in_1               — user has a forced mate
  2. wins_undefended_piece   — coach piece ≥minor is hanging; user takes
  3. wins_overextended_pawn  — coach's pawn push lands within reach
                                of an attacker, capture is SEE-safe

v2 patterns (skewer / pin / discovered attack / mate-in-2) — later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import chess

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────

# How many puzzles can fire in one session before we stop. Set per
# product spec — locked at 3 for MVP.
DEFAULT_FREQUENCY_CAP = 3

# Minimum eval (cp from user's POV, after their best response) for
# the position to qualify as "winning" — under this, even a perfect
# refutation isn't material/mate, so calling it a "punishment puzzle"
# overstates the moment.
MIN_USER_ADVANTAGE_CP = 150

# Tolerance for "equally winning" moves to count as solved.
SOLVED_TOLERANCE_CP = 30

# Tolerance for "close — wins material but not optimal" classification.
CLOSE_TOLERANCE_CP = 200


_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


# ── Types ────────────────────────────────────────────────────────────

@dataclass
class PuzzleSpec:
    """A guided puzzle constructed from a single exploitable coach move.

    All text fields use concrete piece/square references — no jargon.
    """
    pattern_type: str          # "mate_in_1" | "wins_undefended_piece" | "wins_overextended_pawn"
    observation: str           # what's wrong with coach's last move
    challenge: str             # what we ask the user to find
    expected_sans: List[str]   # SANs that count as solved (top engine moves within tolerance)
    near_miss_sans: List[str]  # SANs that are close (gain material but not optimal)
    reveal: str                # full answer with concrete why
    target_square: Optional[str] = None  # for board-highlight; e.g. "e5"


@dataclass
class PuzzleEvaluation:
    """Outcome of evaluating a user's move against an active puzzle."""
    outcome: str               # "solved" | "close" | "missed"
    user_san: str
    expected_sans: List[str]
    feedback_text: str         # ready-to-display text for the sidebar


# ── Top-level entry point ────────────────────────────────────────────

def evaluate_for_puzzle(
    *,
    board_before_coach: chess.Board,
    coach_move: chess.Move,
    board_after_coach: chess.Board,
    user_color: chess.Color,
    pv_top_moves: List[Tuple[str, int]],
    session_puzzle_count: int = 0,
    frequency_cap: int = DEFAULT_FREQUENCY_CAP,
) -> Optional[PuzzleSpec]:
    """Decide whether the position after the coach's move qualifies
    as a punishment puzzle. Returns a PuzzleSpec if yes, else None.

    Args:
      board_before_coach: position before the coach moved
      coach_move:         the coach's actual move
      board_after_coach:  position after the coach moved (user to move)
      user_color:         the user's colour
      pv_top_moves:       engine's top user responses, sorted best first.
                          Each tuple is (san, eval_cp_from_user_pov).
                          Need at least one entry with positive eval to
                          qualify.
      session_puzzle_count: how many puzzles already fired this session
      frequency_cap:      max puzzles per session (default 3)
    """
    # Hard gates that apply regardless of pattern
    if session_puzzle_count >= frequency_cap:
        return None
    if not pv_top_moves:
        return None

    best_san, best_eval = pv_top_moves[0]
    if best_eval < MIN_USER_ADVANTAGE_CP and not _looks_like_mate_eval(best_eval):
        return None

    # Verify the user actually has the move legally
    try:
        best_move = board_after_coach.parse_san(best_san)
    except Exception:
        logger.debug(
            f"[punishment_puzzle] best_san {best_san!r} unparseable in position; skipping"
        )
        return None

    # Compute solved + near-miss SAN sets from the PV. Solved = within
    # SOLVED_TOLERANCE_CP of best. Near-miss = within CLOSE_TOLERANCE_CP.
    expected_sans = []
    near_miss_sans = []
    for san, ev in pv_top_moves:
        if abs(best_eval - ev) <= SOLVED_TOLERANCE_CP:
            expected_sans.append(san)
        elif abs(best_eval - ev) <= CLOSE_TOLERANCE_CP:
            near_miss_sans.append(san)

    # Try each pattern in priority order. First one that fires wins.
    for detector in (
        _detect_mate_in_1,
        _detect_wins_undefended_piece,
        _detect_wins_overextended_pawn,
    ):
        spec = detector(
            board_before_coach=board_before_coach,
            coach_move=coach_move,
            board_after_coach=board_after_coach,
            user_color=user_color,
            best_user_move=best_move,
            best_user_san=best_san,
            expected_sans=expected_sans,
            near_miss_sans=near_miss_sans,
        )
        if spec:
            logger.info(
                f"[punishment_puzzle] armed pattern={spec.pattern_type} "
                f"after coach_move={board_before_coach.san(coach_move)} "
                f"best_response={best_san} eval={best_eval}cp"
            )
            return spec

    return None


def evaluate_user_response(
    *,
    user_move_san: str,
    puzzle: dict,
) -> PuzzleEvaluation:
    """Classify the user's response to an active puzzle. Generates the
    feedback text the sidebar will show.

    Args:
      user_move_san: the move the user actually played (in SAN)
      puzzle: dict shape stored in coach_sessions.active_puzzle —
              must have keys 'expected_sans', 'near_miss_sans',
              'reveal', 'pattern_type'.
    """
    expected = list(puzzle.get("expected_sans") or [])
    near_miss = list(puzzle.get("near_miss_sans") or [])
    reveal = puzzle.get("reveal") or ""
    pattern = puzzle.get("pattern_type") or "puzzle"

    if user_move_san in expected:
        # Solved — celebrate concretely
        if pattern == "mate_in_1":
            text = f"Yes! {user_move_san} is checkmate. Game-ending move."
        else:
            text = f"Yes! {user_move_san} is the punishment. {reveal.split(' — ', 1)[-1] if ' — ' in reveal else reveal}"
        return PuzzleEvaluation(
            outcome="solved",
            user_san=user_move_san,
            expected_sans=expected,
            feedback_text=text,
        )
    if user_move_san in near_miss:
        text = (
            f"Good — {user_move_san} wins something. Even stronger was "
            f"{expected[0]}. {reveal}"
        )
        return PuzzleEvaluation(
            outcome="close",
            user_san=user_move_san,
            expected_sans=expected,
            feedback_text=text,
        )
    # Missed — reveal the answer with the why
    text = f"Almost — {expected[0] if expected else '?'} was the punishment. {reveal}"
    return PuzzleEvaluation(
        outcome="missed",
        user_san=user_move_san,
        expected_sans=expected,
        feedback_text=text,
    )


# ── Pattern detectors ────────────────────────────────────────────────


def _detect_mate_in_1(
    *,
    board_before_coach: chess.Board,
    coach_move: chess.Move,
    board_after_coach: chess.Board,
    user_color: chess.Color,
    best_user_move: chess.Move,
    best_user_san: str,
    expected_sans: List[str],
    near_miss_sans: List[str],
) -> Optional[PuzzleSpec]:
    """Coach's move allowed checkmate. User has at least one move
    that delivers mate."""
    # Verify by playing best_user_move and checking is_checkmate
    b = board_after_coach.copy()
    try:
        b.push(best_user_move)
    except Exception:
        return None
    if not b.is_checkmate():
        return None

    # Build observation: describe coach king's predicament
    coach_king_sq = board_after_coach.king(not user_color)
    coach_king_sq_name = chess.square_name(coach_king_sq) if coach_king_sq is not None else "?"

    # Mating piece description for reveal
    mating_piece = board_after_coach.piece_at(best_user_move.from_square)
    mating_name = _PIECE_NAME.get(mating_piece.piece_type, "piece") if mating_piece else "piece"
    target_sq_name = chess.square_name(best_user_move.to_square)

    return PuzzleSpec(
        pattern_type="mate_in_1",
        observation=f"My king on {coach_king_sq_name} has no escape — there's a forced mate.",
        challenge="Can you find checkmate in one move?",
        expected_sans=expected_sans,
        near_miss_sans=near_miss_sans,
        reveal=(
            f"{best_user_san} is mate — your {mating_name} on {target_sq_name} "
            f"attacks my king and there's nowhere to run."
        ),
        target_square=chess.square_name(coach_king_sq) if coach_king_sq is not None else None,
    )


def _detect_wins_undefended_piece(
    *,
    board_before_coach: chess.Board,
    coach_move: chess.Move,
    board_after_coach: chess.Board,
    user_color: chess.Color,
    best_user_move: chess.Move,
    best_user_san: str,
    expected_sans: List[str],
    near_miss_sans: List[str],
) -> Optional[PuzzleSpec]:
    """Coach has a ≥minor piece that's undefended-or-underdefended,
    and the user's best move captures it for material gain.

    Confidence requirement: the user's capture must be SEE-safe (the
    capturing piece isn't itself lost), and the captured piece must
    be ≥minor (don't fire for pawns — that's the next detector)."""
    # Best move must be a capture
    if not board_after_coach.is_capture(best_user_move):
        return None

    captured_sq = best_user_move.to_square
    captured = board_after_coach.piece_at(captured_sq)
    if not captured:
        # En passant — different pattern, skip
        return None
    if captured.piece_type in (chess.PAWN, chess.KING):
        return None  # pawns handled by overextended_pawn; king isn't winnable

    # Verify SEE — the user's capture should be safe (recapture either
    # not possible or unfavorable for opponent)
    try:
        from services.tactical_safety import capture_is_safe
        if not capture_is_safe(board_after_coach, best_user_move):
            return None
    except Exception:
        # Fall back to a defender count check
        defenders = board_after_coach.attackers(not user_color, captured_sq)
        if defenders:
            return None

    # Build observation: name the piece and its square
    captured_name = _PIECE_NAME.get(captured.piece_type, "piece")
    captured_sq_name = chess.square_name(captured_sq)

    # Compute defender summary for the reveal line
    defenders = list(board_after_coach.attackers(not user_color, captured_sq))
    if not defenders:
        observation = f"My {captured_name} on {captured_sq_name} has no defender."
    else:
        defender_pieces = []
        for d_sq in defenders:
            p = board_after_coach.piece_at(d_sq)
            if p:
                defender_pieces.append(_PIECE_NAME.get(p.piece_type, "piece"))
        defender_str = " and ".join(defender_pieces) if defender_pieces else "something"
        observation = (
            f"My {captured_name} on {captured_sq_name} is only defended by my {defender_str}."
        )

    # Challenge text
    challenge = f"Can you find a move that wins my {captured_name}?"

    # Reveal text — name the user's piece and what protects it
    capturing_piece = board_after_coach.piece_at(best_user_move.from_square)
    if capturing_piece:
        cap_name = _PIECE_NAME.get(capturing_piece.piece_type, "piece")
    else:
        cap_name = "piece"
    reveal = (
        f"{best_user_san} wins the {captured_name} — your {cap_name} takes "
        f"on {captured_sq_name}, and nothing safely recaptures."
    )

    return PuzzleSpec(
        pattern_type="wins_undefended_piece",
        observation=observation,
        challenge=challenge,
        expected_sans=expected_sans,
        near_miss_sans=near_miss_sans,
        reveal=reveal,
        target_square=captured_sq_name,
    )


def _detect_wins_overextended_pawn(
    *,
    board_before_coach: chess.Board,
    coach_move: chess.Move,
    board_after_coach: chess.Board,
    user_color: chess.Color,
    best_user_move: chess.Move,
    best_user_san: str,
    expected_sans: List[str],
    near_miss_sans: List[str],
) -> Optional[PuzzleSpec]:
    """Coach's last move was a pawn push and the user's best move
    captures that pawn. The capture must be SEE-positive — the pawn
    is genuinely overextended, not just baited."""
    # Coach's move must be a pawn push (not a capture by a pawn)
    moving_piece = board_before_coach.piece_at(coach_move.from_square)
    if not moving_piece or moving_piece.piece_type != chess.PAWN:
        return None
    if board_before_coach.is_capture(coach_move):
        return None  # capture, not just a push

    pawn_sq = coach_move.to_square
    pawn_sq_name = chess.square_name(pawn_sq)

    # User's best move must be a capture of THIS pawn
    if best_user_move.to_square != pawn_sq:
        return None
    if not board_after_coach.is_capture(best_user_move):
        return None
    captured = board_after_coach.piece_at(pawn_sq)
    if not captured or captured.piece_type != chess.PAWN:
        return None

    # SEE check — capture must be safe (user gains material)
    try:
        from services.tactical_safety import capture_is_safe
        if not capture_is_safe(board_after_coach, best_user_move):
            return None
    except Exception:
        # Conservative fallback — fewer defenders than attackers
        defenders = board_after_coach.attackers(not user_color, pawn_sq)
        attackers = board_after_coach.attackers(user_color, pawn_sq)
        if len(defenders) >= len(attackers):
            return None

    file_letter = pawn_sq_name[0]
    capturing_piece = board_after_coach.piece_at(best_user_move.from_square)
    cap_name = _PIECE_NAME.get(capturing_piece.piece_type, "piece") if capturing_piece else "piece"

    # Defender summary
    defenders = list(board_after_coach.attackers(not user_color, pawn_sq))
    if not defenders:
        observation = f"I pushed my {file_letter}-pawn to {pawn_sq_name} with no defender."
    else:
        defender_pieces = []
        for d_sq in defenders:
            p = board_after_coach.piece_at(d_sq)
            if p:
                defender_pieces.append(_PIECE_NAME.get(p.piece_type, "piece"))
        defender_str = " and ".join(defender_pieces) if defender_pieces else "something"
        observation = (
            f"I pushed my {file_letter}-pawn to {pawn_sq_name} — "
            f"only my {defender_str} guards it."
        )

    challenge = f"Can you find a capture that wins my {file_letter}-pawn?"
    reveal = (
        f"{best_user_san} wins the pawn — your {cap_name} takes on "
        f"{pawn_sq_name}, and the recapture costs me more than I gain."
    )

    return PuzzleSpec(
        pattern_type="wins_overextended_pawn",
        observation=observation,
        challenge=challenge,
        expected_sans=expected_sans,
        near_miss_sans=near_miss_sans,
        reveal=reveal,
        target_square=pawn_sq_name,
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _looks_like_mate_eval(eval_cp: int) -> bool:
    """Stockfish often encodes mate-in-N as a large eval (e.g. 30000).
    Accept any eval > 5000 cp as a mate-flavoured signal so the
    MIN_USER_ADVANTAGE gate doesn't reject them."""
    return abs(eval_cp) >= 5000
