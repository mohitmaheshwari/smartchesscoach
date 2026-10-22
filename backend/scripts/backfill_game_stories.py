"""Build and store the story, ledger, plan and tags for every analysed game.

Game tags (services/game_tags.py) are only searchable once they are stored
on game_analyses.game_tags. New analyses store them as they run; this fills
in every game analysed before, through the very loader the app uses
(services.game_story.story_for_game), so a backfilled story and a live one
cannot differ.

Only games whose stored story is older than the current schema are touched.
Derived data only: it never changes an analysis, a move or an observation.

Run AFTER the code is deployed (data must never be newer than its reader).

  docker exec -i chess-coach-backend python -m scripts.backfill_game_stories            # dry run
  docker exec -i chess-coach-backend python -m scripts.backfill_game_stories --apply
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

from services.game_story import SCHEMA_VERSION, story_for_game  # noqa: E402
from services.game_tags import ensure_game_tag_indexes  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = every game")
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await ensure_game_tag_indexes(db)

    stale = db.game_analyses.find(
        {"game_story.schema_version": {"$ne": SCHEMA_VERSION}},
        {"_id": 0, "game_id": 1},
    )
    if args.limit:
        stale = stale.limit(args.limit)
    game_ids = [a["game_id"] async for a in stale if a.get("game_id")]
    print(f"games whose stored story is not {SCHEMA_VERSION}: {len(game_ids)}", flush=True)

    counts: collections.Counter = collections.Counter()
    tag_counts: collections.Counter = collections.Counter()
    start = time.time()
    for index, game_id in enumerate(game_ids, 1):
        game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
        if not game:
            counts["no game row"] += 1
            continue
        try:
            story = await story_for_game(db, game, persist=args.apply)
        except Exception as exc:  # one bad game must not stop the run
            counts[f"error {type(exc).__name__}"] += 1
            continue
        if story is None:
            counts["not analysed"] += 1
            continue
        counts["built"] += 1
        if story.get("plan") is None:
            counts["built without a plan"] += 1
        for tag in (story.get("tags") or {}).get("ids") or []:
            if tag.startswith("user_"):
                tag_counts[tag] += 1
        if index % 500 == 0:
            rate = index / max(1e-6, time.time() - start)
            print(f"  {index}/{len(game_ids)}  {rate:.1f} games/s", flush=True)

    mode = "APPLIED (stories and tags written)" if args.apply else "DRY RUN (nothing written)"
    print(f"=== {mode} ===")
    for key, value in counts.most_common():
        print(f"  {key:<32} {value}")
    print("  most common player tags:")
    for tag, value in tag_counts.most_common(12):
        print(f"    {tag:<44} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
