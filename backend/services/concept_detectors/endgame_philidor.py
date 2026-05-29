"""
Philidor position detector.

Philidor = drawing K+R vs K+R+P when the defender keeps their rook on
the 3rd rank (from their POV) until the attacker pushes the pawn,
then drops the rook behind to check the attacking king from the rear.

Defender's setup (canonical):
  - Defender's king on the promotion square (or one in front of the
    pawn)
  - Defender's rook on their 3rd rank (6th from attacker's POV)
  - Attacker has K+R+P; defender has K+R

This detector grades the defender's first "drop to 6th rank" move
when the attacker pushes the pawn to the 6th rank (from their POV) —
the canonical "drop the rook behind" technique.

Decision logic:

    Pre-condition ("clean test"):
      - User's move (defender)
      - Endgame piece set: defender has K+R; attacker has K+R+P (1
        attacker pawn, no other pawns / pieces)
      - User played on their 3rd rank LAST move, but attacker has now
        pushed the pawn — kept implicit by checking the post-condition
      - The attacker just pushed to their 6th rank (defender's 3rd)

For SIMPLICITY in this v1 detector, we use a tight geometry test:

    Pre-condition (simpler):
      - Defender to move
      - K+R+P (attacker) vs K+R (defender), pawn on 5th rank from
        attacker POV (so attacker's pawn is on rank 4 for black-attacker
        / rank 5 for white-attacker — i.e. the rank PRIOR to the
        canonical Philidor drop)

    Grade:
      - Defender's rook moves to the rank BEHIND the attacker (i.e.
        attacker's 1st-2nd rank) — the canonical "drop the rook
        behind" technique                                            → "applied"

For v1 we only grade "applied" (the positive demonstration). False-
missed risk is high here so we skip "missed".
"""
from __future__ import annotations

from typing import Optional

import chess


def detect_endgame_philidor_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    if board_before.turn != user_color:
        return None

    attacker_color = not user_color
    setup = _philidor_test_setup(board_before, defender_color=user_color)
    if setup is None:
        return None
    _, attacker_pawn_sq = setup

    # User must move their rook.
    moved = board_before.piece_at(move.from_square)
    if moved is None or moved.piece_type != chess.ROOK or moved.color != user_color:
        return None

    # "Behind the attacker" = 1st or 2nd rank from attacker's POV.
    behind_ranks = (0, 1) if attacker_color == chess.WHITE else (6, 7)
    if chess.square_rank(move.to_square) not in behind_ranks:
        return None

    # Also require the rook to actually be on the same file as the
    # pawn (the "rear-guard" attack vector) OR within 2 files of it.
    pawn_file = chess.square_file(attacker_pawn_sq)
    rook_file = chess.square_file(move.to_square)
    if abs(rook_file - pawn_file) > 2:
        return None

    return "applied"


def _philidor_test_setup(board: chess.Board, defender_color: chess.Color) -> Optional[tuple]:
    """Returns (defender_rook_sq, attacker_pawn_sq) when the position
    matches the Philidor scope: defender has K+R; attacker has K+R+P
    with the pawn on rank 4 (attacker=BLACK) or rank 5 (attacker=WHITE)."""
    attacker = not defender_color

    defender_rooks = list(board.pieces(chess.ROOK, defender_color))
    if len(defender_rooks) != 1:
        return None
    defender_other = [
        sq for sq, p in board.piece_map().items()
        if p.color == defender_color and p.piece_type not in (chess.KING, chess.ROOK)
    ]
    if defender_other:
        return None

    attacker_rooks = list(board.pieces(chess.ROOK, attacker))
    attacker_pawns = list(board.pieces(chess.PAWN, attacker))
    attacker_other = [
        sq for sq, p in board.piece_map().items()
        if p.color == attacker
        and p.piece_type not in (chess.KING, chess.ROOK, chess.PAWN)
    ]
    if (
        len(attacker_rooks) != 1
        or len(attacker_pawns) != 1
        or attacker_other
    ):
        return None

    pawn_sq = attacker_pawns[0]
    pawn_rank = chess.square_rank(pawn_sq)
    expected_rank = 4 if attacker == chess.WHITE else 3
    if pawn_rank != expected_rank:
        return None

    return defender_rooks[0], pawn_sq
