"""Migrate eligible legacy piece-safety focuses to the exact Plan detector.

Safe by default: without ``--apply`` this script only reports what it would
change. It never promotes a user without at least the already-locked recurrence
floor of three exact fires and the existing ten-analyzed-game focus floor.

Run after the v18 move-observation backfill:

    python scripts/migrate_destination_safety_focus.py --email user@example.com
    python scripts/migrate_destination_safety_focus.py --email user@example.com \\
        --apply --confirm phase8-focus-bundles

To refresh only users who already have an exact destination-safety focus,
without creating or converting any additional focus, use one coordinated
per-user observation + focus migration:

    python scripts/migrate_destination_safety_focus.py --all \
        --existing-exact-only
    python scripts/migrate_destination_safety_focus.py --all \
        --existing-exact-only --apply \
        --confirm destination-safety-focus-v2 \
        --confirm-plan <fingerprint-from-dry-run>
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import uuid

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.detector_quality import QualitySurface, is_authorized
from services.focus_bridge import get_destination_safety_evidence_summary
from services.focus_bridge import destination_safety_focus_fact_version
from services.primary_weakness_picker import (
    INSTRUCTION_TEMPLATE_VERSION,
    MIN_ANALYZED_GAMES,
    MIN_EVIDENCE,
)
from scripts.backfill_move_observations import backfill_one_game, ensure_indexes


FOCUS_KIND = "piece_safety/destination_safety_exact"
INSTRUCTION = "After choosing your move, ask: can they take the piece I just moved?"
REVIEW_AFTER_MEASURED_GAMES = 3
CALENDAR_BACKSTOP_DAYS = 21
EXISTING_EXACT_REFRESH_CONFIRM = "destination-safety-focus-v2"
TRANSITION_STALE_AFTER = timedelta(hours=2)


def _is_existing_exact_focus(focus: Optional[Dict[str, Any]]) -> bool:
    return bool(
        focus
        and (
            focus.get("focus_kind") == FOCUS_KIND
            or focus.get("detector_quality_id") == QUALITY_ID
        )
    )


def _candidate_in_requested_scope(
    candidate: Dict[str, Any], *, existing_exact_only: bool
) -> bool:
    return bool(
        not existing_exact_only
        or candidate.get("existing_exact_focus") is True
    )


def _transition_plan_fingerprint(entries) -> str:
    """Bind apply to a deterministic, identity-free per-user dry-run plan."""
    stable = [
        {
            key: entry.get(key)
            for key in (
                "user_fingerprint",
                "focus_fingerprint",
                "from_version",
                "analyzed_games",
                "games_inspected",
                "observations_inspected",
                "writes_required",
                "exact_fires",
                "eligible_decisions",
                "errors",
                "eligible",
            )
        }
        for entry in entries
    ]
    payload = json.dumps(
        sorted(stable, key=lambda item: item["user_fingerprint"]),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _active_weakness_focuses(db, user_id: str):
    return await db.user_active_focus.find({
        "user_id": user_id,
        "status": "active",
        "type": {"$ne": "strength"},
    }).to_list(length=2)


async def _derive_user_observation_plan(db, user_id: str, *, apply: bool):
    """Reuse the canonical observation writer for one user's stored games."""
    report = {
        "games_inspected": 0,
        "observations_inspected": 0,
        "writes_required": 0,
        "exact_fires": 0,
        "eligible_decisions": 0,
        "misses": 0,
        "handled": 0,
        "errors": 0,
    }
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {
            "game_id": 1,
            "user_id": 1,
            "stockfish_analysis": 1,
            "decryption_v5_data": 1,
        },
    ).sort("analyzed_at", -1)
    async for analysis in cursor:
        game = await db.games.find_one(
            {"game_id": analysis.get("game_id"), "user_id": user_id},
            {"game_id": 1, "user_id": 1, "user_color": 1, "pgn": 1},
        )
        if not game:
            report["errors"] += 1
            continue
        try:
            outcome = await backfill_one_game(db, game, analysis, apply)
        except Exception:
            report["errors"] += 1
            continue
        report["games_inspected"] += 1
        report["observations_inspected"] += int(outcome.get("derived") or 0)
        report["writes_required"] += int(outcome.get("writes") or 0)
        report["exact_fires"] += int(outcome.get("fires") or 0)
        report["eligible_decisions"] += int(
            outcome.get("eligible_decisions") or 0
        )
        report["misses"] += int(outcome.get("misses") or 0)
        report["handled"] += int(outcome.get("handled") or 0)
    return report


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
    if _is_existing_exact_focus(focus) and _valid_existing_exact_bundle(focus):
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
            "id": "destination_safety_exact_focus.v2",
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
        and not focus.get("detector_version_transition")
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
    # A user's active rows hold BOTH their weakness and their strength
    # ("Low blunder rate", type="strength"). Counting a strength as a
    # competing focus made this bail with multiple_active_focuses for 38 of
    # 52 users -- every one of which has exactly one weakness and one
    # strength. Only weakness rows can conflict with a weakness focus.
    active_focuses = await db.user_active_focus.find({
        "user_id": user_id,
        "status": "active",
        "type": {"$ne": "strength"},
    }).to_list(length=2)
    if len(active_focuses) > 1:
        return {
            "eligible": False,
            "reason": "multiple_active_focuses",
            "user_id": user_id,
            "valid_bundle": False,
        }
    focus = active_focuses[0] if active_focuses else None
    if _is_existing_exact_focus(focus):
        qualifying = await _still_has_qualifying_evidence(db, user_id)
        valid = bool(qualifying and _valid_existing_exact_bundle(focus))
        if valid or not qualifying:
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
                "existing_exact_focus": True,
            }
        candidate = await _eligible_update(db, focus)
        candidate["action"] = "update"
        candidate["valid_bundle"] = bool(candidate.get("eligible"))
        candidate["existing_exact_focus"] = True
        return candidate
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


async def _run_existing_exact_refresh(
    db,
    users,
    *,
    apply: bool,
    confirm_plan: Optional[str],
) -> Dict[str, Any]:
    """Preflight all users, then migrate one locked exact focus at a time."""
    entries = []
    reasons = Counter()
    already_current = 0
    for user in users:
        user_id = str(user.get("user_id") or "")
        focuses = await _active_weakness_focuses(db, user_id)
        if len(focuses) != 1:
            reasons[
                "multiple_active_focuses" if len(focuses) > 1 else "no_active_focus"
            ] += 1
            continue
        focus = focuses[0]
        if not _is_existing_exact_focus(focus):
            reasons["outside_existing_exact_focus_scope"] += 1
            continue
        if _valid_existing_exact_bundle(focus):
            reasons["already_migrated"] += 1
            already_current += 1
            continue

        observation_plan = await _derive_user_observation_plan(
            db, user_id, apply=False
        )
        analyzed_games = await db.games.count_documents(
            {"user_id": user_id, "is_analyzed": True}
        )
        eligible = bool(
            analyzed_games >= MIN_ANALYZED_GAMES
            and observation_plan["exact_fires"] >= MIN_EVIDENCE
            and observation_plan["eligible_decisions"] > 0
            and observation_plan["errors"] == 0
        )
        reasons[
            "qualifying_exact_evidence"
            if eligible
            else "insufficient_or_invalid_v2_evidence"
        ] += 1
        entries.append({
            "_user_id": user_id,
            "_focus": focus,
            "user_fingerprint": hashlib.sha256(
                user_id.encode("utf-8")
            ).hexdigest(),
            "focus_fingerprint": hashlib.sha256(
                str(focus.get("_id") or "").encode("utf-8")
            ).hexdigest(),
            "from_version": destination_safety_focus_fact_version(focus),
            "analyzed_games": analyzed_games,
            **observation_plan,
            "eligible": eligible,
        })

    plan_fingerprint = _transition_plan_fingerprint(entries)
    report = {
        "mode": "apply" if apply else "dry_run",
        "existing_exact_only": True,
        "users_scanned": len(users),
        "existing_exact_focuses": already_current + len(entries),
        "already_current": already_current,
        "eligible": sum(int(entry["eligible"]) for entry in entries),
        "ineligible": sum(int(not entry["eligible"]) for entry in entries),
        "valid_bundles_after_run": already_current + sum(
            int(entry["eligible"]) for entry in entries
        ),
        "observations_inspected": sum(
            entry["observations_inspected"] for entry in entries
        ),
        "writes_required": sum(entry["writes_required"] for entry in entries),
        "errors": sum(entry["errors"] for entry in entries),
        "created": 0,
        "updated": 0,
        "skipped": len(users) - len(entries),
        "reasons": dict(sorted(reasons.items())),
        "plan_fingerprint": plan_fingerprint,
    }
    if not apply:
        return report
    if confirm_plan != plan_fingerprint:
        raise ValueError(
            "--apply plan changed; rerun dry-run and pass its "
            "--confirm-plan fingerprint"
        )
    if report["ineligible"] or report["errors"]:
        raise RuntimeError(
            "existing-focus v2 migration aborted before writes: "
            f"ineligible={report['ineligible']} errors={report['errors']}"
        )

    await ensure_indexes(db)
    comparable_keys = (
        "games_inspected",
        "observations_inspected",
        "writes_required",
        "exact_fires",
        "eligible_decisions",
        "misses",
        "handled",
        "errors",
    )
    for entry in entries:
        focus = entry["_focus"]
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        transition = {
            "id": "destination_safety_exact.v1_to_v2",
            "status": "rewriting_observations",
            "from_version": entry["from_version"],
            "to_version": FACT_VERSION,
            "plan_fingerprint": plan_fingerprint,
            "run_id": run_id,
            "started_at": started_at,
        }
        claim = await db.user_active_focus.update_one(
            {
                "_id": focus["_id"],
                "status": "active",
                "$or": [
                    {"detector_version_transition": {"$exists": False}},
                    {
                        "detector_version_transition.status": "failed",
                        "detector_version_transition.to_version": FACT_VERSION,
                    },
                    {
                        "detector_version_transition.status": "rewriting_observations",
                        "detector_version_transition.to_version": FACT_VERSION,
                        "detector_version_transition.started_at": {
                            "$lt": started_at - TRANSITION_STALE_AFTER,
                        },
                    },
                ],
            },
            {"$set": {"detector_version_transition": transition}},
        )
        if int(claim.modified_count or 0) != 1:
            raise RuntimeError(
                "could not claim one existing exact focus for v2 migration"
            )

        stage = "rewrite_observations"
        try:
            applied = await _derive_user_observation_plan(
                db, entry["_user_id"], apply=True
            )
            stage = "verify_observation_plan"
            changed = [
                key for key in comparable_keys
                if int(applied.get(key) or 0) != int(entry.get(key) or 0)
            ]
            if changed:
                raise RuntimeError(
                    "per-user observation plan changed after lock: "
                    + ",".join(changed)
                )
            stage = "rebuild_focus"
            candidate = await _eligible_update(db, focus)
            if not candidate.get("eligible"):
                raise RuntimeError(
                    "v2 observations were written but the exact focus could "
                    "not be rebuilt"
                )
            stage = "repin_focus"
            updated = await db.user_active_focus.update_one(
                {
                    "_id": focus["_id"],
                    "status": "active",
                    "detector_version_transition.run_id": run_id,
                },
                {
                    "$set": candidate["update"],
                    "$unset": {"detector_version_transition": ""},
                },
            )
            if int(updated.modified_count or 0) != 1:
                raise RuntimeError("v2 focus repin lost its transition claim")
        except Exception:
            await db.user_active_focus.update_one(
                {
                    "_id": focus["_id"],
                    "detector_version_transition.run_id": run_id,
                },
                {
                    "$set": {
                        "detector_version_transition.status": "failed",
                        "detector_version_transition.failed_at": datetime.now(
                            timezone.utc
                        ),
                        "detector_version_transition.failure_stage": stage,
                    },
                },
            )
            raise
        report["updated"] += 1
    return report


async def run(
    *,
    apply: bool,
    email: Optional[str],
    all_users: bool,
    confirm: Optional[str] = None,
    existing_exact_only: bool = False,
    confirm_plan: Optional[str] = None,
) -> Dict[str, Any]:
    required_confirm = (
        EXISTING_EXACT_REFRESH_CONFIRM
        if existing_exact_only
        else "phase8-focus-bundles"
    )
    if apply and confirm != required_confirm:
        raise ValueError(f"--apply requires --confirm {required_confirm}")
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
        if existing_exact_only:
            return await _run_existing_exact_refresh(
                db,
                users,
                apply=apply,
                confirm_plan=confirm_plan,
            )
        report = {
            "mode": "apply" if apply else "dry_run",
            "users_scanned": len(users),
            "non_admin_only": bool(all_users),
            "full_cohort": bool(all_users and not email),
            "existing_exact_only": existing_exact_only,
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
            if not _candidate_in_requested_scope(
                candidate,
                existing_exact_only=existing_exact_only,
            ):
                candidate = {
                    "eligible": False,
                    "reason": "outside_existing_exact_focus_scope",
                    "valid_bundle": False,
                }
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
        help=(
            "Required with --apply: phase8-focus-bundles normally, or "
            f"{EXISTING_EXACT_REFRESH_CONFIRM} with --existing-exact-only"
        ),
    )
    parser.add_argument(
        "--existing-exact-only",
        action="store_true",
        help=(
            "refresh only existing exact destination-safety focuses; "
            "never creates or converts another focus"
        ),
    )
    parser.add_argument(
        "--confirm-plan",
        default=None,
        help=(
            "with --existing-exact-only --apply, the exact fingerprint from "
            "the immediately preceding dry-run"
        ),
    )
    args = parser.parse_args()
    report = asyncio.run(
        run(
            apply=args.apply,
            email=args.email,
            all_users=args.all_users,
            confirm=args.confirm,
            existing_exact_only=args.existing_exact_only,
            confirm_plan=args.confirm_plan,
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
        and report.get("created", 0) + report.get("updated", 0)
        != report.get("eligible", 0)
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
