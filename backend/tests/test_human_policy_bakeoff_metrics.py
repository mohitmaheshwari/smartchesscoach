"""Metric and baseline behavior is deterministic and legally normalized."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.human_chess_intelligence.bakeoff_metrics import (  # noqa: E402
    LegalMoveFrequencyBaseline,
    PolicyMetricsAccumulator,
    SegmentedPolicyMetrics,
    normalize_time_control,
    rating_band,
)
from research.human_chess_intelligence.policy_contract import MoveProbability  # noqa: E402


MOVES = (
    MoveProbability("e2e4", 0.6),
    MoveProbability("d2d4", 0.3),
    MoveProbability("g1f3", 0.1),
)


def test_policy_metrics_compute_topk_nll_brier_rank_and_coverage():
    metrics = PolicyMetricsAccumulator()
    metrics.update(MOVES, "d2d4", latency_ms=20)
    result = metrics.finalize()
    assert result["top1_accuracy"] == 0
    assert result["top3_accuracy"] == 1
    assert result["negative_log_likelihood"] == pytest.approx(-__import__("math").log(0.3))
    assert result["multiclass_brier"] == pytest.approx(0.6 ** 2 + (0.3 - 1) ** 2 + 0.1 ** 2)
    assert result["median_actual_move_rank"] == 2
    assert result["coverage"] == 1


def test_missing_actual_move_fails_coverage_without_crashing_metrics():
    metrics = PolicyMetricsAccumulator()
    metrics.update(MOVES, "c2c4")
    result = metrics.finalize()
    assert result["coverage"] == 0
    assert result["missing_actual_probability"] == 1
    assert result["median_actual_move_rank"] is None


def test_segmented_metrics_use_product_rating_and_error_bands():
    metrics = SegmentedPolicyMetrics()
    metrics.update(
        MOVES,
        "e2e4",
        latency_ms=10,
        player_elo=1200,
        time_control="300+5",
        phase="opening",
        color="white",
        cp_loss=175,
        extra_segments={"clock_quartile": "q1_lowest_time_remaining"},
    )
    result = metrics.finalize()["segments"]
    assert result["rating_band"]["1000-1399"]["count"] == 1
    assert result["time_control"]["blitz"]["count"] == 1
    assert result["error_band"]["cp_loss_150_199"]["count"] == 1
    assert result["clock_quartile"]["q1_lowest_time_remaining"]["count"] == 1


def test_legal_frequency_baseline_renormalizes_over_only_current_legal_moves():
    baseline = LegalMoveFrequencyBaseline(alpha=1.0)
    for _ in range(3):
        baseline.observe(player_elo=1200, phase="opening", eco="C60", move_uci="e2e4")
    baseline.observe(player_elo=1200, phase="opening", eco="C60", move_uci="d2d4")
    predictions = baseline.predict(
        ["e2e4", "d2d4", "g1f3"], player_elo=1200, phase="opening", eco="C60"
    )
    assert [move.move_uci for move in predictions] == ["e2e4", "d2d4", "g1f3"]
    assert sum(move.probability for move in predictions) == pytest.approx(1.0)
    assert predictions[0].probability == pytest.approx(4 / 7)


def test_rating_and_time_control_segments_have_fixed_boundaries():
    assert [rating_band(value) for value in (600, 999, 1000, 1399, 1400, 1500)] == [
        "600-999", "600-999", "1000-1399", "1000-1399", "1400-1500", "1400-1500"
    ]
    assert normalize_time_control("60+1") == "bullet"
    assert normalize_time_control("300+5") == "blitz"
    assert normalize_time_control("600+0") == "rapid"
