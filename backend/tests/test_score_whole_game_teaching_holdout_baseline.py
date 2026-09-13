import hashlib
import json
from pathlib import Path

from scripts.score_whole_game_teaching_holdout_baseline import build_report


BACKEND = Path(__file__).resolve().parents[1]
BASELINE = (
    BACKEND
    / "data/corpus_snapshots/whole_game_teaching_review_holdout_baseline_comparison_v1_2026-09-13.json"
)
ADJUDICATION = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_baseline_adjudication_v1.json"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_caption_export_is_identity_free_bound_and_read_only():
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == (
        "f4a08f9131a55b014e07a6bc24ed36f9d7ba7c4a4ab5ec4e2eec4731be0f4ca5"
    )
    packet = _load(BASELINE)
    assert packet["membership_sha256"] == (
        "87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b"
    )
    assert packet["gold_frozen_before_reveal"] is True
    assert len(packet["rows"]) == packet["rows_expected"] == 90
    assert packet["database_writes"] == 0
    assert packet["stockfish_runs"] == 0
    assert packet["model_calls"] == 0
    serialized = json.dumps(packet).lower()
    for forbidden in ("user_id", "game_id", "email", "http://", "https://"):
        assert forbidden not in serialized


def test_frozen_semantic_comparison_is_complete_reproducible_and_fails_gate():
    assert hashlib.sha256(ADJUDICATION.read_bytes()).hexdigest() == (
        "92c3566af399633de96f8fcf2cbe8a7de616079f8346acd2d7d30c7dd4bcd8ad"
    )
    stored = _load(ADJUDICATION)
    rebuilt = build_report()

    assert stored == rebuilt
    assert len(stored["rows"]) == 90
    identities = {
        (row["anonymous_game_key"], row["ply"]) for row in stored["rows"]
    }
    assert len(identities) == 90
    assert stored["summary"] == {
        "holdout_games": 42,
        "players": 42,
        "proved_lessons": 90,
        "zero_denominator_games": 4,
        "legacy_exact_match": 55,
        "legacy_causal_equivalent": 15,
        "legacy_covered": 70,
        "legacy_coverage_pct": 77.78,
        "candidate_fact_upper_bound_covered": 72,
        "candidate_fact_upper_bound_coverage_pct": 80.0,
        "upper_bound_micro_improvement_percentage_points": 2.22,
        "paired_games": 38,
        "legacy_macro_coverage_pct": 78.509,
        "candidate_fact_upper_bound_macro_coverage_pct": 82.456,
        "upper_bound_paired_macro_improvement_percentage_points": 3.947,
        "paired_games_upper_bound_better": 8,
        "paired_games_tied": 24,
        "paired_games_upper_bound_worse": 6,
        "bootstrap_seed": 20260913,
        "bootstrap_draws": 200000,
        "player_clustered_ci95_low_percentage_points": -6.14,
        "player_clustered_ci95_high_percentage_points": 14.474,
        "release_gate_requires_ci_low_above_zero": True,
        "release_gate_passed": False,
        "failure_reason": (
            "Even the shared-fact upper bound has a confidence-interval lower "
            "bound at or below zero; the authorized visible subset cannot "
            "establish the required improvement."
        ),
    }
    assert stored["status"] == "frozen_failed_upper_bound_release_gate"
    assert stored["execution_contract"]["holdout_may_tune_product_logic"] is False
