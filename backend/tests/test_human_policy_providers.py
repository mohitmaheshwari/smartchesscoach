"""Provider adapters preserve evidence boundaries and reject invented context."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.human_chess_intelligence.policy_contract import (  # noqa: E402
    HumanPolicyRequest,
    PolicyContractError,
)
from research.human_chess_intelligence.providers import (  # noqa: E402
    history_reaches_fen,
    maia2_inference_each_unrounded,
    predict_maia2,
    predict_otter,
)


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
MODEL_HASH = "a" * 64


def request(**overrides):
    values = {
        "fen": START,
        "player_elo": 1200,
        "opponent_elo": 1250,
        "time_control": "600+0",
        "clock_fraction": 0.8,
    }
    values.update(overrides)
    return HumanPolicyRequest(**values)


class FakeOtter:
    def __init__(self):
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        moves = (
            [("e7e5", 0.6), ("g8f6", 0.2)]
            if kwargs["fen"].split()[1] == "b"
            else [("e2e4", 0.6), ("g1f3", 0.2)]
        )
        return {
            "moves": [
                {"move": move, "probability": probability}
                for move, probability in moves
            ],
            "win_probability": 0.1,
        }


def test_maia_labels_unsupported_context_without_claiming_to_use_it():
    req = request(history_moves=())

    def fake_inference(model, prepared, fen, elo_self, elo_oppo):
        return {"e2e4": 0.7, "d2d4": 0.3}, 0.55

    evidence = predict_maia2(
        req,
        model=object(),
        prepared=object(),
        model_version="0.11.0",
        model_sha256=MODEL_HASH,
        weight_family="rapid",
        inference_each_fn=fake_inference,
    )
    assert evidence.policy_configuration["clock_mode"] == "unsupported"
    assert evidence.moves[0].move_uci == "e2e4"
    assert "provider_does_not_consume" in evidence.warnings[0]


def test_maia_adapter_defaults_to_the_unrounded_metric_safe_path(monkeypatch):
    req = request()
    called = {}

    def fake_unrounded(model, prepared, fen, elo_self, elo_oppo):
        called["yes"] = True
        return {"e2e4": 0.70000001, "d2d4": 0.29999999}, 0.55

    monkeypatch.setattr(
        "research.human_chess_intelligence.providers.maia2_inference_each_unrounded",
        fake_unrounded,
    )
    evidence = predict_maia2(
        req,
        model=object(),
        prepared=object(),
        model_version="0.11.0",
        model_sha256=MODEL_HASH,
        weight_family="rapid",
    )
    assert called == {"yes": True}
    assert evidence.moves[0].probability == pytest.approx(0.70000001)


def test_observed_otter_rejects_missing_clock_and_non_reconstructing_history():
    model = FakeOtter()
    with pytest.raises(PolicyContractError, match="clock_fraction"):
        predict_otter(
            request(clock_fraction=None), model=model, model_version="0.2.0",
            model_sha256=MODEL_HASH, mode="observed",
        )
    with pytest.raises(PolicyContractError, match="does not reconstruct"):
        predict_otter(
            request(fen=AFTER_E4, history_moves=()), model=model, model_version="0.2.0",
            model_sha256=MODEL_HASH, mode="observed",
        )
    assert model.calls == []


def test_history_reconstruction_is_an_explicit_observed_context_gate():
    assert history_reaches_fen(request()) is True
    assert history_reaches_fen(request(fen=AFTER_E4, history_moves=())) is False
    assert history_reaches_fen(request(fen=AFTER_E4, history_moves=("e2e4",))) is True


def test_observed_otter_passes_validated_context_verbatim():
    model = FakeOtter()
    evidence = predict_otter(
        request(), model=model, model_version="0.2.0",
        model_sha256=MODEL_HASH, mode="observed",
    )
    assert model.calls[0]["clock_fraction"] == 0.8
    assert model.calls[0]["history_moves"] == []
    assert evidence.policy_configuration["clock_mode"] == "observed_validated"


def test_neutral_otter_ablation_is_explicitly_not_observed_evidence():
    model = FakeOtter()
    evidence = predict_otter(
        request(clock_fraction=None, time_control=None),
        model=model,
        model_version="0.2.0",
        model_sha256=MODEL_HASH,
        mode="neutral_ablation",
    )
    assert model.calls[0]["clock_fraction"] == 0.5
    assert model.calls[0]["time_control"] == "600+0"
    assert evidence.policy_configuration["clock_mode"] == "controlled_neutral_0.5"
    assert evidence.warnings == ("neutral_ablation_is_not_observed_player_evidence",)


@pytest.mark.parametrize(
    ("mode", "expected_history", "expected_clock", "history_label", "clock_label"),
    (
        ("history_only", ["e2e4"], 0.5, "observed_validated", "controlled_neutral_0.5"),
        ("clock_only", [], 0.8, "controlled_empty", "observed_validated"),
    ),
)
def test_single_factor_otter_ablations_change_only_the_named_context(
    mode, expected_history, expected_clock, history_label, clock_label
):
    model = FakeOtter()
    evidence = predict_otter(
        request(fen=AFTER_E4, history_moves=("e2e4",)),
        model=model,
        model_version="0.2.0",
        model_sha256=MODEL_HASH,
        mode=mode,
    )
    assert model.calls[0]["history_moves"] == expected_history
    assert model.calls[0]["clock_fraction"] == expected_clock
    assert evidence.policy_configuration["history_mode"] == history_label
    assert evidence.policy_configuration["clock_mode"] == clock_label
    assert evidence.warnings == (f"{mode}_is_a_controlled_ablation",)


def test_history_only_does_not_require_or_invent_observed_clock():
    model = FakeOtter()
    evidence = predict_otter(
        request(fen=AFTER_E4, history_moves=("e2e4",), clock_fraction=None),
        model=model,
        model_version="0.2.0",
        model_sha256=MODEL_HASH,
        mode="history_only",
    )
    assert model.calls[0]["history_moves"] == ["e2e4"]
    assert model.calls[0]["clock_fraction"] == 0.5
    assert evidence.policy_configuration["clock_mode"] == "controlled_neutral_0.5"
