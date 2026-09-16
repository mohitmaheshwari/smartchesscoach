from copy import deepcopy
import time

import chess
import pytest

from coach_play.v2.contracts import (
    CandidateFocus,
    CandidateNovelty,
    CandidateTiming,
    CandidateUrgency,
    CoachingCandidate,
)
from coach_play.v2.shadow_conductor import (
    build_bounded_shadow_packet_from_unified_response,
    SHADOW_POLICIES,
    SHADOW_SCHEMA_VERSION,
    UNIFIED_V1_ADAPTER_VERSION,
    build_shadow_packet,
    build_shadow_packet_from_unified_response,
    candidate_from_unified_decision,
)


def _candidate(
    candidate_id: str,
    *,
    urgency: CandidateUrgency = CandidateUrgency.IMPORTANT,
    focus: CandidateFocus = CandidateFocus.NONE,
    novelty: CandidateNovelty = CandidateNovelty.NEW,
    category: str = "piece_safety",
    phase: str | None = "middlegame",
    verified: bool = True,
) -> CoachingCandidate:
    return CoachingCandidate(
        candidate_id=candidate_id,
        turn_id="12:e2e4",
        source="test",
        timing=CandidateTiming.AFTER_MOVE,
        category=category,
        concept_key=category,
        claim="Your knight on e5 has no defender.",
        transferable_instruction=(
            "Before moving a defender, check what it leaves loose."
        ),
        urgency=urgency,
        focus_relevance=focus,
        novelty=novelty,
        assistance_level=0,
        proof_authority="caption_pipeline",
        proof_references=("rule-1",),
        proof_verified=verified,
        game_phase=phase,
        evidence={
            "fen": "4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
            "move": "e5c4",
            "source_version": "fixture.v1",
            "eval_valid": True,
        },
        visual={"highlight_squares": ["e5"]},
    )


def test_unverified_candidate_is_rejected_fail_closed():
    packet = build_shadow_packet(
        [_candidate("bad", verified=False)],
        created_at="2026-09-16T00:00:00+00:00",
    )
    assert packet["candidate_count"] == 0
    assert packet["rejected_count"] == 1
    assert packet["rejected"][0]["reasons"] == ["proof_not_verified"]
    assert all(
        result["winner_candidate_id"] is None for result in packet["policies"].values()
    )


def test_unified_adapter_requires_visible_verified_caption():
    base = {
        "source": "pwc_unified_v1",
        "layer": "advisory",
        "category": "piece_safety",
        "conceptKey": "loose_piece",
        "text": "Your knight on e5 has no defender.",
        "instruction": "Check what your move leaves loose.",
        "focusMatch": True,
        "proof": {"caption_verified": True, "rule_name": "loose-piece"},
    }
    evidence = {"eval_valid": True, "cp_loss": 180, "move_quality": "mistake"}
    candidate = candidate_from_unified_decision(
        turn_id="12:e2e4",
        decision=base,
        engine_evidence=evidence,
        fen_before="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
        uci="e5c4",
    )
    assert candidate is not None
    assert candidate.admitted is True
    assert candidate.focus_relevance == CandidateFocus.PRIMARY
    assert candidate.novelty == CandidateNovelty.UNKNOWN

    assert (
        candidate_from_unified_decision(
            turn_id="12:e2e4",
            decision={**base, "layer": "silent"},
            engine_evidence=evidence,
            fen_before="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
            uci="e5c4",
        )
        is None
    )
    rejected = candidate_from_unified_decision(
        turn_id="12:e2e4",
        decision={**base, "proof": {"caption_verified": False}},
        engine_evidence=evidence,
        fen_before="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
        uci="e5c4",
    )
    assert rejected is not None
    assert rejected.admitted is False
    assert rejected.abstention_reason == ("caption_not_verified;caption_rule_missing")


def test_shadow_packet_is_deterministic_and_does_not_mutate_candidates():
    candidates = [
        _candidate("danger", urgency=CandidateUrgency.IMMEDIATE_DANGER),
        _candidate("focus", focus=CandidateFocus.PRIMARY),
    ]
    before = [deepcopy(candidate.to_document()) for candidate in candidates]
    first = build_shadow_packet(
        candidates,
        created_at="2026-09-16T00:00:00+00:00",
    )
    second = build_shadow_packet(
        reversed(candidates),
        created_at="2026-09-16T00:00:00+00:00",
    )
    assert first == second
    assert [candidate.to_document() for candidate in candidates] == before
    assert first["schema_version"] == SHADOW_SCHEMA_VERSION
    assert first["player_visible"] is False
    assert set(first["policies"]) == set(SHADOW_POLICIES)


def test_policy_disagreement_is_measured_not_resolved():
    packet = build_shadow_packet(
        [
            _candidate(
                "danger",
                urgency=CandidateUrgency.IMMEDIATE_DANGER,
                focus=CandidateFocus.NONE,
                novelty=CandidateNovelty.REPEATED,
            ),
            _candidate(
                "focus",
                urgency=CandidateUrgency.TEACHABLE,
                focus=CandidateFocus.PRIMARY,
                novelty=CandidateNovelty.NEW,
            ),
        ]
    )
    assert packet["disagreement"] is True
    winners = {
        name: value["winner_candidate_id"] for name, value in packet["policies"].items()
    }
    assert winners["safety_focus_lexicographic"] == "danger"
    assert winners["expected_learning_value"] == "focus"


def test_duplicate_candidate_ids_are_recorded_once():
    packet = build_shadow_packet([_candidate("same"), _candidate("same")])
    assert packet["candidate_count"] == 1
    assert len(packet["candidates"]) == 1


def test_conflicting_duplicate_candidate_id_is_rejected():
    packet = build_shadow_packet(
        [
            _candidate("same", category="piece_safety"),
            _candidate("same", category="king_safety"),
        ]
    )
    assert packet["candidate_count"] == 1
    assert packet["rejected_count"] == 1
    assert packet["rejected"][0]["reasons"] == ["duplicate_candidate_conflict"]


def test_equal_policy_scores_are_recorded_as_ties():
    packet = build_shadow_packet([_candidate("b"), _candidate("a")])
    for result in packet["policies"].values():
        assert result["winner_candidate_id"] == "a"
        assert result["tie"] is True
        assert result["tied_candidate_ids"] == ["a", "b"]


def test_live_response_adapter_is_observational_and_non_mutating():
    live_response = {
        "shouldAutoCommit": False,
        "coachingDecision": {
            "source": "pwc_unified_v1",
            "layer": "critical_interrupt",
            "category": "piece_safety",
            "conceptKey": "loose_piece",
            "text": "Your knight on e5 has no defender.",
            "instruction": "Check what the move leaves loose.",
            "focusMatch": True,
            "proof": {
                "caption_verified": True,
                "rule_name": "loose-piece",
            },
        },
        "visual": {"arrows": [], "highlightSquares": ["e5"]},
    }
    before = deepcopy(live_response)
    packet = build_shadow_packet_from_unified_response(
        turn_id="12:e2e4",
        live_response=live_response,
        engine_evidence={
            "eval_valid": True,
            "move_quality": "blunder",
            "cp_loss": 300,
        },
        fen_before="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
        uci="e5c4",
        created_at="2026-09-16T00:00:00+00:00",
    )
    assert live_response == before
    assert packet["candidate_count"] == 1
    assert "pwc_v2_shadow" not in live_response
    candidate = packet["candidates"][0]
    assert candidate["game_phase"] == "deep_endgame"
    assert candidate["evidence"]["source_version"] == UNIFIED_V1_ADAPTER_VERSION


def test_exact_curriculum_candidate_competes_with_unified_without_mutating_live():
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6", "Qh5"):
        board.push_san(san)
    live_response = {
        "shouldAutoCommit": False,
        "coachingDecision": {
            "source": "pwc_unified_v1",
            "layer": "critical_interrupt",
            "category": "piece_safety",
            "conceptKey": "loose_piece",
            "text": "Nf6 leaves the threat unanswered.",
            "instruction": "Check the opponent's immediate threat first.",
            "focusMatch": False,
            "proof": {
                "caption_verified": True,
                "rule_name": "verified-threat",
            },
        },
        "visual": {"arrows": [], "highlightSquares": []},
    }
    before = deepcopy(live_response)

    packet = build_shadow_packet_from_unified_response(
        turn_id="5:g8f6",
        live_response=live_response,
        engine_evidence={
            "eval_valid": True,
            "move_quality": "blunder",
            "cp_loss": 300,
            "best_move": "Qe7",
        },
        fen_before=board.fen(),
        uci="g8f6",
        coaching_context={
            "primary_focus": {"topic_key": "opening_knowledge"},
            "supporting_focuses": [],
        },
    )

    assert live_response == before
    assert packet["candidate_count"] == 2
    assert {candidate["source"] for candidate in packet["candidates"]} == {
        "pwc_unified_v1",
        "canonical_curriculum_trap",
    }
    curriculum = next(
        candidate
        for candidate in packet["candidates"]
        if candidate["source"] == "canonical_curriculum_trap"
    )
    assert curriculum["focus_relevance"] == "primary"


@pytest.mark.asyncio
async def test_bounded_adapter_timeout_keeps_unified_candidate(monkeypatch):
    from coach_play.v2 import candidate_adapters, shadow_conductor

    live_response = {
        "coachingDecision": {
            "source": "pwc_unified_v1",
            "layer": "advisory",
            "category": "piece_safety",
            "conceptKey": "loose_piece",
            "text": "Your knight on e5 has no defender.",
            "proof": {
                "caption_verified": True,
                "rule_name": "loose-piece",
            },
        },
        "visual": {},
    }

    def slow_curriculum(**_kwargs):
        time.sleep(0.05)
        return ()

    monkeypatch.setattr(
        candidate_adapters,
        "curriculum_candidates_from_turn",
        slow_curriculum,
    )
    monkeypatch.setattr(shadow_conductor, "CURRICULUM_SHADOW_BUDGET_MS", 5)

    packet = await build_bounded_shadow_packet_from_unified_response(
        turn_id="12:e5c4",
        live_response=live_response,
        engine_evidence={
            "eval_valid": True,
            "move_quality": "mistake",
            "cp_loss": 180,
        },
        fen_before="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1",
        uci="e5c4",
    )

    assert packet["candidate_count"] == 1
    assert packet["candidates"][0]["source"] == "pwc_unified_v1"
    assert packet["adapter_observations"][0]["status"] == "timed_out"
    assert packet["adapter_observations"][0]["candidate_count"] == 0
