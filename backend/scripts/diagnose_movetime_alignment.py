"""Quick diagnostic: for N games with move_time_stats, compare PGN-parsed
ply count to game_analyses move_evaluations length. Tells us whether
the critical-move detection is failing because of length mismatches.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.move_time_analyzer import _extract_clk_per_ply  # noqa: E402


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    print(f"DB: {db_name}\n")

    cursor = db.games.find(
        {"is_analyzed": True, "move_time_stats": {"$exists": True}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "move_time_stats": 1},
    ).limit(20)

    matches = mismatches = no_evals = 0
    samples = []
    async for g in cursor:
        gid = g["game_id"]
        pgn = g.get("pgn") or ""
        clks = _extract_clk_per_ply(pgn)
        n_plies = len(clks)

        a = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        )
        evals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        n_evals = len(evals)

        equal = n_plies == n_evals
        if not evals:
            no_evals += 1
        elif equal:
            matches += 1
        else:
            mismatches += 1

        if len(samples) < 10:
            crit = g["move_time_stats"].get("critical_move_time_s")
            samples.append(
                f"  {gid}: clk_plies={n_plies} sf_evals={n_evals} "
                f"equal={equal} crit_time={crit}"
            )

    for line in samples:
        print(line)
    print(f"\nMatches:    {matches}")
    print(f"Mismatches: {mismatches}")
    print(f"No evals:   {no_evals}")


if __name__ == "__main__":
    asyncio.run(main())
