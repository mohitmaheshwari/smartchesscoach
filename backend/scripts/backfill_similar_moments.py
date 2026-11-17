"""Tag already-analysed games with similar moments (services/similar_moments.py).

Run in a THROWAWAY container (never chess-coach-backend: Maia is heavy), with
the backend's volumes for the Maia model:
  docker run -d --rm --cpus=1 --volumes-from chess-coach-backend \
    --network container:chess-coach-backend -e MONGO_URL -e DB_NAME -e MAIA2_MODEL_PATH \
    <backend image> python -u scripts/backfill_similar_moments.py [--limit N]

Strongest games first (the pool only needs players stronger than the learner),
public platforms only, academy children never, games already at VERSION
skipped, so it can be stopped and restarted. Writes only `similar_moments`
rows and games.similar_moments_version; undo = drop those rows and unset the
field (the rows are new).
"""
import os
import sys
import time

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.similar_moments import PUBLIC_PLATFORMS, VERSION, excluded_users, tag_game_moments_sync  # noqa: E402

FIELDS = {"_id": 0, "fen_before": 1, "move_uci": 1, "cp_loss": 1, "phase": 1, "move_number": 1,
          "destination_safety_exact.outcome": 1}


def main(argv):
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    db.similar_moments.create_index([("key", 1), ("rating", -1), ("temptation", -1)])
    children = excluded_users(db)
    # Read the whole list first: tagging takes seconds a game, and a cursor
    # held open across that dies (CursorNotFound killed the first run,
    # 2026-11-17, after 112 games).
    games = list(db.games.find(
        {"is_analyzed": True, "platform": {"$in": list(PUBLIC_PLATFORMS)}, "user_rating": {"$gt": 0},
         "similar_moments_version": {"$ne": VERSION}, "user_id": {"$nin": list(children)}},
        {"_id": 0, "game_id": 1, "user_id": 1, "platform": 1, "user_rating": 1},
    ).sort("user_rating", -1))
    print(f"games to tag {len(games)}", flush=True)
    done = stored = 0
    t0 = time.time()
    for game in games:
        obs = list(db.move_observations.find({"user_id": game["user_id"], "game_id": game["game_id"]}, FIELDS))
        if obs:
            stored += tag_game_moments_sync(db, game, obs)
        done += 1
        if done % 25 == 0:
            print(f"games {done} | moments {stored} | rating now {game['user_rating']} | {round(time.time() - t0)}s", flush=True)
        if limit and done >= limit:
            break
    print(f"DONE games {done} | moments {stored} | {round(time.time() - t0)}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
