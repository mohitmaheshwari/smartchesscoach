#!/usr/bin/env python3
"""Build a privacy-minimized, stratified sample for the MultiPV bake-off.

The script is read-only. It selects opaque game/ply references from the frozen
600–1500 corpus and writes no FEN, PGN, player ID, name, email, or engine line.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import chess
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.corpus_inputs import normalized_position_key  # noqa: E402

SCHEMA_VERSION = "human_chess.sound_findable_sample.v1"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _rating_band(rating: int) -> str:
    if rating < 1000:
        return "600-999"
    if rating < 1400:
        return "1000-1399"
    return "1400-1500"


def _error_band(cp_loss: int) -> str:
    if cp_loss < 150:
        return "cp_loss_100_149"
    if cp_loss < 200:
        return "cp_loss_150_199"
    return "cp_loss_200_plus"


def _phase(value: Any) -> str:
    phase = str(value or "unknown").lower()
    if "opening" in phase:
        return "opening"
    if "middle" in phase:
        return "middlegame"
    if "end" in phase:
        return "endgame"
    return "unknown"


def _stable_order(rows: Iterable[Mapping[str, Any]], seed: str) -> List[Dict[str, Any]]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: hashlib.sha256(
            f"{seed}|{row['game_id']}|{row['ply']}".encode("utf-8")
        ).hexdigest(),
    )


def select_balanced_sample(
    rows: Sequence[Mapping[str, Any]], *, limit: int, seed: str
) -> List[Dict[str, Any]]:
    """Round-robin primary strata and concept families deterministically."""
    primary: Dict[Tuple[str, str, str], Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        key = (row["rating_band"], row["phase"], row["error_band"])
        primary[key][row["concept_family"]].append(dict(row))

    strata: Dict[Tuple[str, str, str], deque] = {}
    for key, concepts in primary.items():
        concept_queues = {
            concept: deque(_stable_order(items, f"{seed}|{concept}"))
            for concept, items in concepts.items()
        }
        ordered = deque()
        while any(concept_queues.values()):
            for concept in sorted(concept_queues):
                if concept_queues[concept]:
                    ordered.append(concept_queues[concept].popleft())
        strata[key] = ordered

    selected: List[Dict[str, Any]] = []
    while len(selected) < limit and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(selected) < limit:
                selected.append(strata[key].popleft())
    return selected


def _axis_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, int]]:
    axes = ("rating_band", "phase", "error_band", "concept_family")
    return {
        axis: dict(sorted(Counter(str(row[axis]) for row in rows).items()))
        for axis in axes
    }


def _primary_strata_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = Counter(
        "|".join((
            str(row["rating_band"]),
            str(row["phase"]),
            str(row["error_band"]),
        ))
        for row in rows
    )
    return dict(sorted(counts.items()))


def _selection_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    strata = _primary_strata_counts(rows)
    stratum_sizes = list(strata.values())
    concept_counts = Counter(str(row["concept_family"]) for row in rows)
    return {
        "count": len(rows),
        "populated_primary_strata": len(strata),
        "primary_stratum_size": {
            "minimum": min(stratum_sizes, default=0),
            "median": statistics.median(stratum_sizes) if stratum_sizes else 0,
            "maximum": max(stratum_sizes, default=0),
        },
        "concept_families_represented": len(concept_counts),
        "named_count": sum(
            count for concept, count in concept_counts.items() if concept != "unnamed"
        ),
        "unnamed_count": concept_counts.get("unnamed", 0),
        "primary_strata": strata,
    }


def build_candidates(
    observations: Iterable[Mapping[str, Any]],
    ratings_by_game: Mapping[str, int],
) -> tuple[List[Dict[str, Any]], Counter]:
    candidates: List[Dict[str, Any]] = []
    counts: Counter = Counter()
    seen_positions = set()
    for observation in observations:
        counts["queried_observations"] += 1
        game_id = str(observation.get("game_id") or "")
        rating = ratings_by_game.get(game_id)
        if rating is None:
            counts["missing_manifest_rating"] += 1
            continue
        try:
            fen = str(observation["fen_before"])
            move_uci = str(observation["move_uci"]).lower()
            board = chess.Board(fen)
            if not board.is_valid() or chess.Move.from_uci(move_uci) not in board.legal_moves:
                raise ValueError("invalid board or move")
            position_key = normalized_position_key(fen)
        except (KeyError, ValueError):
            counts["invalid_position_or_move"] += 1
            continue
        if position_key in seen_positions:
            counts["duplicate_positions_removed"] += 1
            continue
        seen_positions.add(position_key)
        cp_loss = int(observation.get("cp_loss") or 0)
        concept = str(observation.get("missed_pattern") or "unnamed").strip() or "unnamed"
        candidates.append({
            "game_id": game_id,
            "ply": int(observation.get("ply") or 0),
            "rating_band": _rating_band(int(rating)),
            "phase": _phase(observation.get("phase")),
            "error_band": _error_band(cp_loss),
            "concept_family": concept,
        })
    counts["deduplicated_candidates"] = len(candidates)
    return candidates, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--minimum-cp-loss", type=int, default=100)
    parser.add_argument(
        "--compare-limits",
        default="270,405,540,675",
        help="Comma-separated candidate sample sizes to summarize without exporting records.",
    )
    parser.add_argument("--seed", default="sound-findable-2026-08-31")
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.minimum_cp_loss < 0:
        parser.error("--minimum-cp-loss must be non-negative")
    try:
        comparison_limits = sorted({
            int(value.strip())
            for value in args.compare_limits.split(",")
            if value.strip()
        })
    except ValueError:
        parser.error("--compare-limits must contain positive integers")
    if any(value <= 0 for value in comparison_limits):
        parser.error("--compare-limits must contain positive integers")

    manifest_path = args.manifest.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    game_records = list(manifest.get("games") or [])
    ratings_by_game = {
        str(row["game_id"]): int(row["player_rating"])
        for row in game_records
        if row.get("game_id") and isinstance(row.get("player_rating"), (int, float))
    }
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    projection = {
        "_id": 0,
        "game_id": 1,
        "ply": 1,
        "fen_before": 1,
        "move_uci": 1,
        "phase": 1,
        "cp_loss": 1,
        "missed_pattern": 1,
    }
    observations = db.move_observations.find(
        {
            "game_id": {"$in": sorted(ratings_by_game)},
            "schema_version": {"$gte": 16},
            "cp_loss": {"$gte": args.minimum_cp_loss},
            "fen_before": {"$type": "string"},
            "move_uci": {"$type": "string"},
        },
        projection,
    ).sort([("game_id", 1), ("ply", 1)])
    candidates, counts = build_candidates(observations, ratings_by_game)
    client.close()
    selected = select_balanced_sample(candidates, limit=args.limit, seed=args.seed)
    sample = [
        {"sample_index": index, **row}
        for index, row in enumerate(selected)
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "privacy": {
            "contains_fen": False,
            "contains_pgn": False,
            "contains_user_id": False,
            "contains_name_or_email": False,
        },
        "source": {
            "database": os.environ.get("DB_NAME", "chess_coach"),
            "manifest_filename": manifest_path.name,
            "manifest_records_sha256": manifest.get("hashes", {}).get("eligible_records_sha256"),
            "source_revision": args.source_revision,
            "minimum_observation_schema": 16,
        },
        "selection": {
            "seed": args.seed,
            "requested_limit": args.limit,
            "minimum_cp_loss": args.minimum_cp_loss,
            "method": "round_robin_rating_band_x_phase_x_error_band_then_concept_family",
        },
        "opportunities": {
            "counts": dict(sorted(counts.items())),
            "axes": _axis_counts(candidates),
            "primary_strata": _primary_strata_counts(candidates),
        },
        "candidate_sample_sizes": {
            str(limit): _selection_summary(
                select_balanced_sample(candidates, limit=limit, seed=args.seed)
            )
            for limit in comparison_limits
        },
        "selected": {
            "count": len(sample),
            "axes": _axis_counts(sample),
            "primary_strata": _primary_strata_counts(sample),
            "records_sha256": _canonical_sha256(sample),
            "records": sample,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "opportunities": result["opportunities"]["counts"],
        "selected": result["selected"]["count"],
        "records_sha256": result["selected"]["records_sha256"],
        "output": str(args.output),
    }))


if __name__ == "__main__":
    main()
