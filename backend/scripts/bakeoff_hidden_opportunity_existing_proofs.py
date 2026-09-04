#!/usr/bin/env python3
"""Measure existing exact proof owners on the locked opportunity packet.

This is a read-only architecture bake-off. A verified proof outside an
Opportunity-labelled row is recorded as ``outside_opportunity`` rather than a
false positive: the underlying motif may be true while still being incidental,
shared by both branches, or not the most teachable fact.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import chess


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.aligned_tactic_puzzle_proof import (  # noqa: E402
    build_aligned_tactic_proof,
)
from services.back_rank_mate_puzzle_proof import (  # noqa: E402
    build_back_rank_mate_proof,
)
from services.discovered_attack_puzzle_proof import (  # noqa: E402
    build_discovered_attack_proof,
)
from services.forced_mate_puzzle_proof import (  # noqa: E402
    build_forced_mate_proof,
)
from services.caption_facts import (  # noqa: E402
    build_target_line_opportunity_proof,
    build_verified_branch_evidence,
)
from services.fork_puzzle_proof import build_fork_proof  # noqa: E402
from services.free_piece_puzzle_proof import (  # noqa: E402
    build_free_piece_proof,
)
from services.removal_defender_puzzle_proof import (  # noqa: E402
    build_removal_defender_proof,
)
from services.trapped_piece_puzzle_proof import (  # noqa: E402
    build_trapped_piece_proof,
)


PACKET = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_v1_2026-09-02.json"
)
ANNOTATIONS = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_annotations_v1_2026-09-03.json"
)
FAMILY_LOCK = BACKEND / (
    "data/corpus_snapshots/"
    "hidden_opportunities_phase3a_proof_family_lock_v1_2026-09-03.json"
)


def _verified(bundle: object) -> bool:
    return bool(bundle and getattr(bundle, "verifier", None).verified)


def main() -> int:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    annotation_packet = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    lock = json.loads(FAMILY_LOCK.read_text(encoding="utf-8"))
    annotations = {
        row["position_id"]: row
        for row in annotation_packet["annotations"]
    }
    first_family = set(lock["proof_family_order"][0]["position_ids"])
    builders = {
        "free_piece": lambda board, row: build_free_piece_proof(
            board,
            row["played_move"]["uci"],
            row["best_move"]["uci"],
            row["cp_loss"],
        ),
        "fork": lambda board, row: build_fork_proof(
            board,
            row["played_move"]["uci"],
            row["best_move"]["uci"],
            row["stored_four_ply"]["after_best"],
            row["cp_loss"],
        ),
        "aligned": lambda board, row: build_aligned_tactic_proof(
            board,
            row["played_move"]["uci"],
            row["best_move"]["uci"],
            row["stored_four_ply"]["after_best"],
            row["cp_loss"],
        ),
        "discovered_attack": lambda board, row: (
            build_discovered_attack_proof(
                board,
                row["played_move"]["uci"],
                row["best_move"]["uci"],
                row["stored_four_ply"]["after_best"],
                row["cp_loss"],
            )
        ),
        "removal_of_defender": lambda board, row: (
            build_removal_defender_proof(
                board,
                row["played_move"]["uci"],
                row["best_move"]["uci"],
                row["stored_four_ply"]["after_best"],
                row["cp_loss"],
            )
        ),
        "trapped_piece": lambda board, row: build_trapped_piece_proof(
            board,
            row["played_move"]["uci"],
            row["best_move"]["uci"],
            row["cp_loss"],
        ),
        "forced_mate": lambda board, row: build_forced_mate_proof(
            board,
            row["best_move"]["uci"],
            row["stored_four_ply"]["after_best"],
            row["cp_loss"],
        ),
        "back_rank_mate": lambda board, row: build_back_rank_mate_proof(
            board,
            row["played_move"]["uci"],
            row["best_move"]["uci"],
            row["cp_loss"],
        ),
    }
    results = {
        name: {
            "verified": [],
            "opportunity": [],
            "first_family": [],
            "outside_opportunity": [],
        }
        for name in builders
    }
    failures = []
    covered_opportunities = set()
    covered_first_family = set()
    first_family_rows = []
    causal_rows = []

    for row in packet["positions"]:
        position_id = row["position_id"]
        gold = annotations[position_id]
        row_proofs = []
        for name, builder in builders.items():
            try:
                bundle = builder(chess.Board(row["fen"]), row)
            except Exception as exc:  # measurement must expose crashes
                failures.append(f"{position_id}:{name}:{type(exc).__name__}")
                continue
            if not _verified(bundle):
                continue
            item = {
                "position_id": position_id,
                "surface_grade": gold["surface_grade"],
                "idea_family": gold["idea_family"],
                "quality_id": bundle.quality_id,
                "concept_id": bundle.verifier.concept_id,
            }
            results[name]["verified"].append(item)
            row_proofs.append(name)
            if gold["surface_grade"] == "hidden_opportunity":
                results[name]["opportunity"].append(position_id)
                covered_opportunities.add(position_id)
            else:
                results[name]["outside_opportunity"].append(position_id)
            if position_id in first_family:
                results[name]["first_family"].append(position_id)
                covered_first_family.add(position_id)

        try:
            causal = build_target_line_opportunity_proof(
                fen_before=row["fen"],
                played_san=row["played_move"]["san"],
                best_move_san=row["best_move"]["san"],
                pv_after_played=tuple(
                    row["stored_four_ply"]["after_played"]
                ),
                pv_after_best=tuple(
                    row["stored_four_ply"]["after_best"]
                ),
                cp_loss=row["cp_loss"],
            )
        except Exception as exc:
            failures.append(
                f"{position_id}:target_line_causal:{type(exc).__name__}"
            )
            causal = None
        if causal is not None:
            causal_rows.append({
                "position_id": position_id,
                "surface_grade": gold["surface_grade"],
                "idea_family": gold["idea_family"],
                "in_first_family": position_id in first_family,
                "mechanism": causal.mechanism,
                "setup": causal.setup.fact_kind,
                "constraint": causal.constraint.fact_kind,
                "payoff": causal.payoff.fact_kind,
                "payoff_ply": causal.payoff.ply,
                "payoff_piece": causal.payoff.moving_piece,
                "target_piece": causal.payoff.target_piece,
                "target_square": causal.payoff.target_square,
                "target_value_cp": causal.payoff.target_value_cp,
                "net_material_edge_cp": (
                    causal.branch_evidence.difference.net_material_edge_cp
                ),
                "supporting_quality_ids": list(
                    causal.supporting_quality_ids
                ),
            })

        if position_id in first_family:
            evidence = build_verified_branch_evidence(
                fen_before=row["fen"],
                played_san=row["played_move"]["san"],
                best_move_san=row["best_move"]["san"],
                pv_after_played=tuple(
                    row["stored_four_ply"]["after_played"]
                ),
                pv_after_best=tuple(
                    row["stored_four_ply"]["after_best"]
                ),
            )
            if evidence is None:
                failures.append(f"{position_id}:branch_evidence:missing")
            else:
                first_family_rows.append({
                    "position_id": position_id,
                    "idea_family": gold["idea_family"],
                    "played_move": row["played_move"]["san"],
                    "best_move": row["best_move"]["san"],
                    "played_line": list(
                        evidence.played_trace.replayed_san
                    ),
                    "best_line": list(evidence.best_trace.replayed_san),
                    "net_material_edge_cp": (
                        evidence.difference.net_material_edge_cp
                    ),
                    "played_only_captures": [
                        item.contract_dict()
                        for item in evidence.difference.played_only_captures
                    ],
                    "best_only_captures": [
                        item.contract_dict()
                        for item in evidence.difference.best_only_captures
                    ],
                    "best_check_plies": list(
                        evidence.difference.best_check_plies
                    ),
                    "best_single_reply_plies": list(
                        evidence.difference.best_single_reply_plies
                    ),
                    "verified_existing_proofs": sorted(row_proofs),
                })

    summary = {
        name: {
            "verified": len(values["verified"]),
            "opportunity": len(values["opportunity"]),
            "first_family": len(values["first_family"]),
            "outside_opportunity": len(values["outside_opportunity"]),
            "opportunity_ids": values["opportunity"],
            "first_family_ids": values["first_family"],
            "outside_opportunity_ids": values["outside_opportunity"],
        }
        for name, values in results.items()
    }
    report = {
        "schema_version": "hidden_opportunity_existing_proof_bakeoff.v1",
        "positions": len(packet["positions"]),
        "gold_opportunities": 24,
        "first_family_gold": len(first_family),
        "covered_opportunities": len(covered_opportunities),
        "covered_opportunity_ids": sorted(covered_opportunities),
        "covered_first_family": len(covered_first_family),
        "covered_first_family_ids": sorted(covered_first_family),
        "first_family_rows": first_family_rows,
        "target_line_causal": {
            "verified": len(causal_rows),
            "hidden_opportunity": sum(
                row["surface_grade"] == "hidden_opportunity"
                for row in causal_rows
            ),
            "first_family": sum(
                row["in_first_family"] for row in causal_rows
            ),
            "outside_hidden_opportunity": sum(
                row["surface_grade"] != "hidden_opportunity"
                for row in causal_rows
            ),
            "rows": causal_rows,
        },
        "proofs": summary,
        "failures": failures,
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "passed": not failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
