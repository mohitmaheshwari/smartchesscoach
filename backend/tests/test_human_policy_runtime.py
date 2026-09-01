from __future__ import annotations

import pytest

from services.human_behavior_engine import MoveContext, MoveDistribution
from services.human_policy_runtime import (
    MAIA2_PINNED_PACKAGE_VERSION,
    OTTER_PINNED_PACKAGE_VERSION,
    HumanPolicyError,
    HumanPolicyEvidence,
    derive_human_policy_evidence,
    human_policy_evidence_matches_context,
    history_reaches_fen,
)


FEN_AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
HISTORY = ("e2e4", "e7e5")
ENABLED = {"HUMAN_POLICY_EVIDENCE_ENABLED": "true"}


class FakeProvider:
    def __init__(self, provider: str, probabilities, *, available=True):
        self.provider = provider
        self.probabilities = probabilities
        self._available = available
        self.seen_contexts = []

    def available(self):
        return self._available

    def predict(self, ctx, top_k=20):
        self.seen_contexts.append(ctx)
        version = (
            OTTER_PINNED_PACKAGE_VERSION
            if self.provider == "otter"
            else MAIA2_PINNED_PACKAGE_VERSION
        )
        return MoveDistribution(
            self.provider,
            version,
            self.probabilities,
        )


def context(**overrides):
    value = dict(
        fen=FEN_AFTER_E4_E5,
        player_elo=1200,
        opponent_elo=1250,
        time_control="600+0",
        history_uci=HISTORY,
        move_number=2,
    )
    value.update(overrides)
    return MoveContext(**value)


def test_history_must_legally_replay_to_the_exact_position():
    assert history_reaches_fen(HISTORY, FEN_AFTER_E4_E5) is True
    assert history_reaches_fen(("e2e4",), FEN_AFTER_E4_E5) is False
    assert history_reaches_fen(("e2e5",), FEN_AFTER_E4_E5) is False


def test_verified_history_selects_otter_with_locked_neutral_clock_only():
    otter = FakeProvider("otter", {"g1f3": 0.55, "f1c4": 0.25})
    maia = FakeProvider("maia2", {"g1f3": 0.4})
    evidence, reason = derive_human_policy_evidence(
        context(clock_seconds=8, clock_fraction=0.01),
        otter=otter,
        maia=maia,
        env=ENABLED,
    )
    assert reason == "otter_history"
    assert evidence is not None
    assert evidence.provider == "otter"
    assert evidence.history_mode == "verified"
    assert evidence.provider_role == "preferred_history"
    assert evidence.rank_of("g1f3") == 1
    assert "clock_ignored_by_locked_policy" in evidence.warnings
    assert otter.seen_contexts[0].clock_seconds is None
    assert otter.seen_contexts[0].clock_fraction == 0.5
    assert evidence.contract_dict()["clock_mode"] == "controlled_neutral_0.5"
    assert evidence.contract_dict()["clock_used_for_causal_diagnosis"] is False
    assert evidence.contract_dict()["chess_authority"] is False


def test_missing_or_mismatched_history_uses_maia_fallback():
    evidence, reason = derive_human_policy_evidence(
        context(history_uci=("e2e4",)),
        otter=FakeProvider("otter", {"g1f3": 0.9}),
        maia=FakeProvider("maia2", {"g1f3": 0.4, "b1c3": 0.3}),
        env=ENABLED,
    )
    assert reason == "maia_fallback"
    assert evidence is not None
    assert evidence.provider == "maia2"
    assert evidence.history_mode == "none"
    assert "history_does_not_reach_position" in evidence.warnings


def test_unavailable_otter_falls_back_without_breaking_analysis():
    evidence, reason = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {}, available=False),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert reason == "maia_fallback"
    assert evidence is not None
    assert "otter_provider_unavailable" in evidence.warnings


def test_illegal_otter_output_is_rejected_before_maia_fallback():
    evidence, reason = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"a1a8": 0.9}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert reason == "maia_fallback"
    assert evidence is not None
    assert "otter_output_rejected" in evidence.warnings


def test_if_every_provider_is_bad_the_runtime_abstains():
    evidence, reason = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"a1a8": 0.9}),
        maia=FakeProvider("maia2", {"a1a8": 0.9}),
        env=ENABLED,
    )
    assert evidence is None
    assert reason == "maia_output_rejected"


def test_impossible_probability_mass_is_rejected_before_it_can_rank_moves():
    evidence, reason = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"g1f3": 0.8, "f1c4": 0.8}),
        maia=FakeProvider("maia2", {"g1f3": 0.9, "b1c3": 0.9}),
        env=ENABLED,
    )
    assert evidence is None
    assert reason == "maia_output_rejected"


def test_human_policy_can_rank_only_the_supplied_verified_candidate_set():
    evidence, _ = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"g1f3": 0.55, "f1c4": 0.25, "b1c3": 0.1}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert evidence.rank_verified_candidates(("b1c3", "f1c4")) == ("f1c4", "b1c3")
    assert "g1f3" not in evidence.rank_verified_candidates(("b1c3", "f1c4"))


def test_contract_round_trip_and_stale_fingerprint_rejection():
    evidence, _ = derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"g1f3": 0.55}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    packet = evidence.contract_dict()
    assert HumanPolicyEvidence.from_contract(packet) == evidence
    packet["input_fingerprint"] = "0" * 64
    with pytest.raises(HumanPolicyError, match="fingerprint mismatch"):
        HumanPolicyEvidence.from_contract(packet)


def test_stored_evidence_is_bound_to_exact_history_not_only_ply_count():
    ctx = context()
    evidence, _ = derive_human_policy_evidence(
        ctx,
        otter=FakeProvider("otter", {"g1f3": 0.55}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert human_policy_evidence_matches_context(evidence, ctx) is True
    wrong_same_length = context(history_uci=("d2d4", "d7d5"))
    assert human_policy_evidence_matches_context(evidence, wrong_same_length) is False


def test_flag_off_is_a_strict_noop():
    assert derive_human_policy_evidence(
        context(),
        otter=FakeProvider("otter", {"g1f3": 0.5}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env={},
    ) == (None, "disabled")


@pytest.mark.parametrize("player_elo,opponent_elo", [(599, 1200), (1501, 1200)])
def test_runtime_abstains_outside_the_measured_rating_population(player_elo, opponent_elo):
    assert derive_human_policy_evidence(
        context(player_elo=player_elo, opponent_elo=opponent_elo),
        otter=FakeProvider("otter", {"g1f3": 0.5}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    ) == (None, "outside_validated_rating_range")


def test_observed_opponent_rating_may_be_outside_target_player_population():
    evidence, reason = derive_human_policy_evidence(
        context(opponent_elo=1800),
        otter=FakeProvider("otter", {"g1f3": 0.5}),
        maia=FakeProvider("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert reason == "otter_history"
    assert evidence.opponent_elo == 1800


def test_provider_version_drift_is_rejected_even_when_moves_are_legal():
    class Drifted(FakeProvider):
        def predict(self, ctx, top_k=20):
            return MoveDistribution(self.provider, "99.0.0", self.probabilities)

    evidence, reason = derive_human_policy_evidence(
        context(),
        otter=Drifted("otter", {"g1f3": 0.5}),
        maia=Drifted("maia2", {"g1f3": 0.4}),
        env=ENABLED,
    )
    assert evidence is None
    assert reason == "maia_output_rejected"
