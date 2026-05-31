"""Migrate existing defend_scholars_mate evidence to match the tightened
detector window (full_move_number <= 5).

Why this exists
───────────────
Before 2026-05-31, the defend_scholars_mate detector allowed
full_move_number <= 8, which credited the skill on delayed f7-mate
setups (move 7 Ke7, move 8 Nf6, etc.) — geometrically the same
Qxf7# threat but pedagogically a different skill for a 1300-rated
audience (Mohit confirmed). After tightening to <= 5, those evidence
entries are stale in production.

This script removes evidence entries with move_number > 5 from any
user's defend_scholars_mate skill memory AND decrements the applied
counter by the same number, so the displayed counts and the listed
evidence stay consistent.

Safety
──────
  - Dry-run by default. Pass --apply to actually mutate.
  - Idempotent: running twice with --apply is a no-op the second time.
  - Per-user diff is printed before any write.

Run from inside the backend container (mongo via $MONGO_URL):
    docker exec chess-coach-backend python /app/backend/scripts/migrate_scholars_mate_tighten.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient


SKILL_ID = "defend_scholars_mate"
MAX_MOVE_NUMBER = 5  # matches the tightened detector


async def run(apply_changes: bool):
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL not set in env.")
        sys.exit(1)
    db_name = os.environ.get("DB_NAME") or "chess_coach"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    n_users_inspected = 0
    n_users_changed = 0
    n_evidence_dropped = 0
    n_applied_decremented = 0

    cursor = db.coach_memory.find(
        {f"learning.skills.skill_id": SKILL_ID},
        {"_id": 1, "user_id": 1, "learning.skills": 1}
    )
    async for doc in cursor:
        n_users_inspected += 1
        skills = (doc.get("learning") or {}).get("skills") or []
        new_skills: List[dict] = []
        changed = False

        for skill in skills:
            if skill.get("skill_id") != SKILL_ID:
                new_skills.append(skill)
                continue

            evidence = skill.get("evidence") or []
            kept: List[dict] = []
            dropped: List[dict] = []
            for ev in evidence:
                # Only filter entries with source=detector (lesson +
                # demotion entries don't reference move_number for a
                # game position).
                src = ev.get("source")
                mv = ev.get("move_number")
                if src == "detector" and mv is not None and int(mv) > MAX_MOVE_NUMBER:
                    dropped.append(ev)
                else:
                    kept.append(ev)

            if not dropped:
                new_skills.append(skill)
                continue

            new_applied = max(0, int(skill.get("applied", 0)) - len(dropped))
            changed = True
            n_evidence_dropped += len(dropped)
            n_applied_decremented += (skill.get("applied", 0) - new_applied)

            print(f"\n  user_id={doc.get('user_id')}")
            print(f"    applied: {skill.get('applied', 0)} -> {new_applied}")
            print(f"    evidence: {len(evidence)} -> {len(kept)}  (dropped {len(dropped)})")
            for d in dropped[:5]:
                print(f"      drop move {d.get('move_number'):>2} {d.get('move_san','?'):>6}  "
                      f"game={(d.get('game_id') or '')[:18]}")

            new_skill = dict(skill)
            new_skill["evidence"] = kept
            new_skill["applied"] = new_applied
            new_skills.append(new_skill)

        if changed:
            n_users_changed += 1
            if apply_changes:
                await db.coach_memory.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"learning.skills": new_skills}}
                )

    print(f"\n=== SUMMARY ===")
    print(f"  Users inspected:           {n_users_inspected}")
    print(f"  Users with stale evidence: {n_users_changed}")
    print(f"  Evidence entries dropped:  {n_evidence_dropped}")
    print(f"  Applied counter decreased: {n_applied_decremented} total")
    print(f"  Mode:                      {'APPLIED' if apply_changes else 'DRY-RUN (no writes)'}")
    if not apply_changes:
        print(f"\nRe-run with --apply to commit the changes.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Actually write to mongo. Without this flag, dry-run only.")
    args = p.parse_args()
    asyncio.run(run(args.apply))


if __name__ == "__main__":
    main()
