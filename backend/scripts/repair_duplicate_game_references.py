"""Clean up the rows that still point at games removed as duplicate imports.

`migrate_platform_game_id.py` removed 1,543 duplicate `games` rows and their
`game_analyses`/`analysis_queue` rows, but 28 collections reference a game and
six of them were left dangling -- 70,818 rows (measured 2026-10-19). So the
count inflation the de-duplication was meant to fix was still there: the
duplicate OBSERVATIONS survived their game.

Two different repairs, chosen by measurement rather than by taste. For each
(dropped, kept) pair we asked whether the KEPT game already has rows:

  DELETE  the orphan is a true duplicate -- the keeper carries its own copy.
          move_observations, user_pattern_events, user_teaching_memory and
          thinking_scores had ZERO pairs where only the dropped id had rows,
          so nothing here is unique. move_observations also holds a UNIQUE
          index on (game_id, move_number), which means repointing would
          violate it: delete is the only correct move.

  REPOINT the keeper has nothing, so deleting would destroy data. This is
          almost entirely community_puzzles (4,365 rows) plus
          community_training_positions (121). These are SHARED pools, served
          to other users, and `source_game_id` pointing at the kept copy of
          the same game is simply the true statement. Neither collection has
          a unique index, so a repoint cannot collide.

Repointing can leave two rows describing the same position; this script
REPORTS those and does not delete them, because a community puzzle another
user has been served is not something to remove as a side effect of a
de-duplication.

Deleted rows are archived first -- backups are deferred until launch.

    python scripts/repair_duplicate_game_references.py            # dry run
    python scripts/repair_duplicate_game_references.py --apply
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

ARCHIVE = "games_duplicates_archive"
REF_ARCHIVE = "games_duplicates_archive_refs"

# Per-game derived records. The keeper regenerates these from its own
# analysis, so an orphan copy is pure duplication.
DELETE_COLLECTIONS = [
    ("move_observations", "game_id"),
    ("user_pattern_events", "game_id"),
    ("user_teaching_memory", "game_id"),
    ("thinking_scores", "game_id"),
    # Added 2026-10-27 for the second clean-up: one row per game each.
    ("game_tag_index", "game_id"),
    ("game_headlines", "game_id"),
]

# Where only the dropped copy has a row, move it to the keeper rather than
# skip it. A headline is one model call per game, ever (Mohit, 2026-10-23), so
# dropping the only one would leave the keeper untitled for good. Both
# collections are unique on game_id; the keeper has no row here, so a move
# cannot collide.
MOVE_WHEN_ONLY_COPY = {"game_tag_index", "game_headlines"}

# Shared, user-facing pools. Never deleted here.
REPOINT_COLLECTIONS = [
    ("community_puzzles", "source_game_id"),
    ("community_training_positions", "source_game_id"),
]

BATCH = 500


async def ids_with_rows(db, coll: str, field: str, ids: list) -> dict:
    """{id: row count} in one aggregation, not two queries per pair."""
    found = {}
    pipeline = [{"$match": {field: {"$in": ids}}},
                {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}]
    async for row in db[coll].aggregate(pipeline, allowDiskUse=True):
        found[row["_id"]] = row["n"]
    return found


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--db", default=os.environ.get("DB_NAME", "chess_coach"))
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[args.db]
    mode = "APPLY" if args.apply else "DRY RUN (nothing is written)"
    print(f"database: {args.db}   mode: {mode}\n")

    pairs = []
    async for rec in db[ARCHIVE].find({}, {"_id": 0, "game.game_id": 1, "kept_game_id": 1}):
        dropped = (rec.get("game") or {}).get("game_id")
        kept = rec.get("kept_game_id")
        if dropped and kept:
            pairs.append((dropped, kept))
    if not pairs:
        print(f"{ARCHIVE} holds no dropped/kept pairs; nothing to repair.")
        return 0
    # A game kept in one clean-up can be dropped in a later one (2026-10-19,
    # then 2026-10-27). Follow the chain so nothing is repointed at a game
    # that no longer exists.
    kept_of = dict(pairs)

    def final_keeper(game_id: str) -> str:
        seen = set()
        while game_id in kept_of and game_id not in seen:
            seen.add(game_id)
            game_id = kept_of[game_id]
        return game_id

    chained = sum(1 for _, kept in pairs if kept in kept_of)
    pairs = [(dropped, final_keeper(kept)) for dropped, kept in pairs]
    if chained:
        print(f"keepers that were themselves dropped later: {chained:,} (followed to the final keeper)")

    all_ids = sorted({x for pair in pairs for x in pair})
    print(f"dropped/kept pairs: {len(pairs):,}\n")

    existing = set(await db.list_collection_names())
    deleted_total = repointed_total = 0

    # ----------------------------------------------------------- deletes
    for coll, field in DELETE_COLLECTIONS:
        if coll not in existing:
            print(f"{coll}: no such collection"); continue
        counts = await ids_with_rows(db, coll, field, all_ids)

        safe, unsafe = [], []
        for dropped, kept in pairs:
            if not counts.get(dropped):
                continue
            (safe if counts.get(kept) else unsafe).append((dropped, kept))

        rows = sum(counts.get(d, 0) for d, _ in safe)
        print(f"{coll}.{field}")
        print(f"   orphan rows on pairs whose keeper ALSO has rows: {rows:,} "
              f"({len(safe):,} pairs) -> delete")
        if unsafe and coll in MOVE_WHEN_ONLY_COPY:
            print(f"   {len(unsafe):,} pairs where only the dropped id has a row -> move to keeper")
            if args.apply:
                for dropped, kept in unsafe:
                    # A keeper with two dropped copies gets the first copy's
                    # row; the second is then a true duplicate.
                    if await db[coll].count_documents({field: kept}, limit=1):
                        safe.append((dropped, kept))
                        continue
                    result = await db[coll].update_many({field: dropped}, {"$set": {field: kept}})
                    repointed_total += result.modified_count
        elif unsafe:
            # The measurement said this set is empty. If it ever is not, the
            # rows are the only copy and deleting them would lose data.
            print(f"   !! {len(unsafe):,} pairs where ONLY the dropped id has rows "
                  f"-> SKIPPED, needs a repoint decision")

        rows = sum(counts.get(d, 0) for d, _ in safe)
        if args.apply and safe:
            for start in range(0, len(safe), BATCH):
                chunk = [d for d, _ in safe[start:start + BATCH]]
                docs = [doc async for doc in db[coll].find({field: {"$in": chunk}})]
                if docs:
                    await db[REF_ARCHIVE].insert_many(
                        [{"archived_at": datetime.now(timezone.utc).isoformat(),
                          "collection": coll, "field": field, "doc": doc}
                         for doc in docs], ordered=False)
                result = await db[coll].delete_many({field: {"$in": chunk}})
                deleted_total += result.deleted_count
            print(f"   deleted: {rows:,} (archived to {REF_ARCHIVE})")
        print()

    # ---------------------------------------------------------- repoints
    for coll, field in REPOINT_COLLECTIONS:
        if coll not in existing:
            print(f"{coll}: no such collection"); continue
        counts = await ids_with_rows(db, coll, field, all_ids)
        todo = [(d, k) for d, k in pairs if counts.get(d)]
        rows = sum(counts.get(d, 0) for d, _ in todo)
        print(f"{coll}.{field}")
        print(f"   rows pointing at a deleted game: {rows:,} ({len(todo):,} pairs) -> repoint to keeper")

        if args.apply:
            for dropped, kept in todo:
                result = await db[coll].update_many({field: dropped}, {"$set": {field: kept}})
                repointed_total += result.modified_count
            print(f"   repointed: {repointed_total:,}")

        # Report, never delete: same game + same position now listed twice.
        pipeline = [
            {"$match": {field: {"$in": [k for _, k in todo]}}},
            {"$group": {"_id": {"g": f"${field}", "fen": "$fen",
                                "mv": "$move_number"}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
            {"$count": "groups"},
        ]
        dupes = [row async for row in db[coll].aggregate(pipeline, allowDiskUse=True)]
        n = dupes[0]["groups"] if dupes else 0
        print(f"   same game+position listed more than once {'after' if args.apply else 'already'}: "
              f"{n:,} groups (reported only, not deleted)\n")

    # ----------------------------------------------------------- verify
    print("=== remaining references to deleted games ===")
    for coll, field in DELETE_COLLECTIONS + REPOINT_COLLECTIONS:
        if coll not in existing:
            continue
        left = await db[coll].count_documents({field: {"$in": [d for d, _ in pairs]}})
        print(f"   {coll:<32} {left:>7}")

    if args.apply:
        print(f"\ndeleted {deleted_total:,} rows, repointed {repointed_total:,} rows")
        print(f"{REF_ARCHIVE} now holds {await db[REF_ARCHIVE].count_documents({}):,} rows")
    else:
        print("\nnothing was written. re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
