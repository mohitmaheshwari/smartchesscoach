#!/usr/bin/env python3
"""Build a blinded within-game hidden-opportunity ranking packet.

The input is the versioned, anonymized 80-game audit. The builder uses only
stored Stockfish continuations and the canonical exact opportunity composer.
It does not connect to production, run an engine, call a model, or authorize
any player-facing detector.

The public packet intentionally omits centipawn loss, critical flags, proof
family names, mechanism names, quality IDs, formula scores, and detector
membership. Reviewers see the position, both stored branches, and the exact
causal board events needed to judge which moment a coach should stop on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import chess


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.caption_facts import (  # noqa: E402
    HIDDEN_OPPORTUNITY_COMPOSER_VERSION,
    build_verified_hidden_opportunity,
    build_verified_branch_evidence,
)


SCHEMA_VERSION = "hidden_opportunities.moment_ranking_review.v1"
GENERATED_ON = "2026-09-04"
SOURCE_PATH = BACKEND / (
    "data/corpus_snapshots/"
    "full_game_chess_fact_audit_v1_2026-09-03.json"
)
DEFAULT_OUTPUT_PATH = BACKEND / (
    "data/detector_gold/"
    "hidden_opportunities_moment_ranking_review_v1.json"
)


def _hash(value: object, *, namespace: str, length: int = 20) -> str:
    return hashlib.sha256(
        f"{namespace}:{value}".encode("utf-8")
    ).hexdigest()[:length]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def _arguments(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fen_before": decision["fen_before"],
        "played_san": decision["played_san"],
        "best_move_san": decision["best_move_san"],
        "pv_after_played": decision.get("pv_after_played") or [],
        "pv_after_best": decision.get("pv_after_best") or [],
        "cp_loss": decision.get("cp_loss"),
    }


def _candidate_id(group_id: str, decision: Mapping[str, Any]) -> str:
    identity = {
        "group": group_id,
        "ply": decision["ply"],
        "fen": decision["fen_before"],
        "played": decision["played_san"],
        "better": decision["best_move_san"],
    }
    return _hash(
        json.dumps(identity, sort_keys=True, separators=(",", ":")),
        namespace="hidden-opportunity-ranking-candidate",
    )


def _public_step(step: object) -> dict[str, Any]:
    raw = step.contract_dict()
    allowed = (
        "role",
        "branch",
        "ply",
        "fact_kind",
        "actor",
        "move_san",
        "moving_piece",
        "origin",
        "destination",
        "target_piece",
        "target_square",
    )
    return {key: raw[key] for key in allowed if key in raw}


def _public_chain(proof: object) -> list[dict[str, Any]]:
    steps = [proof.setup]
    if hasattr(proof, "constraint"):
        steps.append(proof.constraint)
    else:
        steps.extend(proof.transformation_steps)
    steps.append(proof.payoff)
    return [_public_step(step) for step in steps]


def _public_candidate(
    *,
    group_id: str,
    decision: Mapping[str, Any],
    proof: object,
) -> dict[str, Any]:
    board = chess.Board(decision["fen_before"])
    played_line = [decision["played_san"], *(
        decision.get("pv_after_played") or []
    )]
    better_line = [decision["best_move_san"], *(
        decision.get("pv_after_best") or []
    )]
    return {
        "candidate_id": _candidate_id(group_id, decision),
        "ply": decision["ply"],
        "move_number": decision["move_number"],
        "phase": decision["phase"],
        "position": {
            "fen": decision["fen_before"],
            "side_to_move": "white" if board.turn else "black",
        },
        "played_branch": {
            "move_san": decision["played_san"],
            "line_san": played_line,
        },
        "better_branch": {
            "move_san": decision["best_move_san"],
            "line_san": better_line,
        },
        "causal_chain": _public_chain(proof),
    }


def build_packet() -> dict[str, Any]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    groups = []
    all_candidates = []
    candidate_games = 0
    player_decisions_scanned = 0
    complete_branch_evidence = 0
    positive_edge_decisions = 0
    positive_edge_games = 0

    for game in source["games"]:
        group_id = _hash(
            game["anonymous_game_key"],
            namespace="hidden-opportunity-ranking-group",
        )
        candidates = []
        game_positive_edges = 0
        for decision in game["meaningful_decisions"]:
            player_decisions_scanned += 1
            evidence = build_verified_branch_evidence(**{
                key: value
                for key, value in _arguments(decision).items()
                if key != "cp_loss"
            })
            if evidence is not None:
                complete_branch_evidence += 1
                if evidence.difference.net_material_edge_cp > 0:
                    positive_edge_decisions += 1
                    game_positive_edges += 1
            proof = build_verified_hidden_opportunity(**_arguments(decision))
            if proof is None:
                continue
            public = _public_candidate(
                group_id=group_id,
                decision=decision,
                proof=proof,
            )
            candidates.append(public)
            all_candidates.append(public["candidate_id"])
        if candidates:
            candidate_games += 1
        if game_positive_edges >= 2:
            positive_edge_games += 1
        if len(candidates) < 2:
            continue
        groups.append({
            "review_group_id": group_id,
            "game_context": {
                "rating_band": game["rating_band"],
                "player_color": game["user_color"],
                "result": game["result"],
                "opening": game.get("opening"),
                "moves_san": game["moves_san"],
            },
            "candidates": sorted(candidates, key=lambda row: row["ply"]),
            "reviewer_response": {
                "show_any": None,
                "ranked_candidate_ids": [],
                "rejected_candidate_ids": [],
                "top_choice_reason": None,
                "notes": "",
            },
        })

    groups.sort(key=lambda row: row["review_group_id"])
    comparable_ids = {
        candidate["candidate_id"]
        for group in groups
        for candidate in group["candidates"]
    }
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "source": {
            "path": SOURCE_PATH.relative_to(BACKEND.parent).as_posix(),
            "sha256": _file_sha256(SOURCE_PATH),
        },
        "composer_version": HIDDEN_OPPORTUNITY_COMPOSER_VERSION,
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "blinding": {
            "formula_ids_hidden": True,
            "formula_scores_hidden": True,
            "cp_loss_hidden": True,
            "critical_flags_hidden": True,
            "proof_family_hidden": True,
            "mechanism_name_hidden": True,
        },
        "review_instructions": {
            "task": (
                "Within each game, rank only the moments a coach should stop "
                "on and teach to a 600-1500 player. Reject any moment whose "
                "stored line does not prove the claimed causal chain."
            ),
            "dimensions": [
                "chess_truth",
                "importance_to_this_game",
                "teaching_value",
                "memorability",
                "clarity_within_stored_horizon",
            ],
            "do_not_infer": [
                "durable_player_weakness",
                "mastery",
                "mental_state",
            ],
        },
        "coverage": {
            "games_scanned": len(source["games"]),
            "player_decisions_scanned": player_decisions_scanned,
            "complete_branch_evidence": complete_branch_evidence,
            "positive_material_edge_decisions": positive_edge_decisions,
            "games_with_two_or_more_positive_edges": positive_edge_games,
            "candidate_fires": len(all_candidates),
            "games_with_candidate": candidate_games,
            "comparable_games": len(groups),
            "candidates_in_comparable_games": len(comparable_ids),
        },
        "limitations": [
            (
                "The source packet contains meaningful player decisions only; "
                "it cannot validate opponent-opportunity selection."
            ),
            (
                "The source packet has no stable anonymized player-history "
                "key, so recurrence, novelty, and demonstrated knowledge "
                "cannot yet be compared."
            ),
            (
                "The source packet is an 80-game stratified audit, not a "
                "production-incidence estimate."
            ),
        ],
        "groups": groups,
    }
    encoded_groups = json.dumps(groups).lower()
    for forbidden in ("email", "user_id", "game_id", "username"):
        if forbidden in encoded_groups:
            raise RuntimeError(f"identity field leaked into review: {forbidden}")
    if len(all_candidates) != len(set(all_candidates)):
        raise RuntimeError("candidate IDs are not unique")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    packet = build_packet()
    if not args.summary_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(packet, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(packet["coverage"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
