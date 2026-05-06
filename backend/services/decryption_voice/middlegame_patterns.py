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


def _detect_fianchetto_complete(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    is_user_move: bool,
) -> Optional[str]:
    """Bishop completes a fianchetto: lands on g2/b2 (white) or g7/b7
    (black) with the matching pawn already pushed to g3/b3 or g6/b6.
    Not middlegame-gated — fianchettos happen in the opening."""
    if moving_piece.piece_type != chess.BISHOP:
        return None
    user_color = moving_piece.color
    to_sq_name = chess.square_name(move.to_square)

    fianchetto_targets = {
        chess.WHITE: {"g2": "g3", "b2": "b3"},
        chess.BLACK: {"g7": "g6", "b7": "b6"},
    }
    target_map = fianchetto_targets.get(user_color, {})
    if to_sq_name not in target_map:
        return None
    pawn_sq_name = target_map[to_sq_name]
    pawn_sq = chess.parse_square(pawn_sq_name)
    p = board_before.piece_at(pawn_sq)
    if not p or p.piece_type != chess.PAWN or p.color != user_color:
        return None

    # Long diagonal description varies by square.
    diag = "a1-h8 diagonal" if to_sq_name in ("g2", "b7") else "a8-h1 diagonal"
    if is_user_move:
        return f"Fianchetto — bishop to {to_sq_name}. Eyes the {diag}."
    return f"They fianchetto the bishop to {to_sq_name}, claiming the {diag}."


def _has_isolated_queen_pawn(board: chess.Board, color: bool) -> bool:
    """True if `color` has a d-pawn (white d4-d5; black d4-d5) with no
    own pawns on c-file or e-file."""
    d_files = [chess.D1, chess.D2, chess.D3, chess.D4, chess.D5, chess.D6, chess.D7, chess.D8]
    has_d_pawn = False
    for sq in d_files:
        p = board.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == color:
            has_d_pawn = True
            break
    if not has_d_pawn:
        return False
    # Any c-pawn or e-pawn of same colour?
    for f_idx in (2, 4):  # c-file = 2, e-file = 4
        for r in range(8):
            p = board.piece_at(chess.square(f_idx, r))
            if p and p.piece_type == chess.PAWN and p.color == color:
                return False
    return True


def _detect_isolated_queen_pawn_play(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """User has an IQP and the move is one of the textbook IQP-friendly
    piece manoeuvres (knight to e5/e4, bishop to attacking diagonal)."""
    if not _is_middlegame(board_before, move_number):
        return None
    user_color = moving_piece.color
    if not _has_isolated_queen_pawn(board_before, user_color):
        return None

    to_sq_name = chess.square_name(move.to_square)

    if moving_piece.piece_type == chess.KNIGHT:
        ideal = "e5" if user_color == chess.WHITE else "e4"
        if to_sq_name != ideal:
            return None
        if is_user_move:
            return f"Knight to {to_sq_name} — the IQP outpost. Your isolated d-pawn supports a strong square."
        return f"Their knight lands on {to_sq_name} — IQP outpost."

    if moving_piece.piece_type == chess.BISHOP:
        if user_color == chess.WHITE and to_sq_name not in ("b3", "c4", "d3"):
            return None
        if user_color == chess.BLACK and to_sq_name not in ("b6", "c5", "d6"):
            return None
        if is_user_move:
            return f"Bishop to {to_sq_name} — joins the IQP attack. Your d-pawn pays for itself with active pieces."
        return f"Their bishop to {to_sq_name} — typical IQP attacker."

    return None


def _opp_king_lacks_luft(board: chess.Board, opp_color: bool) -> bool:
    """Opp king sits on its back rank and the three squares directly in
    front are all blocked by own pawns — classic back-rank weakness."""
    king_sq = board.king(opp_color)
    if king_sq is None:
        return False
    back_rank = 7 if opp_color == chess.BLACK else 0
    if chess.square_rank(king_sq) != back_rank:
        return False
    front_rank = back_rank - 1 if opp_color == chess.BLACK else back_rank + 1
    if not (0 <= front_rank <= 7):
        return False
    king_file = chess.square_file(king_sq)
    blocked = 0
    relevant = 0
    for df in (-1, 0, 1):
        nf = king_file + df
        if not (0 <= nf <= 7):
            continue
        relevant += 1
        sq = chess.square(nf, front_rank)
        p = board.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == opp_color:
            blocked += 1
    return blocked >= relevant - 0  # all relevant squares must be opp pawns


def _detect_back_rank_pressure(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """User's rook or queen lands on a file/rank that targets opp's
    back rank when opp's king has no luft. Conservative: requires
    (a) opp king on back rank with all 3 luft-squares blocked by own
    pawns, (b) our piece is rook/queen, (c) our piece's file or rank
    intersects opp's back rank with a clear line."""
    if moving_piece.piece_type not in (chess.ROOK, chess.QUEEN):
        return None
    if not _is_middlegame(board_before, move_number):
        return None

    user_color = moving_piece.color
    opp_color = not user_color
    if not _opp_king_lacks_luft(board_before, opp_color):
        return None

    # Apply the move.
    b = board_before.copy()
    b.push(move)

    # Does our piece attack any back-rank square where opp's king sits or
    # could sit? Check direct attacks from the moved piece.
    opp_back_rank = 7 if opp_color == chess.BLACK else 0
    attacked_squares = b.attacks(move.to_square)
    threatens_back_rank = any(
        chess.square_rank(sq) == opp_back_rank for sq in attacked_squares
    )
    if not threatens_back_rank:
        return None

    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return (
            f"Heavy piece to {sq_name} — eyes their back rank. Their king has no luft."
        )
    return f"Their {_PIECE_NAME[moving_piece.piece_type]} to {sq_name} — back-rank pressure."


def _detect_doubled_pawn_recapture(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    is_user_move: bool,
) -> Optional[str]:
    """Pawn capture that creates doubled pawns on the destination file.
    Often an acceptable structural choice (opens lines, gains tempo)
    but worth naming so the player notices the trade-off."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    if not board_before.is_capture(move):
        return None

    user_color = moving_piece.color
    to_file = chess.square_file(move.to_square)

    b = board_before.copy()
    b.push(move)

    pawn_count_on_file = 0
    for r in range(8):
        p = b.piece_at(chess.square(to_file, r))
        if p and p.piece_type == chess.PAWN and p.color == user_color:
            pawn_count_on_file += 1
    if pawn_count_on_file < 2:
        return None

    file_letter = chr(ord("a") + to_file)
    if is_user_move:
        return (
            f"Recaptures on {chess.square_name(move.to_square)} — doubles your "
            f"{file_letter}-pawns. Opens a file for your rook in return."
        )
    return f"They recapture on {chess.square_name(move.to_square)}, doubling pawns on the {file_letter}-file."


def _detect_luft_push(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """One-square pawn push that creates luft for the user's castled
    king (h2-h3, g2-g3, h7-h6, g7-g6, a2-a3, a7-a6 with king on the
    relevant flank). Distinguishes from standard pawn moves by the
    geometry: king is on castled square, pawn is in front."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    if move_number < 8:
        return None  # in opening, pawn moves usually have other purposes
    user_color = moving_piece.color
    from_rank = chess.square_rank(move.from_square)
    to_rank = chess.square_rank(move.to_square)
    from_file = chess.square_file(move.from_square)
    to_file = chess.square_file(move.to_square)

    # Single-square advance, same file
    if from_file != to_file:
        return None
    starting_rank = 1 if user_color == chess.WHITE else 6
    if from_rank != starting_rank:
        return None
    expected_to_rank = 2 if user_color == chess.WHITE else 5
    if to_rank != expected_to_rank:
        return None

    # Must be on a/g/h file (luft files for castled king)
    if to_file not in (0, 6, 7):
        return None

    # User's king on the relevant flank
    king_sq = board_before.king(user_color)
    if king_sq is None:
        return None
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    castled_rank = 0 if user_color == chess.WHITE else 7
    if king_rank != castled_rank:
        return None
    # Kingside luft (h3/g3 or h6/g6) requires king on f/g/h
    # Queenside luft (a3/a6) requires king on a/b/c
    if to_file in (6, 7) and king_file < 5:
        return None
    if to_file == 0 and king_file > 2:
        return None

    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return f"Pawn to {sq_name} — gives the king luft. No back-rank surprises now."
    return f"They push {sq_name}, giving their king luft."


def _detect_opening_pawn_prep(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Quiet supporting pawn move in the opening (c6, e6, d6, c3, d3,
    e3) that prepares ...d5 / ...e5 / supports a central pawn or
    opens a development square. Common at 600-1500 rating where the
    user is making structurally sensible but unspectacular moves."""
    if moving_piece.piece_type != chess.PAWN:
        return None
    if move_number > 12:
        return None
    if board_before.is_capture(move):
        return None
    user_color = moving_piece.color
    from_rank = chess.square_rank(move.from_square)
    to_rank = chess.square_rank(move.to_square)
    to_file = chess.square_file(move.to_square)

    # Single-square push only (e.g., e7-e6, c2-c3)
    expected_diff = 1 if user_color == chess.WHITE else -1
    if to_rank - from_rank != expected_diff:
        return None
    # Files c, d, e (indices 2, 3, 4)
    if to_file not in (2, 3, 4):
        return None
    # Starting rank must be the pawn's home rank
    starting_rank = 1 if user_color == chess.WHITE else 6
    if from_rank != starting_rank:
        return None

    sq_name = chess.square_name(move.to_square)
    file_letter = chr(ord("a") + to_file)
    # Frame based on file
    if file_letter in ("c", "e"):
        prep = f"prepares ...d{5 if user_color == chess.WHITE else 5}" if user_color == chess.BLACK else "prepares d4 or supports the centre"
    else:
        prep = "frees the queen and supports the centre"
    if is_user_move:
        return f"Pawn to {sq_name} — quiet structural move. Solid setup."
    return f"They play {sq_name} — solid structural move."


def _detect_central_knight_redeployment(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[str]:
    """Knight moves to a central square (c4/c5/d4/d5/e4/e5/f4/f5) past
    the development phase (move > 12). Knight_outpost requires pawn
    support AND no enemy pawn can chase; this fires on central knight
    moves that don't meet that strict bar but are still good
    repositioning."""
    if moving_piece.piece_type != chess.KNIGHT:
        return None
    if move_number <= 12:
        return None  # development phase handled elsewhere
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    if to_file not in (2, 3, 4, 5):  # c, d, e, f
        return None
    if to_rank not in (3, 4):  # ranks 4-5 in 1-indexed (centre ranks)
        return None

    # Must not be a capture (capture detector handles those)
    if board_before.is_capture(move):
        return None

    # Must not already be in knight_outpost territory — re-check that
    # the strict version doesn't fire (we want this as fallback).
    sq_name = chess.square_name(move.to_square)
    if is_user_move:
        return f"Knight to {sq_name} — central post. Eyes both sides of the board."
    return f"Their knight redeploys to {sq_name}."


def detect_middlegame_pattern(
    board_before: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece,
    move_number: int,
    is_user_move: bool,
) -> Optional[Dict]:
    """Run middlegame detectors. Returns first match {name, caption}."""
    # Fianchetto first — works in opening too (not middlegame-gated).
    cap = _detect_fianchetto_complete(board_before, move, moving_piece, is_user_move)
    if cap:
        return {"name": "fianchetto", "caption": cap}

    cap = _detect_knight_outpost(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "knight_outpost", "caption": cap}

    # Central knight redeployment is the looser fallback for knight moves
    # to central squares past the opening that don't meet outpost bar.
    cap = _detect_central_knight_redeployment(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "knight_central", "caption": cap}

    cap = _detect_rook_to_seventh_middlegame(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "rook_seventh", "caption": cap}

    # Back-rank pressure pre-empts generic open-file caption when opp
    # king has no luft — it's more specific and more decisive.
    cap = _detect_back_rank_pressure(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "back_rank_pressure", "caption": cap}

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

    cap = _detect_isolated_queen_pawn_play(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "iqp_play", "caption": cap}

    cap = _detect_doubled_pawn_recapture(board_before, move, moving_piece, is_user_move)
    if cap:
        return {"name": "doubled_pawn_recapture", "caption": cap}

    cap = _detect_prophylactic_king_tuck(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "king_tuck", "caption": cap}

    # Luft pushes — h3/g3/h6/g6/a3/a6 with king on the matching flank.
    cap = _detect_luft_push(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "luft", "caption": cap}

    # Opening structural pawn prep (c6, e6, d6, c3, d3, e3) — only fires
    # in moves 3-12, last in the chain so other openings/development
    # detectors get first crack.
    cap = _detect_opening_pawn_prep(board_before, move, moving_piece, move_number, is_user_move)
    if cap:
        return {"name": "pawn_prep", "caption": cap}

    return None
