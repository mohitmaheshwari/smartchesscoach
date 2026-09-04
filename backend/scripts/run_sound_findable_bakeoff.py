#!/usr/bin/env python3
"""Evaluate Stockfish-safe, human-findable moves on a frozen mistake sample.

This is a read-only research command. It reconstructs positions inside the
production container, runs bounded MultiPV plus the pinned Otter model, and
exports aggregates only. No FEN, PGN, player identity, move, or engine line is
written to the result.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import chess
import chess.engine
from pymongo import MongoClient

try:
    import resource
except ImportError:  # pragma: no cover - Windows development host
    resource = None

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
DEPLOYED_BACKEND_DIR = Path("/app/backend")
if DEPLOYED_BACKEND_DIR.is_dir() and str(DEPLOYED_BACKEND_DIR) not in sys.path:
    # Research adapters above remain frozen; the baseline guard is deliberately
    # imported from the code actually deployed in this container.
    sys.path.append(str(DEPLOYED_BACKEND_DIR))

from coach_play.teaching.candidate_generator import generate_candidates  # noqa: E402
from research.human_chess_intelligence.corpus_inputs import (  # noqa: E402
    build_user_trajectory,
    match_observations_to_trajectory,
)
from research.human_chess_intelligence.policy_contract import HumanPolicyRequest  # noqa: E402
from research.human_chess_intelligence.providers import (  # noqa: E402
    history_reaches_fen,
    predict_otter,
)

SCHEMA_VERSION = "human_chess.sound_findable_bakeoff.v1"
DEFAULT_BANDS = (0, 25, 50, 75, 100, 150)
MATE_SCORE_CP = 100_000


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quantiles(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"minimum": None, "p25": None, "median": None, "p75": None, "p90": None, "maximum": None}
    ordered = sorted(float(value) for value in values)

    def at(fraction: float) -> float:
        return ordered[round((len(ordered) - 1) * fraction)]

    return {
        "minimum": ordered[0],
        "p25": at(0.25),
        "median": at(0.5),
        "p75": at(0.75),
        "p90": at(0.9),
        "maximum": ordered[-1],
    }


def _score_cp(info: Mapping[str, Any], turn: chess.Color) -> int:
    score = info.get("score")
    if score is None:
        raise ValueError("analysis lacks score")
    value = score.pov(turn).score(mate_score=MATE_SCORE_CP)
    if value is None:
        raise ValueError("analysis score cannot be normalized")
    return int(value)


def _wdl_tuple(info: Mapping[str, Any], turn: chess.Color) -> Optional[tuple[int, int, int]]:
    value = info.get("wdl")
    if value is None:
        return None
    relative = value.pov(turn)
    return int(relative.wins), int(relative.draws), int(relative.losses)


def _wdl_outcome(wdl: Optional[tuple[int, int, int]]) -> Optional[str]:
    if wdl is None:
        return None
    labels = ("win", "draw", "loss")
    # Prefer draw only when the engine returns an exact tie for the largest mass.
    index = max(range(3), key=lambda item: (wdl[item], item == 1))
    return labels[index]


def _safe_human_choice(
    candidates: Sequence[Mapping[str, Any]],
    probabilities: Mapping[str, float],
    band_cp: int,
) -> Optional[Dict[str, Any]]:
    safe = [candidate for candidate in candidates if int(candidate["loss_cp"]) <= band_cp]
    if not safe:
        return None
    return dict(max(
        safe,
        key=lambda candidate: (
            float(probabilities.get(str(candidate["move_uci"]), 0.0)),
            -int(candidate["loss_cp"]),
            str(candidate["move_uci"]),
        ),
    ))


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def _summarize(records: Sequence[Mapping[str, Any]], bands: Sequence[int]) -> Dict[str, Any]:
    output: Dict[str, Any] = {"positions": len(records), "bands": {}}
    for band in bands:
        key = str(band)
        rows = [row["bands"][key] for row in records if key in row["bands"]]
        output["bands"][key] = {
            "positions": len(rows),
            "safe_candidate_count": _quantiles([row["safe_count"] for row in rows]),
            "multiple_safe_rate": _rate(sum(row["safe_count"] > 1 for row in rows), len(rows)),
            "multipv_truncation_risk_rate": _rate(sum(row["truncation_risk"] for row in rows), len(rows)),
            "human_choice_differs_from_engine_best_rate": _rate(
                sum(row["choice_differs"] for row in rows), len(rows)
            ),
            "selected_loss_cp": _quantiles([row["selected_loss_cp"] for row in rows]),
            "selected_model_rank": _quantiles([row["selected_model_rank"] for row in rows]),
            "selected_probability": _quantiles([row["selected_probability"] for row in rows]),
            "engine_best_probability": _quantiles([row["engine_best_probability"] for row in rows]),
            "probability_uplift": _quantiles([row["probability_uplift"] for row in rows]),
            "engine_wdl_outcome_preserved_rate": _rate(
                sum(row["wdl_outcome_preserved"] is True for row in rows),
                sum(row["wdl_outcome_preserved"] is not None for row in rows),
            ),
        }

    guard_rows = [row["current_guard"] for row in records if row.get("current_guard")]
    output["current_play_with_coach_guard"] = {
        "positions": len(guard_rows),
        "candidate_count": _quantiles([row["candidate_count"] for row in guard_rows]),
        "moves_outside_probe_multipv": sum(row["moves_outside_probe_multipv"] for row in guard_rows),
        "human_choice_available_positions": sum(row["human_choice_available"] for row in guard_rows),
        "selected_loss_cp": _quantiles([
            row["selected_loss_cp"] for row in guard_rows if row["selected_loss_cp"] is not None
        ]),
        "selected_exceeds_nominal_150cp_rate": _rate(
            sum(
                row["selected_loss_cp"] is not None and row["selected_loss_cp"] > 150
                for row in guard_rows
            ),
            sum(row["selected_loss_cp"] is not None for row in guard_rows),
        ),
        "engine_wdl_outcome_preserved_rate": _rate(
            sum(row["wdl_outcome_preserved"] is True for row in guard_rows),
            sum(row["wdl_outcome_preserved"] is not None for row in guard_rows),
        ),
    }
    return output


def _segment_summaries(
    records: Sequence[Mapping[str, Any]], bands: Sequence[int]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for axis in ("rating_band", "phase", "error_band", "concept_family"):
        grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for row in records:
            grouped[str(row[axis])].append(row)
        result[axis] = {
            value: _summarize(rows, bands)
            for value, rows in sorted(grouped.items())
        }
    return result


def _load_examples(db, manifest: Mapping[str, Any], sample: Mapping[str, Any]):
    selected = list(sample.get("selected", {}).get("records") or [])
    selected_games = {str(row["game_id"]) for row in selected}
    manifest_by_game = {
        str(row["game_id"]): row
        for row in manifest.get("games", [])
        if str(row.get("game_id")) in selected_games
    }
    games = {
        str(row["game_id"]): row
        for row in db.games.find(
            {"game_id": {"$in": sorted(selected_games)}},
            {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
        )
    }
    observations = {}
    cursor = db.move_observations.find(
        {
            "game_id": {"$in": sorted(selected_games)},
            "schema_version": {"$gte": 16},
        },
        {
            "_id": 0,
            "game_id": 1,
            "ply": 1,
            "move_number": 1,
            "fen_before": 1,
            "move_uci": 1,
            "phase": 1,
            "cp_loss": 1,
            "missed_pattern": 1,
            "schema_version": 1,
        },
    ).sort([("game_id", 1), ("ply", 1), ("schema_version", -1)])
    for row in cursor:
        observations.setdefault((str(row["game_id"]), int(row.get("ply") or 0)), row)

    counts: Counter = Counter()
    examples = []
    trajectories = {}
    for selected_row in selected:
        counts["selected_records"] += 1
        game_id = str(selected_row["game_id"])
        record = manifest_by_game.get(game_id)
        game = games.get(game_id)
        observation = observations.get((game_id, int(selected_row["ply"])))
        if not record or not game or not observation:
            counts["missing_join_input"] += 1
            continue
        if game_id not in trajectories:
            try:
                trajectories[game_id] = build_user_trajectory(
                    str(game.get("pgn") or ""), str(game.get("user_color") or "")
                )
            except Exception:
                trajectories[game_id] = None
        trajectory = trajectories[game_id]
        if trajectory is None:
            counts["trajectory_error"] += 1
            continue
        joined, failures = match_observations_to_trajectory([observation], trajectory)
        if failures or not joined:
            counts["observation_join_failure"] += 1
            continue
        _, entry = joined[0]
        opponent_elo = record.get("opponent_rating")
        if not isinstance(opponent_elo, (int, float)):
            counts["missing_opponent_elo"] += 1
            continue
        if entry.time_control is None:
            counts["missing_numeric_time_control"] += 1
            continue
        try:
            request = HumanPolicyRequest(
                fen=entry.fen,
                player_elo=int(record["player_rating"]),
                opponent_elo=int(opponent_elo),
                history_moves=entry.history_moves,
                time_control=entry.time_control,
                clock_fraction=entry.clock_fraction,
            )
        except ValueError:
            counts["invalid_policy_request"] += 1
            continue
        if not history_reaches_fen(request):
            counts["history_does_not_reconstruct_position"] += 1
            continue
        examples.append({
            "request": request,
            "rating_band": selected_row["rating_band"],
            "phase": selected_row["phase"],
            "error_band": selected_row["error_band"],
            "concept_family": selected_row["concept_family"],
        })
        counts["eligible_examples"] += 1
    return examples, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stockfish", required=True, type=Path)
    parser.add_argument("--expected-stockfish-sha256", required=True)
    parser.add_argument("--otter-model", required=True, type=Path)
    parser.add_argument("--expected-otter-sha256", required=True)
    parser.add_argument("--expected-otter-version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--depth", type=int, default=16)
    parser.add_argument("--multipv", type=int, default=12)
    parser.add_argument("--bands", default=",".join(map(str, DEFAULT_BANDS)))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    bands = sorted({int(value) for value in args.bands.split(",")})
    if not bands or any(value < 0 for value in bands):
        parser.error("--bands must contain non-negative integer centipawn candidates")
    if args.depth <= 0 or args.multipv <= 0:
        parser.error("--depth and --multipv must be positive")

    stockfish = args.stockfish.resolve(strict=True)
    otter_path = args.otter_model.resolve(strict=True)
    stockfish_hash = _sha256_file(stockfish)
    otter_hash = _sha256_file(otter_path)
    if stockfish_hash != args.expected_stockfish_sha256.lower():
        raise SystemExit(f"Stockfish SHA-256 mismatch: {stockfish_hash}")
    if otter_hash != args.expected_otter_sha256.lower():
        raise SystemExit(f"Otter SHA-256 mismatch: {otter_hash}")
    otter_version = importlib.metadata.version("otter-chess")
    if otter_version != args.expected_otter_version:
        raise SystemExit(f"Otter version mismatch: {otter_version}")

    manifest_path = args.manifest.resolve(strict=True)
    sample_path = args.sample.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    examples, input_counts = _load_examples(db, manifest, sample)
    client.close()
    if args.limit:
        examples = examples[:args.limit]
        input_counts["limited_examples"] = len(examples)

    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from otter_chess import OtterModel

        torch.backends.nnpack.set_flags(False)
        model = OtterModel(checkpoint_path=str(otter_path), device="cpu")

    records = []
    failures: Counter = Counter()
    started = time.perf_counter()
    engine = chess.engine.SimpleEngine.popen_uci(str(stockfish))
    try:
        configurable = engine.options
        settings = {}
        if "Threads" in configurable:
            settings["Threads"] = 1
        if "Hash" in configurable:
            settings["Hash"] = 64
        if "UCI_ShowWDL" in configurable:
            settings["UCI_ShowWDL"] = True
        if settings:
            engine.configure(settings)

        for index, example in enumerate(examples, start=1):
            request = example["request"]
            board = chess.Board(request.fen)
            try:
                evidence = predict_otter(
                    request,
                    model=model,
                    model_version=otter_version,
                    model_sha256=otter_hash,
                    mode="history_only",
                )
                probabilities = {move.move_uci: move.probability for move in evidence.moves}
                model_ranks = {
                    move.move_uci: rank
                    for rank, move in enumerate(evidence.moves, start=1)
                }
                legal_count = board.legal_moves.count()
                analysis = engine.analyse(
                    board,
                    chess.engine.Limit(depth=args.depth),
                    multipv=min(args.multipv, legal_count),
                )
                if isinstance(analysis, Mapping):
                    analysis = [analysis]
                candidates = []
                for rank, info in enumerate(analysis, start=1):
                    if not info.get("pv"):
                        continue
                    move = info["pv"][0]
                    candidates.append({
                        "move_uci": move.uci(),
                        "rank": rank,
                        "score_cp": _score_cp(info, board.turn),
                        "wdl": _wdl_tuple(info, board.turn),
                    })
                if not candidates:
                    raise ValueError("MultiPV returned no candidates")
                best_score = candidates[0]["score_cp"]
                best_outcome = _wdl_outcome(candidates[0]["wdl"])
                for candidate in candidates:
                    candidate["loss_cp"] = max(0, best_score - candidate["score_cp"])

                row = {
                    **{axis: example[axis] for axis in (
                        "rating_band", "phase", "error_band", "concept_family"
                    )},
                    "bands": {},
                }
                for band in bands:
                    chosen = _safe_human_choice(candidates, probabilities, band)
                    if chosen is None:
                        continue
                    safe_count = sum(candidate["loss_cp"] <= band for candidate in candidates)
                    row["bands"][str(band)] = {
                        "safe_count": safe_count,
                        "truncation_risk": (
                            legal_count > len(candidates)
                            and candidates[-1]["loss_cp"] <= band
                        ),
                        "choice_differs": chosen["rank"] != 1,
                        "selected_loss_cp": chosen["loss_cp"],
                        "selected_model_rank": model_ranks.get(chosen["move_uci"], legal_count + 1),
                        "selected_probability": probabilities.get(chosen["move_uci"], 0.0),
                        "engine_best_probability": probabilities.get(
                            candidates[0]["move_uci"], 0.0
                        ),
                        "probability_uplift": (
                            probabilities.get(chosen["move_uci"], 0.0)
                            - probabilities.get(candidates[0]["move_uci"], 0.0)
                        ),
                        "wdl_outcome_preserved": (
                            None if best_outcome is None
                            else _wdl_outcome(chosen["wdl"]) == best_outcome
                        ),
                    }

                guard = generate_candidates(
                    board,
                    engine,
                    max_candidates=8,
                    max_eval_drop_cp=150,
                    depth=10,
                    teaching_mode=False,
                )
                probe_by_move = {candidate["move_uci"]: candidate for candidate in candidates}
                guard_known = [
                    probe_by_move[candidate.move.uci()]
                    for candidate in guard
                    if candidate.move.uci() in probe_by_move
                ]
                guard_choice = max(
                    guard_known,
                    key=lambda candidate: (
                        probabilities.get(candidate["move_uci"], 0.0),
                        -candidate["loss_cp"],
                        candidate["move_uci"],
                    ),
                    default=None,
                )
                row["current_guard"] = {
                    "candidate_count": len(guard),
                    "moves_outside_probe_multipv": len(guard) - len(guard_known),
                    "human_choice_available": guard_choice is not None,
                    "selected_loss_cp": (
                        guard_choice["loss_cp"] if guard_choice is not None else None
                    ),
                    "wdl_outcome_preserved": (
                        None if guard_choice is None or best_outcome is None
                        else _wdl_outcome(guard_choice["wdl"]) == best_outcome
                    ),
                }
                records.append(row)
            except (ValueError, RuntimeError, chess.engine.EngineError) as exc:
                failures[type(exc).__name__] += 1
            if index % 25 == 0:
                print(json.dumps({
                    "progress": index,
                    "eligible": len(examples),
                    "completed": len(records),
                    "failures": sum(failures.values()),
                }), file=sys.stderr, flush=True)
    finally:
        engine.quit()

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "privacy": {
            "raw_positions_exported": False,
            "raw_moves_exported": False,
            "player_identifiers_exported": False,
            "engine_lines_exported": False,
        },
        "authority_boundary": {
            "soundness_authority": "Stockfish",
            "human_model_role": "rank_only_within_each_stockfish_safe_candidate_set",
            "production_threshold_locked": False,
        },
        "source": {
            "database": os.environ.get("DB_NAME", "chess_coach"),
            "manifest_filename": manifest_path.name,
            "manifest_records_sha256": manifest.get("hashes", {}).get("eligible_records_sha256"),
            "sample_filename": sample_path.name,
            "sample_records_sha256": sample.get("selected", {}).get("records_sha256"),
            "source_revision": args.source_revision,
        },
        "provenance": {
            "stockfish": {
                "binary_basename": stockfish.name,
                "sha256": stockfish_hash,
                "depth": args.depth,
                "multipv": args.multipv,
                "threads": 1,
                "hash_mb": 64,
                "show_wdl": True,
            },
            "otter": {
                "package_version": otter_version,
                "model_basename": otter_path.name,
                "model_sha256": otter_hash,
                "mode": "history_only",
            },
            "candidate_loss_bands_cp": bands,
            "current_guard_baseline": {
                "source": "coach_play.teaching.candidate_generator.generate_candidates",
                "depth": 10,
                "multipv": 8,
                "nominal_soft_band_cp": 150,
                "minimum_candidates_exception": 4,
                "hang_filter": True,
            },
        },
        "counts": {
            "input": dict(sorted(input_counts.items())),
            "completed": len(records),
            "failures": dict(sorted(failures.items())),
        },
        "overall": _summarize(records, bands),
        "segments": _segment_summaries(records, bands),
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
        "wall_seconds": result["runtime"]["wall_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
