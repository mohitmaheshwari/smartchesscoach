#!/usr/bin/env python3
"""
Remove duplicate Play-with-Coach game rows and make the race impossible (2026-08-24).

THE BUG
-------
`_promote_session_to_game` (routes/coach_play.py) guards itself:

    existing = await db.games.find_one({"coach_session_id": session_id})
    if existing:
        return

The insert does write coach_session_id, so the logic is right in isolation --
but there is an `await` between the read and the write, and THREE call sites
(coach_play.py:1222, :7832, :9770). Under concurrency every caller passes the
check before any of them inserts.

Observed: one session promoted NINE times inside 122ms
(06:38:13.870 .. 06:38:13.992), and another three times. Both collections were
hit, because the function inserts into games AND game_analyses.

Cohort impact is small -- 10 redundant rows each, 2 users, 0.1% of games -- but
for the worst-affected user their ENTIRE history is one game counted nine
times, so every per-game rate divides by 9 instead of 1.

THE FIX
-------
1. Delete redundant rows, keeping the earliest _id per (user_id, game_id).
2. Add a PARTIAL UNIQUE index on games.coach_session_id.

   Partial, so the 13,000+ imported chess.com/lichess games -- which have no
   coach_session_id -- are untouched. This makes the race unwinnable at the
   storage layer regardless of how many call sites race.

   NO unique index is added on game_analyses. Three separate paths insert
   there (journey_service.py:821, routes/analysis.py:809,
   coach_play.py:7541), and a constraint could break re-analysis. Its
   duplicates are cleaned, and the games constraint removes the source.

3. The application must also stop treating a lost race as an error -- see the
   DuplicateKeyError handler added to _promote_session_to_game in the same
   commit. Losing the race means the game IS promoted, which is success.

SAFETY
  * dry run by default
  * backs up every row it will delete, to a timestamped collection
  * keeps the earliest _id -- deterministic, and that row is the one whose
    game_analyses siblings were written first
  * re-running is a no-op

USAGE
    python scripts/fix_duplicate_coach_games.py            # dry run
    python scripts/fix_duplicate_coach_games.py --apply
"""
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient  # noqa: E402
from pymongo.errors import DuplicateKeyError, OperationFailure  # noqa: E402

INDEX_NAME = "coach_session_id_unique"


def find_dups(coll):
    """(user_id, game_id) groups with more than one row, oldest _id first."""
    out = []
    for g in coll.aggregate([
        {"$group": {"_id": {"u": "$user_id", "g": "$game_id"},
                    "ids": {"$push": "$_id"}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
    ], allowDiskUse=True):
        ids = sorted(g["ids"])          # ObjectId sorts by creation time
        out.append((g["_id"]["u"], g["_id"]["g"], ids[0], ids[1:]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")]

    plan = {c: find_dups(db[c]) for c in ("games", "game_analyses")}

    print(f"=== {'APPLY' if args.apply else 'DRY RUN'} ===")
    total_del = 0
    for coll, groups in plan.items():
        n = sum(len(d) for _, _, _, d in groups)
        total_del += n
        print(f"\n{coll}: {len(groups)} duplicated (user,game_id) pairs, "
              f"{n} rows to delete, {db[coll].count_documents({})} rows now")
        for u, g, keep, drop in groups:
            print(f"   user={u[:16]} game={str(g)[:26]} keep={keep} drop={len(drop)}")

    if not args.apply:
        print(f"\nwould delete {total_del} rows and create index "
              f"games.{INDEX_NAME}. Re-run with --apply.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    deleted = 0
    for coll, groups in plan.items():
        drop_ids = [i for _, _, _, d in groups for i in d]
        if not drop_ids:
            continue
        backup = f"{coll}_backup_dupcoach_{stamp}"
        docs = list(db[coll].find({"_id": {"$in": drop_ids}}))
        db[backup].insert_many(docs)
        res = db[coll].delete_many({"_id": {"$in": drop_ids}})
        deleted += res.deleted_count
        print(f"\n{coll}: backed up {len(docs)} -> {backup}, deleted {res.deleted_count}")
        if res.deleted_count != len(drop_ids):
            print(f"  FAIL: expected {len(drop_ids)} deletions")
            sys.exit(1)

    # The constraint. Build AFTER cleanup -- if duplicates remained this throws,
    # which is a useful proof that the cleanup actually worked.
    try:
        db.games.create_index(
            "coach_session_id", name=INDEX_NAME, unique=True,
            partialFilterExpression={"coach_session_id": {"$exists": True}},
        )
        print(f"\ncreated unique partial index games.{INDEX_NAME}")
    except (DuplicateKeyError, OperationFailure) as e:
        print(f"\nFAIL: index build rejected -- duplicates remain: {e}")
        sys.exit(1)

    print(f"\ndeleted {deleted} rows total")


if __name__ == "__main__":
    main()
