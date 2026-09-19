"""High-precision stored-best candidates for core opening principles."""
from __future__ import annotations

from typing import Optional

import chess

from services.concept_detectors.missed_gate import (
    engine_move,
    missed_is_allowed,
)
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


def _is_centre_push(board: chess.Board, move: chess.Move,
                    color: chess.Color) -> bool:
    piece = board.piece_at(move.from_square)
    if not piece or piece.color != color or piece.piece_type != chess.PAWN:
        return False
    home = {chess.D2, chess.E2} if color == chess.WHITE else {chess.D7, chess.E7}
    centre = {chess.D4, chess.E4} if color == chess.WHITE else {chess.D5, chess.E5}
    return move.from_square in home and move.to_square in centre


def _missed_or_none(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int],
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
    cp_loss: Optional[int],
    mate_info: Optional[dict],
    predicate,
) -> Optional[str]:
    """"wrong" when the ENGINE's move was this concept and the player's was a
    real mistake.

    _eligible() fails for several reasons -- wrong turn, past move 15, an
    illegal stored move, or simply that the player did not find the engine's
    move. Only the last of those is a missed concept, so every other condition
    is re-checked here rather than assumed.

    See docs/missed_concept_scope.md.
    """
    if move_number is None or move_number > 15:
        return None
    if board_before.turn != user_color or move not in board_before.legal_moves:
        return None
    best = engine_move(board_before, best_move_san, best_move_uci)
    if best is None or best == move:
        return None
    if not predicate(board_before, best, user_color):
        return None
    # They DID the concept, just not on the engine's square: played Nc3 where
    # the engine wanted Nbd2 is two knight developments, and "you missed
    # development" is simply false. The lesson there is the square, which is a
    # different claim we are not making.
    if predicate(board_before, move, user_color):
        return None
    if not missed_is_allowed(board_before, move, cp_loss, mate_info):
        return None
    # The runner's vocabulary is "applied" / "missed"; it maps "missed" to the
    # "wrong" outcome itself. Returning "wrong" here is silently dropped.
    return "missed"


def detect_opening_castling_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    cp_loss: Optional[int] = None,
    mate_info: Optional[dict] = None,
) -> Optional[str]:
    if not _eligible(
        board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    ):
        # Not the engine's move -- the only remaining question is whether the
        # engine's move was the concept and this one was a real mistake.
        return _missed_or_none(
            board_before, move, user_color, move_number,
            best_move_san, best_move_uci, cp_loss, mate_info,
            lambda b, mv, col: b.is_castling(mv),
        )
    return "applied" if board_before.is_castling(move) else None


def detect_opening_center_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    cp_loss: Optional[int] = None,
    mate_info: Optional[dict] = None,
) -> Optional[str]:
    if not _eligible(
        board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    ):
        return _missed_or_none(
            board_before, move, user_color, move_number,
            best_move_san, best_move_uci, cp_loss, mate_info,
            _is_centre_push,
        )
    return "applied" if _is_centre_push(board_before, move, user_color) else None


def detect_opening_development_with_tempo_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    cp_loss: Optional[int] = None,
    mate_info: Optional[dict] = None,
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
