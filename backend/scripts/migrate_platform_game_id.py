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
  2. report duplicate groups, and with --apply delete all but the best row
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
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

INDEX_NAME = "games_platform_game_id_unique"

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
            if args.apply:
                await db.games.update_one(
                    {"game_id": row["game_id"]},
                    {"$set": {"platform_game_id": derived}},
                )
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
        for (user_id, platform, gid), rows in sorted(dupes.items(), key=lambda kv: str(kv[0])):
            rows.sort(key=lambda r: rank_row(r, analysed_ids), reverse=True)
            keeper, drop = rows[0], rows[1:]
            if deleted < 5 or args.apply is False and deleted < 5:
                print(f"      {platform}/{gid} user={user_id}: keep "
                      f"{keeper['game_id'][:8]} (pgn {len(keeper.get('pgn') or '')}b, "
                      f"analysed={keeper['game_id'] in analysed_ids}), "
                      f"drop {', '.join(r['game_id'][:8] for r in drop)}")
            for row in drop:
                deleted += 1
                if args.apply:
                    await db.games.delete_one({"game_id": row["game_id"]})
                    # The dropped row's own analysis/queue rows go with it so
                    # nothing is left pointing at a game that no longer exists.
                    await db.game_analyses.delete_many({"game_id": row["game_id"]})
                    await db.analysis_queue.delete_many({"game_id": row["game_id"]})
        print(f"   rows {'deleted' if args.apply else 'that would be deleted'}: {deleted:,}")

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

    if not args.apply:
        print("\nnothing was written. re-run with --apply to perform the above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
