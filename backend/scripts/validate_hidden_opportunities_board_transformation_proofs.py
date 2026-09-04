#!/usr/bin/env python3
"""Independently validate Phase 3A.2 board-transformation proofs.

The runtime proof is exercised, while this script independently replays both
stored branches, checks every retained intermediate move and persistent piece
identity, and resolves any legal capture exchange beyond the stored horizon.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

import chess


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from scripts.validate_hidden_opportunities_forcing_tempo_proofs import (  # noqa: E402
    _validate_step,
)
from scripts.validate_hidden_opportunities_target_line_proofs import (  # noqa: E402
    _oracle_legal_exchange_gain,
    _oracle_replay,
    _wilson_lower_bound,
)
from services.caption_facts import (  # noqa: E402
    BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION,
    BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID,
    build_board_transformation_opportunity_proof,
    build_endgame_geometry_opportunity_proof,
    build_forcing_tempo_opportunity_proof,
    build_target_line_opportunity_proof,
)
from services.detector_quality import (  # noqa: E402
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
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


def _arguments(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fen_before": row["fen"],
        "played_san": row["played_move"]["san"],
        "best_move_san": row["best_move"]["san"],
        "pv_after_played": tuple(row["stored_four_ply"]["after_played"]),
        "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
        "cp_loss": row["cp_loss"],
    }


def _proof_for(row: dict[str, Any]):
    return build_board_transformation_opportunity_proof(**_arguments(row))


def _horizon_adjusted_gain(
    events: list[dict[str, Any]],
    stored_gain_cp: int,
    payoff: Any,
) -> int:
    board = chess.Board(events[-1]["fen_after"])
    last_move = next(
        event
        for event in reversed(events)
        if event["moving_piece_id"] == payoff.moving_piece_id
    )
    square = chess.parse_square(last_move["destination"])
    piece = board.piece_at(square)
    if piece is None or piece.color == board.turn:
        return stored_gain_cp
    return stored_gain_cp - _oracle_legal_exchange_gain(board, square)


def _validate_chain(
    position_id: str,
    proof: Any,
    branches: dict[str, list[dict[str, Any]]],
    played_gain_cp: int,
    best_gain_cp: int,
) -> list[str]:
    failures = []
    steps = (proof.setup, *proof.transformation_steps, proof.payoff)
    for step in steps:
        failures.extend(_validate_step(position_id, branches, step))

    best = branches["best"]
    played = branches["played"]
    retained_plies = tuple(step.ply for step in proof.transformation_steps)
    expected_plies = tuple(range(2, proof.payoff.ply))
    if retained_plies != expected_plies:
        failures.append(f"{position_id}:intermediate_moves:not_complete")

    oracle_edge = best_gain_cp - played_gain_cp
    if proof.branch_evidence.difference.net_material_edge_cp != oracle_edge:
        failures.append(f"{position_id}:branch_edge:oracle_mismatch")
    if oracle_edge <= 0:
        failures.append(f"{position_id}:branch_edge:not_positive")

    adjusted_gain = _horizon_adjusted_gain(
        best,
        best_gain_cp,
        proof.payoff,
    )
    if adjusted_gain != proof.line_net_material_gain_cp:
        failures.append(f"{position_id}:line_gain:oracle_mismatch")
    if adjusted_gain <= 0:
        failures.append(f"{position_id}:line_gain:not_positive")

    setup = best[0]
    payoff = best[proof.payoff.ply - 1]
    mechanism = proof.mechanism
    if mechanism == "intermediate_exchange_preserves_rook":
        recapture = best[1]
        played_loss = next(
            (
                event
                for event in played
                if event["actor"] == "opponent"
                and event["captured_piece"] == "rook"
            ),
            None,
        )
        escaped_rook = next(
            (
                event
                for event in best[2 : payoff["ply"] - 1]
                if played_loss is not None
                and event["moving_piece_id"]
                == played_loss["captured_piece_id"]
            ),
            None,
        )
        if (
            setup["captured_piece_id"] is None
            or recapture["captured_piece_id"] != setup["moving_piece_id"]
            or played_loss is None
            or escaped_rook is None
            or escaped_rook["captured_piece_id"] is not None
            or payoff["captured_piece_id"]
            != played_loss["moving_piece_id"]
        ):
            failures.append(f"{position_id}:preserved_rook:causality")

    elif mechanism == "forced_king_capture_then_queen_capture":
        king_capture, queen_check, queen_move = best[1:4]
        if (
            setup["moving_piece"] != "rook"
            or not setup["gave_check"]
            or setup["legal_reply_count"] != 1
            or king_capture["moving_piece"] != "king"
            or king_capture["captured_piece_id"]
            != setup["moving_piece_id"]
            or queen_check["moving_piece"] != "queen"
            or not queen_check["gave_check"]
            or queen_move["moving_piece"] != "queen"
            or payoff["moving_piece_id"]
            != queen_check["moving_piece_id"]
            or payoff["captured_piece_id"]
            != queen_move["moving_piece_id"]
        ):
            failures.append(f"{position_id}:forced_queen_capture:causality")

    elif mechanism == "sacrifice_opens_rook_capture_route":
        recapture, rook_capture = best[1:3]
        board_after_recapture = chess.Board(recapture["fen_after"])
        legal_rook_capture = any(
            move.from_square == chess.parse_square(rook_capture["origin"])
            and move.to_square == chess.parse_square(rook_capture["destination"])
            and board_after_recapture.is_capture(move)
            for move in board_after_recapture.legal_moves
        )
        if (
            setup["moving_piece"] not in {"knight", "bishop"}
            or setup["captured_piece"] != "pawn"
            or recapture["moving_piece"] != "pawn"
            or recapture["captured_piece_id"]
            != setup["moving_piece_id"]
            or rook_capture["moving_piece"] != "rook"
            or rook_capture["captured_piece_id"]
            != recapture["moving_piece_id"]
            or not rook_capture["gave_check"]
            or not legal_rook_capture
            or payoff["moving_piece_id"]
            != rook_capture["moving_piece_id"]
            or payoff["captured_piece"]
            not in {"knight", "bishop", "rook", "queen"}
        ):
            failures.append(f"{position_id}:opened_rook_route:causality")
    else:
        failures.append(f"{position_id}:unknown_mechanism")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    cli_args = parser.parse_args()
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    annotation_packet = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    family_lock = json.loads(FAMILY_LOCK.read_text(encoding="utf-8"))
    annotations = {
        row["position_id"]: row for row in annotation_packet["annotations"]
    }
    family_ids = set(family_lock["proof_family_order"][3]["position_ids"])
    hidden_ids = {
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] == "hidden_opportunity"
    }
    failures: list[str] = []
    fires: list[str] = []
    mechanisms: Counter[str] = Counter()
    line_gains: dict[str, int] = {}
    reversal_checks = 0
    reversal_rejections = 0

    for row in packet["positions"]:
        position_id = row["position_id"]
        args = _arguments(row)
        prior_owner = (
            build_target_line_opportunity_proof(**args)
            or build_forcing_tempo_opportunity_proof(**args)
            or build_endgame_geometry_opportunity_proof(**args)
        )
        proof = _proof_for(row)
        if prior_owner is not None and proof is not None:
            failures.append(f"{position_id}:multiple_proof_owners")
        if proof is None:
            continue
        try:
            played, played_gain = _oracle_replay(
                row["fen"],
                row["played_move"]["san"],
                row["stored_four_ply"]["after_played"],
            )
            best, best_gain = _oracle_replay(
                row["fen"],
                row["best_move"]["san"],
                row["stored_four_ply"]["after_best"],
            )
        except (ValueError, AssertionError) as exc:
            failures.append(f"{position_id}:oracle_replay:{exc}")
        else:
            failures.extend(_validate_chain(
                position_id,
                proof,
                {"played": played, "best": best},
                played_gain,
                best_gain,
            ))
        rerun = _proof_for(row)
        if rerun is None or rerun.fingerprint != proof.fingerprint:
            failures.append(f"{position_id}:nondeterministic")
        fires.append(position_id)
        mechanisms[proof.mechanism] += 1
        line_gains[position_id] = proof.line_net_material_gain_cp
        reversal_checks += 1
        reversed_args = {
            **args,
            "played_san": args["best_move_san"],
            "best_move_san": args["played_san"],
            "pv_after_played": args["pv_after_best"],
            "pv_after_best": args["pv_after_played"],
        }
        if build_board_transformation_opportunity_proof(**reversed_args) is None:
            reversal_rejections += 1
        else:
            failures.append(f"{position_id}:branch_reversal_fire")

    fire_ids = set(fires)
    true_positives = len(fire_ids & hidden_ids)
    false_positives = len(fire_ids - hidden_ids)
    true_negatives = len((set(annotations) - hidden_ids) - fire_ids)
    if fire_ids != family_ids:
        failures.append("gold:board_transformation_recall_or_ownership")
    if false_positives:
        failures.append("gold:false_positive")

    authorization = get_authorization(BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID)
    protected = (
        QualitySurface.CAPTION,
        QualitySurface.PROMPT,
        QualitySurface.PLAN,
        QualitySurface.MASTERY,
    )
    leaked = [
        surface.value
        for surface in protected
        if is_authorized(BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID, surface)
    ]
    if authorization.grade != QualityGrade.SHADOW:
        failures.append("authorization:not_shadow")
    if leaked:
        failures.append("authorization:protected_surface_leak")

    wilson = _wilson_lower_bound(true_positives, len(fires))
    blockers = []
    if len(fires) < 50:
        blockers.append("reviewed_positive_count_below_50")
    if wilson < 0.85:
        blockers.append("wilson_lower_bound_below_85_pct")
    blockers.append("architecture_packet_not_population_holdout")
    result = {
        "schema_version": "hidden_opportunities_board_transformation_validation.v1",
        "proof_version": BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION,
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "positions": len(annotations),
        "hidden_opportunities": len(hidden_ids),
        "non_opportunities": len(annotations) - len(hidden_ids),
        "board_transformation_family_gold": len(family_ids),
        "proof_fires": len(fires),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "precision_pct": round((true_positives / len(fires)) * 100, 2),
        "wilson_lower_bound_pct": round(wilson * 100, 2),
        "mechanism_counts": dict(sorted(mechanisms.items())),
        "horizon_adjusted_line_gains_cp": dict(sorted(line_gains.items())),
        "branch_reversal_checks": reversal_checks,
        "branch_reversal_rejections": reversal_rejections,
        "authorization_grade": authorization.grade.value,
        "protected_surface_authorizations": leaked,
        "promotion_eligible": False,
        "promotion_blockers": blockers,
        "proof_position_ids": sorted(fires),
        "failures": failures,
        "passed": not failures and bool(blockers),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if cli_args.output:
        cli_args.output.parent.mkdir(parents=True, exist_ok=True)
        cli_args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
