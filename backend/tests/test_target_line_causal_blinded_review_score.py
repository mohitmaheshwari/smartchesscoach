import json

from scripts.score_target_line_causal_blinded_review import (
    DEFAULT_OUTPUT_PATH,
    score_review,
)
from services.caption_facts import TARGET_LINE_CAUSAL_QUALITY_ID
from services.detector_quality import QualitySurface, is_authorized


def _versioned_score():
    return json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))


def test_versioned_blinded_score_is_deterministic():
    assert score_review() == _versioned_score()


def test_frozen_review_scores_all_cases_once():
    score = _versioned_score()
    raw = score["raw_blinded_score"]

    assert score["sample"] == {
        "cases": 64,
        "detector_candidates": 34,
        "sampled_controls": 30,
        "reviewer_positive": 36,
        "reviewer_nonpositive": 28,
    }
    assert raw["true_positives"] == 32
    assert raw["false_positives"] == 2
    assert raw["false_negatives"] == 4
    assert raw["true_negatives"] == 26
    assert raw["semantic_precision_pct"] == 94.12
    assert raw["wilson_lower_bound_pct"] == 80.91
    assert raw["critical_false_claims"] == 0
    assert len(score["raw_disagreements"]) == 6


def test_review_cannot_promote_the_shadow_detector():
    score = _versioned_score()

    assert score["quality_id"] == TARGET_LINE_CAUSAL_QUALITY_ID
    assert score["raw_gate"]["caption_promotion_gate_passed"] is False
    assert score["raw_gate"]["status"] == "shadow"
    assert score["raw_gate"]["independent_review_complete"] is False
    assert not is_authorized(
        TARGET_LINE_CAUSAL_QUALITY_ID, QualitySurface.CAPTION
    )


def test_score_records_no_external_compute_or_production_access():
    score = _versioned_score()

    assert score["read_only"] is True
    assert score["stockfish_runs"] == 0
    assert score["llm_calls"] == 0
    assert score["database_reads"] == 0
    assert score["database_writes"] == 0
    assert len(score["sources"]["blinded_packet"]["sha256"]) == 64
    assert len(score["sources"]["frozen_review"]["sha256"]) == 64
    assert len(score["sources"]["frozen_answer_key"]["sha256"]) == 64
