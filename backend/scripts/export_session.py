"""
Export a full Play with Coach session for diagnosis.

Shows every move, coaching decisions, checklist states,
player profile, behavior tracking — everything the system produced.

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

    # Get session ID
    session_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not session_id:
        latest = await db.coach_sessions.find_one({}, sort=[("created_at", -1)])
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

    user_id = session.get("user_id", "")

    # Fetch messages
    messages = await db.coach_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    # Fetch postgame
    postgame = await db.postgame_analyses.find_one(
        {"session_id": session_id}, {"_id": 0}
    )

    # Fetch player profile data
    player_strength = await db.player_strength_profiles.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    player_profile = await db.player_profiles.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    thinking_scores_recent = await db.thinking_scores.find(
        {"user_id": user_id}, {"_id": 0, "habit_scores": 1, "overall_score": 1}
    ).sort("calculated_at", -1).limit(5).to_list(5)

    # Fetch problem lifecycle
    problems = await db.problem_lifecycle.find(
        {"user_id": user_id}, {"_id": 0}
    ).to_list(10)

    # Build export
    move_history = session.get("move_history", [])
    fen_history = session.get("fen_history", [])
    evaluations = session.get("evaluations", [])

    moves = []
    for i, entry in enumerate(move_history):
        move_data = {
            "index": i,
            "move": entry.get("move") if isinstance(entry, dict) else entry,
            "by": entry.get("by") if isinstance(entry, dict) else None,
        }
        if i < len(fen_history):
            move_data["fen_before"] = fen_history[i]
        if i + 1 < len(fen_history):
            move_data["fen_after"] = fen_history[i + 1]
        if i < len(evaluations):
            move_data["eval"] = evaluations[i]

        # Messages for this move (by move_index if available, fallback to SAN)
        move_san = move_data["move"]
        move_msgs = [
            m for m in messages
            if m.get("move_index") == i or
               (m.get("move") == move_san and not m.get("move_index"))
        ]
        if move_msgs:
            move_data["coaching"] = move_msgs
        moves.append(move_data)

    export = {
        "exported_at": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "summary": {
            "user_id": user_id,
            "user_color": session.get("user_color"),
            "result": session.get("result"),
            "termination": session.get("termination_reason"),
            "total_moves": len(move_history),
            "user_rating": session.get("user_rating"),
            "detected_opening": session.get("detected_opening"),
            "opening_teaching_active": session.get("opening_teaching_active"),
            "focus_concept": session.get("focus_concept"),
            "created_at": session.get("created_at"),
            "ended_at": session.get("ended_at"),
        },
        "moves": moves,
        "messages": messages,
        "evaluations": evaluations,

        # New coaching system data
        "mde_debug_logs": session.get("mde_debug_logs", []),
        "behavior_summary": session.get("behavior_summary"),
        "fundamental_violations": session.get("fundamental_violations", []),
        "last_coaching_move_index": session.get("last_coaching_move_index"),

        # Player data (what the system knows about this player)
        "player_data": {
            "strength_profile": {
                "strongest": player_strength.get("strongest") if player_strength else None,
                "weakest": player_strength.get("weakest") if player_strength else None,
                "overall_score": player_strength.get("overall_score") if player_strength else None,
                "overall_label": player_strength.get("overall_label") if player_strength else None,
                "domains": player_strength.get("domains") if player_strength else None,
            } if player_strength else None,
            "profile": {
                "average_accuracy": player_profile.get("average_accuracy") if player_profile else None,
                "top_weaknesses": player_profile.get("top_weaknesses") if player_profile else None,
                "phase_accuracy": player_profile.get("phase_accuracy") if player_profile else None,
            } if player_profile else None,
            "recent_habit_scores": thinking_scores_recent,
            "active_problems": problems,
        },

        "postgame": postgame,
        "raw_session_fields": {
            k: v for k, v in session.items()
            if k not in ("fen_history", "move_history", "evaluations", "pgn", "mde_debug_logs")
        },
    }

    # Write to file
    filename = f"/tmp/session_export_{session_id[:8]}.json"
    with open(filename, "w") as f:
        json.dump(export, f, indent=2, default=str)

    # Print summary
    print(f"\n{'='*60}")
    print(f"SESSION EXPORT: {session_id[:8]}")
    print(f"{'='*60}")
    print(f"Color: {session.get('user_color')} | Result: {session.get('result')} | Moves: {len(move_history)}")
    print(f"Rating: {session.get('user_rating')} | Opening: {session.get('detected_opening')}")
    print(f"Focus: {session.get('focus_concept', {}).get('signal') if session.get('focus_concept') else 'none'}")
    print(f"Messages: {len(messages)}")

    # Coaching layer breakdown
    layer_counts = {}
    for m in messages:
        layer = m.get("trigger", m.get("message_type", "unknown"))
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    print(f"\nCoaching layers:")
    for layer, count in sorted(layer_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {layer}: {count}")

    # MDE debug summary
    mde_logs = session.get("mde_debug_logs", [])
    if mde_logs:
        print(f"\nMDE decisions: {len(mde_logs)}")
        layer_counts2 = {}
        for log in mde_logs:
            w = log.get("winner") or "silent"
            layer_counts2[w] = layer_counts2.get(w, 0) + 1
        for layer, count in sorted(layer_counts2.items(), key=lambda x: x[1], reverse=True):
            print(f"  {layer}: {count}")

    # Behavior summary
    behavior = session.get("behavior_summary")
    if behavior:
        print(f"\nBehavior summary:")
        for signal, count in behavior.get("counts", {}).items():
            if count > 0:
                print(f"  {signal}: {count}")

    # Player profile
    if player_strength:
        print(f"\nPlayer profile:")
        print(f"  Strongest: {player_strength.get('strongest')}")
        print(f"  Weakest: {player_strength.get('weakest')}")
        print(f"  Overall: {player_strength.get('overall_label')} ({player_strength.get('overall_score')})")

    # Active problems
    if problems:
        print(f"\nActive problems:")
        for p in problems:
            print(f"  {p.get('category')}: {p.get('state')} (anger={p.get('anger')}, count={p.get('count')})")

    print(f"\nExported to: {filename}")
    print(f"Copy out: docker cp chess-coach-backend:{filename} ./")


if __name__ == "__main__":
    asyncio.run(main())
