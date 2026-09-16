"""Normalise non-integer analysis_queue priorities.

WHY
---
The worker picks the next job with

    sort=[("priority", -1), ("queued_at", 1)]

and MongoDB orders BSON types before values: numbers sort BELOW strings. Under
a descending sort that puts any STRING priority ahead of every integer one. 435
rows written by a one-off July backfill carry `priority: "backfill"`, so a bulk
re-analysis job outranks live games (priority 10) and freshly-onboarded users.

Observed on prod 2026-09-16 — the next job the worker would have taken:

    priority='backfill'  coach_c7888237...     <- first
    priority=None        4c00ce98...  queued 2026-08-17
    priority=None        a8f5b0a0...  queued 2026-09-16

The writer no longer exists in the codebase, so this is a data repair, not a
code fix. Backfills belong at the BOTTOM: -10.

    python backend/scripts/repair_queue_priority_types.py            # dry run
    python backend/scripts/repair_queue_priority_types.py --apply
"""
import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BACKFILL_PRIORITY = -10


async def main(apply: bool) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "test_database")
    ]
    seen = Counter()
    targets = []
    async for row in db.analysis_queue.find(
        {}, {"_id": 1, "priority": 1, "status": 1}
    ):
        p = row.get("priority")
        seen[type(p).__name__] += 1
        if p is not None and not isinstance(p, (int, float)):
            targets.append((row["_id"], p, row.get("status")))

    print(f"mode                 : {'APPLY' if apply else 'DRY RUN'}")
    print(f"priority types found : {dict(seen)}")
    print(f"non-numeric rows     : {len(targets)}")
    by_status = Counter(s for _, _, s in targets)
    print(f"  by status          : {dict(by_status)}")
    print(f"  still pending      : {by_status.get('pending', 0)}"
          f"   <- these are actively jumping the queue")

    if targets and apply:
        for _id, _old, _ in targets:
            await db.analysis_queue.update_one(
                {"_id": _id}, {"$set": {"priority": BACKFILL_PRIORITY}}
            )
        print(f"\n  rewrote {len(targets)} rows to priority={BACKFILL_PRIORITY}")
    elif targets:
        print(f"\n  DRY RUN — would set {len(targets)} rows to "
              f"priority={BACKFILL_PRIORITY}. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args().apply)))
