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
    assert len(packet["cases"]) == 201
    assert len({case["case_id"] for case in packet["cases"]}) == 201
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
        "multi_move_material_accounting": 138,
        "queen_safety_or_greedy_capture": 15,
        "unpunished_opponent_opportunity": 15,
    }
    assert set(answer_key["family_counts"]) == set(
        TEACHING_OPPORTUNITY_QUALITY_IDS
    )
    assert packet["promotion_gate"]["caption_promotion_gate_passed"] is False
    assert "three_families_have_fewer_than_50_available_claims" in (
        packet["promotion_gate"]["blockers"]
    )


def test_every_material_caption_describes_visible_delta_not_total_balance():
    source = _source()
    old_overclaims = (
        "material stays level",
        "come out ahead",
        "finish behind",
        "no better off",
        "stops that finish",
    )

    for candidate in source["candidates"]:
        fact = candidate["fact"]
        comparison = candidate["comparison"]
        rendered = json.dumps(comparison).lower()
        assert all(phrase not in rendered for phrase in old_overclaims)

        if fact["played_visible_material_gain_cp"] is None:
            continue
        claimed_sides = (
            ("played", "stronger")
            if fact["family"] == "multi_move_material_accounting"
            else ("played", "stronger")
            if (
                fact["family"] == "queen_safety_or_greedy_capture"
                and fact["consequence_piece"] != "queen"
            )
            else ()
        )
        for side in claimed_sides:
            score_key = (
                "played_visible_material_gain_cp"
                if side == "played"
                else "best_visible_material_gain_cp"
            )
            score = fact[score_key]
            summary = comparison[side]["summary"].lower()
            if score > 0:
                assert "wins" in summary
            elif score < 0:
                assert "loses" in summary or "costs" in summary
            else:
                assert "trades equal material" in summary


def test_causal_capture_families_exclude_later_voluntary_walk_ins():
    for candidate in _source()["candidates"]:
        fact = candidate["fact"]
        family = fact["family"]
        if family == "queen_safety_or_greedy_capture":
            if fact["consequence_piece"] == "queen":
                assert fact["consequence_ply"] == 2
            else:
                assert fact["consequence_ply"] == 1
        elif (
            family == "unpunished_opponent_opportunity"
            and fact["consequence_piece"] is not None
        ):
            assert fact["consequence_ply"] in {1, 3}


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
