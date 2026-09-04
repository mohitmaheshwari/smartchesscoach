#!/usr/bin/env python3
"""Independently validate Phase 3A.2 forcing-tempo causal proofs.

The runtime proof builder is exercised, but every emitted move, physical-piece
identity, check, forced reply, capture, material yield, and horizon survival
claim is rederived by the separate legal-board oracle used by the target-line
audit. No database, network, engine, user identity, or file write is used.
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

from scripts.validate_hidden_opportunities_target_line_proofs import (  # noqa: E402
    _ORACLE_VALUE_CP,
    _oracle_legal_exchange_gain,
    _oracle_replay,
    _wilson_lower_bound,
)
from services.caption_facts import (  # noqa: E402
    FORCING_TEMPO_CAUSAL_PROOF_VERSION,
    FORCING_TEMPO_CAUSAL_QUALITY_ID,
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

# These two forcing-family ideas already have a stricter canonical owner.
TARGET_LINE_OWNER_IDS = {
    "03eccd1bf3d294170e7f",
    "039bd832a639d9c2f8ab",
}


def _proof_for(row: dict[str, Any]):
    return build_forcing_tempo_opportunity_proof(
        fen_before=row["fen"],
        played_san=row["played_move"]["san"],
        best_move_san=row["best_move"]["san"],
        pv_after_played=tuple(row["stored_four_ply"]["after_played"]),
        pv_after_best=tuple(row["stored_four_ply"]["after_best"]),
        cp_loss=row["cp_loss"],
    )


def _target_proof_for(row: dict[str, Any]):
    return build_target_line_opportunity_proof(
        fen_before=row["fen"],
        played_san=row["played_move"]["san"],
        best_move_san=row["best_move"]["san"],
        pv_after_played=tuple(row["stored_four_ply"]["after_played"]),
        pv_after_best=tuple(row["stored_four_ply"]["after_best"]),
        cp_loss=row["cp_loss"],
    )


def _event_for(
    branches: dict[str, list[dict[str, Any]]],
    step: Any,
) -> dict[str, Any]:
    return branches[step.branch][step.ply - 1]


def _validate_step(
    position_id: str,
    branches: dict[str, list[dict[str, Any]]],
    step: Any,
) -> list[str]:
    event = _event_for(branches, step)
    failures = []
    expected = {
        "actor": step.actor,
        "move_san": step.move_san,
        "moving_piece": step.moving_piece,
        "moving_piece_id": step.moving_piece_id,
        "origin": step.origin,
        "destination": step.destination,
    }
    for field, value in expected.items():
        if event[field] != value:
            failures.append(
                f"{position_id}:{step.role}:{field}:oracle_mismatch"
            )

    if (
        step.target_piece_id is not None
        and step.fact_kind != "check_controls_forced_reply_square"
    ):
        captured_target = (
            event["captured_piece"],
            event["captured_piece_id"],
            event["captured_square"],
            event["captured_value_cp"],
        )
        moved_target = (
            event["moving_piece"],
            event["moving_piece_id"],
            event["destination"],
            next(
                value
                for piece_type, value in _ORACLE_VALUE_CP.items()
                if chess.piece_name(piece_type) == event["moving_piece"]
            ),
        )
        declared_target = (
            step.target_piece,
            step.target_piece_id,
            step.target_square,
            step.target_value_cp,
        )
        if declared_target not in {captured_target, moved_target}:
            failures.append(
                f"{position_id}:{step.role}:target:oracle_mismatch"
            )
    return failures


def _material_yield(
    events: list[dict[str, Any]],
    *,
    moving_piece_id: str,
    payoff_ply: int,
) -> int:
    later_recapture = next(
        (
            event
            for event in events[payoff_ply:]
            if event["captured_piece_id"] == moving_piece_id
        ),
        None,
    )
    captured_value_cp = sum(
        event["captured_value_cp"]
        for event in events
        if (
            event["moving_piece_id"] == moving_piece_id
            and event["captured_piece_id"] is not None
            and (
                later_recapture is None
                or event["ply"] < later_recapture["ply"]
            )
        )
    )
    if later_recapture is not None:
        return captured_value_cp - later_recapture["captured_value_cp"]

    last_piece_move = next(
        event
        for event in reversed(events)
        if event["moving_piece_id"] == moving_piece_id
    )
    final_board = chess.Board(events[-1]["fen_after"])
    final_square = chess.parse_square(last_piece_move["destination"])
    final_piece = final_board.piece_at(final_square)
    if final_piece is None or final_piece.color == final_board.turn:
        return captured_value_cp
    return captured_value_cp - _oracle_legal_exchange_gain(
        final_board, final_square
    )


def _survives_horizon(
    events: list[dict[str, Any]],
    piece_id: str,
) -> bool:
    if any(event["captured_piece_id"] == piece_id for event in events):
        return False
    last_move = next(
        (
            event
            for event in reversed(events)
            if event["moving_piece_id"] == piece_id
        ),
        None,
    )
    if last_move is None:
        return False
    final_board = chess.Board(events[-1]["fen_after"])
    square = chess.parse_square(last_move["destination"])
    piece = final_board.piece_at(square)
    if piece is None:
        return False
    if piece.color == final_board.turn:
        return True
    return not any(
        final_board.is_capture(move) and move.to_square == square
        for move in final_board.legal_moves
    )


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
    material_payoff_cp = None
    if mechanism == "profitable_exchange_before_retreat":
        first, second = best[:2]
        if (
            first["captured_piece_id"] is None
            or second["captured_piece_id"] != first["moving_piece_id"]
        ):
            failures.append(f"{position_id}:profitable_exchange:identity")
        material_payoff_cp = (
            first["captured_value_cp"] - second["captured_value_cp"]
        )
        if any(
            event["actor"] == "initiator"
            and event["captured_piece_id"] == first["captured_piece_id"]
            for event in played
        ):
            failures.append(f"{position_id}:profitable_exchange:played_too")

    elif mechanism == "check_displaces_recapturer":
        played_capture, played_recapture = played[:2]
        setup, king_move, payoff = best[:3]
        if (
            played_capture["captured_piece_id"] is None
            or played_recapture["moving_piece"] != "king"
            or played_recapture["captured_piece_id"]
            != played_capture["moving_piece_id"]
            or not setup["gave_check"]
            or king_move["moving_piece_id"]
            != played_recapture["moving_piece_id"]
            or payoff["moving_piece_id"]
            != played_capture["moving_piece_id"]
            or payoff["captured_piece_id"]
            != played_capture["captured_piece_id"]
        ):
            failures.append(f"{position_id}:check_displacement:causality")
        material_payoff_cp = _material_yield(
            best,
            moving_piece_id=payoff["moving_piece_id"],
            payoff_ply=payoff["ply"],
        )

    elif mechanism == "forced_exchange_then_escape":
        setup, recapture = best[:2]
        escape = _event_for(branches, proof.payoff)
        played_loss = next(
            (
                event
                for event in played
                if event["captured_piece_id"] == escape["moving_piece_id"]
            ),
            None,
        )
        if (
            not setup["gave_check"]
            or setup["captured_piece_id"] is None
            or setup["legal_reply_count"] != 1
            or recapture["captured_piece_id"] != setup["moving_piece_id"]
            or escape["captured_piece_id"] is not None
            or played_loss is None
            or not _survives_horizon(best, escape["moving_piece_id"])
        ):
            failures.append(f"{position_id}:forced_exchange_escape:causality")
        material_payoff_cp = (
            played_loss["captured_value_cp"] if played_loss else 0
        )

    elif mechanism == "forcing_target_displacement":
        setup, displaced, payoff = best[:3]
        declared_future_target = (
            proof.setup.target_piece,
            proof.setup.target_piece_id,
            proof.setup.target_square,
            proof.setup.target_value_cp,
        )
        captured_future_target = (
            payoff["captured_piece"],
            payoff["captured_piece_id"],
            payoff["captured_square"],
            payoff["captured_value_cp"],
        )
        if (
            not setup["gave_check"]
            or setup["legal_reply_count"] != 1
            or payoff["moving_piece_id"] != setup["moving_piece_id"]
            or payoff["captured_piece_id"] != displaced["moving_piece_id"]
            or payoff["destination"] not in setup["attack_squares_after"]
            or declared_future_target != captured_future_target
        ):
            failures.append(f"{position_id}:target_displacement:causality")
        material_payoff_cp = _material_yield(
            best,
            moving_piece_id=setup["moving_piece_id"],
            payoff_ply=payoff["ply"],
        )

    elif mechanism == "check_saves_future_target":
        setup = best[0]
        played_loss = next(
            (
                event
                for event in played
                if event["captured_piece_id"] == setup["moving_piece_id"]
            ),
            None,
        )
        if (
            not setup["gave_check"]
            or played_loss is None
            or not _survives_horizon(best, setup["moving_piece_id"])
        ):
            failures.append(f"{position_id}:check_saves_target:causality")
        material_payoff_cp = (
            played_loss["captured_value_cp"] if played_loss else 0
        )

    elif mechanism == "capture_order_compound_payoff":
        moving_piece_id = best[0]["moving_piece_id"]
        best_captures = [
            event
            for event in best
            if (
                event["actor"] == "initiator"
                and event["moving_piece_id"] == moving_piece_id
                and event["captured_piece_id"] is not None
            )
        ]
        played_capture = next(
            (
                event
                for event in played
                if (
                    event["actor"] == "initiator"
                    and event["moving_piece_id"] == moving_piece_id
                    and event["captured_piece_id"] is not None
                )
            ),
            None,
        )
        played_loss = next(
            (
                event
                for event in played
                if event["captured_piece_id"] == moving_piece_id
            ),
            None,
        )
        if (
            len(best_captures) < 2
            or played_capture is None
            or played_loss is None
        ):
            failures.append(f"{position_id}:capture_order:causality")
            material_payoff_cp = 0
        else:
            material_payoff_cp = _material_yield(
                best,
                moving_piece_id=moving_piece_id,
                payoff_ply=best_captures[-1]["ply"],
            ) - _material_yield(
                played,
                moving_piece_id=moving_piece_id,
                payoff_ply=played_capture["ply"],
            )
    else:
        failures.append(f"{position_id}:unknown_mechanism")

    if material_payoff_cp != proof.material_payoff_cp:
        failures.append(f"{position_id}:material_payoff:oracle_mismatch")
    if not material_payoff_cp or material_payoff_cp <= 0:
        failures.append(f"{position_id}:material_payoff:not_positive")
    return failures


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
    forcing_family = set(
        family_lock["proof_family_order"][1]["position_ids"]
    )
    expected_new_ids = forcing_family - TARGET_LINE_OWNER_IDS
    hidden_ids = {
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] == "hidden_opportunity"
    }

    failures: list[str] = []
    fires: list[str] = []
    target_fires: list[str] = []
    mechanisms: Counter[str] = Counter()
    reversed_checks = 0
    reversed_rejections = 0

    for row in packet["positions"]:
        position_id = row["position_id"]
        target_proof = _target_proof_for(row)
        proof = _proof_for(row)
        if target_proof is not None:
            target_fires.append(position_id)
        if target_proof is not None and proof is not None:
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

        rerun = _proof_for(row)
        if rerun is None or rerun.fingerprint != proof.fingerprint:
            failures.append(f"{position_id}:nondeterministic")
        fires.append(position_id)
        mechanisms[proof.mechanism] += 1

        reversed_checks += 1
        reversed_proof = build_forcing_tempo_opportunity_proof(
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
    composed_ids = fire_ids | set(target_fires)
    true_positives = len(fire_ids & hidden_ids)
    false_positives = len(fire_ids - hidden_ids)
    true_negatives = len((set(annotations) - hidden_ids) - fire_ids)
    if fire_ids != expected_new_ids:
        failures.append("gold:new_forcing_family_ownership")
    if not forcing_family <= composed_ids:
        failures.append("gold:composed_forcing_family_recall")
    if false_positives:
        failures.append("gold:false_positive")

    authorization = get_authorization(FORCING_TEMPO_CAUSAL_QUALITY_ID)
    protected_surfaces = (
        QualitySurface.CAPTION,
        QualitySurface.PROMPT,
        QualitySurface.PLAN,
        QualitySurface.MASTERY,
    )
    protected_surface_authorizations = [
        surface.value
        for surface in protected_surfaces
        if is_authorized(FORCING_TEMPO_CAUSAL_QUALITY_ID, surface)
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
            "hidden_opportunities_forcing_tempo_validation.v2"
        ),
        "proof_version": FORCING_TEMPO_CAUSAL_PROOF_VERSION,
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "positions": len(annotations),
        "hidden_opportunities": len(hidden_ids),
        "non_opportunities": len(annotations) - len(hidden_ids),
        "forcing_family_gold": len(forcing_family),
        "canonical_target_line_owned": len(
            forcing_family & set(target_fires)
        ),
        "new_forcing_proof_fires": len(fires),
        "new_forcing_family_hits": len(fire_ids & expected_new_ids),
        "composed_forcing_family_hits": len(
            composed_ids & forcing_family
        ),
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
        "authorization_grade": authorization.grade.value,
        "protected_surface_authorizations": (
            protected_surface_authorizations
        ),
        "promotion_eligible": False,
        "promotion_blockers": promotion_blockers,
        "canonical_target_line_position_ids": sorted(
            forcing_family & set(target_fires)
        ),
        "new_forcing_proof_position_ids": sorted(fires),
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
