import asyncio
from copy import deepcopy

import chess

from services.curriculum_content_validator import (
    get_defense_ready_trap_ids,
    get_publishable_content_ids,
    validate_all_content,
)
from services.endgame_theory_service import (
    check_move,
    get_all_categories,
    get_lesson,
    get_verified_lesson_data,
)
from services.opening_curriculum_engine import get_available_openings
from services.opening_library_service import (
    OPENING_DATABASE,
    get_opening_for_position,
    match_opening_to_library,
)
from services.opening_theory_json_service import get_lesson_move_steps
from services.teaching_engine import (
    get_lesson_catalog,
    process_endgame_move,
    start_endgame_lesson,
    start_trap_lesson,
)


class FakeCollection:
    def __init__(self, document):
        self.document = deepcopy(document)

    async def find_one(self, query):
        if self.document.get("session_id") == query.get("session_id"):
            return deepcopy(self.document)
        return None

    async def update_one(self, query, update):
        assert self.document.get("session_id") == query.get("session_id")
        for key, value in update.get("$set", {}).items():
            self.document[key] = deepcopy(value)
        for key, value in update.get("$inc", {}).items():
            self.document[key] = self.document.get(key, 0) + value
        for key in update.get("$unset", {}):
            self.document.pop(key, None)


class FakeDB:
    def __init__(self):
        self.coach_sessions = FakeCollection(
            {
                "session_id": "session-1",
                "current_fen": (
                    "rnbqkbnr/pppppppp/8/8/8/8/"
                    "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                ),
            }
        )


def test_public_endgame_catalog_contains_only_verified_lessons():
    report = validate_all_content()["subjects"]["endgames"]["records"]
    expected = {
        content_id
        for content_id, record in report.items()
        if record["publishable"]
    }
    actual = {
        lesson["lesson_id"]
        for category in get_all_categories()
        for lesson in category["lessons"]
    }

    assert actual == expected
    assert get_lesson("rook_endgames", "philidor") is None


def test_public_endgame_lesson_never_contains_answers():
    lesson = get_lesson("king_and_pawn", "square_rule")

    assert lesson is not None
    assert lesson["positions"][-1]["stage"] == "independent_proof"
    for position in lesson["positions"]:
        assert position["answer_hidden"] is True
        assert "correct_move_san" not in position
        assert "correct_move_uci" not in position


def test_independent_endgame_failure_does_not_reveal_answer():
    lesson = get_lesson("king_and_pawn", "square_rule")
    final_index = len(lesson["positions"]) - 1
    result = check_move(
        "king_and_pawn",
        "square_rule",
        final_index,
        "a1a2",
    )

    assert result["correct"] is False
    assert result["stage"] == "independent_proof"
    assert "correct_move_san" not in result
    assert "correct_move_uci" not in result


def test_opening_catalog_hides_recognition_only_records():
    report = validate_all_content()["subjects"]["openings"]
    available = get_available_openings()

    assert len(available) == report["publishable"]
    assert all(item["key"] != "kings_pawn_opening_1_e5" for item in available)


def test_opening_lesson_steps_keep_nonempty_authored_explanations():
    steps = get_lesson_move_steps("london_system", "london_main")

    assert len(steps) > 5
    assert all(step["explanation"].strip() for step in steps)


def test_every_publishable_opening_renders_a_legal_explained_line():
    for opening_key in get_publishable_content_ids("openings"):
        steps = get_lesson_move_steps(opening_key)
        assert steps, opening_key
        assert all(step["explanation"].strip() for step in steps), opening_key
        board = chess.Board()
        for step in steps:
            board.push_san(step["move"])


def test_legacy_opening_library_is_only_a_canonical_verified_projection():
    expected = {
        opening_key.replace("_", "-")
        for opening_key in get_publishable_content_ids("openings")
    }
    assert set(OPENING_DATABASE) == expected
    assert all(record["color"] in {"white", "black"} for record in OPENING_DATABASE.values())


def test_opening_match_falls_back_to_teachable_family_and_reuses_aliases():
    # Najdorf can still be recognized, but its sparse flat line is not a
    # lesson. Route the player to the teachable Sicilian family instead.
    assert match_opening_to_library("Sicilian Najdorf Variation", "B90") == "sicilian-defense"
    assert match_opening_to_library("Giuoco Piano Game", "C54") == "italian-game"


def test_position_recognition_uses_a_verified_lesson_line():
    board = chess.Board()
    board.push_san("e4")
    opening = get_opening_for_position(board.fen())
    assert opening is not None
    assert opening.key in OPENING_DATABASE


def test_play_with_coach_catalog_is_truth_gated():
    catalog = get_lesson_catalog()
    report = validate_all_content()["subjects"]

    assert len(catalog["traps"]) == len(get_defense_ready_trap_ids())
    assert {item["key"] for item in catalog["traps"]} == {"scholars_mate"}
    assert len(catalog["endgames"]) == report["endgames"]["publishable"]
    assert all(item.get("canonical_source") for item in catalog["endgames"])


def test_play_with_coach_endgame_starts_question_first():
    db = FakeDB()
    result = asyncio.run(
        start_endgame_lesson(
            db,
            "session-1",
            "user-1",
            {"category": "king_and_pawn", "lesson_key": "square_rule"},
        )
    )

    assert result["success"] is True
    assert result["instruction"]["answer_hidden"] is True
    assert result["instruction"]["stage"] == "guided_try"
    assert "move" not in result["instruction"]


def test_play_with_coach_requires_unseen_final_endgame_answer():
    db = FakeDB()
    asyncio.run(
        start_endgame_lesson(
            db,
            "session-1",
            "user-1",
            {"category": "king_and_pawn", "lesson_key": "square_rule"},
        )
    )
    raw = get_verified_lesson_data("king_and_pawn", "square_rule")
    for position in raw["positions"][:-1]:
        result = asyncio.run(
            process_endgame_move(
                db,
                "session-1",
                position["correct_move_san"],
            )
        )
        assert result["correct"] is True

    final_wrong = asyncio.run(
        process_endgame_move(db, "session-1", "a3")
    )
    assert final_wrong["stage"] == "independent_proof"
    assert final_wrong["demonstrated"] is False
    assert "expected_move" not in final_wrong


def test_scholars_defense_starts_at_the_threat_without_the_answer():
    db = FakeDB()
    result = asyncio.run(
        start_trap_lesson(
            db,
            "session-1",
            "user-1",
            {"trap_key": "scholars_mate"},
        )
    )

    assert result["mode"] == "avoidance"
    assert result["auto_played_moves"] == ["e4", "e5", "Bc4", "Nc6", "Qh5"]
    assert result["instruction"]["answer_hidden"] is True
    assert "move" not in result["instruction"]


def test_execution_only_trap_cannot_silently_replace_a_defense_lesson():
    result = asyncio.run(
        start_trap_lesson(
            FakeDB(),
            "session-1",
            "user-1",
            {"trap_key": "legals_mate"},
        )
    )

    assert "safe-defense lesson" in result["error"]
