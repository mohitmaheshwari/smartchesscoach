"""One-shot: rename rule_of_square → endgame_rule_of_square in
coach_memory.learning.skills, preserving every evidence entry and
the running counters.

Background (Mohit 2026-06-01): the earlier backfills
(backfill_rule_of_square.py / rebuild_rule_of_square.py) wrote
under skill_id = "rule_of_square" — that's the content_ref in
skill_tree.json, NOT the canonical skill_id. The skill_id everywhere
else (live registry, mastery summary, EvidenceModal lookup,
SkillProgress schema, tests) is "endgame_rule_of_square".

Effect of the bug: the user had 22 detector-credited evidence
entries, but /engine2/skill-evidence/endgame_rule_of_square saw an
empty skill, and /engine2/mastery-summary classified ROS as
"unseen" — so "Learn next" wrongly recommended it. This script
moves the data to the canonical key, after which both UI surfaces
just work.

Idempotent. Dry-run by default; pass --apply to commit.

Behavior per user:
  - No 'rule_of_square' entry: no-op.
  - Has 'rule_of_square' but no canonical entry: rename in place.
  - Has both: merge evidence by (game_id, move_number), sum
    counters, drop the old entry.

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/migrate_ros_skill_id.py
    docker exec chess-coach-backend python /app/backend/scripts/migrate_ros_skill_id.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

OLD_ID = "rule_of_square"
NEW_ID = "endgame_rule_of_square"


def _migrate_skills(skills):
    """Return (new_skills, action) where action is one of:
    'noop' | 'rename' | 'merge'. Mutates nothing on the input list.
    """
    old = next((s for s in skills if s.get("skill_id") == OLD_ID), None)
    if old is None:
        return list(skills), "noop", 0
    canonical = next((s for s in skills if s.get("skill_id") == NEW_ID), None)
    new_skills = [s for s in skills if s.get("skill_id") != OLD_ID]
    if canonical is None:
        renamed = dict(old)
        renamed["skill_id"] = NEW_ID
        if not renamed.get("skill_type"):
            renamed["skill_type"] = "endgame"
        new_skills.append(renamed)
        return new_skills, "rename", len(old.get("evidence") or [])
    # Both exist — merge.
    canonical = dict(canonical)
    existing_keys = {
        (e.get("game_id"), e.get("move_number"))
        for e in (canonical.get("evidence") or [])
    }
    added = 0
    canonical_ev = list(canonical.get("evidence") or [])
    for ev in (old.get("evidence") or []):
        k = (ev.get("game_id"), ev.get("move_number"))
        if k in existing_keys:
            continue
        canonical_ev.append(ev)
        existing_keys.add(k)
        added += 1
    canonical["evidence"] = canonical_ev
    canonical["seen"]    = int(canonical.get("seen", 0))    + int(old.get("seen", 0))
    canonical["applied"] = int(canonical.get("applied", 0)) + int(old.get("applied", 0))
    canonical["correct"] = int(canonical.get("correct", 0)) + int(old.get("correct", 0))
    canonical["wrong"]   = int(canonical.get("wrong", 0))   + int(old.get("wrong", 0))
    new_skills = [s for s in new_skills if s.get("skill_id") != NEW_ID] + [canonical]
    return new_skills, "merge", added


async def main_async(apply_changes: bool):
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL not set."); sys.exit(1)
    db_name = os.environ.get("DB_NAME") or "chess_coach"
    db = AsyncIOMotorClient(mongo_url)[db_name]

    totals = {"users_total": 0, "users_renamed": 0, "users_merged": 0,
              "users_noop": 0, "evidence_moved": 0}

    async for mem in db.coach_memory.find({}, {"_id": 1, "user_id": 1, "learning": 1}):
        totals["users_total"] += 1
        learning = mem.get("learning") or {}
        skills = learning.get("skills") or []
        new_skills, action, moved = _migrate_skills(skills)
        if action == "noop":
            totals["users_noop"] += 1
            continue
        totals[f"users_{action}d"] += 1
        totals["evidence_moved"] += moved
        print(f"user={mem.get('user_id')}  action={action}  moved={moved}")
        if apply_changes:
            await db.coach_memory.update_one(
                {"_id": mem["_id"]},
                {"$set": {"learning.skills": new_skills}}
            )

    print("\n=== TOTALS ===")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    print(f"  mode: {'APPLIED' if apply_changes else 'DRY-RUN (no writes)'}")
    if not apply_changes:
        print("\nRe-run with --apply to commit.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    asyncio.run(main_async(args.apply))


if __name__ == "__main__":
    main()
