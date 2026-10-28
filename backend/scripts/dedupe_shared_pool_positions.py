"""Remove the second copy of a position from the shared puzzle pools.

Both copies of a duplicated import were mined for puzzles. When the duplicate
games were removed (2026-10-19 and 2026-10-27), repair_duplicate_game_references.py
repointed the dropped copy's `community_puzzles` and
`community_training_positions` rows at the kept game, so the same game and
position is now listed more than once: 286 puzzle groups and 4,357 training
position groups (4,704 extra rows), measured 2026-10-28. A player can be
served the same puzzle twice.

Rule (Mohit approved 2026-10-28): keep every copy anyone has played, and keep
the oldest copy when nobody has; archive then delete the rest. "Played" is an
on-document `attempts` count, a `puzzle_attempts.puzzle_id` row or a
`training_solve_attempts.position_id` row. A scan of every collection on
2026-10-28 found no other reference to these ids. Only groups whose game is a
duplicate-import keeper are touched: that is the defect, nothing else.

  docker exec -i chess-coach-backend python -m scripts.dedupe_shared_pool_positions            # dry run
  docker exec -i chess-coach-backend python -m scripts.dedupe_shared_pool_positions --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

ARCHIVE = "community_pool_duplicates_archive"
# (collection, how a row is referenced by attempts)
POOLS = (("community_puzzles", "_id"), ("community_training_positions", "position_id"))


def ref_of(doc: dict, key: str) -> str:
    return str(doc.get(key)) if doc.get(key) is not None else ""


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print("mode:", "APPLY" if args.apply else "DRY RUN (nothing is written)")
    kept_games = list({r["kept_game_id"] async for r in db.games_duplicates_archive.find(
        {}, {"_id": 0, "kept_game_id": 1}) if r.get("kept_game_id")})

    for coll, key in POOLS:
        groups = await db[coll].aggregate([
            {"$match": {"source_game_id": {"$in": kept_games}}},
            {"$group": {"_id": {"g": "$source_game_id", "fen": "$fen", "mv": "$move_number"},
                        "n": {"$sum": 1}, "oids": {"$push": "$_id"}}},
            {"$match": {"n": {"$gt": 1}}},
        ], allowDiskUse=True).to_list(None)
        oids = [o for g in groups for o in g["oids"]]
        docs = {d["_id"]: d async for d in db[coll].find({"_id": {"$in": oids}})}
        refs = [ref_of(d, key) for d in docs.values() if ref_of(d, key)]
        played = set(await db.puzzle_attempts.distinct("puzzle_id", {"puzzle_id": {"$in": refs}}))
        played |= set(await db.training_solve_attempts.distinct("position_id", {"position_id": {"$in": refs}}))

        drop, kept_played = [], 0
        for g in groups:
            rows = sorted((docs[o] for o in g["oids"] if o in docs), key=lambda d: d["_id"])
            was_played = [d for d in rows if (d.get("attempts") or 0) > 0 or ref_of(d, key) in played]
            keep = was_played or rows[:1]
            kept_played += len(was_played)
            keep_ids = {d["_id"] for d in keep}
            drop += [(d, rows[0] if not was_played else was_played[0]) for d in rows if d["_id"] not in keep_ids]

        print(f"\n{coll}: groups {len(groups):,}, copies kept because played {kept_played:,}, "
              f"copies to archive and delete {len(drop):,}")
        if args.apply and drop:
            now = datetime.now(timezone.utc).isoformat()
            for start in range(0, len(drop), 500):
                chunk = drop[start:start + 500]
                await db[ARCHIVE].insert_many([
                    {"archived_at": now, "collection": coll, "reason": "same_game_and_position",
                     "kept": keeper["_id"], "doc": doc} for doc, keeper in chunk], ordered=False)
                await db[coll].delete_many({"_id": {"$in": [doc["_id"] for doc, _ in chunk]}})
            left = await db[coll].aggregate([
                {"$match": {"source_game_id": {"$in": kept_games}}},
                {"$group": {"_id": {"g": "$source_game_id", "fen": "$fen", "mv": "$move_number"}, "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}}, {"$count": "groups"}], allowDiskUse=True).to_list(None)
            print(f"   done; groups still listed more than once: {left[0]['groups'] if left else 0:,}")
    if args.apply:
        print(f"\n{ARCHIVE} holds {await db[ARCHIVE].count_documents({}):,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
