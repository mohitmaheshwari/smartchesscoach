"""Migrate eligible legacy piece-safety focuses to the exact Plan detector.

Safe by default: without ``--apply`` this script only reports what it would
change. It never promotes a user without at least the already-locked recurrence
floor of three exact fires and the existing ten-analyzed-game focus floor.

Run after the v18 move-observation backfill:

    python scripts/migrate_destination_safety_focus.py --email user@example.com
    python scripts/migrate_destination_safety_focus.py --email user@example.com \\
        --apply --confirm phase8-focus-bundles
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
from typing import Any, Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.detector_quality import QualitySurface, is_authorized
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
            "reason": "insufficient_exact_evidence",
            "user_id": user_id,
            "analyzed_games": analyzed_games,
            "exact_fires": exact_fires,
            "exact_decisions": evidence["decisions"],
        }

    now = datetime.now(timezone.utc)
    baseline_rate = round(evidence["misses"] / max(analyzed_games, 1), 3)
    document_id = focus.get("_id") or ObjectId()
    instruction_id = str(focus.get("instruction_id") or document_id)
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
        "reason": "qualifying_exact_evidence",
        "user_id": user_id,
        "analyzed_games": analyzed_games,
        "exact_fires": exact_fires,
        "exact_decisions": evidence["decisions"],
        "document_id": document_id,
        "update": update,
    }


def _is_non_admin(user: Dict[str, Any]) -> bool:
    return str(user.get("role") or "user").strip().lower() not in {
        "admin",
        "super_admin",
    }


def _valid_existing_exact_bundle(focus: Dict[str, Any]) -> bool:
    return bool(
        focus.get("status") == "active"
        and focus.get("focus_kind") == FOCUS_KIND
        and focus.get("detector_quality_id") == QUALITY_ID
        and str(focus.get("detector_quality_grade") or "").lower() == "plan"
        and focus.get("proof_detector_id") == FACT_VERSION
        and str(focus.get("instruction_id") or "").strip()
        and str(focus.get("instruction_text") or "").strip()
        and str(focus.get("instruction_version") or "").strip()
        and is_authorized(QUALITY_ID, QualitySurface.PLAN)
    )


async def _still_has_qualifying_evidence(db, user_id: str) -> bool:
    analyzed_games = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    exact_fires = await db.move_observations.count_documents({
        "user_id": user_id,
        "schema_version": {"$gte": 18},
        "destination_safety_exact.version": FACT_VERSION,
        "destination_safety_exact.fires": True,
    })
    evidence = await get_destination_safety_evidence_summary(db, user_id)
    return bool(
        analyzed_games >= MIN_ANALYZED_GAMES
        and exact_fires >= MIN_EVIDENCE
        and evidence["decisions"] > 0
    )


async def _candidate_for_user(db, user: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(user.get("user_id") or "")
    if not user_id:
        return {"eligible": False, "reason": "invalid_user", "user_id": ""}
    if not _is_non_admin(user):
        return {
            "eligible": False,
            "reason": "excluded_admin_role",
            "user_id": user_id,
            "valid_bundle": False,
        }
    active_focuses = await db.user_active_focus.find({
        "user_id": user_id,
        "status": "active",
    }).to_list(length=2)
    if len(active_focuses) > 1:
        return {
            "eligible": False,
            "reason": "multiple_active_focuses",
            "user_id": user_id,
            "valid_bundle": False,
        }
    focus = active_focuses[0] if active_focuses else None
    if focus and (
        focus.get("focus_kind") == FOCUS_KIND
        or focus.get("detector_quality_id") == QUALITY_ID
    ):
        qualifying = await _still_has_qualifying_evidence(db, user_id)
        valid = bool(qualifying and _valid_existing_exact_bundle(focus))
        return {
            "eligible": False,
            "reason": (
                "already_migrated"
                if valid
                else "invalid_existing_exact_focus"
            ),
            "user_id": user_id,
            "qualifying_evidence": qualifying,
            "valid_bundle": valid,
        }
    if focus and focus.get("topic_key") != "piece_safety":
        return {
            "eligible": False,
            "reason": "active_focus_conflict",
            "user_id": user_id,
            "valid_bundle": False,
        }

    source = focus or {
        "_id": ObjectId(),
        "user_id": user_id,
        "topic_key": "piece_safety",
        "type": "weakness",
        "status": "active",
    }
    candidate = await _eligible_update(db, source)
    candidate["action"] = "update" if focus else "insert"
    candidate["valid_bundle"] = bool(candidate.get("eligible"))
    if candidate.get("eligible") and not focus:
        candidate["insert"] = {
            "_id": candidate["document_id"],
            "user_id": user_id,
            "type": "weakness",
            "status": "active",
            "moments_page_topic": "piece_safety",
            "picker_score": candidate["exact_fires"],
            "picker_evidence_count": candidate["exact_fires"],
            **candidate["update"],
        }
    return candidate


async def run(
    *,
    apply: bool,
    email: Optional[str],
    all_users: bool,
    confirm: Optional[str] = None,
) -> Dict[str, Any]:
    if apply and confirm != "phase8-focus-bundles":
        raise ValueError("--apply requires --confirm phase8-focus-bundles")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        if not email and not all_users:
            raise ValueError("choose --email for one account or --all for the cohort")
        user_id = await _resolve_user_id(db, email)
        if email and not user_id:
            raise ValueError("email did not resolve to a user")
        if user_id:
            users = await db.users.find(
                {"user_id": user_id},
                {"_id": 0, "user_id": 1, "role": 1},
            ).to_list(length=1)
        else:
            users = await db.users.find(
                {},
                {"_id": 0, "user_id": 1, "role": 1},
            ).to_list(length=None)
            users = [user for user in users if _is_non_admin(user)]
        report = {
            "mode": "apply" if apply else "dry_run",
            "users_scanned": len(users),
            "non_admin_only": bool(all_users),
            "full_cohort": bool(all_users and not email),
            "eligible": 0,
            "qualifying_evidence": 0,
            "valid_bundles_after_run": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "reasons": {},
        }
        reasons = Counter()
        for user in users:
            candidate = await _candidate_for_user(db, user)
            reasons[candidate.get("reason") or "unknown"] += 1
            report["valid_bundles_after_run"] += int(
                candidate.get("valid_bundle") is True
            )
            if (
                candidate.get("reason") == "qualifying_exact_evidence"
                or candidate.get("qualifying_evidence") is True
            ):
                report["qualifying_evidence"] += 1
            if not candidate["eligible"]:
                report["skipped"] += 1
                continue
            report["eligible"] += 1
            if apply:
                if candidate["action"] == "insert":
                    await db.user_active_focus.insert_one(candidate["insert"])
                    report["created"] += 1
                else:
                    result = await db.user_active_focus.update_one(
                        {"_id": candidate["document_id"], "status": "active"},
                        {"$set": candidate["update"]},
                    )
                    report["updated"] += int(result.modified_count)
        report["reasons"] = dict(sorted(reasons.items()))
        return report
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email")
    target.add_argument("--all", action="store_true", dest="all_users")
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional path for the aggregate JSON report.",
    )
    parser.add_argument(
        "--confirm",
        default=None,
        help="Required with --apply: phase8-focus-bundles",
    )
    args = parser.parse_args()
    report = asyncio.run(
        run(
            apply=args.apply,
            email=args.email,
            all_users=args.all_users,
            confirm=args.confirm,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    if (
        args.apply
        and report["created"] + report["updated"] != report["eligible"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
