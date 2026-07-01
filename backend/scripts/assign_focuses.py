"""
Cron-like: for every eligible user without an active focus, pick one.
Also runs the day-14 outcome check on any focus whose locked_until is past.

Usage:
    python scripts/assign_focuses.py            # dry-run report
    python scripts/assign_focuses.py --apply    # write focuses + close expired
"""
import argparse, asyncio, os, sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from services.primary_weakness_picker import (
    pick_next_focus, assign_focus, ensure_indexes,
    check_focus_outcome, close_focus, COLLECTION,
)


async def main_async(apply: bool, user_id: str, limit: int):
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    if apply:
        await ensure_indexes(db)

    # Step 1: outcome check on expired active focuses
    now_iso = datetime.now(timezone.utc).isoformat()
    expired = await db[COLLECTION].find({
        "status": "active",
        "locked_until": {"$lte": now_iso},
    }).to_list(length=None)
    print(f"=== Step 1: {len(expired)} expired active focuses to check ===")
    for f in expired:
        outcome = await check_focus_outcome(db, f)
        print(f"  user {f['user_id']}  topic={f['topic_key']}  → {outcome['resolution']} ({outcome.get('delta_pct')}%)  action={outcome['action']}")
        if apply:
            await close_focus(db, f, outcome)

    # Step 2: pick focuses for users without one
    q = {}
    if user_id:
        q["user_id"] = user_id
    else:
        q = {"is_analyzed": True}

    print(f"\n=== Step 2: picking focuses for users without one ===")
    picked = 0
    skipped = 0
    ineligible = 0
    seen_users = set()
    cur = db.games.aggregate([
        {"$match": q},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 10}}},
        {"$sort": {"n": -1}},
    ])
    if limit:
        # limit at cursor level
        cur = db.games.aggregate([
            {"$match": q},
            {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": 10}}},
            {"$sort": {"n": -1}},
            {"$limit": limit},
        ])
    async for row in cur:
        uid = row["_id"]
        seen_users.add(uid)
        # Already has active focus?
        existing = await db[COLLECTION].find_one({"user_id": uid, "status": "active"})
        if existing:
            skipped += 1
            continue
        if apply:
            f = await assign_focus(db, uid)
        else:
            f = await pick_next_focus(db, uid)
        if f:
            picked += 1
            name = (await db.users.find_one({"user_id": uid}, {"name": 1}) or {}).get("name", "?")
            topic = f.get("topic_key") or f.get("topic")
            score = f.get("picker_score") or f.get("score")
            ev = f.get("picker_evidence_count") or f.get("evidence_count")
            print(f"  {name[:24]:<24} → focus={topic:<32} score={score:>7.2f}  evidence={ev}")
        else:
            ineligible += 1

    print(f"\n=== Summary ===")
    print(f"users seen:               {len(seen_users)}")
    print(f"already had active focus: {skipped}")
    print(f"newly assigned focus:     {picked}")
    print(f"ineligible (no candidates or cooldown): {ineligible}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--user-id", default=None)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    asyncio.run(main_async(args.apply, args.user_id, args.limit))


if __name__ == "__main__":
    main()
