"""
One-shot backfill: compute + persist user_opening_profile for every
user that has analyzed games. Phase-3 Component 1 of the opening
intelligence layer.

Usage:
  MONGO_URL=mongodb://... docker exec -i chess-coach-backend python \\
    scripts/backfill_opening_profiles.py [--limit N] [--user USER_ID]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--user", type=str, default="")
    parser.add_argument("--out", type=str, default="/tmp/opening_profiles_backfill.json")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required.", file=sys.stderr)
        sys.exit(1)

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.user_opening_profile import (
        compute_opening_profile,
        persist_opening_profile,
        ensure_opening_profile_indexes,
        USER_OPENING_PROFILE_VERSION,
    )

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    print("Ensuring indexes on user_opening_profiles…", file=sys.stderr)
    await ensure_opening_profile_indexes(db)

    # Identify all users with at least one analyzed game.
    pipeline = [
        {"$match": {"is_analyzed": True}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]
    if args.user:
        pipeline = [{"$match": {"is_analyzed": True, "user_id": args.user}}] + pipeline[1:]
    target_users = []
    async for r in db.games.aggregate(pipeline):
        uid = r.get("_id")
        if uid:
            target_users.append((uid, r.get("n", 0)))
        if args.limit and len(target_users) >= args.limit:
            break
    print(f"Target users: {len(target_users)}", file=sys.stderr)

    t0 = time.time()
    successes = 0
    failures = 0
    per_user_report = []

    for i, (uid, n) in enumerate(target_users, 1):
        try:
            profile = await compute_opening_profile(db, uid)
            ok = await persist_opening_profile(db, profile)
            if ok:
                successes += 1
            else:
                failures += 1
            per_user_report.append({
                "user_id": uid,
                "games": n,
                "white_top_3": [
                    {"name": o["name"], "games": o["games"], "wr": o["win_rate"]}
                    for o in profile["white"]["openings"][:3]
                ],
                "black_top_3": [
                    {"name": o["name"], "games": o["games"], "wr": o["win_rate"]}
                    for o in profile["black"]["openings"][:3]
                ],
                "trap_exposure_count": len(profile["trap_exposure"]["by_trap"]),
            })
        except Exception as e:
            failures += 1
            per_user_report.append({"user_id": uid, "error": str(e)[:200]})

        if i % 10 == 0:
            print(f"  progress: {i}/{len(target_users)}  ok={successes} fail={failures}", file=sys.stderr)

    elapsed = time.time() - t0

    out = {
        "elapsed_seconds": round(elapsed, 1),
        "users_processed": len(target_users),
        "successes": successes,
        "failures": failures,
        "version": USER_OPENING_PROFILE_VERSION,
        "per_user": per_user_report,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))

    print()
    print(f"Backfill complete in {elapsed:.1f}s")
    print(f"  users processed: {len(target_users)}")
    print(f"  successes:       {successes}")
    print(f"  failures:        {failures}")
    print(f"\nFull report: {args.out}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
