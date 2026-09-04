"""Phase 6 private old/new Game Review validation evidence."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import inspect
import json

import pytest

from services.game_review_contracts import (
    ReviewContractViolation,
    ReviewPresentationMode,
)
from services.game_review_validation_service import (
    build_validation_review_document,
    blind_variant_modes,
    ensure_validation_indexes,
    public_validation_packet,
    public_validation_rubric,
    public_validation_submission,
    resolve_blind_variant,
    store_validation_review,
    validate_validation_ratings,
)


NOW = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)


def _ratings():
    return {
        "chess_truth": "correct",
        "moment_choice": "strong",
        "explanation_clarity": "clear",
        "personalization": "specific",
        "reflection_value": "useful",
        "story_coherence": "coherent",
        "next_action_quality": "useful",
    }


def test_public_rubric_has_stable_unique_ids_and_labels():
    rubric = public_validation_rubric()
    assert [item["id"] for item in rubric] == list(_ratings())
    for dimension in rubric:
        option_ids = [option["id"] for option in dimension["options"]]
        assert len(option_ids) == len(set(option_ids))
        assert all(option["label"] for option in dimension["options"])


def test_validation_indexes_enforce_idempotency_and_reentry_lookup():
    class FakeCollection:
        def __init__(self):
            self.calls = []

        async def create_index(self, keys, **kwargs):
            self.calls.append((keys, kwargs))

    class FakeDb:
        def __init__(self):
            self.collection = FakeCollection()

        def __getitem__(self, _name):
            return self.collection

    database = FakeDb()
    asyncio.run(ensure_validation_indexes(database))
    assert database.collection.calls[0] == ("review_id", {"unique": True})
    assert database.collection.calls[1][0] == [
        ("reviewer_user_id", 1),
        ("game_id", 1),
        ("presentation_variant", 1),
        ("source_v5_version", 1),
        ("plan_id", 1),
    ]


def test_blind_variants_are_stable_complete_and_access_controlled():
    first = blind_variant_modes("validator-1", "game-1")
    second = blind_variant_modes("validator-1", "game-1")
    assert first == second
    assert set(first) == {"a", "b"}
    assert set(first.values()) == {
        ReviewPresentationMode.LEGACY,
        ReviewPresentationMode.PERSONALIZED,
    }
    assert resolve_blind_variant(
        comparison_allowed=True,
        requested_variant=None,
    ) == "a"
    with pytest.raises(ReviewContractViolation, match="not enabled"):
        resolve_blind_variant(
            comparison_allowed=False,
            requested_variant="a",
        )
    with pytest.raises(ReviewContractViolation, match="unknown"):
        resolve_blind_variant(
            comparison_allowed=True,
            requested_variant="personalized",
        )


def test_ratings_require_every_exact_server_dimension_and_option():
    assert validate_validation_ratings(_ratings()) == _ratings()

    missing = _ratings()
    missing.pop("story_coherence")
    with pytest.raises(ReviewContractViolation, match="every rubric dimension"):
        validate_validation_ratings(missing)

    tampered = _ratings()
    tampered["chess_truth"] = "five_stars"
    with pytest.raises(ReviewContractViolation, match="chess_truth"):
        validate_validation_ratings(tampered)


def test_document_derives_critical_truth_failure_and_contains_no_chess_payload():
    ratings = _ratings()
    ratings["chess_truth"] = "critical_false_claim"
    document = build_validation_review_document(
        reviewer_user_id="validator-1",
        game_id="game-1",
        presentation_variant="a",
        presentation_mode="personalized",
        ratings=ratings,
        notes="The claimed relationship is not on the board.",
        source_v5_version=138,
        plan_id="plan-1",
        submitted_at=NOW,
    )
    assert document["critical_truth_failure"] is True
    assert document["review_id"].startswith("review-validation:")
    encoded = json.dumps(document).lower()
    for forbidden in (
        '"fen"',
        '"pgn"',
        '"caption"',
        '"detector_id"',
        '"reflection_answer"',
    ):
        assert forbidden not in encoded


def test_personalized_document_requires_rendered_plan_but_legacy_does_not():
    with pytest.raises(ReviewContractViolation, match="plan_id"):
        build_validation_review_document(
            reviewer_user_id="validator-1",
            game_id="game-1",
            presentation_variant="a",
            presentation_mode="personalized",
            ratings=_ratings(),
            notes="",
            source_v5_version=138,
            plan_id=None,
            submitted_at=NOW,
        )

    legacy = build_validation_review_document(
        reviewer_user_id="validator-1",
        game_id="game-1",
        presentation_variant="b",
        presentation_mode="legacy",
        ratings=_ratings(),
        notes="",
        source_v5_version=138,
        plan_id=None,
        submitted_at=NOW,
    )
    assert legacy["plan_id"] is None


def test_storage_is_idempotent_and_public_projection_is_minimal():
    class FakeCollection:
        def __init__(self):
            self.calls = []

        async def update_one(self, selector, update, upsert=False):
            self.calls.append((selector, update, upsert))

    document = build_validation_review_document(
        reviewer_user_id="validator-1",
        game_id="game-1",
        presentation_variant="b",
        presentation_mode="legacy",
        ratings=_ratings(),
        notes="Useful baseline.",
        source_v5_version=138,
        plan_id=None,
        submitted_at=NOW,
    )
    collection = FakeCollection()

    async def exercise():
        await store_validation_review(collection, document)
        return await store_validation_review(collection, document)

    stored = asyncio.run(exercise())
    assert len(collection.calls) == 2
    assert collection.calls[0][0] == {"review_id": document["review_id"]}
    assert collection.calls[0][2] is True
    assert public_validation_submission(stored) == {
        "presentation_variant": "b",
        "ratings": _ratings(),
        "notes": "Useful baseline.",
        "critical_truth_failure": False,
        "submitted_at": NOW.isoformat(),
    }


def test_public_packet_drives_client_labels_and_reentry():
    packet = public_validation_packet(
        active_variant="a",
        personalized_available=True,
        existing_submission=None,
    )
    assert packet["enabled"] is True
    assert packet["active_variant"] == "a"
    assert packet["comparison_ready"] is True
    assert packet["presentation_options"] == [
        {"id": "a", "label": "Review A"},
        {"id": "b", "label": "Review B"},
    ]
    assert packet["rubric"] == public_validation_rubric()


def test_validation_service_has_no_board_engine_network_or_llm_dependency():
    import services.game_review_validation_service as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "import chess",
        "stockfish",
        "requests",
        "httpx",
        "openai",
        "anthropic",
    )
    assert all(token not in source for token in forbidden)
