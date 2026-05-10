"""
Replay every user move's feedback generation for a Play-with-Coach session.

The MoveFeedbackPanel data is transient — generated on demand by
get_last_move_feedback, not stored in coach_messages. So to see what
the user actually saw move-by-move, we re-run generate_move_feedback
on each user move and dump the full result.

Diagnoses the user's report: 'd5 mistake — that's all the coach told'.
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

from services.realtime_coaching_feedback import generate_move_feedback

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def run(session_id: Optional[str] = None):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    if not session_id:
        # Pick the most recent session with at least 5 moves
        async for s in db.coach_sessions.find(
            {}, {"_id": 0, "session_id": 1, "user_id": 1, "move_history": 1}
        ).sort("created_at", -1).limit(50):
            mh = s.get("move_history") or []
            if len(mh) >= 5:
                session_id = s["session_id"]
                break

    if not session_id:
        print("No session found.")
        return

    session = await db.coach_sessions.find_one({"session_id": session_id})
    if not session:
        print(f"Session {session_id} not found")
        return

    user_id = session.get("user_id")
    move_history = session.get("move_history") or []
    user_move_count = sum(1 for m in move_history if m.get("by") == "player")

    print(f"\n=== Session: {session_id} ===")
    print(f"User: {user_id}")
    print(f"Total user moves: {user_move_count}")
    print()

    # Replay feedback for each user move
    for n in range(1, min(user_move_count + 1, 21)):
        print(f"\n{'=' * 70}")
        print(f"USER MOVE #{n}")
        print(f"{'=' * 70}")
        try:
            fb = await generate_move_feedback(db, session_id, n, user_id)
        except Exception as e:
            print(f"  ERROR generating feedback: {e}")
            continue
        if fb is None:
            print("  feedback = None")
            continue
        # fb is a MoveFeedback object — .to_dict() gives us everything
        try:
            d = fb.to_dict()
        except Exception:
            d = fb if isinstance(fb, dict) else {"_obj": str(fb)}

        # Print the user-facing fields with priority
        priority_fields = [
            "user_move", "user_move_quality",
            "best_move",
            "coaching_message",
            "socratic_question", "expects_response",
            "encouragement",
            "rule",
            "meta_pattern_id",
            "best_move_explanation",
            "coach_move_explanation",
        ]
        for k in priority_fields:
            v = d.get(k)
            if v is None or v == "":
                continue
            v_str = str(v)
            if len(v_str) > 300:
                v_str = v_str[:300] + "..."
            print(f"  {k}: {v_str}")

        # Also dump any field we missed that has user-facing-looking content
        skip = set(priority_fields) | {
            "_id", "fen_before", "fen_after", "session_id", "user_id",
            "move_number", "tactical_analysis", "eval_before", "eval_after",
            "centipawn_loss", "is_user_move", "rating_band", "rating",
            "user_move_uci", "best_move_uci", "coach_move", "coach_move_uci",
        }
        for k in sorted(d.keys()):
            if k in skip:
                continue
            v = d.get(k)
            if v is None or v == "" or (isinstance(v, (list, dict)) and not v):
                continue
            v_str = str(v)
            if len(v_str) > 200:
                v_str = v_str[:200] + "..."
            print(f"  [extra] {k}: {v_str}")

    client.close()


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(sid))
