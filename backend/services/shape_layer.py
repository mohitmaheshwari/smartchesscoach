"""
Shape-layer facade (TIER 3 selection logic).

`select_shape_for_position(board, eval_data, shapes_fired_this_game)`
runs the geometric detectors, applies the engine verifier, suppresses
patterns already fired in this game, sorts by priority (HIGHER first),
and returns the single highest-priority surviving pattern as a dict
ready to drop into a per-move output record:

    {
        "pattern_id":   "knight_fork",
        "pattern_name": "Knight Fork",
        "pattern_desc": "Your knight attacks two big pieces at once. They can save only one.",
        "mover":        "c7",
        "targets":      ["a8", "e8"],
        "executing_move": "c7e8",
        "evidence":     "knight jumps to e8 attacking 2 pieces",
    }

Returns None if no pattern passes verification + suppression.

Design notes:
  - Side to move on `board` is treated as 'us'; the pattern fires from
    that side's perspective. Use the pre-move board so the engine's
    best_move_uci aligns naturally with what we detect.
  - Suppression is once-per-game per pattern_id by default (matches the
    TIER 2 caption-principle convention). The caller maintains the set
    and we mutate it on fire.
  - The engine verifier is strict: patterns with executing_move only
    fire if the engine's best move (or top-3 if available) matches.
    Heuristic-only patterns pass through.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set
import chess

from services.shape_detectors import detect_all_shapes, verify_with_engine_data
from services.shape_patterns import PATTERNS_BY_ID


def _is_relevant_to_move(
    ev: Dict,
    played_move: Optional[chess.Move],
    best_move_uci: str,
) -> bool:
    """Move-relevance gate: a pattern fires only when the played move is
    actually INVOLVED in the pattern. Without this, every pattern whose
    geometry holds anywhere on the board surfaces under every move —
    producing teaching that has nothing to do with what the player did.

    Two cases:
      1. Pattern has an executing_move (e.g. a fork move, capture):
         fires if played_move matches (player executed it) OR engine's
         best move matches (player missed it — surface as a lesson).
      2. Pattern is positional (no executing_move): fires if the played
         move's from or to square overlaps mover/targets — i.e., the
         move involves a piece named in the pattern.

    Pattern-specific dynamic checks (mate-in-1 simulation, defended-front,
    capture-by-played-move suppression) now live in verify_dynamics()
    keyed on each pattern's `dynamic_policy` field. This function only
    handles geometric move-relevance.
    """
    ex = ev.get("executing_move")
    played_uci = played_move.uci() if played_move else ""
    if ex:
        return played_uci == ex or best_move_uci == ex
    if played_move is None:
        # No move context — can't gate. Pass through (used for tests).
        return True

    involved: Set[int] = set()
    if ev.get("mover"):
        try:
            mover_val = ev["mover"]
            if isinstance(mover_val, int):
                involved.add(mover_val)
            else:
                involved.add(chess.parse_square(str(mover_val)))
        except Exception:
            pass
    for t in ev.get("targets") or []:
        try:
            if isinstance(t, int):
                involved.add(t)
            else:
                involved.add(chess.parse_square(str(t)))
        except Exception:
            pass
    return played_move.from_square in involved or played_move.to_square in involved


def _coerce_square(s) -> Optional[int]:
    """Best-effort coerce mover/target value to a chess square int."""
    if s is None:
        return None
    if isinstance(s, int):
        return s
    try:
        return chess.parse_square(str(s))
    except Exception:
        return None


def _verify_mate_in_1_simulated(
    ev: Dict,
    board: chess.Board,
    played_move: Optional[chess.Move],
) -> bool:
    """Pattern passes iff some candidate piece has a legal move that
    delivers checkmate against the enemy king. Catches Parth's flagged
    Qd4 false-positive (back-rank-trap geometry but no real mate).
    """
    if board.turn != _own_color(board):
        # We don't have the move — fall through, trust geometry.
        return True
    them = not _own_color(board)
    them_king_sq = board.king(them)
    if them_king_sq is None:
        return True
    back_rank = 7 if them == chess.BLACK else 0
    # Candidates: any of our R/Q (the typical mating pieces). Could extend
    # for knight_mate (knights) etc. by inspecting pattern_id.
    pid = ev.get("pattern_id")
    if pid == "back_rank_trap":
        candidate_types = (chess.ROOK, chess.QUEEN)
    elif pid == "knight_mate":
        candidate_types = (chess.KNIGHT,)
    elif pid == "queen_knight_mate":
        candidate_types = (chess.QUEEN, chess.KNIGHT)
    elif pid == "h7_attack":
        candidate_types = (chess.QUEEN, chess.BISHOP, chess.KNIGHT, chess.ROOK)
    else:
        candidate_types = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
    for piece_type in candidate_types:
        for sq in board.pieces(piece_type, _own_color(board)):
            for move in board.legal_moves:
                if move.from_square != sq:
                    continue
                # For back-rank we constrain landing on the back rank;
                # other mates can land anywhere.
                if pid == "back_rank_trap" and chess.square_rank(move.to_square) != back_rank:
                    continue
                test_board = board.copy()
                test_board.push(move)
                if test_board.is_checkmate():
                    return True
    return False


def _verify_pin_capture_suppress(
    ev: Dict,
    board: chess.Board,
    played_move: Optional[chess.Move],
) -> bool:
    """Suppress pin when the played move captures the pinned front piece.
    The pin geometry exists pre-move but the player just cashes it in as
    a trade — pedagogically misleading to call it a pin afterwards
    (Parth flagged Bxf3 on game 1b196a4f move 12).
    """
    if played_move is None:
        return True
    targets = ev.get("targets") or []
    if not targets:
        return True
    front = _coerce_square(targets[0])
    if front is None:
        return True
    if played_move.to_square == front:
        return False
    return True


def _verify_open_line_move_uses_diagonal(
    ev: Dict,
    board: chess.Board,
    played_move: Optional[chess.Move],
) -> bool:
    """Suppress open_long_line when the played move does not actually USE
    the open diagonal.

    Two gates layered:
      1. to_square must land on the diagonal (introduced 2026-05-19 for
         Mohit's Qxa2 case — queen departed b2 on the a1-h8 diagonal to
         capture on a2; teaching was dishonest).
      2. The moving piece must be a slider that uses diagonals — queen
         or bishop. A knight landing on d4 happens to sit on the
         a1-h8 diagonal but doesn't USE it (Mohit 2026-05-28, game
         65650b2b m20 Nd4: knight to a central square got captioned
         'long diagonal has open squares for your queen or bishop to
         use' — the moved piece can't use it). Same for a rook landing
         on a long-diagonal square: it's not the rook's line. The
         teaching is for sliders, not knights/rooks/kings.
    """
    if played_move is None:
        return True
    targets = ev.get("targets") or []
    if not targets:
        return True
    diag_squares: set = set()
    for t in targets:
        sq = _coerce_square(t)
        if sq is not None:
            diag_squares.add(sq)
    # Gate 1: must land on the diagonal.
    if played_move.to_square not in diag_squares:
        return False
    # Gate 2: must be a diagonal-using slider. Look at the from-square
    # piece (pre-push), since board is the position before played_move.
    moving_piece = board.piece_at(played_move.from_square)
    if moving_piece is None:
        return True  # defensive; can't tell — let geometry decide
    return moving_piece.piece_type in (chess.QUEEN, chess.BISHOP)


def _verify_skewer_front_defended(
    ev: Dict,
    board: chess.Board,
    played_move: Optional[chess.Move],
) -> bool:
    """Require the front piece (targets[0]) to be defended unless it's the
    king. An undefended front piece means our slider just captures it for
    free — there's no "forces opponent to move" dilemma. Parth flagged
    Qxd2 (game 1b196a4f move 14) where black bishop on d2 was hanging.
    """
    if played_move is None:
        # No move context; let geometric detector decide.
        return True
    targets = ev.get("targets") or []
    if not targets:
        return True
    front = _coerce_square(targets[0])
    if front is None:
        return True
    piece = board.piece_at(front)
    if piece is None:
        return True
    if piece.piece_type == chess.KING:
        return True  # check-skewers: forced-move comes from check, not defender
    # Also suppress if the played move captures the front piece (covers
    # the case Parth flagged: Qxd2 captured a hanging bishop).
    if played_move.to_square == front:
        return False
    them = piece.color
    defenders = board.attackers(them, front)
    if not defenders:
        return False  # hanging — not a tactical skewer
    return True


# Dispatcher: each pattern's `dynamic_policy` maps to a verifier function.
# Patterns without a policy (or with "geometry_only") pass through.
# When a new bug class is identified, add a new policy here AND set the
# field on the relevant entries in shape_patterns.py.
_DYNAMIC_POLICY_VERIFIERS = {
    "mate_in_1_simulated":           _verify_mate_in_1_simulated,
    "pin_capture_suppress":          _verify_pin_capture_suppress,
    "skewer_front_defended":         _verify_skewer_front_defended,
    "open_line_move_uses_diagonal":  _verify_open_line_move_uses_diagonal,
}


def verify_dynamics(
    candidates: List[Dict],
    board: chess.Board,
    played_move: Optional[chess.Move],
) -> List[Dict]:
    """Filter candidates by their pattern's dynamic_policy. A pattern
    survives only if its policy's verifier returns True (or no policy
    is declared — defaults to geometry_only / pass-through).
    """
    out: List[Dict] = []
    for ev in candidates:
        spec = PATTERNS_BY_ID.get(ev.get("pattern_id", ""), {})
        policy = spec.get("dynamic_policy", "geometry_only")
        verifier = _DYNAMIC_POLICY_VERIFIERS.get(policy)
        if verifier is None:
            out.append(ev)  # geometry_only / unknown policy → pass through
            continue
        try:
            if verifier(ev, board, played_move):
                out.append(ev)
        except Exception as e:
            # Defensive: a buggy verifier shouldn't crash the pipeline.
            # Fall back to passing the candidate through.
            out.append(ev)
    return out


def _own_color(board: chess.Board) -> chess.Color:
    return board.turn


def select_shape_for_position(
    board: chess.Board,
    eval_data: Optional[Dict] = None,
    shapes_fired_this_game: Optional[Set[str]] = None,
    prev_move: Optional[chess.Move] = None,
) -> Optional[Dict]:
    """Return the single highest-priority shape pattern this move surfaces,
    or None. `shapes_fired_this_game` is mutated on fire so duplicates don't
    repeat across the rest of the game.
    """
    if shapes_fired_this_game is None:
        shapes_fired_this_game = set()

    try:
        candidates = detect_all_shapes(board, prev_move=prev_move)
    except Exception:
        return None
    if not candidates:
        return None

    # Move-relevance gate: only surface patterns where the played move is
    # actually involved. Without this, a pin/fork/discovery on the other
    # side of the board fires under a routine developing move. The user's
    # move-4 Nf6 firing back_rank_trap and hidden_attack was exactly this.
    best_move_uci = (eval_data or {}).get("best_move_uci", "") if eval_data else ""
    candidates = [ev for ev in candidates if _is_relevant_to_move(ev, prev_move, best_move_uci)]
    if not candidates:
        return None

    # Dynamic-policy gate: each pattern's `dynamic_policy` (declared in
    # shape_patterns.py) controls a per-class semantic check beyond static
    # geometry. Added 2026-05-15 to centralize the back_rank_trap mate-in-1
    # check, pin capture-suppress, and skewer defended-front check that
    # Parth's bug round surfaced. See verify_dynamics().
    candidates = verify_dynamics(candidates, board, prev_move)
    if not candidates:
        return None

    # Engine verifier (best/top_3/heuristic) filtering.
    verified = verify_with_engine_data(candidates, eval_data)
    if not verified:
        return None

    # Suppress patterns already fired this game.
    verified = [ev for ev in verified if ev["pattern_id"] not in shapes_fired_this_game]
    if not verified:
        return None

    # Sort: HIGHER priority number wins (opposite of caption principles).
    def _prio(ev):
        spec = PATTERNS_BY_ID.get(ev["pattern_id"], {})
        return -spec.get("priority", 0)
    verified.sort(key=_prio)

    top = verified[0]
    spec = PATTERNS_BY_ID.get(top["pattern_id"], {})
    shapes_fired_this_game.add(top["pattern_id"])

    return {
        "pattern_id":     top["pattern_id"],
        "pattern_name":   spec.get("name", ""),
        "pattern_desc":   spec.get("description", ""),
        "mover":          top.get("mover"),
        "targets":        top.get("targets", []),
        "executing_move": top.get("executing_move"),
        "evidence":       top.get("evidence", ""),
    }


def tally_shapes_across_games(
    per_move_records_by_game: List[List[Dict]],
) -> List[Dict]:
    """Aggregate shape-pattern fires across a list of games (each game is a
    list of per-move records that already contain `shape_pattern_id`).
    Returns a list of dicts sorted by frequency:

        [{"pattern_id": "free_piece", "name": "Free Piece",
          "description": "...", "count": 7, "games": 4}, ...]

    Used by Pattern-of-the-Day on the home dashboard.
    """
    from collections import Counter
    pattern_counts = Counter()
    pattern_games = {}
    for game_records in per_move_records_by_game:
        seen_this_game = set()
        for rec in game_records:
            pid = rec.get("shape_pattern_id")
            if not pid:
                continue
            pattern_counts[pid] += 1
            seen_this_game.add(pid)
        for pid in seen_this_game:
            pattern_games[pid] = pattern_games.get(pid, 0) + 1

    out = []
    for pid, count in pattern_counts.most_common():
        spec = PATTERNS_BY_ID.get(pid, {})
        out.append({
            "pattern_id":  pid,
            "name":        spec.get("name", ""),
            "description": spec.get("description", ""),
            "count":       count,
            "games":       pattern_games.get(pid, 0),
        })
    return out
