"""Enroll or pause exact accounts through the existing review feature flag.

This is the only Phase 8 cohort mutation. It refuses enrollment unless the
global target is locked and the exact user already has an immutable baseline.
Pausing keeps cohort, baseline and journey history so the UI can explain that
the lesson is saved instead of silently disappearing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.complete_coaching_access import (
    BASELINE_COLLECTION,
    BASELINE_VERSION,
    TARGET_COLLECTION,
    TARGET_LOCK_ID,
)
from services.game_review_contracts import USER_FEATURE_FLAG


CONFIRMATION = "phase8-pilot"
COHORT = "phase8_release_rescue_2026_09"
FEATURE_PATH = f"feature_flags.{USER_FEATURE_FLAG}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    emails = sorted({str(value).strip().lower() for value in args.email})
    if any("@" not in email for email in emails):
        raise SystemExit("Every account must be an explicit email")
    if args.apply and args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing write: --confirm must equal {CONFIRMATION!r}")

    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    database_name = os.environ.get("DB_NAME")
    if not mongo_url or not database_name:
        raise SystemExit("MONGO_URL and DB_NAME must come from the environment")
    client = MongoClient(mongo_url)
    try:
        db = client[database_name]
        target = db[TARGET_COLLECTION].find_one(
            {"_id": TARGET_LOCK_ID, "status": "locked"}
        )
        if not target and not args.disable:
            raise SystemExit("Phase 8 target is not locked")
        users = list(db.users.find(
            {"email": {"$in": emails}},
            {"_id": 0, "user_id": 1, "email": 1, "role": 1, FEATURE_PATH: 1},
        ))
        found = {str(user.get("email") or "").lower() for user in users}
        missing = sorted(set(emails) - found)
        if missing:
            raise SystemExit("One or more exact emails did not resolve")

        rows = []
        for user in users:
            if str(user.get("role") or "user").lower() in {"admin", "super_admin"}:
                raise SystemExit("Real-user Phase 8 enrollment excludes admin roles")
            baseline = db[BASELINE_COLLECTION].find_one({
                "user_id": user["user_id"],
                "baseline_version": BASELINE_VERSION,
                "target_lock_id": TARGET_LOCK_ID,
            })
            if not baseline and not args.disable:
                raise SystemExit(
                    f"Immutable pre-enrollment baseline missing for {user['email']}"
                )
            rows.append({
                "email": user["email"],
                "baseline_id": str((baseline or {}).get("_id") or ""),
                "current_enabled": bool(
                    (((user.get("feature_flags") or {}).get(
                        USER_FEATURE_FLAG
                    ) or {}).get("enabled") is True)
                ),
            })
        report = {
            "mode": "pause" if args.disable else "enroll",
            "apply": bool(args.apply),
            "target_lock_id": TARGET_LOCK_ID if target else None,
            "matched": rows,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if not args.apply:
            print("DRY RUN ONLY — no enrollment changed.")
            return 0

        now = datetime.now(timezone.utc)
        for user, row in zip(users, rows):
            if args.disable:
                update = {"$set": {
                    f"{FEATURE_PATH}.enabled": False,
                    f"{FEATURE_PATH}.phase8_paused_at": now,
                }}
            else:
                update = {"$set": {
                    f"{FEATURE_PATH}.enabled": True,
                    f"{FEATURE_PATH}.validation_compare": False,
                    f"{FEATURE_PATH}.cohort": COHORT,
                    f"{FEATURE_PATH}.phase8_enrolled_at": now,
                    f"{FEATURE_PATH}.phase8_target_lock_id": TARGET_LOCK_ID,
                    f"{FEATURE_PATH}.phase8_baseline_id": row["baseline_id"],
                }}
            result = db.users.update_one(
                {"user_id": user["user_id"], "email": user["email"]},
                update,
            )
            if result.matched_count != 1:
                raise SystemExit("Enrollment changed underneath this command")
        print(f"Updated {len(users)} exact account(s).")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
