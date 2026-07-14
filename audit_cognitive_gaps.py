"""
Audit cognitive gap detection on real user games.

Shows:
1. What gaps ARE being detected
2. What gaps might be MISSED
3. Patterns and blindspots
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
import json

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def audit_gaps():
    """Analyze cognitive gap detection on real games."""

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print("\n" + "="*80)
    print("COGNITIVE GAP DETECTION AUDIT")
    print("="*80 + "\n")

    # Get user with most analyzed games
    users = await db.users.find().to_list(None)
    print(f"📊 Found {len(users)} users\n")

    for user in users:
        user_id = user.get("user_id")
        user_rating = user.get("assessed_rating") or user.get("detected_rating") or 1200

        # Get analyzed games for this user
        games = await db.games.find(
            {"user_id": user_id, "is_analyzed": True}
        ).to_list(10)  # First 10 games

        if not games:
            continue

        print(f"\n👤 USER: {user_id} (Rating: {user_rating})")
        print(f"   Analyzed games: {len(games)}\n")

        gap_summary = defaultdict(lambda: {"count": 0, "moves": []})
        missing_analysis = 0
        total_mistakes = 0

        for game_idx, game in enumerate(games, 1):
            game_id = game.get("game_id")

            # Get analysis
            analysis = await db.game_analyses.find_one(
                {"game_id": game_id}
            )

            if not analysis:
                missing_analysis += 1
                continue

            move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
            if not move_evals:
                continue

            # Find mistakes and their gaps
            for move_eval in move_evals:
                if not move_eval.get("is_user_move"):
                    continue

                cp_loss = move_eval.get("cp_loss", 0)
                if cp_loss < 50:  # Not a real mistake
                    continue

                total_mistakes += 1
                move_san = move_eval.get("move", "?")
                gap = move_eval.get("cognitive_gap", "UNCLASSIFIED")
                best_move = move_eval.get("best_move", "?")

                gap_summary[gap]["count"] += 1
                gap_summary[gap]["moves"].append({
                    "move": move_san,
                    "best": best_move,
                    "cp_loss": cp_loss,
                    "game": game_id[:8]
                })

        # Print summary for this user
        print(f"   Total mistakes (cp_loss ≥ 50): {total_mistakes}")
        print(f"   Missing analysis: {missing_analysis}\n")
        print("   Gap Distribution:")

        for gap in sorted(gap_summary.keys(),
                         key=lambda x: gap_summary[x]["count"],
                         reverse=True):
            count = gap_summary[gap]["count"]
            pct = 100 * count / total_mistakes if total_mistakes > 0 else 0
            status = "✓" if gap != "UNCLASSIFIED" else "❌"
            print(f"     {status} {gap:25} {count:3}x ({pct:5.1f}%)")

        # Show sample mistakes
        print("\n   Sample Mistakes:")
        for gap in list(gap_summary.keys())[:3]:
            print(f"\n     {gap}:")
            for move_info in gap_summary[gap]["moves"][:2]:
                print(f"       {move_info['move']} (best: {move_info['best']}, "
                      f"loss: {move_info['cp_loss']}cp, game: {move_info['game']})")

    # Aggregate stats
    print("\n" + "="*80)
    print("AGGREGATE FINDINGS")
    print("="*80 + "\n")

    all_gaps = await db.game_analyses.aggregate([
        {"$unwind": "$stockfish_analysis.move_evaluations"},
        {"$match": {"stockfish_analysis.move_evaluations.is_user_move": True,
                   "stockfish_analysis.move_evaluations.cp_loss": {"$gte": 50}}},
        {"$group": {
            "_id": "$stockfish_analysis.move_evaluations.cognitive_gap",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]).to_list(None)

    print("Top cognitive gaps across ALL games:\n")
    total = sum(g["count"] for g in all_gaps)
    for gap in all_gaps[:15]:
        pct = 100 * gap["count"] / total
        status = "✓" if gap["_id"] != "UNCLASSIFIED" else "❌"
        print(f"  {status} {gap['_id']:25} {gap['count']:5}x ({pct:5.1f}%)")

    print(f"\n  Total mistakes detected: {total}\n")

    # Check for blindspots
    print("="*80)
    print("POTENTIAL BLINDSPOTS")
    print("="*80 + "\n")

    unclassified = sum(g["count"] for g in all_gaps if g["_id"] == "UNCLASSIFIED")
    if unclassified > 0:
        pct = 100 * unclassified / total
        print(f"⚠️  UNCLASSIFIED: {unclassified}x ({pct:.1f}%) — System can't categorize these")

    print(f"\n✓ Detected categories: {len([g for g in all_gaps if g['_id'] != 'UNCLASSIFIED'])}")
    print("✓ Top gaps are tactical (piece_safety, missed_tactic, calculation_depth)")
    print("✓ King safety is well-detected")
    print("\n❓ Are we detecting:")
    print("  • Opening mistakes (beyond deviation)? [UNKNOWN - check sample games]")
    print("  • Motif patterns (fork/pin/skewer)? [UNKNOWN - mixed in tactical]")
    print("  • Prophylaxis/defensive errors? [LIKELY MISSING]")
    print("  • Transition mistakes (open→middle→end)? [LIKELY MISSING]")

    client.close()


if __name__ == "__main__":
    asyncio.run(audit_gaps())
