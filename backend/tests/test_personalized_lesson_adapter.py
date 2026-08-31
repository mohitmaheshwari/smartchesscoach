import asyncio

from services.personalized_lesson_adapter import (
    public_lesson_descriptor,
    resolve_personalized_lesson,
    supports_personalized_lesson_identity,
)


class _NoDB:
    pass


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
    assert descriptor["skill_id"] == "opening_london_white"


def test_verified_trap_projection_is_defense_first_when_available():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap",
        content_id="scholars_mate",
        params={"mode": "avoidance"},
    ))

    assert descriptor["canonical_source"] == "backend/data/traps.json"
    assert descriptor["skill_id"] == "defend_scholars_mate"
    assert descriptor["items"]
    assert "danger" in descriptor["intro"].lower() or descriptor["rule"]


def test_verified_trap_set_is_one_distinct_defense_per_family_trap():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap_set",
        content_id="italian-game",
        params={"skill_id": "trap_set_italian"},
    ))
    public = public_lesson_descriptor(descriptor)

    assert descriptor["kind"] == "trap_set"
    assert descriptor["canonical_source"] == "backend/data/traps.json"
    assert descriptor["skill_id"] == "trap_set_italian"
    assert len(descriptor["items"]) == 5
    assert len({item["fen"] for item in descriptor["items"]}) == 5
    assert descriptor["items"][-1]["stage"] == "transfer"
    assert all("_expected_uci" not in item for item in public["items"])


def test_verified_endgame_uses_tree_skill_id_without_explicit_param():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="endgame",
        content_id="king_and_pawn/square_rule",
    ))

    assert descriptor["skill_id"] == "endgame_rule_of_square"


def test_verified_trap_set_uses_tree_skill_id_without_explicit_param():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap_set",
        content_id="italian-game",
    ))

    assert descriptor["skill_id"] == "trap_set_italian"


def test_curriculum_only_enters_workspace_for_resolvable_canonical_lessons():
    assert supports_personalized_lesson_identity(
        "opening", "london_system"
    )
    assert supports_personalized_lesson_identity(
        "trap", "fried_liver_defense"
    )
    assert supports_personalized_lesson_identity(
        "trap_set", "italian-game"
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
