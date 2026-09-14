"""Build a blinded review packet for the four locked teaching families.

The input is the frozen offline development measurement. This packet is useful
for independent defect discovery, but it is deliberately ineligible for
promotion because the 100-game source set was used during development.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Tuple

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.caption_facts import (  # noqa: E402
    TEACHING_OPPORTUNITY_PROOF_VERSION,
    TEACHING_OPPORTUNITY_QUALITY_IDS,
)


SCHEMA_VERSION = "deterministic_teaching_opportunity_blinded_review.v1"
ANSWER_KEY_SCHEMA_VERSION = (
    "deterministic_teaching_opportunity_blinded_review_answer_key.v1"
)
DEFAULT_SOURCE = BACKEND / (
    "data/corpus_snapshots/"
    "deterministic_teaching_opportunity_family_measurement_v3_2026-09-14.json"
)
DEFAULT_PACKET = BACKEND / (
    "data/detector_gold/"
    "deterministic_teaching_opportunity_blinded_development_review_v1.json"
)
DEFAULT_ANSWER_KEY = BACKEND / (
    "data/detector_gold/"
    "deterministic_teaching_opportunity_blinded_development_answer_key_v1.json"
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _case_id(fingerprint: str) -> str:
    return _sha256_bytes(
        f"teaching-opportunity-independent-review:{fingerprint}".encode("utf-8")
    )


def build_packets(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    candidates = source.get("candidates")
    summary = source.get("summary")
    if (
        source.get("schema_version")
        != "deterministic_teaching_opportunity_measurement.v2"
        or source.get("status") != "development_shadow_evidence_only"
        or not isinstance(candidates, list)
        or not isinstance(summary, Mapping)
        or summary.get("proof_version") != TEACHING_OPPORTUNITY_PROOF_VERSION
        or summary.get("caption_authorized_family_count") != 0
    ):
        raise ValueError("source measurement is not the frozen Shadow contract")

    public_cases = []
    answer_rows = []
    seen_fingerprints = set()
    family_counts = Counter()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("candidate must be a mapping")
        fact = candidate.get("fact")
        comparison = candidate.get("comparison")
        if not isinstance(fact, Mapping) or not isinstance(comparison, Mapping):
            raise ValueError("candidate fact and comparison are required")
        family = str(fact.get("family") or "")
        quality_id = str(fact.get("quality_id") or "")
        fingerprint = str(fact.get("fingerprint") or "")
        if (
            family not in TEACHING_OPPORTUNITY_QUALITY_IDS
            or quality_id != TEACHING_OPPORTUNITY_QUALITY_IDS[family]
            or fact.get("schema_version") != TEACHING_OPPORTUNITY_PROOF_VERSION
            or comparison.get("schema_version")
            != "teaching_opportunity_comparison.v2"
            or comparison.get("rollout_mode") != "shadow"
            or (comparison.get("display") or {}).get("authorized") is not False
            or comparison.get("opportunity_fingerprint") != fingerprint
            or fingerprint in seen_fingerprints
        ):
            raise ValueError("candidate identity or proof binding is invalid")
        seen_fingerprints.add(fingerprint)
        family_counts[family] += 1
        case_id = _case_id(fingerprint)
        public_cases.append(
            {
                "case_id": case_id,
                "position": {
                    "fen_before": candidate.get("fen_before"),
                    "actor": candidate.get("actor"),
                    "source_ply": candidate.get("ply"),
                    "played_move": candidate.get("played_san"),
                    "stronger_move": candidate.get("best_move_san"),
                },
                "visible_claim": {
                    "headline": comparison.get("headline"),
                    "what_happened": (comparison.get("played") or {}).get(
                        "summary"
                    ),
                    "stronger_idea": (comparison.get("stronger") or {}).get(
                        "summary"
                    ),
                    "memory_cue": comparison.get("memory_cue"),
                },
                "replay": {
                    "played_line": (comparison.get("played") or {}).get("moves"),
                    "stronger_line": (comparison.get("stronger") or {}).get(
                        "moves"
                    ),
                },
            }
        )
        answer_rows.append(
            {
                "case_id": case_id,
                "family": family,
                "quality_id": quality_id,
                "opportunity_fingerprint": fingerprint,
                "anonymous_source_unit": candidate.get("anonymous_game_key"),
            }
        )

    public_cases.sort(
        key=lambda item: _sha256_bytes(
            f"teaching-opportunity-review-order:{item['case_id']}".encode("utf-8")
        )
    )
    answer_rows.sort(key=lambda item: item["case_id"])
    ordered_case_ids = [item["case_id"] for item in public_cases]
    selection_fingerprint = _sha256_bytes("|".join(ordered_case_ids).encode("utf-8"))
    packet = {
        "schema_version": SCHEMA_VERSION,
        "sample": "development",
        "development_only": True,
        "promotion_eligible": False,
        "blinded": True,
        "detector_labels_exposed": False,
        "source_measurement_sha256": source_sha256,
        "selection_fingerprint_sha256": selection_fingerprint,
        "cases": public_cases,
        "review_rubric": {
            "verdict_values": ["true", "false", "uncertain", "invalid_case"],
            "required_checks": [
                "both displayed branches replay legally from the supplied FEN",
                "the visible wording distinguishes played history from counterfactual play",
                "every named piece, square, owner and move matches the board",
                "mate wording reaches legal checkmate rather than an incomplete threat",
                "material wording survives captures, recaptures and forcing replies",
                "the memory cue follows from this position and is not a universal false rule",
            ],
            "response_contract": {
                "case_id": "copy exactly",
                "verdict": "one verdict_values entry",
                "critical_false_claim": "boolean",
                "review_note": "short chess reason naming the refuting or confirming line",
            },
        },
        "promotion_gate": {
            "minimum_reviewed_visible_claims_per_family": 50,
            "minimum_semantic_precision_pct": 95.0,
            "minimum_wilson_95_lower_pct": 85.0,
            "critical_false_claims_allowed": 0,
            "independent_review_complete": False,
            "caption_promotion_gate_passed": False,
            "blockers": [
                "development_sample_is_not_promotion_eligible",
                "independent_blinded_review_pending",
                "three_families_have_fewer_than_50_available_claims",
            ],
        },
    }
    answer_key = {
        "schema_version": ANSWER_KEY_SCHEMA_VERSION,
        "source_measurement_sha256": source_sha256,
        "review_packet_selection_fingerprint_sha256": selection_fingerprint,
        "family_counts": {
            family: family_counts[family]
            for family in TEACHING_OPPORTUNITY_QUALITY_IDS
        },
        "cases": answer_rows,
    }
    return packet, answer_key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--answer-key", type=Path, default=DEFAULT_ANSWER_KEY)
    args = parser.parse_args()
    source_path = args.source.resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    packet, answer_key = build_packets(
        source,
        source_sha256=_sha256_path(source_path),
    )
    for path, payload in ((args.packet, packet), (args.answer_key, answer_key)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "cases": len(packet["cases"]),
                "family_counts": answer_key["family_counts"],
                "promotion_eligible": packet["promotion_eligible"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
