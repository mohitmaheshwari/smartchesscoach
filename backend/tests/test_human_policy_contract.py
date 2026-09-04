"""The offline human-policy contract cannot acquire chess authority."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.human_chess_intelligence.policy_contract import (  # noqa: E402
    HumanPolicyEvidence,
    HumanPolicyRequest,
    MoveProbability,
    PolicyContractError,
    validate_evidence,
)

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MODEL_HASH = "a" * 64


def request(**overrides):
    values = {
        "fen": START,
        "player_elo": 1200,
        "opponent_elo": 1250,
        "history_moves": (),
        "time_control": "600+0",
        "clock_fraction": 0.8,
    }
    values.update(overrides)
    return HumanPolicyRequest(**values)


def evidence(req, **overrides):
    values = {
        "provider": "test-model",
        "model_version": "1.0",
        "model_sha256": MODEL_HASH,
        "input_fingerprint": req.input_fingerprint,
        "moves": (
            MoveProbability("e2e4", 0.4),
            MoveProbability("g1f3", 0.2),
        ),
        "latency_ms": 12.5,
        "policy_configuration": {
            "clock_mode": "observed",
            "history_mode": "observed",
        },
    }
    values.update(overrides)
    return HumanPolicyEvidence(**values)


def test_fingerprint_uses_every_model_input_but_not_audit_ids():
    first = request(game_id="g1", ply_index=2)
    same_inputs = request(game_id="g2", ply_index=99)
    different_clock = request(clock_fraction=0.7)
    assert first.input_fingerprint == same_inputs.input_fingerprint
    assert first.input_fingerprint != different_clock.input_fingerprint


def test_valid_top_k_evidence_records_partial_probability_mass():
    req = request()
    checked = validate_evidence(req, evidence(req))
    assert checked.to_dict()["probability_mass_returned"] == pytest.approx(0.6)


def test_illegal_move_is_rejected_even_with_high_probability():
    req = request()
    candidate = evidence(req, moves=(MoveProbability("e2e5", 0.99),))
    with pytest.raises(PolicyContractError, match="illegal move"):
        validate_evidence(req, candidate)


def test_stale_input_fingerprint_is_rejected():
    req = request()
    candidate = evidence(req, input_fingerprint="b" * 64)
    with pytest.raises(PolicyContractError, match="different model inputs"):
        validate_evidence(req, candidate)


def test_missing_or_unpinned_provenance_is_rejected():
    req = request()
    with pytest.raises(PolicyContractError, match="model_version"):
        validate_evidence(req, evidence(req, model_version=""))
    with pytest.raises(PolicyContractError, match="model_sha256"):
        validate_evidence(req, evidence(req, model_sha256="latest"))
    with pytest.raises(PolicyContractError, match="clock_mode and history_mode"):
        validate_evidence(req, evidence(req, policy_configuration={}))


def test_duplicates_unsorted_probabilities_and_excess_mass_are_rejected():
    req = request()
    duplicate = evidence(req, moves=(
        MoveProbability("e2e4", 0.4), MoveProbability("e2e4", 0.2)
    ))
    with pytest.raises(PolicyContractError, match="duplicate"):
        validate_evidence(req, duplicate)

    unsorted = evidence(req, moves=(
        MoveProbability("e2e4", 0.2), MoveProbability("g1f3", 0.4)
    ))
    with pytest.raises(PolicyContractError, match="descending"):
        validate_evidence(req, unsorted)

    excess = evidence(req, moves=(
        MoveProbability("e2e4", 0.7), MoveProbability("g1f3", 0.4)
    ))
    with pytest.raises(PolicyContractError, match="exceeds one"):
        validate_evidence(req, excess)


def test_clock_and_history_are_validated_without_inventing_missing_values():
    no_clock = request(clock_fraction=None)
    assert no_clock.model_inputs()["clock_fraction"] is None
    assert request(history_moves=("e2e4", "e7e5")).history_moves == ("e2e4", "e7e5")
    with pytest.raises(PolicyContractError, match="clock_fraction"):
        request(clock_fraction=1.2)
    with pytest.raises(PolicyContractError, match="history UCI"):
        request(history_moves=("e4",))


def test_contract_contains_no_correctness_or_weakness_field():
    req = request()
    payload = evidence(req).to_dict()
    forbidden = {"correct", "best_move", "weakness", "mastery", "concept", "cp_loss"}
    assert forbidden.isdisjoint(payload)
