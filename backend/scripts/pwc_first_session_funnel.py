"""pwc_first_session_funnel.py — the exact PWC first-session funnel,
built from the Session 3 product residency (2026-08-07,
docs/product_residency_notes.md).

Extends the existing Activation Timeline pattern
(scripts/activation_timeline.py) with PWC-specific stages the residency
found matter, especially the mid-session abandonment gap the residency
surfaced directly: a session can sit `status: "active"` indefinitely,
with no result, no ended_at, and no postgame -- a real, distinct leak
from "never started PWC at all."

Stages traced, per real user, first PWC session only:
  signup -> first PWC session created -> first evaluated move ->
  first mistake (severity != good) -> session resolved (has a result)
  vs abandoned (still "active", no result, no ended_at) ->
  postgame_analyses exists -> returned for a second coach_sessions doc

Usage:
  docker exec -i chess-coach-backend python3 scripts/pwc_first_session_funnel.py --recent 50
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

TEST_MARKERS = ("test", "demo_", "dev_user_local")


def _dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _is_real(user_id: str, email: str) -> bool:
    email = (email or "").lower()
    uid = (user_id or "").lower()
    if any(m in email or m in uid for m in TEST_MARKERS):
        return False
    return True


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--recent", type=int, default=50, help="most recent real signups to trace")
    args = p.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    users = await db.users.find(
        {}, {"_id": 0, "user_id": 1, "email": 1, "created_at": 1, "role": 1}
    ).sort("created_at", -1).to_list(500)
    real_users = [
        u for u in users
        if _is_real(u.get("user_id"), u.get("email")) and u.get("role") not in ("admin", "super_admin")
    ][: args.recent]

    n = len(real_users)
    print(f"Tracing {n} real recent signups (role != admin/super_admin, no test/demo markers).\n")

    counts = {
        "signed_up": n,
        "started_pwc": 0,
        "first_move_evaluated": 0,
        "reached_first_mistake": 0,
        "session_resolved": 0,
        "session_abandoned_active": 0,
        "has_postgame": 0,
        "returned_second_session": 0,
    }
    abandoned_examples = []

    for u in real_users:
        uid = u["user_id"]
        first_session = await db.coach_sessions.find_one(
            {"user_id": uid}, sort=[("created_at", 1)]
        )
        if not first_session:
            continue
        counts["started_pwc"] += 1

        evals = first_session.get("evaluations") or []
        if evals:
            counts["first_move_evaluated"] += 1
        if any((e.get("score") is not None and e.get("best_move") and e.get("move") != e.get("best_move")) for e in evals):
            # Heuristic: real severity lives in move_snapshots.coaching.severity,
            # not on the flat evaluations[] array -- check that directly too.
            pass
        snapshots = first_session.get("move_snapshots") or []
        had_mistake = any(
            (s.get("coaching") or {}).get("severity") in ("mistake", "blunder", "inaccuracy")
            for s in snapshots
        )
        if had_mistake:
            counts["reached_first_mistake"] += 1

        resolved = bool(first_session.get("result"))
        abandoned = (
            first_session.get("status") == "active"
            and not first_session.get("result")
            and not first_session.get("ended_at")
        )
        if resolved:
            counts["session_resolved"] += 1
        if abandoned:
            counts["session_abandoned_active"] += 1
            if len(abandoned_examples) < 5:
                age_days = (datetime.now(timezone.utc) - _dt(first_session.get("created_at"))).days
                abandoned_examples.append(
                    f"  {uid}: session {first_session.get('session_id')}, "
                    f"created {first_session.get('created_at')}, still active {age_days}d later"
                )

        pg = await db.postgame_analyses.find_one({"session_id": first_session.get("session_id")})
        if pg:
            counts["has_postgame"] += 1

        n_sessions = await db.coach_sessions.count_documents({"user_id": uid})
        if n_sessions >= 2:
            counts["returned_second_session"] += 1

    print("=== PWC FIRST-SESSION FUNNEL ===")
    base = max(1, counts["signed_up"])
    for k, v in counts.items():
        pct = round(100 * v / base)
        print(f"  {k:28s}: {v:4d} / {base}  ({pct}%)")

    print("\n=== ABANDONED SESSIONS (status=active, no result, no ended_at) -- real examples ===")
    for line in abandoned_examples:
        print(line)
    if counts["session_abandoned_active"] > len(abandoned_examples):
        print(f"  ... and {counts['session_abandoned_active'] - len(abandoned_examples)} more")


asyncio.run(main())
