#!/usr/bin/env python3
"""Test complete end-to-end coaching loop"""
import os
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

async def test_full_loop():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]

    user_id = "user_8b599930d7ef"
    print("=" * 60)
    print("END-TO-END COACHING LOOP TEST")
    print("=" * 60)

    # STEP 1: Verify user has games analyzed
    games = await db.games.find({"user_id": user_id}).to_list(None)
    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find({"game_id": {"$in": game_ids}}).to_list(None)
    print(f"\nSTEP 1: Games & Analysis")
    print(f"  Games: {len(games)}")
    print(f"  Analyzed: {len(analyses)}")

    # STEP 2: Get top cognitive gap
    gap_data = {}
    for a in analyses:
        moves = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        for m in moves:
            if not m.get("is_opponent_move") and m.get("cp_loss", 0) > 0:
                gap = m.get("cognitive_gap")
                if gap:
                    if gap not in gap_data:
                        gap_data[gap] = {"count": 0, "cp_loss": 0}
                    gap_data[gap]["count"] += 1
                    gap_data[gap]["cp_loss"] += m.get("cp_loss", 0)

    if not gap_data:
        print("ERROR: No gaps found")
        return

    top_gap = sorted(gap_data.items(), key=lambda x: x[1]["count"], reverse=True)[0]
    gap_name = top_gap[0]
    gap_mistakes = top_gap[1]["count"]
    gap_cp = top_gap[1]["cp_loss"]
    print(f"\nSTEP 2: Identify Gap")
    print(f"  Gap: {gap_name}")
    print(f"  Mistakes: {gap_mistakes}")
    print(f"  Total cp_loss: {gap_cp}")

    # STEP 3: Check prescription
    pres = await db.user_coaching_prescriptions.find_one(
        {"user_id": user_id, "issue_detected": gap_name, "status": "pending"}
    )
    if not pres:
        print(f"ERROR: No pending prescription for {gap_name}")
        return

    prescription_id = pres["prescription_id"]
    print(f"\nSTEP 3: Prescription Exists")
    print(f"  ID: {prescription_id}")
    print(f"  Status: pending")

    # STEP 4: Activate prescription
    now = datetime.now(timezone.utc)
    baseline_cp = gap_cp

    result = await db.user_coaching_prescriptions.update_one(
        {"prescription_id": prescription_id, "user_id": user_id},
        {
            "$set": {
                "status": "active",
                "started_at": now.isoformat(),
                "baseline_metric": baseline_cp,
                "current_metric": baseline_cp,
                "improvement_pct": 0.0,
                "updated_at": now.isoformat()
            }
        }
    )

    print(f"\nSTEP 4: Activate Prescription")
    print(f"  Baseline metric: {baseline_cp}cp")
    print(f"  Status: pending → active")
    print(f"  Started: {now.isoformat()}")

    # STEP 5: Check for training games
    games_after = await db.games.find({
        "user_id": user_id,
        "date_played": {"$gte": now.isoformat()}
    }).to_list(None)

    print(f"\nSTEP 5: Training Phase")
    print(f"  Games after activation: {len(games_after)}")

    # STEP 6: Calculate improvement (if games exist)
    current_cp = 0
    games_with_gap_after = 0

    for game in games_after:
        analysis = await db.game_analyses.find_one({"game_id": game["game_id"]})
        if analysis:
            moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            gap_found = False
            for m in moves:
                if not m.get("is_opponent_move") and m.get("cognitive_gap") == gap_name and m.get("cp_loss", 0) > 0:
                    current_cp += m.get("cp_loss", 0)
                    gap_found = True
            if gap_found:
                games_with_gap_after += 1

    print(f"\nSTEP 6: Track Improvement")
    print(f"  Games with gap after start: {games_with_gap_after}")
    print(f"  Current cp_loss: {current_cp}cp")

    # STEP 7: Check auto-close
    if games_with_gap_after >= 3:
        improvement = (baseline_cp - current_cp) / baseline_cp if baseline_cp > 0 else 0
        improvement_pct = improvement * 100
        print(f"\nSTEP 7: Auto-Close Check")
        print(f"  Baseline: {baseline_cp}cp")
        print(f"  Current: {current_cp}cp")
        print(f"  Improvement: {improvement_pct:.1f}%")

        if improvement >= 0.50:
            print(f"  STATUS: ELIGIBLE FOR AUTO-CLOSE ✓")
        else:
            print(f"  STATUS: Keep training (need 50%, have {improvement_pct:.1f}%)")
    else:
        print(f"\nSTEP 7: Auto-Close Check")
        print(f"  STATUS: Waiting for training (need {3 - games_with_gap_after} more games)")

    # Summary
    print(f"\n" + "=" * 60)
    print("COACHING LOOP STATUS:")
    print("=" * 60)
    print("✓ Analyze games → identify gap")
    print("✓ Create prescription → baseline calculated")
    print("✓ User activates plan → tracking starts")
    print(f"? User trains → (waiting for {3 - min(games_with_gap_after, 3)} more games)")
    print("? System measures improvement → (calculates after 3+ games)")
    print("? Auto-close on 50% improvement → (triggers when ready)")
    print("=" * 60)

asyncio.run(test_full_loop())
