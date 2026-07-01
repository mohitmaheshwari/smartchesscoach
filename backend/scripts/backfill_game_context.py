"""
Backfill time_control_category + user_rating + opponent_rating on all games.

Theme 2 — Context Enrichment. Pure derivation from PGN headers + existing
fields. Idempotent. Bulk_write for speed.

Usage:
    python scripts/backfill_game_context.py            # dry-run
    python scripts/backfill_game_context.py --apply    # write
    python scripts/backfill_game_context.py --apply --user-id user_xxx  # test one user
"""
import argparse, asyncio, os, sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from services.game_context_enricher import derive_context_fields


async def main_async(apply: bool, user_id: str, limit: int):
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    q = {}
    if user_id:
        q["user_id"] = user_id
    cur = db.games.find(q, {"game_id": 1, "user_id": 1, "user_color": 1,
                             "pgn": 1, "time_control": 1})
    if limit:
        cur = cur.limit(limit)

    print(f"=== {'APPLY' if apply else 'DRY-RUN'} ===  filter={q}  limit={limit}")
    ops_buffer = []
    n = 0
    fields_counter = Counter()
    tc_counter = Counter()
    examples = []

    async for g in cur:
        derived = derive_context_fields(g)
        if not derived:
            continue
        for k in derived: fields_counter[k] += 1
        if "time_control_category" in derived:
            tc_counter[derived["time_control_category"]] += 1
        if len(examples) < 5:
            examples.append((g["game_id"][:12], derived))
        ops_buffer.append(UpdateOne({"game_id": g["game_id"]}, {"$set": derived}))
        n += 1
        if len(ops_buffer) >= 500 and apply:
            await db.games.bulk_write(ops_buffer, ordered=False)
            ops_buffer = []
            if n % 2000 == 0:
                print(f"  ... {n:,} games processed")
    if ops_buffer and apply:
        await db.games.bulk_write(ops_buffer, ordered=False)

    print(f"\nGames processed: {n:,}")
    print(f"Field population:")
    for f, c in fields_counter.most_common():
        print(f"  {f:<28} {c:>6,}  ({round(100*c/max(n,1))}%)")
    print(f"Time-control categories:")
    for cat, c in tc_counter.most_common():
        print(f"  {cat:<12} {c:>6,}")
    print(f"\nSamples:")
    for gid, d in examples:
        print(f"  {gid}..  {d}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--user-id", default=None)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    asyncio.run(main_async(args.apply, args.user_id, args.limit))


if __name__ == "__main__":
    main()
