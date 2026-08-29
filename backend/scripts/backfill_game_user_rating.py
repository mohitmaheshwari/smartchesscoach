"""Backfill authoritative games.user_rating values; dry-run by default.

This script never substitutes DEFAULT_RATING. Rows without a stored side/API or
PGN rating remain unknown. Pass --write explicitly to persist recoverable rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rating_resolver import resolve_game_user_rating


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    query = {"$or": [
        {"user_rating": {"$exists": False}},
        {"user_rating": None},
    ]}
    projection = {
        "_id": 1,
        "game_id": 1,
        "user_color": 1,
        "user_rating": 1,
        "user_rating_at_time": 1,
        "white_rating": 1,
        "black_rating": 1,
        "white": 1,
        "black": 1,
        "pgn": 1,
    }
    cursor = db.games.find(query, projection)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    counts = Counter()
    for game in cursor:
        counts["scanned"] += 1
        result = resolve_game_user_rating(game)
        if result["rating"] is None:
            counts["unresolved"] += 1
            continue
        counts["recoverable"] += 1
        counts[f"source:{result['source']}"] += 1
        if args.write:
            update = db.games.update_one(
                {"_id": game["_id"], "user_rating": {"$in": [None]}},
                {"$set": {
                    "user_rating": result["rating"],
                    "user_rating_source": result["source"],
                }},
            )
            counts["updated"] += update.modified_count

    report = {
        "mode": "write" if args.write else "dry_run",
        "authoritative_only": True,
        "unknown_preserved": True,
        **dict(counts),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
