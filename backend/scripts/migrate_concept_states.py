"""Backfill `state` onto user_concept_understanding.

docs/teaching_loop_scope.md

Before the concept test existed, `acknowledged` (and then `mastered_at`)
could be set from a 3-game clean streak alone — so a concept was marked
"understood" without the user ever demonstrating anything. It just stopped
coming up.

Those rows are NOT wrong, but they are not proof either. They carry real
streak evidence, so they migrate to MONITORING — the phase where we watch
real games — rather than to MASTERED. To be called mastered they now have
to pass a test and then stay clean.

Nothing is invented: no test result is fabricated for any row.

RUN THIS AFTER THE DEPLOY, NEVER BEFORE. Writing a state the deployed code
does not yet understand silently drops those rows out of user-facing pools.

    python backend/scripts/migrate_concept_states.py            # dry run
    python backend/scripts/migrate_concept_states.py --apply
"""

import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.concept_test_service import (  # noqa: E402
    STATE_MONITORING,
    STATE_SHOWN,
)


async def main(apply: bool) -> int:
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    coll = db.user_concept_understanding

    total = await coll.count_documents({})
    already = await coll.count_documents({"state": {"$exists": True}})
    print(f"user_concept_understanding : {total:,} rows")
    print(f"  already carrying `state` : {already:,}")

    plan = Counter()
    samples = {STATE_MONITORING: [], STATE_SHOWN: []}

    cursor = coll.find(
        {"state": {"$exists": False}},
        {"_id": 1, "concept_id": 1, "user_id": 1, "mastered_at": 1,
         "acknowledged": 1, "streak_clean": 1, "clean_games_total": 1},
    )
    async for row in cursor:
        proven_before = bool(row.get("mastered_at")) or bool(row.get("acknowledged"))
        target = STATE_MONITORING if proven_before else STATE_SHOWN
        plan[target] += 1
        if len(samples[target]) < 5:
            samples[target].append(
                f"{str(row.get('user_id'))[:18]:<18} {str(row.get('concept_id'))[:28]:<28} "
                f"streak={row.get('streak_clean') or 0:<3} clean={row.get('clean_games_total') or 0:<4} "
                f"mastered_at={'yes' if row.get('mastered_at') else 'no'}"
            )

    print("\nplanned transitions:")
    for state, n in plan.most_common():
        print(f"  -> {state:<12} {n:,}")
    print("\n  NOTE: rows land in `monitoring`, never `mastered`. They keep their")
    print("        streak evidence but must pass a test to be called understood.")

    for state, rows in samples.items():
        if rows:
            print(f"\n  sample rows -> {state}:")
            for r in rows:
                print(f"    {r}")

    if not apply:
        print("\nDRY RUN — nothing written. Re-run with --apply.")
        return 0

    moved = 0
    for target, query in (
        (STATE_MONITORING, {"state": {"$exists": False},
                            "$or": [{"mastered_at": {"$nin": [None, ""]}},
                                    {"acknowledged": True}]}),
        (STATE_SHOWN, {"state": {"$exists": False}}),
    ):
        res = await coll.update_many(query, {"$set": {"state": target}})
        moved += res.modified_count
        print(f"  wrote {res.modified_count:,} rows -> {target}")

    remaining_mastered = await coll.count_documents({"state": "mastered"})
    print(f"\ndone. {moved:,} rows migrated.")
    print(f"rows in `mastered` after migration: {remaining_mastered}  (must be 0)")
    return 0 if remaining_mastered == 0 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
