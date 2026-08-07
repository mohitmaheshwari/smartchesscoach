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
  vs unresolved (still "active", no result, no ended_at, age-bucketed)
  -> postgame_analyses exists -> returned for a second coach_sessions doc

Correction, 2026-08-07 (external review): the original version classified
ANY session with status=="active" and no result/ended_at as "abandoned,"
with no minimum age. That's a real latent bug -- a session started 30
seconds ago and still being genuinely played would have been misclassified
identically to one dead for 3 months. Checked the actual age distribution
of the 18 flagged sessions in the first real run: minimum age was 244
hours (10.2 days), so nothing in that specific run was a false positive --
but the query itself had no age gate, so a different population could have
produced one. Buckets below are informed by that real distribution (a
typical PWC game takes well under 2 hours per the residency's traced
examples) rather than picked from round-number intuition alone.
`unresolved_stale` (>24h old) is the age-gated replacement for the old
unconditional `session_abandoned_active` -- use that field going forward,
not the old name.

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


def is_unresolved(session: dict) -> bool:
    """A first PWC session with no result and no ended_at, still 'active'.

    Pulled out as its own function (2026-08-07) so it's directly unit
    testable -- see backend/tests/test_pwc_first_session_funnel.py.
    """
    return (
        session.get("status") == "active"
        and not session.get("result")
        and not session.get("ended_at")
    )


def classify_unresolved_age(age_hours: float | None) -> str:
    """Bucket an unresolved session's age in hours.

    Buckets informed by the real age distribution found in production
    (2026-08-07): the first live run's minimum "abandoned" age was 244h
    (10.2 days) -- nothing was ever close to the 2h boundary. The 2h
    threshold itself comes from this residency's traced real game
    durations (well under 2 hours), not a round-number guess.
    `age_hours=None` (no parseable created_at) is treated conservatively
    as the stalest bucket rather than silently dropped.
    """
    if age_hours is None:
        return "unresolved_over_7d"
    if age_hours < 2:
        return "unresolved_recent_under_2h"
    if age_hours < 24:
        return "unresolved_2h_to_24h"
    if age_hours < 24 * 7:
        return "unresolved_1d_to_7d"
    return "unresolved_over_7d"


def is_stale_bucket(bucket: str) -> bool:
    """Everything except the youngest bucket counts as the real leak."""
    return bucket != "unresolved_recent_under_2h"


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
        # Age-bucketed replacement for the old unconditional "abandoned"
        # field. unresolved_recent (<2h) is NOT counted as a leak -- a
        # session that young could still be genuinely in progress.
        "unresolved_recent_under_2h": 0,
        "unresolved_2h_to_24h": 0,
        "unresolved_1d_to_7d": 0,
        "unresolved_over_7d": 0,
        "unresolved_stale": 0,  # sum of the three >2h buckets -- the real leak
        "has_postgame": 0,
        "returned_second_session": 0,
    }
    stale_examples = []

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
        if resolved:
            counts["session_resolved"] += 1
        if is_unresolved(first_session):
            created = _dt(first_session.get("created_at"))
            age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600 if created else None
            bucket = classify_unresolved_age(age_hours)
            counts[bucket] += 1
            if is_stale_bucket(bucket):
                counts["unresolved_stale"] += 1
                if len(stale_examples) < 5:
                    age_days = round((age_hours or 0) / 24, 1)
                    stale_examples.append(
                        f"  {uid}: session {first_session.get('session_id')}, "
                        f"created {first_session.get('created_at')}, unresolved {age_days}d later ({bucket})"
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

    print("\n=== STALE UNRESOLVED SESSIONS (>2h old, status=active, no result, no ended_at) -- real examples ===")
    for line in stale_examples:
        print(line)
    if counts["unresolved_stale"] > len(stale_examples):
        print(f"  ... and {counts['unresolved_stale'] - len(stale_examples)} more")
    if counts["unresolved_recent_under_2h"]:
        print(f"\n  (+{counts['unresolved_recent_under_2h']} more unresolved but under 2h old -- "
              f"NOT counted as stale, could still be genuinely in progress)")


if __name__ == "__main__":
    # 2026-08-07: guarded (was module-level, unconditional) so the pure
    # classification functions above can be imported for unit tests
    # (backend/tests/test_pwc_first_session_funnel.py) without triggering
    # a live DB connection attempt on import.
    asyncio.run(main())
