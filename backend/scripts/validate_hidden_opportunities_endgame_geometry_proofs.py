#!/usr/bin/env python3
"""Independently validate Phase 3A.2 endgame-geometry proofs.

Runtime proofs are exercised, while every move, identity, capture, promotion,
check, branch edge, and survival statement is rederived by the independent
legal-board oracle. No exact WDL is inferred from stored Stockfish lines.
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
    _material_yield,
    _survives_horizon,
    _validate_step,
)
from scripts.validate_hidden_opportunities_target_line_proofs import (  # noqa: E402
    _ORACLE_VALUE_CP,
    _oracle_replay,
    _wilson_lower_bound,
)
from services.caption_facts import (  # noqa: E402
    ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION,
    ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID,
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
    return build_endgame_geometry_opportunity_proof(**_arguments(row))


def _validate_chain(
    position_id: str,
    proof: Any,
    branches: dict[str, list[dict[str, Any]]],
    played_gain_cp: int,
    best_gain_cp: int,
) -> list[str]:
    failures = []
    for step in (proof.setup, proof.constraint, proof.payoff):
        failures.extend(_validate_step(position_id, branches, step))

    played = branches["played"]
    best = branches["best"]
    oracle_edge = best_gain_cp - played_gain_cp
    if proof.branch_evidence.difference.net_material_edge_cp != oracle_edge:
        failures.append(f"{position_id}:branch_edge:oracle_mismatch")
    if oracle_edge <= 0:
        failures.append(f"{position_id}:branch_edge:not_positive")

    mechanism = proof.mechanism
    payoff_value_cp = None
    if mechanism == "king_route_reaches_pawn":
        setup = best[0]
        route = best[proof.constraint.ply - 1]
        payoff = best[proof.payoff.ply - 1]
        board = chess.Board(proof.branch_evidence.best_trace.initial_fen)
        if (
            any(
                piece.piece_type not in {chess.KING, chess.PAWN}
                for piece in board.piece_map().values()
            )
            or setup["moving_piece"] != "king"
            or route["moving_piece_id"] != setup["moving_piece_id"]
            or payoff["moving_piece_id"] != setup["moving_piece_id"]
            or payoff["captured_piece"] != "pawn"
            or any(
                event["actor"] == "initiator"
                and event["captured_piece_id"]
                == payoff["captured_piece_id"]
                for event in played
            )
        ):
            failures.append(f"{position_id}:king_route:causality")
        payoff_value_cp = payoff["captured_value_cp"]

    elif mechanism == "immediate_pawn_push_promotes":
        setup = best[0]
        played_push = played[proof.constraint.ply - 1]
        promotion = best[proof.payoff.ply - 1]
        promotion_piece_type = next(
            piece_type
            for piece_type in _ORACLE_VALUE_CP
            if chess.piece_name(piece_type) == proof.promotion_piece
        )
        if (
            setup["moving_piece"] != "pawn"
            or setup["moving_piece_id"] != promotion["moving_piece_id"]
            or played_push["moving_piece_id"] != setup["moving_piece_id"]
            or played_push["destination"] != setup["destination"]
            or played_push["ply"] <= setup["ply"]
            or promotion["promotion_piece"] != proof.promotion_piece
            or any(
                event["moving_piece_id"] == setup["moving_piece_id"]
                and event["promotion_piece"] is not None
                for event in played
            )
            or not _survives_horizon(best, setup["moving_piece_id"])
        ):
            failures.append(f"{position_id}:promotion_tempo:causality")
        payoff_value_cp = (
            _ORACLE_VALUE_CP[promotion_piece_type]
            - _ORACLE_VALUE_CP[chess.PAWN]
        )

    elif mechanism == "king_move_preserves_rook_exchange":
        setup = best[0]
        checking_rook = best[proof.constraint.ply - 1]
        payoff = best[proof.payoff.ply - 1]
        preserved_rook_id = played[0]["moving_piece_id"]
        if (
            setup["moving_piece"] != "king"
            or played[0]["moving_piece"] != "rook"
            or not checking_rook["gave_check"]
            or checking_rook["moving_piece"] != "rook"
            or payoff["moving_piece_id"] != preserved_rook_id
            or payoff["captured_piece_id"]
            != checking_rook["moving_piece_id"]
            or any(
                event["moving_piece_id"] == preserved_rook_id
                for event in best[: payoff["ply"] - 1]
            )
            or any(
                event["actor"] == "initiator"
                and event["captured_piece_id"]
                == checking_rook["moving_piece_id"]
                for event in played
            )
        ):
            failures.append(f"{position_id}:rook_exchange:causality")
        payoff_value_cp = payoff["captured_value_cp"]

    elif mechanism == "alternate_rook_preserves_promotion_capture":
        best_capture = best[0]
        played_capture = played[0]
        promotion = best[proof.constraint.ply - 1]
        payoff = best[proof.payoff.ply - 1]
        played_promotion = next(
            (
                event
                for event in played
                if event["promotion_piece"] is not None
            ),
            None,
        )
        if (
            best_capture["moving_piece"] != "rook"
            or played_capture["moving_piece"] != "rook"
            or best_capture["moving_piece_id"]
            == played_capture["moving_piece_id"]
            or best_capture["captured_piece_id"]
            != played_capture["captured_piece_id"]
            or played_promotion is None
            or promotion["moving_piece_id"]
            != played_promotion["moving_piece_id"]
            or promotion["destination"] != played_promotion["destination"]
            or payoff["moving_piece_id"]
            != played_capture["moving_piece_id"]
            or payoff["captured_piece_id"]
            != promotion["moving_piece_id"]
            or not _survives_horizon(
                played, promotion["moving_piece_id"]
            )
            or _material_yield(
                best,
                moving_piece_id=payoff["moving_piece_id"],
                payoff_ply=payoff["ply"],
            ) <= 0
        ):
            failures.append(f"{position_id}:alternate_rook:causality")
        payoff_value_cp = payoff["captured_value_cp"]
    else:
        failures.append(f"{position_id}:unknown_mechanism")

    if payoff_value_cp != proof.payoff_value_cp:
        failures.append(f"{position_id}:payoff_value:oracle_mismatch")
    return failures


def _final_target_recaptures(
    events: list[dict[str, Any]],
    payoff: Any,
) -> list[str]:
    board = chess.Board(events[-1]["fen_after"])
    last_move = next(
        event
        for event in reversed(events)
        if event["moving_piece_id"] == payoff.moving_piece_id
    )
    square = chess.parse_square(last_move["destination"])
    return [
        board.san(move)
        for move in board.legal_moves
        if board.is_capture(move) and move.to_square == square
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    cli_args = parser.parse_args()
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    annotation_packet = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    family_lock = json.loads(FAMILY_LOCK.read_text(encoding="utf-8"))
    annotations = {
        row["position_id"]: row
        for row in annotation_packet["annotations"]
    }
    family_ids = set(
        family_lock["proof_family_order"][2]["position_ids"]
    )
    hidden_ids = {
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] == "hidden_opportunity"
    }

    failures: list[str] = []
    fires: list[str] = []
    mechanisms: Counter[str] = Counter()
    reversed_checks = 0
    reversed_rejections = 0
    exchange_recaptures: dict[str, list[str]] = {}

    for row in packet["positions"]:
        position_id = row["position_id"]
        args = _arguments(row)
        prior_owner = (
            build_target_line_opportunity_proof(**args)
            or build_forcing_tempo_opportunity_proof(**args)
        )
        proof = _proof_for(row)
        if prior_owner is not None and proof is not None:
            failures.append(f"{position_id}:multiple_proof_owners")
        if proof is None:
            continue

        try:
            played_events, played_gain = _oracle_replay(
                row["fen"],
                row["played_move"]["san"],
                row["stored_four_ply"]["after_played"],
            )
            best_events, best_gain = _oracle_replay(
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
                {"played": played_events, "best": best_events},
                played_gain,
                best_gain,
            ))
            if proof.payoff_kind == "checking_rook_exchange":
                exchange_recaptures[position_id] = _final_target_recaptures(
                    best_events, proof.payoff
                )

        rerun = _proof_for(row)
        if rerun is None or rerun.fingerprint != proof.fingerprint:
            failures.append(f"{position_id}:nondeterministic")
        fires.append(position_id)
        mechanisms[proof.mechanism] += 1

        reversed_checks += 1
        reversed_proof = build_endgame_geometry_opportunity_proof(
            fen_before=row["fen"],
            played_san=row["best_move"]["san"],
            best_move_san=row["played_move"]["san"],
            pv_after_played=tuple(row["stored_four_ply"]["after_best"]),
            pv_after_best=tuple(row["stored_four_ply"]["after_played"]),
            cp_loss=row["cp_loss"],
        )
        if reversed_proof is None:
            reversed_rejections += 1
        else:
            failures.append(f"{position_id}:branch_reversal_fire")

    fire_ids = set(fires)
    true_positives = len(fire_ids & hidden_ids)
    false_positives = len(fire_ids - hidden_ids)
    true_negatives = len((set(annotations) - hidden_ids) - fire_ids)
    if fire_ids != family_ids:
        failures.append("gold:endgame_family_recall_or_ownership")
    if false_positives:
        failures.append("gold:false_positive")
    if not exchange_recaptures.get("00bb6cd1492bc5b6f355"):
        failures.append("exchange_resource:recapture_not_recorded")

    authorization = get_authorization(ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID)
    protected_surfaces = (
        QualitySurface.CAPTION,
        QualitySurface.PROMPT,
        QualitySurface.PLAN,
        QualitySurface.MASTERY,
    )
    protected_surface_authorizations = [
        surface.value
        for surface in protected_surfaces
        if is_authorized(ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID, surface)
    ]
    if authorization.grade != QualityGrade.SHADOW:
        failures.append("authorization:not_shadow")
    if protected_surface_authorizations:
        failures.append("authorization:protected_surface_leak")

    wilson = _wilson_lower_bound(true_positives, len(fires))
    promotion_blockers = []
    if len(fires) < 50:
        promotion_blockers.append("reviewed_positive_count_below_50")
    if wilson < 0.85:
        promotion_blockers.append("wilson_lower_bound_below_85_pct")
    if len(hidden_ids) < 50:
        promotion_blockers.append(
            "architecture_packet_not_population_holdout"
        )

    result = {
        "schema_version": (
            "hidden_opportunities_endgame_geometry_validation.v2"
        ),
        "proof_version": ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION,
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "positions": len(annotations),
        "hidden_opportunities": len(hidden_ids),
        "non_opportunities": len(annotations) - len(hidden_ids),
        "endgame_family_gold": len(family_ids),
        "proof_fires": len(fires),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "precision_pct": round(
            (true_positives / len(fires) if fires else 0.0) * 100,
            2,
        ),
        "wilson_lower_bound_pct": round(wilson * 100, 2),
        "mechanism_counts": dict(sorted(mechanisms.items())),
        "branch_reversal_checks": reversed_checks,
        "branch_reversal_rejections": reversed_rejections,
        "checking_rook_exchange_final_legal_recaptures": (
            exchange_recaptures
        ),
        "exact_wdl_claims": 0,
        "authorization_grade": authorization.grade.value,
        "protected_surface_authorizations": (
            protected_surface_authorizations
        ),
        "promotion_eligible": False,
        "promotion_blockers": promotion_blockers,
        "proof_position_ids": sorted(fires),
        "failures": failures,
        "passed": not failures and bool(promotion_blockers),
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
