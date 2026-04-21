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


def _move_serves_principle(facts: PositionFacts, principle: Principle) -> bool:
    """Does this move address the given principle?

    Used with the demand analyzer: after the position tells us what principle
    it's demanding, we check whether the played (or best) move answers that
    demand. This is the replacement for category-shape matching.
    """
    if principle == Principle.DEVELOPMENT:
        return facts.move_category in _DEVELOP_CATEGORIES or facts.move_category in _CASTLE_CATEGORIES

    if principle == Principle.KING_SAFETY:
        # Castling is the textbook king-safety move. A king move or a piece
        # block that reduces attackers also counts, but detecting that needs
        # pre/post comparison — skip for MVP; castle coverage is 90% of cases.
        return facts.move_category in _CASTLE_CATEGORIES

    if principle == Principle.CENTRAL_CONTROL:
        # Central pawn pushes or pieces that land on central squares
        if facts.move_category in _CENTER_CATEGORIES:
            return True
        import chess as _chess
        center_squares = {_chess.D4, _chess.E4, _chess.D5, _chess.E5,
                          _chess.C4, _chess.C5, _chess.F4, _chess.F5}
        return facts.to_square in center_squares

    if principle == Principle.PIECE_SAFETY:
        # A move serves piece safety if it doesn't LEAVE anything hanging.
        return len(facts.hanging_ours) == 0

    if principle == Principle.OPPONENT_THREATS:
        # A move serves threat-awareness if it doesn't allow new attacks on us.
        # Approximate: after the move, no NEW undefended threats against us.
        new_undef = [t for t in facts.new_threats
                     if t.defender_count == 0 and t.is_new]
        return len(new_undef) == 0

    return False


def _principle_served_by_best(played: PositionFacts, best: PositionFacts) -> Optional[Principle]:
    """Legacy shape-matching fallback — only used when demand analyzer is unavailable.

    The main path now uses position_demands.dominant_demand() to determine
    WHICH principle applies, then _move_serves_principle() to check whether
    played/best serve it. That's position-driven, not move-shape-driven.
    """
    if best.move_category in _CASTLE_CATEGORIES and played.move_category not in _CASTLE_CATEGORIES:
        return Principle.KING_SAFETY

    in_opening = best.phase.value == "opening" and best.move_number <= 12
    if in_opening:
        if best.move_category in _DEVELOP_CATEGORIES and played.move_category not in _DEVELOP_CATEGORIES:
            return Principle.DEVELOPMENT
        if best.move_category in _CENTER_CATEGORIES and played.move_category in (
            MoveCategory.FLANK_PAWN_PUSH, MoveCategory.KNIGHT_RETREAT, MoveCategory.BISHOP_RETREAT
        ):
            return Principle.CENTRAL_CONTROL

    if len(played.hanging_ours) > len(best.hanging_ours):
        return Principle.PIECE_SAFETY
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


def _is_move_in_book(move_history_including_played: List[str]) -> bool:
    """Check if the played move keeps us within book theory for some opening.

    'In book' means the entire move sequence so far is a prefix of a known
    opening's main line or a recognized variation. This is the Scandinavian
    fix: Qxd5 on move 2 is book, so no principle-based critique should fire.

    Returns False if the opening theory data can't be loaded (safe default:
    don't suppress principle checks if we can't prove we're in book).
    """
    if not move_history_including_played:
        return False
    try:
        from services.opening_theory_tree_service import load_theory_tree
        tree = load_theory_tree()
    except Exception:
        return False
    if not tree:
        return False

    total = len(move_history_including_played)

    for opening_key, opening_data in tree.items():
        if not isinstance(opening_data, dict):
            continue
        main_line = opening_data.get("main_line") or []
        if total <= len(main_line) and list(move_history_including_played) == main_line[:total]:
            return True
        # Check variations (moves_from_parent extends the main_line prefix)
        for var_data in (opening_data.get("variations") or {}).values():
            if not isinstance(var_data, dict):
                continue
            var_moves = var_data.get("moves_from_parent") or []
            full_line = main_line + var_moves
            if total <= len(full_line) and list(move_history_including_played) == full_line[:total]:
                return True
    return False


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
    strong_openings: Optional[set] = None,
    player_style: Optional[dict] = None,
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

    # Priority 3: PRINCIPLE_MISS — demand-driven, but theory and personal
    # strength beat generic principle. Gates in order:
    #   (a) Book theory gate — if we're still in book, theory applies.
    #   (b) Personal strength gate — if the user wins with this opening,
    #       they know what they're doing; don't lecture.
    # Tactical misses and walked-into failures still fire (above) because
    # book/strong-opening moves shouldn't actually hang pieces — but if they
    # somehow do, we still flag it.
    if move_history_san is not None:
        full_history = list(move_history_san)
        if not full_history or full_history[-1] != played_san:
            full_history = full_history + [played_san]
        if _is_move_in_book(full_history):
            return MoveCritique(
                deviation_type=DeviationType.ON_PLAN_NUDGE,
                cp_loss=cp_loss,
                played_category=played_facts.move_category,
                best_category=best_facts.move_category,
                played_move_san=played_san,
                best_move_san=best_san,
                notes=["in opening book — theory applies, not generic principles"],
            )

    # (b) Personal strength gate — user plays this opening well.
    # Only applies when we've detected an opening name AND it matches the
    # user's strong set. Protects against false positives for small cp_loss
    # deviations in lines the user has proven they understand.
    if strong_openings and played_facts.opening_name and cp_loss < 80:
        try:
            from services.player_performance import is_strong_opening
            if is_strong_opening(played_facts.opening_name, strong_openings):
                return MoveCritique(
                    deviation_type=DeviationType.ON_PLAN_NUDGE,
                    cp_loss=cp_loss,
                    played_category=played_facts.move_category,
                    best_category=best_facts.move_category,
                    played_move_san=played_san,
                    best_move_san=best_san,
                    notes=[f"strong personal record in {played_facts.opening_name}"],
                )
        except Exception:
            pass

    # (c) Style match gate — move fits the user's established style.
    # Attacking players get credit for aggressive moves (captures, checks,
    # new threats). Positional players get credit for quiet piece repositioning.
    # Only small cp deviations — real blunders still flagged regardless of style.
    if player_style and cp_loss < 60:
        is_aggressive_move = (
            played_facts.is_check
            or played_facts.is_capture
            or len([t for t in played_facts.new_threats if t.is_new]) > 0
        )
        is_quiet_move = (
            not played_facts.is_check
            and not played_facts.is_capture
            and len(played_facts.new_threats) == 0
        )
        if player_style.get("is_attacking") and is_aggressive_move:
            return MoveCritique(
                deviation_type=DeviationType.ON_PLAN_NUDGE,
                cp_loss=cp_loss,
                played_category=played_facts.move_category,
                best_category=best_facts.move_category,
                played_move_san=played_san,
                best_move_san=best_san,
                notes=["matches your attacking style"],
            )
        if player_style.get("is_positional") and is_quiet_move:
            return MoveCritique(
                deviation_type=DeviationType.ON_PLAN_NUDGE,
                cp_loss=cp_loss,
                played_category=played_facts.move_category,
                best_category=best_facts.move_category,
                played_move_san=played_san,
                best_move_san=best_san,
                notes=["matches your positional style"],
            )

    # Ask the POSITION what it's demanding (not what shape the best move has).
    # Then check whether played serves that demand while best does.
    try:
        from services.position_demands import dominant_demand
        demand = dominant_demand(board_before, min_urgency=0.4)
    except Exception:
        demand = None

    if demand is not None:
        best_serves = _move_serves_principle(best_facts, demand.principle)
        played_serves = _move_serves_principle(played_facts, demand.principle)
        if best_serves and not played_serves:
            return MoveCritique(
                deviation_type=DeviationType.PRINCIPLE_MISS,
                teaching_focus=demand.principle,
                cp_loss=cp_loss,
                played_category=played_facts.move_category,
                best_category=best_facts.move_category,
                played_move_san=played_san,
                best_move_san=best_san,
                notes=[demand.evidence],
            )
    # If no principle is urgent enough to teach about, we don't invent one.
    # The move will fall through to ON_PLAN_NUDGE or DIRECTIONLESS below —
    # which policy silences for medium/focused bands. Silence is the right
    # answer when the position isn't asking for anything specific.

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
