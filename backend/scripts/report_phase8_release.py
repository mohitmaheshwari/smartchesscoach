"""Read-only Phase 8 reach and 42-day review report.

The report contains aggregates only. It never prints or writes user IDs,
emails, game IDs, positions, credentials, or lesson answers.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.complete_coaching_access import (  # noqa: E402
    TARGET_COLLECTION,
    TARGET_LOCK_ID,
)
from services.game_review_contracts import USER_FEATURE_FLAG  # noqa: E402
from services.phase8_release_evidence import (  # noqa: E402
    build_phase8_journey_projection,
)


REPORT_VERSION = "phase8_release_report.v1"
COHORT = "phase8_release_rescue_2026_09"
REVIEW_DAYS = 42
ORDERED_STEPS = (
    "baseline_frozen",
    "cohort_eligible",
    "home_focus_served",
    "lesson_opened",
    "server_graded_first_attempt",
    "lesson_completed",
    "review_served",
    "later_unassisted_opportunity",
    "verdict_served",
)


def _utc(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def release_status(
    *,
    completion_target: int,
    completed_users: int,
    first_enrollment_at: Optional[datetime],
    now: datetime,
    review_days: int = REVIEW_DAYS,
) -> Dict[str, Any]:
    """Apply the frozen absolute target without curve-grading it later."""
    if completion_target <= 0:
        raise ValueError("completion_target must be positive")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    due = (
        first_enrollment_at + timedelta(days=review_days)
        if first_enrollment_at
        else None
    )
    if completed_users >= completion_target:
        status = "complete"
    elif due is not None and now >= due:
        status = "pilot_incomplete"
    else:
        status = "in_progress"
    return {
        "status": status,
        "completion_target": completion_target,
        "completed_users": completed_users,
        "target_lowered": False,
        "first_enrollment_at": (
            first_enrollment_at.isoformat() if first_enrollment_at else None
        ),
        "formal_review_due_at": due.isoformat() if due else None,
        "review_days": review_days,
    }


def classify_journey_gap(
    projection: Dict[str, Any],
    *,
    later_analyzed_games: int,
) -> str:
    steps = projection.get("steps") or {}
    if not steps.get("home_focus_served"):
        return "reach_not_observed"
    if not steps.get("lesson_opened"):
        return "product_path_home_to_lesson"
    if not steps.get("server_graded_first_attempt"):
        return "product_path_missing_server_grade"
    if not steps.get("lesson_completed"):
        return "product_path_lesson_not_completed"
    if not steps.get("review_served"):
        return "product_path_review_not_served"
    if not steps.get("later_unassisted_opportunity"):
        return (
            "user_inactivity_no_later_game"
            if later_analyzed_games <= 0
            else "evidence_gap_no_comparable_opportunity"
        )
    if not steps.get("verdict_served"):
        return "product_path_verdict_not_served"
    if not projection.get("complete"):
        return "contract_inconsistency"
    return "complete"


async def build_release_report(
    db,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    target = await db[TARGET_COLLECTION].find_one(
        {"_id": TARGET_LOCK_ID, "status": "locked"},
        {"_id": 0},
    )
    if not target:
        raise ValueError("Phase 8 target is not locked")
    completion_target = int(target.get("completion_target") or 0)
    review_days = int(target.get("review_after_days") or REVIEW_DAYS)
    users = await db.users.find(
        {
            f"feature_flags.{USER_FEATURE_FLAG}.cohort": COHORT,
        },
        {
            "_id": 0,
            "user_id": 1,
            "role": 1,
            f"feature_flags.{USER_FEATURE_FLAG}": 1,
        },
    ).to_list(length=None)
    users = [
        user
        for user in users
        if str(user.get("role") or "user").strip().lower()
        not in {"admin", "super_admin"}
    ]

    enrollment_times = []
    projections = []
    gap_counts = Counter()
    transfer_counts = Counter()
    step_counts = Counter()
    for user in users:
        user_id = str(user.get("user_id") or "")
        enrollment = ((user.get("feature_flags") or {}).get(
            USER_FEATURE_FLAG
        ) or {})
        enrolled_at = _utc(enrollment.get("phase8_enrolled_at"))
        if enrolled_at:
            enrollment_times.append(enrolled_at)
        projection = await build_phase8_journey_projection(db, user_id)
        projections.append(projection)
        for step in ORDERED_STEPS:
            if (projection.get("steps") or {}).get(step) is True:
                step_counts[step] += 1
        verdict = (projection.get("transfer") or {}).get("verdict")
        if verdict:
            transfer_counts[str(verdict)] += 1
        later_games = 0
        if enrolled_at:
            later_games = await db.games.count_documents({
                "user_id": user_id,
                "is_analyzed": True,
                "date_played": {"$gt": enrolled_at},
            })
        gap_counts[classify_journey_gap(
            projection,
            later_analyzed_games=later_games,
        )] += 1

    completed = sum(1 for item in projections if item.get("complete") is True)
    first_enrollment = min(enrollment_times) if enrollment_times else None
    status = release_status(
        completion_target=completion_target,
        completed_users=completed,
        first_enrollment_at=first_enrollment,
        now=now,
        review_days=review_days,
    )
    return {
        "schema_version": REPORT_VERSION,
        "generated_at": now.isoformat(),
        "cohort": COHORT,
        "target_lock": {
            "contract_version": target.get("contract_version"),
            "eligible_denominator": target.get("eligible_denominator"),
            "completion_target": completion_target,
            "target_lowered": False,
        },
        "enrolled_non_admin_users": len(users),
        "journey": {
            "completed_users": completed,
            "step_counts": {
                step: int(step_counts[step])
                for step in ORDERED_STEPS
            },
            "gap_counts": dict(sorted(gap_counts.items())),
        },
        "transfer_verdicts": dict(sorted(transfer_counts.items())),
        "review": status,
        "contains_identifiers": False,
        "writes_performed": 0,
    }


async def _main(args) -> int:
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    try:
        report = await build_release_report(client[db_name])
    finally:
        client.close()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report_json:
        Path(args.report_json).write_text(rendered + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-json",
        help="Optional local aggregate report path; contains no identities.",
    )
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
