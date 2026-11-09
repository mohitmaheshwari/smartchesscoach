"""
Backfill time_control_category + user_rating + opponent_rating on all games.

Theme 2 — Context Enrichment. Pure derivation from PGN headers + existing
fields. Idempotent. Bulk_write for speed.

Usage:
    python scripts/backfill_game_context.py            # dry-run
    python scripts/backfill_game_context.py --apply    # write
    python scripts/backfill_game_context.py --apply --user-id user_xxx  # test one user

    # Fill only fields a game does not have; never replace a stored value.
    # This is what import does since 2026-11-09 (fill_missing_context).
    python scripts/backfill_game_context.py --only-missing
    python scripts/backfill_game_context.py --only-missing --apply --undo-file /root/x.json
"""
import argparse, asyncio, json, os, sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from services.game_context_enricher import (
    _FILL_FIELDS, derive_context_fields, fill_missing_context)


async def only_missing_async(apply: bool, user_id: str, limit: int, undo_file: str):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    q = {"$or": [{f: None} for f in ("time_control_category", "opponent_rating")]}
    if user_id:
        q["user_id"] = user_id
    proj = {"game_id": 1, "user_color": 1, "pgn": 1, "time_control": 1,
            **{f: 1 for f in _FILL_FIELDS}}
    cur = db.games.find(q, proj)
    if limit:
        cur = cur.limit(limit)
    fields, tc, ops, undo = Counter(), Counter(), [], []
    scanned = written = 0
    async for g in cur:
        scanned += 1
        added = fill_missing_context(dict(g))
        if not added:
            continue
        fields.update(added.keys())
        if "time_control_category" in added:
            tc[added["time_control_category"]] += 1
        # The filter repeats "still empty", so a value written meanwhile wins.
        ops.append(UpdateOne({"_id": g["_id"], **{k: None for k in added}}, {"$set": added}))
        undo.append([g["game_id"], sorted(added)])
        if apply and len(ops) >= 500:
            written += (await db.games.bulk_write(ops, ordered=False)).modified_count
            ops = []
    if apply and ops:
        written += (await db.games.bulk_write(ops, ordered=False)).modified_count
    if apply:
        # Undo: $unset the listed fields on the listed game_ids.
        with open(undo_file, "w") as fh:
            json.dump(undo, fh)
    print(json.dumps({"mode": "apply" if apply else "dry_run", "scanned": scanned,
                      "games_to_fill": len(undo), "written": written,
                      "fields": dict(fields), "categories": dict(tc)}, indent=2))


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
    p.add_argument("--only-missing", action="store_true")
    p.add_argument("--undo-file", default="")
    args = p.parse_args()
    if args.only_missing:
        if args.apply and not args.undo_file:
            sys.exit("--only-missing --apply needs --undo-file")
        asyncio.run(only_missing_async(args.apply, args.user_id, args.limit, args.undo_file))
        return
    asyncio.run(main_async(args.apply, args.user_id, args.limit))


if __name__ == "__main__":
    main()
