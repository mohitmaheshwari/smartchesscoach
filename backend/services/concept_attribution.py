"""
Concept Attribution — from "this was on the board" to "you did this"
====================================================================

`board_concepts` answers *which named concept is live in a position*. That is not
the same as a diagnosis: the rule of the square being on the board does not mean
the player failed it. This module closes that gap.

THE TEST EVERY ATTRIBUTION MUST PASS
------------------------------------
A move is only blamed for a concept when BOTH hold:

  1. the move made it worse — the concept's outcome flipped against the mover
     as a direct result of this move, and
  2. it was avoidable — at least one legal alternative did not flip it.

Clause 2 is what stops the coach blaming a player for a lost position. If every
move lets the pawn through, letting the pawn through is not the mistake.

WHY IT IS CONSERVATIVE
----------------------
A wrong name is worse than no name: "you didn't apply the rule of the square"
about a position where that was never the issue destroys trust faster than
`generic_endgame_slip` ever did. Every predicate here is silent when the geometry
is ambiguous, and every one is deterministic — no engine, no eval, no model.
"""

import logging
from typing import Any, Dict, List, Optional

import chess

from services.board_concepts import (
    _passed_pawns,
    _path_clear,
    _steps_to_promote,
    back_rank_weakness,
    newly_trapped_pieces,
    opposition,
)

logger = logging.getLogger(__name__)

# Checking "did a safe alternative exist?" costs one detector run per legal move.
# In an endgame that is cheap; in a crowded middlegame it is not, and these
# concepts are endgame-shaped anyway.
MAX_ALTERNATIVES = 60


def _pawn_is_catchable(board: chess.Board, pawn_sq: int, color: chess.Color) -> Optional[bool]:
    """Can `color`'s opponent king catch this passed pawn? None if the question
    does not apply (pawn is blocked, or there is no king)."""
    if not _path_clear(board, pawn_sq, color):
        return None
    king_sq = board.king(not color)
    if king_sq is None:
        return None
    steps = _steps_to_promote(pawn_sq, color)
    promo_sq = chess.square(chess.square_file(pawn_sq), 7 if color == chess.WHITE else 0)
    tempo = 1 if board.turn == (not color) else 0
    return chess.square_distance(king_sq, promo_sq) <= steps + tempo


def _enemy_runners(board: chess.Board, me: chess.Color) -> Dict[int, bool]:
    """Every enemy passed pawn -> can my king catch it."""
    out = {}
    for sq in _passed_pawns(board, not me):
        catchable = _pawn_is_catchable(board, sq, not me)
        if catchable is not None:
            out[sq] = catchable
    return out


def _let_a_pawn_through(board: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
    """Did this move turn a catchable enemy passer into an uncatchable one?"""
    me = board.turn
    before = _enemy_runners(board, me)
    if not any(before.values()):
        return None  # nothing was catchable, so nothing was lost here

    after_board = board.copy(stack=False)
    after_board.push(move)
    after = _enemy_runners(after_board, me)

    escaped = [
        sq for sq, was_catchable in before.items()
        if was_catchable and after.get(sq) is False
    ]
    if not escaped:
        return None

    # Avoidable? Did any legal alternative keep every one of them catchable.
    for alt in list(board.legal_moves)[:MAX_ALTERNATIVES]:
        if alt == move:
            continue
        alt_board = board.copy(stack=False)
        alt_board.push(alt)
        alt_state = _enemy_runners(alt_board, me)
        if all(alt_state.get(sq) is not False for sq in escaped):
            pawn_sq = escaped[0]
            return {
                "concept": "rule_of_square",
                "failure": "let_the_pawn_through",
                "pawn_square": chess.square_name(pawn_sq),
                "promotion_square": chess.square_name(
                    chess.square(chess.square_file(pawn_sq), 0 if me == chess.WHITE else 7)
                ),
                "avoidable_with": alt.uci(),
                "squares": [chess.square_name(pawn_sq)],
            }
    return None


def _surrendered_the_opposition(board: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
    """In a king-and-pawn ending, did a king move that could have taken the
    opposition go unplayed?

    Only fires when the position is genuinely an opposition question: kings and
    pawns only. With pieces on, the opposition is rarely the lesson.
    """
    if any(board.pieces(pt, c)
           for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
           for c in (chess.WHITE, chess.BLACK)):
        return None

    me = board.turn
    me_name = "white" if me == chess.WHITE else "black"

    def takes_it(mv: chess.Move) -> bool:
        nb = board.copy(stack=False)
        nb.push(mv)
        opp = opposition(nb)
        return bool(opp and opp["held_by"] == me_name)

    if takes_it(move):
        return None  # they took it

    winner = next((mv for mv in board.legal_moves if takes_it(mv)), None)
    if winner is None:
        return None  # it was not available; not a failure

    return {
        "concept": "opposition",
        "failure": "surrendered_the_opposition",
        "available_with": winner.uci(),
        "played": move.uci(),
        "squares": [chess.square_name(board.king(me))] if board.king(me) is not None else [],
    }


def _allowed_back_rank_mate(board: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
    """Did this move hand the opponent a mate on the mover's back rank?"""
    me = board.turn
    back_rank = 0 if me == chess.WHITE else 7

    def mate_on_back_rank(b: chess.Board) -> Optional[chess.Move]:
        for mv in b.legal_moves:
            if chess.square_rank(mv.to_square) != back_rank:
                continue
            b.push(mv)
            mated = b.is_checkmate()
            b.pop()
            if mated:
                return mv
        return None

    after = board.copy(stack=False)
    after.push(move)
    threat = mate_on_back_rank(after)
    if threat is None:
        return None

    # Avoidable? Any legal alternative with no such mate.
    for alt in list(board.legal_moves)[:MAX_ALTERNATIVES]:
        if alt == move:
            continue
        ab = board.copy(stack=False)
        ab.push(alt)
        if mate_on_back_rank(ab) is None:
            weak = back_rank_weakness(after, me)
            return {
                "concept": "back_rank",
                "failure": "allowed_back_rank_mate",
                "mating_move": threat.uci(),
                "avoidable_with": alt.uci(),
                "had_luft": bool(weak is None),
                "squares": [chess.square_name(threat.to_square)],
            }
    return None


def _trapped_own_piece(board: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
    """Did this move walk one of the mover's own pieces into a trap?"""
    fresh = newly_trapped_pieces(board, move)
    if not fresh:
        return None

    for alt in list(board.legal_moves)[:MAX_ALTERNATIVES]:
        if alt == move:
            continue
        if not newly_trapped_pieces(board, alt):
            t = fresh[0]
            return {
                "concept": "trapped_piece",
                "failure": "trapped_own_piece",
                "piece": t["piece"],
                "square": t["square"],
                "cost_cp": t["cost_cp"],
                "avoidable_with": alt.uci(),
                "squares": [t["square"]],
            }
    return None


ATTRIBUTORS = (
    _let_a_pawn_through,
    _allowed_back_rank_mate,
    _trapped_own_piece,
    _surrendered_the_opposition,
)


def attribute(fen_before: str, move_uci: str) -> Optional[Dict[str, Any]]:
    """Name what this move did wrong, or None.

    Returns at most ONE attribution — the first that fires, in severity order
    (a lost pawn race and a mate outrank a surrendered opposition). A move that
    breaks two concepts is still one lesson, and a coach names one thing.
    """
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
    except Exception:
        return None
    if move not in board.legal_moves:
        return None

    for fn in ATTRIBUTORS:
        try:
            hit = fn(board, move)
        except Exception as exc:
            logger.warning("concept_attribution %s failed: %s", fn.__name__, exc)
            continue
        if hit:
            return hit
    return None
