import json

from scripts.build_deterministic_teaching_opportunity_review_packet import (
    DEFAULT_ANSWER_KEY,
    DEFAULT_PACKET,
    DEFAULT_SOURCE,
    build_packets,
    _sha256_path,
)
from services.caption_facts import TEACHING_OPPORTUNITY_QUALITY_IDS
from scripts.score_deterministic_teaching_opportunity_review import (
    REVIEW_SCHEMA_VERSION,
    score_review,
)


def _source():
    return json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))


def test_versioned_blinded_packet_is_deterministic():
    expected_packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    expected_key = json.loads(DEFAULT_ANSWER_KEY.read_text(encoding="utf-8"))
    packet, answer_key = build_packets(
        _source(), source_sha256=_sha256_path(DEFAULT_SOURCE)
    )

    assert packet == expected_packet
    assert answer_key == expected_key


def test_public_cases_are_identity_free_and_detector_blind():
    packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    encoded = json.dumps(packet["cases"]).lower()

    assert packet["blinded"] is True
    assert packet["promotion_eligible"] is False
    assert len(packet["cases"]) == 250
    assert len({case["case_id"] for case in packet["cases"]}) == 250
    assert "@" not in encoded
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "anonymous_game_key",
        "anonymous_player_key",
        "quality_id",
        "family",
        "proof_version",
        "cp_loss",
        "fingerprint",
    ):
        assert forbidden not in encoded


def test_answer_key_records_real_family_shortfalls_without_authorizing_them():
    packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    answer_key = json.loads(DEFAULT_ANSWER_KEY.read_text(encoding="utf-8"))

    assert answer_key["family_counts"] == {
        "forced_mate_story": 33,
        "multi_move_material_accounting": 165,
        "queen_safety_or_greedy_capture": 20,
        "unpunished_opponent_opportunity": 32,
    }
    assert set(answer_key["family_counts"]) == set(
        TEACHING_OPPORTUNITY_QUALITY_IDS
    )
    assert packet["promotion_gate"]["caption_promotion_gate_passed"] is False
    assert "three_families_have_fewer_than_50_available_claims" in (
        packet["promotion_gate"]["blockers"]
    )


def _complete_true_review(packet):
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "source_review_packet_sha256": _sha256_path(DEFAULT_PACKET),
        "independence_attestation": {
            "independent_from_implementation": True,
            "answer_key_unseen": True,
            "detector_code_unseen": True,
        },
        "case_reviews": [
            {
                "case_id": case["case_id"],
                "verdict": "true",
                "critical_false_claim": False,
                "review_note": "Both lines replay and the visible claim follows.",
            }
            for case in packet["cases"]
        ],
    }


def test_scorer_grades_each_family_separately_and_never_promotes_development():
    packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    answer_key = json.loads(DEFAULT_ANSWER_KEY.read_text(encoding="utf-8"))
    score = score_review(
        packet,
        answer_key,
        _complete_true_review(packet),
        packet_sha256=_sha256_path(DEFAULT_PACKET),
    )

    assert score["family_scores"]["multi_move_material_accounting"][
        "numeric_quality_gate_passed"
    ] is True
    for family in (
        "forced_mate_story",
        "queen_safety_or_greedy_capture",
        "unpunished_opponent_opportunity",
    ):
        assert score["family_scores"][family]["numeric_quality_gate_passed"] is False
    assert score["caption_authorizations_changed"] == 0
    assert score["overall_promotion_gate_passed"] is False


def test_scorer_rejects_an_incomplete_or_duplicate_review():
    import pytest

    packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
    answer_key = json.loads(DEFAULT_ANSWER_KEY.read_text(encoding="utf-8"))
    review = _complete_true_review(packet)
    review["case_reviews"][-1] = dict(review["case_reviews"][0])

    with pytest.raises(ValueError, match="review response row is invalid"):
        score_review(
            packet,
            answer_key,
            review,
            packet_sha256=_sha256_path(DEFAULT_PACKET),
        )
