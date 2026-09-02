from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.build_aligned_payoff_caption_promotion_packet import (
    NEGATIVE_STRATA,
    QUALITY_ID,
    _candidate,
    independent_gold,
)
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)
from services.verified_puzzle_admission import (
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import build_position_verdict
from services.verified_puzzle_feedback import build_verified_puzzle_feedback
from services.verified_puzzle_runtime import grade_resolved_puzzle


PACKET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "detector_gold"
    / "aligned_payoff_caption_promotion_v1.json"
)
PACKET_SHA256 = (
    "5fc64110390f739cfea3cdb12929d8994590bfd399dc4b016c3b3b8c8a56ec1e"
)


def _packet():
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def _canonical_sha256(value) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _row(case):
    return {
        "fen": case["fen_before"],
        "played_move": case["played_move_uci"],
        "best_move_uci": case["best_move_uci"],
        "pv_after_best": case["pv_after_best"],
        "cp_loss": case["cp_loss"],
    }


def test_packet_is_pinned_private_and_meets_each_subtype_bar():
    packet = _packet()

    assert _canonical_sha256(packet) == PACKET_SHA256
    assert packet["schema_version"] == "aligned_payoff.caption_promotion.v1"
    assert packet["quality_id"] == QUALITY_ID
    assert packet["selection"]["selection_fingerprint_sha256"] == (
        "de3ccb6ff3338b63e37c0945875dabb15151e4b8a85762283716d4dc53fc7c37"
    )
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_writes"] == 0
    assert packet["summary"] == {
        "caption_promotion_gate_passed": True,
        "combined_wilson_lower_pct": 92.87,
        "critical_adversarial_errors": 0,
        "pin_true_positives": 25,
        "pin_wilson_lower_pct": 86.68,
        "reviewed_fires": 50,
        "semantic_precision_pct": 100,
        "skewer_true_positives": 25,
        "skewer_wilson_lower_pct": 86.68,
        "true_negative_cases": 50,
        "true_negatives": 50,
        "true_positives": 50,
    }
    assert packet["population"] == {
        "by_attacker_piece": {"bishop": 178, "queen": 107, "rook": 151},
        "by_creation_mode": {"direct": 374, "discovered": 62},
        "by_kind": {"pin": 285, "skewer": 151},
        "by_pool": {
            "community_puzzles": 104,
            "community_training_positions": 332,
        },
        "candidate_replay_failures": 0,
        "distinct_source_keys": 363,
        "documents_scanned": 52085,
        "full_pool_outcomes": {
            "attacker_left_before_payoff": 1963,
            "incomplete_line": 609,
            "insufficient_consequence": 44,
            "insufficient_net_gain": 4666,
            "no_created_alignment": 41305,
            "pin_exact": 422,
            "pin_front_escaped": 350,
            "pin_target_not_captured": 1423,
            "same_move": 296,
            "skewer_exact": 215,
            "skewer_front_not_cleared": 280,
            "skewer_rear_escaped": 69,
            "skewer_rear_not_captured": 443,
        },
        "independent_outcomes": {"pin_exact": 285, "skewer_exact": 151},
        "stored_candidates": 436,
        "stored_fact_mismatches": 0,
    }
    raw = PACKET_PATH.read_text(encoding="utf-8").lower()
    assert "@" not in raw
    assert "mongo_url" not in raw
    assert "password" not in raw
    assert "bhutramohit" not in raw
    assert "user_id" not in raw
    assert "game_id" not in raw


def test_every_packet_case_replays_against_independent_gold_and_candidate():
    packet = _packet()
    fires = packet["fires"]
    negatives = packet["negatives"]

    assert len(fires) == 50
    assert len({case["source_key"] for case in fires}) == 50
    assert Counter(case["gold"]["kind"] for case in fires) == {
        "pin": 25,
        "skewer": 25,
    }
    for kind in ("pin", "skewer"):
        subset = [case for case in fires if case["gold"]["kind"] == kind]
        assert {case["pool"] for case in subset} == {
            "community_puzzles",
            "community_training_positions",
        }
        assert {case["gold"]["creation_mode"] for case in subset} == {
            "direct",
            "discovered",
        }
        assert {case["gold"]["attacker_piece"] for case in subset} == {
            "bishop",
            "rook",
            "queen",
        }

    for case in fires:
        gold = independent_gold(_row(case))
        assert gold["verified"] is True, case["case_id"]
        assert gold["reason"] == f"{case['gold']['kind']}_exact"
        for field, expected in case["gold"].items():
            actual = gold[field]
            if field == "replayed_uci":
                actual = list(actual)
            assert actual == expected, (case["case_id"], field)
        candidate = _candidate(_row(case))
        assert candidate == {
            "fired": True,
            "kind": case["gold"]["kind"],
        }
        assert case["candidate_fired"] is True
        assert case["candidate_kind"] == case["gold"]["kind"]

    counts = Counter()
    assert len(negatives) == 50
    assert len({case["source_key"] for case in negatives}) == 50
    for case in negatives:
        gold = independent_gold(_row(case))
        assert gold["verified"] is False, case["case_id"]
        assert gold["reason"] == case["gold"]["reason"]
        assert gold["reason"] in NEGATIVE_STRATA
        counts[gold["reason"]] += 1
        assert _candidate(_row(case)) == {"fired": False, "kind": None}
        assert case["candidate_fired"] is False
    assert counts == Counter({name: 5 for name in NEGATIVE_STRATA})


def test_authorization_is_caption_only_and_has_no_plan_or_mastery_leak():
    authorization = get_authorization(QUALITY_ID)

    assert authorization.grade == QualityGrade.CAPTION
    assert authorization.evidence_ref.endswith(
        "aligned_payoff_caption_promotion_v1.json"
    )
    assert is_authorized(QUALITY_ID, QualitySurface.CAPTION)
    assert not is_authorized(QUALITY_ID, QualitySurface.PROMPT)
    assert not is_authorized(QUALITY_ID, QualitySurface.PLAN)
    assert not is_authorized(QUALITY_ID, QualitySurface.MASTERY)


def test_caption_fact_drives_feedback_but_not_prompt_or_recovery_identity():
    for case in _packet()["fires"]:
        gold = case["gold"]
        verdict = build_position_verdict(
            source_kind="promotion_packet",
            source_ref=case["case_id"],
            move_evaluation={
                "fen_before": case["fen_before"],
                "move": case["played_move_uci"],
                "best_move_uci": case["best_move_uci"],
                "cp_loss": case["cp_loss"],
                "pv_after_best": case["pv_after_best"],
            },
            broad_category="missed_tactic",
        )
        puzzle = {
            "fen": case["fen_before"],
            "best_move_uci": case["best_move_uci"],
            "verified_admission": verdict.to_document(),
        }

        assert verdict.status == AdmissionStatus.BROAD
        assert verdict.concept_id is None
        assert verdict.caption_concept_id == f"tactic.{gold['kind']}"
        assert verdict.reason_codes == (
            "caption_proof_verified",
            "broad_category_verified",
        )
        assert verdict.verifier_facts[0]["creation_mode"] == gold["creation_mode"]
        assert verdict.verifier_facts[0]["attacker_piece"] == gold["attacker_piece"]
        assert verdict.verifier_facts[0]["front_piece"] == gold["front_piece"]
        assert verdict.verifier_facts[0]["rear_piece"] == gold["rear_piece"]
        assert stored_verdict_is_structurally_current(puzzle)

        feedback = build_verified_puzzle_feedback(
            puzzle,
            case["played_move_uci"],
            correct=False,
            primary_uci=case["best_move_uci"],
        )
        assert gold["attacker_piece"] in feedback["why"]
        assert gold["attacker_square"] in feedback["why"]
        assert gold["front_piece"] in feedback["why"]
        assert gold["front_square"] in feedback["why"]
        assert gold["rear_piece"] in feedback["why"]
        assert gold["rear_square"] in feedback["why"]
        if gold["creation_mode"] == "discovered":
            assert "clears a line for your" in feedback["why"]
        else:
            assert "puts your" in feedback["why"]
        if gold["kind"] == "pin":
            assert "shields something more valuable" in feedback["remember"]
        else:
            assert "stands in front of another piece" in feedback["remember"]

        grade = grade_resolved_puzzle(puzzle, case["best_move_uci"])
        assert grade["correct"] is True
        assert grade["recovery_weakness"] == "missed_tactic"
        assert grade["pattern_type"] == "missed_tactic"
        assert verdict.caption_concept_id not in {
            grade["recovery_weakness"],
            grade["pattern_type"],
        }


def test_packet_generator_has_no_engine_llm_network_or_write_path():
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "build_aligned_payoff_caption_promotion_packet.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "StockfishEngine",
        "stockfish_service",
        "call_llm",
        "httpx",
        "requests.",
        ".insert_one(",
        ".update_one(",
        ".delete_one(",
    )
    assert not any(token in source for token in forbidden)
