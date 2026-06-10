"""Requeue games whose analysis FAILED so the worker re-analyzes them.

Context (2026-06-10): a code regression around 2026-06-07/08 crashed
analysis with `'str' object has no attribute 'get'`, leaving ~140 games
marked analysis_status="failed" and is_analyzed=false. Those jobs sit in
analysis_queue as status="failed" — the worker only claims status="pending",
so they are never retried. This script deletes the stale queue entry for
each failed game and inserts a fresh status="pending" job.

Unlike reanalyze_recent_games.py (which targets is_analyzed=True recent
games for a caption refresh), this targets the FAILED, still-unanalyzed
games specifically.

Usage (in the backend container, which reaches prod Mongo via the SSH tunnel):

    # Dry-run (DEFAULT — shows what would be enqueued, no writes):
    python scripts/requeue_failed_games.py

    # Canary: requeue just one, to confirm the worker analyzes it cleanly:
    python scripts/requeue_failed_games.py --limit 1 --apply

    # Requeue all failed games:
    python scripts/requeue_failed_games.py --apply

    # Only those that crashed with the known regression:
    python scripts/requeue_failed_games.py --error-substr "'str' object" --apply
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import pymongo


def run(args):
    client = pymongo.MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    # Failed games that still have no analysis. Match on the game record so we
    # have pgn/user_color to build the job, not just the (possibly stale) queue.
    query = {"analysis_status": "failed", "is_analyzed": {"$ne": True}}
    if args.error_substr:
        query["analysis_error"] = {"$regex": args.error_substr}

    games = list(
        db.games.find(
            query,
            {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1,
             "user_color": 1, "analysis_error": 1, "imported_at": 1},
        ).sort("imported_at", 1)
    )

    print("=== Requeue failed games ===")
    print(f"  mode:   {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  filter: {query}")
    print(f"  matched: {len(games)} failed game(s)")
    if args.limit:
        games = games[: args.limit]
        print(f"  limited to: {len(games)} (canary)")
    print()

    enq = 0
    skipped_no_pgn = 0
    per_user = {}
    for g in games:
        gid = g.get("game_id")
        if not gid or not g.get("pgn"):
            skipped_no_pgn += 1
            continue
        uid = g.get("user_id")
        per_user[uid] = per_user.get(uid, 0) + 1
        if args.apply:
            # Drop stale failed/completed queue rows, mark the game pending,
            # and enqueue a fresh job the worker will claim.
            db.analysis_queue.delete_many({"game_id": gid})
            db.analysis_queue.insert_one({
                "game_id": gid,
                "user_id": uid,
                "pgn": g.get("pgn", ""),
                "user_color": g.get("user_color", "white"),
                "status": "pending",
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "attempts": 0,
                "retry_count": 0,
                "enqueued_by": "requeue_failed_games_2026-06-10",
                "priority": 0,
            })
            # Reset the game flags so a fresh analysis can claim/overwrite.
            db.games.update_one(
                {"game_id": gid},
                {"$set": {"analysis_status": "pending"},
                 "$unset": {"analysis_error": ""}},
            )
        enq += 1

    print(f"Games {'enqueued' if args.apply else 'WOULD enqueue'}: {enq}")
    print(f"Skipped (no pgn): {skipped_no_pgn}")
    print()
    print("By user:")
    for uid, n in sorted(per_user.items(), key=lambda x: -x[1])[:20]:
        print(f"  {str(uid)[-14:]}: {n}")

    if not args.apply:
        print("\nDRY-RUN. Re-run with --apply (add --limit 1 to canary one first).")
    else:
        pend = db.analysis_queue.count_documents({"status": "pending"})
        print(f"\nEnqueued. analysis_queue pending now: {pend}")
        print("Start the local worker to drain:  python analysis_worker.py")

    client.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Actually enqueue (default dry-run)")
    p.add_argument("--limit", type=int, default=0, help="Only requeue the first N (0 = all)")
    p.add_argument("--error-substr", type=str, default=None,
                   help="Only games whose analysis_error matches this regex")
    run(p.parse_args())


if __name__ == "__main__":
    main()
