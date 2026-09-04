"""Build the offline, blinded forcing-tempo pre-promotion packet.

Only versioned anonymized evidence is read. Shared normalization and blinding
helpers come from the target-line packet builder so source identity, overlap
exclusion, control selection, and public-case shape cannot drift by family.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.build_target_line_causal_pre_promotion_packet import (  # noqa: E402
    ARCHITECTURE_GOLD_PATH,
    CAPTION_FIRE_MINIMUM,
    CONTROL_TARGET,
    FULL_AUDIT_PATH,
    FULL_CONTROL_TARGET,
    PRIOR_CONTROL_TARGET,
    PRIOR_PACKET_PATH,
    _architecture_signatures,
    _evidence,
    _normalize_full_cases,
    _normalize_prior_cases,
    _position_signature,
    _public_review_case,
    _select_full_controls,
    _select_prior_controls,
    _source_record,
)
from services.caption_facts import (  # noqa: E402
    FORCING_TEMPO_CAUSAL_PROOF_VERSION,
    FORCING_TEMPO_CAUSAL_QUALITY_ID,
    build_forcing_tempo_opportunity_proof,
)


SCHEMA_VERSION = "forcing_tempo_causal.pre_promotion_review.v1"
GENERATED_ON = "2026-09-03"
DEFAULT_OUTPUT_PATH = BACKEND_ROOT / (
    "data/detector_gold/forcing_tempo_causal_pre_promotion_review_v1.json"
)


def _proof(row: Mapping[str, Any]):
    return build_forcing_tempo_opportunity_proof(
        fen_before=row["fen_before"],
        played_san=row["played_san"],
        best_move_san=row["best_move_san"],
        pv_after_played=row["pv_after_played"],
        pv_after_best=row["pv_after_best"],
        cp_loss=row.get("cp_loss"),
    )


def build_packet() -> dict[str, Any]:
    architecture_signatures = _architecture_signatures()
    all_rows = list(_normalize_full_cases()) + list(_normalize_prior_cases())
    seen_signatures: set[str] = set()
    fires: list[dict[str, Any]] = []
    controls_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    population = Counter()
    mechanism_counts = Counter()
    fire_source_units: set[str] = set()

    for row in all_rows:
        population["cases_scanned"] += 1
        signature = _position_signature(row)
        if signature in architecture_signatures:
            population["architecture_overlap_excluded"] += 1
            continue
        if signature in seen_signatures:
            population["duplicate_positions_excluded"] += 1
            continue
        seen_signatures.add(signature)
        evidence = _evidence(row)
        if evidence is None:
            population["incomplete_branch_evidence"] += 1
            continue
        population["complete_branch_evidence"] += 1
        proof = _proof(row)
        if proof is not None:
            fires.append(row)
            mechanism_counts[proof.mechanism] += 1
            fire_source_units.add(row["source_unit_key"])
            continue
        if evidence.difference.net_material_edge_cp > 0:
            controls_by_source[row["source_kind"]].append(row)
            population["positive_edge_near_controls"] += 1
        else:
            population["nonpositive_edge_no_fires"] += 1

    controls = _select_full_controls(
        controls_by_source["full_game_audit_80"]
    ) + _select_prior_controls(
        controls_by_source["prior_cause_packet_100"]
    )
    public_cases = [_public_review_case(row) for row in fires + controls]
    public_cases.sort(key=lambda case: hashlib.sha256(
        f"forcing-tempo-review:{case['case_id']}".encode("utf-8")
    ).hexdigest())
    case_ids = [case["case_id"] for case in public_cases]
    fire_shortfall = max(0, CAPTION_FIRE_MINIMUM - len(fires))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "quality_id": FORCING_TEMPO_CAUSAL_QUALITY_ID,
        "proof_version": FORCING_TEMPO_CAUSAL_PROOF_VERSION,
        "status": "pre_promotion_blocked",
        "sources": [
            _source_record(
                FULL_AUDIT_PATH, role="independent_full_game_population"
            ),
            _source_record(
                PRIOR_PACKET_PATH, role="independent_stored_line_population"
            ),
            _source_record(
                ARCHITECTURE_GOLD_PATH,
                role="development_overlap_exclusion_only",
            ),
        ],
        "claim_under_review": (
            "The complete stored continuations prove that move order or a "
            "forcing tempo preserves or creates a positive material payoff."
        ),
        "selection": {
            "candidate_policy": (
                "all independent post-horizon-guard detector fires"
            ),
            "control_policy": (
                "the shared deterministic two-branch positive-edge control "
                "policy: 23 stratified full-game controls and seven distinct "
                "prior-packet controls"
            ),
            "candidate_target": "all_available",
            "control_target": CONTROL_TARGET,
            "full_game_controls": FULL_CONTROL_TARGET,
            "prior_packet_controls": PRIOR_CONTROL_TARGET,
            "selection_fingerprint_sha256": hashlib.sha256(
                "|".join(case_ids).encode("utf-8")
            ).hexdigest(),
        },
        "population": {
            **dict(sorted(population.items())),
            "candidate_fires": len(fires),
            "candidate_fire_source_units": len(fire_source_units),
            "mechanisms": dict(sorted(mechanism_counts.items())),
        },
        "review_packet": {
            "blinded": True,
            "detector_labels_exposed": False,
            "cases": len(public_cases),
            "candidate_fires_hidden": len(fires),
            "controls_hidden": len(controls),
        },
        "promotion_gate": {
            "caption_fire_minimum": CAPTION_FIRE_MINIMUM,
            "available_independent_fires": len(fires),
            "fire_shortfall": fire_shortfall,
            "true_negative_minimum": 20,
            "controls_awaiting_review": len(controls),
            "semantic_precision_minimum_pct": 95.0,
            "wilson_lower_minimum_pct": 85.0,
            "critical_adversarial_errors_allowed": 0,
            "independent_review_complete": False,
            "caption_promotion_gate_passed": False,
            "blockers": [
                "reviewed_fire_minimum_not_met",
                "independent_blinded_review_pending",
                "final_rendered_claim_audit_pending",
            ],
        },
        "review_rubric": {
            "verdict_values": [
                "proved_forcing_tempo_payoff",
                "not_proved",
                "insufficient_stored_horizon",
            ],
            "required_checks": [
                "both stored branches replay legally and completely",
                "physical pieces remain identical across the causal steps",
                "the checking or exchange move actually forces the stated response",
                "the played and better branches differ in the stated outcome",
                "the exact causal sequence has a positive material payoff",
                "no final-position legal capture erases a survival claim",
            ],
            "response_contract": {
                "case_id": "copy from the blinded case",
                "verdict": "one verdict_values entry",
                "critical_false_claim": "boolean",
                "review_note": "short chess reason",
            },
        },
        "cases": public_cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    packet = build_packet()
    encoded = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
