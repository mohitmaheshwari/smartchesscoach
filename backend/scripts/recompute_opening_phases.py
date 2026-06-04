"""Recompute opening_mastery_tracker phases for all existing rows.

After Mohit 2026-06-04 loosened the FREE_PLAY → MASTERED threshold
(two paths: 3-game @65% or 10-game avg @55%), existing rows in
FREE_PLAY won't re-promote until their next game. This script forces
the recomputation across all rows so the data reflects the new rule
immediately.

Idempotent. Reads each row, applies _compute_phase, writes the new
phase only when it differs from the stored one.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/recompute_opening_phases.py        # dry-run
  docker exec chess-coach-backend python \\
    /app/backend/scripts/recompute_opening_phases.py --apply
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
from services.opening_mastery_tracker import _compute_phase

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    transitions: Counter[str] = Counter()
    changes = []

    cursor = db.user_opening_mastery.find(
        {}, {"_id": 1, "phase": 1, "games_played": 1, "accuracy_history": 1, "opening_key": 1, "user_id": 1},
    )
    async for row in cursor:
        current = row.get("phase", "introduction")
        gp = row.get("games_played", 0)
        acc = row.get("accuracy_history") or []
        new = _compute_phase(current, gp, acc)
        if new != current:
            transitions[f"{current} → {new}"] += 1
            changes.append({
                "_id": row["_id"],
                "user_id": (row.get("user_id") or "")[-12:],
                "opening_key": row.get("opening_key"),
                "from": current,
                "to": new,
                "games_played": gp,
                "accuracy": acc[-5:],
            })

    print(f"Would change {len(changes)} of N rows")
    print()
    print("Transitions:")
    for k, v in transitions.most_common():
        print(f"  {k}: {v}")
    print()
    print("Sample changes (up to 12):")
    for c in changes[:12]:
        print(f"  user=…{c['user_id']} opening={c['opening_key']:<22} "
              f"{c['from']} → {c['to']} (games={c['games_played']}, last5={c['accuracy']})")

    if not args.apply:
        print()
        print("DRY RUN — rerun with --apply to commit.")
        return 0

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for c in changes:
        await db.user_opening_mastery.update_one(
            {"_id": c["_id"]},
            {"$set": {"phase": c["to"], "updated_at": now}},
        )
    print()
    print(f"APPLIED. {len(changes)} rows updated.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
