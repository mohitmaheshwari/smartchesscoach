"""Does a concept sentence actually reach a rendered game review?

Rendered through generate_game_decryption_v5 -- the real path a player's
review takes -- never a hand-rolled harness, because a harness proves the
function works and not that the product says anything.
"""
import asyncio
import collections
import os
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

from services.game_decryption_v5_service import generate_game_decryption_v5

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N}},
        {"$project": {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1, "user_color": 1}},
    ]):
        games.append(g)

    seen = collections.Counter()
    games_with = 0
    shown = 0
    for g in games:
        a = await db.game_analyses.find_one(
            {"game_id": g["game_id"]},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1})
        evs = ((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not evs:
            continue
        try:
            out = await generate_game_decryption_v5(
                g["pgn"], g.get("user_color") or "white", evs,
                g.get("user_id") or "u", db, game_id=g["game_id"],
                persist_learning_side_effects=False, allow_llm_polish=False)
        except Exception as exc:
            print("  render failed for %s: %s: %s" % (g["game_id"][:10], type(exc).__name__, exc))
            continue
        moves = out if isinstance(out, list) else ((out or {}).get("moves") or [])
        hits = [m for m in moves if isinstance(m, dict) and m.get("concept_sentence")]
        if hits:
            games_with += 1
        print("  %s: %d moves, %d carry a concept sentence" % (g["game_id"][:10], len(moves), len(hits)))
        for m in hits:
            cs = m["concept_sentence"]
            seen[cs["skill_id"]] += 1
            if shown < 6:
                shown += 1
                print("      move %s %s  [%s / %s]" % (
                    m.get("move_number"), m.get("move_san") or m.get("move"),
                    cs["skill_id"], cs["outcome"]))
                print("        %s" % cs["text"])

    print("\n%d of %d rendered games carry at least one concept sentence" % (games_with, len(games)))
    print("by detector:", dict(seen))


asyncio.run(main())
