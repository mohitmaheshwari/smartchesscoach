"""Stored-best adapters for the canonical middlegame pattern recognizers.

The chess geometry remains owned by
``services.decryption_voice.middlegame_patterns``.  This module adds only the
evidence rule required for mastery measurement: the played move must be the
legal best move already stored with the game analysis.  Candidates are
positive-only and remain Shadow until corpus replay and blind coach review.
"""
from __future__ import annotations

from typing import Optional

import chess

from services.concept_detectors.evidence import stored_best_matches
from services.decryption_voice.middlegame_patterns import (
    detect_middlegame_pattern,
)


def _detect_pattern_application(
    expected_pattern: str,
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int],
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
) -> Optional[str]:
    if move_number is None or board_before.turn != user_color:
        return None
    moving_piece = board_before.piece_at(move.from_square)
    if not moving_piece or moving_piece.color != user_color:
        return None
    if not stored_best_matches(
        board_before, move, best_move_san, best_move_uci
    ):
        return None
    result = detect_middlegame_pattern(
        board_before,
        move,
        moving_piece,
        int(move_number),
        True,
    )
    if result and result.get("name") == expected_pattern:
        return "applied"
    return None


def detect_knight_outpost_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "knight_outpost", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_rook_open_file_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "rook_open_file", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_rook_seventh_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "rook_seventh", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_central_pawn_break_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "pawn_break", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_minority_attack_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "minority_attack", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_iqp_play_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "iqp_play", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_luft_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "luft", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )


def detect_prophylactic_king_tuck_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    return _detect_pattern_application(
        "king_tuck", board_before, move, user_color, move_number,
        best_move_san, best_move_uci,
    )
