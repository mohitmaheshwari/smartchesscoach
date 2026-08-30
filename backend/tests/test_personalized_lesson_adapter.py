import asyncio

from services.personalized_lesson_adapter import (
    grade_personalized_move,
    public_lesson_descriptor,
    resolve_personalized_lesson,
    supports_personalized_lesson_identity,
)


class _NoDB:
    pass


SCREENSHOT_FEN = (
    "r1bq1rk1/bppp1pp1/p4nnp/8/1PBNP3/"
    "P1N2Q2/2P2PPP/R1B2RK1 w - - 0 1"
)


def test_verified_endgame_is_normalized_without_public_answers():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="endgame",
        content_id="king_and_pawn/square_rule",
    ))
    public = public_lesson_descriptor(descriptor)

    assert public["canonical_source"] == (
        "backend/data/coaching/endgame_theory_tree.json"
    )
    assert public["items"][-1]["stage"] == "transfer"
    assert all(
        "correct_move" not in str(item)
        and "_endgame_position_index" not in item
        for item in public["items"]
    )


def test_verified_opening_projection_reads_canonical_authored_steps():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="opening",
        content_id="london_system",
        params={"player_color": "white"},
    ))
    public = public_lesson_descriptor(descriptor)

    assert public["canonical_source"] == "backend/data/opening_curriculum.json"
    assert public["items"]
    assert all("_expected_san" not in item for item in public["items"])
    assert all("_expected_reason" not in item for item in public["items"])
    assert public["items"][0]["reason_choices"]
    assert public["content_version"]


def test_verified_trap_projection_is_defense_first_when_available():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap",
        content_id="scholars_mate",
        params={"mode": "avoidance"},
    ))

    assert descriptor["canonical_source"] == "backend/data/traps.json"
    assert descriptor["items"]
    assert "danger" in descriptor["intro"].lower() or descriptor["rule"]


def test_curriculum_only_enters_workspace_for_resolvable_canonical_lessons():
    assert supports_personalized_lesson_identity(
        "opening", "london_system"
    )
    assert supports_personalized_lesson_identity(
        "trap", "fried_liver_defense"
    )
    assert supports_personalized_lesson_identity(
        "endgame", "basic_mates/queen_mate"
    )
    assert supports_personalized_lesson_identity(
        "concept", "piece_safety"
    )
    assert not supports_personalized_lesson_identity(
        "concept", "iqp_play"
    )
    assert not supports_personalized_lesson_identity(
        "concept", "not_a_real_lesson"
    )


def test_piece_safety_uses_exact_screenshot_geometry_and_filters_mismatches(
    monkeypatch,
):
    async def supply(db, user_id, pattern, limit):
        assert pattern == "piece_safety"
        assert limit == 20
        return {
            "own_puzzles": [
                {
                    "puzzle_id": "not-piece-safety",
                    "fen": "7k/8/8/8/8/8/4K3/8 w - - 0 1",
                    "best_move_san": "Kf3",
                    "source": "own_game",
                    "source_game_id": "wrong-game",
                },
                {
                    "puzzle_id": "screenshot-position",
                    "fen": SCREENSHOT_FEN,
                    "best_move_san": "Ne6",
                    "source": "own_game",
                    "source_game_id": "screenshot-game",
                    "move_number": 18,
                },
            ],
            "community_puzzles": [],
        }

    monkeypatch.setattr(
        "services.puzzle_extraction_service.get_pattern_training_puzzles",
        supply,
    )
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="concept",
        content_id="piece_safety",
    ))
    item = descriptor["items"][0]
    public = public_lesson_descriptor(descriptor)["items"][0]

    assert len(descriptor["items"]) == 1
    assert item["item_id"] == "screenshot-position"
    assert item["side_to_move"] == "White"
    assert item["reason_prompt"] == "Which piece needs your attention first?"
    assert item["_expected_reason"] == "piece_in_danger:d4"
    assert item["_help_squares"] == ["d4", "a7"]
    assert "knight on d4" in item["_help_message"]
    assert "bishop on a7" in item["_help_message"]
    choices = {choice["id"]: choice for choice in public["reason_choices"]}
    assert choices["piece_in_danger:d4"]["label"] == (
        "My knight on d4 can be taken."
    )
    assert public["reason_choices"][0]["id"] != "piece_in_danger:d4"
    assert "_problem_square" not in public


def test_piece_safety_grader_requires_the_move_to_solve_the_named_danger(
    monkeypatch,
):
    async def evaluate(**kwargs):
        return {
            "is_acceptable": True,
            "best_move_san": "Ne6",
            "feedback": "legacy generic feedback",
        }

    monkeypatch.setattr(
        "services.puzzle_move_evaluator.evaluate_puzzle_move",
        evaluate,
    )
    descriptor = {
        "kind": "concept",
        "items": [],
    }
    item = {
        "fen": SCREENSHOT_FEN,
        "_expected_san": "Ne6",
        "_puzzle_evaluator": True,
        "_problem_square": "d4",
        "_problem_piece_name": "knight",
        "_on_correct": (
            "Yes. You dealt with the attack on your knight on d4. "
            "Before starting your own idea, check whether an attacked piece "
            "needs help."
        ),
        "_on_wrong": (
            "That still leaves your knight on d4 where the bishop on a7 "
            "can take it. Deal with that attack first."
        ),
    }

    correct = asyncio.run(grade_personalized_move(descriptor, item, "d4e6"))
    ignored = asyncio.run(grade_personalized_move(descriptor, item, "g1h1"))

    assert correct["correct"] is True
    assert "knight on d4" in correct["feedback"]
    assert ignored["correct"] is False
    assert "bishop on a7" in ignored["feedback"]
    assert "legacy generic feedback" not in str((correct, ignored))
