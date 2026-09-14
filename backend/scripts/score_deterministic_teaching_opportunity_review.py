"""Score one complete independent review against the separate family key."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping

from scripts.build_deterministic_teaching_opportunity_review_packet import (
    ANSWER_KEY_SCHEMA_VERSION,
    SCHEMA_VERSION as PACKET_SCHEMA_VERSION,
)
from services.caption_facts import (
    TEACHING_OPPORTUNITY_CLAIM_CONTRACTS,
    TEACHING_OPPORTUNITY_QUALITY_IDS,
)


SCHEMA_VERSION = "deterministic_teaching_opportunity_review_score.v1"
REVIEW_SCHEMA_VERSION = "deterministic_teaching_opportunity_independent_review.v1"
VALID_VERDICTS = frozenset({"true", "false", "uncertain", "invalid_case"})


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson_lower(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + (z * z / total)
    centre = proportion + (z * z / (2 * total))
    margin = z * math.sqrt(
        (proportion * (1 - proportion) / total)
        + (z * z / (4 * total * total))
    )
    return (centre - margin) / denominator


def score_review(
    packet: Mapping[str, Any],
    answer_key: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    packet_sha256: str,
) -> Dict[str, Any]:
    packet_cases = packet.get("cases")
    key_rows = answer_key.get("cases")
    review_rows = review.get("case_reviews")
    attestation = review.get("independence_attestation")
    if (
        packet.get("schema_version") != PACKET_SCHEMA_VERSION
        or packet.get("blinded") is not True
        or answer_key.get("schema_version") != ANSWER_KEY_SCHEMA_VERSION
        or review.get("schema_version") != REVIEW_SCHEMA_VERSION
        or review.get("source_review_packet_sha256") != packet_sha256
        or not isinstance(packet_cases, list)
        or not isinstance(key_rows, list)
        or not isinstance(review_rows, list)
        or not isinstance(attestation, Mapping)
        or attestation.get("independent_from_implementation") is not True
        or attestation.get("answer_key_unseen") is not True
        or attestation.get("detector_code_unseen") is not True
    ):
        raise ValueError("packet, key, review binding or independence is invalid")

    packet_ids = [str(item.get("case_id") or "") for item in packet_cases]
    key_by_id = {
        str(item.get("case_id") or ""): item
        for item in key_rows
        if isinstance(item, Mapping)
    }
    review_by_id = {}
    for item in review_rows:
        if not isinstance(item, Mapping):
            raise ValueError("review row must be a mapping")
        case_id = str(item.get("case_id") or "")
        verdict = str(item.get("verdict") or "")
        note = " ".join(str(item.get("review_note") or "").split())
        critical = item.get("critical_false_claim")
        if (
            not case_id
            or case_id in review_by_id
            or verdict not in VALID_VERDICTS
            or not note
            or not isinstance(critical, bool)
            or (critical and verdict != "false")
        ):
            raise ValueError("review response row is invalid")
        review_by_id[case_id] = item
    if (
        len(packet_ids) != len(set(packet_ids))
        or set(packet_ids) != set(key_by_id)
        or set(packet_ids) != set(review_by_id)
    ):
        raise ValueError("review must cover every blinded case exactly once")
    if answer_key.get("review_packet_selection_fingerprint_sha256") != packet.get(
        "selection_fingerprint_sha256"
    ):
        raise ValueError("answer key belongs to a different packet selection")

    family_rows = {family: Counter() for family in TEACHING_OPPORTUNITY_QUALITY_IDS}
    claim_contract_rows = {
        claim_contract: Counter()
        for contracts in TEACHING_OPPORTUNITY_CLAIM_CONTRACTS.values()
        for claim_contract in contracts
    }
    key_family_counts = Counter()
    key_claim_contract_counts = Counter()
    for case_id in packet_ids:
        family = str(key_by_id[case_id].get("family") or "")
        if family not in family_rows:
            raise ValueError("answer key contains an unknown family")
        if key_by_id[case_id].get("quality_id") != (
            TEACHING_OPPORTUNITY_QUALITY_IDS[family]
        ):
            raise ValueError("answer key quality identity is invalid")
        claim_contract = str(
            key_by_id[case_id].get("claim_contract") or ""
        )
        if claim_contract not in TEACHING_OPPORTUNITY_CLAIM_CONTRACTS[family]:
            raise ValueError("answer key contains an invalid claim contract")
        key_family_counts[family] += 1
        key_claim_contract_counts[claim_contract] += 1
        response = review_by_id[case_id]
        verdict = str(response["verdict"])
        family_rows[family][verdict] += 1
        family_rows[family]["critical_false_claim"] += int(
            response["critical_false_claim"]
        )
        claim_contract_rows[claim_contract][verdict] += 1
        claim_contract_rows[claim_contract]["critical_false_claim"] += int(
            response["critical_false_claim"]
        )
    if answer_key.get("family_counts") != {
        family: key_family_counts[family]
        for family in TEACHING_OPPORTUNITY_QUALITY_IDS
    }:
        raise ValueError("answer key family counts are inconsistent")
    expected_contract_counts = {
        claim_contract: key_claim_contract_counts[claim_contract]
        for contracts in TEACHING_OPPORTUNITY_CLAIM_CONTRACTS.values()
        for claim_contract in sorted(contracts)
    }
    if answer_key.get("claim_contract_counts") != expected_contract_counts:
        raise ValueError("answer key claim-contract counts are inconsistent")

    def _numeric_score(counts: Counter) -> Dict[str, Any]:
        denominator = counts["true"] + counts["false"] + counts["uncertain"]
        precision = counts["true"] / denominator if denominator else 0.0
        wilson = _wilson_lower(counts["true"], denominator)
        numeric_gate = bool(
            denominator >= 50
            and precision >= 0.95
            and wilson >= 0.85
            and counts["critical_false_claim"] == 0
        )
        return {
            "reviewed_claims": denominator,
            "true": counts["true"],
            "false": counts["false"],
            "uncertain": counts["uncertain"],
            "invalid_case": counts["invalid_case"],
            "critical_false_claims": counts["critical_false_claim"],
            "semantic_precision_pct": round(precision * 100, 4),
            "wilson_95_lower_pct": round(wilson * 100, 4),
            "numeric_quality_gate_passed": numeric_gate,
        }

    claim_contract_scores = {
        claim_contract: {
            **_numeric_score(counts),
            "caption_promotion_gate_passed": False,
            "promotion_blocker": "development_sample_is_not_promotion_eligible",
        }
        for claim_contract, counts in sorted(claim_contract_rows.items())
    }
    family_scores = {}
    for family, counts in family_rows.items():
        score = _numeric_score(counts)
        required_contracts = sorted(
            TEACHING_OPPORTUNITY_CLAIM_CONTRACTS[family]
        )
        contracts_pass = all(
            claim_contract_scores[claim_contract][
                "numeric_quality_gate_passed"
            ]
            for claim_contract in required_contracts
        )
        score["aggregate_numeric_quality_gate_passed"] = score[
            "numeric_quality_gate_passed"
        ]
        score["numeric_quality_gate_passed"] = bool(
            score["numeric_quality_gate_passed"] and contracts_pass
        )
        score["claim_contracts"] = required_contracts
        score["all_claim_contract_gates_passed"] = contracts_pass
        score["caption_promotion_gate_passed"] = False
        score["promotion_blocker"] = (
            "development_sample_is_not_promotion_eligible"
        )
        family_scores[family] = score

    return {
        "schema_version": SCHEMA_VERSION,
        "source_review_packet_sha256": packet_sha256,
        "sample": packet.get("sample"),
        "development_only": packet.get("development_only") is True,
        "independence_attestation": dict(attestation),
        "family_scores": family_scores,
        "claim_contract_scores": claim_contract_scores,
        "caption_authorizations_changed": 0,
        "overall_promotion_gate_passed": False,
        "next_step": (
            "correct any independently found defects, freeze the implementation, "
            "then build fresh non-holdout packets with at least 50 claims per "
            "visible claim contract"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    answer_key = json.loads(args.answer_key.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    result = score_review(
        packet,
        answer_key,
        review,
        packet_sha256=_sha256_path(args.packet),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result["family_scores"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
