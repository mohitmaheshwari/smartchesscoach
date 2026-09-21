"""Close lesson sessions that have nothing left to serve.

A learner who answered the FINAL item of a personalized lesson WRONG
advanced past the end of the item list, but `complete` required `correct`,
so the session stayed `status: "active"`. `start_lesson` resumes
`active`/`paused` sessions, so it handed that empty session back on every
request forever -- `current_item: None`, nothing to answer, no way to get
another position for that skill.

The cause is fixed in `services/teaching_engine.py` (a session now closes
when it is exhausted, whether or not the last answer was right). This
script repairs the sessions that were already bricked before that shipped.

Whether a session is bricked is decided by asking the REAL read path
(`get_personalized_lesson`) what it would serve, rather than guessing from
the stored document -- the item list is computed at serve time and is not
stored, so no field on the document can answer it.

RUN THIS AFTER THE DEPLOY, NEVER BEFORE.

    python backend/scripts/repair_bricked_lesson_sessions.py           # dry run
    python backend/scripts/repair_bricked_lesson_sessions.py --apply
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main(apply: bool) -> int:
    from services.teaching_engine import get_personalized_lesson

    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]

    open_sessions = await db.learning_sessions.find(
        {"status": {"$in": ["active", "paused"]}},
        {"_id": 0, "session_id": 1, "user_id": 1, "skill_id": 1,
         "current_index": 1, "lesson_type": 1},
    ).to_list(length=None)

    print(f"open sessions (active/paused): {len(open_sessions)}")

    bricked, healthy, unreadable = [], 0, 0
    for row in open_sessions:
        try:
            view = await get_personalized_lesson(db, row["user_id"], row["session_id"])
        except Exception as exc:
            unreadable += 1
            print(f"  ? {row['session_id'][:36]}  could not read: {exc}")
            continue
        if not isinstance(view, dict) or view.get("error"):
            unreadable += 1
            continue
        if view.get("current_item"):
            healthy += 1
        else:
            bricked.append(row)

    print(f"  still serving an item : {healthy}")
    print(f"  nothing left to serve : {len(bricked)}   <- bricked")
    if unreadable:
        print(f"  unreadable            : {unreadable}  (left alone)")

    for row in bricked:
        print(f"    {str(row['session_id'])[:36]}  user={str(row['user_id'])[:16]} "
              f"skill={row.get('skill_id')} idx={row.get('current_index')}")

    if not bricked:
        print("\nnothing to repair.")
        return 0

    if not apply:
        print("\nDRY RUN — nothing written. Re-run with --apply.")
        return 0

    now = datetime.now(timezone.utc)
    repaired = 0
    for row in bricked:
        res = await db.learning_sessions.update_one(
            {"session_id": row["session_id"], "status": {"$in": ["active", "paused"]}},
            {"$set": {
                "status": "completed",
                "completed_at": now,
                "closed_by": "repair_bricked_lesson_sessions",
            }},
        )
        repaired += res.modified_count

    print(f"\nclosed {repaired} bricked session(s).")
    print("Those learners can now start a fresh session for that skill.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
