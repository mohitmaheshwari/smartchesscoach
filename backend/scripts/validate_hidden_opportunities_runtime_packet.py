#!/usr/bin/env python3
"""Reproduce the locked 100-position Hidden Opportunities runtime baseline.

The validator is offline: it reads anonymized stored branches, runs no engine,
uses no database or network, and writes nothing.  It fails when a branch is no
longer legal or the current analyzer drifts from the reviewed baseline.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.pv_tactical_analyzer import explain_best_move_tactically


PACKET = BACKEND / "data/corpus_snapshots/hidden_opportunities_chess_gold_v1_2026-09-02.json"
BASELINE = BACKEND / "data/corpus_snapshots/hidden_opportunities_current_runtime_comparison_v1_2026-09-03.json"


def _push(board: chess.Board, notation: str) -> None:
    try:
        move = chess.Move.from_uci(notation)
        if move not in board.legal_moves:
            raise ValueError
    except Exception:
        move = board.parse_san(notation)
    board.push(move)


def _branch_is_legal(row: dict, branch: str) -> bool:
    board = chess.Board(row["fen"])
    first = row["played_move"] if branch == "played" else row["best_move"]
    try:
        _push(board, first["uci"])
        for notation in row["stored_four_ply"][f"after_{branch}"]:
            _push(board, notation)
    except Exception:
        return False
    return True


def main() -> int:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    reviewed = {row["position_id"]: row for row in baseline["assessments"]}
    counts = Counter()
    drift = []
    illegal = []

    for row in packet["positions"]:
        position_id = row["position_id"]
        for branch in ("played", "best"):
            if not _branch_is_legal(row, branch):
                illegal.append({"position_id": position_id, "branch": branch})

        output = None
        error = None
        try:
            output = explain_best_move_tactically(
                row["fen"],
                row["best_move"]["uci"],
                row["best_move"]["san"],
                row["stored_four_ply"]["after_best"],
            )
        except Exception as exc:  # baseline includes one known runtime crash
            error = f"{type(exc).__name__}: {exc}"

        counts["positions"] += 1
        counts["non_null"] += int(output is not None)
        counts["crashes"] += int(error is not None)
        expected = reviewed.get(position_id)
        expected_output = expected.get("current_output") if expected else None
        expected_error = expected.get("current_error") if expected else None
        if output != expected_output or error != expected_error:
            drift.append({
                "position_id": position_id,
                "expected_output": expected_output,
                "actual_output": output,
                "expected_error": expected_error,
                "actual_error": error,
            })

    result = {
        "schema_version": "hidden_opportunities_runtime_validation.v1",
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        "positions": counts["positions"],
        "legal_branches": counts["positions"] * 2 - len(illegal),
        "expected_non_null": baseline["measured"]["pv_analyzer_non_null"],
        "actual_non_null": counts["non_null"],
        "expected_crashes": baseline["measured"]["pv_analyzer_crashes"],
        "actual_crashes": counts["crashes"],
        "runtime_drift_count": len(drift),
        "illegal_branches": illegal,
        "runtime_drift": drift,
        "passed": not illegal and not drift,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
