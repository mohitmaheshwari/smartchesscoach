from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.build_fork_payoff_caption_promotion_packet import (
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
from services.fork_puzzle_proof import FORK_QUALITY_ID
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
    / "fork_payoff_caption_promotion_v1.json"
)
PACKET_SHA256 = (
    "43bb871f6167984d577799effb645eccfef3b2870606065d0164d46ebd47436f"
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


def test_packet_is_pinned_private_and_meets_the_locked_caption_bar():
    packet = _packet()

    assert _canonical_sha256(packet) == PACKET_SHA256
    assert packet["schema_version"] == "fork_payoff.caption_promotion.v1"
    assert packet["quality_id"] == FORK_QUALITY_ID
    assert packet["selection"]["selection_fingerprint_sha256"] == (
        "d5917f80f7ed646d3672c8ed205c6e7209ad54c1361f4f42240bb3296b53dff0"
    )
    assert packet["stockfish_runs"] == 0
    assert packet["llm_calls"] == 0
    assert packet["database_writes"] == 0
    assert packet["summary"] == {
        "caption_promotion_gate_passed": True,
        "critical_adversarial_errors": 0,
        "reviewed_fires": 50,
        "semantic_precision_pct": 100.0,
        "true_negative_cases": 25,
        "true_negatives": 25,
        "true_positives": 50,
        "wilson_lower_pct": 92.87,
    }
    assert packet["population"] == {
        "by_forking_piece": {
            "bishop": 118,
            "knight": 451,
            "pawn": 60,
            "rook": 80,
        },
        "by_pool": {
            "community_puzzles": 155,
            "community_training_positions": 554,
        },
        "by_target_count": {"2": 651, "3": 58},
        "candidate_replay_failures": 0,
        "distinct_source_keys": 589,
        "documents_scanned": 52060,
        "independent_outcomes": {"fork_exact": 709},
        "stored_candidates": 709,
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
    assert {case["gold"]["forking_piece"] for case in fires} == {
        "knight",
        "bishop",
        "rook",
        "pawn",
    }
    assert {len(case["gold"]["targets"]) for case in fires} == {2, 3}
    for case in fires:
        gold = independent_gold(_row(case))
        assert gold["verified"] is True, case["case_id"]
        assert gold["reason"] == "fork_exact"
        assert _candidate_fires(_row(case)) is True
        assert case["candidate_fired"] is True
        assert case["gold"] == {
            "reason": gold["reason"],
            "forking_piece": gold["forking_piece"],
            "fork_square": gold["fork_square"],
            "targets": list(gold["targets"]),
            "captured_target": gold["captured_target"],
            "net_material_gain_cp": gold["net_material_gain_cp"],
            "replayed_uci": list(gold["replayed_uci"]),
        }

    counts = Counter()
    assert len({case["source_key"] for case in negatives}) == 25
    for case in negatives:
        gold = independent_gold(_row(case))
        assert gold["verified"] is False, case["case_id"]
        assert gold["reason"] == case["gold"]["reason"]
        assert gold["reason"] in NEGATIVE_STRATA
        counts[gold["reason"]] += 1
        assert _candidate_fires(_row(case)) is False
        assert case["candidate_fired"] is False
    assert counts == Counter({name: 5 for name in NEGATIVE_STRATA})


def test_authorization_is_caption_only_and_has_no_plan_or_mastery_leak():
    authorization = get_authorization(FORK_QUALITY_ID)

    assert authorization.grade == QualityGrade.CAPTION
    assert authorization.evidence_ref.endswith(
        "fork_payoff_caption_promotion_v1.json"
    )
    assert is_authorized(FORK_QUALITY_ID, QualitySurface.CAPTION)
    assert not is_authorized(FORK_QUALITY_ID, QualitySurface.PROMPT)
    assert not is_authorized(FORK_QUALITY_ID, QualitySurface.PLAN)
    assert not is_authorized(FORK_QUALITY_ID, QualitySurface.MASTERY)


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
        assert verdict.caption_concept_id == (
            f"tactic.{gold['forking_piece']}_fork"
        )
        assert verdict.reason_codes == (
            "caption_proof_verified",
            "broad_category_verified",
        )
        assert stored_verdict_is_structurally_current(puzzle)
        feedback = build_verified_puzzle_feedback(
            puzzle,
            case["played_move_uci"],
            correct=False,
            primary_uci=case["best_move_uci"],
        )
        assert f"puts your {gold['forking_piece']} on {gold['fork_square']}" in (
            feedback["why"]
        )
        assert "at the same time" in feedback["why"]
        assert all(target in feedback["why"] for target in gold["targets"])
        assert feedback["remember"] == (
            "Before choosing a move, scan every legal check and capture for one "
            "move that attacks more than one piece."
        )
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
        / "build_fork_payoff_caption_promotion_packet.py"
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
