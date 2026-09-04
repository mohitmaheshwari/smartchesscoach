"""Capture immutable Phase 8 pre-enrollment baselines.

Read-only by default. Apply requires an explicit selector, UTC cutoff, source
commit and confirmation phrase. Aggregate output contains no email or user id.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

from services.complete_coaching_access import BASELINE_COLLECTION
from services.phase8_release_evidence import (
    FOCUS_KIND,
    build_pre_enrollment_baseline,
    same_immutable_baseline,
)


CONFIRMATION = "phase8-baselines"


def _parse_cutoff(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--cutoff must include a timezone")
    return parsed.astimezone(timezone.utc)


async def _resolve_users(db, *, email: Optional[str], all_users: bool):
    if email:
        user = await db.users.find_one(
            {"email": {"$regex": f"^{email}$", "$options": "i"}},
            {"_id": 0, "user_id": 1, "role": 1},
        )
        return [user] if user else []
    if not all_users:
        raise ValueError("choose --email for one account or --all for the cohort")
    users = await db.users.find(
        {},
        {"_id": 0, "user_id": 1, "role": 1},
    ).to_list(length=None)
    return [
        user
        for user in users
        if str(user.get("role") or "user").strip().lower()
        not in {"admin", "super_admin"}
    ]


async def run(
    *,
    apply: bool,
    email: Optional[str],
    all_users: bool,
    cutoff: datetime,
    source_commit: str,
) -> Dict[str, Any]:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        users = await _resolve_users(db, email=email, all_users=all_users)
        report: Dict[str, Any] = {
            "mode": "apply" if apply else "dry_run",
            "cutoff_at": cutoff.isoformat(),
            "users_scanned": len(users),
            "eligible_focus_users": 0,
            "would_create": 0,
            "created": 0,
            "already_current": 0,
            "insufficient_pre_period": 0,
            "invalid": 0,
            "reasons": {},
        }
        reasons = Counter()
        if apply:
            await db[BASELINE_COLLECTION].create_index(
                [("user_id", 1), ("target_lock_id", 1)],
                unique=True,
            )
        for user in users:
            user_id = str((user or {}).get("user_id") or "")
            try:
                proposed = await build_pre_enrollment_baseline(
                    db,
                    user_id,
                    cutoff=cutoff,
                    source_commit=source_commit,
                )
            except ValueError as exc:
                reason = str(exc)
                reasons[reason] += 1
                if reason == "current exact Plan focus is required":
                    continue
                report["invalid"] += 1
                continue
            report["eligible_focus_users"] += 1
            report["insufficient_pre_period"] += int(
                proposed["status"] == "insufficient_pre_period"
            )
            existing = await db[BASELINE_COLLECTION].find_one(
                {"_id": proposed["_id"]}
            )
            if existing:
                if not same_immutable_baseline(existing, proposed):
                    report["invalid"] += 1
                    reasons["immutable baseline conflict"] += 1
                    continue
                report["already_current"] += 1
                continue
            report["would_create"] += 1
            if apply:
                await db[BASELINE_COLLECTION].insert_one(proposed)
                report["created"] += 1
        report["reasons"] = dict(sorted(reasons.items()))
        return report
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email")
    target.add_argument("--all", action="store_true", dest="all_users")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--source-commit", default=os.environ.get("GIT_COMMIT", ""))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing write: --confirm must equal {CONFIRMATION!r}")
    if not args.source_commit:
        raise SystemExit("--source-commit or GIT_COMMIT is required")
    report = asyncio.run(run(
        apply=args.apply,
        email=args.email,
        all_users=args.all_users,
        cutoff=_parse_cutoff(args.cutoff),
        source_commit=args.source_commit,
    ))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report_json:
        Path(args.report_json).write_text(rendered + "\n", encoding="utf-8")
    if report["invalid"]:
        return 1
    if args.apply and report["created"] != report["would_create"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
