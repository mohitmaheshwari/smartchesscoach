"""Shared independent legal-capture minimax for puzzle proof adapters."""

from __future__ import annotations

from typing import Optional

import chess

from services.caption_facts import PIECE_VALUE_CP


VERIFIER_VERSION = "legal_exchange_verifier.v1"


def captured_value_cp(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUE_CP[chess.PAWN]
    piece = board.piece_at(move.to_square)
    return PIECE_VALUE_CP.get(piece.piece_type, 0) if piece else 0


def promotion_gain_cp(move: chess.Move) -> int:
    if move.promotion is None:
        return 0
    return PIECE_VALUE_CP.get(move.promotion, 0) - PIECE_VALUE_CP[chess.PAWN]


def independent_exchange_gain(
    board: chess.Board,
    target_square: int,
    forced_first: Optional[chess.Move] = None,
) -> int:
    """Return the side-to-move's best net gain in captures on one square."""

    def reply_gain(work: chess.Board, depth: int = 0) -> int:
        if depth > 32:
            return 0
        best = 0
        for move in list(work.legal_moves):
            if move.to_square != target_square or not work.is_capture(move):
                continue
            immediate = captured_value_cp(work, move) + promotion_gain_cp(move)
            after = work.copy(stack=False)
            after.push(move)
            best = max(best, immediate - reply_gain(after, depth + 1))
        return best

    if forced_first is None:
        return reply_gain(board)
    if (
        forced_first not in board.legal_moves
        or forced_first.to_square != target_square
        or not board.is_capture(forced_first)
    ):
        raise ValueError("forced verifier move is not a legal target capture")
    immediate = captured_value_cp(board, forced_first) + promotion_gain_cp(forced_first)
    after = board.copy(stack=False)
    after.push(forced_first)
    return immediate - reply_gain(after, 1)


__all__ = [
    "VERIFIER_VERSION",
    "captured_value_cp",
    "independent_exchange_gain",
    "promotion_gain_cp",
]
