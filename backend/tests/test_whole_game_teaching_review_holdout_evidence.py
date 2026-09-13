import hashlib
import json
from pathlib import Path

from scripts.export_whole_game_review_evidence import assert_private
from scripts.measure_whole_game_teaching_holdout_coverage import build_report


BACKEND = Path(__file__).resolve().parents[1]
PACKET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_packet_v1.json"
)
WORKSHEET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_worksheet_v1.json"
)
ADJUDICATION = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_adjudication_v1.json"
)
COVERAGE = (
    BACKEND
    / "data/corpus_snapshots/whole_game_teaching_review_holdout_fact_coverage_v1_2026-09-13.json"
)
MARKER = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_implementation_freeze_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_holdout_chain_is_bound_private_complete_and_zero_critical():
    assert _sha256(PACKET) == (
        "ee694af72dc95a7c0ea6807023c0fc1e98e37cfe8726eb452d941bddef0695f9"
    )
    assert _sha256(WORKSHEET) == (
        "adefb7104e7c48639f1f7c50064a3a3d14c71c4c2e5c11af6f09dc7927ca6a17"
    )
    assert _sha256(COVERAGE) == (
        "df5b564ee852058176924d810360c98b3dc335fbe593bf85710da09c9af11c26"
    )

    packet = _load(PACKET)
    assert_private(packet, ())
    assert packet["database_writes"] == 0
    assert packet["stockfish_runs"] == 0
    assert packet["model_calls"] == 0
    assert len(packet["games"]) == 42

    marker = _load(MARKER)
    adjudication = _load(ADJUDICATION)
    assert marker["source_commit"] == (
        "76a411306b0066b4e585f6f23f2d0df8a7306e7e"
    )
    assert adjudication["source"]["frozen_implementation_source_commit"] == (
        marker["source_commit"]
    )
    assert adjudication["review_contract"]["games_reviewed"] == 42
    assert adjudication["review_contract"]["proposed_moments_reviewed"] == 90
    assert adjudication["accepted_gold"]["critical_false_claims"] == 0
    assert adjudication["decision"]["holdout_may_tune_product_logic"] is False


def test_frozen_holdout_coverage_matches_current_pure_facts_exactly():
    stored = _load(COVERAGE)
    rebuilt = build_report(PACKET, WORKSHEET)

    assert stored == rebuilt
    assert stored["summary"] == {
        "gold_moments": 90,
        "exact_fact": 72,
        "different_fact": 9,
        "no_typed_fact": 9,
        "exact_coverage_pct": 80.0,
    }
    assert stored["by_gold_family"]["allowed_forced_mate"]["exact_fact"] == 8
    assert stored["by_gold_family"]["missed_forced_mate"]["exact_fact"] == 5
