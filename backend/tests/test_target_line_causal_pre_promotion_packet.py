import hashlib
import json
from pathlib import Path

from scripts.build_target_line_causal_pre_promotion_packet import (
    DEFAULT_ANSWER_KEY_OUTPUT_PATH,
    DEFAULT_INDEPENDENT_REVIEW_PATH,
    DEFAULT_OUTPUT_PATH,
    FRESH_OUTPUT_PATH,
    build_packet,
)
from services.caption_facts import TARGET_LINE_CAUSAL_QUALITY_ID
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)


def _versioned_packet():
    return json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))


def _fresh_packet():
    return json.loads(FRESH_OUTPUT_PATH.read_text(encoding="utf-8"))


def test_frozen_pre_promotion_packet_is_hash_bound_to_the_review():
    review = json.loads(
        DEFAULT_INDEPENDENT_REVIEW_PATH.read_text(encoding="utf-8")
    )

    assert review["frozen"] is True
    assert review["packet_sha256"] == hashlib.sha256(
        DEFAULT_OUTPUT_PATH.read_bytes()
    ).hexdigest()


def test_frozen_v3_builder_refuses_newer_detector_version():
    try:
        build_packet()
    except RuntimeError as exc:
        assert "v3 packet is frozen" in str(exc)
    else:
        raise AssertionError("evolved detector must not regenerate v3 packet")


def test_packet_is_blinded_and_contains_no_identity_or_machine_label():
    packet = _versioned_packet()
    encoded = json.dumps(packet).lower()

    assert packet["review_packet"]["blinded"] is True
    assert packet["schema_version"] == (
        "target_line_causal.pre_promotion_review.v3"
    )
    assert packet["review_packet"]["cases"] == 127
    assert len(packet["cases"]) == 127
    assert len({case["case_id"] for case in packet["cases"]}) == 127
    assert "@" not in encoded
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "cp_loss",
        "candidate_fired",
        "mechanism",
        "proof",
        "gold",
    ):
        assert all(forbidden not in case for case in packet["cases"])


def test_packet_records_the_real_fire_shortfall_without_promoting():
    packet = _versioned_packet()

    assert packet["quality_id"] == TARGET_LINE_CAUSAL_QUALITY_ID
    assert packet["population"]["candidate_fires"] == 97
    assert packet["population"]["candidate_fire_source_units"] == 92
    assert packet["population"]["architecture_overlap_excluded"] == 3
    assert packet["review_packet"]["candidate_fires_hidden"] == 97
    assert packet["review_packet"]["controls_hidden"] == 30
    assert len(packet["review_packet"]["population_control_strata"]) == 12
    assert packet["promotion_gate"]["fire_shortfall"] == 0
    assert "reviewed_fire_minimum_not_met" not in (
        packet["promotion_gate"]["blockers"]
    )
    assert packet["promotion_gate"]["caption_promotion_gate_passed"] is False
    assert packet["promotion_gate"]["independent_review_complete"] is False

    authorization = get_authorization(TARGET_LINE_CAUSAL_QUALITY_ID)
    assert authorization.grade == QualityGrade.SHADOW
    assert is_authorized(
        TARGET_LINE_CAUSAL_QUALITY_ID, QualitySurface.DIAGNOSTIC
    )
    assert not is_authorized(
        TARGET_LINE_CAUSAL_QUALITY_ID, QualitySurface.CAPTION
    )


def test_packet_has_no_runtime_or_external_compute_side_effects():
    packet = _versioned_packet()

    assert packet["read_only"] is True
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_reads"] == 0
    assert packet["database_writes"] == 0
    assert all(len(source["sha256"]) == 64 for source in packet["sources"])


def test_answer_key_is_generated_only_after_exact_frozen_review():
    packet = _versioned_packet()
    answer_key = json.loads(
        DEFAULT_ANSWER_KEY_OUTPUT_PATH.read_text(encoding="utf-8")
    )
    candidates = set(answer_key["candidate_case_ids"])
    controls = set(answer_key["control_case_ids"])

    assert answer_key["created_after_blinded_review_was_frozen"] is True
    assert len(candidates) == 97
    assert len(controls) == 30
    assert not candidates & controls
    assert candidates | controls == {
        case["case_id"] for case in packet["cases"]
    }
    assert len(answer_key["source_packet"]["sha256"]) == 64
    assert len(answer_key["source_review"]["sha256"]) == 64
    assert answer_key["source_packet"]["sha256"] == hashlib.sha256(
        DEFAULT_OUTPUT_PATH.read_bytes()
    ).hexdigest()
    assert answer_key["source_review"]["sha256"] == hashlib.sha256(
        DEFAULT_INDEPENDENT_REVIEW_PATH.read_bytes()
    ).hexdigest()


def test_fresh_v4_packet_matches_the_canonical_builder_exactly():
    packet = _fresh_packet()

    assert build_packet(generation="v4") == packet
    assert packet["schema_version"] == (
        "target_line_causal.pre_promotion_review.v4"
    )
    assert packet["proof_version"] == "target_line_causal_proof.v6"
    assert packet["population"]["cases_scanned"] == 1500
    assert packet["population"]["complete_branch_evidence"] == 1500
    assert packet["population"]["candidate_fires"] == 53
    assert packet["population"]["candidate_fire_source_units"] == 53
    assert packet["review_packet"]["candidate_fires_hidden"] == 53
    assert packet["review_packet"]["controls_hidden"] == 30
    assert packet["review_packet"]["cases"] == 83
    assert len(packet["review_packet"]["population_control_strata"]) == 12
    assert packet["promotion_gate"]["fire_shortfall"] == 0


def test_fresh_v4_packet_is_blinded_private_and_disjoint_from_v3():
    fresh = _fresh_packet()
    prior = _versioned_packet()
    fresh_encoded = json.dumps(fresh["cases"]).lower()

    assert len(fresh["cases"]) == len({
        case["case_id"] for case in fresh["cases"]
    })
    assert "@" not in fresh_encoded
    assert all(
        set(case) == {
            "case_id",
            "review_group",
            "position",
            "played_branch",
            "better_branch",
        }
        for case in fresh["cases"]
    )
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "cp_loss",
        "candidate_fired",
        "mechanism",
        "proof",
        "gold",
    ):
        assert forbidden not in fresh_encoded

    def signature(case):
        return (
            case["position"]["fen"],
            case["played_branch"]["move_san"],
            case["better_branch"]["move_san"],
        )

    assert not (
        {signature(case) for case in fresh["cases"]}
        & {signature(case) for case in prior["cases"]}
    )
