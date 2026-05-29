"""
Lucena position detector.

Lucena = winning K+R+P vs K+R when the attacker's pawn is on the 7th
rank, attacker's king is in front of the pawn, and the defender's
rook is cutting off the attacker's king on the file beside the pawn.
The winning technique is "building a bridge" with the rook so the
king can escape the checks and the pawn promotes.

Canonical setup (white to move, white's pawn on c7, white's king on
c8, black's rook on c-file or nearby):

    8/2K5/2P5/8/8/8/4r3/4R3 w - - 0 1
    (white Rd1->d4 builds the bridge)

This is a very specific endgame. We grade two things:

    Pre-condition ("clean test"):
      - User's move
      - Only K+R+P (user) vs K+R (opponent) on the board
      - User's pawn is on the 7th rank from the user's POV
      - User's king is on the promotion square OR the file of the pawn,
        ahead of the pawn
      - The pawn is NOT a rook pawn (a/h files — Lucena fails there)

    Grade:
      - User plays a rook move that lands on the 4th rank (from user's
        POV) along the file adjacent to the pawn — the classic bridge-
        building setup move                                          → "applied"
      - User pushes the pawn (premature) or moves the king while a
        bridge-building rook move was on the board                   → "missed"
      - Otherwise                                                    → None
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_endgame_lucena_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    if board_before.turn != user_color:
        return None
    if not _is_lucena_test_position(board_before, user_color):
        return None

    user_pawn_sq = next(iter(board_before.pieces(chess.PAWN, user_color)))
    pawn_file = chess.square_file(user_pawn_sq)
    if pawn_file in (0, 7):
        # Rook-pawn Lucena doesn't win; skip the test.
        return None

    bridge_rank = 3 if user_color == chess.WHITE else 4
    # Adjacent file — the file the defender's rook tends to be on.
    # For c-pawn, bridge file is e (skipping d which is between).
    bridge_file_offset = +2 if pawn_file < 4 else -2
    bridge_file = pawn_file + bridge_file_offset
    if not (0 <= bridge_file <= 7):
        return None
    bridge_square = chess.square(bridge_file, bridge_rank)

    moved = board_before.piece_at(move.from_square)
    if moved is None:
        return None

    # Classic bridge-builder: rook move to the bridge square.
    if (
        moved.piece_type == chess.ROOK
        and move.to_square == bridge_square
    ):
        return "applied"

    # Otherwise — if bridge-building rook move was legal but skipped,
    # missed.
    for cand_sq in board_before.pieces(chess.ROOK, user_color):
        cand = chess.Move(cand_sq, bridge_square)
        if cand in board_before.legal_moves:
            return "missed"
    return None


def _is_lucena_test_position(board: chess.Board, user_color: chess.Color) -> bool:
    """User has K+R+P, opponent has K+R, user's pawn is on the 7th
    rank from user's POV, user's king is on the promotion square or
    the file of the pawn ahead of it."""
    opp = not user_color

    user_pawns = list(board.pieces(chess.PAWN, user_color))
    user_rooks = list(board.pieces(chess.ROOK, user_color))
    user_other = [
        sq for sq, p in board.piece_map().items()
        if p.color == user_color and p.piece_type not in (chess.KING, chess.ROOK, chess.PAWN)
    ]
    opp_rooks = list(board.pieces(chess.ROOK, opp))
    opp_other = [
        sq for sq, p in board.piece_map().items()
        if p.color == opp and p.piece_type not in (chess.KING, chess.ROOK)
    ]

    if not (
        len(user_pawns) == 1
        and len(user_rooks) == 1
        and not user_other
        and len(opp_rooks) == 1
        and not opp_other
    ):
        return False

    user_pawn_sq = user_pawns[0]
    pawn_rank = chess.square_rank(user_pawn_sq)
    needed_rank = 6 if user_color == chess.WHITE else 1  # 7th from POV
    if pawn_rank != needed_rank:
        return False

    user_king = board.king(user_color)
    if user_king is None:
        return False
    promotion_rank = 7 if user_color == chess.WHITE else 0
    promotion_square = chess.square(chess.square_file(user_pawn_sq), promotion_rank)
    pawn_file = chess.square_file(user_pawn_sq)
    if (
        chess.square_file(user_king) == pawn_file
        and chess.square_rank(user_king) == promotion_rank
    ):
        return True
    # King on file of pawn, ahead of it (one square ahead = same as
    # promotion sq for 7th-rank pawn; we already checked that).
    return user_king == promotion_square
