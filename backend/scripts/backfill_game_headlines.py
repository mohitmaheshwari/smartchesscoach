"""Write each analysed game's title and teaching line, one model call per game.

The games list and the review page show a game's title once it is saved
(services/game_headline.py). This writes it for games analysed before titles
existed, so the list is not empty. A game whose headline already carries
`llm_used` is skipped: Mohit, 2026-10-23, "once LLM is used, don't make
another call". So this is resumable -- a restart only does what is left.

Headlines written earlier on 2026-10-23, before `llm_used` existed, are marked
first, so those games are not asked again either.

  docker exec -i chess-coach-backend python -m scripts.backfill_game_headlines            # count only
  docker exec -i chess-coach-backend python -m scripts.backfill_game_headlines --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
import time

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from services.game_headline import COLLECTION, headline_for_game  # noqa: E402
from services.game_story import story_for_game  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    headlines = db[COLLECTION]
    await headlines.create_index("game_id", unique=True)

    # Headlines written before llm_used existed: the model was used for them.
    marked = await headlines.update_many(
        {"llm_used": {"$exists": False}, "$or": [
            {"source": "llm"},
            {"source": "rules", "reason": {"$nin": [None, "llm_error", "disabled", "error"]}},
        ]},
        {"$set": {"llm_used": True}},
    ) if args.apply else None
    if marked is not None:
        print(f"marked earlier headlines as used: {marked.modified_count}", flush=True)

    done = {h["game_id"] async for h in headlines.find({"llm_used": True}, {"_id": 0, "game_id": 1})}
    todo = [a["game_id"] async for a in db.game_analyses.find(
        {"game_story.plan": {"$ne": None}}, {"_id": 0, "game_id": 1}) if a.get("game_id") not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"games with a story and no headline from the model yet: {len(todo)}", flush=True)
    if not args.apply:
        return 0

    counts: collections.Counter = collections.Counter()
    gate = asyncio.Semaphore(max(1, args.concurrency))
    start = time.time()

    async def one(game_id: str):
        async with gate:
            game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
            if not game:
                counts["no game row"] += 1
                return
            story = await story_for_game(db, game, persist=False)
            if not story or not story.get("plan"):
                counts["no story"] += 1
                return
            written = await headline_for_game(db, game, story)
            counts[f"{written.get('source')}" + ("" if written.get("llm_used") else " (not used)")] += 1
            n = sum(counts.values())
            if n % 250 == 0:
                print(f"  {n}/{len(todo)}  {n / max(1e-6, time.time() - start):.1f} games/s  {dict(counts)}",
                      flush=True)

    await asyncio.gather(*(one(g) for g in todo))
    print("=== done ===")
    for key, value in counts.most_common():
        print(f"  {key:<24} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
