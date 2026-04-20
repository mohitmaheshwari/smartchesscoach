"""
User Activity Timeline — chronological log of what a user has done on the site.

Stitches events from multiple collections into one time-sorted stream:
  - Game imports        (games.imported_at)
  - Game analyses       (game_analyses.created_at / analyzed_at)
  - Coach sessions      (coach_sessions.created_at / completed_at)
  - Postgame analyses   (postgame_analyses.created_at + coach_prescription)
  - Puzzle attempts     (puzzle_attempts.attempted_at / created_at)
  - Notifications       (notifications.created_at)
  - Opening progress    (user_opening_progress.updated_at)

Usage:
    python scripts/user_activity.py <user_id>                    # last 100 events
    python scripts/user_activity.py <user_id> --limit 50
    python scripts/user_activity.py <user_id> --days 30
    python scripts/user_activity.py <user_id> --types game,coach # filter
    python scripts/user_activity.py                              # dev_user_local

Defaults to dev_user_local when no user_id given.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ─── HELPERS ──────────────────────────────────────────────────────────


def _to_datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _fmt_ts(dt):
    if not dt:
        return "               "
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _fmt_rel(dt):
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    d = now - dt
    if d.total_seconds() < 60:
        return "just now"
    if d.total_seconds() < 3600:
        return f"{int(d.total_seconds() // 60)}m ago"
    if d.total_seconds() < 86400:
        return f"{int(d.total_seconds() // 3600)}h ago"
    if d.days < 7:
        return f"{d.days}d ago"
    if d.days < 30:
        return f"{d.days // 7}w ago"
    return f"{d.days // 30}mo ago"


# ─── EVENT COLLECTORS ─────────────────────────────────────────────────


async def collect_game_imports(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    if since:
        q["imported_at"] = {"$gte": since}
    async for g in db.games.find(
        q, {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1,
            "platform": 1, "imported_at": 1, "termination": 1}
    ).sort("imported_at", -1).limit(500):
        ts = _to_datetime(g.get("imported_at"))
        if not ts:
            continue
        result = (g.get("result") or "").lower()
        if result in ("1-0", "0-1"):
            uc = (g.get("user_color") or "").lower()
            outcome = "won" if (result == "1-0" and uc == "white") or (result == "0-1" and uc == "black") else "lost"
        elif result in ("1/2-1/2", "draw", "d"):
            outcome = "drew"
        elif result in ("win", "w"): outcome = "won"
        elif result in ("loss", "l"): outcome = "lost"
        else:
            outcome = "played"
        opening = g.get("opening") or "unknown opening"
        platform = g.get("platform") or "unknown"
        events.append({
            "ts": ts,
            "type": "game",
            "summary": f"{outcome} a game — {opening} [{platform}]",
            "detail": f"termination={g.get('termination', '?')}",
            "game_id": g.get("game_id"),
        })
    return events


async def collect_analyses(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    if since:
        q["created_at"] = {"$gte": since}
    async for a in db.game_analyses.find(
        q, {"_id": 0, "game_id": 1, "created_at": 1,
            "stockfish_analysis.accuracy": 1,
            "stockfish_analysis.blunders": 1,
            "stockfish_analysis.mistakes": 1}
    ).sort("created_at", -1).limit(500):
        ts = _to_datetime(a.get("created_at"))
        if not ts:
            continue
        sf = a.get("stockfish_analysis") or {}
        events.append({
            "ts": ts,
            "type": "analysis",
            "summary": (
                f"game analyzed — accuracy {sf.get('accuracy', '?')}%, "
                f"{sf.get('blunders', 0)} blunders, {sf.get('mistakes', 0)} mistakes"
            ),
            "game_id": a.get("game_id"),
        })
    return events


async def collect_coach_sessions(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    if since:
        q["created_at"] = {"$gte": since}
    async for s in db.coach_sessions.find(
        q, {"_id": 0, "session_id": 1, "created_at": 1, "completed_at": 1,
            "status": 1, "result": 1, "opponent": 1, "focus": 1}
    ).sort("created_at", -1).limit(200):
        start = _to_datetime(s.get("created_at"))
        end = _to_datetime(s.get("completed_at"))
        if start:
            events.append({
                "ts": start,
                "type": "coach",
                "summary": f"started Play-with-Coach session"
                           + (f" (focus: {s['focus']})" if s.get("focus") else ""),
                "session_id": s.get("session_id"),
            })
        if end and s.get("status") == "completed":
            result = s.get("result") or "finished"
            events.append({
                "ts": end,
                "type": "coach",
                "summary": f"completed Play-with-Coach — {result}",
                "session_id": s.get("session_id"),
            })
    return events


async def collect_prescriptions(db, user_id, since):
    events = []
    q = {"user_id": user_id, "coach_prescription": {"$exists": True, "$ne": None}}
    if since:
        q["created_at"] = {"$gte": since}
    async for p in db.postgame_analyses.find(
        q, {"_id": 0, "coach_prescription": 1, "prescription_reason": 1,
            "prescription_type": 1, "game_result": 1, "created_at": 1}
    ).sort("created_at", -1).limit(200):
        ts = _to_datetime(p.get("created_at"))
        if not ts:
            continue
        events.append({
            "ts": ts,
            "type": "prescription",
            "summary": (
                f"coach prescribed: {p.get('coach_prescription')} "
                f"({p.get('prescription_type', 'pattern')}) after {p.get('game_result', '?')}"
            ),
            "detail": p.get("prescription_reason", ""),
        })
    return events


async def collect_puzzles(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    # puzzle_attempts uses attempted_at in some places, created_at elsewhere — try both
    time_field = None
    sample = await db.puzzle_attempts.find_one(q, {"attempted_at": 1, "created_at": 1})
    if sample:
        time_field = "attempted_at" if sample.get("attempted_at") else "created_at"
    if not time_field:
        return events
    if since:
        q[time_field] = {"$gte": since}
    async for attempt in db.puzzle_attempts.find(
        q, {"_id": 0, "correct": 1, "weakness_type": 1,
            "puzzle_id": 1, "attempted_at": 1, "created_at": 1}
    ).sort(time_field, -1).limit(200):
        ts = _to_datetime(attempt.get(time_field))
        if not ts:
            continue
        solved = "solved" if attempt.get("correct") else "missed"
        weakness = attempt.get("weakness_type") or ""
        events.append({
            "ts": ts,
            "type": "puzzle",
            "summary": f"{solved} a {weakness} puzzle".strip() if weakness else f"{solved} a puzzle",
        })
    return events


async def collect_opening_progress(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    if since:
        q["updated_at"] = {"$gte": since}
    async for op in db.user_opening_progress.find(
        q, {"_id": 0, "opening_name": 1, "games_played": 1,
            "mastery_level": 1, "updated_at": 1}
    ).sort("updated_at", -1).limit(50):
        ts = _to_datetime(op.get("updated_at"))
        if not ts:
            continue
        events.append({
            "ts": ts,
            "type": "opening",
            "summary": (
                f"opening progress: {op.get('opening_name', '?')} — "
                f"{op.get('games_played', 0)} games, mastery {op.get('mastery_level', 0)}%"
            ),
        })
    return events


async def collect_notifications(db, user_id, since):
    events = []
    q = {"user_id": user_id}
    if since:
        q["created_at"] = {"$gte": since}
    async for n in db.notifications.find(
        q, {"_id": 0, "title": 1, "body": 1, "created_at": 1, "kind": 1}
    ).sort("created_at", -1).limit(100):
        ts = _to_datetime(n.get("created_at"))
        if not ts:
            continue
        title = n.get("title") or n.get("kind") or "notification"
        events.append({
            "ts": ts,
            "type": "notification",
            "summary": f"notification: {title}",
            "detail": (n.get("body") or "")[:80],
        })
    return events


# ─── MAIN ─────────────────────────────────────────────────────────────


COLLECTORS = {
    "game": collect_game_imports,
    "analysis": collect_analyses,
    "coach": collect_coach_sessions,
    "prescription": collect_prescriptions,
    "puzzle": collect_puzzles,
    "opening": collect_opening_progress,
    "notification": collect_notifications,
}


async def build_activity(db, user_id, limit, days, types_filter):
    since = None
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    chosen = types_filter if types_filter else list(COLLECTORS.keys())
    all_events = []
    for kind in chosen:
        collector = COLLECTORS.get(kind)
        if not collector:
            continue
        events = await collector(db, user_id, since)
        all_events.extend(events)

    all_events.sort(key=lambda e: e["ts"], reverse=True)
    return all_events[:limit]


async def main_async(user_id, limit, days, types_filter):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Identity hint
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "display_name": 1})
    label = (user or {}).get("display_name") or (user or {}).get("email") or user_id
    print()
    print(f"Activity for: {label}  ({user_id})")
    print(f"DB: {DB_NAME}  |  limit={limit}  days={days or 'all'}  types={','.join(types_filter) if types_filter else 'all'}")
    print()

    events = await build_activity(db, user_id, limit, days, types_filter)

    if not events:
        print("  No activity in this window.")
    else:
        print(f"  {'When':<17} {'Relative':<10} {'Type':<13} Summary")
        print(f"  {'-'*17} {'-'*10} {'-'*13} {'-'*60}")
        for e in events:
            ts = _fmt_ts(e["ts"])
            rel = _fmt_rel(e["ts"])
            t = e["type"]
            summary = e["summary"]
            print(f"  {ts:<17} {rel:<10} {t:<13} {summary}")
            if e.get("detail"):
                print(f"  {' '*17} {' '*10} {' '*13} > {e['detail']}")

        print()
        # Quick counts
        counts = {}
        for e in events:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
        print("  Counts by type:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))

    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", nargs="?", default="dev_user_local")
    parser.add_argument("--limit", type=int, default=100, help="Max events to show (default 100)")
    parser.add_argument("--days", type=int, default=None, help="Only show events from last N days")
    parser.add_argument("--types", type=str, default=None,
                        help=f"Comma-separated filter: {','.join(COLLECTORS.keys())}")
    args = parser.parse_args()
    types_filter = [t.strip() for t in args.types.split(",")] if args.types else None
    asyncio.run(main_async(args.user_id, args.limit, args.days, types_filter))


if __name__ == "__main__":
    main()
