#!/usr/bin/env python3
"""
Requeue Missing Games
======================
Finds games that were imported but never queued for Stockfish analysis,
and adds them to the analysis queue.

Usage:
    python requeue_missing.py          # Dry run (shows what would be queued)
    python requeue_missing.py --go     # Actually queue them
    
    # From host:
    docker exec -it chess-coach-backend python requeue_missing.py --go
"""

import os
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

dry_run = "--go" not in sys.argv


def main():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]

    # Get all game IDs
    all_game_ids = set()
    for g in db.games.find({}, {"_id": 0, "game_id": 1}):
        all_game_ids.add(g["game_id"])

    # Get analyzed game IDs
    analyzed_ids = set()
    for a in db.game_analyses.find({}, {"_id": 0, "game_id": 1}):
        analyzed_ids.add(a["game_id"])

    # Get queued game IDs
    queued_ids = set()
    for q in db.analysis_queue.find({}, {"_id": 0, "game_id": 1}):
        queued_ids.add(q["game_id"])

    # Find missing: imported but not analyzed AND not in queue
    missing = all_game_ids - analyzed_ids - queued_ids

    print(f"Total games:          {len(all_game_ids)}")
    print(f"Already analyzed:     {len(analyzed_ids)}")
    print(f"Already in queue:     {len(queued_ids)}")
    print(f"Missing (need queue): {len(missing)}")
    print()

    if not missing:
        print("Nothing to do — all games are either analyzed or queued.")
        return

    if dry_run:
        print("DRY RUN — showing what would be queued:")
        for gid in list(missing)[:20]:
            game = db.games.find_one({"game_id": gid}, {"_id": 0, "game_id": 1, "user_id": 1, "opponent_name": 1})
            if game:
                print(f"  {game['game_id'][:25]}  (user: {game.get('user_id', '?')}, vs {game.get('opponent_name', '?')})")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        print()
        print("Run with --go to actually queue them:")
        print(f"  python {sys.argv[0]} --go")
        return

    # Queue them
    queued = 0
    for gid in missing:
        game = db.games.find_one({"game_id": gid}, {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1})
        if not game or not game.get("pgn"):
            print(f"  Skipping {gid} (no PGN)")
            continue

        db.analysis_queue.insert_one({
            "game_id": gid,
            "user_id": game["user_id"],
            "status": "pending",
            "attempts": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        queued += 1

    print(f"Queued {queued} games for analysis.")
    print("The backend fallback processor will pick them up automatically (every 15 seconds).")


if __name__ == "__main__":
    main()
