"""High-precision positive candidates for coach-level chess principles.

Every detector here requires the played move to equal the already-stored
Stockfish best move. The detector then proves only a board fact. These
candidates remain Shadow until corpus replay and blind semantic review.
"""
from __future__ import annotations

from typing import Optional

import chess

from services.cognitive_gap_subtypes import _is_endgame_board
from services.concept_detectors.evidence import stored_best_matches
from services.concept_detectors.missed_gate import engine_move, missed_is_allowed


def _after(board: chess.Board, move: chess.Move) -> chess.Board:
    result = board.copy(stack=False)
    result.push(move)
    return result


def _is_passed_pawn(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    for enemy_square in board.pieces(chess.PAWN, not color):
        enemy_file = chess.square_file(enemy_square)
        enemy_rank = chess.square_rank(enemy_square)
        if abs(enemy_file - file_index) > 1:
            continue
        if color == chess.WHITE and enemy_rank > rank_index:
            return False
        if color == chess.BLACK and enemy_rank < rank_index:
            return False
    return True


def _is_development(board: chess.Board, move: chess.Move,
                    color: chess.Color) -> bool:
    piece = board.piece_at(move.from_square)
    if not piece or piece.color != color:
        return False
    home = ({chess.B1, chess.G1, chess.C1, chess.F1} if color == chess.WHITE
            else {chess.B8, chess.G8, chess.C8, chess.F8})
    return (piece.piece_type in (chess.KNIGHT, chess.BISHOP)
            and move.from_square in home)


def _is_king_centralizing(board: chess.Board, move: chess.Move,
                          color: chess.Color) -> bool:
    piece = board.piece_at(move.from_square)
    if not piece or piece.color != color or piece.piece_type != chess.KING:
        return False
    centre = (chess.D4, chess.E4, chess.D5, chess.E5)
    return (min(chess.square_distance(move.to_square, sq) for sq in centre)
            < min(chess.square_distance(move.from_square, sq) for sq in centre))


def _missed(board_before, move, user_color, best_move_san, best_move_uci,
            cp_loss, mate_info, predicate) -> Optional[str]:
    """"wrong" when the ENGINE's move was this concept and the player's move
    was a real mistake. See docs/missed_concept_scope.md."""
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


def detect_coached_development_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    cp_loss: Optional[int] = None,
    mate_info: Optional[dict] = None,
) -> Optional[str]:
    if move_number is None or move_number > 15:
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return _missed(board_before, move, user_color, best_move_san,
                       best_move_uci, cp_loss, mate_info, _is_development)
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.color != user_color:
        return None
    home_squares = (
        {chess.B1, chess.G1, chess.C1, chess.F1}
        if user_color == chess.WHITE
        else {chess.B8, chess.G8, chess.C8, chess.F8}
    )
    if (
        piece.piece_type in (chess.KNIGHT, chess.BISHOP)
        and move.from_square in home_squares
    ):
        return "applied"
    return None


def detect_endgame_king_centralization_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
    cp_loss: Optional[int] = None,
    mate_info: Optional[dict] = None,
) -> Optional[str]:
    if not _is_endgame_board(board_before):
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return _missed(board_before, move, user_color, best_move_san,
                       best_move_uci, cp_loss, mate_info, _is_king_centralizing)
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.color != user_color or piece.piece_type != chess.KING:
        return None
    center = (chess.D4, chess.E4, chess.D5, chess.E5)
    before = min(chess.square_distance(move.from_square, sq) for sq in center)
    after = min(chess.square_distance(move.to_square, sq) for sq in center)
    return "applied" if after < before else None


def detect_endgame_create_passed_pawn_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _is_endgame_board(board_before):
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return None
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.color != user_color or piece.piece_type != chess.PAWN:
        return None
    was_passed = _is_passed_pawn(board_before, move.from_square, user_color)
    board_after = _after(board_before, move)
    promoted = board_after.piece_at(move.to_square)
    if not promoted or promoted.piece_type != chess.PAWN:
        return None
    is_passed = _is_passed_pawn(board_after, move.to_square, user_color)
    return "applied" if is_passed and not was_passed else None


def _rook_is_active(
    board: chess.Board,
    rook_square: chess.Square,
    color: chess.Color,
) -> bool:
    file_index = chess.square_file(rook_square)
    file_has_pawn = any(
        chess.square_file(square) == file_index
        for square in board.pieces(chess.PAWN, chess.WHITE)
        | board.pieces(chess.PAWN, chess.BLACK)
    )
    seventh_rank = 6 if color == chess.WHITE else 1
    return not file_has_pawn or chess.square_rank(rook_square) == seventh_rank


def detect_endgame_active_rook_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _is_endgame_board(board_before):
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return None
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.color != user_color or piece.piece_type != chess.ROOK:
        return None
    before = _rook_is_active(board_before, move.from_square, user_color)
    board_after = _after(board_before, move)
    after = _rook_is_active(board_after, move.to_square, user_color)
    return "applied" if after and not before else None


def detect_endgame_stop_promotion_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    if not _is_endgame_board(board_before):
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return None
    opponent = not user_color
    urgent = []
    for square in board_before.pieces(chess.PAWN, opponent):
        rank = chess.square_rank(square)
        advanced = rank >= 5 if opponent == chess.WHITE else rank <= 2
        if advanced and _is_passed_pawn(board_before, square, opponent):
            urgent.append(square)
    if not urgent:
        return None

    if board_before.is_capture(move) and move.to_square in urgent:
        return "applied"
    board_after = _after(board_before, move)
    for pawn_square in urgent:
        if board_after.piece_at(pawn_square) is None:
            continue
        step = 8 if opponent == chess.WHITE else -8
        block_square = pawn_square + step
        if not 0 <= block_square < 64:
            continue
        blocker = board_after.piece_at(block_square)
        if blocker and blocker.color == user_color:
            return "applied"
    return None
