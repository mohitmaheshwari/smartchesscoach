from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routes import training_advanced
from trick_library_service import (
    get_public_trap_by_key,
    get_public_traps,
    get_trap_by_key,
)


PRIVATE_FIELDS = {
    "setup_moves",
    "trap_line",
    "winning_line",
    "winning_move",
    "full_sequence",
    "practice_fen",
    "defense_setup_moves",
    "defense_line",
    "safe_moves",
}


def test_public_trap_catalog_preserves_every_lesson_without_answers():
    traps = get_public_traps()

    assert len(traps) == 36
    assert all(trap["answer_hidden"] is True for trap in traps)
    assert all(PRIVATE_FIELDS.isdisjoint(trap) for trap in traps)
    assert all(trap["practice_href"].startswith("/training?") for trap in traps)


def test_public_detail_is_redacted_while_server_copy_keeps_the_lesson():
    public = get_public_trap_by_key("fried_liver_defense")
    private = get_trap_by_key("fried_liver_defense")

    assert public and private
    assert PRIVATE_FIELDS.isdisjoint(public)
    assert private.get("defense_line")


@pytest.mark.asyncio
async def test_answer_bearing_legacy_practice_endpoint_is_retired():
    with pytest.raises(HTTPException) as exc:
        await training_advanced.get_trick_for_practice(
            "fried_liver_defense", "avoidance"
        )

    assert exc.value.status_code == 410
    assert "personalized" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_client_declared_trap_success_cannot_write_learning_evidence():
    with pytest.raises(HTTPException) as exc:
        await training_advanced.record_trap_attempt_endpoint(
            None,
            {"trap_key": "fried_liver_defense", "mode": "avoidance", "success": True},
            SimpleNamespace(user_id="u1"),
        )

    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_retired_avoidance_grader_never_starts_a_runtime_engine():
    with pytest.raises(HTTPException) as exc:
        await training_advanced.validate_avoidance_move({
            "fen": "not trusted",
            "user_move": "not trusted",
        })

    assert exc.value.status_code == 410
