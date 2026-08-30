import chess

from services.curriculum_content_validator import validate_all_content
from trick_library_service import (
    TRAPS_DATABASE,
    get_all_traps,
    get_trap_for_practice,
)


def _replay(moves):
    board = chess.Board()
    for move in moves:
        board.push_san(move)
    return board


def test_play_with_coach_catalog_is_the_validated_canonical_catalog():
    report = validate_all_content()["subjects"]["traps"]

    assert len(get_all_traps()) == report["publishable"]
    assert all(
        trap["canonical_source"] == "backend/data/traps.json"
        for trap in get_all_traps()
    )


def test_execution_practice_uses_the_full_authored_line():
    lesson = get_trap_for_practice("legals_mate", "execution")

    assert lesson is not None
    assert lesson["full_sequence"] == (
        lesson["setup_moves"] + lesson["winning_line"]
    )
    assert len(lesson["winning_line"]) > 1
    assert _replay(lesson["full_sequence"]).is_checkmate()


def test_scholars_mate_is_defense_first_and_legal():
    trap = TRAPS_DATABASE["scholars_mate"]
    lesson = get_trap_for_practice("scholars_mate", "avoidance")

    assert trap["victim_color"] == "black"
    assert lesson is not None
    assert lesson["user_color"] == "black"
    assert lesson["defense_line"] == ["Qe7"]
    assert lesson["how_to_avoid"].startswith("Defend f7")
    assert _replay(lesson["full_sequence"]).is_valid()


def test_every_exposed_practice_sequence_is_legal():
    for trap in get_all_traps():
        execution = get_trap_for_practice(trap["key"], "execution")
        assert execution is not None
        _replay(execution["full_sequence"])

        recognition = get_trap_for_practice(trap["key"], "recognition")
        assert recognition is not None
        assert chess.Board(recognition["fen"]).is_valid()

        avoidance = get_trap_for_practice(trap["key"], "avoidance")
        if avoidance:
            _replay(avoidance["full_sequence"])
