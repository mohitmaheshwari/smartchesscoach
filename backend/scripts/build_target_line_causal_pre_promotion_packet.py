"""Build the offline, blinded target/line pre-promotion review packet.

This script reads only versioned anonymized evidence.  It never connects to a
database, runs an engine, calls an LLM, or writes outside an explicit output
path.  The public review cases intentionally omit detector labels, proof
objects, centipawn values, stored classifications, and source names.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from services.caption_facts import (
    TARGET_LINE_CAUSAL_PROOF_VERSION,
    TARGET_LINE_CAUSAL_QUALITY_ID,
    build_target_line_opportunity_proof,
    build_verified_branch_evidence,
)


SCHEMA_VERSION = "target_line_causal.pre_promotion_review.v3"
ANSWER_KEY_SCHEMA_VERSION = "target_line_causal.pre_promotion_answer_key.v3"
FROZEN_PROOF_VERSION = "target_line_causal_proof.v4"
FRESH_SCHEMA_VERSION = "target_line_causal.pre_promotion_review.v4"
FRESH_ANSWER_KEY_SCHEMA_VERSION = (
    "target_line_causal.pre_promotion_answer_key.v4"
)
FRESH_PROOF_VERSION = "target_line_causal_proof.v6"
GENERATED_ON = "2026-09-04"
CAPTION_FIRE_MINIMUM = 50
CONTROL_TARGET = 30
FULL_CONTROL_TARGET = 23
PRIOR_CONTROL_TARGET = 7
MAX_FULL_CONTROLS_PER_SOURCE_UNIT = 2

FULL_AUDIT_PATH = BACKEND_ROOT / (
    "data/corpus_snapshots/full_game_chess_fact_audit_v1_2026-09-03.json"
)
PRIOR_PACKET_PATH = BACKEND_ROOT / (
    "data/detector_gold/verified_single_game_cause_promotion_v1.json"
)
ARCHITECTURE_GOLD_PATH = BACKEND_ROOT / (
    "data/corpus_snapshots/hidden_opportunities_chess_gold_v1_2026-09-02.json"
)
POPULATION_PATH = BACKEND_ROOT / (
    "data/corpus_snapshots/"
    "target_line_population_export_v1_2026-09-04.json"
)
FRESH_POPULATION_PATH = BACKEND_ROOT / (
    "data/corpus_snapshots/"
    "target_line_population_export_v2_2026-09-04.json"
)
DEFAULT_OUTPUT_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_review_v3.json"
)
DEFAULT_ANSWER_KEY_OUTPUT_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_answer_key_v3.json"
)
DEFAULT_INDEPENDENT_REVIEW_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_independent_review_v3.json"
)
FRESH_OUTPUT_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_review_v4.json"
)
FRESH_ANSWER_KEY_OUTPUT_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_answer_key_v4.json"
)
FRESH_INDEPENDENT_REVIEW_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_independent_review_v4.json"
)


def _hash(value: object, *, namespace: str, length: int = 20) -> str:
    return hashlib.sha256(
        f"{namespace}:{value}".encode("utf-8")
    ).hexdigest()[:length]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _position_signature(row: Mapping[str, Any]) -> str:
    payload = {
        "fen_before": row["fen_before"],
        "played_san": row["played_san"],
        "best_move_san": row["best_move_san"],
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _case_id(row: Mapping[str, Any]) -> str:
    payload = {
        "source_unit_key": row["source_unit_key"],
        "ply": row.get("ply"),
        "fen_before": row["fen_before"],
        "played_san": row["played_san"],
        "best_move_san": row["best_move_san"],
        "pv_after_played": row["pv_after_played"],
        "pv_after_best": row["pv_after_best"],
    }
    return _hash(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        namespace="target-line-pre-promotion-case",
    )


def _normalize_full_cases() -> Iterable[dict[str, Any]]:
    packet = json.loads(FULL_AUDIT_PATH.read_text(encoding="utf-8"))
    for game in packet["games"]:
        source_unit_key = _hash(
            game["anonymous_game_key"],
            namespace="target-line-source-unit",
        )
        for decision in game["meaningful_decisions"]:
            yield {
                "source_kind": "full_game_audit_80",
                "source_unit_key": source_unit_key,
                "ply": decision.get("ply"),
                "rating_band": game.get("rating_band"),
                "phase": decision.get("phase"),
                "fen_before": decision["fen_before"],
                "played_san": decision["played_san"],
                "best_move_san": decision["best_move_san"],
                "pv_after_played": list(
                    decision.get("pv_after_played") or []
                ),
                "pv_after_best": list(
                    decision.get("pv_after_best") or []
                ),
                "cp_loss": decision.get("cp_loss"),
            }


def _normalize_prior_cases() -> Iterable[dict[str, Any]]:
    packet = json.loads(PRIOR_PACKET_PATH.read_text(encoding="utf-8"))
    for collection_name in ("fires", "negatives"):
        for case in packet[collection_name]:
            yield {
                "source_kind": "prior_cause_packet_100",
                "source_unit_key": _hash(
                    case["game_key"],
                    namespace="target-line-source-unit",
                ),
                "ply": case.get("ply"),
                "rating_band": None,
                "phase": None,
                "fen_before": case["fen_before"],
                "played_san": case["move_san"],
                "best_move_san": case["best_move_san"],
                "pv_after_played": list(
                    case.get("pv_after_played") or []
                ),
                "pv_after_best": list(
                    case.get("pv_after_best") or []
                ),
                "cp_loss": case.get("cp_loss"),
            }


def _normalize_population_cases(
    path: Path = POPULATION_PATH,
    *,
    source_kind: str = "population_export_1500",
) -> Iterable[dict[str, Any]]:
    packet = json.loads(path.read_text(encoding="utf-8"))
    for position in packet["positions"]:
        signature = _position_signature(position)
        yield {
            "source_kind": source_kind,
            "source_unit_key": _hash(
                signature,
                namespace="target-line-source-unit",
            ),
            "ply": None,
            "rating_band": position["rating_band"],
            "phase": position["phase"],
            "fen_before": position["fen_before"],
            "played_san": position["played_san"],
            "best_move_san": position["best_move_san"],
            "pv_after_played": list(position["pv_after_played"]),
            "pv_after_best": list(position["pv_after_best"]),
            "cp_loss": position["cp_loss"],
        }


def _architecture_signatures() -> set[str]:
    packet = json.loads(
        ARCHITECTURE_GOLD_PATH.read_text(encoding="utf-8")
    )
    return {
        _position_signature({
            "fen_before": row["fen"],
            "played_san": row["played_move"]["san"],
            "best_move_san": row["best_move"]["san"],
        })
        for row in packet["positions"]
    }


def _proof(row: Mapping[str, Any]):
    return build_target_line_opportunity_proof(
        fen_before=row["fen_before"],
        played_san=row["played_san"],
        best_move_san=row["best_move_san"],
        pv_after_played=row["pv_after_played"],
        pv_after_best=row["pv_after_best"],
        cp_loss=row.get("cp_loss"),
    )


def _evidence(row: Mapping[str, Any]):
    return build_verified_branch_evidence(
        fen_before=row["fen_before"],
        played_san=row["played_san"],
        best_move_san=row["best_move_san"],
        pv_after_played=row["pv_after_played"],
        pv_after_best=row["pv_after_best"],
    )


def _stable_order(row: Mapping[str, Any], *, namespace: str) -> str:
    return _hash(_case_id(row), namespace=namespace, length=64)


def _select_full_controls(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cover every observed rating-band/phase stratum, then hash-fill."""
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(row["rating_band"], row["phase"])].append(row)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    per_source: Counter[str] = Counter()

    def add_first(candidates: Iterable[dict[str, Any]]) -> bool:
        ordered = sorted(
            candidates,
            key=lambda item: _stable_order(
                item, namespace="target-line-control-order"
            ),
        )
        for row in ordered:
            case_id = _case_id(row)
            if case_id in selected_ids:
                continue
            if (
                per_source[row["source_unit_key"]]
                >= MAX_FULL_CONTROLS_PER_SOURCE_UNIT
            ):
                continue
            selected.append(row)
            selected_ids.add(case_id)
            per_source[row["source_unit_key"]] += 1
            return True
        return False

    for stratum in sorted(strata):
        if not add_first(strata[stratum]):
            raise RuntimeError(f"unable to cover control stratum {stratum}")
    for row in sorted(
        rows,
        key=lambda item: _stable_order(
            item, namespace="target-line-control-order"
        ),
    ):
        if len(selected) >= FULL_CONTROL_TARGET:
            break
        add_first((row,))
    if len(selected) != FULL_CONTROL_TARGET:
        raise RuntimeError("full-audit control target was not met")
    return selected


def _select_prior_controls(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    for row in sorted(
        rows,
        key=lambda item: _stable_order(
            item, namespace="target-line-prior-control-order"
        ),
    ):
        if row["source_unit_key"] in used_sources:
            continue
        selected.append(row)
        used_sources.add(row["source_unit_key"])
        if len(selected) == PRIOR_CONTROL_TARGET:
            break
    if len(selected) != PRIOR_CONTROL_TARGET:
        raise RuntimeError("prior-packet control target was not met")
    return selected


def _select_population_controls(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cover all 12 rating-band/phase cells, then hash-fill to 30."""
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(row["rating_band"], row["phase"])].append(row)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_sources: set[str] = set()

    def add_first(candidates: Iterable[dict[str, Any]]) -> bool:
        for row in sorted(
            candidates,
            key=lambda item: _stable_order(
                item, namespace="target-line-population-control-order"
            ),
        ):
            case_id = _case_id(row)
            if (
                case_id in selected_ids
                or row["source_unit_key"] in selected_sources
            ):
                continue
            selected.append(row)
            selected_ids.add(case_id)
            selected_sources.add(row["source_unit_key"])
            return True
        return False

    expected_strata = {
        (band, phase)
        for band in ("600-899", "900-1199", "1200-1499", "1500-1999")
        for phase in ("opening", "middlegame", "endgame")
    }
    if set(strata) != expected_strata:
        missing = sorted(expected_strata - set(strata))
        raise RuntimeError(f"missing population control strata: {missing}")
    for stratum in sorted(strata):
        if not add_first(strata[stratum]):
            raise RuntimeError(f"unable to cover control stratum {stratum}")
    for row in sorted(
        rows,
        key=lambda item: _stable_order(
            item, namespace="target-line-population-control-order"
        ),
    ):
        if len(selected) >= CONTROL_TARGET:
            break
        add_first((row,))
    if len(selected) != CONTROL_TARGET:
        raise RuntimeError("population control target was not met")
    return selected


def _public_review_case(row: Mapping[str, Any]) -> dict[str, Any]:
    board = chess.Board(row["fen_before"])
    return {
        "case_id": _case_id(row),
        "review_group": row["source_unit_key"],
        "position": {
            "fen": row["fen_before"],
            "side_to_move": "white" if board.turn else "black",
        },
        "played_branch": {
            "move_san": row["played_san"],
            "stored_continuation_san": row["pv_after_played"],
        },
        "better_branch": {
            "move_san": row["best_move_san"],
            "stored_continuation_san": row["pv_after_best"],
        },
    }


def _source_record(path: Path, *, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(BACKEND_ROOT.parent).as_posix(),
        "sha256": _file_sha256(path),
        "role": role,
    }


def _assert_frozen_builder_version() -> None:
    if TARGET_LINE_CAUSAL_PROOF_VERSION != FROZEN_PROOF_VERSION:
        raise RuntimeError(
            "the v3 packet is frozen against target_line_causal_proof.v4; "
            "do not regenerate it with a newer detector"
        )


def _assert_fresh_builder_version() -> None:
    if TARGET_LINE_CAUSAL_PROOF_VERSION != FRESH_PROOF_VERSION:
        raise RuntimeError(
            "the v4 packet is frozen against target_line_causal_proof.v6; "
            "do not regenerate it with a newer detector"
        )


def build_packet(
    *,
    with_membership: bool = False,
    generation: str = "v3",
) -> Any:
    if generation == "v3":
        _assert_frozen_builder_version()
        schema_version = SCHEMA_VERSION
        architecture_signatures = _architecture_signatures()
        all_rows = (
            list(_normalize_full_cases())
            + list(_normalize_prior_cases())
            + list(_normalize_population_cases())
        )
        control_source_kind = "population_export_1500"
        sources = [
            _source_record(
                FULL_AUDIT_PATH, role="independent_full_game_population"
            ),
            _source_record(
                PRIOR_PACKET_PATH, role="independent_stored_line_population"
            ),
            _source_record(
                POPULATION_PATH,
                role="independent_population_expansion_1500",
            ),
            _source_record(
                ARCHITECTURE_GOLD_PATH,
                role="development_overlap_exclusion_only",
            ),
        ]
        candidate_policy = (
            "all independent post-horizon-guard detector fires"
        )
        control_policy = (
            "30 complete two-branch positive-edge no-fires from the "
            "1,500-position population; every rating-band/phase stratum "
            "covered and exactly one control per source unit"
        )
    elif generation == "v4":
        _assert_fresh_builder_version()
        schema_version = FRESH_SCHEMA_VERSION
        architecture_signatures = set()
        control_source_kind = "population_export_v2_1500"
        all_rows = list(_normalize_population_cases(
            FRESH_POPULATION_PATH,
            source_kind=control_source_kind,
        ))
        sources = [
            _source_record(
                FRESH_POPULATION_PATH,
                role=(
                    "fresh_detector_blind_population_1500_with_2164_"
                    "prior_content_signatures_excluded"
                ),
            ),
        ]
        candidate_policy = (
            "all fresh target_line_causal_proof.v6 fires; no subsampling"
        )
        control_policy = (
            "30 fresh complete two-branch positive-edge v6 no-fires; "
            "every rating-band/phase stratum covered and exactly one "
            "control per source unit"
        )
    else:
        raise ValueError("generation must be v3 or v4")

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

    fires.sort(
        key=lambda item: _stable_order(
            item, namespace="target-line-fire-order"
        )
    )
    controls = _select_population_controls(
        controls_by_source[control_source_kind]
    )
    public_cases = [_public_review_case(row) for row in fires + controls]
    public_cases.sort(
        key=lambda item: _hash(
            item["case_id"],
            namespace="target-line-blinded-review-order",
            length=64,
        )
    )
    case_ids = [case["case_id"] for case in public_cases]
    fire_shortfall = max(0, CAPTION_FIRE_MINIMUM - len(fires))
    population_control_strata = Counter(
        f"{row['rating_band']}:{row['phase']}"
        for row in controls
    )
    blockers = [
        "independent_blinded_review_pending",
        "final_rendered_claim_audit_pending",
    ]
    if fire_shortfall:
        blockers.insert(0, "reviewed_fire_minimum_not_met")

    packet = {
        "schema_version": schema_version,
        "generated_on": GENERATED_ON,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "quality_id": TARGET_LINE_CAUSAL_QUALITY_ID,
        "proof_version": TARGET_LINE_CAUSAL_PROOF_VERSION,
        "status": "pre_promotion_blocked",
        "sources": sources,
        "claim_under_review": (
            "The two complete stored continuations prove a positive "
            "setup-to-constraint-to-material-payoff target/line chain."
        ),
        "selection": {
            "candidate_policy": (
                candidate_policy
            ),
            "control_policy": (
                control_policy
            ),
            "candidate_target": "all_available",
            "control_target": CONTROL_TARGET,
            "population_controls": CONTROL_TARGET,
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
            "population_control_strata": dict(
                sorted(population_control_strata.items())
            ),
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
            "blockers": blockers,
        },
        "review_rubric": {
            "verdict_values": [
                "proved_target_line_payoff",
                "not_proved",
                "insufficient_stored_horizon",
            ],
            "required_checks": [
                "both stored branches replay legally and completely",
                "the same physical setup piece and target are followed",
                "the claimed target/line relation distinguishes the branches",
                "the exact causal sequence has a positive material payoff",
                "no recapture or final-position horizon leak erases the payoff",
                "legal quiet checks after the stored horizon are tested before "
                "accepting a material payoff",
                "no named motif is inferred without its canonical proof",
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
    if with_membership:
        return packet, {
            "candidate_case_ids": sorted(_case_id(row) for row in fires),
            "control_case_ids": sorted(_case_id(row) for row in controls),
        }
    return packet


def build_answer_key(
    *,
    packet_path: Path = DEFAULT_OUTPUT_PATH,
    review_path: Path = DEFAULT_INDEPENDENT_REVIEW_PATH,
    generation: str = "v3",
) -> dict[str, Any]:
    packet_path = packet_path.resolve()
    review_path = review_path.resolve()
    packet, membership = build_packet(
        with_membership=True,
        generation=generation,
    )
    if json.loads(packet_path.read_text(encoding="utf-8")) != packet:
        raise ValueError("frozen packet does not match deterministic builder")
    packet_sha256 = _file_sha256(packet_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("frozen") is not True:
        raise ValueError("independent review is not frozen")
    if review.get("packet_sha256") != packet_sha256:
        raise ValueError("independent review is not bound to frozen packet")
    response_ids = [
        response.get("case_id") for response in review.get("responses", [])
    ]
    packet_ids = {case["case_id"] for case in packet["cases"]}
    if (
        len(response_ids) != len(packet_ids)
        or len(set(response_ids)) != len(response_ids)
        or set(response_ids) != packet_ids
    ):
        raise ValueError("independent review does not cover packet exactly")
    return {
        "schema_version": (
            FRESH_ANSWER_KEY_SCHEMA_VERSION
            if generation == "v4"
            else ANSWER_KEY_SCHEMA_VERSION
        ),
        "generated_on": GENERATED_ON,
        "created_after_blinded_review_was_frozen": True,
        "source_packet": {
            "path": packet_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": packet_sha256,
        },
        "source_review": {
            "path": review_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": _file_sha256(review_path),
        },
        "proof_version": TARGET_LINE_CAUSAL_PROOF_VERSION,
        **membership,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--answer-key-output", type=Path)
    parser.add_argument(
        "--generation",
        choices=("v3", "v4"),
        default="v3",
    )
    args = parser.parse_args()
    packet = build_packet(generation=args.generation)
    encoded = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if args.answer_key_output:
        if not args.output:
            raise ValueError("--answer-key-output requires --output")
        review_path = (
            FRESH_INDEPENDENT_REVIEW_PATH
            if args.generation == "v4"
            else DEFAULT_INDEPENDENT_REVIEW_PATH
        )
        answer_key = build_answer_key(
            packet_path=args.output,
            review_path=review_path,
            generation=args.generation,
        )
        args.answer_key_output.parent.mkdir(parents=True, exist_ok=True)
        args.answer_key_output.write_text(
            json.dumps(answer_key, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
