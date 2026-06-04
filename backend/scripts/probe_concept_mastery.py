"""Probe concept mastery state for one user — diagnostic for Engine 2 Phase 1.

Shows the current mastery state of every concept the user has been shown:
streak_clean, acknowledged, mastered_at, violations_total, clean_games_total.
Sorted to surface mastered concepts at top, struggling at bottom.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/probe_concept_mastery.py --user-id user_8b599930d7ef
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", default="user_8b599930d7ef")
    ap.add_argument("--email", default=None,
                    help="Look up user by email instead of user_id")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    if args.email:
        u = await db.users.find_one({"email": args.email}, {"_id": 0, "user_id": 1})
        if not u:
            print(f"user with email {args.email} not found")
            return 1
        user_id = u["user_id"]
    else:
        user_id = args.user_id

    rows = await db.user_concept_understanding.find(
        {"user_id": user_id}, {"_id": 0},
    ).to_list(None)
    if not rows:
        print(f"No concept-understanding rows for user {user_id}")
        return 0

    # Sort: mastered first (by mastered_at desc), then struggling (by violations desc).
    def sort_key(r):
        acked = r.get("acknowledged")
        return (
            0 if acked else 1,
            -(r.get("clean_games_total") or 0) if acked else -(r.get("violations_total") or 0),
        )

    rows.sort(key=sort_key)

    print(f"=== Concept mastery for user {user_id} ===")
    print(f"Total concepts on file: {len(rows)}")
    n_mastered = sum(1 for r in rows if r.get("acknowledged"))
    n_struggling = sum(1 for r in rows if (r.get("violations_total") or 0) >= 3)
    print(f"  Mastered (acknowledged=True): {n_mastered}")
    print(f"  Struggling (violations ≥ 3):  {n_struggling}")
    print()
    print(f"{'#':>3}  {'concept_id':<38}  {'state':<10}  {'streak':>6}  "
          f"{'clean':>5}  {'viol':>4}  {'shown':>6}  mastered_at")
    print("-" * 110)
    for i, r in enumerate(rows, 1):
        cid = (r.get("concept_id") or "?")[:38]
        acked = r.get("acknowledged")
        streak = r.get("streak_clean") or 0
        clean = r.get("clean_games_total") or 0
        viol = r.get("violations_total") or 0
        shown = r.get("shown_count") or 0
        mastered = (r.get("mastered_at") or "")[:19]
        state = (
            "MASTERED" if acked
            else ("STRUGGLING" if viol >= 3 else "LEARNING")
        )
        print(f"{i:>3}  {cid:<38}  {state:<10}  {streak:>6}  "
              f"{clean:>5}  {viol:>4}  {shown:>6}  {mastered}")

    print()
    print("Summary by state:")
    states = Counter()
    for r in rows:
        if r.get("acknowledged"):
            states["MASTERED"] += 1
        elif (r.get("violations_total") or 0) >= 3:
            states["STRUGGLING"] += 1
        else:
            states["LEARNING"] += 1
    for s, n in states.most_common():
        print(f"  {s:<12}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
