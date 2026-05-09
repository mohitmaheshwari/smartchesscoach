"""
Inspect the most recent Play-with-Coach session — dump all coach_messages
with full context so we can see exactly what the coach said vs what the
user perceived.

For debugging the "d5 mistake — and that's all the coach told" report.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def run(session_id: Optional[str] = None):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if not session_id:
        # Find the most recent session that has any coach messages
        pipe = [
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$session_id", "latest": {"$first": "$created_at"}}},
            {"$sort": {"latest": -1}},
            {"$limit": 1},
        ]
        async for doc in db.coach_messages.aggregate(pipe):
            session_id = doc["_id"]
            break
        if not session_id:
            print("No coach_messages found.")
            return

    print(f"\n=== Session: {session_id} ===\n")

    session = await db.coach_sessions.find_one(
        {"session_id": session_id},
        {"_id": 0, "user_id": 1, "user_color": 1, "result": 1,
         "move_history": 1, "created_at": 1},
    )
    if session:
        print(f"User: {session.get('user_id')}")
        print(f"Color: {session.get('user_color')}")
        print(f"Result: {session.get('result')}")
        moves = session.get("move_history") or []
        print(f"Moves played: {len(moves)}")
        if moves:
            line = []
            for i, m in enumerate(moves):
                san = m.get("move_san") or m.get("move") or "?"
                if i % 2 == 0:
                    line.append(f"{i//2+1}. {san}")
                else:
                    line[-1] += f" {san}"
            print("Game: " + " ".join(line[:20]))
        print()

    cursor = db.coach_messages.find(
        {"session_id": session_id},
    ).sort("created_at", 1)
    msgs = await cursor.to_list(500)
    print(f"=== {len(msgs)} coach_messages stored for this session ===\n")

    for i, m in enumerate(msgs):
        print(f"[{i+1:>3}]  trigger={m.get('trigger')}   move={m.get('move')!r}   move_number={m.get('move_number')}")
        # Print the full text — no truncation
        text = m.get("message") or ""
        for line in text.split("\n"):
            print(f"        | {line}")
        # Other potentially user-facing fields
        for fld in ("coaching_message", "socratic_question", "encouragement",
                    "rule", "narrative", "main_idea"):
            val = m.get(fld)
            if val and val != text:
                print(f"        + {fld}: {val}")
        print()

    client.close()


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(sid))
