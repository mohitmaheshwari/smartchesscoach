"""Check what cognitive_gap values actually exist in game_analyses."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    # Get all unique cognitive_gap values with their counts
    gap_counts = {}
    cp_loss_by_gap = {}

    cursor = db.game_analyses.find(
        {}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}
    ).limit(50)

    async for doc in cursor:
        evals = doc.get("stockfish_analysis", {}).get("move_evaluations", [])
        for ev in evals:
            gap = ev.get("cognitive_gap", "")
            cp = ev.get("cp_loss", 0) or 0
            if gap:
                gap_counts[gap] = gap_counts.get(gap, 0) + 1
                if gap not in cp_loss_by_gap:
                    cp_loss_by_gap[gap] = []
                cp_loss_by_gap[gap].append(cp)

    print(f"Total unique cognitive_gap values: {len(gap_counts)}")
    print()
    for gap, count in sorted(gap_counts.items(), key=lambda x: -x[1]):
        avg_cp = sum(cp_loss_by_gap[gap]) / len(cp_loss_by_gap[gap]) if cp_loss_by_gap[gap] else 0
        high_cp = sum(1 for cp in cp_loss_by_gap[gap] if cp >= 100)
        print(f"  {gap}: {count} total, {high_cp} with cp>=100, avg_cp={avg_cp:.0f}")

if __name__ == "__main__":
    asyncio.run(main())
