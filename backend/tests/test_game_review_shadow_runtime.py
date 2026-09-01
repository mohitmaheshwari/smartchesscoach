"""Phase 3 runtime bridge and invisible-persistence tests."""
from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path

from services.caption_pipeline import (
    CaptionExplanation,
    MoveTeachingDecision,
    TeachingMeta,
    TextSurface,
    VisualSurface,
)
from services.game_review_shadow_runtime import (
    adapt_simple_hang_event,
    build_shadow_storage_payload,
    derive_current_review_observations,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _decision(*, verified: bool = True) -> MoveTeachingDecision:
    return MoveTeachingDecision(
        text=TextSurface(
            caption="Your bishop on g5 could be taken.",
            rule_name="R12_BLUNDER",
        ),
        visual=VisualSurface(
            arrows=[{"from": "h6", "to": "g5"}],
            highlight_squares=["g5"],
        ),
        teaching_meta=TeachingMeta(
            has_teaching_content=True,
            principle_cue="Before moving, check whether that piece can be taken.",
        ),
        explanation=CaptionExplanation(
            board_explanation="Your bishop on g5 could be taken.",
            transferable_instruction=(
                "Before moving, check whether that piece can be taken."
            ),
            confidence="verified" if verified else "limited",
            provenance=["caption_pipeline:R12"],
            final_verified=verified,
        ),
    )


def _observation(**overrides):
    value = {
        "schema_version": 17,
        "missed_pattern": "piece_safety",
        "subtype": "simple_hang",
        "was_critical_moment": True,
        "cp_loss": 320,
    }
    value.update(overrides)
    return value


def test_current_simple_hang_adapts_exact_central_decision():
    pair = adapt_simple_hang_event(
        decision=_decision(),
        observation=_observation(),
        game_id="g",
        ply=17,
        move_number=9,
        san="Bg5",
    )
    event, features = pair
    assert event.player_authorized is True
    assert event.outcome.value == "allowed"
    assert event.evidence.quality_id == "gap:piece_safety:simple_hang"
    assert event.teaching.caption == "Your bishop on g5 could be taken."
    assert event.reflection_eligible is True
    assert features.event_id == event.event_id
    assert features.was_critical_moment is True
    assert features.cp_loss == 320


def test_old_or_unpromoted_observations_fail_closed():
    kwargs = {
        "decision": _decision(),
        "game_id": "g",
        "ply": 17,
        "move_number": 9,
        "san": "Bg5",
    }
    assert adapt_simple_hang_event(
        observation=_observation(schema_version=15), **kwargs
    ) is None
    assert adapt_simple_hang_event(
        observation=_observation(subtype="threat_ignored"), **kwargs
    ) is None


def test_unverified_central_decision_is_retained_only_as_silent_audit_event():
    event, _ = adapt_simple_hang_event(
        decision=_decision(verified=False),
        observation=_observation(),
        game_id="g",
        ply=17,
        move_number=9,
        san="Bg5",
    )
    assert event.player_authorized is False
    assert event.outcome.value == "silent"


def test_storage_payload_is_shadow_versioned_and_honestly_allows_no_plan():
    empty = build_shadow_storage_payload(
        game_id="g",
        events=(),
        features={},
        generated_at=NOW,
        source_v5_version=138,
    )
    assert empty["rollout_mode"] == "shadow"
    assert empty["source_v5_version"] == 138
    assert empty["plan"] is None

    event, features = adapt_simple_hang_event(
        decision=_decision(),
        observation=_observation(),
        game_id="g",
        ply=17,
        move_number=9,
        san="Bg5",
    )
    payload = build_shadow_storage_payload(
        game_id="g",
        events=(event,),
        features={event.event_id: features},
        generated_at=NOW,
        source_v5_version=138,
    )
    assert payload["plan"]["rollout_mode"] == "shadow"
    assert payload["selected_event_ids"] == [event.event_id]


def test_derivation_reuses_canonical_observation_authority(monkeypatch):
    captured = {}

    def fake_deriver(**kwargs):
        captured.update(kwargs)
        return [{"move_number": 7, "schema_version": 17}]

    monkeypatch.setattr(
        "services.game_review_shadow_runtime.derive_observations_for_game",
        fake_deriver,
    )
    result = derive_current_review_observations(
        game_id="g",
        user_id="u",
        user_color="white",
        pgn="pgn",
        move_evaluations=({"move_number": 7},),
        opponent_move_evaluations=({"move_number": 6},),
    )
    assert result == {7: {"move_number": 7, "schema_version": 17}}
    assert captured["decryption_v5_data"] is None
    assert captured["stockfish_analysis"]["opponent_move_evaluations"]


def test_runtime_has_no_database_network_engine_or_llm_call():
    import services.game_review_shadow_runtime as module

    source = inspect.getsource(module).lower()
    forbidden = (
        "pymongo",
        "motor",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "import stockfish",
        "chess.engine",
    )
    assert all(token not in source for token in forbidden)


def test_production_callers_persist_shadow_without_returning_it():
    root = Path(__file__).parents[2]
    route_source = (root / "backend" / "routes" / "coach.py").read_text(
        encoding="utf-8"
    )
    worker_source = (root / "backend" / "analysis_worker.py").read_text(
        encoding="utf-8"
    )
    assert "game_teaching_plan_output=_game_teaching_plan" in route_source
    assert '"game_teaching_plan": _game_teaching_plan' in route_source
    assert "game_teaching_plan_output=_game_teaching_plan" in worker_source
    assert 'analysis_doc["game_teaching_plan"]' in worker_source
    v5_source = (
        root / "backend" / "services" / "game_decryption_v5_service.py"
    ).read_text(encoding="utf-8")
    assert "game_teaching_plan_output" in v5_source
    # Shadow measurement cannot require enabling the visible API feature.
    shadow_block = v5_source[v5_source.index("# Phase 3 personalized review planner."):]
    assert "personalized_game_review_enabled" not in shadow_block
    # Phase 5 reads the stored plan, but the route's default-off projection
    # still returns the exact legacy object unless the server flag is on.
    projection = route_source[route_source.index('"decryption_v5_data": 1'):]
    projection = projection[: projection.index("}")]
    assert '"game_teaching_plan"' in projection
    assert "maybe_attach_phase5_review_fields" in route_source
