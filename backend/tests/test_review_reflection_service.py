"""Phase 2 tests for backend-owned, event-scoped reflection."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import inspect
import json

import pytest

from quick_tag_registry import QuickTagEngine, generate_quick_tags
from services.caption_pipeline import CaptionExplanation, MoveTeachingDecision, TextSurface
from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    EventActor,
    EventOutcome,
    PlayerReflection,
    ReviewContractViolation,
)
from services.personal_curriculum import (
    PIC_CANONICAL_SOURCE,
    PIC_CONTENT_ID,
)
from services.game_review_event_adapter import (
    MoveEventContext,
    adapt_move_teaching_decision,
)
from services.review_reflection_service import (
    build_document_from_stored_contracts,
    build_event_reflection_document,
    build_pic_simple_hang_reflection_prompt,
    build_reflection_prompt,
    public_reflection_history,
    public_reflection_receipt,
    store_event_reflection,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _event(*, reflection_requested: bool = True):
    decision = MoveTeachingDecision(
        text=TextSurface(caption="Your bishop could be taken."),
        explanation=CaptionExplanation(
            board_explanation="Your bishop could be taken.",
            transferable_instruction="Check every piece before you move.",
            final_verified=True,
            confidence="verified",
        ),
    )
    context = MoveEventContext(
        game_id="fixture-game",
        ply=23,
        move_number=12,
        san="Bg5",
        actor=EventActor.USER,
        concept_id="piece_safety.undefended_piece",
        outcome=EventOutcome.ALLOWED,
        quality_id="gap:piece_safety:simple_hang",
        provenance=("move_observation:fixture-game:23",),
        opportunity_eligible=True,
        requested_surface=QualitySurface.PLAN,
        reflection_requested=reflection_requested,
        content_ref=PIC_CONTENT_ID,
        canonical_source=PIC_CANONICAL_SOURCE,
    )
    return adapt_move_teaching_decision(decision, context)


def _quick_tags(rating: int = 900):
    return generate_quick_tags(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        user_move="e4",
        best_move="e4",
        mistake_category="missed_forcing_move",
        rating=rating,
        move_number=1,
        include_honest_escapes=True,
    )


def test_registry_always_returns_both_honest_escape_options_within_band_cap():
    for rating in (700, 1100, 1500, 1900):
        result = _quick_tags(rating)
        expected_cap = QuickTagEngine(rating).adaptive_config["max_quick_tags"]
        ids = result["shown_tag_ids"]
        assert "not_sure" in ids
        assert "none_of_these" in ids
        assert result["escape_option_ids"] == ["not_sure", "none_of_these"]
        assert len(ids) <= expected_cap


def test_legacy_quick_tag_entrypoint_keeps_its_original_response_contract():
    result = generate_quick_tags(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        user_move="e4",
        best_move="e4",
        mistake_category="missed_forcing_move",
        rating=900,
        move_number=1,
    )
    assert set(result) == {
        "tags",
        "shown_tag_ids",
        "max_selections",
        "neutral_option_id",
    }
    assert "none_of_these" not in result["shown_tag_ids"]


def test_prompt_uses_exact_backend_ids_and_labels_without_client_invention():
    tags = _quick_tags()
    prompt = build_reflection_prompt(_event(), tags)

    assert prompt.public_dict()["options"] == [
        {"id": item["id"], "label": item["label"]} for item in tags["tags"]
    ]
    assert prompt.public_dict()["input_mode"] == "options_only"
    assert prompt.question == "What were you thinking before this move?"


def test_pic_prompt_uses_the_canonical_registry_with_honest_escapes():
    prompt = build_pic_simple_hang_reflection_prompt(
        _event(),
        fen_before=(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/"
            "RNBQKBNR w KQkq - 0 1"
        ),
        user_move="e4",
        best_move="e4",
        rating=900,
        cp_loss=200,
        move_number=1,
    )
    assert {"not_sure", "none_of_these"}.issubset(prompt.option_ids)


def test_prompt_rejects_diagnostic_or_non_reflection_event():
    with pytest.raises(ReviewContractViolation, match="reflection-eligible"):
        build_reflection_prompt(_event(reflection_requested=False), _quick_tags())


def test_prompt_rejects_registry_output_without_honest_escapes():
    with pytest.raises(ReviewContractViolation, match="not_sure and none_of_these"):
        build_reflection_prompt(
            _event(),
            {"tags": [{"id": "played_fast", "label": "I played too fast"}]},
        )


def test_stored_document_is_event_scoped_options_only_and_contains_no_raw_board():
    event = _event()
    prompt = build_reflection_prompt(event, _quick_tags())
    reflection = PlayerReflection(
        prompt_id=prompt.prompt_id,
        event_id=event.event_id,
        shown_option_ids=prompt.option_ids,
        selected_option_id="not_sure",
        elapsed_ms=1200,
        answered_before_reveal=True,
        submitted_at=NOW,
    )
    document = build_event_reflection_document(
        user_id="user-fixture",
        game_id="fixture-game",
        event=event,
        prompt=prompt,
        reflection=reflection,
    )

    encoded = json.dumps(document, sort_keys=True).lower()
    assert document["reflection_kind"] == "game_review_event"
    assert document["event"]["event_id"] == event.event_id
    assert document["response"]["shown_option_ids"] == list(prompt.option_ids)
    for forbidden in ("free_text", '"fen"', '"pgn"', '"user_move"', '"best_move"'):
        assert forbidden not in encoded


def test_stored_contract_submission_accepts_only_the_exact_server_prompt():
    event = _event()
    prompt = build_reflection_prompt(event, _quick_tags())
    document = build_document_from_stored_contracts(
        user_id="user-fixture",
        game_id="fixture-game",
        event_contract=event.contract_dict(),
        prompt_contract=prompt.public_dict(),
        shown_option_ids=prompt.option_ids,
        selected_option_id="not_sure",
        elapsed_ms=500,
        answered_before_reveal=True,
    )
    assert document["response"]["selected_option_id"] == "not_sure"

    with pytest.raises(ReviewContractViolation, match="exactly match"):
        build_document_from_stored_contracts(
            user_id="user-fixture",
            game_id="fixture-game",
            event_contract=event.contract_dict(),
            prompt_contract=prompt.public_dict(),
            shown_option_ids=("not_sure", "none_of_these"),
            selected_option_id="not_sure",
            elapsed_ms=500,
            answered_before_reveal=True,
        )


def test_stored_contract_submission_rejects_tampered_authorization():
    event = _event()
    prompt = build_reflection_prompt(event, _quick_tags())
    event_contract = event.contract_dict()
    event_contract["display"]["authorized"] = False
    with pytest.raises(ReviewContractViolation, match="not eligible"):
        build_document_from_stored_contracts(
            user_id="user-fixture",
            game_id="fixture-game",
            event_contract=event_contract,
            prompt_contract=prompt.public_dict(),
            shown_option_ids=prompt.option_ids,
            selected_option_id="not_sure",
            elapsed_ms=500,
            answered_before_reveal=True,
        )


def test_storage_is_idempotent_and_receipt_hides_detector_details():
    class FakeCollection:
        def __init__(self):
            self.calls = []

        async def update_one(self, selector, update, upsert=False):
            self.calls.append((selector, update, upsert))

    event = _event()
    prompt = build_reflection_prompt(event, _quick_tags())
    reflection = PlayerReflection(
        prompt_id=prompt.prompt_id,
        event_id=event.event_id,
        shown_option_ids=prompt.option_ids,
        selected_option_id="none_of_these",
        elapsed_ms=800,
        answered_before_reveal=False,
        submitted_at=NOW,
    )
    document = build_event_reflection_document(
        user_id="user-fixture",
        game_id="fixture-game",
        event=event,
        prompt=prompt,
        reflection=reflection,
    )
    collection = FakeCollection()

    async def exercise_storage():
        stored_document = await store_event_reflection(collection, document)
        await store_event_reflection(collection, document)
        return stored_document

    stored = asyncio.run(exercise_storage())

    assert len(collection.calls) == 2
    assert collection.calls[0][0] == {"reflection_id": document["reflection_id"]}
    assert collection.calls[0][2] is True
    receipt = public_reflection_receipt(stored)
    assert receipt == {
        "success": True,
        "reflection_id": document["reflection_id"],
        "event_id": event.event_id,
        "selected_option_id": "none_of_these",
    }
    assert "quality_id" not in receipt


def test_public_history_exposes_only_reentry_state():
    history = public_reflection_history([{
        "event": {
            "event_id": "event-1",
            "detector_id": "private-detector",
            "fen": "private-board",
        },
        "response": {
            "prompt_id": "prompt-1",
            "selected_option_id": "not_sure",
            "answered_before_reveal": True,
            "shown_option_ids": ["not_sure", "none_of_these"],
            "elapsed_ms": 900,
        },
        "provenance": {"quality_id": "private-quality"},
    }])

    assert history == [{
        "event_id": "event-1",
        "prompt_id": "prompt-1",
        "selected_option_id": "not_sure",
        "answered_before_reveal": True,
    }]
    assert "private" not in json.dumps(history).lower()


def test_reflection_service_has_no_board_engine_network_or_llm_dependency():
    import services.review_reflection_service as module

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
