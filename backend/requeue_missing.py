#!/usr/bin/env python3
"""
Requeue Missing Games
======================
Finds games that were imported but never queued for Stockfish analysis,
and adds them to the analysis queue.

A sync imports every game but queues only up to its analysis budget
(journey_service, "Analysis is capped; importing is not"), so a player with a
long history keeps many games that were never queued. --played-since limits
the requeue to recent ones (by played_at_utc).

Rows go in at priority 0. Every path a player is waiting on queues at 1 or
higher (re-analysis 1, academy 3, sync 5-9, live game 10), and the worker
claims highest priority first, so these run only when nothing else is waiting.

Usage:
    python requeue_missing.py                                   # dry run
    python requeue_missing.py --played-since 2026-10-09         # dry run, recent only
    python requeue_missing.py --played-since 2026-10-09 --go --undo-file /root/x.json

    # From host:
    docker exec -it chess-coach-backend python requeue_missing.py --go --undo-file ...
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")
ENQUEUED_BY = "requeue_missing"


def main(args):
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]

    since = None
    if args.played_since:
        since = datetime.strptime(args.played_since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    analyzed_ids = {a["game_id"] for a in db.game_analyses.find({}, {"_id": 0, "game_id": 1})}
    queued_ids = {q["game_id"] for q in db.analysis_queue.find({}, {"_id": 0, "game_id": 1})}

    query = {"is_analyzed": {"$ne": True}}
    if since:
        query["played_at_utc"] = {"$gte": since}
    missing = []
    c = Counter()
    per_user = Counter()
    for g in db.games.find(query, {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1}):
        gid = g["game_id"]
        if gid in analyzed_ids or gid in queued_ids:
            continue
        if not g.get("pgn"):
            c["skipped_no_pgn"] += 1
            continue
        missing.append((gid, g["user_id"]))
        per_user[g["user_id"]] += 1

    print(f"Filter:               {query}")
    print(f"Already analyzed:     {len(analyzed_ids)}")
    print(f"Already in queue:     {len(queued_ids)}")
    print(f"Missing (need queue): {len(missing)}  across {len(per_user)} users, "
          f"per user {sorted(per_user.values(), reverse=True)}")
    print(f"Skipped (no PGN):     {c['skipped_no_pgn']}")

    if not args.go:
        print("\nDRY RUN. Add --go --undo-file <path> to queue them.")
        return

    now = datetime.now(timezone.utc)
    queued = []
    for gid, uid in missing:
        db.analysis_queue.insert_one({
            "game_id": gid,
            "user_id": uid,
            "status": "pending",
            "priority": 0,
            "attempts": 0,
            "retry_count": 0,
            "queued_at": now.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "enqueued_by": ENQUEUED_BY,
        })
        queued.append(gid)

    # Undo: delete pending rows for these game_ids with enqueued_by == ENQUEUED_BY.
    with open(args.undo_file, "w") as fh:
        json.dump({"enqueued_by": ENQUEUED_BY, "queued_at": now.isoformat(), "game_ids": queued}, fh)
    print(f"\nQueued {len(queued)} games at priority 0. Undo list: {args.undo_file}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--go", action="store_true", help="actually queue (default dry run)")
    p.add_argument("--played-since", default="", help="YYYY-MM-DD, by played_at_utc")
    p.add_argument("--undo-file", default="")
    a = p.parse_args()
    if a.go and not a.undo_file:
        sys.exit("--go needs --undo-file")
    main(a)
