"""What did the correction verifier actually add to a review?

A render time with no baseline says nothing. Same games, rendered twice: once
with the verifier live, once with it stubbed out, so the difference is the
engine check and nothing else.
"""
import asyncio
import os
import statistics
import sys
import time

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

import services.caption_concept_corrections as corrections
from services.game_decryption_v5_service import generate_game_decryption_v5

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6


async def render(db, g, evs):
    t0 = time.time()
    try:
        await generate_game_decryption_v5(
            g["pgn"], g.get("user_color") or "white", evs,
            g.get("user_id") or "u", db, game_id=g["game_id"],
            persist_learning_side_effects=False, allow_llm_polish=False)
    except Exception as exc:
        print("   render failed: %s" % exc)
        return None
    return time.time() - t0


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N}},
        {"$project": {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1, "user_color": 1}},
    ]):
        games.append(g)

    prepared = []
    for g in games:
        a = await db.game_analyses.find_one(
            {"game_id": g["game_id"]},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1})
        evs = ((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        if evs:
            prepared.append((g, evs))

    real = corrections.verify_corrections
    on, off = [], []

    for g, evs in prepared:
        corrections.verify_corrections = real
        t_on = await render(db, g, evs)
        corrections.verify_corrections = lambda *a, **k: {}
        t_off = await render(db, g, evs)
        corrections.verify_corrections = real
        if t_on is None or t_off is None:
            continue
        on.append(t_on)
        off.append(t_off)
        print("  %s  verifier on %5.1fs   off %5.1fs   added %+5.1fs" % (
            g["game_id"][:10], t_on, t_off, t_on - t_off))

    if on:
        print("\n%d games" % len(on))
        print("  median with verifier : %.1fs" % statistics.median(on))
        print("  median without       : %.1fs" % statistics.median(off))
        print("  median cost of the check: %+.1fs" % (
            statistics.median(on) - statistics.median(off)))
        print("  worst single game added : %+.1fs" % max(a - b for a, b in zip(on, off)))


asyncio.run(main())
