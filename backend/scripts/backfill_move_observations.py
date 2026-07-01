"""
Backfill move_observations across all existing game_analyses.

Phase 3 of the move_observations rollout — see docs/move_observations_scope.md.

This script is SAFE-BY-DEFAULT:
  - Default = DRY-RUN. Prints what it would derive but writes nothing.
  - --apply actually writes to MongoDB.
  - Idempotent — re-running with --apply overwrites by (game_id, move_number)
    so it can be safely re-run after a deriver bug fix.
  - --user-id LIMITS the run to one user (great for testing).
  - --limit N processes only the first N analyses.

After Mohit signs off on docs/move_observations_scope.md:

    # Dry-run on one user first (e.g. Mohit himself)
    python scripts/backfill_move_observations.py --user-id user_8b599930d7ef

    # Dry-run across whole corpus (no DB writes)
    python scripts/backfill_move_observations.py

    # Real backfill
    python scripts/backfill_move_observations.py --apply

Expected runtime on full corpus (~9,572 analyses): ~10-15 min single-thread.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from services.move_observation_deriver import (
    derive_observations_for_game,
    aggregate_user_signals,
    SCHEMA_VERSION,
)

COLLECTION = "move_observations"


async def ensure_indexes(db):
    """Create the indexes the scope doc declares."""
    coll = db[COLLECTION]
    await coll.create_index([("user_id", 1), ("derived_at", -1)])
    await coll.create_index([("game_id", 1), ("move_number", 1)], unique=True)
    await coll.create_index([("user_id", 1), ("missed_pattern", 1)])
    await coll.create_index([("user_id", 1), ("concept_used", 1)])
    await coll.create_index([("user_id", 1), ("was_critical_moment", 1)])


async def backfill_one_game(db, game_doc, analysis_doc, apply: bool, skip_if_current: bool = True) -> int:
    """Derive + (optionally) upsert observations for one game.
    Returns the count derived (regardless of apply). 0 = skipped.

    skip_if_current: if any observation for this game is already at
    SCHEMA_VERSION, skip. Lets a crashed backfill resume without
    re-processing everything.
    """
    game_id = game_doc.get("game_id")
    user_id = game_doc.get("user_id")
    user_color = game_doc.get("user_color", "white")

    if skip_if_current:
        existing = await db[COLLECTION].find_one(
            {"game_id": game_id, "schema_version": SCHEMA_VERSION},
            {"_id": 1},
        )
        if existing:
            return 0

    sf = analysis_doc.get("stockfish_analysis") or {}
    if not sf.get("move_evaluations"):
        return 0

    v5 = analysis_doc.get("decryption_v5_data") or None

    obs_list = derive_observations_for_game(
        stockfish_analysis=sf,
        game_id=game_id,
        user_id=user_id,
        user_color=user_color,
        decryption_v5_data=v5,
        derived_at=datetime.now(timezone.utc),
    )
    if not obs_list:
        return 0

    if apply:
        ops = [
            UpdateOne(
                {"game_id": obs["game_id"], "move_number": obs["move_number"]},
                {"$set": obs},
                upsert=True,
            )
            for obs in obs_list
        ]
        if ops:
            await db[COLLECTION].bulk_write(ops, ordered=False)

    return len(obs_list)


async def main_async(apply: bool, user_id: Optional[str], limit: int):
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if apply:
        await ensure_indexes(db)

    # Find analyses to process
    q = {}
    if user_id:
        q["user_id"] = user_id

    cursor = db.game_analyses.find(
        q, {"game_id": 1, "user_id": 1, "stockfish_analysis": 1, "decryption_v5_data": 1}
    ).sort("analyzed_at", -1)
    if limit:
        cursor = cursor.limit(limit)

    print(f"=== {'APPLY' if apply else 'DRY-RUN'} backfill ===")
    print(f"User filter: {user_id or '(all)'}")
    print(f"Limit:       {limit or '(no limit)'}")
    print(f"Schema:      v{SCHEMA_VERSION}")
    print()

    total_games = 0
    total_obs = 0
    per_user_obs = {}
    errors = []

    # Resilient iteration — retry on transient MongoDB connection drops
    skipped_already_v = 0
    processed = 0
    while True:
        try:
            async for analysis in cursor:
                game_id = analysis.get("game_id")
                game = await db.games.find_one(
                    {"game_id": game_id},
                    {"game_id": 1, "user_id": 1, "user_color": 1}
                )
                if not game:
                    errors.append(("no-game-doc", game_id))
                    continue

                try:
                    n = await backfill_one_game(db, game, analysis, apply)
                except Exception as e:
                    errors.append((str(e)[:80], game_id))
                    continue

                if n == 0:
                    skipped_already_v += 1
                else:
                    total_obs += n
                total_games += 1
                processed += 1
                uid = game.get("user_id", "?")
                per_user_obs[uid] = per_user_obs.get(uid, 0) + n

                if total_games % 100 == 0:
                    print(f"  ... {total_games} games processed ({skipped_already_v} already at v{SCHEMA_VERSION}), {total_obs:,} new obs")
            break  # cursor exhausted cleanly
        except Exception as e:
            print(f"  ! cursor error: {str(e)[:120]}. Reopening cursor...")
            # Reopen cursor, skipping the games we've already processed via skip_if_current
            cursor = db.game_analyses.find(
                q, {"game_id": 1, "user_id": 1, "stockfish_analysis": 1, "decryption_v5_data": 1}
            ).sort("analyzed_at", -1)
            if limit:
                cursor = cursor.limit(limit)

    print()
    print(f"=== Done ===")
    print(f"Games processed:        {total_games:,}")
    print(f"Observations derived:   {total_obs:,}")
    print(f"Unique users covered:   {len(per_user_obs):,}")
    print(f"Avg observations/game:  {total_obs/max(total_games,1):.1f}")
    print(f"Errors:                 {len(errors)}")
    for err, gid in errors[:10]:
        print(f"  - [{err}] game={gid}")

    if apply:
        # Spot-check: top 5 users by observation count
        print()
        print("=== Spot-check: top 5 users by observation count ===")
        top = sorted(per_user_obs.items(), key=lambda x: -x[1])[:5]
        for uid, n in top:
            user = await db.users.find_one({"user_id": uid}, {"name": 1, "email": 1})
            name = (user or {}).get("name") or "?"
            print(f"  {uid}  ({name}):  {n:,} observations")
            # Pull their aggregate
            cur = db[COLLECTION].find({"user_id": uid})
            obs_list = await cur.to_list(length=2000)
            agg = aggregate_user_signals(obs_list)
            print(f"     threat_response_rate: {agg.get('threat_response_rate')}")
            print(f"     blunder_punish_rate:  {agg.get('blunder_punish_rate')}")
            print(f"     critical_find_rate:   {agg.get('critical_find_rate')}")
            print(f"     missed_pattern_counts: {agg.get('missed_pattern_counts')}")
            print(f"     concept_used_counts:   {agg.get('concept_used_counts')}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Actually write to MongoDB. Default = dry-run.")
    p.add_argument("--user-id", default=None, help="Limit to one user_id (for testing).")
    p.add_argument("--limit", type=int, default=0, help="Process at most N analyses (0 = no limit).")
    args = p.parse_args()
    asyncio.run(main_async(args.apply, args.user_id, args.limit))


if __name__ == "__main__":
    main()
