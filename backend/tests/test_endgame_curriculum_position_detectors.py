"""All verified endgame lessons derive exact stored-best transfer checks."""
from __future__ import annotations

import chess

from services.concept_detectors.endgame_curriculum_positions import (
    curriculum_endgame_detectors,
    curriculum_endgame_lesson_ids,
    detector_id_for_lesson,
)
from services.detector_quality import QualityGrade, grade_for
from services.endgame_theory_service import get_verified_lesson_data


def _first_case():
    lesson_id = curriculum_endgame_lesson_ids()[0]
    category, lesson = lesson_id.split("/", 1)
    position = get_verified_lesson_data(category, lesson)["positions"][0]
    board = chess.Board(position["fen"])
    expected = chess.Move.from_uci(position["correct_move_uci"])
    detector = curriculum_endgame_detectors()[detector_id_for_lesson(lesson_id)]
    return lesson_id, board, expected, detector


def test_every_publishable_endgame_lesson_has_an_exact_transfer_detector():
    lesson_ids = curriculum_endgame_lesson_ids()
    detectors = curriculum_endgame_detectors()
    assert len(lesson_ids) == 20
    assert len(detectors) == len(lesson_ids)
    assert set(detectors) == {detector_id_for_lesson(item) for item in lesson_ids}


def test_exact_position_applies_only_when_authored_and_stored_answers_agree():
    _, board, expected, detector = _first_case()
    assert detector(
        board,
        expected,
        board.turn,
        best_move_uci=expected.uci(),
    ) == "applied"
    assert detector(board, expected, board.turn) is None


def test_exact_position_records_a_miss_only_when_stored_best_is_authored_answer():
    _, board, expected, detector = _first_case()
    alternative = next(move for move in board.legal_moves if move != expected)
    assert detector(
        board,
        alternative,
        board.turn,
        best_move_uci=expected.uci(),
    ) == "missed"


def test_all_exact_endgame_detectors_fail_closed_to_shadow():
    for lesson_id in curriculum_endgame_lesson_ids():
        quality_id = f"concept:{detector_id_for_lesson(lesson_id)}"
        assert grade_for(quality_id) == QualityGrade.SHADOW
