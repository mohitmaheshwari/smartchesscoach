#!/usr/bin/env python3
"""Score admitted puzzle answers with Maia-2 and verify likely distractors.

The output is aggregate-only and shadow-only. It does not claim empirical
difficulty calibration because historical attempts lack solver rating and
support-level evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import chess
import chess.engine
from bson import ObjectId
from pymongo import MongoClient

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.policy_contract import HumanPolicyRequest  # noqa: E402
from research.human_chess_intelligence.providers import predict_maia2  # noqa: E402

SCHEMA_VERSION = "human_chess.puzzle_stage3_shadow_bakeoff.v1"
MATE_SCORE_CP = 100_000


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


def _average_ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2.0
        for offset in range(start, end):
            ranks[order[offset]] = average
        start = end
    return ranks


def spearman(values_a: Sequence[float], values_b: Sequence[float]) -> Optional[float]:
    if len(values_a) != len(values_b) or len(values_a) < 3:
        return None
    a = _average_ranks(values_a)
    b = _average_ranks(values_b)
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    denominator = math.sqrt(
        sum((x - mean_a) ** 2 for x in a)
        * sum((y - mean_b) ** 2 for y in b)
    )
    return numerator / denominator if denominator else None


def _score_cp(info: Mapping[str, Any], turn: chess.Color) -> int:
    value = info["score"].pov(turn).score(mate_score=MATE_SCORE_CP)
    if value is None:
        raise ValueError("engine score missing")
    return int(value)


def _wdl_outcome(info: Mapping[str, Any], turn: chess.Color) -> Optional[str]:
    value = info.get("wdl")
    if value is None:
        return None
    wdl = value.pov(turn)
    masses = (int(wdl.wins), int(wdl.draws), int(wdl.losses))
    labels = ("win", "draw", "loss")
    return labels[max(range(3), key=lambda index: (masses[index], index == 1))]


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def summarize(records: Sequence[Mapping[str, Any]], ratings: Sequence[int]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"positions": len(records), "ratings": {}}
    difficulty_score = {"easy": 2.0, "medium": 1.0, "hard": 0.0}
    for rating in ratings:
        key = str(rating)
        rows = [row["ratings"][key] for row in records if key in row["ratings"]]
        cp_pairs = [
            (float(record["cp_loss"]), float(record["ratings"][key]["target_probability"]))
            for record in records
            if isinstance(record.get("cp_loss"), (int, float)) and key in record["ratings"]
        ]
        difficulty_pairs = [
            (difficulty_score[record["difficulty"]], float(record["ratings"][key]["target_probability"]))
            for record in records
            if record.get("difficulty") in difficulty_score and key in record["ratings"]
        ]
        thresholds = {}
        for threshold in (25, 50, 100, 150, 300):
            thresholds[str(threshold)] = _rate(
                sum(row["distractor_loss_cp"] >= threshold for row in rows), len(rows)
            )
        result["ratings"][key] = {
            "positions": len(rows),
            "target_probability": _quantiles(row["target_probability"] for row in rows),
            "best_acceptable_model_rank": _quantiles(row["best_acceptable_rank"] for row in rows),
            "top_wrong_probability": _quantiles(row["distractor_probability"] for row in rows),
            "target_probability_margin_over_top_wrong": _quantiles(
                row["target_probability"] - row["distractor_probability"] for row in rows
            ),
            "engine_verified_top_wrong_loss_cp": _quantiles(
                row["distractor_loss_cp"] for row in rows
            ),
            "top_wrong_changes_engine_wdl_rate": _rate(
                sum(row["distractor_changes_wdl"] is True for row in rows),
                sum(row["distractor_changes_wdl"] is not None for row in rows),
            ),
            "top_wrong_loss_at_least_cp": thresholds,
            "acceptable_answer_preserves_engine_wdl_rate": _rate(
                sum(row["acceptable_preserves_wdl"] is True for row in rows),
                sum(row["acceptable_preserves_wdl"] is not None for row in rows),
            ),
            "spearman_cp_loss_vs_target_probability": spearman(
                [pair[0] for pair in cp_pairs], [pair[1] for pair in cp_pairs]
            ),
            "spearman_current_easiness_label_vs_target_probability": spearman(
                [pair[0] for pair in difficulty_pairs], [pair[1] for pair in difficulty_pairs]
            ),
        }
    monotonic = 0
    for record in records:
        values = [record["ratings"][str(rating)]["target_probability"] for rating in ratings]
        monotonic += all(left <= right + 1e-12 for left, right in zip(values, values[1:]))
    result["target_probability_non_decreasing_with_rating_rate"] = _rate(monotonic, len(records))
    return result


def _segments(records: Sequence[Mapping[str, Any]], ratings: Sequence[int]) -> Dict[str, Any]:
    output = {}
    for axis in ("pool", "difficulty", "admission_status", "concept_family"):
        grouped = defaultdict(list)
        for record in records:
            grouped[str(record[axis])].append(record)
        output[axis] = {
            value: summarize(rows, ratings)
            for value, rows in sorted(grouped.items())
        }
    return output


def _load_puzzles(db, sample: Mapping[str, Any]):
    records = sample.get("selected", {}).get("records") or []
    community_refs = [
        ObjectId(row["puzzle_ref"])
        for row in records
        if row["pool"] == "community_puzzles" and ObjectId.is_valid(row["puzzle_ref"])
    ]
    training_refs = [
        row["puzzle_ref"]
        for row in records
        if row["pool"] == "community_training_positions"
    ]
    projection = {
        "position_id": 1,
        "fen": 1,
        "fen_before": 1,
        "difficulty": 1,
        "cp_loss": 1,
        "verified_admission": 1,
    }
    community = {
        str(row["_id"]): row
        for row in db.community_puzzles.find({"_id": {"$in": community_refs}}, projection)
    }
    training = {
        str(row.get("position_id")): row
        for row in db.community_training_positions.find(
            {"position_id": {"$in": training_refs}}, projection
        )
    }
    output = []
    counts: Counter = Counter()
    for sample_row in records:
        counts["sample_records"] += 1
        source = community if sample_row["pool"] == "community_puzzles" else training
        puzzle = source.get(str(sample_row["puzzle_ref"]))
        if puzzle is None:
            counts["missing_puzzle"] += 1
            continue
        admission = puzzle.get("verified_admission") or {}
        acceptable = tuple(sorted({
            str(move).lower() for move in admission.get("acceptable_moves_uci") or []
        }))
        try:
            board = chess.Board(str(puzzle.get("fen") or puzzle.get("fen_before") or ""))
            legal = {move.uci() for move in board.legal_moves}
            if not acceptable or not set(acceptable).issubset(legal):
                raise ValueError
        except ValueError:
            counts["invalid_position_or_answer"] += 1
            continue
        output.append({
            "board": board,
            "acceptable": acceptable,
            "pool": sample_row["pool"],
            "difficulty": sample_row["difficulty"],
            "admission_status": sample_row["admission_status"],
            "concept_family": sample_row["concept_family"],
            "cp_loss": puzzle.get("cp_loss"),
        })
        counts["eligible"] += 1
    return output, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maia-model", required=True, type=Path)
    parser.add_argument("--expected-maia-sha256", required=True)
    parser.add_argument("--expected-maia-version", required=True)
    parser.add_argument("--stockfish", required=True, type=Path)
    parser.add_argument("--expected-stockfish-sha256", required=True)
    parser.add_argument("--ratings", default="800,1000,1200,1400")
    parser.add_argument("--engine-depth", type=int, default=14)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    ratings = sorted({int(value) for value in args.ratings.split(",")})
    if not ratings or any(rating < 600 or rating > 1500 for rating in ratings):
        parser.error("--ratings must be within the product's 600-1500 target range")

    maia_path = args.maia_model.resolve(strict=True)
    stockfish = args.stockfish.resolve(strict=True)
    maia_hash = _sha256_file(maia_path)
    stockfish_hash = _sha256_file(stockfish)
    if maia_hash != args.expected_maia_sha256.lower():
        raise SystemExit("Maia model hash mismatch")
    if stockfish_hash != args.expected_stockfish_sha256.lower():
        raise SystemExit("Stockfish hash mismatch")
    maia_version = importlib.metadata.version("maia2")
    if maia_version != args.expected_maia_version:
        raise SystemExit("Maia package version mismatch")

    sample_path = args.sample.resolve(strict=True)
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
    db_name = os.environ.get("DB_NAME", "chess_coach")
    puzzles, input_counts = _load_puzzles(client[db_name], sample)
    client.close()
    if args.limit:
        puzzles = puzzles[:args.limit]
        input_counts["limited"] = len(puzzles)

    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from maia2.inference import prepare
        from maia2.model import from_pretrained

        torch.backends.nnpack.set_flags(False)
        model = from_pretrained("rapid", device="cpu", save_root=str(maia_path.parent))
        prepared = prepare()

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
    records = []
    failures: Counter = Counter()
    try:
        for index, puzzle in enumerate(puzzles, start=1):
            board = puzzle["board"]
            rating_evidence = {}
            distractor_moves = set()
            try:
                for rating in ratings:
                    request = HumanPolicyRequest(
                        fen=board.fen(),
                        player_elo=rating,
                        opponent_elo=rating,
                    )
                    evidence = predict_maia2(
                        request,
                        model=model,
                        prepared=prepared,
                        model_version=maia_version,
                        model_sha256=maia_hash,
                        weight_family="rapid",
                    )
                    probabilities = {move.move_uci: move.probability for move in evidence.moves}
                    ranks = {move.move_uci: rank for rank, move in enumerate(evidence.moves, start=1)}
                    wrong = next(
                        move for move in evidence.moves
                        if move.move_uci not in puzzle["acceptable"]
                    )
                    distractor_moves.add(chess.Move.from_uci(wrong.move_uci))
                    rating_evidence[str(rating)] = {
                        "target_probability": sum(
                            probabilities.get(move, 0.0) for move in puzzle["acceptable"]
                        ),
                        "best_acceptable_rank": min(
                            ranks.get(move, len(ranks) + 1) for move in puzzle["acceptable"]
                        ),
                        "distractor_move": wrong.move_uci,
                        "distractor_probability": wrong.probability,
                    }

                best_info = engine.analyse(board, chess.engine.Limit(depth=args.engine_depth))
                best_score = _score_cp(best_info, board.turn)
                best_outcome = _wdl_outcome(best_info, board.turn)
                root_moves = sorted(
                    distractor_moves
                    | {chess.Move.from_uci(move) for move in puzzle["acceptable"]},
                    key=lambda move: move.uci(),
                )
                constrained = engine.analyse(
                    board,
                    chess.engine.Limit(depth=args.engine_depth),
                    multipv=len(root_moves),
                    root_moves=root_moves,
                )
                if isinstance(constrained, Mapping):
                    constrained = [constrained]
                engine_by_move = {
                    info["pv"][0].uci(): {
                        "loss_cp": max(0, best_score - _score_cp(info, board.turn)),
                        "outcome": _wdl_outcome(info, board.turn),
                    }
                    for info in constrained
                    if info.get("pv")
                }
                acceptable_engine = [
                    engine_by_move[move] for move in puzzle["acceptable"]
                    if move in engine_by_move
                ]
                acceptable_preserves = (
                    None if best_outcome is None or not acceptable_engine
                    else any(item["outcome"] == best_outcome for item in acceptable_engine)
                )
                for rating in ratings:
                    item = rating_evidence[str(rating)]
                    engine_item = engine_by_move[item.pop("distractor_move")]
                    item["distractor_loss_cp"] = engine_item["loss_cp"]
                    item["distractor_changes_wdl"] = (
                        None if best_outcome is None
                        else engine_item["outcome"] != best_outcome
                    )
                    item["acceptable_preserves_wdl"] = acceptable_preserves
                records.append({
                    **{axis: puzzle[axis] for axis in (
                        "pool", "difficulty", "admission_status", "concept_family", "cp_loss"
                    )},
                    "ratings": rating_evidence,
                })
            except (ValueError, RuntimeError, StopIteration, KeyError, chess.engine.EngineError) as exc:
                failures[type(exc).__name__] += 1
            if index % 25 == 0:
                print(json.dumps({
                    "progress": index,
                    "total": len(puzzles),
                    "completed": len(records),
                    "failures": sum(failures.values()),
                }), file=sys.stderr, flush=True)
    finally:
        engine.quit()

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "shadow_only": True,
        "outcome_calibration": {
            "performed": False,
            "reason": "historical attempts lack attempt-time solver rating and support-level evidence",
        },
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
            "maia2": {
                "package_version": maia_version,
                "model_sha256": maia_hash,
                "weight_family": "rapid",
                "rating_grid": ratings,
            },
            "stockfish": {
                "sha256": stockfish_hash,
                "depth": args.engine_depth,
                "threads": 1,
                "hash_mb": 64,
                "show_wdl": True,
            },
        },
        "counts": {
            "input": dict(sorted(input_counts.items())),
            "completed": len(records),
            "failures": dict(sorted(failures.items())),
        },
        "overall": summarize(records, ratings),
        "segments": _segments(records, ratings),
        "runtime": {
            "wall_seconds": time.perf_counter() - started,
            "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "completed": len(records),
        "failures": dict(failures),
        "runtime": result["runtime"],
        "overall": result["overall"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
