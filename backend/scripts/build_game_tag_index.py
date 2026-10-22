"""Fill game_tag_index from the tags already stored with each game's story.

game_tag_index (services/game_tags.py) is what tag counts and searches read:
one small document per game. New stories write it as they are stored; this
fills it for every game whose story was stored before it existed.

Reads game_analyses ONCE, projecting only the story's tags, in small batches.

  docker exec -i chess-coach-backend python -m scripts.build_game_tag_index
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from pymongo import UpdateOne  # noqa: E402

from services.game_tags import TAG_INDEX_COLLECTION, ensure_game_tag_indexes, tag_index_doc  # noqa: E402


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await ensure_game_tag_indexes(db)
    index = db[TAG_INDEX_COLLECTION]
    ops, written, start = [], 0, time.time()
    cursor = db.game_analyses.find(
        {"game_story.tags": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1, "game_story.tags": 1},
        batch_size=200,
    )
    async for a in cursor:
        tags = (a.get("game_story") or {}).get("tags")
        if not a.get("game_id") or not tags:
            continue
        doc = tag_index_doc(a["game_id"], a.get("user_id"), tags)
        ops.append(UpdateOne({"game_id": a["game_id"]}, {"$set": doc}, upsert=True))
        if len(ops) >= 500:
            await index.bulk_write(ops, ordered=False)
            written += len(ops)
            ops = []
            print(f"  {written} written ({written / max(1e-6, time.time() - start):.0f}/s)", flush=True)
    if ops:
        await index.bulk_write(ops, ordered=False)
        written += len(ops)
    print(f"done: {written} tag records, {await index.count_documents({})} in {TAG_INDEX_COLLECTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
