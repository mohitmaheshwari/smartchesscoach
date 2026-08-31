"""High-precision stored-best candidates for core opening principles."""
from __future__ import annotations

from typing import Optional

import chess

from services.concept_detectors.evidence import stored_best_matches


def _eligible(
    board: chess.Board,
    move: chess.Move,
    color: chess.Color,
    move_number: Optional[int],
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
) -> bool:
    return bool(
        move_number is not None
        and move_number <= 15
        and board.turn == color
        and move in board.legal_moves
        and stored_best_matches(board, move, best_move_san, best_move_uci)
    )


def detect_opening_castling_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _eligible(
        board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    ):
        return None
    return "applied" if board_before.is_castling(move) else None


def detect_opening_center_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _eligible(
        board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    ):
        return None
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.color != user_color or piece.piece_type != chess.PAWN:
        return None
    home = {chess.D2, chess.E2} if user_color == chess.WHITE else {chess.D7, chess.E7}
    center = {chess.D4, chess.E4} if user_color == chess.WHITE else {chess.D5, chess.E5}
    return "applied" if move.from_square in home and move.to_square in center else None


def detect_opening_development_with_tempo_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _eligible(
        board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    ):
        return None
    piece = board_before.piece_at(move.from_square)
    home = (
        {chess.B1, chess.G1, chess.C1, chess.F1}
        if user_color == chess.WHITE
        else {chess.B8, chess.G8, chess.C8, chess.F8}
    )
    if (
        not piece
        or piece.color != user_color
        or piece.piece_type not in (chess.KNIGHT, chess.BISHOP)
        or move.from_square not in home
    ):
        return None
    after = board_before.copy(stack=False)
    after.push(move)
    valuable_targets = {
        square
        for target_type in (chess.ROOK, chess.QUEEN, chess.KING)
        for square in after.pieces(target_type, not user_color)
    }
    attacks = after.attacks(move.to_square)
    return "applied" if attacks & valuable_targets else None
