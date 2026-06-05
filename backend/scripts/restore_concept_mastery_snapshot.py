"""Rollback companion to cleanup_artifact_mastery.py.

Restores user_concept_understanding from a snapshot JSON written before
the cleanup ran. Use this if a cleanup --apply over-stripped and you
need to revert.

Usage:

    python backend/scripts/restore_concept_mastery_snapshot.py \\
        backend/snapshots/user_concept_understanding_pre_cleanup_2026-06-06_0312.json

The script restores ONLY the fields that the cleanup touches:
  - mastered_at
  - acknowledged
  - mastery_stripped_at         (cleared)
  - mastery_stripped_reason     (cleared)
  - mastery_stripped_thresholds (cleared)

Other fields (streak_clean, clean_games_total, last_violation_at, etc.)
are left as-is — they may have advanced during the time between snapshot
and restore, and we don't want to undo organic events.

Idempotent: re-running on the same snapshot restores to the same state.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from motor.motor_asyncio import AsyncIOMotorClient


async def run(snapshot_path: Path):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if not snapshot_path.exists():
        print(f"ERROR: snapshot not found: {snapshot_path}")
        sys.exit(1)

    with open(snapshot_path, "r", encoding="utf-8") as f:
        snap = json.load(f)

    rows = snap.get("rows", [])
    print(f"=== Restore from snapshot: {snapshot_path.name} ===")
    print(f"  exported_at: {snap.get('exported_at')}")
    print(f"  rows in snapshot: {len(rows)}")
    print()

    restored = 0
    skipped = 0
    for row in rows:
        uid = row.get("user_id")
        cid = row.get("concept_id")
        mastered_at = row.get("mastered_at")
        acknowledged = row.get("acknowledged", False)
        if not (uid and cid):
            skipped += 1
            continue
        # Only restore mastery fields. Don't unwind streak_clean / totals
        # — those may have legitimate updates since the snapshot.
        result = await db.user_concept_understanding.update_one(
            {"user_id": uid, "concept_id": cid},
            {"$set": {
                "mastered_at": mastered_at,
                "acknowledged": acknowledged,
            },
             "$unset": {
                "mastery_stripped_at": "",
                "mastery_stripped_reason": "",
                "mastery_stripped_thresholds": "",
            }},
        )
        if result.matched_count > 0:
            restored += 1
        else:
            skipped += 1

    print(f"Restored: {restored}")
    print(f"Skipped:  {skipped} (row no longer matches user_id+concept_id)")
    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_path", type=Path,
                        help="Path to the pre_cleanup JSON snapshot")
    args = parser.parse_args()
    asyncio.run(run(args.snapshot_path))


if __name__ == "__main__":
    main()
