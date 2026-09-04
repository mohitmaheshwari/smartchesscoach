"""Safely enroll exact accounts in the Phase 6 Game Review validation cohort.

Credentials are read only from the backend container environment. The command
is read-only unless both ``--apply`` and the exact confirmation phrase are
provided.

Examples::

    python scripts/configure_personalized_review_validation.py \
        --email reviewer@example.com

    python scripts/configure_personalized_review_validation.py \
        --email reviewer@example.com --apply --confirm phase6-validation
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Iterable


CONFIRMATION = "phase6-validation"
FEATURE_PATH = "feature_flags.personalized_game_review_coach"


def normalize_emails(values: Iterable[str]) -> tuple[str, ...]:
    emails = tuple(sorted({str(value or "").strip().lower() for value in values}))
    if not emails or any("@" not in email for email in emails):
        raise ValueError("Every validation account must have an explicit email")
    return emails


def feature_update(*, enabled: bool) -> Dict[str, Any]:
    return {
        "$set": {
            f"{FEATURE_PATH}.enabled": bool(enabled),
            f"{FEATURE_PATH}.validation_compare": bool(enabled),
            f"{FEATURE_PATH}.cohort": "phase6_validation_2026_09",
        }
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--confirm", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    emails = normalize_emails(args.email)
    if args.apply and args.confirm != CONFIRMATION:
        raise SystemExit(
            f"Refusing write: --confirm must equal {CONFIRMATION!r}"
        )

    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    database_name = os.environ.get("DB_NAME")
    if not mongo_url or not database_name:
        raise SystemExit("MONGO_URL and DB_NAME must come from the environment")
    db = MongoClient(mongo_url)[database_name]
    users = list(db.users.find(
        {"email": {"$in": list(emails)}},
        {"_id": 0, "user_id": 1, "email": 1, FEATURE_PATH: 1},
    ))
    found = {str(user.get("email") or "").lower() for user in users}
    missing = sorted(set(emails) - found)
    report = {
        "mode": "disable" if args.disable else "enable",
        "apply": bool(args.apply),
        "matched": [
            {"user_id": user.get("user_id"), "email": user.get("email")}
            for user in users
        ],
        "missing": missing,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if missing:
        raise SystemExit("Refusing write because one or more exact emails are missing")
    if not args.apply:
        print("DRY RUN ONLY — no user document was changed.")
        return 0

    update = feature_update(enabled=not args.disable)
    for user in users:
        result = db.users.update_one(
            {"user_id": user["user_id"], "email": user["email"]},
            update,
        )
        if result.matched_count != 1:
            raise SystemExit(f"Enrollment changed underneath us: {user['user_id']}")
    print(f"Updated {len(users)} exact validation account(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
