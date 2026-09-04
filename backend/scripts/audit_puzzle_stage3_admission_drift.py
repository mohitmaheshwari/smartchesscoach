#!/usr/bin/env python3
"""Recheck sampled puzzle answers whose WDL bucket drifts at shallow depth.

This is a read-only, aggregate-only Stage 3 safety audit. It intentionally
exports no puzzle identifiers, positions, or moves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import chess
import chess.engine
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.run_puzzle_stage3_shadow_bakeoff import (  # noqa: E402
    _load_puzzles,
    _score_cp,
    _wdl_outcome,
)

SCHEMA_VERSION = "human_chess.puzzle_stage3_admission_drift.v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quantiles(values: Iterable[float]) -> Dict[str, Optional[float]]:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return {"minimum": None, "p25": None, "median": None, "p75": None, "p90": None, "maximum": None}
    at = lambda fraction: ordered[round((len(ordered) - 1) * fraction)]
    return {
        "minimum": ordered[0],
        "p25": at(0.25),
        "median": at(0.5),
        "p75": at(0.75),
        "p90": at(0.9),
        "maximum": ordered[-1],
    }


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def summarize(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    baseline_mismatches = [row for row in rows if row["baseline_preserves_wdl"] is False]
    confirmed = [row for row in baseline_mismatches if row["confirmation_preserves_wdl"] is False]
    resolved = [row for row in baseline_mismatches if row["confirmation_preserves_wdl"] is True]
    return {
        "positions": len(rows),
        "baseline_wdl_preservation_rate": _rate(
            sum(row["baseline_preserves_wdl"] is True for row in rows),
            sum(row["baseline_preserves_wdl"] is not None for row in rows),
        ),
        "baseline_mismatches": len(baseline_mismatches),
        "confirmation_rechecks": len(baseline_mismatches),
        "resolved_at_confirmation_depth": len(resolved),
        "confirmed_wdl_mismatches": len(confirmed),
        "confirmed_mismatch_rate": _rate(len(confirmed), len(rows)),
        "confirmed_acceptable_move_loss_cp": _quantiles(
            row["confirmation_acceptable_loss_cp"] for row in confirmed
        ),
    }


def _segments(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    result = {}
    for axis in ("pool", "difficulty", "admission_status", "concept_family"):
        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row[axis])].append(row)
        result[axis] = {value: summarize(items) for value, items in sorted(grouped.items())}
    return result


def _evaluate(engine, board: chess.Board, acceptable: Sequence[str], depth: int) -> Dict[str, Any]:
    best = engine.analyse(board, chess.engine.Limit(depth=depth))
    best_score = _score_cp(best, board.turn)
    best_wdl = _wdl_outcome(best, board.turn)
    constrained = engine.analyse(
        board,
        chess.engine.Limit(depth=depth),
        multipv=len(acceptable),
        root_moves=[chess.Move.from_uci(move) for move in acceptable],
    )
    if isinstance(constrained, Mapping):
        constrained = [constrained]
    accepted = [
        {"score": _score_cp(info, board.turn), "wdl": _wdl_outcome(info, board.turn)}
        for info in constrained
        if info.get("pv")
    ]
    return {
        "preserves_wdl": (
            None if best_wdl is None or not accepted
            else any(item["wdl"] == best_wdl for item in accepted)
        ),
        "acceptable_loss_cp": (
            None if not accepted else max(0, best_score - max(item["score"] for item in accepted))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stockfish", required=True, type=Path)
    parser.add_argument("--expected-stockfish-sha256", required=True)
    parser.add_argument("--baseline-depth", type=int, default=14)
    parser.add_argument("--confirmation-depth", type=int, default=20)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if args.confirmation_depth <= args.baseline_depth:
        parser.error("--confirmation-depth must exceed --baseline-depth")

    stockfish = args.stockfish.resolve(strict=True)
    stockfish_hash = _sha256_file(stockfish)
    if stockfish_hash != args.expected_stockfish_sha256.lower():
        raise SystemExit("Stockfish hash mismatch")
    sample_path = args.sample.resolve(strict=True)
    sample = json.loads(sample_path.read_text(encoding="utf-8"))

    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
    db_name = os.environ.get("DB_NAME", "chess_coach")
    puzzles, input_counts = _load_puzzles(client[db_name], sample)
    client.close()

    engine = chess.engine.SimpleEngine.popen_uci(str(stockfish))
    settings = {}
    if "Threads" in engine.options:
        settings["Threads"] = 1
    if "Hash" in engine.options:
        settings["Hash"] = 64
    if "UCI_ShowWDL" in engine.options:
        settings["UCI_ShowWDL"] = True
    if settings:
        engine.configure(settings)

    started = time.perf_counter()
    rows = []
    failures: Counter = Counter()
    try:
        for index, puzzle in enumerate(puzzles, start=1):
            try:
                baseline = _evaluate(
                    engine, puzzle["board"], puzzle["acceptable"], args.baseline_depth
                )
                confirmation = {"preserves_wdl": None, "acceptable_loss_cp": None}
                if baseline["preserves_wdl"] is False:
                    confirmation = _evaluate(
                        engine,
                        puzzle["board"],
                        puzzle["acceptable"],
                        args.confirmation_depth,
                    )
                rows.append({
                    **{axis: puzzle[axis] for axis in (
                        "pool", "difficulty", "admission_status", "concept_family"
                    )},
                    "baseline_preserves_wdl": baseline["preserves_wdl"],
                    "baseline_acceptable_loss_cp": baseline["acceptable_loss_cp"],
                    "confirmation_preserves_wdl": confirmation["preserves_wdl"],
                    "confirmation_acceptable_loss_cp": confirmation["acceptable_loss_cp"],
                })
            except (ValueError, RuntimeError, KeyError, chess.engine.EngineError) as exc:
                failures[type(exc).__name__] += 1
            if index % 50 == 0:
                print(json.dumps({
                    "progress": index,
                    "total": len(puzzles),
                    "completed": len(rows),
                    "baseline_mismatches": sum(
                        row["baseline_preserves_wdl"] is False for row in rows
                    ),
                }), file=sys.stderr, flush=True)
    finally:
        engine.quit()

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "aggregate_only": True,
        "privacy": {
            "positions_moves_and_identifiers_exported": False,
            "player_trajectories_exported": False,
        },
        "source": {
            "database": db_name,
            "sample_filename": sample_path.name,
            "sample_records_sha256": sample.get("selected", {}).get("records_sha256"),
            "source_revision": args.source_revision,
        },
        "provenance": {
            "stockfish_sha256": stockfish_hash,
            "baseline_depth": args.baseline_depth,
            "confirmation_depth": args.confirmation_depth,
            "threads": 1,
            "hash_mb": 64,
            "show_wdl": True,
        },
        "counts": {
            "input": dict(sorted(input_counts.items())),
            "completed": len(rows),
            "failures": dict(sorted(failures.items())),
        },
        "overall": summarize(rows),
        "segments": _segments(rows),
        "runtime": {
            "wall_seconds": time.perf_counter() - started,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "overall": result["overall"]}, sort_keys=True))


if __name__ == "__main__":
    main()
