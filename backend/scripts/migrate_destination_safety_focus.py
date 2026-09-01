"""Migrate eligible legacy piece-safety focuses to the exact Plan detector.

Safe by default: without ``--apply`` this script only reports what it would
change. It never promotes a user without at least the already-locked recurrence
floor of three exact fires and the existing ten-analyzed-game focus floor.

Run after the v18 move-observation backfill:

    python scripts/migrate_destination_safety_focus.py --email user@example.com
    python scripts/migrate_destination_safety_focus.py --email user@example.com --apply
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.focus_bridge import get_destination_safety_evidence_summary
from services.primary_weakness_picker import (
    INSTRUCTION_TEMPLATE_VERSION,
    MIN_ANALYZED_GAMES,
    MIN_EVIDENCE,
)


FOCUS_KIND = "piece_safety/destination_safety_exact"
INSTRUCTION = "After choosing your move, ask: can they take the piece I just moved?"
REVIEW_AFTER_MEASURED_GAMES = 3
CALENDAR_BACKSTOP_DAYS = 21


async def _resolve_user_id(db, email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    user = await db.users.find_one(
        {"email": {"$regex": f"^{email}$", "$options": "i"}},
        {"_id": 0, "user_id": 1},
    )
    return str((user or {}).get("user_id") or "") or None


async def _eligible_update(db, focus: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(focus.get("user_id") or "")
    if (
        focus.get("focus_kind") == FOCUS_KIND
        or focus.get("detector_quality_id") == QUALITY_ID
    ):
        return {
            "eligible": False,
            "reason": "already_migrated",
            "user_id": user_id,
            "analyzed_games": 0,
            "exact_fires": 0,
            "exact_decisions": 0,
        }
    analyzed_games = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    exact_query = {
        "user_id": user_id,
        "schema_version": {"$gte": 18},
        "destination_safety_exact.version": FACT_VERSION,
        "destination_safety_exact.fires": True,
    }
    exact_fires = await db.move_observations.count_documents(exact_query)
    evidence = await get_destination_safety_evidence_summary(db, user_id)
    eligible = (
        analyzed_games >= MIN_ANALYZED_GAMES
        and exact_fires >= MIN_EVIDENCE
        and evidence["decisions"] > 0
    )
    if not eligible:
        return {
            "eligible": False,
            "user_id": user_id,
            "analyzed_games": analyzed_games,
            "exact_fires": exact_fires,
            "exact_decisions": evidence["decisions"],
        }

    now = datetime.now(timezone.utc)
    baseline_rate = round(evidence["misses"] / max(analyzed_games, 1), 3)
    instruction_id = str(focus.get("instruction_id") or focus.get("_id"))
    update = {
        "cycle_version": 1,
        "focus_kind": FOCUS_KIND,
        "topic_key": "piece_safety",
        "coaching_label": "Keeping your pieces safe",
        "coaching_narrative": (
            "I found the same board problem in several of your games: the "
            "piece you had just moved could be taken immediately. We will "
            "build one final safety check into your move."
        ),
        "subtype_histogram": {
            "destination_safety_exact": {
                "count": exact_fires,
                "dominant_severity": "critical",
            }
        },
        "picker_evidence_count": exact_fires,
        "detector_quality_id": QUALITY_ID,
        "detector_quality_grade": "plan",
        "proof_eligibility": "verified",
        "diagnosis_detector_id": FACT_VERSION,
        "proof_detector_id": FACT_VERSION,
        "instruction_id": instruction_id,
        "instruction_text": INSTRUCTION,
        "instruction_version": INSTRUCTION_TEMPLATE_VERSION,
        "instruction_subtype": "destination_safety_exact",
        "baseline_metric": {
            "name": "destination_safety_exact_misses_per_game",
            "value": baseline_rate,
            "occurrence_count": evidence["misses"],
            "n_games_at_baseline": analyzed_games,
        },
        "current_metric": None,
        "resolution": "measurement_pending",
        "next_action": "practice",
        "evidence_summary": {
            "baseline": evidence,
            "recent": {"decisions": 0, "misses": 0, "handled": 0},
            "last_verdict": "measurement_pending",
            "measured_at": now,
        },
        "review_after_measured_games": REVIEW_AFTER_MEASURED_GAMES,
        "calendar_backstop_days": CALENDAR_BACKSTOP_DAYS,
        "started_at": now,
        "locked_until": now + timedelta(days=CALENDAR_BACKSTOP_DAYS),
        "updated_at": now,
        "migration": {
            "id": "destination_safety_exact.v1",
            "migrated_at": now,
            "previous_quality_id": focus.get("detector_quality_id"),
            "previous_focus_kind": focus.get("focus_kind"),
        },
    }
    return {
        "eligible": True,
        "user_id": user_id,
        "analyzed_games": analyzed_games,
        "exact_fires": exact_fires,
        "exact_decisions": evidence["decisions"],
        "update": update,
    }


async def run(*, apply: bool, email: Optional[str], all_users: bool) -> Dict[str, Any]:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        if not email and not all_users:
            raise ValueError("choose --email for one account or --all for the cohort")
        user_id = await _resolve_user_id(db, email)
        if email and not user_id:
            raise ValueError("email did not resolve to a user")
        query: Dict[str, Any] = {
            "status": "active",
            "topic_key": "piece_safety",
            "$or": [{"type": "weakness"}, {"type": {"$exists": False}}],
        }
        if user_id:
            query["user_id"] = user_id
        focuses = await db.user_active_focus.find(query).to_list(length=None)
        report = {
            "mode": "apply" if apply else "dry_run",
            "focuses_scanned": len(focuses),
            "eligible": 0,
            "updated": 0,
            "skipped": 0,
            "users": [],
        }
        for focus in focuses:
            candidate = await _eligible_update(db, focus)
            public = {key: value for key, value in candidate.items() if key != "update"}
            report["users"].append(public)
            if not candidate["eligible"]:
                report["skipped"] += 1
                continue
            report["eligible"] += 1
            if apply:
                result = await db.user_active_focus.update_one(
                    {"_id": focus["_id"], "status": "active"},
                    {"$set": candidate["update"]},
                )
                report["updated"] += int(result.modified_count)
        return report
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email")
    target.add_argument("--all", action="store_true", dest="all_users")
    args = parser.parse_args()
    report = asyncio.run(
        run(apply=args.apply, email=args.email, all_users=args.all_users)
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if args.apply and report["updated"] != report["eligible"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
