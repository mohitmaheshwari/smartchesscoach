import chess

from services.concept_detectors.coach_principles import (
    detect_coached_development_application,
    detect_endgame_active_rook_application,
    detect_endgame_create_passed_pawn_application,
    detect_endgame_king_centralization_application,
    detect_endgame_stop_promotion_application,
)


def test_development_requires_the_stored_best_move():
    board = chess.Board()
    move = board.parse_san("Nf3")
    assert detect_coached_development_application(
        board,
        move,
        chess.WHITE,
        move_number=1,
        best_move_uci="g1f3",
    ) == "applied"
    assert detect_coached_development_application(
        board,
        move,
        chess.WHITE,
        move_number=1,
        best_move_uci="b1c3",
    ) is None


def test_best_king_move_toward_center_is_detected_in_endgame():
    board = chess.Board("8/8/8/8/8/8/4k3/K7 w - - 0 1")
    move = board.parse_san("Kb2")
    assert detect_endgame_king_centralization_application(
        board,
        move,
        chess.WHITE,
        best_move_uci=move.uci(),
    ) == "applied"


def test_best_pawn_capture_can_create_a_passed_pawn():
    board = chess.Board("8/8/8/1p1p4/2P5/8/4k3/K7 w - - 0 1")
    move = board.parse_san("cxb5")
    assert detect_endgame_create_passed_pawn_application(
        board,
        move,
        chess.WHITE,
        best_move_uci=move.uci(),
    ) == "applied"


def test_best_rook_move_from_closed_to_open_file_is_detected():
    board = chess.Board("8/8/8/8/8/8/P3k3/R5K1 w - - 0 1")
    move = board.parse_san("Rb1")
    assert detect_endgame_active_rook_application(
        board,
        move,
        chess.WHITE,
        best_move_uci=move.uci(),
    ) == "applied"


def test_best_move_that_captures_advanced_passed_pawn_is_detected():
    board = chess.Board("8/8/8/8/8/8/2p1k3/2R3K1 w - - 0 1")
    move = board.parse_san("Rxc2")
    assert detect_endgame_stop_promotion_application(
        board,
        move,
        chess.WHITE,
        best_move_uci=move.uci(),
    ) == "applied"
