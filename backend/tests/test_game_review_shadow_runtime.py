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
from services.caption_facts import (
    LegalMaterialLossCause,
    PieceOnSquare,
    build_verified_line_cause,
)
from services.game_review_shadow_runtime import (
    VERIFIED_CAUSE_QUALITY_ID,
    adapt_review_event,
    adapt_simple_hang_event,
    build_shadow_storage_payload,
    derive_current_review_observations,
)
from services.move_observation_deriver import current_deriver_identity


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _decision(*, verified: bool = True, with_cause: bool = False) -> MoveTeachingDecision:
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
        cause=(
            LegalMaterialLossCause(
                affected=PieceOnSquare("bishop", "g5"),
                attacker=PieceOnSquare("pawn", "h6"),
                punishment_san="hxg5",
                material_loss_cp=200,
                best_move_san="Bh4",
                best_move_purpose="moves_affected_piece",
                best_move_from="g5",
                best_move_to="h4",
            )
            if with_cause else None
        ),
    )


def _observation(**overrides):
    value = {
        "schema_version": 17,
        "deriver_identity": current_deriver_identity(),
        "missed_pattern": "piece_safety",
        "subtype": "simple_hang",
        "was_critical_moment": True,
        "cp_loss": 320,
    }
    value.update(overrides)
    return value


def _allowed_mate_decision() -> MoveTeachingDecision:
    cause = build_verified_line_cause(
        fen_before="8/p1p2p1p/6p1/6Pk/2Q5/P6P/KPP2q2/3r4 b - - 4 30",
        played_san="Rd2",
        best_move_san="Qf3",
        pv_after_played=("Qg4#",),
        pv_after_best=("Qxc7", "Rf1", "Qc4", "Rf2"),
        cp_loss=10608,
    )
    assert cause is not None
    return MoveTeachingDecision(
        text=TextSurface(caption="Legacy caption", rule_name="R12_BLUNDER"),
        teaching_meta=TeachingMeta(
            has_teaching_content=True,
            mover_state_before="winning",
            mover_state_after="losing",
            decisiveness_changed=True,
        ),
        explanation=CaptionExplanation(
            board_explanation="Legacy caption",
            transferable_instruction="Legacy principle",
            confidence="verified",
            provenance=["caption_pipeline:R12"],
            final_verified=True,
        ),
        debug_facts={"cp_loss": 10608},
        cause=cause,
    )


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


def test_quality_v2_requires_both_master_and_its_own_flag():
    kwargs = {
        "decision": _decision(with_cause=True),
        "observation": _observation(),
        "game_id": "g",
        "ply": 17,
        "move_number": 9,
        "san": "Bg5",
    }
    default_event, _ = adapt_simple_hang_event(**kwargs, env={})
    assert "cause" not in default_event.contract_dict()

    master_only, _ = adapt_simple_hang_event(
        **kwargs,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    )
    assert "cause" not in master_only.contract_dict()

    v2_event, _ = adapt_simple_hang_event(
        **kwargs,
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )
    assert v2_event.contract_dict()["cause"]["affected"]["square"] == "g5"


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


def test_verified_line_event_exists_only_when_both_v2_flags_are_enabled():
    kwargs = {
        "decision": _allowed_mate_decision(),
        "observation": _observation(
            missed_pattern=None,
            subtype=None,
        ),
        "game_id": "g-mate",
        "ply": 60,
        "move_number": 30,
        "san": "Rd2",
    }
    assert adapt_review_event(**kwargs, env={}) is None
    assert adapt_review_event(
        **kwargs,
        env={"PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true"},
    ) is None
    event, features = adapt_review_event(
        **kwargs,
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )
    assert event.evidence.quality_id == VERIFIED_CAUSE_QUALITY_ID
    assert event.player_authorized is True
    assert event.contract_dict()["cause"]["lesson_kind"] == "allowed_forced_mate"
    assert features.cp_loss == 10608


def test_quality_v2_fails_closed_for_missing_or_stale_deriver_identity():
    env = {
        "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
        "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
    }
    kwargs = {
        "decision": _decision(with_cause=True),
        "game_id": "g",
        "ply": 17,
        "move_number": 9,
        "san": "Bg5",
        "env": env,
    }
    assert adapt_review_event(observation={}, **kwargs) is None
    assert adapt_review_event(
        observation=_observation(
            deriver_identity={
                **current_deriver_identity(),
                "manifest_sha256": "stale",
            }
        ),
        **kwargs,
    ) is None
    assert adapt_review_event(observation=_observation(), **kwargs) is not None


def test_v2_simple_hang_keeps_its_existing_quality_identity():
    event, _ = adapt_review_event(
        decision=_decision(with_cause=True),
        observation=_observation(),
        game_id="g",
        ply=17,
        move_number=9,
        san="Bg5",
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )
    assert event.evidence.quality_id == "gap:piece_safety:simple_hang"


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
    assert empty["deriver_identity"] == current_deriver_identity()
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


def test_quality_v2_storage_uses_the_practical_candidate_formula_only_when_enabled():
    event, features = adapt_simple_hang_event(
        decision=_decision(),
        observation=_observation(),
        game_id="g",
        ply=17,
        move_number=9,
        san="Bg5",
    )
    base = build_shadow_storage_payload(
        game_id="g",
        events=(event,),
        features={event.event_id: features},
        generated_at=NOW,
        source_v5_version=138,
        env={},
    )
    v2 = build_shadow_storage_payload(
        game_id="g",
        events=(event,),
        features={event.event_id: features},
        generated_at=NOW,
        source_v5_version=138,
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )
    assert base["formula_id"] == "D_teaching_then_critical"
    assert v2["formula_id"] == "E_transition_then_teaching"


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
