"""Freeze the Phase 8 eligible denominator and absolute completion target.

The command consumes the *post-apply idempotency* reports from the stored
observation and focus-bundle jobs. It is read-only by default. Apply is an
immutable insert and requires the exact confirmation phrase.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.complete_coaching_access import TARGET_COLLECTION, TARGET_LOCK_ID
from services.destination_safety_detector import FACT_VERSION, QUALITY_ID
from services.move_observation_deriver import SCHEMA_VERSION


CONFIRMATION = "phase8-target-lock"
CONTRACT_VERSION = "phase8_reach_target.v1"
REVIEW_AFTER_DAYS = 42


def _load_report(path: str) -> tuple[Dict[str, Any], str]:
    raw = Path(path).read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload, hashlib.sha256(raw).hexdigest()


def build_target_lock(
    coverage: Dict[str, Any],
    focus: Dict[str, Any],
    *,
    coverage_sha256: str,
    focus_sha256: str,
    completion_target: int,
    created_at: datetime,
    source_commit: str,
) -> Dict[str, Any]:
    if coverage.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("coverage report is not from the current observation schema")
    if coverage.get("fact_version") != FACT_VERSION:
        raise ValueError("coverage report is not from the current exact detector")
    if coverage.get("quality_id") != QUALITY_ID:
        raise ValueError("coverage report carries the wrong quality id")
    if coverage.get("mode") != "dry_run":
        raise ValueError("target lock requires the post-apply dry-run report")
    if coverage.get("full_corpus") is not True:
        raise ValueError("target lock requires a full-corpus coverage report")
    if int(coverage.get("errors") or 0) != 0:
        raise ValueError("coverage report contains errors")
    if int(coverage.get("writes_required") or 0) != 0:
        raise ValueError("stored-observation reconciliation is not idempotent")
    inspected = int(coverage.get("observations_inspected") or 0)
    if inspected <= 0:
        raise ValueError("coverage report inspected no observations")
    storage = coverage.get("storage") or {}
    decisions = coverage.get("decisions") or {}
    unresolved = int(storage.get("missing") or 0) + int(
        storage.get("stale_version") or 0
    )
    invalid = int(decisions.get("invalid") or 0)
    if unresolved > invalid:
        raise ValueError("valid observations remain missing or stale")

    if focus.get("mode") != "dry_run":
        raise ValueError("target lock requires the post-apply focus dry-run")
    if (
        focus.get("full_cohort") is not True
        or focus.get("non_admin_only") is not True
    ):
        raise ValueError("target lock requires the full non-admin focus cohort")
    if int(focus.get("eligible") or 0) != 0:
        raise ValueError("focus reconciliation is not idempotent")
    denominator = int(focus.get("valid_bundles_after_run") or 0)
    if denominator <= 0:
        raise ValueError("focus report produced no eligible denominator")
    if not isinstance(completion_target, int) or isinstance(completion_target, bool):
        raise ValueError("completion target must be an integer")
    if completion_target <= 0 or completion_target > denominator:
        raise ValueError("completion target must be between 1 and the denominator")
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    if not source_commit:
        raise ValueError("source commit is required")

    return {
        "_id": TARGET_LOCK_ID,
        "contract_version": CONTRACT_VERSION,
        "status": "locked",
        "created_at": created_at,
        "source_commit": source_commit,
        "eligible_denominator": denominator,
        "completion_target": completion_target,
        "review_after_days": REVIEW_AFTER_DAYS,
        "review_anchor": "first_non_admin_enrollment",
        "quality_id": QUALITY_ID,
        "fact_version": FACT_VERSION,
        "observation_schema_version": SCHEMA_VERSION,
        "coverage": {
            "observations_inspected": inspected,
            "exact_fires": int(coverage.get("exact_fires") or 0),
            "users_covered": int(coverage.get("users_covered") or 0),
            "invalid_observations": invalid,
            "report_sha256": coverage_sha256,
        },
        "focuses": {
            "users_scanned": int(focus.get("users_scanned") or 0),
            "qualifying_evidence": int(focus.get("qualifying_evidence") or 0),
            "valid_bundles": denominator,
            "report_sha256": focus_sha256,
        },
    }


def _same_lock(existing: Dict[str, Any], proposed: Dict[str, Any]) -> bool:
    immutable = (
        "contract_version",
        "status",
        "source_commit",
        "eligible_denominator",
        "completion_target",
        "review_after_days",
        "quality_id",
        "fact_version",
        "observation_schema_version",
        "coverage",
        "focuses",
    )
    return all(existing.get(key) == proposed.get(key) for key in immutable)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-report", required=True)
    parser.add_argument("--focus-report", required=True)
    parser.add_argument("--completion-target", required=True, type=int)
    parser.add_argument("--source-commit", default=os.environ.get("GIT_COMMIT", ""))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional path for the identifier-free target-lock artifact.",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing write: --confirm must equal {CONFIRMATION!r}")

    coverage, coverage_hash = _load_report(args.coverage_report)
    focus, focus_hash = _load_report(args.focus_report)
    proposed = build_target_lock(
        coverage,
        focus,
        coverage_sha256=coverage_hash,
        focus_sha256=focus_hash,
        completion_target=args.completion_target,
        created_at=datetime.now(timezone.utc),
        source_commit=args.source_commit,
    )
    rendered = json.dumps(proposed, indent=2, sort_keys=True, default=str)
    print(rendered)
    if args.report_json:
        Path(args.report_json).write_text(rendered + "\n", encoding="utf-8")
    if not args.apply:
        print("DRY RUN ONLY — no target lock was written.")
        return 0

    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    database_name = os.environ.get("DB_NAME")
    if not mongo_url or not database_name:
        raise SystemExit("MONGO_URL and DB_NAME must come from the environment")
    client = MongoClient(mongo_url)
    try:
        collection = client[database_name][TARGET_COLLECTION]
        existing = collection.find_one({"_id": TARGET_LOCK_ID})
        if existing:
            if not _same_lock(existing, proposed):
                raise SystemExit("A different immutable Phase 8 target is already locked")
            print("Target already locked with identical evidence; zero writes.")
            return 0
        collection.insert_one(proposed)
        print("Phase 8 target locked.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
