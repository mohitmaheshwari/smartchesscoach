"""
Day-14 focus outcome check — cron-runnable.

For every active focus whose locked_until is past, computes the outcome
(improved/stuck/regressed) and either:
  - closes it with a celebrate/escalate action, or
  - extends by 7 days if stuck

Suitable to run daily via cron:
    0 3 * * *  python /app/backend/scripts/run_focus_outcome_checks.py --apply

Prints a summary for logging.
"""
import argparse, asyncio, os, sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from services.primary_weakness_picker import (
    check_focus_outcome, close_focus, COLLECTION,
)


async def main_async(apply: bool):
    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    now_iso = datetime.now(timezone.utc).isoformat()
    expired = await db[COLLECTION].find({
        "status": "active",
        "locked_until": {"$lte": now_iso},
    }).to_list(length=None)
    print(f"=== {'APPLY' if apply else 'DRY-RUN'} — {len(expired)} focuses due for outcome check ===\n")

    from collections import Counter
    outcomes = Counter()

    for f in expired:
        outcome = await check_focus_outcome(db, f)
        outcomes[outcome["resolution"]] += 1
        user = await db.users.find_one({"user_id": f["user_id"]}, {"name": 1})
        name = (user or {}).get("name", "?")
        delta = outcome.get("delta_pct")
        delta_str = f"{delta:+}%" if delta is not None else "n/a"
        print(f"  {name[:24]:<24} {f['topic_key']:<32} → {outcome['resolution']:<10} {delta_str:>8}  action={outcome['action']}")
        if apply:
            await close_focus(db, f, outcome)

    print(f"\nOutcome breakdown: {dict(outcomes)}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    main()
