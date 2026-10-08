"""
Cron-like: re-pick every eligible user's signature strength.

THE REASON THIS EXISTS. Mohit, 2026-10-07, on the home page: *"it won't change
over time, or would it?"* The strength is the first line a player reads, and all
39 stored strengths were written on 2026-07-02 -- 96 days earlier -- because
`assign_strength()` has **zero callers anywhere in the codebase**. It was
written, it works, it is idempotent, and nothing ever runs it. Whatever was true
of a player in July is what the page still says.

This is the mirror of scripts/assign_focuses.py, which has run daily at 03:00
since it was written. The weakness half of the picture refreshes; the strength
half froze on day one.

DIFFERENT FROM FOCUSES IN ONE IMPORTANT WAY. A focus is *locked* for a period on
purpose -- you cannot coach someone on a new thing every morning. A strength is
not a commitment, it is an observation, so it should simply be current. So this
re-picks for everyone eligible rather than skipping users who already have one,
and `assign_strength` upserts in place.

Usage:
    python scripts/assign_strengths.py            # dry-run report
    python scripts/assign_strengths.py --apply    # re-pick and write
    python scripts/assign_strengths.py --user X   # one user
"""
import argparse
import asyncio
import collections
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

from services.primary_strength_picker import (
    COLLECTION, assign_strength, pick_signature_strength,
)

# Same bar as the focus assigner: below this there is not enough evidence to
# say anything about a player, and a strength asserted from four games is the
# kind of claim that makes the whole page untrustworthy.
MIN_ANALYSED_GAMES = 10


def _age_days(value, now):
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value)[:19]).replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None
    return (now - when).days


async def main_async(apply: bool, user_id: str, limit: int) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    now = datetime.now(timezone.utc)

    if user_id:
        user_ids = [user_id]
    else:
        user_ids = [d["user_id"] async for d in db.users.find(
            {}, {"_id": 0, "user_id": 1})]
    if limit:
        user_ids = user_ids[:limit]

    print("=== %d users to consider (%s) ==="
          % (len(user_ids), "APPLY" if apply else "dry run"))

    ages = []
    async for doc in db[COLLECTION].find(
            {"type": "strength", "status": "active"},
            {"_id": 0, "updated_at": 1, "created_at": 1}):
        age = _age_days(doc.get("updated_at") or doc.get("created_at"), now)
        if age is not None:
            ages.append(age)
    if ages:
        ages.sort()
        print("    before: %d stored strengths, age in days "
              "min %d median %d max %d"
              % (len(ages), ages[0], ages[len(ages) // 2], ages[-1]))

    outcome = collections.Counter()
    changed = []
    for uid in user_ids:
        analysed = await db.game_analyses.count_documents({"user_id": uid})
        if analysed < MIN_ANALYSED_GAMES:
            outcome["skipped: too few analysed games"] += 1
            continue

        existing = await db[COLLECTION].find_one(
            {"user_id": uid, "type": "strength", "status": "active"},
            {"_id": 0, "label": 1})
        before = (existing or {}).get("label")

        picked = await pick_signature_strength(db, uid)
        if not picked:
            outcome["no strength stands out"] += 1
            continue

        if apply:
            await assign_strength(db, uid)

        if before is None:
            outcome["new strength"] += 1
            changed.append((uid, "(none)", picked["label"]))
        elif before != picked["label"]:
            outcome["CHANGED"] += 1
            changed.append((uid, before, picked["label"]))
        else:
            outcome["unchanged (refreshed)"] += 1

    print()
    for key, count in outcome.most_common():
        print("    %-34s %4d" % (key, count))

    if changed:
        print("\n=== what moved ===")
        for uid, before, after in changed[:40]:
            print("    %s  %s  ->  %s" % (uid, before, after))
        if len(changed) > 40:
            print("    ... and %d more" % (len(changed) - 40))

    if not apply:
        print("\n(dry run -- nothing written. re-run with --apply)")
    client.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--user", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply, args.user, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
