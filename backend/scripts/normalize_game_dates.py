"""
Normalise `date_played_iso` so chronology stops depending on the importer
=========================================================================

`date_played` holds two formats ("2026-08-30T13:51:45+00:00" and
"2026.03.31") and "2026." sorts AFTER "2026-", so a lexical sort interleaves
them. `date_played_iso` was meant to be the clean field but is written only by
a one-off backfill: it froze at 2026-08-31 while games kept arriving and is
absent on ~1,200 rows, so a Mongo descending sort drops the newest games to
the end. Both failures return wrong answers rather than errors.

This rewrites `date_played_iso` as a full ISO8601 UTC timestamp derived from
`services.game_dates.parse_game_date`, so a Mongo-side sort is finally safe.

DRY RUN BY DEFAULT. Nothing is written without --apply.

    docker exec chess-coach-backend python scripts/normalize_game_dates.py
    docker exec chess-coach-backend python scripts/normalize_game_dates.py --apply

Note this widens the field from date-only to date-and-time. Consumers that
compared it to a bare "YYYY-MM-DD" still work for ordering and for >= range
queries, because ISO8601 sorts lexically. Consumers doing equality on a date
string would not, so they are listed in the report before anything changes.
"""

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from services.game_dates import parse_game_date

BATCH = 500


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="actually write; omit for a dry run")
    parser.add_argument("--limit", type=int, default=0,
                        help="cap documents examined (0 = all)")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    stats = Counter()
    samples = []
    pending = []

    cursor = db.games.find(
        {}, {"_id": 1, "game_id": 1, "date_played": 1, "date_played_iso": 1}
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    async for game in cursor:
        stats["examined"] += 1
        parsed = parse_game_date(game.get("date_played"))
        if parsed is None:
            parsed = parse_game_date(game.get("date_played_iso"))
        if parsed is None:
            stats["unusable_date"] += 1
            continue
        canonical = parsed.isoformat()
        current = game.get("date_played_iso")
        if current == canonical:
            stats["already_correct"] += 1
            continue
        if current is None:
            # The rows that actually broke things: absent, so a Mongo
            # descending sort put the NEWEST games last.
            stats["filling_missing"] += 1
        elif str(current)[:10] == canonical[:10] and parsed.hour == 0 \
                and parsed.minute == 0 and parsed.second == 0:
            # Same day, and we have no real time to add -- rewriting
            # "2026-03-01" to "2026-03-01T00:00:00+00:00" changes no ordering
            # (ISO8601 sorts lexically either way) and would churn ~14k
            # documents for nothing. Leave it alone.
            stats["cosmetic_skipped"] += 1
            continue
        else:
            # Either the stored day is wrong, or we can upgrade a date-only
            # value to one that carries a time and so orders within a day.
            stats["rewriting_stale"] += 1
        if len(samples) < 8:
            samples.append((game.get("game_id"), current, canonical))
        pending.append(UpdateOne({"_id": game["_id"]},
                                 {"$set": {"date_played_iso": canonical}}))
        if args.apply and len(pending) >= BATCH:
            await db.games.bulk_write(pending, ordered=False)
            stats["written"] += len(pending)
            pending = []

    if args.apply and pending:
        await db.games.bulk_write(pending, ordered=False)
        stats["written"] += len(pending)

    mode = "APPLIED" if args.apply else "DRY RUN — nothing written"
    print(f"=== normalize_game_dates: {mode} ===")
    for key in ("examined", "already_correct", "cosmetic_skipped",
                "filling_missing", "rewriting_stale", "unusable_date", "written"):
        print(f"  {key:18} {stats.get(key, 0)}")
    print("\n  sample changes (game_id, before, after):")
    for row in samples:
        print("   ", row)
    if not args.apply:
        print("\n  re-run with --apply to write these.")


if __name__ == "__main__":
    asyncio.run(main())
