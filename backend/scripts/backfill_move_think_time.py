"""Put per-ply think-time on analyses that were written without it.

attach_move_times has always run, but in PHASE 6 -- after the analysis
document is written -- so the mutation fed the thinking score and was then
discarded. Measured 2026-10-18: 0 of 19,896 analyses carried
`time_spent_seconds`, while 12,047 games already had the game-level
`move_time_stats` computed from the same clocks.

The clocks are in the PGN, so this is recomputable with no engine work.
Uses move_time_analyzer, which is the only module allowed to parse %clk
(feedback_single_source_of_truth) -- do not add a second parser here.

    python scripts/backfill_move_think_time.py --dry-run
    python scripts/backfill_move_think_time.py --limit 500
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from services.move_time_analyzer import attach_move_times


async def main(args):
    db = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    )[os.environ.get("DB_NAME", "chess_coach")]

    q = {"stockfish_analysis.move_evaluations.0": {"$exists": True}}
    if not args.force:
        q["stockfish_analysis.move_evaluations.time_spent_seconds"] = {
            "$exists": False}

    cur = db.game_analyses.find(
        q, {"_id": 0, "game_id": 1, "user_id": 1,
            "stockfish_analysis.move_evaluations": 1})
    if args.limit:
        cur = cur.limit(args.limit)

    seen = timed = no_clock = no_game = written = 0
    moves_timed = 0
    async for a in cur:
        seen += 1
        g = await db.games.find_one(
            {"game_id": a["game_id"]},
            {"_id": 0, "pgn": 1, "user_color": 1, "time_control": 1})
        if not g or not g.get("pgn"):
            no_game += 1
            continue
        evs = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        n = attach_move_times(g["pgn"], g.get("user_color") or "white",
                              g.get("time_control"), evs)
        if not n:
            no_clock += 1
            continue
        timed += 1
        moves_timed += n
        if not args.dry_run:
            await db.game_analyses.update_one(
                {"game_id": a["game_id"], "user_id": a.get("user_id")},
                {"$set": {"stockfish_analysis.move_evaluations": evs}},
            )
            written += 1
        if seen % 500 == 0:
            print(f"  ... {seen} seen, {timed} timed", flush=True)

    print(f"\n  analyses seen            {seen}")
    print(f"  got think-times          {timed}")
    print(f"  moves timed              {moves_timed}")
    print(f"  PGN had no usable clock  {no_clock}")
    print(f"  game row missing/no pgn  {no_game}")
    print(f"  written                  {written}"
          f"{'  (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="redo analyses that already have times")
    asyncio.run(main(p.parse_args()))
