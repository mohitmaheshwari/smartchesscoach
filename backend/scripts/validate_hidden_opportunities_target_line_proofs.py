#!/usr/bin/env python3
"""Independently validate Phase 3A.2 target/line causal proofs.

The proof builder is exercised, but its emitted board facts are checked by a
separate legal replay and piece-identity tracker in this script. No database,
network, engine, user identity, or file write is used.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys
from typing import Any

import chess


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_facts import (  # noqa: E402
    TARGET_LINE_CAUSAL_PROOF_VERSION,
    TARGET_LINE_CAUSAL_QUALITY_ID,
    TARGET_LINE_MIN_PAYOFF_CP,
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
HORIZON_LIMITED_GOLD_IDS = {"00906363fd88603401ce"}
WHOLE_BRANCH_BELOW_PAYOFF_FLOOR_IDS = {"001d12f6e8e923e5d08d"}
SETTLEMENT_PLIES = 4

# Independent test-oracle values. Runtime material truth remains owned by
# caption_facts; this mirror exists specifically to catch drift in that owner.
_ORACLE_VALUE_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _piece_name(piece: chess.Piece) -> str:
    return chess.piece_name(piece.piece_type)


def _piece_id(piece: chess.Piece, square: int) -> str:
    color = "white" if piece.color == chess.WHITE else "black"
    return f"{color}:{_piece_name(piece)}:{chess.square_name(square)}"


def _parse_move(board: chess.Board, raw: Any) -> chess.Move:
    text = str(raw or "").strip()
    try:
        move = chess.Move.from_uci(text)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    move = board.parse_san(text)
    if move not in board.legal_moves:
        raise ValueError(f"illegal oracle move: {text}")
    return move


def _oracle_replay(
    fen: str,
    leading_move: str,
    continuation: list[str],
) -> tuple[list[dict[str, Any]], int]:
    board = chess.Board(fen)
    identities = {
        square: _piece_id(piece, square)
        for square, piece in board.piece_map().items()
    }
    events: list[dict[str, Any]] = []
    net_gain_cp = 0

    for ply, raw in enumerate([leading_move, *continuation], start=1):
        move = _parse_move(board, raw)
        moving_piece = board.piece_at(move.from_square)
        if moving_piece is None:
            raise ValueError("oracle move has no moving piece")
        moving_id = identities[move.from_square]
        captured_square = move.to_square
        if board.is_en_passant(move):
            captured_square += -8 if board.turn == chess.WHITE else 8
        captured_piece = board.piece_at(captured_square)
        captured_id = (
            identities.get(captured_square)
            if captured_piece is not None
            else None
        )
        san = board.san(move)
        actor = "initiator" if ply % 2 else "opponent"
        captured_value_cp = (
            _ORACLE_VALUE_CP[captured_piece.piece_type]
            if captured_piece is not None
            else 0
        )
        promotion_piece = (
            chess.piece_name(move.promotion)
            if move.promotion is not None
            else None
        )
        promotion_gain_cp = (
            _ORACLE_VALUE_CP[move.promotion]
            - _ORACLE_VALUE_CP[chess.PAWN]
            if move.promotion is not None
            else 0
        )
        net_gain_cp += (
            captured_value_cp + promotion_gain_cp
            if actor == "initiator"
            else -(captured_value_cp + promotion_gain_cp)
        )

        rook_transfer = None
        if board.is_castling(move):
            rank = chess.square_rank(move.from_square)
            if chess.square_file(move.to_square) > chess.square_file(
                move.from_square
            ):
                rook_from = chess.square(7, rank)
                rook_to = chess.square(5, rank)
            else:
                rook_from = chess.square(0, rank)
                rook_to = chess.square(3, rank)
            rook_transfer = (rook_from, rook_to, identities[rook_from])

        identities.pop(move.from_square)
        if captured_piece is not None:
            identities.pop(captured_square, None)
        board.push(move)
        identities[move.to_square] = moving_id
        if rook_transfer is not None:
            rook_from, rook_to, rook_id = rook_transfer
            identities.pop(rook_from, None)
            identities[rook_to] = rook_id

        gave_check = board.is_check()
        legal_reply_count = board.legal_moves.count()

        events.append({
            "ply": ply,
            "actor": actor,
            "move_san": san,
            "origin": chess.square_name(move.from_square),
            "destination": chess.square_name(move.to_square),
            "moving_piece": _piece_name(moving_piece),
            "moving_piece_id": moving_id,
            "captured_piece": (
                _piece_name(captured_piece)
                if captured_piece is not None
                else None
            ),
            "captured_piece_id": captured_id,
            "captured_square": (
                chess.square_name(captured_square)
                if captured_piece is not None
                else None
            ),
            "captured_value_cp": captured_value_cp,
            "promotion_piece": promotion_piece,
            "promotion_gain_cp": promotion_gain_cp,
            "gave_check": gave_check,
            "legal_reply_count": legal_reply_count,
            "attack_squares_after": tuple(
                chess.square_name(square)
                for square in board.attacks(move.to_square)
            ),
            "fen_after": board.fen(),
        })
    return events, net_gain_cp


def _oracle_legal_exchange_gain(
    board: chess.Board,
    target_square: int,
) -> int:
    """Independently solve the legal capture exchange on one square."""
    if board.turn not in {chess.WHITE, chess.BLACK}:
        return 0

    def solve(work: chess.Board, depth: int = 0) -> int:
        if depth > 32:
            return 0
        best = 0
        for move in list(work.legal_moves):
            if move.to_square != target_square or not work.is_capture(move):
                continue
            captured_square = move.to_square
            if work.is_en_passant(move):
                captured_square += -8 if work.turn == chess.WHITE else 8
            captured = work.piece_at(captured_square)
            immediate = (
                _ORACLE_VALUE_CP[captured.piece_type]
                if captured is not None
                else 0
            )
            if move.promotion is not None:
                immediate += (
                    _ORACLE_VALUE_CP[move.promotion]
                    - _ORACLE_VALUE_CP[chess.PAWN]
                )
            after = work.copy(stack=False)
            after.push(move)
            best = max(best, immediate - solve(after, depth + 1))
        return best

    return solve(board.copy(stack=False))


def _oracle_move_material_delta(
    board: chess.Board,
    move: chess.Move,
    root: chess.Color,
) -> int:
    captured_value = 0
    if board.is_en_passant(move):
        captured_value = _ORACLE_VALUE_CP[chess.PAWN]
    elif board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured is not None:
            captured_value = _ORACLE_VALUE_CP[captured.piece_type]
    promotion_gain = (
        _ORACLE_VALUE_CP[move.promotion] - _ORACLE_VALUE_CP[chess.PAWN]
        if move.promotion is not None
        else 0
    )
    delta = captured_value + promotion_gain
    return delta if board.turn == root else -delta


def _oracle_settled_material_gain(
    fen: str,
    leading_move: str,
    continuation: list[str],
) -> int:
    """Independent four-ply forcing-check material oracle."""
    board = chess.Board(fen)
    root = board.turn
    gain = 0
    for raw in (leading_move, *continuation):
        move = _parse_move(board, raw)
        gain += _oracle_move_material_delta(board, move, root)
        board.push(move)

    def settle(work: chess.Board, depth: int) -> int:
        if work.is_checkmate():
            return -100_000 if work.turn == root else 100_000
        if depth <= 0:
            return 0
        if work.is_check():
            moves = list(work.legal_moves)
            values = []
        else:
            moves = [
                move
                for move in work.legal_moves
                if (
                    work.is_capture(move)
                    or move.promotion is not None
                    or work.gives_check(move)
                )
            ]
            values = [0]
        for move in moves:
            delta = _oracle_move_material_delta(work, move, root)
            after = work.copy(stack=False)
            after.push(move)
            values.append(delta + settle(after, depth - 1))
        return max(values) if work.turn == root else min(values)

    return gain + settle(board, SETTLEMENT_PLIES)


def _proof_for(row: dict[str, Any]):
    return build_target_line_opportunity_proof(
        fen_before=row["fen"],
        played_san=row["played_move"]["san"],
        best_move_san=row["best_move"]["san"],
        pv_after_played=tuple(
            row["stored_four_ply"]["after_played"]
        ),
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
    failures = []
    event = _event_for(branches, step)
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
    return failures


def _validate_chain(
    position_id: str,
    proof: Any,
    branches: dict[str, list[dict[str, Any]]],
    played_gain_cp: int,
    best_gain_cp: int,
    best_settled_gain_cp: int,
) -> list[str]:
    failures = []
    for step in (proof.setup, proof.constraint, proof.payoff):
        failures.extend(_validate_step(position_id, branches, step))

    payoff_event = _event_for(branches, proof.payoff)
    payoff_target = (
        payoff_event["captured_piece"],
        payoff_event["captured_piece_id"],
        payoff_event["captured_square"],
        payoff_event["captured_value_cp"],
    )
    declared_target = (
        proof.payoff.target_piece,
        proof.payoff.target_piece_id,
        proof.payoff.target_square,
        proof.payoff.target_value_cp,
    )
    if payoff_target != declared_target:
        failures.append(f"{position_id}:payoff:target:oracle_mismatch")
    if payoff_event["captured_value_cp"] < TARGET_LINE_MIN_PAYOFF_CP:
        failures.append(f"{position_id}:payoff:below_locked_floor")

    oracle_edge = best_gain_cp - played_gain_cp
    if proof.branch_evidence.difference.net_material_edge_cp != oracle_edge:
        failures.append(f"{position_id}:branch_edge:oracle_mismatch")
    if oracle_edge <= 0:
        failures.append(f"{position_id}:branch_edge:not_positive")
    if proof.settled_material_gain_cp != best_settled_gain_cp:
        failures.append(f"{position_id}:settled_gain:oracle_mismatch")
    if best_settled_gain_cp < TARGET_LINE_MIN_PAYOFF_CP:
        failures.append(f"{position_id}:settled_gain:below_locked_floor")

    best_events = branches["best"]
    played_events = branches["played"]
    if proof.mechanism in {
        "persistent_piece_attack",
        "target_enters_controlled_square",
    }:
        setup = _event_for(branches, proof.setup)
        payoff = _event_for(branches, proof.payoff)
        if setup["moving_piece_id"] != payoff["moving_piece_id"]:
            failures.append(f"{position_id}:persistent_piece:identity")
        if payoff["destination"] not in setup["attack_squares_after"]:
            failures.append(f"{position_id}:persistent_piece:geometry")
        if any(
            event["moving_piece_id"] == setup["moving_piece_id"]
            for event in best_events[1 : proof.payoff.ply - 1]
        ):
            failures.append(f"{position_id}:persistent_piece:moved_early")
        target_moves = [
            event
            for event in best_events[1 : proof.payoff.ply - 1]
            if event["moving_piece_id"] == payoff["captured_piece_id"]
        ]
        if proof.mechanism == "target_enters_controlled_square":
            if (
                not target_moves
                or target_moves[-1]["destination"]
                != payoff["destination"]
            ):
                failures.append(f"{position_id}:target_entry:not_proved")
        elif target_moves:
            failures.append(f"{position_id}:static_target:moved")

    elif proof.mechanism == "exchange_sequence":
        if len(best_events) < 3:
            failures.append(f"{position_id}:exchange:short")
        else:
            first, second, third = best_events[:3]
            if (
                first["captured_piece_id"] is None
                or second["captured_piece_id"]
                != first["moving_piece_id"]
                or third["captured_piece_id"]
                != second["moving_piece_id"]
            ):
                failures.append(f"{position_id}:exchange:identity")
            if any(
                event["actor"] == "initiator"
                and event["captured_piece_id"]
                == first["captured_piece_id"]
                for event in played_events
            ):
                failures.append(
                    f"{position_id}:exchange:first_target_in_played"
                )

    elif proof.mechanism == "remove_future_attacker":
        setup = _event_for(branches, proof.setup)
        contrast = _event_for(branches, proof.payoff)
        if (
            setup["captured_piece_id"] is None
            or contrast["moving_piece_id"]
            != setup["captured_piece_id"]
        ):
            failures.append(f"{position_id}:future_attacker:identity")
        if any(
            event["actor"] == "opponent"
            and event["captured_piece_id"]
            == contrast["captured_piece_id"]
            for event in best_events
        ):
            failures.append(f"{position_id}:future_attacker:same_loss")

    elif proof.mechanism == "immediate_free_capture":
        if proof.payoff.ply != 1 or payoff_event["captured_piece_id"] is None:
            failures.append(f"{position_id}:free_capture:not_immediate")
    else:
        failures.append(f"{position_id}:unknown_mechanism")

    if proof.mechanism in {
        "persistent_piece_attack",
        "target_enters_controlled_square",
        "immediate_free_capture",
    } and any(
        event["actor"] == "initiator"
        and event["captured_piece_id"]
        == payoff_event["captured_piece_id"]
        for event in played_events
    ):
        failures.append(f"{position_id}:target_also_captured_in_played")
    if proof.mechanism in {
        "persistent_piece_attack",
        "target_enters_controlled_square",
        "immediate_free_capture",
    }:
        mover_id = payoff_event["moving_piece_id"]
        later_recapture = next(
            (
                event
                for event in best_events[proof.payoff.ply :]
                if event["captured_piece_id"] == mover_id
            ),
            None,
        )
        captured_value = sum(
            event["captured_value_cp"]
            for event in best_events
            if (
                event["moving_piece_id"] == mover_id
                and event["captured_piece_id"] is not None
                and (
                    later_recapture is None
                    or event["ply"] < later_recapture["ply"]
                )
            )
        )
        recapture_cost = 0
        if later_recapture is not None:
            recapture_cost = later_recapture["captured_value_cp"]
        else:
            last_piece_move = next(
                (
                    event
                    for event in reversed(best_events)
                    if event["moving_piece_id"] == mover_id
                ),
                payoff_event,
            )
            final_board = chess.Board(best_events[-1]["fen_after"])
            final_square = chess.parse_square(
                last_piece_move["destination"]
            )
            final_piece = final_board.piece_at(final_square)
            if final_piece is not None and final_piece.color != final_board.turn:
                recapture_cost = _oracle_legal_exchange_gain(
                    final_board, final_square
                )
        if captured_value - recapture_cost <= 0:
            failures.append(f"{position_id}:payoff:not_net_positive")
    return failures


def _wilson_lower_bound(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * total)) / total
    )
    return (center - margin) / denominator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    cli_args = parser.parse_args()
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    annotation_packet = json.loads(
        ANNOTATIONS.read_text(encoding="utf-8")
    )
    family_lock = json.loads(FAMILY_LOCK.read_text(encoding="utf-8"))
    annotations = {
        row["position_id"]: row
        for row in annotation_packet["annotations"]
    }
    first_family = set(
        family_lock["proof_family_order"][0]["position_ids"]
    )
    failures: list[str] = []
    fires = []
    mechanism_counts: Counter[str] = Counter()
    reversed_branch_checks = 0
    reversed_branch_rejections = 0

    for row in packet["positions"]:
        position_id = row["position_id"]
        proof = _proof_for(row)
        if proof is not None:
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
                best_settled_gain = _oracle_settled_material_gain(
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
                    best_settled_gain,
                ))
            rerun = _proof_for(row)
            if rerun is None or rerun.fingerprint != proof.fingerprint:
                failures.append(f"{position_id}:nondeterministic")
            fires.append(position_id)
            mechanism_counts[proof.mechanism] += 1

        if proof is not None:
            reversed_branch_checks += 1
            reversed_proof = build_target_line_opportunity_proof(
                fen_before=row["fen"],
                played_san=row["best_move"]["san"],
                best_move_san=row["played_move"]["san"],
                pv_after_played=tuple(
                    row["stored_four_ply"]["after_best"]
                ),
                pv_after_best=tuple(
                    row["stored_four_ply"]["after_played"]
                ),
                cp_loss=row["cp_loss"],
            )
            if reversed_proof is None:
                reversed_branch_rejections += 1
            else:
                failures.append(f"{position_id}:branch_reversal_fire")

    hidden_ids = {
        position_id
        for position_id, annotation in annotations.items()
        if annotation["surface_grade"] == "hidden_opportunity"
    }
    fire_ids = set(fires)
    true_positives = len(fire_ids & hidden_ids)
    false_positives = len(fire_ids - hidden_ids)
    true_negatives = len((set(annotations) - hidden_ids) - fire_ids)
    first_family_hits = len(fire_ids & first_family)
    precision = true_positives / len(fires) if fires else 0.0
    wilson = _wilson_lower_bound(true_positives, len(fires))
    authorization = get_authorization(TARGET_LINE_CAUSAL_QUALITY_ID)
    protected_surfaces = (
        QualitySurface.CAPTION,
        QualitySurface.PROMPT,
        QualitySurface.PLAN,
        QualitySurface.MASTERY,
    )
    protected_surface_authorizations = [
        surface.value
        for surface in protected_surfaces
        if is_authorized(TARGET_LINE_CAUSAL_QUALITY_ID, surface)
    ]
    if authorization.grade != QualityGrade.SHADOW:
        failures.append("authorization:not_shadow")
    if protected_surface_authorizations:
        failures.append("authorization:protected_surface_leak")
    if false_positives:
        failures.append("gold:false_positive")
    target_line_fact_exclusions = (
        HORIZON_LIMITED_GOLD_IDS | WHOLE_BRANCH_BELOW_PAYOFF_FLOOR_IDS
    )
    provable_first_family = first_family - target_line_fact_exclusions
    if (
        len(fire_ids & provable_first_family) != len(provable_first_family)
        or fire_ids & target_line_fact_exclusions
    ):
        failures.append("gold:provable_first_family_recall")

    promotion_blockers = []
    if len(fires) < 50:
        promotion_blockers.append("reviewed_positive_count_below_50")
    if wilson < 0.85:
        promotion_blockers.append("wilson_lower_bound_below_85_pct")
    if len(hidden_ids) < 50:
        promotion_blockers.append("architecture_packet_not_population_holdout")

    result = {
        "schema_version": (
            "hidden_opportunities_target_line_validation.v6"
        ),
        "proof_version": TARGET_LINE_CAUSAL_PROOF_VERSION,
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "positions": len(annotations),
        "hidden_opportunities": len(hidden_ids),
        "non_opportunities": len(annotations) - len(hidden_ids),
        "proof_fires": len(fires),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "precision_pct": round(precision * 100, 2),
        "wilson_lower_bound_pct": round(wilson * 100, 2),
        "all_hidden_opportunity_recall_pct": round(
            true_positives / len(hidden_ids) * 100, 2
        ),
        "first_family_hits": first_family_hits,
        "first_family_total": len(first_family),
        "provable_first_family_total": len(provable_first_family),
        "horizon_limited_gold_position_ids": sorted(
            HORIZON_LIMITED_GOLD_IDS
        ),
        "whole_branch_below_payoff_floor_position_ids": sorted(
            WHOLE_BRANCH_BELOW_PAYOFF_FLOOR_IDS
        ),
        "settlement_plies": SETTLEMENT_PLIES,
        "first_family_recall_pct": round(
            first_family_hits / len(first_family) * 100, 2
        ),
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "branch_reversal_checks": reversed_branch_checks,
        "branch_reversal_rejections": reversed_branch_rejections,
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
