"""Give every imported game the platform's own id, then make it unique.

Why: dedup keyed on our derived `url` plus a byte-equal `pgn`, and the check
was check-then-act with no index behind it. Two concurrent syncs each passed
the check before either insert landed and both wrote the game. Measured
2026-10-18 on user_8b599930d7ef: 13 of 127 lichess games stored twice, 11 of
the pairs sharing an `imported_at` to the second, and the two copies of
Jl8C0lUw holding PGNs of 880 and 2675 bytes -- one fetched without clocks --
so the `pgn` clause could never have matched them either. Both copies were
analysed, so Stockfish ran twice on one game.

Steps, in this order:
  1. backfill `platform_game_id` from `url`, falling back to the PGN [Site]
  2. report duplicate groups, and with --apply keep the best row and move the
     rest (with their analyses) into `games_duplicates_archive` before
     deleting them -- there is no off-box backup, so the archive is what makes
     this reversible
  3. create the unique partial index, which is the only thing that closes
     the race for good

Run with no flags first: it changes nothing and prints what it would do.

    python scripts/migrate_platform_game_id.py
    python scripts/migrate_platform_game_id.py --apply

Deploy the code BEFORE running this. The index rejects a second insert, which
the new import path handles as "already imported"; the old path would raise.
"""
import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

INDEX_NAME = "games_platform_game_id_unique"
URL_INDEX_NAME = "games_user_url_unique"
# Never copied from a dropped duplicate onto the keeper: they describe one
# copy's own analysis, or its identity.
KEEP_OWN_PREFIXES = ("analysis_", "analyzed_")
KEEP_OWN_FIELDS = {"game_id", "is_analyzed", "pic_evidence", "imported_at", "platform_game_id"}

# Dropped rows are copied here before deletion. There is no off-box backup of
# this database, so a delete with no archive is unrecoverable; with one, the
# migration is a move rather than a destruction.
ARCHIVE = "games_duplicates_archive"

LICHESS_URL = re.compile(r"lichess\.org/(\w+)")
CHESSCOM_URL = re.compile(r"/game/(?:live|daily)/(\d+)")
TRAILING_DIGITS = re.compile(r"/(\d+)/?$")


def platform_game_id_from_row(row: dict) -> str | None:
    """The same identity the import path derives, read back off a stored row.

    Takes `url` first and the PGN [Site] header second, because 749 of 20,774
    rows carry no url (older import paths) but every imported PGN carries a
    Site line.
    """
    platform = (row.get("platform") or "").lower()
    url = row.get("url") or ""
    pgn = row.get("pgn") or ""

    if platform == "lichess":
        match = LICHESS_URL.search(url) or LICHESS_URL.search(pgn)
        return match.group(1) if match else None

    if platform in ("chess.com", "chesscom"):
        for text in (url, pgn):
            match = CHESSCOM_URL.search(text) or TRAILING_DIGITS.search(text.strip())
            if match:
                return match.group(1)
    return None


def rank_row(row: dict, analysed_ids: set) -> tuple:
    """Which copy of a duplicated game to KEEP. Higher is better.

    An analysed copy outranks an unanalysed one so the keeper is the row the
    rest of the database already points at, and a longer PGN outranks a
    shorter one because the long copy is the one that carries [%clk] -- the
    only source of per-move think time.
    """
    return (
        1 if row.get("game_id") in analysed_ids else 0,
        1 if row.get("is_analyzed") else 0,
        len(row.get("pgn") or ""),
        str(row.get("imported_at") or ""),
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the backfill, delete duplicates, build the index")
    parser.add_argument("--db", default=os.environ.get("DB_NAME", "chess_coach"))
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[args.db]
    mode = "APPLY" if args.apply else "DRY RUN (nothing is written)"
    print(f"database: {args.db}   mode: {mode}\n")

    # ---------------------------------------------------- 1. backfill
    total = await db.games.count_documents({})
    print(f"step 1 -- backfill platform_game_id over {total:,} games")

    groups: dict[tuple, list[dict]] = defaultdict(list)
    writes = 0
    unresolved: dict[str, int] = defaultdict(int)
    # Ids are written AFTER step 2. Once the unique index exists (it has since
    # 2026-10-19), writing the id onto the second copy of a game before that
    # copy is archived is a duplicate-key error.
    pending_ids: dict[str, str] = {}

    cursor = db.games.find(
        {}, {"_id": 0, "game_id": 1, "user_id": 1, "platform": 1, "url": 1,
             "pgn": 1, "is_analyzed": 1, "imported_at": 1, "platform_game_id": 1}
    )
    async for row in cursor:
        existing = row.get("platform_game_id")
        derived = existing or platform_game_id_from_row(row)
        if not derived:
            unresolved[row.get("platform") or "(none)"] += 1
            continue
        if not existing:
            writes += 1
            pending_ids[row["game_id"]] = derived
        groups[(row.get("user_id"), row.get("platform"), derived)].append(row)

    print(f"   ids to write : {writes:,}")
    print(f"   already set  : {sum(len(v) for v in groups.values()) - writes:,}")
    if unresolved:
        print("   no id derivable (left uncovered by the index, not guessed):")
        for platform, count in sorted(unresolved.items(), key=lambda kv: -kv[1]):
            print(f"      {platform:<18} {count:,}")

    # ---------------------------------------------------- 2. duplicates
    dupes = {key: rows for key, rows in groups.items() if len(rows) > 1}
    extra = sum(len(rows) - 1 for rows in dupes.values())
    print(f"\nstep 2 -- duplicate groups: {len(dupes):,}  (rows to delete: {extra:,})")

    if dupes:
        analysed_ids = set()
        async for row in db.game_analyses.find({}, {"_id": 0, "game_id": 1}):
            analysed_ids.add(row.get("game_id"))

        by_user: dict[str, int] = defaultdict(int)
        for (user_id, _platform, _gid), rows in dupes.items():
            by_user[user_id] += len(rows) - 1
        print("   worst-affected users:")
        for user_id, count in sorted(by_user.items(), key=lambda kv: -kv[1])[:10]:
            print(f"      {user_id:<24} {count:,} extra rows")

        deleted = 0
        filled: dict[str, int] = defaultdict(int)
        for (user_id, platform, gid), rows in sorted(dupes.items(), key=lambda kv: str(kv[0])):
            rows.sort(key=lambda r: rank_row(r, analysed_ids), reverse=True)
            keeper, drop = rows[0], rows[1:]
            # The kept copy can lack what the dropped one has: 53 copies
            # written by POST /import-games had no url and no ratings, while
            # their twins from the sync did (2026-10-27). Copy over every
            # field the keeper is missing, except the analysis state, which
            # belongs to the copy that was analysed.
            keeper_full = await db.games.find_one({"game_id": keeper["game_id"]}, {"_id": 0}) or {}
            fill = {}
            for row in drop:
                other = await db.games.find_one({"game_id": row["game_id"]}, {"_id": 0}) or {}
                for key, value in other.items():
                    if key not in keeper_full and key not in fill and not key.startswith(KEEP_OWN_PREFIXES) \
                            and key not in KEEP_OWN_FIELDS:
                        fill[key] = value
            for key in fill:
                filled[key] += 1
            if args.apply and fill:
                await db.games.update_one({"game_id": keeper["game_id"]}, {"$set": fill})
            if deleted < 5 or args.apply is False and deleted < 5:
                print(f"      {platform}/{gid} user={user_id}: keep "
                      f"{keeper['game_id'][:8]} (pgn {len(keeper.get('pgn') or '')}b, "
                      f"analysed={keeper['game_id'] in analysed_ids}), "
                      f"drop {', '.join(r['game_id'][:8] for r in drop)}")
            for row in drop:
                deleted += 1
                pending_ids.pop(row["game_id"], None)
                if not args.apply:
                    continue

                game_id = row["game_id"]
                # Archive the whole row, and its analysis, BEFORE removing
                # anything. Read the full document rather than the projection
                # this loop carries, or the archive would be a summary.
                full = await db.games.find_one({"game_id": game_id})
                analyses = [a async for a in db.game_analyses.find({"game_id": game_id})]
                await db[ARCHIVE].insert_one({
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "duplicate_import",
                    "kept_game_id": keeper["game_id"],
                    "platform_game_id": gid,
                    "game": full,
                    "game_analyses": analyses,
                })

                await db.games.delete_one({"game_id": game_id})
                # The dropped row's own analysis/queue rows go with it so
                # nothing is left pointing at a game that no longer exists.
                await db.game_analyses.delete_many({"game_id": game_id})
                await db.analysis_queue.delete_many({"game_id": game_id})
        if filled:
            print("   fields copied onto keepers that lacked them:")
            for key, count in sorted(filled.items(), key=lambda kv: -kv[1]):
                print(f"      {key:<28} {count:,}")
        if args.apply:
            print(f"   rows archived to {ARCHIVE} and deleted: {deleted:,}")
            print(f"   archive now holds: {await db[ARCHIVE].count_documents({}):,} rows")
        else:
            print(f"   rows that would be archived then deleted: {deleted:,}")

    # ------------------------------------------- 1b. ids for the survivors
    print(f"\nstep 1b -- write platform_game_id onto the {len(pending_ids):,} kept rows that lack it")
    if args.apply:
        for game_id, derived in pending_ids.items():
            await db.games.update_one({"game_id": game_id}, {"$set": {"platform_game_id": derived}})

    # ---------------------------------------------------- 3. index
    print(f"\nstep 3 -- unique partial index {INDEX_NAME}")
    existing_names = [ix["name"] async for ix in db.games.list_indexes()]
    if INDEX_NAME in existing_names:
        print("   already present")
    elif not args.apply:
        print("   would create (unique, partial on platform_game_id existing)")
    else:
        await db.games.create_index(
            [("user_id", 1), ("platform", 1), ("platform_game_id", 1)],
            name=INDEX_NAME,
            unique=True,
            partialFilterExpression={"platform_game_id": {"$exists": True}},
        )
        print("   created")

    # The same game by url, which also stops a writer that never sets
    # platform_game_id (a stale backend on another machine, 2026-10-27).
    print(f"\nstep 3b -- unique partial index {URL_INDEX_NAME}")
    if URL_INDEX_NAME in existing_names:
        print("   already present")
    elif not args.apply:
        print("   would create (unique on user_id + url, partial on a non-empty url)")
    else:
        await db.games.create_index(
            [("user_id", 1), ("url", 1)],
            name=URL_INDEX_NAME,
            unique=True,
            partialFilterExpression={"url": {"$gt": ""}},
        )
        print("   created")

    if not args.apply:
        print("\nnothing was written. re-run with --apply to perform the above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
