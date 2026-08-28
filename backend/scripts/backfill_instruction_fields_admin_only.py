"""backfill_instruction_fields_admin_only.py

Sprint 2 (docs/one_surviving_instruction_scope.md) ships instruction_id/
instruction_text/instruction_version only on NEW user_active_focus docs
(written by assign_focus going forward). Existing active focuses --
including admin/super_admin accounts' own current focus -- predate this
and have none of these fields. Since a focus can be locked for up to 14
days, that means the intended internal testers couldn't actually
experience Sprint 2 until their current focus naturally expires and a
new one gets assigned, unless it's backfilled.

Scope of this script (2026-08-08, external review of b0105f21): admin/
super_admin accounts ONLY, and only their currently-`status: "active"`,
`topic_key: "piece_safety"` focus (V1's boundary -- see the scope doc).
Never touches a real user's document. Computes instruction_text from
the doc's OWN already-stored subtype_histogram/rating_band/rating_used
-- reuses the exact same _tier_closing lookup assign_focus uses, does
NOT re-run the picker or change which topic/subtype is assigned.

Usage:
  python backend/scripts/backfill_instruction_fields_admin_only.py            # dry-run report
  python backend/scripts/backfill_instruction_fields_admin_only.py --apply    # write
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.focus_bridge import _pick_dominant_subtype  # noqa: E402
from services.primary_weakness_picker import (  # noqa: E402
    INSTRUCTION_TEMPLATE_VERSION,
    _tier_closing,
)

ROLLOUT_ROLES = ("admin", "super_admin")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="actually write (default: dry-run report only)")
    args = p.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    admin_users = await db.users.find(
        {"role": {"$in": list(ROLLOUT_ROLES)}}, {"_id": 0, "user_id": 1, "role": 1}
    ).to_list(100)
    admin_ids = {u["user_id"] for u in admin_users}
    print(f"Admin/super_admin accounts: {len(admin_ids)} ({sorted(admin_ids)})\n")

    candidates = await db.user_active_focus.find({
        "status": "active",
        "topic_key": "piece_safety",
        "$or": [{"type": {"$exists": False}}, {"type": "weakness"}],
        "user_id": {"$in": list(admin_ids)},
    }).to_list(100)

    print(f"Candidate active piece_safety focuses belonging to admin accounts: {len(candidates)}\n")

    to_update = []
    for doc in candidates:
        if doc.get("instruction_text"):
            print(f"  SKIP {doc['user_id']}: already has instruction_text")
            continue
        dominant_subtype = _pick_dominant_subtype(doc.get("subtype_histogram") or {})
        if not dominant_subtype:
            print(f"  SKIP {doc['user_id']}: no subtype_histogram to derive an instruction from")
            continue
        instruction_text = _tier_closing(
            doc.get("rating_band") or "intermediate", dominant_subtype, doc.get("rating_used")
        )
        to_update.append({
            "_id": doc["_id"],
            "user_id": doc["user_id"],
            "instruction_id": str(doc["_id"]),  # reuse the doc's own real _id, same as assign_focus does
            "instruction_text": instruction_text,
            "instruction_version": INSTRUCTION_TEMPLATE_VERSION,
            "instruction_subtype": dominant_subtype,
        })
        print(f"  WOULD UPDATE {doc['user_id']}: subtype={dominant_subtype!r} "
              f"instruction_text={instruction_text!r}")

    print(f"\n{len(to_update)} doc(s) to update.")
    if not args.apply:
        print("Dry run -- no writes made. Pass --apply to write.")
        return

    for u in to_update:
        await db.user_active_focus.update_one(
            {"_id": u["_id"]},
            {"$set": {
                "instruction_id": u["instruction_id"],
                "instruction_text": u["instruction_text"],
                "instruction_version": u["instruction_version"],
                "instruction_subtype": u["instruction_subtype"],
            }},
        )
    print(f"Applied. {len(to_update)} doc(s) updated.")


if __name__ == "__main__":
    asyncio.run(main())
