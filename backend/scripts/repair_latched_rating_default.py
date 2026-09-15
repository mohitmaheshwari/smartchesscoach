"""Repair best_performance_rating rows latched at the fabricated 1200 default.

WHY
---
`get_user_rating_from_games()` returns {'rating': 1200, 'source': 'default'}
when it finds no rating data. Both seeding sites in `initialize_coach_memory`
assigned that straight into `performance.best_performance_rating`, which is a
MAX (see the guard in `update_memory_after_game`) - so once 1200 was written a
real, LOWER rating could never correct it.

Measured on prod 2026-09-15: 19 of 69 users sat at 1200 while chess.com /
lichess reported their true rating as 120-1065 (median 546). Those users were
rating-gated out of the 0-999 curriculum root `coached_development`, which
blocks 7 further skills, and were scored against harsher move-classification
thresholds meant for stronger players.

The code fix (same commit) stops NEW rows latching. This repairs existing ones.

Only rows whose stored value is EXACTLY the 1200 constant are touched, and only
when the extractor can supply a measured rating. Anything else is left alone.

    python backend/scripts/repair_latched_rating_default.py            # dry run
    python backend/scripts/repair_latched_rating_default.py --apply
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.coach_memory import (  # noqa: E402
    get_or_create_memory,
    get_user_rating_from_games,
)

LATCHED_DEFAULT = 1200


async def main(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "test_database")
    ]
    user_ids = await db.games.distinct("user_id")
    print(f"users with games: {len(user_ids)}")
    print(f"mode            : {'APPLY' if apply else 'DRY RUN'}\n")

    repaired = skipped_no_data = skipped_not_latched = 0
    moved_below_1000 = 0
    rows = []

    for user_id in user_ids:
        memory = await get_or_create_memory(db, user_id)
        stored = int(memory.performance.best_performance_rating or 0)
        if stored != LATCHED_DEFAULT:
            skipped_not_latched += 1
            continue

        info = await get_user_rating_from_games(db, user_id)
        source = info.get("source") or "default"
        measured = info.get("rating")
        if source == "default" or not isinstance(measured, (int, float)):
            skipped_no_data += 1
            continue

        measured = int(measured)
        if measured == stored:
            skipped_not_latched += 1
            continue

        rows.append((user_id, stored, measured, source))
        if measured < 1000:
            moved_below_1000 += 1

        if apply:
            await db.coach_memory.update_one(
                {"user_id": user_id},
                {"$set": {"performance.best_performance_rating": measured}},
            )
        repaired += 1

    for user_id, stored, measured, source in rows[:25]:
        print(f"  {user_id[:22]:<24} {stored} -> {measured:<6} ({source})")
    if len(rows) > 25:
        print(f"  ... and {len(rows) - 25} more")

    print()
    print(f"  repaired                 : {repaired}")
    print(f"  now below 1000           : {moved_below_1000}"
          f"  <- these unlock the 0-999 curriculum root")
    print(f"  skipped (no rating data) : {skipped_no_data}")
    print(f"  skipped (not latched)    : {skipped_not_latched}")
    if not apply:
        print("\n  DRY RUN - nothing written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the repairs")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
