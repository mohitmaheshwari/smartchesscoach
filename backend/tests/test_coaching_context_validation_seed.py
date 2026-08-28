"""Safety and shape tests for the isolated coaching-context validation data."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.seed_coaching_context_validation import (  # noqa: E402
    FIXTURE_SET,
    MUTABLE_COLLECTIONS,
    VALIDATION_DB_NAME,
    build_fixture_documents,
    ensure_validation_database_name,
    fixture_filter,
    validate_fixture_documents,
)


NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def test_database_guard_accepts_only_the_isolated_database():
    assert ensure_validation_database_name(VALIDATION_DB_NAME) == VALIDATION_DB_NAME
    for unsafe in ("test_database", "production", "", "chessguru_validation_copy"):
        with pytest.raises(ValueError):
            ensure_validation_database_name(unsafe)


def test_fixture_set_covers_the_required_fail_closed_states():
    documents = build_fixture_documents(NOW)
    users = {row["user_id"] for row in documents["users"]}
    assert {
        "validation_ctx_no_focus",
        "validation_ctx_primary",
        "validation_ctx_no_opportunity",
        "validation_ctx_unauthorized",
        "validation_ctx_missing_instruction",
    }.issubset(users)

    focuses = {row["user_id"]: row for row in documents["user_active_focus"]}
    assert "validation_ctx_no_focus" not in focuses
    assert focuses["validation_ctx_primary"]["detector_quality_id"] == (
        "gap:piece_safety:simple_hang"
    )
    assert focuses["validation_ctx_missing_instruction"]["instruction_id"] is None
    assert focuses["validation_ctx_unauthorized"]["detector_quality_id"] != (
        "gap:piece_safety:simple_hang"
    )

    observations = documents["move_observations"]
    assert any(row["user_id"] == "validation_ctx_primary" for row in observations)
    assert not any(
        row["user_id"] == "validation_ctx_no_opportunity" for row in observations
    )

    memories = {row["user_id"]: row for row in documents["coach_memory"]}
    assert memories["validation_ctx_no_focus"]["learning"] == {}
    assert memories["validation_ctx_unauthorized"]["learning"] == {}


def test_every_mutable_document_is_tagged_and_contains_no_real_identity_fields():
    documents = build_fixture_documents(NOW)
    validate_fixture_documents(documents)

    assert set(documents) == set(MUTABLE_COLLECTIONS)
    for rows in documents.values():
        for row in rows:
            assert row["validation_fixture_set"] == FIXTURE_SET


def test_reset_filter_can_only_select_this_fixture_set():
    assert fixture_filter() == {"validation_fixture_set": FIXTURE_SET}
