from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_free_piece_exact_caption_promotion_packet import (
    NEGATIVE_STRATA,
    _candidate_fires,
    independent_gold,
)
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)
from services.free_piece_puzzle_proof import FREE_PIECE_QUALITY_ID
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
    / "free_piece_exact_caption_promotion_v1.json"
)
PACKET_SHA256 = (
    "32d4bde64a14f01c96a0a4ece896e88f5c0e3a7a505be7bed948904f5f7a1c8e"
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
        "cp_loss": case["cp_loss"],
    }


def test_packet_is_pinned_private_and_meets_the_locked_caption_bar():
    packet = _packet()

    assert _canonical_sha256(packet) == PACKET_SHA256
    assert packet["schema_version"] == "free_piece_exact.caption_promotion.v1"
    assert packet["quality_id"] == FREE_PIECE_QUALITY_ID
    assert packet["selection"]["selection_fingerprint_sha256"] == (
        "2c758e25f505847438fd2819349f4410a077f9d802753551facbc1546acdd752"
    )
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_writes"] == 0
    assert packet["summary"] == {
        "caption_promotion_gate_passed": True,
        "critical_adversarial_errors": 0,
        "reviewed_fires": 50,
        "semantic_precision_pct": 100.0,
        "true_negative_cases": 20,
        "true_negatives": 20,
        "true_positives": 50,
        "wilson_lower_pct": 92.87,
    }
    assert packet["population"] == {
        "by_pool": {
            "community_puzzles": 403,
            "community_training_positions": 1204,
        },
        "by_target_piece": {
            "bishop": 579,
            "knight": 533,
            "queen": 218,
            "rook": 277,
        },
        "candidate_replay_failures": 0,
        "distinct_source_keys": 1305,
        "documents_scanned": 52060,
        "independent_outcomes": {"free_piece_exact": 1607},
        "stored_candidates": 1607,
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

    assert len({case["source_key"] for case in fires}) == 50
    assert {case["pool"] for case in fires} == {
        "community_puzzles",
        "community_training_positions",
    }
    assert {case["gold"]["captured_piece"] for case in fires} == {
        "knight",
        "bishop",
        "rook",
        "queen",
    }
    for case in fires:
        gold = independent_gold(_row(case))
        assert gold["verified"] is True, case["case_id"]
        assert gold["reason"] == "free_piece_exact"
        assert _candidate_fires(_row(case)) is True
        assert case["candidate_fired"] is True
        assert case["gold"] == {
            "reason": gold["reason"],
            "captured_piece": gold["captured_piece"],
            "captured_square": gold["captured_square"],
            "captured_value_cp": gold["captured_value_cp"],
        }

    counts = {name: 0 for name in NEGATIVE_STRATA}
    assert len({case["source_key"] for case in negatives}) == 20
    for case in negatives:
        gold = independent_gold(_row(case))
        assert gold["verified"] is False, case["case_id"]
        assert gold["reason"] == case["gold"]["reason"]
        assert gold["reason"] in counts
        counts[gold["reason"]] += 1
        assert _candidate_fires(_row(case)) is False
        assert case["candidate_fired"] is False
    assert counts == {name: 5 for name in NEGATIVE_STRATA}


def test_authorization_is_caption_only_and_has_no_plan_or_mastery_leak():
    authorization = get_authorization(FREE_PIECE_QUALITY_ID)

    assert authorization.grade == QualityGrade.CAPTION
    assert authorization.evidence_ref.endswith(
        "free_piece_exact_caption_promotion_v1.json"
    )
    assert is_authorized(FREE_PIECE_QUALITY_ID, QualitySurface.CAPTION)
    assert not is_authorized(FREE_PIECE_QUALITY_ID, QualitySurface.PROMPT)
    assert not is_authorized(FREE_PIECE_QUALITY_ID, QualitySurface.PLAN)
    assert not is_authorized(FREE_PIECE_QUALITY_ID, QualitySurface.MASTERY)


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
        assert verdict.caption_concept_id == "tactic.free_piece"
        assert stored_verdict_is_structurally_current(puzzle)
        feedback = build_verified_puzzle_feedback(
            puzzle,
            case["played_move_uci"],
            correct=False,
            primary_uci=case["best_move_uci"],
        )
        assert feedback["why"].endswith(
            f"takes the {gold['captured_piece']} on {gold['captured_square']}, "
            "and the opponent has no legal recapture."
        )
        assert feedback["remember"] == (
            "Before choosing a plan, scan every legal capture and count the recaptures."
        )
        grade = grade_resolved_puzzle(puzzle, case["best_move_uci"])
        assert grade["correct"] is True
        assert grade["recovery_weakness"] == "missed_tactic"
        assert grade["pattern_type"] == "missed_tactic"
        assert "tactic.free_piece" not in {
            grade["recovery_weakness"],
            grade["pattern_type"],
        }
