"""Cleanup script: strip artifact mastered_at stamps from the 2026-06-04 backfill.

Per docs/artifact_mastery_cleanup_scope.md. The 2026-06-04 one-shot
backfill stamped mastered_at against the streak math at backfill time —
permissive for users with long game histories. Result: 749 of 763
mastered_at stamps came from the same backfill window, many on concepts
the user hadn't genuinely mastered.

This script audits every user_concept_understanding row with mastered_at
set and strips the stamp when the row fails a stricter rule. Live game
events from this point forward will re-master legitimate concepts
organically.

Usage:

    # Dry-run (DEFAULT — no writes):
    python backend/scripts/cleanup_artifact_mastery.py

    # Dry-run with custom thresholds (preview before locking):
    python backend/scripts/cleanup_artifact_mastery.py \\
        --clean-min 5 --violation-max 3 --clean-high-floor 20

    # Apply for real (requires --apply AND --confirm-thresholds flags):
    python backend/scripts/cleanup_artifact_mastery.py --apply --confirm-thresholds

The script ALWAYS writes a pre-cleanup snapshot to
backend/snapshots/user_concept_understanding_pre_cleanup_YYYY-MM-DD.json
before any --apply writes. Restore via:
    python backend/scripts/restore_concept_mastery_snapshot.py <snapshot.json>

Defaults are gut numbers (NOT data-locked). Run dry-run first, look at
the histogram, set the real numbers via flags, then --apply.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from motor.motor_asyncio import AsyncIOMotorClient


# ─── Threshold defaults (gut numbers — replace via flags after dry-run) ──

DEFAULT_CLEAN_MIN = 5         # Min clean games to claim mastery
DEFAULT_VIOLATION_MAX = 3      # Above this, need a higher clean floor
DEFAULT_CLEAN_HIGH_FLOOR = 20  # Clean games needed when violations exceed max

# 2026-06-06 — the dry-run histogram revealed the high-clean bucket
# (clean=165-169, 41 rows) is entirely DEAD-NAMESPACE concepts
# (piece_without_purpose, knight_fork, blocked_bishop, etc.) — the
# deprecated lowercase v5-plan IDs the central pipeline no longer
# emits. These are ALREADY filtered from the PWC gate + InGameMastery
# panel (commit 42f4b0be), so their mastered_at is functionally inert.
# Live-namespace concepts (these prefixes) are the ones that reach the
# gate and cause real over-suppression — the clean/violation rule
# applies to THEM. Dead-namespace mastered_at gets stripped as pure
# stale-data cleanup (no downside; they're already ignored downstream).
LIVE_PREFIXES = ("TAC_", "OP_", "MID_", "END_", "DEF_", "STR_")


def _is_live_namespace(concept_id: str) -> bool:
    return bool(concept_id) and any(concept_id.startswith(p) for p in LIVE_PREFIXES)


def should_keep_mastery(row: dict, args) -> tuple[bool, str]:
    """Per-row keep/strip decision.

    Dead-namespace concepts: always strip (stale, already filtered from
    gate/UI — see 42f4b0be). Live-namespace: apply the clean/violation
    rule (Rule R1, scope §3) — these are the rows that affect the gate.

    Returns:
        (keep: bool, reason: str) — reason is the rule branch that decided.
    """
    concept_id = row.get("concept_id") or ""
    if not _is_live_namespace(concept_id):
        return (False, "dead_namespace_stale (already filtered from gate/UI)")

    clean = int(row.get("clean_games_total") or 0)
    violations = int(row.get("violations_total") or 0)

    if clean < args.clean_min:
        return (False, f"clean_games_total={clean} < min={args.clean_min}")

    if violations <= args.violation_max:
        return (True, f"clean={clean} OK, violations={violations} <= max={args.violation_max}")

    if clean >= args.clean_high_floor:
        return (True, f"clean={clean} >= high_floor={args.clean_high_floor} overrides violations={violations}")

    return (
        False,
        f"violations={violations} > max={args.violation_max} AND clean={clean} < high_floor={args.clean_high_floor}",
    )


async def write_snapshot(db, snapshot_path: Path, user_id_filter=None) -> int:
    """Pre-cleanup snapshot for rollback. JSON dump of every row that
    currently has mastered_at set."""
    query = {"mastered_at": {"$ne": None}}
    if user_id_filter:
        query["user_id"] = user_id_filter
    rows = await db.user_concept_understanding.find(
        query, {"_id": 0},
    ).to_list(20000)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "rows": rows,
        }, f, indent=2, default=str)
    return len(rows)


async def run(args):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"=== Artifact-Mastery Cleanup ===")
    print(f"  thresholds: clean_min={args.clean_min}, violation_max={args.violation_max}, clean_high_floor={args.clean_high_floor}")
    print(f"  mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  scope: {'user=' + args.user_id if args.user_id else 'ALL USERS'}")
    print()

    query = {"mastered_at": {"$ne": None}}
    if args.user_id:
        query["user_id"] = args.user_id

    cursor = db.user_concept_understanding.find(
        query,
        {"_id": 1, "user_id": 1, "concept_id": 1, "clean_games_total": 1,
         "violations_total": 1, "mastered_at": 1, "last_violation_at": 1,
         "streak_clean": 1},
    )

    histogram = defaultdict(int)
    strips = []  # rows that would be stripped
    keeps = 0
    per_user_before = defaultdict(int)
    per_user_strip = defaultdict(int)
    # Namespace split (2026-06-06): isolate the rows that actually
    # affect the PWC gate (live-namespace) from the inert dead-namespace
    # ones, so the threshold lock is judged against the live distribution.
    ns_counts = {
        "live_keep": 0, "live_strip": 0,
        "dead_keep": 0, "dead_strip": 0,
    }

    async for row in cursor:
        uid = row.get("user_id", "")
        per_user_before[uid] += 1
        keep, reason = should_keep_mastery(row, args)
        clean = int(row.get("clean_games_total") or 0)
        violations = int(row.get("violations_total") or 0)
        is_live = _is_live_namespace(row.get("concept_id") or "")
        ns = "live" if is_live else "dead"
        ns_counts[f"{ns}_{'keep' if keep else 'strip'}"] += 1
        # Histogram only over LIVE-namespace (the rows that matter for
        # the gate) so the keep/strip cliff isn't drowned by dead rows.
        if is_live:
            clean_bucket = f"clean={(clean // 5) * 5}-{(clean // 5) * 5 + 4}"
            violation_bucket = f"violations={(violations // 5) * 5}-{(violations // 5) * 5 + 4}"
            histogram[f"keep={keep}, {clean_bucket}, {violation_bucket}"] += 1
        if not keep:
            strips.append({
                "_id": str(row["_id"]),
                "user_id": uid,
                "concept_id": row.get("concept_id"),
                "clean_games_total": clean,
                "violations_total": violations,
                "mastered_at": row.get("mastered_at"),
                "namespace": ns,
                "reason": reason,
            })
            per_user_strip[uid] += 1
        else:
            keeps += 1

    print(f"Total rows with mastered_at: {keeps + len(strips)}")
    print(f"  Would KEEP:  {keeps}")
    print(f"  Would STRIP: {len(strips)}")
    print()
    print("Namespace split (live = reaches the PWC gate; dead = already filtered, inert):")
    print(f"  LIVE  keep={ns_counts['live_keep']:>4}  strip={ns_counts['live_strip']:>4}")
    print(f"  DEAD  keep={ns_counts['dead_keep']:>4}  strip={ns_counts['dead_strip']:>4}  (dead always strips)")
    print("  >>> Lock thresholds against the LIVE numbers — dead is pure cleanup.")
    print()
    print("LIVE-namespace histogram (the keep/strip cliff that matters, top 20):")
    for bucket, count in sorted(histogram.items(), key=lambda x: -x[1])[:20]:
        print(f"  {count:5}  {bucket}")
    print()

    print("Per-user impact (top 20 by strip count):")
    for uid in sorted(per_user_strip, key=lambda u: -per_user_strip[u])[:20]:
        before = per_user_before[uid]
        strip = per_user_strip[uid]
        after = before - strip
        print(f"  {uid[-12:]} : before={before:3} → after={after:3} (strip {strip})")
    print()

    if args.apply:
        if not args.confirm_thresholds:
            print("REFUSING TO APPLY: --confirm-thresholds flag required for safety.")
            print("Add --confirm-thresholds after reviewing the dry-run histogram.")
            return

        # Snapshot first
        snapshot_path = (
            REPO_ROOT / "backend" / "snapshots"
            / f"user_concept_understanding_pre_cleanup_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.json"
        )
        print(f"Writing pre-cleanup snapshot to {snapshot_path}...")
        snap_count = await write_snapshot(db, snapshot_path, user_id_filter=args.user_id)
        print(f"  Snapshot: {snap_count} rows")
        print()

        # Apply strips
        now_iso = datetime.now(timezone.utc).isoformat()
        applied = 0
        for s in strips:
            try:
                # Need ObjectId; reconstruct from str
                from bson import ObjectId
                await db.user_concept_understanding.update_one(
                    {"_id": ObjectId(s["_id"])},
                    {"$set": {
                        "mastered_at": None,
                        "acknowledged": False,
                        "mastery_stripped_at": now_iso,
                        "mastery_stripped_reason": "artifact_backfill_cleanup",
                        "mastery_stripped_thresholds": {
                            "clean_min": args.clean_min,
                            "violation_max": args.violation_max,
                            "clean_high_floor": args.clean_high_floor,
                        },
                    }},
                )
                applied += 1
            except Exception as e:
                print(f"  STRIP FAILED for {s['_id']}: {e}")

        print(f"Applied {applied}/{len(strips)} strips.")

        # Audit log
        audit_path = (
            REPO_ROOT / "backend" / "logs"
            / f"artifact_mastery_cleanup_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.json"
        )
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump({
                "ran_at": now_iso,
                "thresholds": {
                    "clean_min": args.clean_min,
                    "violation_max": args.violation_max,
                    "clean_high_floor": args.clean_high_floor,
                },
                "snapshot_path": str(snapshot_path),
                "rows_kept": keeps,
                "rows_stripped": applied,
                "per_user_impact": dict(per_user_strip),
                "strips": strips,
            }, f, indent=2, default=str)
        print(f"Audit log: {audit_path}")
    else:
        print("DRY-RUN complete. To apply:")
        print(f"  python {Path(__file__).name} --apply --confirm-thresholds \\")
        print(f"      --clean-min {args.clean_min} --violation-max {args.violation_max} \\")
        print(f"      --clean-high-floor {args.clean_high_floor}")

    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually apply strips (default is dry-run)")
    parser.add_argument("--confirm-thresholds", action="store_true",
                        help="Required with --apply to confirm thresholds reviewed")
    parser.add_argument("--user-id", type=str, default=None,
                        help="Limit to a single user_id for testing")
    parser.add_argument("--clean-min", type=int, default=DEFAULT_CLEAN_MIN,
                        help=f"Minimum clean_games_total to claim mastery (default {DEFAULT_CLEAN_MIN})")
    parser.add_argument("--violation-max", type=int, default=DEFAULT_VIOLATION_MAX,
                        help=f"Above this, need clean_high_floor (default {DEFAULT_VIOLATION_MAX})")
    parser.add_argument("--clean-high-floor", type=int, default=DEFAULT_CLEAN_HIGH_FLOOR,
                        help=f"Clean floor when violations exceed max (default {DEFAULT_CLEAN_HIGH_FLOOR})")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
