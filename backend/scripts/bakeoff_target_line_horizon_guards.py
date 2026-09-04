"""Bake off whole-branch horizon guards against the frozen v3 review.

This is an offline research utility. It replays only legal chess moves from
the anonymized packet and performs bounded material-only capture quiescence.
It does not call Stockfish, Maia, an LLM, a database, or the network.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.build_target_line_causal_pre_promotion_packet import (
    _architecture_signatures,
    _normalize_full_cases,
    _normalize_population_cases,
    _normalize_prior_cases,
    _position_signature,
    _proof,
)
from scripts.validate_hidden_opportunities_target_line_proofs import (
    _wilson_lower_bound,
)
from services.caption_facts import (
    PIECE_VALUE_CP,
    TARGET_LINE_CAUSAL_PROOF_VERSION,
    TARGET_LINE_MIN_PAYOFF_CP,
)


PACKET_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_review_v3.json"
)
REVIEW_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_independent_review_v3.json"
)
ANSWER_KEY_PATH = BACKEND_ROOT / (
    "data/detector_gold/target_line_causal_pre_promotion_answer_key_v3.json"
)
DEPTHS = (1, 2, 4, 6)
QUIET_CHECK_CANDIDATES = (
    ("captures_only_depth_2", "captures_only", 2),
    ("first_settlement_ply_checks_depth_3", "first_ply_checks", 3),
    ("all_quiet_checks_depth_3", "all_quiet_checks", 3),
    ("all_quiet_checks_depth_4", "all_quiet_checks", 4),
)


def _capture_delta(
    board: chess.Board, move: chess.Move, root: chess.Color
) -> int:
    captured_value = 0
    if board.is_en_passant(move):
        captured_value = PIECE_VALUE_CP[chess.PAWN]
    else:
        captured = board.piece_at(move.to_square)
        if captured is not None:
            captured_value = PIECE_VALUE_CP.get(captured.piece_type, 0)
    promotion_gain = 0
    if move.promotion is not None:
        promotion_gain = (
            PIECE_VALUE_CP.get(move.promotion, 0)
            - PIECE_VALUE_CP[chess.PAWN]
        )
    signed = captured_value + promotion_gain
    return signed if board.turn == root else -signed


@lru_cache(maxsize=None)
def _capture_quiescence(fen: str, root: bool, depth: int) -> int:
    board = chess.Board(fen)
    if board.is_checkmate():
        return -100_000 if board.turn == root else 100_000
    if depth <= 0:
        return 0
    if board.is_check():
        moves = list(board.legal_moves)
        if not moves:
            return -100_000 if board.turn == root else 100_000
        values = []
    else:
        moves = [
            move
            for move in board.legal_moves
            if board.is_capture(move) or move.promotion is not None
        ]
        values = [0]
    for move in moves:
        delta = _capture_delta(board, move, root)
        after = board.copy(stack=False)
        after.push(move)
        values.append(
            delta + _capture_quiescence(after.fen(), root, depth - 1)
        )
    return max(values) if board.turn == root else min(values)


def _settled_gain(row: Mapping[str, Any], branch: str, depth: int) -> int:
    root = chess.Board(row["fen_before"]).turn
    first_key = "played_san" if branch == "played" else "best_move_san"
    line_key = "pv_after_played" if branch == "played" else "pv_after_best"
    board = chess.Board(row["fen_before"])
    gain = 0
    tokens = [row[first_key], *row[line_key]]
    for token in tokens:
        move = board.parse_san(token)
        gain += _capture_delta(board, move, root)
        board.push(move)
        if board.is_game_over(claim_draw=True):
            break
    return gain + _capture_quiescence(board.fen(), root, depth)


@lru_cache(maxsize=None)
def _forcing_quiescence(
    fen: str,
    root: bool,
    depth: int,
    policy: str,
    settlement_ply: int,
) -> int:
    board = chess.Board(fen)
    if board.is_checkmate():
        return -100_000 if board.turn == root else 100_000
    if depth <= 0:
        return 0
    if board.is_check():
        moves = list(board.legal_moves)
        values = []
    else:
        include_quiet_checks = (
            policy == "all_quiet_checks"
            or (policy == "first_ply_checks" and settlement_ply == 0)
        )
        moves = [
            move
            for move in board.legal_moves
            if (
                board.is_capture(move)
                or move.promotion is not None
                or (include_quiet_checks and board.gives_check(move))
            )
        ]
        values = [0]
    for move in moves:
        delta = _capture_delta(board, move, root)
        after = board.copy(stack=False)
        after.push(move)
        values.append(
            delta
            + _forcing_quiescence(
                after.fen(),
                root,
                depth - 1,
                policy,
                settlement_ply + 1,
            )
        )
    return max(values) if board.turn == root else min(values)


def _settled_gain_with_policy(
    row: Mapping[str, Any],
    branch: str,
    *,
    depth: int,
    policy: str,
) -> int:
    root = chess.Board(row["fen_before"]).turn
    first_key = "played_san" if branch == "played" else "best_move_san"
    line_key = "pv_after_played" if branch == "played" else "pv_after_best"
    board = chess.Board(row["fen_before"])
    gain = 0
    for token in (row[first_key], *row[line_key]):
        move = board.parse_san(token)
        gain += _capture_delta(board, move, root)
        board.push(move)
        if board.is_game_over(claim_draw=True):
            break
    return gain + _forcing_quiescence(
        board.fen(), root, depth, policy, 0
    )


def _source_rows() -> dict[str, Mapping[str, Any]]:
    rows = (
        list(_normalize_full_cases())
        + list(_normalize_prior_cases())
        + list(_normalize_population_cases())
    )
    return {_position_signature(row): row for row in rows}


def _reviewed_candidate_rows() -> tuple[
    dict[str, Any],
    list[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
]:
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    answer_key = json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))
    candidates = set(answer_key["candidate_case_ids"])
    responses = {
        response["case_id"]: response for response in review["responses"]
    }
    source_rows = _source_rows()
    candidate_rows = []
    for case in packet["cases"]:
        if case["case_id"] not in candidates:
            continue
        signature = _position_signature({
            "fen_before": case["position"]["fen"],
            "played_san": case["played_branch"]["move_san"],
            "best_move_san": case["better_branch"]["move_san"],
        })
        candidate_rows.append((
            case["case_id"], source_rows[signature], responses[case["case_id"]]
        ))
    return packet, candidate_rows


def run_bakeoff() -> dict[str, Any]:
    packet, candidate_rows = _reviewed_candidate_rows()
    formulas = {
        "best_positive": lambda best, played: best >= TARGET_LINE_MIN_PAYOFF_CP,
        "edge_positive": lambda best, played: (
            best - played >= TARGET_LINE_MIN_PAYOFF_CP
        ),
        "best_and_edge_positive": lambda best, played: (
            best >= TARGET_LINE_MIN_PAYOFF_CP
            and best - played >= TARGET_LINE_MIN_PAYOFF_CP
        ),
    }
    results = []
    for depth in DEPTHS:
        settled = {
            case_id: (
                _settled_gain(row, "best", depth),
                _settled_gain(row, "played", depth),
            )
            for case_id, row, _ in candidate_rows
        }
        for name, predicate in formulas.items():
            retained = [
                (case_id, response)
                for case_id, _, response in candidate_rows
                if predicate(*settled[case_id])
            ]
            true_positive = sum(
                response["verdict"] == "proved_target_line_payoff"
                for _, response in retained
            )
            false_positive = len(retained) - true_positive
            precision = true_positive / len(retained) if retained else 0.0
            critical = sum(
                response["critical_false_claim"]
                for _, response in retained
            )
            removed = [
                case_id
                for case_id, _, _ in candidate_rows
                if not predicate(*settled[case_id])
            ]
            results.append({
                "depth": depth,
                "formula": name,
                "retained_candidates": len(retained),
                "true_positives": true_positive,
                "false_positives": false_positive,
                "critical_false_claims": critical,
                "semantic_precision_pct": round(precision * 100, 2),
                "wilson_lower_bound_pct": round(
                    _wilson_lower_bound(true_positive, len(retained)) * 100,
                    2,
                ),
                "removed_candidates": len(removed),
                "removed_case_ids": sorted(removed),
            })

    current_retained = [
        (case_id, response)
        for case_id, row, response in candidate_rows
        if _proof(row) is not None
    ]
    reviewed_signatures = {
        _position_signature({
            "fen_before": case["position"]["fen"],
            "played_san": case["played_branch"]["move_san"],
            "best_move_san": case["better_branch"]["move_san"],
        })
        for case in packet["cases"]
    }
    excluded_signatures = reviewed_signatures | _architecture_signatures()
    unseen_signatures: set[str] = set()
    unseen_rows = []
    for row in _normalize_population_cases():
        signature = _position_signature(row)
        if signature in excluded_signatures or signature in unseen_signatures:
            continue
        unseen_signatures.add(signature)
        unseen_rows.append(row)
    unseen_fires = [row for row in unseen_rows if _proof(row) is not None]
    return {
        "schema_version": "target_line_causal.horizon_guard_bakeoff.v1",
        "generated_on": "2026-09-04",
        "read_only": True,
        "stockfish_runs": 0,
        "maia_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "candidate_cases": len(candidate_rows),
        "material_floor_cp": TARGET_LINE_MIN_PAYOFF_CP,
        "depths": list(DEPTHS),
        "results": results,
        "current_detector_development_replay": {
            "proof_version": TARGET_LINE_CAUSAL_PROOF_VERSION,
            "retained_candidates": len(current_retained),
            "reviewer_proved": sum(
                response["verdict"] == "proved_target_line_payoff"
                for _, response in current_retained
            ),
            "reviewer_negative_case_ids": sorted(
                case_id
                for case_id, response in current_retained
                if response["verdict"] != "proved_target_line_payoff"
            ),
            "reviewer_critical_flags": sum(
                bool(response["critical_false_claim"])
                for _, response in current_retained
            ),
        },
        "fresh_holdout_availability": {
            "reviewed_packet_signatures_excluded": len(reviewed_signatures),
            "remaining_unique_population_positions": len(unseen_signatures),
            "current_detector_fires": len(unseen_fires),
            "promotion_packet_possible": len(unseen_fires) >= 50,
            "blocker": (
                None
                if len(unseen_fires) >= 50
                else "all_available_population_fires_were_already_reviewed"
            ),
        },
    }


def run_quiet_check_bakeoff() -> dict[str, Any]:
    _, candidate_rows = _reviewed_candidate_rows()

    results = []
    for name, policy, depth in QUIET_CHECK_CANDIDATES:
        retained = []
        settled_scores = {}
        for case_id, row, response in candidate_rows:
            score = _settled_gain_with_policy(
                row, "best", depth=depth, policy=policy
            )
            settled_scores[case_id] = score
            if score >= TARGET_LINE_MIN_PAYOFF_CP:
                retained.append((case_id, response))
        true_positive = sum(
            response["verdict"] == "proved_target_line_payoff"
            for _, response in retained
        )
        results.append({
            "candidate": name,
            "policy": policy,
            "depth": depth,
            "retained_candidates": len(retained),
            "reviewer_true_positives": true_positive,
            "reviewer_false_positives": len(retained) - true_positive,
            "reviewer_critical_false_claims": sum(
                bool(response["critical_false_claim"])
                for _, response in retained
            ),
            "semantic_precision_pct": round(
                true_positive / len(retained) * 100, 2
            ) if retained else 0.0,
            "wilson_lower_bound_pct": round(
                _wilson_lower_bound(true_positive, len(retained)) * 100, 2
            ),
            "c1d5_retained": any(
                case_id == "c1d5d2537da9d8784fd8"
                for case_id, _ in retained
            ),
            "c1d5_settled_gain_cp": settled_scores[
                "c1d5d2537da9d8784fd8"
            ],
        })
    return {
        "schema_version": "target_line_causal.quiet_check_bakeoff.v1",
        "generated_on": "2026-09-04",
        "read_only": True,
        "stockfish_runs": 0,
        "maia_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "candidate_cases": len(candidate_rows),
        "material_floor_cp": TARGET_LINE_MIN_PAYOFF_CP,
        "decision_candidates": [name for name, _, _ in QUIET_CHECK_CANDIDATES],
        "results": results,
    }


def run_runtime_replay() -> dict[str, Any]:
    """Score the currently imported production proof on frozen v3 candidates."""
    _, candidate_rows = _reviewed_candidate_rows()
    retained = [
        (case_id, response)
        for case_id, row, response in candidate_rows
        if _proof(row) is not None
    ]
    true_positive = sum(
        response["verdict"] == "proved_target_line_payoff"
        for _, response in retained
    )
    false_case_ids = sorted(
        case_id
        for case_id, response in retained
        if response["verdict"] != "proved_target_line_payoff"
    )
    critical_case_ids = sorted(
        case_id
        for case_id, response in retained
        if response["critical_false_claim"]
    )
    retained_count = len(retained)
    precision = true_positive / retained_count if retained_count else 0.0
    wilson = _wilson_lower_bound(true_positive, retained_count)
    c1d5_case_id = "c1d5d2537da9d8784fd8"
    c1d5_retained = any(
        case_id == c1d5_case_id for case_id, _ in retained
    )
    gates = {
        "retained_at_least_50": retained_count >= 50,
        "semantic_precision_at_least_95_pct": precision >= 0.95,
        "wilson_lower_bound_at_least_85_pct": wilson >= 0.85,
        "zero_reviewer_negative_survivors": not false_case_ids,
        "zero_critical_false_claims": not critical_case_ids,
        "c1d5_quiet_check_refutation_rejected": not c1d5_retained,
    }
    return {
        "schema_version": "target_line_causal.frozen_runtime_replay.v1",
        "generated_on": "2026-09-04",
        "read_only": True,
        "stockfish_runs": 0,
        "maia_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "proof_version": TARGET_LINE_CAUSAL_PROOF_VERSION,
        "candidate_cases": len(candidate_rows),
        "retained_candidates": retained_count,
        "reviewer_true_positives": true_positive,
        "reviewer_false_positives": retained_count - true_positive,
        "reviewer_negative_case_ids": false_case_ids,
        "reviewer_critical_false_claims": len(critical_case_ids),
        "reviewer_critical_case_ids": critical_case_ids,
        "semantic_precision_pct": round(precision * 100, 2),
        "wilson_lower_bound_pct": round(wilson * 100, 2),
        "c1d5_retained": c1d5_retained,
        "gates": gates,
        "passed": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--mode",
        choices=("horizon", "quiet-check", "runtime-replay"),
        default="horizon",
    )
    args = parser.parse_args()
    if args.mode == "quiet-check":
        result = run_quiet_check_bakeoff()
    elif args.mode == "runtime-replay":
        result = run_runtime_replay()
    else:
        result = run_bakeoff()
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
