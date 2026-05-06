"""
Middlegame pattern detector. Recognises common middlegame ideas that
deserve their own caption — knight outpost, rook to open file, rook to
seventh, prophylactic king tucks, pawn breaks.

V5 narrative had nothing for these; they were the biggest unfilled
gap. These cover ~30-50% of "good" middlegame moves at 600-1500 rating
where the user is doing something positionally meaningful but the move
isn't sharp enough to fire a tactical detector.

Voice: short Indian English SVO. Pronouns swap based on is_user_move.
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


def _is_middlegame(board: chess.Board, move_number: int) -> bool:
    """Cheap middlegame heuristic: past opening, before deep endgame."""
    if move_number < 8 or move_number > 35:
        return False
    piece_count = sum(1 for sq in chess.SQUARES if board.piece_at(sq))
    return piece_count > 14


def _detect_knight_outpost(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Knight moves to a square that:
      - Is on rank 5/6 (white) or 4/3 (black)
      - Is supported by a friendly pawn
      - Cannot be attacked by an enemy pawn (no enemy pawn on adjacent
        files that can reach this square)
    That's a textbook outpost — secure, hard-to-dislodge piece.
    """
    if moving_piece.piece_type != chess.KNIGHT:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    user_color = moving_piece.color
    to_sq = move.to_square
    to_rank = chess.square_rank(to_sq)
    to_file = chess.square_file(to_sq)

    # White outposts on rank 4-5 (index), black on rank 2-3.
    if user_color == chess.WHITE and to_rank not in (4, 5):
        return None
    if user_color == chess.BLACK and to_rank not in (2, 3):
        return None

    # Apply move to inspect post-state.
    b = board_before.copy()
    b.push(move)

    # Supported by friendly pawn?
    pawn_support_rank = to_rank - 1 if user_color == chess.WHITE else to_rank + 1
    has_pawn_support = False
    for df in (-1, 1):
        nf = to_file + df
        if 0 <= nf <= 7:
            sq = chess.square(nf, pawn_support_rank)
            p = b.piece_at(sq)
            if p and p.piece_type == chess.PAWN and p.color == user_color:
                has_pawn_support = True
                break
    if not has_pawn_support:
        return None

    # Can any enemy pawn reach this square (i.e., is there an enemy pawn
    # on adjacent files at any rank ahead/equal that could push)?
    for df in (-1, 1):
        nf = to_file + df
        if not (0 <= nf <= 7):
            continue
        # Check ranks where an enemy pawn could push to to_sq
        if user_color == chess.WHITE:
            # Black pawns advance toward lower ranks — for an enemy pawn
            # to attack to_sq, it'd need to be on rank above (to_rank+1)
            for nr in range(to_rank + 1, 8):
                p = b.piece_at(chess.square(nf, nr))
                if p and p.piece_type == chess.PAWN and p.color != user_color:
                    return None
        else:
            for nr in range(0, to_rank):
                p = b.piece_at(chess.square(nf, nr))
                if p and p.piece_type == chess.PAWN and p.color != user_color:
                    return None

    sq_name = chess.square_name(to_sq)
    if is_user_move:
        return f"Plants the knight on {sq_name} — secure outpost. No enemy pawn can chase it."
    return f"Their knight lands on {sq_name} — a secure outpost protected by their pawn."


def _detect_rook_to_open_file(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    is_user_move: bool,
) -> Optional[str]:
    """Rook moves to a file with NO friendly pawns (open or half-open
    from rook's POV). Captures are excluded — rook captures get their
    own caption."""
    if moving_piece.piece_type != chess.ROOK:
        return None
    if board_before.is_capture(move):
        return None

    user_color = moving_piece.color
    to_file = chess.square_file(move.to_square)

    # Check if any friendly pawn is on this file.
    has_friendly_pawn = False
    for r in range(8):
        sq = chess.square(to_file, r)
        p = board_before.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == user_color:
            has_friendly_pawn = True
            break
    if has_friendly_pawn:
        return None

    # Was the rook NOT on this file before? (don't fire on a rook just
    # shuffling along a file it already occupied).
    from_file = chess.square_file(move.from_square)
    if from_file == to_file:
        return None

    file_letter = chr(ord('a') + to_file)
    # Check enemy pawns to differentiate open vs half-open
    has_enemy_pawn = False
    for r in range(8):
        sq = chess.square(to_file, r)
        p = board_before.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color != user_color:
            has_enemy_pawn = True
            break

    file_kind = "half-open" if has_enemy_pawn else "open"
    if is_user_move:
        return f"Rook to the {file_letter}-file — {file_kind}. The rook controls the column."
    return f"Their rook swings to the {file_letter}-file ({file_kind}), claiming the column."


def _detect_rook_to_seventh_middlegame(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Rook reaches the 7th rank in middlegame. Endgame version is in
    endgame_technique.py. Middlegame 7th-rank rooks are usually decisive
    if undefended — they target enemy pawns and pin the king."""
    if moving_piece.piece_type != chess.ROOK:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    user_color = moving_piece.color
    target_rank = 6 if user_color == chess.WHITE else 1
    if chess.square_rank(move.to_square) != target_rank:
        return None
    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return f"Rook to the seventh — {sq_name}. From here it eats pawns and ties the enemy king down."
    return f"Their rook reaches the seventh on {sq_name}. Tough to kick out."


def _detect_prophylactic_king_tuck(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Quiet king move (Kh1, Kg1, Kh8, Kg8) in middlegame — typically
    sidestepping a future attack on the diagonal or back-rank."""
    if moving_piece.piece_type != chess.KING:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    user_color = moving_piece.color
    to_sq_name = chess.square_name(move.to_square)
    from_sq_name = chess.square_name(move.from_square)
    # Castled-king tucks: Kh1 from g1 (white) or Kh8 from g8 (black)
    if user_color == chess.WHITE:
        if from_sq_name == "g1" and to_sq_name in ("h1", "f1"):
            if is_user_move:
                return f"King tucks to {to_sq_name}. Steps off a future diagonal or back-rank threat before it lands."
            return f"They tuck the king to {to_sq_name} prophylactically."
    else:
        if from_sq_name == "g8" and to_sq_name in ("h8", "f8"):
            if is_user_move:
                return f"King tucks to {to_sq_name}. Steps off a future diagonal or back-rank threat before it lands."
            return f"They tuck the king to {to_sq_name} prophylactically."
    return None


def _detect_central_pawn_break(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Pawn moves into a square that opens a file or breaks the centre.
    Conservative: fire when the pushed pawn captures an enemy pawn or
    is itself a CENTRAL pawn (c/d/e/f) advancing past rank 4."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    if to_file not in (2, 3, 4, 5):  # c, d, e, f files only
        return None
    user_color = moving_piece.color
    target_rank_min = 4 if user_color == chess.WHITE else 3
    if (user_color == chess.WHITE and to_rank < target_rank_min) or (
        user_color == chess.BLACK and to_rank > target_rank_min
    ):
        return None

    is_capture = board_before.is_capture(move)
    sq_name = chess.square_name(move.to_square)
    if is_capture:
        if is_user_move:
            return f"Pawn break — opens lines toward their king with {sq_name}."
        return f"They open the centre with {sq_name}."
    if is_user_move:
        return f"Central pawn push to {sq_name}. Tests their pawn structure."
    return f"They push the central pawn to {sq_name}."


def _detect_queen_lift_attack(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Queen lifts to 3rd/4th rank (white) or 5th/6th (black) heading
    toward enemy king-side — typical kingside attack indicator."""
    if moving_piece.piece_type != chess.QUEEN:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    user_color = moving_piece.color
    to_rank = chess.square_rank(move.to_square)
    to_file = chess.square_file(move.to_square)

    # Aim at enemy king-side (file f-h or kingside generally).
    if to_file < 5:  # not on f, g, h files
        return None
    if user_color == chess.WHITE:
        if to_rank not in (3, 4, 5):
            return None
    else:
        if to_rank not in (4, 3, 2):
            return None

    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return f"Queen lifts toward {sq_name}, joining the attack on their king."
    return f"Their queen lifts to {sq_name} — heading for your king."


def _detect_minority_attack_push(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Pawn push on the side where you have fewer pawns (a-, b-pawn
    advance) — minority attack idea, common in QGD-style structures."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    if not _is_middlegame(board_before, move_number):
        return None
    to_file = chess.square_file(move.to_square)
    if to_file not in (0, 1):  # a, b file
        return None
    user_color = moving_piece.color
    # Count pawns on a-c vs e-h files (rough flank check).
    queenside_pawns = sum(
        1 for sq in chess.SQUARES
        if (p := board_before.piece_at(sq))
        and p.piece_type == chess.PAWN
        and p.color == user_color
        and chess.square_file(sq) <= 2
    )
    kingside_pawns = sum(
        1 for sq in chess.SQUARES
        if (p := board_before.piece_at(sq))
        and p.piece_type == chess.PAWN
        and p.color == user_color
        and chess.square_file(sq) >= 5
    )
    enemy_queenside = sum(
        1 for sq in chess.SQUARES
        if (p := board_before.piece_at(sq))
        and p.piece_type == chess.PAWN
        and p.color != user_color
        and chess.square_file(sq) <= 2
    )
    if queenside_pawns >= enemy_queenside:
        return None
    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return f"Minority attack — pushing {sq_name} to create weaknesses on their queenside."
    return f"They push {sq_name} on the queenside — minority attack idea."


def detect_middlegame_pattern(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[Dict]:
    """Run middlegame detectors. Returns first match {name, caption}."""
    cap = _detect_knight_outpost(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "knight_outpost", "caption": cap}

    cap = _detect_rook_to_seventh_middlegame(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "rook_seventh", "caption": cap}

    cap = _detect_rook_to_open_file(board_before, move, moving_piece, is_user_move)
    if cap:
        return {"name": "rook_open_file", "caption": cap}

    cap = _detect_queen_lift_attack(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "queen_lift", "caption": cap}

    cap = _detect_central_pawn_break(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "pawn_break", "caption": cap}

    cap = _detect_minority_attack_push(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "minority_attack", "caption": cap}

    cap = _detect_prophylactic_king_tuck(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "king_tuck", "caption": cap}

    return None
