"""Run one human-policy candidate beside MongoDB and export aggregates only.

The command is intentionally read-only: it loads the frozen chronological
manifest, reconstructs held-out user moves inside the production host, scores
one candidate, and writes aggregate metrics with provenance. Raw PGNs, move
histories, FENs, user IDs, game IDs, names, and emails are never written.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import chess
from pymongo import MongoClient

try:
    import resource
except ImportError:  # pragma: no cover - Windows development host
    resource = None

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.bakeoff_metrics import (  # noqa: E402
    LegalMoveFrequencyBaseline,
    SegmentedPolicyMetrics,
)
from research.human_chess_intelligence.corpus_inputs import (  # noqa: E402
    build_user_trajectory,
    match_observations_to_trajectory,
    normalized_position_key,
    split_game_records,
)
from research.human_chess_intelligence.policy_contract import (  # noqa: E402
    HumanPolicyRequest,
    PolicyContractError,
)
from research.human_chess_intelligence.providers import (  # noqa: E402
    history_reaches_fen,
    predict_maia2,
    predict_otter,
)

SCHEMA_VERSION = "human_policy_corpus_bakeoff.v1"
OBSERVATION_SCHEMA_MIN = 16


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_games(db, records: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ids = [row["game_id"] for row in records]
    projection = {
        "_id": 0,
        "game_id": 1,
        "pgn": 1,
        "user_color": 1,
        "eco": 1,
        "opening": 1,
    }
    return {
        row["game_id"]: row
        for row in db.games.find({"game_id": {"$in": ids}}, projection)
        if row.get("game_id")
    }


def _load_observations(db, game_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    projection = {
        "_id": 0,
        "game_id": 1,
        "fen_before": 1,
        "move_uci": 1,
        "move_number": 1,
        "ply": 1,
        "phase": 1,
        "color": 1,
        "cp_loss": 1,
    }
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    cursor = db.move_observations.find(
        {"game_id": {"$in": list(game_ids)}, "schema_version": {"$gte": OBSERVATION_SCHEMA_MIN}},
        projection,
    )
    for row in cursor:
        grouped[str(row["game_id"])].append(row)
    return grouped


def _build_examples(
    game_records: Sequence[Mapping[str, Any]],
    game_docs: Mapping[str, Mapping[str, Any]],
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[List[Dict[str, Any]], Counter]:
    counts: Counter = Counter()
    examples: List[Dict[str, Any]] = []
    for record in sorted(game_records, key=lambda row: (row["user_id"], row["played_date"], row["game_id"])):
        counts["manifest_games"] += 1
        game_id = str(record["game_id"])
        game = game_docs.get(game_id)
        if not game:
            counts["missing_game_document"] += 1
            continue
        opponent_elo = record.get("opponent_rating")
        if not isinstance(opponent_elo, (int, float)):
            counts["missing_opponent_elo"] += 1
            continue
        try:
            trajectory = build_user_trajectory(str(game.get("pgn") or ""), str(game.get("user_color") or ""))
        except Exception:
            counts["trajectory_error"] += 1
            continue
        rows = list(observations.get(game_id, ()))
        counts["stored_observations"] += len(rows)
        joined, failures = match_observations_to_trajectory(rows, trajectory)
        counts["observation_join_failures"] += failures
        for observation, entry in joined:
            try:
                board = chess.Board(entry.fen)
                move = chess.Move.from_uci(entry.move_uci)
            except ValueError:
                counts["invalid_position_or_move"] += 1
                continue
            if move not in board.legal_moves:
                counts["illegal_actual_move"] += 1
                continue
            request = HumanPolicyRequest(
                fen=entry.fen,
                player_elo=int(record["player_rating"]),
                opponent_elo=int(opponent_elo),
                history_moves=entry.history_moves,
                time_control=entry.time_control,
                clock_fraction=entry.clock_fraction,
            )
            examples.append({
                "request": request,
                "actual_move_uci": entry.move_uci,
                "phase": str(observation.get("phase") or "unknown"),
                "color": str(observation.get("color") or game.get("user_color") or "unknown"),
                "cp_loss": int(observation.get("cp_loss") or 0),
                "eco": game.get("eco") or game.get("opening"),
                "position_key": normalized_position_key(entry.fen),
            })
            counts["joined_examples"] += 1

    deduplicated: List[Dict[str, Any]] = []
    seen = set()
    for example in examples:
        key = example["position_key"]
        if key in seen:
            counts["duplicate_evaluation_positions_removed"] += 1
            continue
        seen.add(key)
        deduplicated.append(example)
    counts["deduplicated_examples"] = len(deduplicated)
    return deduplicated, counts


def _train_baseline(
    history_records: Sequence[Mapping[str, Any]],
    game_docs: Mapping[str, Mapping[str, Any]],
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
    evaluation_position_keys: set[str],
) -> tuple[LegalMoveFrequencyBaseline, Counter]:
    baseline = LegalMoveFrequencyBaseline(alpha=1.0)
    counts: Counter = Counter()
    records_by_id = {str(row["game_id"]): row for row in history_records}
    for game_id in sorted(records_by_id):
        record = records_by_id[game_id]
        game = game_docs.get(game_id, {})
        for observation in observations.get(game_id, ()):
            try:
                position_key = normalized_position_key(str(observation.get("fen_before") or ""))
                move_uci = str(observation.get("move_uci") or "").lower()
                if chess.Move.from_uci(move_uci) not in chess.Board(str(observation["fen_before"])).legal_moves:
                    raise ValueError("illegal")
            except (KeyError, ValueError):
                counts["invalid_history_observation"] += 1
                continue
            if position_key in evaluation_position_keys:
                counts["cross_split_duplicate_positions_removed"] += 1
                continue
            baseline.observe(
                player_elo=int(record["player_rating"]),
                phase=str(observation.get("phase") or "unknown"),
                eco=game.get("eco") or game.get("opening"),
                move_uci=move_uci,
            )
            counts["fitting_observations"] += 1
    return baseline, counts


def _model_provenance(args) -> Dict[str, Any]:
    if args.provider == "baseline":
        return {
            "provider": "legal_move_frequency",
            "configuration": "rating_band+opening_or_phase; add_one_alpha=1.0",
        }
    path = args.model_path.resolve(strict=True)
    actual_hash = _sha256_file(path)
    if actual_hash != args.expected_model_sha256.lower():
        raise SystemExit(f"model SHA-256 mismatch: {actual_hash}")
    distribution = "maia2" if args.provider == "maia2" else "otter-chess"
    actual_version = importlib.metadata.version(distribution)
    if actual_version != args.expected_package_version:
        raise SystemExit(
            f"package version mismatch: expected {args.expected_package_version}, got {actual_version}"
        )
    return {
        "provider": args.provider,
        "package_version": actual_version,
        "model_path_basename": path.name,
        "model_sha256": actual_hash,
        "weight_family": args.weight_family if args.provider == "maia2" else None,
        "otter_mode": args.otter_mode if args.provider == "otter" else None,
        "device": "cpu",
    }


def _nearest_quantile(values: Sequence[float], fraction: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return float(ordered[max(0, min(len(ordered) - 1, index))])


def _clock_distribution(examples: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    values = sorted(
        float(example["request"].clock_fraction)
        for example in examples
        if example["request"].clock_fraction is not None
    )
    return {
        "count": len(values),
        "min": values[0] if values else None,
        "p25": _nearest_quantile(values, 0.25),
        "median": _nearest_quantile(values, 0.5),
        "p75": _nearest_quantile(values, 0.75),
        "max": values[-1] if values else None,
    }


def _clock_quartile(value: Optional[float], distribution: Mapping[str, Any]) -> str:
    if value is None:
        return "not_measured"
    if value <= distribution["p25"]:
        return "q1_lowest_time_remaining"
    if value <= distribution["median"]:
        return "q2"
    if value <= distribution["p75"]:
        return "q3"
    return "q4_highest_time_remaining"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", default="min_history_10_future_5")
    parser.add_argument("--provider", required=True, choices=("baseline", "maia2", "otter"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--expected-package-version")
    parser.add_argument("--expected-model-sha256")
    parser.add_argument("--weight-family", choices=("rapid", "blitz"), default="rapid")
    parser.add_argument(
        "--otter-mode",
        choices=("observed", "history_only", "clock_only", "neutral_ablation"),
        default="observed",
    )
    parser.add_argument(
        "--require-observed-context",
        action="store_true",
        help="score only examples with validated numeric time control and pre-move clock",
    )
    parser.add_argument("--source-revision", default="unknown")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.provider != "baseline" and not all((
        args.model_path, args.expected_package_version, args.expected_model_sha256
    )):
        parser.error("model path, package version, and model SHA are required for model providers")
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")

    started = time.perf_counter()
    manifest_path = args.manifest.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    history_records, evaluation_records = split_game_records(manifest, args.split)
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    evaluation_docs = _load_games(db, evaluation_records)
    evaluation_observations = _load_observations(db, [row["game_id"] for row in evaluation_records])
    examples, input_counts = _build_examples(
        evaluation_records, evaluation_docs, evaluation_observations
    )
    require_observed = args.require_observed_context or (
        args.provider == "otter" and args.otter_mode in {"observed", "clock_only"}
    )
    if require_observed:
        before = len(examples)
        with_clock = [
            example for example in examples
            if example["request"].time_control is not None
            and example["request"].clock_fraction is not None
        ]
        input_counts["missing_observed_context_removed"] = before - len(with_clock)
        examples = [
            example for example in with_clock
            if history_reaches_fen(example["request"])
        ]
        input_counts["nonstandard_or_inconsistent_history_removed"] = (
            len(with_clock) - len(examples)
        )
        input_counts["observed_context_examples"] = len(examples)
    elif args.provider == "otter" and args.otter_mode == "history_only":
        before = len(examples)
        with_time_control = [
            example for example in examples
            if example["request"].time_control is not None
        ]
        input_counts["missing_numeric_time_control_removed"] = before - len(with_time_control)
        examples = [
            example for example in with_time_control
            if history_reaches_fen(example["request"])
        ]
        input_counts["nonstandard_or_inconsistent_history_removed"] = (
            len(with_time_control) - len(examples)
        )
        input_counts["history_context_examples"] = len(examples)
    if args.limit:
        examples = examples[:args.limit]
        input_counts["limited_examples"] = len(examples)

    clock_distribution = _clock_distribution(examples)

    provenance = _model_provenance(args)
    metrics = SegmentedPolicyMetrics()
    failures: Counter = Counter()

    if args.provider == "baseline":
        history_docs = _load_games(db, history_records)
        history_observations = _load_observations(db, [row["game_id"] for row in history_records])
        baseline, fitting_counts = _train_baseline(
            history_records,
            history_docs,
            history_observations,
            {example["position_key"] for example in examples},
        )
        for example in examples:
            request = example["request"]
            tick = time.perf_counter()
            predictions = baseline.predict(
                (move.uci() for move in chess.Board(request.fen).legal_moves),
                player_elo=request.player_elo,
                phase=example["phase"],
                eco=example["eco"],
            )
            latency_ms = (time.perf_counter() - tick) * 1000
            metrics.update(
                predictions,
                example["actual_move_uci"],
                latency_ms=latency_ms,
                player_elo=request.player_elo,
                time_control=request.time_control,
                phase=example["phase"],
                color=example["color"],
                cp_loss=example["cp_loss"],
                extra_segments={
                    "clock_quartile": _clock_quartile(
                        request.clock_fraction, clock_distribution
                    )
                },
            )
    else:
        fitting_counts = Counter()
        model_path = args.model_path.resolve(strict=True)
        with contextlib.redirect_stdout(sys.stderr):
            import torch

            # Some server CPUs cannot initialize NNPACK. Explicitly disable it
            # for every candidate so one harmless warning is not repeated for
            # every convolution.
            torch.backends.nnpack.set_flags(False)
            if args.provider == "maia2":
                from maia2.inference import prepare
                from maia2.model import from_pretrained

                model = from_pretrained(
                    args.weight_family, device="cpu", save_root=str(model_path.parent)
                )
                prepared = prepare()
            else:
                from otter_chess import OtterModel

                model = OtterModel(checkpoint_path=str(model_path), device="cpu")
                prepared = None

        for example in examples:
            request = example["request"]
            try:
                if args.provider == "maia2":
                    evidence = predict_maia2(
                        request,
                        model=model,
                        prepared=prepared,
                        model_version=provenance["package_version"],
                        model_sha256=provenance["model_sha256"],
                        weight_family=args.weight_family,
                    )
                else:
                    evidence = predict_otter(
                        request,
                        model=model,
                        model_version=provenance["package_version"],
                        model_sha256=provenance["model_sha256"],
                        mode=args.otter_mode,
                    )
            except (PolicyContractError, ValueError, RuntimeError) as exc:
                failures[type(exc).__name__] += 1
                continue
            metrics.update(
                evidence.moves,
                example["actual_move_uci"],
                latency_ms=evidence.latency_ms,
                player_elo=request.player_elo,
                time_control=request.time_control,
                phase=example["phase"],
                color=example["color"],
                cp_loss=example["cp_loss"],
                extra_segments={
                    "clock_quartile": _clock_quartile(
                        request.clock_fraction, clock_distribution
                    )
                },
            )

    engine_versions = Counter(
        str(row.get("engine_version") or "unknown")
        for row in db.game_analyses.find(
            {"game_id": {"$in": [record["game_id"] for record in evaluation_records]}},
            {"_id": 0, "engine_version": 1},
        )
    )
    client.close()
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "raw_player_trajectory_exported": False,
        "stockfish_reanalysis": False,
        "source": {
            "database": os.environ.get("DB_NAME", "chess_coach"),
            "manifest_filename": manifest_path.name,
            "manifest_records_sha256": manifest.get("hashes", {}).get("eligible_records_sha256"),
            "split": args.split,
            "source_revision": args.source_revision,
            "move_observation_schema_min": OBSERVATION_SCHEMA_MIN,
            "engine_versions": dict(sorted(engine_versions.items())),
        },
        "candidate": provenance,
        "counts": {
            "history_games": len(history_records),
            "evaluation_games": len(evaluation_records),
            "input": dict(sorted(input_counts.items())),
            "fitting": dict(sorted(fitting_counts.items())),
            "provider_failures": dict(sorted(failures.items())),
            "clock_fraction_distribution": clock_distribution,
        },
        "metrics": metrics.finalize(),
        "runtime": {
            "wall_seconds": time.perf_counter() - started,
            "max_rss_kb": (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
            ),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "candidate": result["candidate"],
        "counts": result["counts"],
        "overall": result["metrics"]["overall"],
        "wall_seconds": result["runtime"]["wall_seconds"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
