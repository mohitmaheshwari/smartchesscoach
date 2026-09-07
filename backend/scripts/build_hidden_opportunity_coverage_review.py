#!/usr/bin/env python3
"""Build a blinded false-negative review for hidden opportunities.

The source is the versioned, anonymized 80-game audit.  Every meaningful
decision from a game where the canonical composer found no exact opportunity
is retained.  This lets a reviewer decide whether the game genuinely lacked a
memorable opportunity or whether the exact proof substrate missed one.

The builder runs no engine, model, network request, or database operation.  It
does not define a second opportunity recognizer: candidate membership comes
only from ``build_verified_hidden_opportunity`` and branch facts come only from
``build_verified_branch_evidence``.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
    build_verified_branch_evidence,
    build_verified_hidden_opportunity,
    build_verified_line_cause,
)


SCHEMA_VERSION = "hidden_opportunities.coverage_review.v1"
GENERATED_ON = "2026-09-04"
SOURCE_PATH = BACKEND / (
    "data/corpus_snapshots/"
    "full_game_chess_fact_audit_v1_2026-09-03.json"
)
DEFAULT_OUTPUT_PATH = BACKEND / (
    "data/detector_gold/"
    "hidden_opportunities_coverage_review_v1.json"
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


def _public_event(event: object) -> dict[str, Any]:
    raw = event.contract_dict()
    allowed = (
        "ply",
        "actor",
        "move_san",
        "moving_piece",
        "origin",
        "destination",
        "captured_piece",
        "captured_square",
        "promotion_piece",
        "gave_check",
        "checkmate",
        "stalemate",
        "legal_reply_count",
    )
    return {key: raw[key] for key in allowed}


def _public_branch(trace: object) -> dict[str, Any]:
    return {
        "line_san": list(trace.replayed_san),
        "events": [_public_event(event) for event in trace.events],
    }


def _outcome_shape(evidence: object, initiator: chess.Color) -> str:
    """Describe stored branch topology without claiming a chess mechanism."""
    played = evidence.played_trace
    better = evidence.best_trace
    if (
        better.checkmate
        and better.checkmating_color == initiator
        and played.checkmate
        and played.checkmating_color != initiator
    ):
        return "mate_direction_swing"
    if better.checkmate and better.checkmating_color == initiator:
        return "better_branch_mates"
    if played.checkmate and played.checkmating_color != initiator:
        return "played_branch_gets_mated"

    edge = evidence.difference.net_material_edge_cp
    better_gain = better.net_material_gain_cp
    played_gain = played.net_material_gain_cp
    if edge <= 0:
        return "no_positive_material_difference"
    if better_gain > 0 and played_gain < 0:
        return "wins_material_and_avoids_loss"
    if better_gain > 0:
        return "wins_material"
    if better_gain == 0 and played_gain < 0:
        return "avoids_material_loss"
    if better_gain < 0 and played_gain < better_gain:
        return "reduces_material_loss"
    return "other_positive_material_difference"


def _review_decision(
    *,
    group_id: str,
    decision: Mapping[str, Any],
    evidence: object,
) -> dict[str, Any]:
    board = chess.Board(decision["fen_before"])
    identity = {
        "group": group_id,
        "ply": decision["ply"],
        "fen": decision["fen_before"],
        "played": decision["played_san"],
        "better": decision["best_move_san"],
    }
    decision_id = _hash(
        json.dumps(identity, sort_keys=True, separators=(",", ":")),
        namespace="hidden-opportunity-coverage-decision",
    )
    return {
        "decision_id": decision_id,
        "ply": decision["ply"],
        "move_number": decision["move_number"],
        "phase": decision["phase"],
        "position": {
            "fen": decision["fen_before"],
            "side_to_move": "white" if board.turn else "black",
        },
        "played_branch": _public_branch(evidence.played_trace),
        "better_branch": _public_branch(evidence.best_trace),
        "reviewer_response": {
            "surface_grade": None,
            "idea_family": None,
            "evidence_horizon_sufficient": None,
            "reason": "",
        },
    }


def build_packet() -> dict[str, Any]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    topology = Counter()
    no_candidate_topology = Counter()
    no_candidate_phase = Counter()
    no_candidate_rating_band = Counter()
    existing_line_causes = Counter()
    no_candidate_line_causes = Counter()
    no_exact_cause_topology = Counter()
    no_exact_cause_phase = Counter()
    no_exact_cause_rating_band = Counter()
    groups = []
    complete_branch_evidence = 0
    candidate_fires = 0
    candidate_games = 0
    positive_edge_games = 0
    no_candidate_games_with_positive_edge = 0
    games_with_existing_line_cause = 0
    no_candidate_games_with_existing_line_cause = 0
    games_without_opportunity_or_line_cause = 0
    decisions_without_opportunity_or_line_cause = 0
    all_decision_ids = []

    for game in source["games"]:
        group_id = _hash(
            game["anonymous_game_key"],
            namespace="hidden-opportunity-coverage-group",
        )
        game_rows = []
        game_has_candidate = False
        game_has_positive_edge = False
        game_has_line_cause = False
        decision_records = []
        for decision in game["meaningful_decisions"]:
            arguments = _arguments(decision)
            evidence = build_verified_branch_evidence(**{
                key: value
                for key, value in arguments.items()
                if key != "cp_loss"
            })
            if evidence is None:
                topology["incomplete_or_invalid_branch_evidence"] += 1
                decision_records.append((decision, None, None, None))
                continue
            complete_branch_evidence += 1
            shape = _outcome_shape(
                evidence,
                chess.Board(decision["fen_before"]).turn,
            )
            topology[shape] += 1
            if evidence.difference.net_material_edge_cp > 0:
                game_has_positive_edge = True
            proof = build_verified_hidden_opportunity(**arguments)
            if proof is not None:
                candidate_fires += 1
                game_has_candidate = True
            line_cause = build_verified_line_cause(
                **arguments,
                include_branch_evidence=False,
            )
            if line_cause is not None:
                existing_line_causes[line_cause.lesson_kind] += 1
                game_has_line_cause = True
            decision_records.append((decision, evidence, proof, line_cause))

        if game_has_positive_edge:
            positive_edge_games += 1
        if game_has_line_cause:
            games_with_existing_line_cause += 1
        if game_has_candidate:
            candidate_games += 1
            continue

        if game_has_positive_edge:
            no_candidate_games_with_positive_edge += 1
        if game_has_line_cause:
            no_candidate_games_with_existing_line_cause += 1
        else:
            games_without_opportunity_or_line_cause += 1
        for decision, evidence, proof, line_cause in decision_records:
            if evidence is None:
                no_candidate_topology[
                    "incomplete_or_invalid_branch_evidence"
                ] += 1
                continue
            if proof is not None:
                raise RuntimeError("candidate leaked into a no-candidate game")
            if line_cause is not None:
                no_candidate_line_causes[line_cause.lesson_kind] += 1
            shape = _outcome_shape(
                evidence,
                chess.Board(decision["fen_before"]).turn,
            )
            no_candidate_topology[shape] += 1
            no_candidate_phase[str(decision["phase"])] += 1
            no_candidate_rating_band[str(game["rating_band"])] += 1
            if not game_has_line_cause:
                decisions_without_opportunity_or_line_cause += 1
                no_exact_cause_topology[shape] += 1
                no_exact_cause_phase[str(decision["phase"])] += 1
                no_exact_cause_rating_band[str(game["rating_band"])] += 1
            public = _review_decision(
                group_id=group_id,
                decision=decision,
                evidence=evidence,
            )
            game_rows.append(public)
            all_decision_ids.append(public["decision_id"])

        groups.append({
            "review_group_id": group_id,
            "game_context": {
                "rating_band": game["rating_band"],
                "player_color": game["user_color"],
                "result": game["result"],
                "opening": game.get("opening"),
                "moves_san": game["moves_san"],
            },
            "decisions": sorted(game_rows, key=lambda row: row["ply"]),
            "reviewer_response": {
                "game_has_hidden_opportunity": None,
                "best_decision_ids": [],
                "rejected_decision_ids": [],
                "notes": "",
            },
        })

    groups.sort(key=lambda row: row["review_group_id"])
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
            "cp_loss_hidden": True,
            "critical_flags_hidden": True,
            "stored_labels_hidden": True,
            "existing_captions_hidden": True,
            "proof_family_hidden": True,
            "mechanism_name_hidden": True,
            "composer_rejection_reason_hidden": True,
        },
        "review_instructions": {
            "task": (
                "Review every meaningful decision in each no-candidate game. "
                "Decide whether the stored branches prove a memorable missed "
                "opportunity, support only a narrower factual caption, or are "
                "insufficient to teach beyond the played game."
            ),
            "surface_grades": [
                "hidden_opportunity",
                "caption_only",
                "evidence_insufficient",
            ],
            "required_checks": [
                "legal branch replay",
                "actor and move direction",
                "capture and recapture accounting",
                "setup-to-payoff causality",
                "whether the payoff survives the stored horizon",
                "teaching value for a 600-1500 player",
            ],
            "do_not_infer": [
                "moves beyond the stored continuation",
                "durable player weakness",
                "mastery",
                "mental state",
            ],
        },
        "coverage": {
            "games_scanned": len(source["games"]),
            "meaningful_decisions_scanned": sum(
                len(game["meaningful_decisions"])
                for game in source["games"]
            ),
            "complete_branch_evidence": complete_branch_evidence,
            "candidate_fires": candidate_fires,
            "games_with_candidate": candidate_games,
            "games_without_candidate": len(groups),
            "decisions_in_no_candidate_games": len(all_decision_ids),
            "games_with_positive_material_edge": positive_edge_games,
            "no_candidate_games_with_positive_material_edge": (
                no_candidate_games_with_positive_edge
            ),
            "games_with_existing_verified_line_cause": (
                games_with_existing_line_cause
            ),
            "no_candidate_games_with_existing_verified_line_cause": (
                no_candidate_games_with_existing_line_cause
            ),
            "games_without_opportunity_or_verified_line_cause": (
                games_without_opportunity_or_line_cause
            ),
            "decisions_without_opportunity_or_verified_line_cause": (
                decisions_without_opportunity_or_line_cause
            ),
        },
        "evidence_topology": {
            "all_meaningful_decisions": dict(sorted(topology.items())),
            "no_candidate_games": dict(
                sorted(no_candidate_topology.items())
            ),
            "no_candidate_decisions_by_phase": dict(
                sorted(no_candidate_phase.items())
            ),
            "no_candidate_decisions_by_rating_band": dict(
                sorted(no_candidate_rating_band.items())
            ),
            "existing_verified_line_causes": dict(
                sorted(existing_line_causes.items())
            ),
            "existing_verified_line_causes_in_no_candidate_games": dict(
                sorted(no_candidate_line_causes.items())
            ),
            "games_without_either_exact_cause": dict(
                sorted(no_exact_cause_topology.items())
            ),
            "games_without_either_exact_cause_by_phase": dict(
                sorted(no_exact_cause_phase.items())
            ),
            "games_without_either_exact_cause_by_rating_band": dict(
                sorted(no_exact_cause_rating_band.items())
            ),
        },
        "interpretation_limits": [
            (
                "Game incidence is not detector recall. Only frozen reviewer "
                "labels on this packet can establish false negatives."
            ),
            (
                "A positive branch material difference is a topology fact, "
                "not proof of a memorable tactic or teachable causal chain."
            ),
            (
                "A non-positive material difference may still contain mate, "
                "opening, endgame, defensive, or positional teaching value."
            ),
            (
                "The source contains player decisions only and cannot measure "
                "opponent-side opportunity coverage."
            ),
            (
                "Absence of both exact cause types is not proof that Game "
                "Review is silent; narrower verified captions and canonical "
                "opening or principle evidence are separate existing paths."
            ),
        ],
        "answer_key_status": "not_created_until_review_is_frozen",
        "groups": groups,
    }

    encoded_groups = json.dumps(groups).lower()
    for forbidden in (
        "email",
        "user_id",
        "game_id",
        "username",
        "cp_loss",
        "quality_id",
        "proof_version",
        "mechanism",
        "cognitive_gap",
        "current_review",
    ):
        if forbidden in encoded_groups:
            raise RuntimeError(
                f"private or answer-bearing field leaked: {forbidden}"
            )
    if len(all_decision_ids) != len(set(all_decision_ids)):
        raise RuntimeError("review decision IDs are not unique")
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
    print(json.dumps({
        "coverage": packet["coverage"],
        "evidence_topology": packet["evidence_topology"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
