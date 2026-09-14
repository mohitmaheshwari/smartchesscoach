"""
What do people actually do when they arrive?
============================================

Reads `product_events` -- the collection the frontend now writes to -- and
prints the funnel. Before this pipeline existed every `track()` call in the
app was a no-op (posthog is never initialised), so questions like "why do
players abandon the diagnostic" could only be answered by reconstructing
intent from database side-effects, and several could not be answered at all.

    docker exec chess-coach-backend python scripts/product_funnel.py
    docker exec chess-coach-backend python scripts/product_funnel.py --days 7
    docker exec chess-coach-backend python scripts/product_funnel.py --event diagnostic_first_answer

Nothing here interprets. It counts what happened and says how many people it
happened to, because a funnel that editorialises is a funnel you stop
trusting.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

COLLECTION = "product_events"

# The order a new player moves through the product. Events outside this list
# are still counted, just not laid out as a funnel.
JOURNEY = [
    ("funnel_landing_viewed", "landed"),
    ("funnel_landing_cta_clicked", "clicked the landing CTA"),
    ("funnel_activation_cta", "chose a door on the hub"),
    ("diagnostic_started", "started the positions"),
    ("diagnostic_first_answer", "answered the first one"),
    ("diagnostic_completed", "finished the positions"),
    ("diagnostic_abandoned", "left the positions early"),
    ("funnel_import_done", "connected an account"),
    ("funnel_first_aha", "opened their first game"),
    ("funnel_pwc_started", "played the coach"),
    ("funnel_review_opened", "opened a review"),
    ("funnel_training_solve", "solved a training puzzle"),
    ("funnel_home_viewed", "reached home"),
]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--event", help="break one event down by its props")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    query = {"occurred_at": {"$gte": since}}

    total = await db[COLLECTION].count_documents({})
    window = await db[COLLECTION].count_documents(query)
    print(f"product_events: {total} recorded, {window} in the last {args.days} days")
    if not total:
        print("\n  Nothing recorded yet. If the frontend has just been deployed,")
        print("  this fills as people use the product.")
        return

    counts = Counter()
    people = defaultdict(set)
    anonymous = Counter()
    async for row in db[COLLECTION].find(
        query, {"_id": 0, "event": 1, "user_id": 1, "anonymous": 1}
    ):
        name = row.get("event")
        counts[name] += 1
        if row.get("user_id"):
            people[name].add(row["user_id"])
        else:
            anonymous[name] += 1

    print(f"\n{'step':34}{'events':>8}{'people':>8}{'anon':>7}")
    seen = set()
    for event, label in JOURNEY:
        seen.add(event)
        if not counts.get(event):
            continue
        print(f"  {label:32}{counts[event]:8}{len(people[event]):8}"
              f"{anonymous[event]:7}")

    other = [(e, n) for e, n in counts.most_common() if e not in seen]
    if other:
        print("\neverything else:")
        for event, n in other[:25]:
            print(f"  {event:32}{n:8}{len(people[event]):8}{anonymous[event]:7}")

    if args.event:
        print(f"\n=== {args.event} broken down by prop ===")
        by_prop = defaultdict(Counter)
        n = 0
        async for row in db[COLLECTION].find(
            dict(query, event=args.event), {"_id": 0, "props": 1}
        ):
            n += 1
            for key, value in (row.get("props") or {}).items():
                by_prop[key][str(value)] += 1
        print(f"  {n} events")
        for key in sorted(by_prop):
            top = ", ".join(f"{v}={c}" for v, c in by_prop[key].most_common(6))
            print(f"    {key:28} {top}")


if __name__ == "__main__":
    asyncio.run(main())
