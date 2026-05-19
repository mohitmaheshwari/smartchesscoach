"""
Dump everything captured for one Play with Coach session.

Use this after playing a game to see, in order:
  - every request the frontend made
  - every response the backend sent
  - duration of each call
  - HTTP / error status

Usage (inside the container):
    docker exec -it chess-coach-backend python scripts/dump_pwc_session.py <session_id>

    # Quick summary only:
    docker exec -it chess-coach-backend python scripts/dump_pwc_session.py <session_id> --summary

    # Most recent session for a user:
    docker exec -it chess-coach-backend python scripts/dump_pwc_session.py --user <user_id> --latest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _trim(value, max_len=400):
    """Compress a value to a single readable line. Truncate strings,
    summarize dicts/lists."""
    if value is None:
        return "null"
    if isinstance(value, str):
        s = value.replace("\n", " ")
        return s if len(s) <= max_len else s[:max_len] + "..."
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        keys = list(value.keys())[:8]
        return "{" + ", ".join(keys) + ("..." if len(value) > 8 else "") + "}"
    if isinstance(value, list):
        return f"[{len(value)} items]"
    return str(value)[:max_len]


async def find_session_id(db, args) -> str | None:
    if args.session_id:
        return args.session_id
    if args.user and args.latest:
        s = await db.coach_sessions.find_one(
            {"user_id": args.user},
            {"_id": 0, "session_id": 1},
            sort=[("created_at", -1)],
        )
        return s.get("session_id") if s else None
    return None


async def main(args):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    session_id = await find_session_id(db, args)
    if not session_id:
        print("Need either --session-id <id> or --user <uid> --latest", file=sys.stderr)
        sys.exit(2)

    # Header — session metadata so a debugger has anchor info.
    session = await db.coach_sessions.find_one(
        {"session_id": session_id},
        {"_id": 0, "user_id": 1, "status": 1, "result": 1, "user_color": 1,
         "created_at": 1, "ended_at": 1, "current_fen": 1,
         "move_history": 1, "pedagogical_mode_active": 1,
         "coaching_decisions": 1, "move_snapshots": 1,
         "fundamental_violations": 1, "behavior_events": 1,
         "habit_violations": 1, "opportunity_history": 1},
    )
    if not session:
        print(f"No coach_session found for {session_id}", file=sys.stderr)
        sys.exit(2)

    print("=" * 78)
    print(f"SESSION  {session_id}")
    print(f"  user_id    : {session.get('user_id')}")
    print(f"  status     : {session.get('status')}")
    print(f"  result     : {session.get('result')}")
    print(f"  color      : {session.get('user_color')}")
    print(f"  created_at : {session.get('created_at')}")
    print(f"  ended_at   : {session.get('ended_at')}")
    print(f"  fen        : {session.get('current_fen')}")
    print(f"  moves      : {len(session.get('move_history') or [])}")
    print(f"  pedagogical_active : {session.get('pedagogical_mode_active')}")

    # Internal arrays — these often the ones that should populate but don't.
    internal_counts = {
        "coaching_decisions": len(session.get("coaching_decisions") or []),
        "move_snapshots": len(session.get("move_snapshots") or []),
        "fundamental_violations": len(session.get("fundamental_violations") or []),
        "behavior_events": len(session.get("behavior_events") or []),
        "habit_violations": len(session.get("habit_violations") or []),
        "opportunity_history": len(session.get("opportunity_history") or []),
    }
    print()
    print("INTERNAL STATE COUNTS  (zero = layer silent for this game)")
    for k, v in internal_counts.items():
        flag = " <-- EMPTY" if v == 0 else ""
        print(f"  {k:24s} {v:4d}{flag}")

    # Coach messages
    msg_count = await db.coach_messages.count_documents({"session_id": session_id})
    print(f"\nCOACH MESSAGES         {msg_count:4d}")
    if not args.summary:
        async for m in db.coach_messages.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("created_at", 1):
            print(f"  {m.get('created_at')}  type={m.get('type')}  move={m.get('move_number')}  {_trim(m.get('message'), 120)}")

    # Trace rows — what the API actually returned, in order
    trace_count = await db.pwc_session_traces.count_documents({"session_id": session_id})
    print(f"\nREQUEST TRACES         {trace_count:4d}")
    if trace_count == 0:
        print("  (none — either pre-tracer game, or tracer wiring not deployed yet)")
    else:
        async for t in db.pwc_session_traces.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("ts", 1):
            print(f"  {t.get('ts')}  {t.get('endpoint'):42s} {t.get('duration_ms'):>6.0f}ms  {t.get('status')}")
            if not args.summary:
                req = t.get("request")
                resp = t.get("response")
                if req:
                    print(f"     req  : {_trim(req, 200)}")
                if resp:
                    print(f"     resp : {_trim(resp, 200)}")

    # Postgame
    pg = await db.postgame_analyses.find_one(
        {"session_id": session_id}, {"_id": 0},
    )
    print(f"\nPOSTGAME ANALYSIS      {'present' if pg else 'MISSING'}")
    if pg and not args.summary:
        for k, v in pg.items():
            print(f"  {k:20s} {_trim(v, 100)}")

    print("=" * 78)
    client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session_id", nargs="?", help="session_id to dump")
    ap.add_argument("--user", help="user_id (use with --latest)")
    ap.add_argument("--latest", action="store_true", help="pick most recent session for --user")
    ap.add_argument("--summary", action="store_true", help="skip per-event detail")
    args = ap.parse_args()
    if args.session_id and args.session_id.startswith("--"):
        args.session_id = None
    asyncio.run(main(args))
