#!/usr/bin/env python3
"""
Backfill users.country from chess.com public profiles (2026-08-24).

ChessGuru captured no country before today. Chess.com's /pub/player/{username}
is unauthenticated, so existing accounts CAN be filled retroactively -- unlike
lichess, which needs the user's token and is therefore forward-only.

Writes, per user:
    country         ISO-3166 alpha-2, e.g. "IN"
    country_source  "chesscom"

Normalisation goes through services/player_country so a chess.com URL can never
be stored where a lichess ISO code goes.

SAFETY
  * dry run by default
  * writes by _id, never update_one({"user_id": ...}) -- users is not
    guaranteed unique on user_id and that bug silently dropped 68 rows during
    the Gate 3 backfill
  * skips users that already have a country, so re-running is a no-op and a
    lichess-sourced country is never overwritten by chess.com
  * a failed or missing lookup writes NOTHING rather than null
  * polite pacing: chess.com asks for a serial, identified client

USAGE
    python scripts/backfill_user_country.py                # dry run
    python scripts/backfill_user_country.py --apply
"""
import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.player_country import (  # noqa: E402
    country_update_fields,
    fetch_chesscom_country,
)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--delay", type=float, default=0.35,
                    help="seconds between chess.com requests")
    args = ap.parse_args()

    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")
    ]

    import httpx

    stats = Counter()
    found = Counter()
    updates = []

    cur = db.users.find({}, {"_id": 1, "user_id": 1, "chess_com_username": 1,
                             "chesscom_username": 1, "country": 1})
    users = await cur.to_list(length=None)
    print(f"users: {len(users)}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        for u in users:
            if u.get("country"):
                stats["skipped (already has country)"] += 1
                continue
            uname = u.get("chess_com_username") or u.get("chesscom_username")
            if not uname:
                stats["no chess.com username"] += 1
                continue
            c = await fetch_chesscom_country(uname, client=client)
            if c:
                stats["resolved"] += 1
                found[c] += 1
                updates.append((u["_id"], c))
            else:
                stats["lookup returned nothing"] += 1
            await asyncio.sleep(args.delay)

    print(f"\n=== {'APPLY' if args.apply else 'DRY RUN'} ===")
    for k, v in sorted(stats.items()):
        print(f"  {k:34} {v}")
    print(f"\n  country distribution ({len(found)} distinct):")
    for c, n in found.most_common():
        print(f"    {c}  {n}")

    if not args.apply:
        print(f"\n  would update {len(updates)} users. Re-run with --apply.")
        return

    n = 0
    for _id, c in updates:
        res = await db.users.update_one(
            {"_id": _id}, {"$set": country_update_fields(c, "chesscom")}
        )
        n += res.matched_count
    print(f"\n  updated {n}/{len(updates)} users (by _id)")
    if n != len(updates):
        print(f"  FAIL: {len(updates) - n} intended writes matched no document")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
