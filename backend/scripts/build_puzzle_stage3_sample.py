#!/usr/bin/env python3
"""Build a privacy-minimized stratified sample of admitted puzzle positions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import chess
from pymongo import MongoClient

SCHEMA_VERSION = "human_chess.puzzle_stage3_sample.v1"


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def normalize_difficulty(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "beginner": "easy",
        "easy": "easy",
        "intermediate": "medium",
        "medium": "medium",
        "advanced": "hard",
        "hard": "hard",
    }.get(normalized, "unknown")


def _position_key(fen: str) -> str:
    return " ".join(chess.Board(fen).fen(en_passant="fen").split()[:4])


def _stable_order(rows: Iterable[Mapping[str, Any]], seed: str) -> List[Dict[str, Any]]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: hashlib.sha256(
            f"{seed}|{row['pool']}|{row['puzzle_ref']}".encode()
        ).hexdigest(),
    )


def select_balanced(
    rows: Sequence[Mapping[str, Any]], limit: int, seed: str
) -> List[Dict[str, Any]]:
    primary = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = (row["pool"], row["difficulty"], row["admission_status"])
        primary[key][row["concept_family"]].append(dict(row))
    strata = {}
    for key, concepts in primary.items():
        queues = {
            concept: deque(_stable_order(items, f"{seed}|{concept}"))
            for concept, items in concepts.items()
        }
        ordered = deque()
        while any(queues.values()):
            for concept in sorted(queues):
                if queues[concept]:
                    ordered.append(queues[concept].popleft())
        strata[key] = ordered
    selected = []
    while len(selected) < limit and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(selected) < limit:
                selected.append(strata[key].popleft())
    return selected


def _strata(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    return dict(sorted(Counter(
        f"{row['pool']}|{row['difficulty']}|{row['admission_status']}"
        for row in rows
    ).items()))


def _summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    strata = _strata(rows)
    sizes = list(strata.values())
    return {
        "count": len(rows),
        "populated_primary_strata": len(strata),
        "primary_strata": strata,
        "stratum_size": {
            "minimum": min(sizes, default=0),
            "median": statistics.median(sizes) if sizes else 0,
            "maximum": max(sizes, default=0),
        },
        "concept_families": len({row["concept_family"] for row in rows}),
    }


def build_candidates(
    community_rows: Iterable[Mapping[str, Any]],
    training_rows: Iterable[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], Counter]:
    counts: Counter = Counter()
    by_position: Dict[str, Dict[str, Any]] = {}
    conflicts = set()
    for pool, rows in (
        ("community_puzzles", community_rows),
        ("community_training_positions", training_rows),
    ):
        for puzzle in rows:
            counts[f"{pool}_scanned"] += 1
            admission = puzzle.get("verified_admission")
            if not isinstance(admission, Mapping):
                counts["missing_admission"] += 1
                continue
            status = str(admission.get("status") or "missing")
            if status == "quarantine":
                counts["quarantined"] += 1
                continue
            acceptable = tuple(sorted({
                str(move).lower()
                for move in admission.get("acceptable_moves_uci") or []
                if isinstance(move, str)
            }))
            fen = puzzle.get("fen") or puzzle.get("fen_before")
            try:
                board = chess.Board(str(fen or ""))
                if not board.is_valid() or not acceptable:
                    raise ValueError
                legal = {move.uci() for move in board.legal_moves}
                if not set(acceptable).issubset(legal):
                    raise ValueError
                position_key = _position_key(str(fen))
            except ValueError:
                counts["invalid_position_or_answers"] += 1
                continue
            reference = (
                str(puzzle.get("_id"))
                if pool == "community_puzzles"
                else str(puzzle.get("position_id") or puzzle.get("puzzle_id") or puzzle.get("_id"))
            )
            row = {
                "pool": pool,
                "puzzle_ref": reference,
                "difficulty": normalize_difficulty(puzzle.get("difficulty")),
                "admission_status": status,
                "concept_family": str(
                    admission.get("concept_id")
                    or admission.get("broad_category")
                    or puzzle.get("issue_type")
                    or puzzle.get("pattern_type")
                    or "unnamed"
                ),
                "_answers": acceptable,
            }
            prior = by_position.get(position_key)
            if prior is None:
                by_position[position_key] = row
            elif prior["_answers"] != acceptable:
                conflicts.add(position_key)
            else:
                counts["duplicate_same_answer_removed"] += 1
    for key in conflicts:
        by_position.pop(key, None)
    counts["conflicting_positions_removed"] = len(conflicts)
    candidates = []
    for row in by_position.values():
        clean = {key: value for key, value in row.items() if not key.startswith("_")}
        candidates.append(clean)
    counts["eligible_unique_positions"] = len(candidates)
    return candidates, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", required=True, type=int)
    parser.add_argument("--compare-limits", default="120,240,360,480")
    parser.add_argument("--seed", default="puzzle-stage3-2026-08-31")
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    comparison_limits = sorted({
        int(value.strip()) for value in args.compare_limits.split(",") if value.strip()
    })
    if args.limit <= 0 or any(value <= 0 for value in comparison_limits):
        parser.error("sample limits must be positive")

    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = client[db_name]
    projection = {
        "fen": 1,
        "fen_before": 1,
        "position_id": 1,
        "puzzle_id": 1,
        "difficulty": 1,
        "issue_type": 1,
        "pattern_type": 1,
        "verified_admission": 1,
    }
    candidates, counts = build_candidates(
        db.community_puzzles.find({}, projection),
        db.community_training_positions.find({}, projection),
    )
    client.close()
    selected = select_balanced(candidates, args.limit, args.seed)
    records = [
        {"sample_index": index, **row}
        for index, row in enumerate(selected)
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "privacy": {
            "contains_positions_or_moves": False,
            "contains_player_or_game_identifiers": False,
            "contains_only_opaque_puzzle_references": True,
        },
        "source": {"database": db_name, "source_revision": args.source_revision},
        "selection": {
            "seed": args.seed,
            "requested_limit": args.limit,
            "method": "round_robin_pool_x_normalized_difficulty_x_admission_then_concept",
        },
        "opportunities": {
            "counts": dict(sorted(counts.items())),
            **_summary(candidates),
        },
        "candidate_sample_sizes": {
            str(limit): _summary(select_balanced(candidates, limit, args.seed))
            for limit in comparison_limits
        },
        "selected": {
            **_summary(records),
            "records_sha256": _canonical_hash(records),
            "records": records,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "opportunities": result["opportunities"]["counts"],
        "sample_candidates": result["candidate_sample_sizes"],
        "selected": result["selected"]["count"],
        "records_sha256": result["selected"]["records_sha256"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
