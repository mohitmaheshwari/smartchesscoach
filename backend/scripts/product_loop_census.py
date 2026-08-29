"""Read-only aggregate census for ChessGuru's coaching and revenue loops.

The report intentionally emits counts only. It never prints user identifiers,
emails, usernames, games, PGNs, positions, moves, payment IDs or provider IDs.

Usage:
    python scripts/product_loop_census.py
    python scripts/product_loop_census.py --days 30 --json

Connection comes from MONGO_URL and DB_NAME. No collection is mutated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, Iterable, Mapping, Optional

from pymongo import MongoClient


REPORT_VERSION = 1
DEFAULT_DAYS = 30

CORE_COLLECTIONS = (
    "users",
    "games",
    "game_analyses",
    "move_observations",
    "user_active_focus",
    "focus_history",
    "puzzle_attempts",
    "training_solve_attempts",
    "training_plans",
    "coach_sessions",
    "postgame_analyses",
    "payment_intents",
    "community_training_positions",
)

RECENT_COLLECTIONS = {
    "games": "imported_at",
    "game_analyses": "analyzed_at",
    "coach_sessions": "created_at",
    "puzzle_attempts": "created_at",
    "training_solve_attempts": "attempted_at",
}


def _as_utc(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _recent_summary(rows: Iterable[Mapping[str, Any]], date_field: str, since: datetime) -> Dict[str, int]:
    records = 0
    users = set()
    for row in rows:
        occurred_at = _as_utc(row.get(date_field))
        if occurred_at is None or occurred_at < since:
            continue
        records += 1
        user_id = row.get("user_id")
        if user_id:
            users.add(user_id)
    return {"records": records, "users": len(users)}


def _counter(values: Iterable[Any]) -> Dict[str, int]:
    return dict(sorted(Counter(str(value) if value is not None else "null" for value in values).items()))


def build_report(db, *, now: datetime, days: int) -> Dict[str, Any]:
    now = now.astimezone(timezone.utc)
    since = now - timedelta(days=days)

    counts = {name: db[name].count_documents({}) for name in CORE_COLLECTIONS}

    focus_rows = list(
        db.user_active_focus.find(
            {},
            {
                "_id": 0,
                "user_id": 1,
                "status": 1,
                "resolution": 1,
                "type": 1,
                "topic_key": 1,
                "current_metric": 1,
                "cycle_version": 1,
                "instruction_id": 1,
            },
        )
    )
    active_focus_rows = [row for row in focus_rows if row.get("status") == "active"]
    active_weakness_rows = [row for row in active_focus_rows if row.get("type") == "weakness"]

    recent: Dict[str, Dict[str, int]] = {}
    for collection_name, date_field in RECENT_COLLECTIONS.items():
        rows = db[collection_name].find({}, {"_id": 0, "user_id": 1, date_field: 1})
        recent[collection_name] = _recent_summary(rows, date_field, since)

    payment_statuses = _counter(
        row.get("status")
        for row in db.payment_intents.find({}, {"_id": 0, "status": 1})
    )

    return {
        "report_version": REPORT_VERSION,
        "generated_at": now.isoformat(),
        "window": {"days": days, "since": since.isoformat()},
        "counts": counts,
        "focus": {
            "users_with_any_focus_history": len({row.get("user_id") for row in focus_rows if row.get("user_id")}),
            "statuses": _counter(row.get("status") for row in focus_rows),
            "resolutions": _counter(row.get("resolution") for row in focus_rows),
            "with_current_metric": sum(row.get("current_metric") is not None for row in focus_rows),
            "cycle_v1": sum(row.get("cycle_version") == 1 for row in focus_rows),
            "active_records": len(active_focus_rows),
            "active_users": len({row.get("user_id") for row in active_focus_rows if row.get("user_id")}),
            "active_types": _counter(row.get("type") for row in active_focus_rows),
            "active_topics": _counter(row.get("topic_key") for row in active_focus_rows),
            "active_with_instruction_id": sum(bool(row.get("instruction_id")) for row in active_focus_rows),
            "active_weakness_records": len(active_weakness_rows),
            "active_weakness_users": len({row.get("user_id") for row in active_weakness_rows if row.get("user_id")}),
        },
        "adoption": {
            "lifetime_puzzle_attempt_users": len(db.puzzle_attempts.distinct("user_id")),
            "lifetime_training_solve_users": len(db.training_solve_attempts.distinct("user_id")),
            "lifetime_coach_session_users": len(db.coach_sessions.distinct("user_id")),
            "recent": recent,
        },
        "billing": {
            "payment_intent_statuses": payment_statuses,
            "pro_marked_users": db.users.count_documents({"plan": "pro"}),
            "verified_successful_payment_intents": sum(
                count for status, count in payment_statuses.items()
                if status in {"paid", "verified", "captured", "active"}
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--json", action="store_true", help="Emit compact JSON instead of indented JSON")
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be positive")

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    report = build_report(client[db_name], now=datetime.now(timezone.utc), days=args.days)
    print(json.dumps(report, indent=None if args.json else 2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

