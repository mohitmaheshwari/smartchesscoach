"""
MoveCritique — classify WHY a move differs from the engine's best, not HOW MUCH.

Stockfish gives us a cp delta. That's a sensor reading, not teaching material.
This module compares PositionFacts for the played move vs the engine's best move
and labels the deviation with something a coach can actually teach from.

Output is consumed by coaching_policy.py (decides volume/voice) and the rendering
layer (coaching_library templates, smart_coaching LLM). Neither should ever see
a raw centipawn value in the voice path — only through the critique.
"""

import chess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from services.position_facts import (
    PositionFacts, MoveCategory, extract_facts,
)


class DeviationType(str, Enum):
    """What KIND of mistake was this — not how bad."""
    BEST_MOVE = "best_move"                    # student played the engine's top choice
    ON_PLAN_NUDGE = "on_plan_nudge"            # same idea as best, just marginally different
    RIGHT_IDEA_WRONG_SQUARE = "right_idea_wrong_square"  # same piece-plan, better destination
    PRINCIPLE_MISS = "principle_miss"          # best served an opening/middle principle you ignored
    TACTICAL_MISS = "tactical_miss"            # best had a concrete tactic (fork/pin/win material) you skipped
    WALKED_INTO = "walked_into"                # your move hangs a piece / allows opponent tactic
    DIRECTIONLESS = "directionless"            # neither best nor played is clearly principled; small delta


class Principle(str, Enum):
    """Named principles/patterns the critique may attach to. Keep short, teachable."""
    PIECE_SAFETY = "piece_safety"
    KING_SAFETY = "king_safety"
    DEVELOPMENT = "development"
    CENTRAL_CONTROL = "central_control"
    TACTICAL_AWARENESS = "tactical_awareness"
    OPPONENT_THREATS = "opponent_threats"
    PIECE_ACTIVITY = "piece_activity"
    TEMPO = "tempo"


@dataclass
class MoveCritique:
    """Coach-facing classification of a played move."""
    deviation_type: DeviationType
    teaching_focus: Optional[Principle] = None      # the ONE principle/pattern to name

    # Specific patterns (populated when relevant)
    walked_into_pattern: Optional[str] = None       # "hanging piece", "knight fork", etc.
    tactical_pattern_missed: Optional[str] = None   # "fork opportunity", "pin on g-file"

    # Raw context for rendering (never speak the cp directly)
    cp_loss: int = 0
    played_category: Optional[MoveCategory] = None
    best_category: Optional[MoveCategory] = None
    best_move_san: Optional[str] = None
    played_move_san: Optional[str] = None

    # Extra notes the renderer may use ("hanging piece: knight on f6")
    notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Classification helpers
# ─────────────────────────────────────────────────────────────────────────────

_DEVELOP_CATEGORIES = {
    MoveCategory.KNIGHT_DEVELOP, MoveCategory.BISHOP_DEVELOP,
    MoveCategory.QUEEN_DEVELOP,
}
_CENTER_CATEGORIES = {
    MoveCategory.CENTRAL_PAWN_PUSH, MoveCategory.EXTENDED_CENTER_PAWN,
}
_CASTLE_CATEGORIES = {
    MoveCategory.CASTLE_KINGSIDE, MoveCategory.CASTLE_QUEENSIDE,
}


def _played_walked_into_something(played: PositionFacts, best: PositionFacts) -> Optional[str]:
    """Did the played move create a concrete problem the best move avoided?

    Compares post-move facts. The hanging/forks lists in PositionFacts refer to
    the resulting position, so `played.hanging_ours` > `best.hanging_ours` means
    the played move left something vulnerable.
    """
    if len(played.hanging_ours) > len(best.hanging_ours):
        victim = played.hanging_ours[0]
        return f"hanging piece on {chess.square_name(victim.square)}"
    if len(played.forks_by_them) > len(best.forks_by_them):
        return "opponent fork"
    if len(played.pins_against_us) > len(best.pins_against_us):
        return "opponent pin"
    if len(played.skewers_on_us) > len(best.skewers_on_us):
        return "opponent skewer"
    # Did the played move let the opponent attack something new and undefended?
    new_undefended = [t for t in played.new_threats if t.defender_count == 0 and t.is_new]
    best_new_undefended = [t for t in best.new_threats if t.defender_count == 0 and t.is_new]
    if len(new_undefended) > len(best_new_undefended):
        sq = chess.square_name(new_undefended[0].square)
        return f"undefended piece on {sq}"
    return None


def _best_had_tactic_played_missed(played: PositionFacts, best: PositionFacts) -> Optional[str]:
    """Did the best move execute a concrete tactic the played move didn't?"""
    # Forks WE create
    if len(best.forks_by_us) > len(played.forks_by_us):
        return "fork opportunity"
    # Captures winning material
    if best.forcing_moves_us.get("material_gain", 0) > played.forcing_moves_us.get("material_gain", 0) + 100:
        return "free material"
    # Pins against them
    if len(best.pins_against_them) > len(played.pins_against_them):
        return "pin opportunity"
    # Skewers against them
    if len(best.skewers_on_them) > len(played.skewers_on_them):
        return "skewer opportunity"
    # Capturing their hanging piece
    if len(played.hanging_theirs) > len(best.hanging_theirs):
        # best removed an opponent hanging piece (by capturing it)
        captured_sq = played.hanging_theirs[0]
        return f"free piece on {chess.square_name(captured_sq.square)}"
    return None


def _principle_served_by_best(played: PositionFacts, best: PositionFacts) -> Optional[Principle]:
    """What principle does the best move satisfy that the played move ignored?"""
    # Castle when played didn't
    if best.move_category in _CASTLE_CATEGORIES and played.move_category not in _CASTLE_CATEGORIES:
        return Principle.KING_SAFETY

    # Development in opening: best develops new piece, played doesn't
    in_opening = best.phase.value == "opening" and best.move_number <= 12
    if in_opening:
        if best.move_category in _DEVELOP_CATEGORIES and played.move_category not in _DEVELOP_CATEGORIES:
            return Principle.DEVELOPMENT
        # Central control: best is central push, played is flank/retreat
        if best.move_category in _CENTER_CATEGORIES and played.move_category in (
            MoveCategory.FLANK_PAWN_PUSH, MoveCategory.KNIGHT_RETREAT, MoveCategory.BISHOP_RETREAT
        ):
            return Principle.CENTRAL_CONTROL

    # Piece safety: played hangs something best doesn't
    if len(played.hanging_ours) > len(best.hanging_ours):
        return Principle.PIECE_SAFETY
    # Opponent threats: played allows new threats best prevents
    if len(played.new_threats) > len(best.new_threats) + 1:
        return Principle.OPPONENT_THREATS

    return None


def _same_piece_different_square(played_move: chess.Move, best_move: chess.Move,
                                  board_before: chess.Board) -> bool:
    """Do played and best move the SAME piece to DIFFERENT squares?"""
    played_piece = board_before.piece_at(played_move.from_square)
    best_piece = board_before.piece_at(best_move.from_square)
    if not played_piece or not best_piece:
        return False
    if played_move.from_square != best_move.from_square:
        return False
    return played_move.to_square != best_move.to_square


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def classify_move(
    board_before: chess.Board,
    played_move: chess.Move,
    played_san: str,
    best_move: Optional[chess.Move],
    best_san: Optional[str],
    *,
    cp_loss: int = 0,
    move_history_san: Optional[List[str]] = None,
    played_facts: Optional[PositionFacts] = None,
    best_facts: Optional[PositionFacts] = None,
) -> MoveCritique:
    """Classify a played move against the engine's best.

    Args:
        board_before: the position BEFORE the move
        played_move / played_san: what the student actually played
        best_move / best_san: engine's top choice (pass None if no engine data)
        cp_loss: centipawn loss from the mover's perspective (>= 0)
        move_history_san: optional — enables opening detection inside facts
        played_facts / best_facts: optional — pre-computed to avoid recomputation

    Returns:
        MoveCritique with deviation_type and teaching_focus populated.
    """
    # Trivial: no engine data → treat as directionless (we can't judge)
    if best_move is None or best_san is None:
        return MoveCritique(
            deviation_type=DeviationType.DIRECTIONLESS,
            cp_loss=cp_loss,
            played_move_san=played_san,
            best_move_san=best_san,
        )

    # Trivial: student played the best move
    if played_move == best_move:
        if played_facts is None:
            played_facts = extract_facts(
                board_before, played_move, played_san,
                move_history_san=move_history_san,
            )
        return MoveCritique(
            deviation_type=DeviationType.BEST_MOVE,
            cp_loss=0,
            played_category=played_facts.move_category,
            best_category=played_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
        )

    # Compute both fact objects
    if played_facts is None:
        played_facts = extract_facts(
            board_before, played_move, played_san,
            move_history_san=move_history_san,
        )
    if best_facts is None:
        best_facts = extract_facts(
            board_before, best_move, best_san,
            move_history_san=move_history_san,
        )

    # Priority 1: WALKED_INTO — played move created a problem best avoided
    walked_into = _played_walked_into_something(played_facts, best_facts)
    if walked_into:
        return MoveCritique(
            deviation_type=DeviationType.WALKED_INTO,
            teaching_focus=Principle.OPPONENT_THREATS,
            walked_into_pattern=walked_into,
            cp_loss=cp_loss,
            played_category=played_facts.move_category,
            best_category=best_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
            notes=[f"Played allows: {walked_into}"],
        )

    # Priority 2: TACTICAL_MISS — best had a concrete winning tactic
    tactic = _best_had_tactic_played_missed(played_facts, best_facts)
    if tactic:
        return MoveCritique(
            deviation_type=DeviationType.TACTICAL_MISS,
            teaching_focus=Principle.TACTICAL_AWARENESS,
            tactical_pattern_missed=tactic,
            cp_loss=cp_loss,
            played_category=played_facts.move_category,
            best_category=best_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
            notes=[f"Best had: {tactic}"],
        )

    # Priority 3: PRINCIPLE_MISS — best served a principle played ignored
    principle = _principle_served_by_best(played_facts, best_facts)
    if principle:
        return MoveCritique(
            deviation_type=DeviationType.PRINCIPLE_MISS,
            teaching_focus=principle,
            cp_loss=cp_loss,
            played_category=played_facts.move_category,
            best_category=best_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
        )

    # Priority 4: RIGHT_IDEA_WRONG_SQUARE — same piece, different destination
    if _same_piece_different_square(played_move, best_move, board_before):
        return MoveCritique(
            deviation_type=DeviationType.RIGHT_IDEA_WRONG_SQUARE,
            teaching_focus=Principle.PIECE_ACTIVITY,
            cp_loss=cp_loss,
            played_category=played_facts.move_category,
            best_category=best_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
        )

    # Priority 5: ON_PLAN_NUDGE — same move category, small delta, no patterns differ
    if played_facts.move_category == best_facts.move_category and cp_loss < 80:
        return MoveCritique(
            deviation_type=DeviationType.ON_PLAN_NUDGE,
            cp_loss=cp_loss,
            played_category=played_facts.move_category,
            best_category=best_facts.move_category,
            played_move_san=played_san,
            best_move_san=best_san,
        )

    # Everything else — small deviation with no clear teaching angle
    return MoveCritique(
        deviation_type=DeviationType.DIRECTIONLESS,
        cp_loss=cp_loss,
        played_category=played_facts.move_category,
        best_category=best_facts.move_category,
        played_move_san=played_san,
        best_move_san=best_san,
    )
