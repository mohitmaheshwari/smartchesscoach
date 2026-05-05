"""
Audit how many games we have, how many are analyzed, and how many can
actually run through the voice pipeline. Answers "why does
batch_voice_regen only find N games when we have M total?"

Layers checked:
  1. games            — every game ever imported / created
  2. game_analyses    — Stockfish-analyzed games
  3. has decryption_v5_data — V5 pipeline ran successfully
  4. has stockfish_analysis.move_evaluations — needed for engine-mate
                                                + moment context
  5. losses-and-draws — what voice regen actually processes (wins skip)

Usage (inside the backend container):
    python scripts/game_coverage_audit.py
"""

import asyncio
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


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    games_total = await db.games.count_documents({})
    analyses_total = await db.game_analyses.count_documents({})
    with_v5 = await db.game_analyses.count_documents(
        {"decryption_v5_data": {"$exists": True, "$ne": []}}
    )
    with_move_evals = await db.game_analyses.count_documents(
        {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}}
    )
    with_truth = await db.game_analyses.count_documents(
        {"truth_line": {"$exists": True, "$ne": None}}
    )
    with_decryption_block = await db.game_analyses.count_documents(
        {"decryption_block": {"$exists": True, "$ne": None}}
    )
    with_moments = await db.game_analyses.count_documents(
        {"decryption_block.moments.0": {"$exists": True}}
    )
    with_flagged = await db.game_analyses.count_documents(
        {"decryption_block.moments.needs_review": True}
    )

    # Win/loss/draw breakdown across analyzed games (need to join games)
    wins = losses = draws = unknown_result = 0
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": []}},
        {"_id": 0, "game_id": 1},
    ):
        gid = ga.get("game_id")
        g = await db.games.find_one(
            {"game_id": gid},
            {"_id": 0, "user_color": 1, "result": 1},
        )
        if not g:
            unknown_result += 1
            continue
        result = g.get("result") or "*"
        uc = (g.get("user_color") or "").lower()
        if (uc == "white" and result == "1-0") or (uc == "black" and result == "0-1"):
            wins += 1
        elif result in ("1/2-1/2", "1/2", "draw"):
            draws += 1
        elif result in ("1-0", "0-1"):
            losses += 1
        else:
            unknown_result += 1

    total_v5 = wins + losses + draws + unknown_result

    # Games that will be processed by voice regen (i.e., not wins).
    voice_processable = losses + draws + unknown_result

    # Total moments + flagged moments across all analyses.
    total_moments = 0
    flagged_moments = 0
    async for ga in db.game_analyses.find(
        {"decryption_block.moments": {"$exists": True}},
        {"_id": 0, "decryption_block.moments": 1},
    ):
        moments = ((ga.get("decryption_block") or {}).get("moments") or [])
        total_moments += len(moments)
        flagged_moments += sum(1 for m in moments if m.get("needs_review"))

    print("=" * 70)
    print("GAME COVERAGE AUDIT")
    print("=" * 70)
    print(f"  games (collection):                       {games_total}")
    print(f"  game_analyses (collection):               {analyses_total}")
    print(f"  └─ with stockfish_analysis.move_evals:    {with_move_evals}")
    print(f"  └─ with decryption_v5_data:               {with_v5}  ← batch script processes these")
    print(f"  └─ with truth_line set:                   {with_truth}")
    print(f"  └─ with decryption_block set:             {with_decryption_block}")
    print(f"  └─ with at least one moment:              {with_moments}")
    print(f"  └─ with at least one flagged moment:      {with_flagged}")
    print()
    print("V5-enabled breakdown by result:")
    print(f"  wins (skipped — voice for losses only):   {wins}")
    print(f"  losses:                                   {losses}")
    print(f"  draws:                                    {draws}")
    print(f"  unknown / other:                          {unknown_result}")
    print(f"  voice-processable (losses+draws+other):   {voice_processable}")
    print()
    print(f"  total moments across DB:                  {total_moments}")
    print(f"  flagged moments (queue size):             {flagged_moments}")
    print("=" * 70)

    # Spot the gap.
    gap_no_analysis = games_total - analyses_total
    gap_no_v5 = analyses_total - with_v5
    if gap_no_analysis > 0 or gap_no_v5 > 0:
        print()
        print("GAPS:")
        if gap_no_analysis > 0:
            print(f"  {gap_no_analysis} game(s) have no Stockfish analysis yet")
            print(f"     (still in analysis_queue or never queued).")
        if gap_no_v5 > 0:
            print(f"  {gap_no_v5} analyzed game(s) have no decryption_v5_data")
            print(f"     (older imports — pre-V5 schema, or V5 generation failed).")
            print(f"     Re-running V5 generation on these would expand the queue.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
