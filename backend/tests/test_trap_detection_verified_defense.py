import chess

from services.concept_detectors.trap_detection import detect_trap_application


def _board_after(moves):
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return board


def test_exact_authored_victim_defense_is_an_application():
    setup = ["e4", "e5", "Bc4", "Nc6", "Qh5"]
    board = _board_after(setup)
    move = board.parse_san("Qe7")
    assert detect_trap_application(
        board,
        move,
        chess.BLACK,
        move_number=3,
        move_history_san=setup + ["Qe7"],
        best_move_uci=move.uci(),
    ) == "applied"


def test_authored_defense_without_stored_best_is_not_mastery_evidence():
    setup = ["e4", "e5", "Bc4", "Nc6", "Qh5"]
    board = _board_after(setup)
    move = board.parse_san("Qe7")
    assert detect_trap_application(
        board,
        move,
        chess.BLACK,
        move_number=3,
        move_history_san=setup + ["Qe7"],
    ) is None


def test_arbitrary_deviation_is_not_called_a_verified_defense():
    setup = ["e4", "e5", "Bc4", "Nc6", "Qh5"]
    board = _board_after(setup)
    move = board.parse_san("g6")
    assert detect_trap_application(
        board,
        move,
        chess.BLACK,
        move_number=3,
        move_history_san=setup + ["g6"],
    ) is None
