"""Apply the strict-gated authoring safe subset as live caption overrides.

Companion to authoring_safe_subset.py. Reads
_snapshots/authoring_safe_subset.json (the 73 items that passed the
strict gate) and:

  1. Upserts each into the `authored_caption_overrides` collection,
     keyed by (game_id, move_number, move_san). The V5 service's
     render path checks this collection on every move; when a hit
     exists, Parth's caption replaces the rendered one (see hook in
     services/game_decryption_v5_service.py).

  2. Marks each source feedback in move_feedback as status=valid +
     admin_notes pointing at this run, so the queue empties cleanly
     and we can audit which apply run produced each override.

Idempotent. Re-running upserts the same overrides without dupes;
marking feedback that's already 'valid' is a no-op (still rewrites
the admin_notes for traceability).

Usage (in container):

    # Dry-run preview (default — shows what WOULD be applied, no writes):
    python /app/backend/scripts/authoring_apply_safe_subset.py

    # Actually write:
    python /app/backend/scripts/authoring_apply_safe_subset.py --apply

The dry-run prints a per-item summary so Mohit can eyeball the
subset one last time before flipping --apply.
"""
import os
import asyncio
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


SNAP_DIR = Path("/app/backend/scripts/_snapshots")
SAFE_JSON = SNAP_DIR / "authoring_safe_subset.json"


async def main(apply: bool):
    if not SAFE_JSON.exists():
        print(f"FATAL: {SAFE_JSON} not found. Run authoring_safe_subset.py first.")
        return

    safe = json.loads(SAFE_JSON.read_text())
    if not safe:
        print("Safe subset is empty. Nothing to apply.")
        return

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]

    print(f"=== {'APPLYING' if apply else 'DRY-RUN PREVIEW'} ===")
    print(f"Items in safe subset: {len(safe)}")
    print()

    upserts = 0
    feedback_marked = 0
    already_overridden = 0

    for item in safe:
        gid = item.get("game_id")
        mn = item.get("move_number")
        san = item.get("move_san")
        if not gid or mn is None or not san:
            print(f"  SKIP: missing key fields on {item.get('feedback_id')}")
            continue

        override_doc = {
            "game_id": gid,
            "move_number": mn,
            "move_san": san,
            "fen": item.get("fen"),
            "caption": item.get("suggested_caption"),
            "source_feedback_id": item.get("feedback_id"),
            "source_user_id": item.get("user_name"),
            "severity": item.get("severity"),
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "apply_run": "authoring_safe_subset_2026-06-03",
        }

        existing = await db.authored_caption_overrides.find_one(
            {"game_id": gid, "move_number": mn, "move_san": san},
            {"_id": 0, "source_feedback_id": 1},
        )
        if existing:
            already_overridden += 1

        if apply:
            await db.authored_caption_overrides.update_one(
                {"game_id": gid, "move_number": mn, "move_san": san},
                {"$set": override_doc},
                upsert=True,
            )
            upserts += 1
            # Mark the source feedback as valid
            r = await db.move_feedback.update_one(
                {"feedback_id": item.get("feedback_id")},
                {"$set": {
                    "status": "valid",
                    "admin_notes": (
                        f"Applied as override on {datetime.now(timezone.utc).date()}; "
                        f"strict-gate authoring_safe_subset run."
                    ),
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            if r.matched_count:
                feedback_marked += 1
        else:
            # Dry-run line per item — short form
            print(
                f"  m{mn} {san} [{item.get('severity')}] cp={item.get('cp_loss')}  "
                f"{item.get('feedback_id')}  "
                f"({'EXISTING' if existing else 'NEW'})"
            )

    print()
    print(f"Summary:")
    print(f"  to-upsert items:   {len(safe)}")
    print(f"  already existing:  {already_overridden}")
    print(f"  new overrides:     {len(safe) - already_overridden}")
    if apply:
        print(f"  upserts run:       {upserts}")
        print(f"  feedback marked:   {feedback_marked}")
        print("\nApplied. authored_caption_overrides is now the source of truth for these positions.")
    else:
        print("\nDry-run only — no writes. Re-run with --apply to commit.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Commit upserts + status updates. Without this, dry-run only.")
    args = p.parse_args()
    asyncio.run(main(args.apply))
