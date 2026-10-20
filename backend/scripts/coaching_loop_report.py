"""Per-concept coaching-loop coverage: which stages exist, and does teaching land.

The loop is only a loop for a concept when all five stages exist:

    1 detect    a detector finds it in a real game, at a grade that may speak
    2 plan      it can become someone's current priority
    3 teach     there is content, with a question and a grader
    4 practise  there is a pool to drill it
    5 observe   we see it applied in a LATER real game, and record that

This reports those five per concept, plus the conversions between them. It is
read-only and composes existing owners -- `detector_quality` for grades and
identity, `concept_contract_registry` for content bindings, and the database
for what actually happened. It deliberately introduces no new mapping file:
a `gap:<family>:<subtype>` id already carries the family that `user_active_focus`
and `community_puzzles` key on, so the join is a split, not a table.

Three rules it obeys, each from a mistake already made on this codebase:

  * Denominators, never counts. `applied / (applied + missed)`, because a raw
    count of successes says nothing without the chances that were offered.
  * A concept with no recorded failures, or no recorded successes, is unfit to
    carry a progress claim -- it cannot move in one direction. Both are flagged.
  * What cannot be mapped is reported, not dropped. A concept missing from the
    output would read as a concept with no problem.

Usage:
    python scripts/coaching_loop_report.py                 # all concepts
    python scripts/coaching_loop_report.py --concept piece_safety
    python scripts/coaching_loop_report.py --user user_b189135388c9
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.detector_quality import _AUTHORIZATIONS  # noqa: E402

UNFIT_NO_SUCCESS = "cannot record a success"
UNFIT_NO_FAILURE = "cannot record a failure"


def _grade_name(value: Any) -> str:
    return str(getattr(value, "name", value))


def _family(quality_id: str) -> Optional[str]:
    """`gap:piece_safety:simple_hang` -> `piece_safety`.

    This is the whole identity bridge for the gap family and it is deliberately
    a split rather than a lookup: `user_active_focus.topic_key` and
    `community_puzzles.issue_type` already use exactly this token, so inventing
    a mapping table would create a second truth for a string that already
    agrees with itself.
    """
    parts = quality_id.split(":")
    if len(parts) >= 3 and parts[0] == "gap":
        return parts[1]
    return None


def static_stages() -> Dict[str, Dict[str, Any]]:
    """Stage 1 and 3 from the authorities, with no database access."""
    rows: Dict[str, Dict[str, Any]] = {}
    for quality_id, auth in _AUTHORIZATIONS.items():
        rows[quality_id] = {
            "quality_id": quality_id,
            "family": _family(quality_id),
            "grade": _grade_name(auth.grade),
            "prefix": quality_id.split(":", 1)[0],
            "limitations": tuple(getattr(auth, "limitations", ()) or ()),
            "content_id": None,
            "has_grader": False,
        }

    # Content and grader come from the contract index, which composes the
    # curriculum owners. Missing is a real answer here, not an error: the index
    # covers concept-level detectors and authored content, and the gap family
    # sits outside it.
    try:
        from services.concept_contract_registry import build_concept_contract_index

        index = build_concept_contract_index()
        for contract in index.contracts.values():
            content_id = getattr(contract.content, "content_id", None)
            for quality_id in contract.detector_quality_ids or ():
                if quality_id in rows:
                    rows[quality_id]["content_id"] = content_id
                    rows[quality_id]["has_grader"] = bool(contract.grader_ref)
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        print(f"   note: contract index unavailable ({exc}); stage 3 unknown")

    # A question + grading spec is a second, independent route to stage 3 --
    # several gap families have one without a contract-index entry.
    try:
        from services import lesson_question_spec as lqs

        source = ""
        spec_path = getattr(lqs, "__file__", "")
        if spec_path:
            with open(spec_path, encoding="utf-8") as handle:
                source = handle.read()
        for row in rows.values():
            family = row["family"]
            if family and family in source:
                row["has_grader"] = True
    except Exception as exc:  # pragma: no cover
        print(f"   note: question specs unreadable ({exc})")
    return rows


async def live_stages(db, rows: Dict[str, Dict[str, Any]], user: Optional[str]) -> None:
    """Stages 2, 4 and 5, from what actually happened."""
    user_filter = {"user_id": user} if user else {}

    # Stage 2 -- plan reach, by family.
    plan: Dict[str, set] = collections.defaultdict(set)
    plan_active: Dict[str, set] = collections.defaultdict(set)
    async for doc in db.user_active_focus.find(
        user_filter, {"_id": 0, "topic_key": 1, "user_id": 1, "status": 1}
    ):
        topic = doc.get("topic_key")
        if not topic:
            continue
        plan[topic].add(doc.get("user_id"))
        if doc.get("status") == "active":
            plan_active[topic].add(doc.get("user_id"))

    # Stage 4 -- practise supply, by family.
    practise: Dict[str, int] = collections.Counter()
    async for doc in db.community_puzzles.find({}, {"_id": 0, "issue_type": 1}):
        practise[str(doc.get("issue_type"))] += 1

    # Stage 5 -- application, keyed on the full quality id the ledger stores.
    applied: Dict[str, int] = collections.Counter()
    missed: Dict[str, int] = collections.Counter()
    taught_users: Dict[str, set] = collections.defaultdict(set)
    unknown_qids: Dict[str, int] = collections.Counter()
    async for doc in db.learning_sessions.find(
        user_filter, {"_id": 0, "user_id": 1, "events": 1}
    ):
        for event in doc.get("events") or []:
            result = event.get("lesson_result")
            if not isinstance(result, Mapping):
                continue
            application = result.get("application") or {}
            quality_id = application.get("detector_quality_id")
            if not quality_id:
                continue
            if quality_id not in rows:
                unknown_qids[quality_id] += 1
                continue
            taught_users[quality_id].add(doc.get("user_id"))
            outcome = application.get("outcome")
            if outcome == "applied":
                applied[quality_id] += 1
            elif outcome == "missed":
                missed[quality_id] += 1

    for quality_id, row in rows.items():
        family = row["family"] or ""
        row["plan_users"] = len(plan.get(family, ()))
        row["plan_active_users"] = len(plan_active.get(family, ()))
        row["puzzles"] = practise.get(family, 0)
        row["applied"] = applied.get(quality_id, 0)
        row["missed"] = missed.get(quality_id, 0)
        row["taught_users"] = len(taught_users.get(quality_id, ()))

    rows["__unknown_quality_ids__"] = {"unknown": dict(unknown_qids)}


def loop_complete(row: Mapping[str, Any]) -> Tuple[bool, Tuple[str, ...]]:
    missing = []
    if row["grade"] in {"SHADOW", "DISABLED"}:
        missing.append("1 detect")
    if not row.get("plan_users"):
        missing.append("2 plan")
    if not (row.get("content_id") or row.get("has_grader")):
        missing.append("3 teach")
    if not row.get("puzzles"):
        missing.append("4 practise")
    if not (row.get("applied") or row.get("missed")):
        missing.append("5 observe")
    return (not missing), tuple(missing)


def unfitness(row: Mapping[str, Any]) -> Optional[str]:
    applied, missed = row.get("applied", 0), row.get("missed", 0)
    if not (applied or missed):
        return None
    if not applied:
        return UNFIT_NO_SUCCESS
    if not missed:
        return UNFIT_NO_FAILURE
    return None


def report(rows: Dict[str, Dict[str, Any]], only: Optional[str]) -> None:
    unknown = rows.pop("__unknown_quality_ids__", {}).get("unknown", {})
    items = [
        row for row in rows.values()
        if not only or only in (row["quality_id"], row["family"] or "")
    ]
    items.sort(key=lambda r: (-(r.get("applied", 0) + r.get("missed", 0)),
                              r["quality_id"]))

    complete = [r for r in items if loop_complete(r)[0]]
    print(f"concepts examined: {len(items)}    loop-complete: {len(complete)}")
    print()
    header = "%-48s %-8s %5s %5s %7s %7s %7s" % (
        "concept", "grade", "plan", "puzz", "applied", "missed", "rate")
    print(header)
    print("-" * len(header))
    for row in items:
        total = row.get("applied", 0) + row.get("missed", 0)
        rate = ("%5.0f%%" % (100.0 * row["applied"] / total)) if total else "    -"
        print("%-48s %-8s %5d %5d %7d %7d %7s" % (
            row["quality_id"][:48], row["grade"], row.get("plan_users", 0),
            row.get("puzzles", 0), row.get("applied", 0), row.get("missed", 0),
            rate))

    print()
    print("LOOP-COMPLETE CONCEPTS")
    if complete:
        for row in complete:
            total = row["applied"] + row["missed"]
            print("   %-48s application rate %.0f%% over %d chances"
                  % (row["quality_id"], 100.0 * row["applied"] / total, total))
    else:
        print("   none")

    print()
    print("UNFIT TO CARRY A PROGRESS CLAIM")
    flagged = [(r, unfitness(r)) for r in items if unfitness(r)]
    if flagged:
        for row, why in flagged:
            print("   %-48s %s (%d applied / %d missed)"
                  % (row["quality_id"], why, row["applied"], row["missed"]))
    else:
        print("   none")

    print()
    print("WHERE THE LOOP BREAKS, counted by stage")
    stage_counts = collections.Counter()
    for row in items:
        for stage in loop_complete(row)[1]:
            stage_counts[stage] += 1
    for stage, count in sorted(stage_counts.items()):
        print("   %-12s missing on %3d of %d concepts" % (stage, count, len(items)))

    print()
    print("NOT MAPPED -- reported rather than dropped")
    print("   quality ids in lesson evidence with no authorization: %d %s"
          % (len(unknown), dict(list(unknown.items())[:4]) if unknown else ""))
    near = [r for r in items
            if r["grade"] not in {"SHADOW", "DISABLED"}
            and not (r.get("applied") or r.get("missed"))]
    print("   authorized to speak but never observed applying: %d" % len(near))
    for row in near[:8]:
        print("      %-48s %s" % (row["quality_id"], ", ".join(loop_complete(row)[1])))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concept", default=None,
                        help="a quality id or a family such as piece_safety")
    parser.add_argument("--user", default=None, help="restrict stages 2 and 5")
    args = parser.parse_args()

    rows = static_stages()
    url = os.environ["MONGO_URL"].replace("host.docker.internal", "localhost")
    db_name = os.environ.get("DB_NAME")
    if not db_name:
        raise SystemExit("DB_NAME must be set explicitly; the default is a trap")
    db = AsyncIOMotorClient(url, serverSelectionTimeoutMS=30000)[db_name]
    print(f"db={db_name}  concepts from detector_quality={len(rows)}")
    if args.user:
        print(f"restricted to user {args.user}")
    print()
    await live_stages(db, rows, args.user)
    report(rows, args.concept)


if __name__ == "__main__":
    asyncio.run(main())
