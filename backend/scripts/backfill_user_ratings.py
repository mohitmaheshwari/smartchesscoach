"""
Backfill per-user ratings from PGN headers.

Problem: `player_profiles.chesscom_stats.rating` and related fields are
empty for every user, but PGN headers contain `[WhiteElo "X"]` /
`[BlackElo "Y"]` on every imported game. This script extracts those,
aggregates per user, and writes:

  player_profiles.chesscom_stats.rating   (most-recent chess.com games)
  player_profiles.lichess_stats.rating    (most-recent lichess games)
  player_profiles.current_rating          (highest of the two, or latest)
  player_profiles.rating_history          (per-game samples for future use)

Aggregation: average of the last 10 rated games on each platform. If <10
available, uses whatever exists. More robust than a single-game snapshot.

Usage:
  docker cp scripts/backfill_user_ratings.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/backfill_user_ratings.py
  docker exec -it chess-coach-backend python3 scripts/backfill_user_ratings.py --apply
  docker exec -it chess-coach-backend python3 scripts/backfill_user_ratings.py --user user_8b599930d7ef --apply
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("backfill_user_ratings")

PROGRESS_EVERY = 10
RATING_WINDOW = 10  # average over this many most-recent games per platform


_WHITE_ELO = re.compile(r'\[WhiteElo\s+"(\d+)"\]')
_BLACK_ELO = re.compile(r'\[BlackElo\s+"(\d+)"\]')


def _extract_rating_for_user(pgn: str, user_color: str) -> int:
    """Extract the user's rating from a PGN based on their color. Returns 0
    if not found or malformed."""
    if not pgn:
        return 0
    if (user_color or "white").lower() == "white":
        m = _WHITE_ELO.search(pgn)
    else:
        m = _BLACK_ELO.search(pgn)
    if not m:
        return 0
    try:
        r = int(m.group(1))
        return r if 0 < r < 4000 else 0
    except Exception:
        return 0


async def process_one_user(db, user_id: str, apply: bool) -> Dict:
    """Compute per-platform ratings for a single user and optionally persist."""
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "user_color": 1, "pgn": 1, "platform": 1, "imported_at": 1},
    ).sort("imported_at", -1).to_list(500)

    if not games:
        return {"user_id": user_id, "skipped": "no_games"}

    # Collect per-platform rating history (most recent first — games query is desc)
    by_platform: Dict[str, List[Dict]] = defaultdict(list)
    history_samples = []
    for g in games:
        rating = _extract_rating_for_user(g.get("pgn", ""), g.get("user_color"))
        if rating <= 0:
            continue
        platform = (g.get("platform") or "unknown").lower()
        sample = {
            "game_id": g.get("game_id"),
            "rating": rating,
            "platform": platform,
            "date": str(g.get("imported_at") or ""),
        }
        by_platform[platform].append(sample)
        history_samples.append(sample)

    if not history_samples:
        return {"user_id": user_id, "skipped": "no_ratings_in_pgn"}

    # Aggregate: last N on each platform
    chesscom_rating = None
    lichess_rating = None
    if by_platform.get("chess.com"):
        recent = [s["rating"] for s in by_platform["chess.com"][:RATING_WINDOW]]
        chesscom_rating = int(round(mean(recent)))
    if by_platform.get("lichess"):
        recent = [s["rating"] for s in by_platform["lichess"][:RATING_WINDOW]]
        lichess_rating = int(round(mean(recent)))

    # Current rating: prefer whichever platform has the MOST recent sample.
    # history_samples is already newest-first (from games sort).
    current_rating = history_samples[0]["rating"] if history_samples else 0

    stats = {
        "user_id": user_id,
        "games_with_rating": len(history_samples),
        "chesscom_rating": chesscom_rating,
        "lichess_rating": lichess_rating,
        "current_rating": current_rating,
    }

    if apply:
        update_doc = {"current_rating": current_rating}
        if chesscom_rating is not None:
            update_doc["chesscom_stats.rating"] = chesscom_rating
        if lichess_rating is not None:
            update_doc["lichess_stats.rating"] = lichess_rating
        # Keep only a bounded history (last 50) to avoid doc bloat
        update_doc["rating_history"] = history_samples[:50]
        update_doc["ratings_backfilled_at"] = datetime.now(timezone.utc).isoformat()
        await db.player_profiles.update_one(
            {"user_id": user_id},
            {"$set": update_doc},
            upsert=True,
        )

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Backfill per-user ratings from PGN headers.")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N users (0 = all).")
    parser.add_argument("--user", type=str, default="", help="Only process this user_id.")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    logger.info(f"Connecting to {db_name} at {url}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    if args.user:
        user_ids = [args.user]
    else:
        users = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(1000)
        user_ids = [u.get("user_id") for u in users if u.get("user_id")]

    if args.limit:
        user_ids = user_ids[: args.limit]

    if not args.apply:
        logger.info("DRY RUN — no writes. Pass --apply to persist.")
    logger.info(f"Users to process: {len(user_ids)}")

    results = []
    skipped_by_reason = defaultdict(int)
    chesscom_present = 0
    lichess_present = 0

    for i, uid in enumerate(user_ids, 1):
        try:
            r = await process_one_user(db, uid, apply=args.apply)
        except Exception as e:
            logger.warning(f"failed on {uid}: {e}")
            continue
        if r.get("skipped"):
            skipped_by_reason[r["skipped"]] += 1
            continue
        results.append(r)
        if r.get("chesscom_rating"):
            chesscom_present += 1
        if r.get("lichess_rating"):
            lichess_present += 1
        if i % PROGRESS_EVERY == 0:
            logger.info(f"  progress: {i}/{len(user_ids)} users")

    print()
    print("═" * 60)
    print(f"Users processed:                 {len(user_ids)}")
    print(f"Users with a rating extracted:   {len(results)}")
    print(f"  ... with chess.com rating:     {chesscom_present}")
    print(f"  ... with lichess rating:       {lichess_present}")
    if skipped_by_reason:
        print()
        print("Skipped:")
        for reason, cnt in skipped_by_reason.items():
            print(f"  {reason:30s} {cnt}")

    if results:
        # Rating distribution preview
        print()
        print("Rating distribution preview (by current_rating):")
        bands = [("<1000", 0, 999), ("1000-1199", 1000, 1199),
                 ("1200-1399", 1200, 1399), ("1400-1599", 1400, 1599),
                 ("1600+", 1600, 9999)]
        for band_name, lo, hi in bands:
            cnt = sum(1 for r in results if lo <= (r.get("current_rating") or 0) <= hi)
            print(f"  {band_name:<12} {cnt}")

        # Top 10 by rating
        print()
        print("Sample — top 10 by current_rating:")
        ranked = sorted(results, key=lambda r: -(r.get("current_rating") or 0))[:10]
        print(f"  {'user_id':<30} {'chess.com':>10}  {'lichess':>8}  {'games':>6}")
        for r in ranked:
            cc = r.get("chesscom_rating") or "—"
            lc = r.get("lichess_rating") or "—"
            print(
                f"  {r['user_id']:<30} {str(cc):>10}  {str(lc):>8}  "
                f"{r.get('games_with_rating'):>6}"
            )

    if not args.apply:
        print()
        print("DRY RUN complete. Re-run with --apply to persist.")


if __name__ == "__main__":
    asyncio.run(main())
