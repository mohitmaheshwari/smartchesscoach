"""Build the read-only corpus manifest for the human-chess bake-off.

This script reads games plus the IDs of analyses that already contain stored
Stockfish move evidence.  It never writes to MongoDB and never runs an engine.
The output intentionally excludes PGNs, names, emails, and credentials; it
contains only opaque IDs, provenance, eligibility facts, deterministic split
cutoffs, and hashes.

Usage inside the backend container:

    python backend/scripts/build_human_chess_research_manifest.py
    python backend/scripts/build_human_chess_research_manifest.py \
        --output backend/data/corpus_snapshots/human_chess_research_2026-08-31.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.backfill_human_model_prerequisites import (  # noqa: E402
    SCHEMA_VERSION as PREREQUISITE_SCHEMA_VERSION,
    build_update,
    normalise_date,
    parse_clocks_seconds,
)

MANIFEST_SCHEMA_VERSION = "human_chess_research_manifest.v1"
TARGET_RATING_MIN = 600
TARGET_RATING_MAX = 1500
ALLOWED_PLATFORMS = frozenset({"chess.com", "lichess"})

# Candidates are measured, not selected here.  A later data-lock cites the
# resulting coverage and chooses a track-specific split.
SPLIT_CANDIDATES: Tuple[Tuple[str, int, int], ...] = (
    ("min_history_5_future_3", 5, 3),
    ("min_history_10_future_5", 10, 5),
    ("min_history_20_future_5", 20, 5),
    ("min_history_30_future_10", 30, 10),
)

GAME_PROJECTION = {
    "_id": 0,
    "game_id": 1,
    "user_id": 1,
    "platform": 1,
    "pgn": 1,
    "user_color": 1,
    "user_rating": 1,
    "opponent_rating": 1,
    "date_played": 1,
    "date_played_iso": 1,
    "time_control": 1,
    "time_control_category": 1,
    "human_model": 1,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _mainline_clock_evidence(pgn: str) -> Dict[str, Any]:
    """Independently verify the historical v1 flat clock producer.

    python-chess walks the main line and reads each node's `%clk`.  A record is
    clock-qualified only when every mainline ply has a clock and that ordered
    series exactly matches the v1 producer.  This prevents one missing tag or
    a variation comment from silently shifting every later clock to the wrong
    move.
    """
    if not pgn:
        return {
            "mainline_ply_count": 0,
            "annotated_ply_count": 0,
            "complete": False,
            "matches_v1": False,
            "parse_errors": ["missing_pgn"],
        }
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception as exc:
        return {
            "mainline_ply_count": 0,
            "annotated_ply_count": 0,
            "complete": False,
            "matches_v1": False,
            "parse_errors": [f"read_error:{type(exc).__name__}"],
        }
    if game is None:
        return {
            "mainline_ply_count": 0,
            "annotated_ply_count": 0,
            "complete": False,
            "matches_v1": False,
            "parse_errors": ["empty_game"],
        }

    aligned: List[Optional[int]] = []
    for node in game.mainline():
        remaining = node.clock()
        aligned.append(None if remaining is None else int(float(remaining)))

    v1 = parse_clocks_seconds(pgn)
    complete = bool(aligned) and all(value is not None for value in aligned)
    mainline_values = [value for value in aligned if value is not None]
    errors = [f"pgn:{type(err).__name__}" for err in (game.errors or [])]
    return {
        "mainline_ply_count": len(aligned),
        "annotated_ply_count": len(mainline_values),
        "complete": complete and not errors,
        "matches_v1": complete and not errors and mainline_values == v1,
        "parse_errors": errors,
    }


def _stored_prerequisite_status(game: Mapping[str, Any], derived: Mapping[str, Any]) -> str:
    stored = game.get("human_model")
    if not isinstance(stored, Mapping) or not stored:
        return "missing"
    if stored.get("schema_version") != PREREQUISITE_SCHEMA_VERSION:
        return "schema_mismatch"
    expected = {
        key.split("human_model.", 1)[1]: value
        for key, value in derived.items()
        if key.startswith("human_model.")
    }
    if bool(expected) and all(stored.get(key) == value for key, value in expected.items()):
        return "match"
    return "value_mismatch"


def build_game_record(
    game: Mapping[str, Any], analyzed_game_ids: Set[str]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return a privacy-minimized eligible record, or one exclusion reason."""
    game_id = str(game.get("game_id") or "").strip()
    user_id = str(game.get("user_id") or "").strip()
    if not game_id:
        return None, "missing_game_id"
    if not user_id:
        return None, "missing_user_id"
    if game.get("platform") not in ALLOWED_PLATFORMS:
        return None, "non_external_platform"
    if game_id not in analyzed_game_ids:
        return None, "missing_stored_analysis"

    derived, producer_stats = build_update(dict(game))
    if not derived:
        return None, "missing_prerequisites"
    rating = _positive_int(derived.get("human_model.player_elo"))
    if rating is None:
        return None, "missing_player_rating"
    if not TARGET_RATING_MIN <= rating <= TARGET_RATING_MAX:
        return None, "outside_target_rating"

    played_date = normalise_date(game.get("date_played_iso")) or normalise_date(
        game.get("date_played")
    )
    if not played_date:
        return None, "missing_trusted_play_date"

    pgn = str(game.get("pgn") or "")
    clock = _mainline_clock_evidence(pgn)
    if clock["mainline_ply_count"] <= 0:
        return None, "invalid_or_empty_pgn"

    rating_source = "unknown"
    if producer_stats.get("elo_player_from_store"):
        rating_source = "stored_user_rating"
    elif producer_stats.get("elo_player_from_pgn"):
        rating_source = "pgn_side_rating"

    prerequisite_status = _stored_prerequisite_status(game, derived)
    record = {
        "game_id": game_id,
        "user_id": user_id,
        "played_date": played_date,
        "platform": game.get("platform"),
        "player_rating": rating,
        "opponent_rating": _positive_int(derived.get("human_model.opponent_elo")),
        "rating_source": rating_source,
        "time_control": game.get("time_control"),
        "time_control_category": game.get("time_control_category"),
        "mainline_ply_count": clock["mainline_ply_count"],
        "clock_annotated_ply_count": clock["annotated_ply_count"],
        "clock_complete": clock["complete"],
        "clock_matches_v1": clock["matches_v1"],
        "clock_qualified": bool(clock["complete"] and clock["matches_v1"]),
        "pgn_parse_error_count": len(clock["parse_errors"]),
        "prerequisite_schema_version": PREREQUISITE_SCHEMA_VERSION,
        "stored_prerequisite_status": prerequisite_status,
        "stored_prerequisite_matches_producer": prerequisite_status == "match",
        "pgn_sha256": _sha256_text(pgn),
    }
    return record, None


def _percentile(values: Sequence[int], fraction: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[max(0, min(len(ordered) - 1, index))]


def _distribution(values: Sequence[int]) -> Dict[str, Optional[int]]:
    if not values:
        return {key: None for key in ("min", "p25", "median", "p75", "p90", "max")}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "p25": _percentile(ordered, 0.25),
        "median": _percentile(ordered, 0.5),
        "p75": _percentile(ordered, 0.75),
        "p90": _percentile(ordered, 0.9),
        "max": ordered[-1],
    }


def build_manifest(
    games: Iterable[Mapping[str, Any]],
    analyzed_game_ids: Set[str],
    *,
    generated_at: str,
    source_revision: str,
) -> Dict[str, Any]:
    exclusions: Counter = Counter()
    records: List[Dict[str, Any]] = []
    seen_game_ids: Set[str] = set()
    seen_pgn_hashes: Set[str] = set()

    for game in games:
        raw_id = str(game.get("game_id") or "").strip()
        if raw_id and raw_id in seen_game_ids:
            exclusions["duplicate_game_id"] += 1
            continue
        if raw_id:
            seen_game_ids.add(raw_id)
        record, reason = build_game_record(game, analyzed_game_ids)
        if reason:
            exclusions[reason] += 1
        elif record:
            if record["pgn_sha256"] in seen_pgn_hashes:
                exclusions["duplicate_pgn"] += 1
                continue
            seen_pgn_hashes.add(record["pgn_sha256"])
            records.append(record)

    records.sort(key=lambda row: (row["user_id"], row["played_date"], row["game_id"]))
    by_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_user[record["user_id"]].append(record)

    users: List[Dict[str, Any]] = []
    split_summary: Dict[str, Dict[str, Any]] = {
        key: {
            "min_history_games": history,
            "future_games": future,
            "eligible_users": 0,
            "eligible_games": 0,
            "clock_qualified_evaluation_users": 0,
        }
        for key, history, future in SPLIT_CANDIDATES
    }

    for user_id in sorted(by_user):
        rows = by_user[user_id]
        cutoffs: Dict[str, Dict[str, int]] = {}
        for key, min_history, future in SPLIT_CANDIDATES:
            if len(rows) < min_history + future:
                continue
            evaluation_start = len(rows) - future
            cutoffs[key] = {
                "history_end_exclusive": evaluation_start,
                "evaluation_start_inclusive": evaluation_start,
                "evaluation_end_exclusive": len(rows),
            }
            summary = split_summary[key]
            summary["eligible_users"] += 1
            summary["eligible_games"] += len(rows)
            if all(row["clock_qualified"] for row in rows[evaluation_start:]):
                summary["clock_qualified_evaluation_users"] += 1

        users.append({
            "user_id": user_id,
            "game_count": len(rows),
            "first_played_date": rows[0]["played_date"],
            "last_played_date": rows[-1]["played_date"],
            "clock_qualified_game_count": sum(bool(row["clock_qualified"]) for row in rows),
            "split_cutoffs": cutoffs,
        })

    game_counts = [user["game_count"] for user in users]
    ordered_ids = [record["game_id"] for record in records]
    payload_digest = _sha256_text(_canonical_json(records))
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": {
            "database": "chess_coach",
            "code_revision": source_revision,
            "read_only": True,
            "stockfish_reanalysis": False,
            "prerequisite_schema_version": PREREQUISITE_SCHEMA_VERSION,
        },
        "eligibility_contract": {
            "platforms": sorted(ALLOWED_PLATFORMS),
            "rating_min": TARGET_RATING_MIN,
            "rating_max": TARGET_RATING_MAX,
            "requires_stored_analysis": True,
            "requires_trusted_play_date": True,
            "requires_valid_mainline_pgn": True,
            "exact_duplicate_pgns_removed": True,
            "position_deduplication_required_downstream": True,
            "clock_qualification": "all mainline plies annotated and equal to v1 producer order",
        },
        "counts": {
            "eligible_games": len(records),
            "eligible_users": len(users),
            "clock_qualified_games": sum(bool(row["clock_qualified"]) for row in records),
            "stored_prerequisite_status": dict(sorted(Counter(
                row["stored_prerequisite_status"] for row in records
            ).items())),
            "exclusions": dict(sorted(exclusions.items())),
            "games_per_user": _distribution(game_counts),
        },
        "split_candidates": split_summary,
        "hashes": {
            "ordered_game_ids_sha256": _sha256_text("\n".join(ordered_ids)),
            "eligible_records_sha256": payload_digest,
        },
        "users": users,
        "games": records,
    }


async def _load_from_mongo(limit: Optional[int]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    cursor = db.games.find({}, GAME_PROJECTION).sort("game_id", 1)
    if limit:
        cursor = cursor.limit(limit)
    games = await cursor.to_list(length=limit or None)
    analysis_cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1},
    )
    analyzed = {str(row["game_id"]) async for row in analysis_cursor if row.get("game_id")}
    client.close()
    return games, analyzed


def _default_revision() -> str:
    return os.environ.get("SOURCE_REVISION", "unknown")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source-revision", default=_default_revision())
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    args = parser.parse_args()

    games, analyzed = asyncio.run(_load_from_mongo(args.limit))
    manifest = build_manifest(
        games,
        analyzed,
        generated_at=args.generated_at,
        source_revision=args.source_revision,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote={args.output}")
    print(_canonical_json({
        "schema_version": manifest["schema_version"],
        "counts": manifest["counts"],
        "split_candidates": manifest["split_candidates"],
        "hashes": manifest["hashes"],
    }))


if __name__ == "__main__":
    main()
