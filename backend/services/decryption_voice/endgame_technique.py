"""
Endgame technique detector. Recognises common endgame ideas and
produces deterministic captions describing what the move accomplishes
positionally.

Patterns covered:
  - king_activation: in low-piece endgames, the user's king moves
    forward toward the centre
  - winning_pawn_promotion: pawn pushes one square from promotion
  - pawn_promotion: pawn promotes
  - rook_to_seventh: rook reaches the 7th/2nd rank
  - king_blockades_pawn: user's king sits in front of an enemy passed pawn

These complement the existing opposition / outside_passed_pawn /
pawn_race detectors in concept_dispatcher. Voice rule the same — short
SVO Indian English, no idioms.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import chess

logger = logging.getLogger(__name__)


_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def _is_endgame(board: chess.Board) -> bool:
    """Cheap endgame heuristic: total non-king pieces low OR no queens."""
    piece_count = sum(1 for sq in chess.SQUARES if board.piece_at(sq))
    if piece_count <= 12:
        return True
    queens = (
        len(board.pieces(chess.QUEEN, chess.WHITE))
        + len(board.pieces(chess.QUEEN, chess.BLACK))
    )
    if queens == 0 and piece_count <= 18:
        return True
    return False


def _detect_pawn_promotion(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """Pawn move that actually promotes."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    promo_rank = 7 if moving_piece.color == chess.WHITE else 0
    if chess.square_rank(move.to_square) != promo_rank:
        return None
    promo_piece = move.promotion or chess.QUEEN
    promo_name = _PIECE_NAME.get(promo_piece, "queen")
    return f"Promotes to a {promo_name}. The pawn became a piece — game-changing material."


def _detect_pawn_one_step_from_promotion(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """User's pawn pushes to the 7th (or 2nd if black) rank — one step
    from promoting. The opponent must address this directly."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    near_promo_rank = 6 if moving_piece.color == chess.WHITE else 1
    if chess.square_rank(move.to_square) != near_promo_rank:
        return None
    return (
        f"Pushes the pawn to {chess.square_name(move.to_square)} — "
        f"one square from promoting. Hard to stop now."
    )


def _detect_king_activation(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """In endgame, user's king moves toward the centre (rank 3-6)."""
    if moving_piece.piece_type != chess.KING:
        return None
    if not _is_endgame(board_before):
        return None
    to_rank = chess.square_rank(move.to_square)
    from_rank = chess.square_rank(move.from_square)
    # White king moves UP toward centre (4 or 5); black moves DOWN.
    if moving_piece.color == chess.WHITE:
        if to_rank > from_rank and to_rank >= 2:
            return (
                f"Activates the king toward {chess.square_name(move.to_square)}. "
                "In the endgame the king is a fighting piece."
            )
    else:
        if to_rank < from_rank and to_rank <= 5:
            return (
                f"Activates the king toward {chess.square_name(move.to_square)}. "
                "In the endgame the king is a fighting piece."
            )
    return None


def _detect_rook_to_seventh(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """Rook reaches the 7th (white) or 2nd (black) rank in the endgame."""
    if moving_piece.piece_type != chess.ROOK:
        return None
    target_rank = 6 if moving_piece.color == chess.WHITE else 1
    if chess.square_rank(move.to_square) != target_rank:
        return None
    if not _is_endgame(board_before):
        return None
    return (
        f"Rook to {chess.square_name(move.to_square)} — reaches the seventh rank. "
        "From here it eats pawns and pins the enemy king."
    )


def _detect_king_blockades_passed_pawn(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
) -> Optional[str]:
    """User's king moves to a square directly in front of an enemy
    passed pawn (one square ahead of it)."""
    if moving_piece.piece_type != chess.KING:
        return None
    user_color = moving_piece.color
    opp_color = not user_color
    direction = 1 if opp_color == chess.WHITE else -1  # opp pawns advance this way
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)

    # Is there an enemy pawn one square behind on the same file (relative
    # to opp's direction of advance)?
    behind_rank = to_rank - direction
    if behind_rank < 0 or behind_rank > 7:
        return None
    behind_sq = chess.square(to_file, behind_rank)
    p = board_before.piece_at(behind_sq)
    if not p or p.piece_type != chess.PAWN or p.color != opp_color:
        return None

    # Is that pawn passed? (no enemy pawn ahead on same/adjacent files)
    promo_rank = 7 if opp_color == chess.WHITE else 0
    nr = behind_rank + direction
    while 0 <= nr <= 7:
        for nf in (to_file - 1, to_file, to_file + 1):
            if 0 <= nf <= 7:
                pp = board_before.piece_at(chess.square(nf, nr))
                if pp and pp.piece_type == chess.PAWN and pp.color != opp_color:
                    return None  # not passed — friendly pawn blocks
        nr += direction

    return (
        f"King to {chess.square_name(to_sq)} — sits in front of their passed pawn. "
        "Stops it from running."
    )


def detect_endgame_technique(
    board_before: chess.Board,
    move_san: str,
    user_color_name: str,
) -> Optional[Dict]:
    """Run endgame detectors. Returns {name, caption} for the first
    matching pattern, or None."""
    try:
        move = board_before.parse_san(move_san)
        moving_piece = board_before.piece_at(move.from_square)
        if not moving_piece:
            return None
    except Exception:
        return None

    # Order: most decisive first.
    cap = _detect_pawn_promotion(board_before, move, moving_piece)
    if cap:
        return {"name": "pawn_promotion", "caption": cap}

    cap = _detect_pawn_one_step_from_promotion(board_before, move, moving_piece)
    if cap:
        return {"name": "pawn_near_promotion", "caption": cap}

    cap = _detect_rook_to_seventh(board_before, move, moving_piece)
    if cap:
        return {"name": "rook_to_seventh", "caption": cap}

    cap = _detect_king_blockades_passed_pawn(board_before, move, moving_piece)
    if cap:
        return {"name": "king_blockades_pawn", "caption": cap}

    cap = _detect_king_activation(board_before, move, moving_piece)
    if cap:
        return {"name": "king_activation", "caption": cap}

    return None
