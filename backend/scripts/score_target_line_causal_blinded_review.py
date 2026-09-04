"""Score the frozen target/line review without changing the detector.

The reviewer packet intentionally hides candidate/control membership.  This
script reveals that membership only after a complete response file exists,
then reports the raw blinded confusion matrix.  It reads versioned local
evidence only: no database, engine, network, or LLM is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts import build_target_line_causal_pre_promotion_packet as packet_builder
from scripts.validate_hidden_opportunities_target_line_proofs import (
    _wilson_lower_bound,
)


SCHEMA_VERSION = "target_line_causal.blinded_review_score.v1"
GENERATED_ON = "2026-09-03"
DEFAULT_REVIEW_PATH = packet_builder.BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_blinded_codex_review_v1.json"
)
DEFAULT_PACKET_PATH = packet_builder.BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_review_v1.json"
)
DEFAULT_ANSWER_KEY_PATH = packet_builder.BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_answer_key_v1.json"
)
DEFAULT_OUTPUT_PATH = packet_builder.BACKEND_ROOT / (
    "data/corpus_snapshots/"
    "target_line_causal_blinded_codex_review_score_v1_2026-09-03.json"
)
VERDICTS = {
    "proved_target_line_payoff",
    "not_proved",
    "insufficient_stored_horizon",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_review(
    *,
    packet_path: Path = DEFAULT_PACKET_PATH,
    review_path: Path = DEFAULT_REVIEW_PATH,
    answer_key_path: Path = DEFAULT_ANSWER_KEY_PATH,
) -> dict[str, Any]:
    packet_path = packet_path.resolve()
    review_path = review_path.resolve()
    answer_key_path = answer_key_path.resolve()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    answer_key = json.loads(answer_key_path.read_text(encoding="utf-8"))
    packet_sha256 = _sha256(packet_path)
    review_packet_sha256 = review.get("packet_sha256")
    if (
        review_packet_sha256 is not None
        and review_packet_sha256 != packet_sha256
    ):
        raise ValueError("frozen review is not bound to this packet")
    packet_cases = {case["case_id"]: case for case in packet["cases"]}
    responses = review.get("responses")
    if not isinstance(responses, list):
        raise ValueError("review responses must be a list")
    response_by_id: dict[str, dict[str, Any]] = {}
    for response in responses:
        case_id = response.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("every response requires a case_id")
        if case_id in response_by_id:
            raise ValueError(f"duplicate response: {case_id}")
        if response.get("verdict") not in VERDICTS:
            raise ValueError(f"invalid verdict for {case_id}")
        if not isinstance(response.get("critical_false_claim"), bool):
            raise ValueError(f"invalid critical_false_claim for {case_id}")
        if not isinstance(response.get("review_note"), str):
            raise ValueError(f"invalid review_note for {case_id}")
        response_by_id[case_id] = response
    if set(response_by_id) != set(packet_cases):
        missing = sorted(set(packet_cases) - set(response_by_id))
        extra = sorted(set(response_by_id) - set(packet_cases))
        raise ValueError(
            f"response case set mismatch; missing={missing}, extra={extra}"
        )

    candidate_ids = set(answer_key["candidate_case_ids"])
    control_ids = set(answer_key["control_case_ids"])
    if candidate_ids & control_ids:
        raise ValueError("answer-key candidate/control overlap")
    if candidate_ids | control_ids != set(packet_cases):
        raise ValueError("answer-key case set does not match packet")
    if answer_key["source_packet"]["sha256"] != packet_sha256:
        raise ValueError("answer key is not bound to this packet")
    private_membership = {
        case_id: case_id in candidate_ids for case_id in packet_cases
    }

    confusion: Counter[str] = Counter()
    disagreements: list[dict[str, Any]] = []
    for case_id, response in response_by_id.items():
        detector_selected = private_membership[case_id]
        reviewer_proved = (
            response["verdict"] == "proved_target_line_payoff"
        )
        if detector_selected and reviewer_proved:
            bucket = "true_positive"
        elif detector_selected:
            bucket = "false_positive"
        elif reviewer_proved:
            bucket = "false_negative"
        else:
            bucket = "true_negative"
        confusion[bucket] += 1
        if bucket in {"false_positive", "false_negative"}:
            disagreements.append({
                "case_id": case_id,
                "bucket": bucket,
                "reviewer_verdict": response["verdict"],
                "critical_false_claim": response["critical_false_claim"],
                "review_note": response["review_note"],
            })

    tp = confusion["true_positive"]
    fp = confusion["false_positive"]
    fn = confusion["false_negative"]
    tn = confusion["true_negative"]
    selected = tp + fp
    reviewer_positive = tp + fn
    precision = tp / selected if selected else 0.0
    packet_positive_capture = (
        tp / reviewer_positive if reviewer_positive else 0.0
    )
    critical_errors = sum(
        bool(response["critical_false_claim"])
        for response in responses
    )
    candidate_critical_errors = sum(
        bool(response["critical_false_claim"])
        for case_id, response in response_by_id.items()
        if private_membership[case_id]
    )
    control_critical_flags = critical_errors - candidate_critical_errors
    fire_minimum = packet["promotion_gate"]["caption_fire_minimum"]
    precision_minimum = (
        packet["promotion_gate"]["semantic_precision_minimum_pct"] / 100
    )
    wilson_minimum = (
        packet["promotion_gate"]["wilson_lower_minimum_pct"] / 100
    )
    true_negative_minimum = packet["promotion_gate"][
        "true_negative_minimum"
    ]
    wilson = _wilson_lower_bound(tp, selected)

    modern_review = review.get("schema_version") == (
        "target_line_causal.independent_review.v3"
    )
    independent_complete = bool(modern_review and review.get("frozen"))
    available_ok = selected >= fire_minimum
    precision_ok = precision >= precision_minimum
    wilson_ok = wilson >= wilson_minimum
    negatives_ok = tn >= true_negative_minimum
    critical_ok = candidate_critical_errors == 0
    modern_blockers = []
    if not available_ok:
        modern_blockers.append("reviewed_fire_minimum_not_met")
    if not precision_ok:
        modern_blockers.append("raw_blinded_precision_below_95_pct")
    if not wilson_ok:
        modern_blockers.append("raw_blinded_wilson_below_85_pct")
    if not negatives_ok:
        modern_blockers.append("true_negative_minimum_not_met")
    if not critical_ok:
        modern_blockers.append("critical_candidate_false_claims_present")
    if not independent_complete:
        modern_blockers.append("independent_reviewer_still_required")
    modern_blockers.append("final_rendered_claim_audit_pending")

    score = {
        "schema_version": (
            "target_line_causal.blinded_review_score.v2"
            if modern_review else SCHEMA_VERSION
        ),
        "generated_on": "2026-09-04" if modern_review else GENERATED_ON,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "quality_id": packet["quality_id"],
        "proof_version": packet["proof_version"],
        "review_independence": review.get("reviewer_independence") or {
            "reviewer": review.get("reviewer"),
            "method": review.get("method"),
            "frozen": review.get("frozen"),
        },
        "sources": {
            "blinded_packet": {
                "path": packet_path.relative_to(
                    packet_builder.BACKEND_ROOT.parent
                ).as_posix(),
                "sha256": _sha256(packet_path),
            },
            "frozen_review": {
                "path": review_path.relative_to(
                    packet_builder.BACKEND_ROOT.parent
                ).as_posix(),
                "sha256": _sha256(review_path),
            },
            "frozen_answer_key": {
                "path": answer_key_path.relative_to(
                    packet_builder.BACKEND_ROOT.parent
                ).as_posix(),
                "sha256": _sha256(answer_key_path),
            },
        },
        "sample": {
            "cases": len(packet_cases),
            "detector_candidates": selected,
            "sampled_controls": fn + tn,
            "reviewer_positive": reviewer_positive,
            "reviewer_nonpositive": fp + tn,
        },
        "raw_blinded_score": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "semantic_precision_pct": round(precision * 100, 2),
            "wilson_lower_bound_pct": round(wilson * 100, 2),
            "packet_positive_capture_pct": round(
                packet_positive_capture * 100, 2
            ),
            "critical_false_claims": critical_errors,
            "recall_warning": (
                "Controls are sampled positive-edge near-controls, not an "
                "opportunity-denominator population; packet_positive_capture "
                "is not population recall."
            ),
        },
        "raw_gate": (
            {
                "available_fires_meet_minimum": available_ok,
                "precision_meets_minimum": precision_ok,
                "wilson_meets_minimum": wilson_ok,
                "true_negatives_meet_minimum": negatives_ok,
                "zero_critical_errors": critical_ok,
                "independent_review_complete": independent_complete,
                "caption_promotion_gate_passed": False,
                "status": "shadow",
                "blockers": modern_blockers,
            }
            if modern_review
            else {
                "available_fires_meet_minimum": available_ok,
                "precision_meets_minimum": precision_ok,
                "wilson_meets_minimum": wilson_ok,
                "true_negatives_meet_minimum": negatives_ok,
                "zero_critical_errors": critical_errors == 0,
                "independent_review_complete": False,
                "caption_promotion_gate_passed": False,
                "status": "shadow",
                "blockers": [
                    "reviewed_fire_minimum_not_met",
                    "raw_blinded_precision_below_95_pct",
                    "raw_blinded_wilson_below_85_pct",
                    "independent_reviewer_still_required",
                    "final_rendered_claim_audit_pending",
                ],
            }
        ),
        "raw_disagreements": sorted(
            disagreements, key=lambda item: item["case_id"]
        ),
    }
    if modern_review:
        score["raw_blinded_score"].update({
            "candidate_critical_false_claims": candidate_critical_errors,
            "control_critical_flags": control_critical_flags,
        })
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument(
        "--answer-key", type=Path, default=DEFAULT_ANSWER_KEY_PATH
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_review(
        packet_path=args.packet,
        review_path=args.review,
        answer_key_path=args.answer_key,
    )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
