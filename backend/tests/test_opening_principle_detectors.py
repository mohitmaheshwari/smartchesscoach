"""Stored-best opening principle and sound-deviation candidates."""
from __future__ import annotations

import chess

from services.concept_detectors.opening_play import (
    detect_sound_opening_deviation_application,
)
from services.concept_detectors.opening_principles import (
    detect_opening_castling_application,
    detect_opening_center_application,
    detect_opening_development_with_tempo_application,
)


def _after(*moves: str) -> chess.Board:
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return board


def test_sound_london_deviation_requires_played_move_to_be_stored_best():
    board = _after("d4", "d5")
    move = board.parse_san("Nf3")
    history = ["d4", "d5", "Nf3"]
    assert detect_sound_opening_deviation_application(
        board,
        move,
        chess.WHITE,
        move_number=2,
        opening_name="london_system",
        move_history_san=history,
        best_move_uci=move.uci(),
    ) == "applied"
    assert detect_sound_opening_deviation_application(
        board,
        move,
        chess.WHITE,
        move_number=2,
        opening_name="london_system",
        move_history_san=history,
        best_move_uci="c1f4",
    ) is None


def test_opening_center_requires_stored_best():
    board = chess.Board()
    move = board.parse_san("e4")
    assert detect_opening_center_application(
        board, move, chess.WHITE, move_number=1, best_move_uci=move.uci()
    ) == "applied"
    assert detect_opening_center_application(
        board, move, chess.WHITE, move_number=1
    ) is None


def test_castling_as_stored_best_is_positive_evidence():
    board = _after("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5")
    move = board.parse_san("O-O")
    assert detect_opening_castling_application(
        board, move, chess.WHITE, move_number=4, best_move_uci=move.uci()
    ) == "applied"


def test_development_with_tempo_names_only_a_real_high_value_attack():
    board = _after("e4", "d5", "exd5", "Qxd5")
    move = board.parse_san("Nc3")
    assert detect_opening_development_with_tempo_application(
        board, move, chess.WHITE, move_number=3, best_move_uci=move.uci()
    ) == "applied"

    quiet_board = chess.Board()
    quiet = quiet_board.parse_san("Nf3")
    assert detect_opening_development_with_tempo_application(
        quiet_board,
        quiet,
        chess.WHITE,
        move_number=1,
        best_move_uci=quiet.uci(),
    ) is None
