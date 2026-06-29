"""
Player Motivation — distribution read-out.

Shows how the user base answered the onboarding "What brings you to ChessGuru?"
question (self-declared). This is the strategic probe: are signups serious
improvers or casual players?

Usage (direct prod, no tunnel — see memory project_stable_prod_db_connection):
  MONGO_URL='mongodb://admin_user_mii_s_c:<pwd>@72.60.204.176:27017/?authSource=admin' \
  DB_NAME=chess_coach python3 scripts/player_motivation_distribution.py
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

LABELS = {
    "compete": "Compete and climb the ratings",
    "improve": "Get steadily better",
    "learn": "Learn and enjoy the game",
    "fun": "Just play for fun",
}
ORDER = ["compete", "improve", "learn", "fun"]


async def main():
    db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=9000
    )[os.environ.get("DB_NAME", "chess_coach")]

    total = await db.users.count_documents({})
    counts = {}
    async for row in db.users.aggregate([
        {"$group": {"_id": "$player_motivation", "n": {"$sum": 1}}}
    ]):
        counts[row["_id"]] = row["n"]

    answered = sum(n for k, n in counts.items() if k in LABELS)
    not_answered = total - answered

    print(f"\nPlayer motivation — {total} users ({answered} answered)\n")
    for key in ORDER:
        n = counts.get(key, 0)
        pct = f"{100*n/answered:.0f}%" if answered else "-"
        bar = "#" * int(round(20 * n / answered)) if answered else ""
        print(f"  {LABELS[key]:<32} {n:>4}  {pct:>4}  {bar}")
    print(f"  {'(not yet answered)':<32} {not_answered:>4}")

    # surface any unexpected stored values (typo guard)
    junk = {k: v for k, v in counts.items() if k not in LABELS and k is not None}
    if junk:
        print(f"\n  ⚠ unexpected values: {junk}")


if __name__ == "__main__":
    asyncio.run(main())
