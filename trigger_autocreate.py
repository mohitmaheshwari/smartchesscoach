#!/usr/bin/env python3
"""Trigger the recommendations endpoint logic to auto-create prescriptions"""
import os
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

async def simulate_recommendations_endpoint():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]

    user_id = "user_8b599930d7ef"
    print("Simulating recommendations endpoint call for user with games...")
    print()

    # This is the logic from recommendations-with-accuracy endpoint
    games = await db.games.find({"user_id": user_id}).to_list(None)
    if not games:
        print("No games found")
        return

    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find({"game_id": {"$in": game_ids}}).to_list(None)

    gap_data = {}
    for analysis in analyses:
        moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        for move in moves:
            if not move.get("is_opponent_move") and move.get("cp_loss", 0) > 0:
                gap = move.get("cognitive_gap")
                if gap:
                    if gap not in gap_data:
                        gap_data[gap] = {"cp_loss": 0, "count": 0}
                    gap_data[gap]["cp_loss"] += move.get("cp_loss", 0)
                    gap_data[gap]["count"] += 1

    # Get top 5 gaps
    sorted_gaps = sorted(gap_data.items(), key=lambda x: x[1]["count"], reverse=True)[:5]

    print(f"Found {len(sorted_gaps)} top gaps")
    print()

    # For each gap, check if pending prescription exists, if not CREATE IT
    for gap_name, gap_info in sorted_gaps:
        gap_cp = gap_info["cp_loss"]

        # THIS IS THE AUTO-CREATE LOGIC FROM THE ENDPOINT
        pending_pres = await db.user_coaching_prescriptions.find_one(
            {
                "user_id": user_id,
                "issue_detected": gap_name,
                "status": "pending"
            },
            {"_id": 0, "prescription_id": 1}
        )

        if pending_pres:
            prescription_id = pending_pres.get("prescription_id")
            print(f"✓ {gap_name}: prescription_id = {prescription_id} (EXISTS)")
        else:
            # AUTO-CREATE
            prescription_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            duration_weeks = 4
            expected_completion = (now + timedelta(weeks=duration_weeks)).isoformat()

            new_pres = {
                "prescription_id": prescription_id,
                "user_id": user_id,
                "plan_id": None,
                "plan_name": gap_name.replace("_", " ").title(),
                "status": "pending",
                "issue_detected": gap_name,
                "reasoning": f"Auto-detected from game analysis: {gap_info['count']} mistakes",
                "baseline_metric": 0.0,
                "current_metric": 0.0,
                "improvement_pct": 0.0,
                "started_at": None,
                "completed_at": None,
                "expected_completion_date": expected_completion,
                "priority_order": 999,
                "modules_completed": [],
                "current_module": None,
                "puzzles_completed": 0,
                "puzzle_accuracy": 0.0,
                "notes": "",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

            result = await db.user_coaching_prescriptions.insert_one(new_pres)
            print(f"✓ {gap_name}: prescription_id = {prescription_id} (CREATED)")

    print()
    print("Verifying all prescriptions now exist...")
    print()

    # Verify all now exist
    for gap_name, _ in sorted_gaps:
        pres = await db.user_coaching_prescriptions.find_one(
            {"user_id": user_id, "issue_detected": gap_name, "status": "pending"}
        )
        if pres:
            print(f"✓ {gap_name}: {pres['prescription_id']}")
        else:
            print(f"✗ {gap_name}: STILL MISSING")

asyncio.run(simulate_recommendations_endpoint())
