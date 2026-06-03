"""Fast variant of pick_authoring_games — classifies buckets via server-side
aggregation instead of pulling every game's full decryption_v5_data over the
wire. Drops in for the same role: picks N games per bucket and persists to
the authoring_queue collection under a fresh round_id so Parth's
/review/authoring page shows them as the active round.

The original pick_authoring_games.py iterates every game_analyses doc with
its v5 data attached (~megabytes each × 4000 games = gigabytes). On a
production-sized DB it hangs for tens of minutes. This version pushes the
filter logic into MongoDB's aggregation engine — counts only — so the wire
payload stays tiny.

Tradeoff: positional-mistake bucket's "no TAC_HANGING_PIECE" refinement is
dropped (would need nested principle inspection). Otherwise functionally
equivalent classification.

Usage:
  docker exec chess-coach-backend python \
    /app/backend/scripts/pick_authoring_games_fast.py --per-bucket 5 --persist
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

BUCKETS = [
    "TACTICAL_BLUNDER",
    "POSITIONAL_MISTAKE",
    "ENDGAME",
    "OPENING_DRIFT",
    "WON_WITH_BLUNDER",
]


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-bucket", type=int, default=5)
    ap.add_argument("--persist", action="store_true")
    ap.add_argument("--round-id", type=str, default=None)
    ap.add_argument("--include-authored", action="store_true",
                    help="Allow re-picking games already authored on. Default excludes.")
    ap.add_argument("--max-per-owner", type=int, default=3)
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    already_authored: set[str] = set()
    if not args.include_authored:
        already_authored = set(
            await db.move_feedback.distinct(
                "game_id", {"is_authoring_submission": True}
            )
        )
    print(f"[picker-fast] Excluding {len(already_authored)} authored game_ids", file=sys.stderr)

    # Server-side classification — no v5 data leaves the DB. Each $filter
    # counts how many moves match a predicate; the boolean is "count > 0".
    pipeline = [
        {"$match": {
            "decryption_v5_data": {"$type": "array"},
            "game_id": {"$nin": list(already_authored)},
        }},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "tactical_blunder_count": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$and": [
                    {"$eq": ["$$this.is_user_move", True]},
                    {"$gte": [{"$ifNull": ["$$this.cp_loss", 0]}, 200]},
                ]},
            }}},
            "positional_mistake_count": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$and": [
                    {"$eq": ["$$this.is_user_move", True]},
                    {"$gte": [{"$ifNull": ["$$this.cp_loss", 0]}, 50]},
                    {"$lte": [{"$ifNull": ["$$this.cp_loss", 0]}, 150]},
                ]},
            }}},
            "endgame_count": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$eq": ["$$this.phase", "endgame"]},
            }}},
            "opening_drift_count": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$and": [
                    {"$eq": ["$$this.is_user_move", True]},
                    {"$eq": ["$$this.phase", "opening"]},
                    {"$gte": [{"$ifNull": ["$$this.cp_loss", 0]}, 30]},
                    {"$lte": [{"$ifNull": ["$$this.cp_loss", 0]}, 100]},
                ]},
            }}},
        }},
    ]
    print("[picker-fast] Running aggregation…", file=sys.stderr)
    classified = [r async for r in db.game_analyses.aggregate(pipeline)]
    print(f"[picker-fast] Classified {len(classified)} games", file=sys.stderr)

    # Pull side info for each candidate in one query
    candidate_gids = [r["game_id"] for r in classified]
    games_by_id: dict[str, dict] = {}
    async for g in db.games.find(
        {"game_id": {"$in": candidate_gids}, "is_active": {"$ne": False}, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "user_id": 1,
         "opening": 1, "opening_name": 1, "imported_at": 1},
    ):
        games_by_id[g["game_id"]] = g

    bucket_to_games: dict[str, list[str]] = defaultdict(list)
    classified_by_id: dict[str, dict] = {}
    for r in classified:
        gid = r["game_id"]
        if gid not in games_by_id:
            continue
        classified_by_id[gid] = r
        g = games_by_id[gid]
        user_won = (
            (g.get("result") == "1-0" and g.get("user_color") == "white")
            or (g.get("result") == "0-1" and g.get("user_color") == "black")
        )
        if r["tactical_blunder_count"] > 0:
            bucket_to_games["TACTICAL_BLUNDER"].append(gid)
        if r["positional_mistake_count"] > 0:
            bucket_to_games["POSITIONAL_MISTAKE"].append(gid)
        if r["endgame_count"] > 0:
            bucket_to_games["ENDGAME"].append(gid)
        if r["opening_drift_count"] > 0:
            bucket_to_games["OPENING_DRIFT"].append(gid)
        if user_won and r["tactical_blunder_count"] > 0:
            bucket_to_games["WON_WITH_BLUNDER"].append(gid)

    print(f"[picker-fast] Bucket sizes: {{b: len(v) for b, v in bucket_to_games.items()}}", file=sys.stderr)
    for b in BUCKETS:
        print(f"  {b}: {len(bucket_to_games.get(b, []))}", file=sys.stderr)

    # Pick, prefer recent imports, ensure variety across buckets + owners
    picked_set: set[str] = set()
    picked: list[tuple[str, str]] = []  # (game_id, bucket)
    per_owner: dict[str, int] = {}
    for b in BUCKETS:
        candidates = [g for g in bucket_to_games.get(b, []) if g not in picked_set]
        candidates.sort(
            key=lambda gid: games_by_id[gid].get("imported_at") or "",
            reverse=True,
        )
        n_in_bucket = 0
        for gid in candidates:
            if n_in_bucket >= args.per_bucket:
                break
            owner = games_by_id[gid].get("user_id") or "?"
            if per_owner.get(owner, 0) >= args.max_per_owner:
                continue
            picked.append((gid, b))
            picked_set.add(gid)
            per_owner[owner] = per_owner.get(owner, 0) + 1
            n_in_bucket += 1

    print(f"\n── Picked {len(picked)} games across {len(per_owner)} owners ──")
    for i, (gid, b) in enumerate(picked, 1):
        g = games_by_id[gid]
        r = classified_by_id[gid]
        opening = (g.get("opening_name") or g.get("opening") or "?")[:38]
        print(
            f"  {i:>2}. [{b:<18}] {gid:<38} "
            f"blund={r['tactical_blunder_count']:<2} "
            f"mist={r['positional_mistake_count']:<2} "
            f"color={(g.get('user_color') or '?'):<5} {opening:<38} "
            f"owner=…{(g.get('user_id') or '?')[-6:]}"
        )

    if args.persist:
        round_id = args.round_id or f"round_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        await db.authoring_queue.delete_many({"round_id": round_id})
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for order, (gid, b) in enumerate(picked, 1):
            g = games_by_id[gid]
            docs.append({
                "round_id": round_id,
                "game_id": gid,
                "bucket": b,
                "user_id": g.get("user_id"),
                "result": g.get("result"),
                "user_color": g.get("user_color"),
                "opening": g.get("opening") or g.get("opening_name"),
                "imported_at": g.get("imported_at"),
                "picked_at": now,
                "order_in_round": order,
            })
        if docs:
            await db.authoring_queue.insert_many(docs)
            print(f"\nPersisted {len(docs)} games under round_id={round_id}")
        else:
            print("\nNothing to persist (no games matched)")


if __name__ == "__main__":
    asyncio.run(main())
