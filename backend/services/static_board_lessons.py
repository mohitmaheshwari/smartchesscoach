"""Depth-free lessons for mistakes the tactical net cannot explain.

Step 2 of the ladder agreed with Mohit 2026-09-24:

    1. tactical net   -- 8 candidate lines both directions + the ~30 proof
                         modules (fork, trapped, pin/skewer, hanging, mate,
                         deflection, ...). If it fires, teach the tactic.
    2. STATIC checks  -- this module.
    3. neither fires  -- say nothing. Not a fallback sentence, not a
                         principle from a bank. Silence.

Why this layer exists
---------------------
Measured over 300 engine-confirmed mistakes the tactical net could not
explain, roughly a third are things a human coach would comment on without
hesitating: a piece still on its starting square, a king still in the middle,
a knight with nowhere to go. Without this layer all of that falls into step 3
and we go silent on exactly the material a 1200 most needs.

Two properties every check here must have
-----------------------------------------
DEPTH-FREE. These are board facts, recomputed identically at depth 0 and
depth 40. That matters because 25% of line-derived lessons changed when the
same search ran 6 plies deeper (measured 2026-09-24, single-threaded). A
lesson that moves when the engine thinks longer is not a lesson.

COMPARATIVE. Every check asks what the PLAYED move did that the ENGINE'S move
did not. A bare observation ("your knight is on the rim") is true of countless
fine positions and teaches nothing. Anchoring to the engine's own choice is
what makes the claim about this move rather than about chess in general, and
it is the part that is engine-backed.

None of these claims that the static fact CAUSED the evaluation drop. The
engine established the move was a mistake; this layer says what visibly
differs. Keep that distinction in the wording.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess

from services.caption_facts import PIECE_VALUE_CP

HOME_SQUARES: Dict[tuple, set] = {
    (chess.WHITE, chess.KNIGHT): {chess.B1, chess.G1},
    (chess.WHITE, chess.BISHOP): {chess.C1, chess.F1},
    (chess.WHITE, chess.ROOK): {chess.A1, chess.H1},
    (chess.BLACK, chess.KNIGHT): {chess.B8, chess.G8},
    (chess.BLACK, chess.BISHOP): {chess.C8, chess.F8},
    (chess.BLACK, chess.ROOK): {chess.A8, chess.H8},
}

# Biggest first. As in punishment_resolver, this order is a claim about chess
# (a king in the middle outranks a stacked pawn), not the order someone
# happened to author them in.
LESSON_RANK: tuple = (
    "KING_IN_THE_MIDDLE",
    "PIECE_STILL_ASLEEP",
    "PIECE_HAS_NOWHERE_TO_GO",
    "PAWNS_STACKED",
)


@dataclass
class StaticLesson:
    kind: str
    piece: Optional[str] = None
    square: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "piece": self.piece,
                "square": self.square, **self.detail}


def _asleep(board: chess.Board, colour: bool) -> List[int]:
    """Our knights/bishops/rooks still sitting on their starting squares."""
    out = []
    for (col, ptype), squares in HOME_SQUARES.items():
        if col != colour:
            continue
        for sq in squares:
            piece = board.piece_at(sq)
            if piece and piece.color == colour and piece.piece_type == ptype:
                out.append(sq)
    return out


def _safe_destinations(board: chess.Board, square: int, owner: bool) -> int:
    """How many squares this piece can go to without simply being won."""
    piece = board.piece_at(square)
    if piece is None:
        return 0
    value = PIECE_VALUE_CP.get(piece.piece_type, 0)
    n = 0
    for mv in board.legal_moves:
        if mv.from_square != square:
            continue
        probe = board.copy(stack=False)
        probe.push(mv)
        attackers = probe.attackers(not owner, mv.to_square)
        if not attackers:
            n += 1
            continue
        cheapest = min(PIECE_VALUE_CP.get(probe.piece_at(s).piece_type, 0)
                       for s in attackers if probe.piece_at(s) is not None)
        if cheapest >= value and probe.attackers(owner, mv.to_square):
            n += 1
    return n


def _stacked(board: chess.Board, colour: bool) -> int:
    files: Dict[int, int] = {}
    for sq, piece in board.piece_map().items():
        if piece.color == colour and piece.piece_type == chess.PAWN:
            f = chess.square_file(sq)
            files[f] = files.get(f, 0) + 1
    return sum(v - 1 for v in files.values() if v > 1)


def detect(fen_before: str, played_san: str,
           best_san: Optional[str]) -> Optional[StaticLesson]:
    """What did the played move leave undone that the engine's move did not?

    Returns the highest-ranked static difference, or None. None is a real
    answer -- it means step 3, silence.
    """
    if not (fen_before and played_san and best_san):
        return None
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(played_san)
        best = board.parse_san(best_san)
    except (ValueError, AssertionError, KeyError):
        return None
    mover = board.piece_at(played.from_square)
    if mover is None:
        return None
    us = mover.color

    after_played = board.copy(stack=False)
    after_played.push(played)
    after_best = board.copy(stack=False)
    after_best.push(best)

    found: Dict[str, StaticLesson] = {}

    # --- king still in the middle, and the engine wanted to castle ---------
    if board.is_castling(best) and not board.is_castling(played):
        king_sq = after_played.king(us)
        if king_sq is not None:
            found["KING_IN_THE_MIDDLE"] = StaticLesson(
                "KING_IN_THE_MIDDLE", "king", chess.square_name(king_sq),
                {"castle_move": best_san})

    # --- a piece still on its starting square, and the engine moved it -----
    asleep_before = set(_asleep(board, us))
    if best.from_square in asleep_before and played.from_square not in asleep_before:
        piece = board.piece_at(best.from_square)
        still = sorted(asleep_before - {best.from_square})
        found["PIECE_STILL_ASLEEP"] = StaticLesson(
            "PIECE_STILL_ASLEEP", chess.piece_name(piece.piece_type),
            chess.square_name(best.from_square),
            {"engine_move": best_san,
             "others_still_home": [chess.square_name(s) for s in still]})

    # --- one of our pieces has (nearly) nowhere safe to go ----------------
    # Comparative: bad after the played move, and not after the engine's.
    for sq, piece in after_played.piece_map().items():
        if piece.color != us or piece.piece_type in (chess.KING, chess.PAWN):
            continue
        # A piece with no safe squares that nobody is attacking is not in
        # trouble -- it is just modestly placed. Without this the check fired
        # on 21.5% of GOOD moves (measured 2026-09-24), because by the
        # cheaper-attacker test a queen has almost no "safe" square in any
        # normal position. Require it to actually be under attack.
        if not after_played.attackers(not us, sq):
            continue
        if _safe_destinations(after_played, sq, us) > 0:
            continue
        # does the engine's move leave that same piece with somewhere to go?
        same = after_best.piece_at(sq)
        if same is not None and same.color == us and same.piece_type == piece.piece_type:
            if _safe_destinations(after_best, sq, us) == 0:
                continue          # stuck either way -- not about this move
        cur = found.get("PIECE_HAS_NOWHERE_TO_GO")
        val = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if cur is None or val > cur.detail.get("value_cp", 0):
            found["PIECE_HAS_NOWHERE_TO_GO"] = StaticLesson(
                "PIECE_HAS_NOWHERE_TO_GO", chess.piece_name(piece.piece_type),
                chess.square_name(sq), {"value_cp": val})

    # --- the played move stacks our pawns and the engine's does not -------
    sp, sb = _stacked(after_played, us), _stacked(after_best, us)
    if sp > sb:
        found["PAWNS_STACKED"] = StaticLesson(
            "PAWNS_STACKED", "pawn", None,
            {"extra_stacked": sp - sb})

    for kind in LESSON_RANK:
        if kind in found:
            return found[kind]
    return None
