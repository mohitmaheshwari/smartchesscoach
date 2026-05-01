"""
Quick status snapshot of the analysis queue.

Tells you how many games are still pending, currently processing,
recently completed, and failed. Useful while a reanalysis sweep is
draining (e.g., after running scripts/reanalyze_all_games.py --apply).

Usage (on the server):
  docker exec -it chess-coach-backend python3 scripts/analysis_queue_status.py

  # Watch it live, refreshes every 10s
  docker exec -it chess-coach-backend python3 scripts/analysis_queue_status.py --watch

  # Just the numbers, no decoration (good for piping into other tools)
  docker exec -it chess-coach-backend python3 scripts/analysis_queue_status.py --plain

  # Scope to one user
  docker exec -it chess-coach-backend python3 scripts/analysis_queue_status.py --user user_1e2b7b2777bc

Reads only — no writes, safe to run anytime.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient


def get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    return MongoClient(mongo_url)[db_name]


def snapshot(db, user_id: str | None = None) -> dict:
    """Return current queue counts + a few derived numbers."""
    base: dict = {}
    if user_id:
        base["user_id"] = user_id

    # Counts by status
    pending = db.analysis_queue.count_documents({**base, "status": "pending"})
    processing = db.analysis_queue.count_documents({**base, "status": "processing"})
    completed = db.analysis_queue.count_documents({**base, "status": "completed"})
    failed = db.analysis_queue.count_documents({**base, "status": "failed"})

    # Reanalysis-tagged subset (so we can separate the current sweep
    # from organic new-game analyses)
    reanalysis_pending = db.analysis_queue.count_documents(
        {**base, "status": "pending", "reanalysis": True}
    )
    reanalysis_processing = db.analysis_queue.count_documents(
        {**base, "status": "processing", "reanalysis": True}
    )

    # Throughput hint: completed in the last 5 minutes (ISO string field)
    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    completed_recent = db.analysis_queue.count_documents(
        {**base, "status": "completed", "updated_at": {"$gte": five_min_ago}}
    )

    # Currently-claimed jobs that haven't heartbeated in a while
    # are likely stuck — surface them
    stale_threshold = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    stale_processing = db.analysis_queue.count_documents(
        {
            **base,
            "status": "processing",
            "last_heartbeat": {"$lt": stale_threshold},
        }
    )

    # Total analyzed games on the games collection (the canonical
    # source-of-truth flag the worker sets on success)
    analyzed_games = db.games.count_documents(
        {**({"user_id": user_id} if user_id else {}), "is_analyzed": True}
    )

    return {
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "reanalysis_pending": reanalysis_pending,
        "reanalysis_processing": reanalysis_processing,
        "completed_last_5m": completed_recent,
        "stale_processing": stale_processing,
        "analyzed_games_total": analyzed_games,
    }


def render(snap: dict, plain: bool = False) -> str:
    if plain:
        return (
            f"pending={snap['pending']} processing={snap['processing']} "
            f"completed={snap['completed']} failed={snap['failed']} "
            f"reanalysis_pending={snap['reanalysis_pending']} "
            f"throughput_5m={snap['completed_last_5m']}"
        )

    pending = snap["pending"]
    processing = snap["processing"]
    throughput = snap["completed_last_5m"]

    # Crude ETA: minutes until pending drains at current 5-minute rate
    if pending and throughput:
        per_min = throughput / 5
        eta_min = pending / per_min
        eta_str = f"~{eta_min:.0f} min" if eta_min < 90 else f"~{eta_min/60:.1f} hr"
    elif pending and not throughput:
        eta_str = "(no throughput in last 5m — worker idle?)"
    else:
        eta_str = "queue empty"

    lines = [
        "─" * 56,
        f"  ANALYSIS QUEUE STATUS",
        "─" * 56,
        f"  Pending:           {pending:>5}",
        f"    └ reanalysis:    {snap['reanalysis_pending']:>5}",
        f"  Processing:        {processing:>5}",
        f"    └ reanalysis:    {snap['reanalysis_processing']:>5}",
        f"    └ stale (>15m):  {snap['stale_processing']:>5}",
        f"  Completed (total): {snap['completed']:>5}",
        f"  Failed:            {snap['failed']:>5}",
        "",
        f"  Throughput (5m):   {throughput:>5}",
        f"  ETA to drain:      {eta_str}",
        "",
        f"  is_analyzed=True games in DB: {snap['analyzed_games_total']}",
        "─" * 56,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", type=str, default=None, help="Scope to one user_id.")
    parser.add_argument("--watch", action="store_true", help="Refresh every 10 seconds.")
    parser.add_argument("--interval", type=int, default=10, help="Watch refresh seconds.")
    parser.add_argument("--plain", action="store_true", help="Single-line plain output.")
    args = parser.parse_args()

    db = get_db()

    if not args.watch:
        snap = snapshot(db, user_id=args.user)
        print(render(snap, plain=args.plain))
        return 0

    # Watch mode: refresh until pending hits zero or user Ctrl-Cs
    try:
        while True:
            snap = snapshot(db, user_id=args.user)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}]")
            print(render(snap, plain=args.plain))
            if snap["pending"] == 0 and snap["processing"] == 0:
                print("\nQueue drained.")
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
