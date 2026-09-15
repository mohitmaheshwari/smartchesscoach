#!/usr/bin/env python3
"""Score a frozen independent review of exact played-checkmate captions."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts import build_exact_terminal_checkmate_caption_packet as builder  # noqa: E402


SCHEMA_VERSION = "exact_terminal_checkmate.caption_review_score.v1"
GENERATED_ON = "2026-09-15"
VERDICTS = frozenset({
    "proved_exact_terminal_checkmate",
    "not_proved",
    "invalid_case",
})
TEACHING_VERDICTS = frozenset({
    "correct_and_teachable",
    "correct_but_not_teachable",
    "incorrect_or_overclaimed",
})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson_lower(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    spread = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return (centre - spread) / denominator


def _blank_response() -> dict[str, Any]:
    return {
        "schema_version": builder.REVIEW_RESPONSE_SCHEMA_VERSION,
        "verdict": None,
        "teaching_verdict": None,
        "critical_false_claim": None,
        "review_note": "",
    }


def _assert_only_review_changed(
    source: Mapping[str, Any], reviewed: Mapping[str, Any]
) -> None:
    comparison = deepcopy(dict(reviewed))
    comparison.pop("independent_review", None)
    cases = comparison.get("cases")
    if not isinstance(cases, list):
        raise ValueError("reviewed packet has no cases")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("reviewed packet contains a non-object case")
        case["reviewer_response"] = _blank_response()
    if comparison != source:
        raise ValueError("review changed content outside reviewer_response")


def score_review(
    *,
    packet_path: Path,
    reviewed_path: Path,
    answer_key_path: Path,
) -> dict[str, Any]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    answer_key = json.loads(answer_key_path.read_text(encoding="utf-8"))
    packet_sha = _sha256(packet_path)
    if packet.get("schema_version") != builder.SCHEMA_VERSION:
        raise ValueError("unexpected terminal review packet schema")
    if answer_key.get("schema_version") != builder.ANSWER_KEY_SCHEMA_VERSION:
        raise ValueError("unexpected terminal answer-key schema")
    if (answer_key.get("source_packet") or {}).get("sha256") != packet_sha:
        raise ValueError("answer key is not bound to the frozen packet")
    if (answer_key.get("source_packet") or {}).get(
        "selection_fingerprint_sha256"
    ) != (packet.get("selection") or {}).get("selection_fingerprint_sha256"):
        raise ValueError("answer key selection fingerprint changed")
    independent = reviewed.get("independent_review")
    if not isinstance(independent, Mapping):
        raise ValueError("independent review attestation is missing")
    if independent.get("packet_sha256") != packet_sha:
        raise ValueError("independent review is bound to another packet")
    if independent.get("frozen") is not True:
        raise ValueError("independent review is not frozen")
    if not str(independent.get("reviewer") or "").strip() or not str(
        independent.get("method") or ""
    ).strip():
        raise ValueError("independent review identity and method are required")
    _assert_only_review_changed(packet, reviewed)

    source_cases = {
        str(case["case_id"]): case for case in packet.get("cases", [])
    }
    reviewed_cases = {
        str(case["case_id"]): case for case in reviewed.get("cases", [])
    }
    if not source_cases or set(source_cases) != set(reviewed_cases):
        raise ValueError("reviewed case set does not match the packet")
    candidate_ids = set(answer_key.get("candidate_case_ids") or [])
    control_ids = set(answer_key.get("control_case_ids") or [])
    if candidate_ids & control_ids or candidate_ids | control_ids != set(source_cases):
        raise ValueError("answer-key membership does not partition the packet")

    confusion: Counter[str] = Counter()
    teaching: Counter[str] = Counter()
    candidate_critical = 0
    control_critical = 0
    disagreements: list[dict[str, Any]] = []
    for case_id, case in reviewed_cases.items():
        response = case.get("reviewer_response")
        if not isinstance(response, Mapping):
            raise ValueError(f"{case_id}: reviewer response is missing")
        if response.get("schema_version") != builder.REVIEW_RESPONSE_SCHEMA_VERSION:
            raise ValueError(f"{case_id}: reviewer response schema is wrong")
        verdict = str(response.get("verdict") or "")
        teaching_verdict = str(response.get("teaching_verdict") or "")
        critical = response.get("critical_false_claim")
        if verdict not in VERDICTS:
            raise ValueError(f"{case_id}: invalid verdict")
        if teaching_verdict not in TEACHING_VERDICTS:
            raise ValueError(f"{case_id}: invalid teaching verdict")
        if type(critical) is not bool:
            raise ValueError(f"{case_id}: critical_false_claim must be boolean")
        if not str(response.get("review_note") or "").strip():
            raise ValueError(f"{case_id}: review note is required")
        selected = case_id in candidate_ids
        proved = verdict == "proved_exact_terminal_checkmate"
        if selected and proved:
            bucket = "true_positive"
        elif selected:
            bucket = "false_positive"
        elif proved:
            bucket = "false_negative"
        else:
            bucket = "true_negative"
        confusion[bucket] += 1
        teaching[teaching_verdict] += 1
        if critical:
            if selected:
                candidate_critical += 1
            else:
                control_critical += 1
        if bucket != "true_positive" and bucket != "true_negative":
            disagreements.append({
                "case_id": case_id,
                "bucket": bucket,
                "verdict": verdict,
                "teaching_verdict": teaching_verdict,
                "critical_false_claim": critical,
                "review_note": response["review_note"],
            })

    tp = confusion["true_positive"]
    fp = confusion["false_positive"]
    fn = confusion["false_negative"]
    tn = confusion["true_negative"]
    selected = tp + fp
    precision = tp / selected if selected else 0.0
    wilson = _wilson_lower(tp, selected)
    candidate_teachable = sum(
        1
        for case_id in candidate_ids
        if reviewed_cases[case_id]["reviewer_response"]["teaching_verdict"]
        == "correct_and_teachable"
    )
    gate = packet["promotion_gate"]
    checks = {
        "reviewed_fire_minimum_met": selected >= gate["caption_fire_minimum"],
        "exact_fact_has_zero_false_positives": fp == 0,
        "semantic_precision_met": precision >= gate["semantic_precision_minimum_pct"] / 100,
        "wilson_lower_bound_met": wilson >= gate["wilson_lower_minimum_pct"] / 100,
        "true_negative_minimum_met": tn >= gate["true_negative_minimum"],
        "zero_candidate_critical_false_claims": candidate_critical == 0,
        "all_candidate_copy_correct_and_teachable": candidate_teachable == selected,
        "independent_review_complete": True,
    }
    passed = all(checks.values())
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "quality_id": packet["quality_id"],
        "proof_version": packet["proof_version"],
        "sources": {
            "packet": {"path": str(packet_path), "sha256": packet_sha},
            "review": {"path": str(reviewed_path), "sha256": _sha256(reviewed_path)},
            "sealed_answer_key": {
                "path": str(answer_key_path),
                "sha256": _sha256(answer_key_path),
            },
        },
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
        },
        "caption_evidence": {
            "semantic_precision_pct": round(precision * 100, 2),
            "wilson_lower_bound_pct": round(wilson * 100, 2),
            "candidate_copy_correct_and_teachable": candidate_teachable,
            "candidate_critical_false_claims": candidate_critical,
            "control_critical_flags": control_critical,
            "teaching_verdicts_all_cases": dict(sorted(teaching.items())),
        },
        "promotion_gate": {
            **checks,
            "caption_promotion_gate_passed": passed,
            "status": "caption_eligible" if passed else "shadow",
            "blockers": blockers,
        },
        "disagreements": sorted(disagreements, key=lambda row: row["case_id"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    score = score_review(
        packet_path=args.packet,
        reviewed_path=args.reviewed,
        answer_key_path=args.answer_key,
    )
    encoded = json.dumps(score, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
