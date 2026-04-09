"""
Export a full Play with Coach session for diagnosis.

Shows every move, every coaching message, every intervention —
exactly what the player saw, with positions.

Usage:
  docker cp scripts/export_session.py chess-coach-backend:/app/backend/scripts/

  # Export most recent session:
  docker exec -it chess-coach-backend python3 scripts/export_session.py

  # Export specific session:
  docker exec -it chess-coach-backend python3 scripts/export_session.py SESSION_ID
"""

import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    # Get session ID from args or find most recent
    session_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not session_id:
        latest = await db.coach_sessions.find_one(
            {},
            sort=[("created_at", -1)]
        )
        if not latest:
            print("No sessions found.")
            return
        session_id = latest["session_id"]
        print(f"Using most recent session: {session_id}")

    # Fetch session
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        print(f"Session {session_id} not found.")
        return

    # Fetch all messages for this session
    messages = await db.coach_messages.find(
        {"session_id": session_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    # Fetch postgame analysis if exists
    postgame = await db.postgame_analyses.find_one(
        {"session_id": session_id},
        {"_id": 0}
    )

    # Build the export
    export = {
        "exported_at": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "summary": {
            "user_color": session.get("user_color"),
            "result": session.get("result"),
            "termination": session.get("termination_reason"),
            "total_moves": len(session.get("move_history", [])),
            "user_rating": session.get("user_rating"),
            "coach_skill_level": session.get("coach_skill_level"),
            "created_at": session.get("created_at"),
            "ended_at": session.get("ended_at"),
            "detected_opening": session.get("detected_opening"),
            "opening_to_teach": session.get("opening_to_teach"),
            "opening_teaching_active": session.get("opening_teaching_active"),
            "curriculum_active": session.get("curriculum_active"),
        },
        "moves": [],
        "messages": [],
        "evaluations": session.get("evaluations", []),
        "fundamental_violations": session.get("fundamental_violations", []),
        "habit_violations": session.get("habit_violations", []),
        "guardian_overrides": session.get("guardian_overrides", []),
        "postgame": postgame,
    }

    # Build move-by-move timeline
    move_history = session.get("move_history", [])
    fen_history = session.get("fen_history", [])
    evaluations = session.get("evaluations", [])

    for i, move_entry in enumerate(move_history):
        move_data = {
            "index": i,
            "move": move_entry.get("move") if isinstance(move_entry, dict) else move_entry,
            "fen_before": fen_history[i] if i < len(fen_history) else None,
            "fen_after": fen_history[i + 1] if i + 1 < len(fen_history) else None,
        }

        # Attach evaluation if available
        if i < len(evaluations):
            ev = evaluations[i]
            if isinstance(ev, dict):
                move_data["eval"] = ev
            else:
                move_data["eval"] = {"score": ev}

        # Attach any messages for this move
        move_msgs = [m for m in messages if m.get("move_number") == (i + 1) // 2 + 1
                     or m.get("move") == (move_entry.get("move") if isinstance(move_entry, dict) else move_entry)]
        if move_msgs:
            move_data["coaching_messages"] = move_msgs

        export["moves"].append(move_data)

    # All messages (in order)
    export["messages"] = messages

    # Raw session fields for full diagnosis
    export["raw_session"] = {
        k: v for k, v in session.items()
        if k not in ("fen_history", "move_history", "evaluations", "_id")
        and not isinstance(v, bytes)
    }

    # Write to file
    filename = f"/tmp/session_export_{session_id[:8]}.json"
    with open(filename, "w") as f:
        json.dump(export, f, indent=2, default=str)

    print(f"\nExported to: {filename}")
    print(f"\nSession: {session_id}")
    print(f"Color: {session.get('user_color')} | Result: {session.get('result')} | Moves: {len(move_history)}")
    print(f"Opening: {session.get('detected_opening')} | Teaching: {session.get('opening_teaching_active')}")
    print(f"Messages: {len(messages)}")
    if export["fundamental_violations"]:
        print(f"Fundamental violations: {len(export['fundamental_violations'])}")
    print(f"\nTo copy out: docker cp chess-coach-backend:{filename} ./")

    # Also print a quick summary of messages
    print(f"\n{'='*60}")
    print("MESSAGE TIMELINE")
    print(f"{'='*60}")
    for msg in messages:
        move = msg.get("move", "?")
        mtype = msg.get("type", "?")
        quality = msg.get("move_quality", "")
        text = msg.get("message", "")[:120]
        trigger = msg.get("trigger", "")
        print(f"  [{mtype}] move={move} quality={quality} trigger={trigger}")
        print(f"    {text}")
        if msg.get("question"):
            q = msg["question"]
            if isinstance(q, dict):
                print(f"    Q: {q.get('prompt', '')[:100]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
