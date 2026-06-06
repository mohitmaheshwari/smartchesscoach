"""Enqueue full re-analysis for the last N games per active user.

Built 2026-06-06. The opp-side failure-mode framework (commit 700fb473)
needs opponent best_move + PV, which only get computed during a FULL
Stockfish re-analysis (not a V5 caption regen). This script enqueues
re-analysis jobs for recent games so opp-mistake captions start
explaining WHY.

Mohit's call (2026-06-06): "mass re-analyze recent only" — balances
coverage (the games users actually revisit) against the cost of a
full-corpus Stockfish run.

The analysis_worker picks up status=pending jobs FIFO and re-runs the
full pipeline (Stockfish + traps + V5), upserting game_analyses. No
skip-if-analyzed guard, so existing games get overwritten with fresh
analysis that includes opponent_move_evaluations.

Usage (in prod container):

    # Dry-run (DEFAULT — shows what would be enqueued, no writes):
    python /app/backend/scripts/reanalyze_recent_games.py

    # Custom N (games per user):
    python /app/backend/scripts/reanalyze_recent_games.py --per-user 20

    # Actually enqueue:
    python /app/backend/scripts/reanalyze_recent_games.py --apply

    # Limit to one user (testing):
    python /app/backend/scripts/reanalyze_recent_games.py --user-id user_xxx --apply

Idempotent-ish: if a game already has a pending/processing job, it's
skipped (no duplicate enqueue). Completed jobs for the same game get a
fresh pending job (re-analysis).
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


DEFAULT_PER_USER = 20


async def run(args):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("=== Re-analyze recent games ===")
    print(f"  per-user: {args.per_user}")
    print(f"  mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  scope: {'user=' + args.user_id if args.user_id else 'ALL active users'}")
    print()

    # Active users = users with at least one analyzed game.
    if args.user_id:
        user_ids = [args.user_id]
    else:
        user_ids = await db.games.distinct("user_id", {"is_analyzed": True})

    total_enqueued = 0
    total_skipped_existing = 0
    per_user_counts = {}

    for uid in user_ids:
        if not uid:
            continue
        # Most recent N analyzed games for this user, newest first.
        recent = await db.games.find(
            {"user_id": uid, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1,
             "date_played": 1, "imported_at": 1},
        ).sort([("date_played", -1), ("imported_at", -1)]).limit(args.per_user).to_list(args.per_user)

        enq = 0
        for g in recent:
            gid = g.get("game_id")
            if not gid or not g.get("pgn"):
                continue
            # Skip if a job is already pending/processing for this game.
            existing = await db.analysis_queue.find_one({
                "game_id": gid,
                "status": {"$in": ["pending", "processing"]},
            })
            if existing:
                total_skipped_existing += 1
                continue
            if args.apply:
                # Remove any prior completed/failed job for this game so the
                # queue stays clean, then enqueue a fresh pending job.
                await db.analysis_queue.delete_many({"game_id": gid})
                await db.analysis_queue.insert_one({
                    "game_id": gid,
                    "user_id": uid,
                    "pgn": g.get("pgn", ""),
                    "user_color": g.get("user_color", "white"),
                    "status": "pending",
                    "queued_at": datetime.now(timezone.utc).isoformat(),
                    "attempts": 0,
                    "enqueued_by": "reanalyze_recent_games_2026-06-06",
                    # 2026-06-06: bulk re-analysis is LOW priority so it
                    # never blocks freshly-played live games (priority=10).
                    "priority": 0,
                })
            enq += 1
            total_enqueued += 1
        if enq:
            per_user_counts[uid] = enq

    print(f"Users with games to re-analyze: {len(per_user_counts)}")
    print(f"Total games {'enqueued' if args.apply else 'WOULD enqueue'}: {total_enqueued}")
    print(f"Skipped (already pending/processing): {total_skipped_existing}")
    print()
    print("Top 15 users by re-analysis count:")
    for uid in sorted(per_user_counts, key=lambda u: -per_user_counts[u])[:15]:
        print(f"  {uid[-12:]}: {per_user_counts[uid]}")

    if not args.apply:
        print()
        print("DRY-RUN. To enqueue:")
        print(f"  python {os.path.basename(__file__)} --apply --per-user {args.per_user}")
    else:
        print()
        print("Enqueued. The analysis_worker will process these FIFO.")
        print("Monitor: db.analysis_queue.count_documents({status:'pending'})")

    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually enqueue (default is dry-run)")
    parser.add_argument("--per-user", type=int, default=DEFAULT_PER_USER,
                        help=f"Recent games per user to re-analyze (default {DEFAULT_PER_USER})")
    parser.add_argument("--user-id", type=str, default=None,
                        help="Limit to a single user_id (testing)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
