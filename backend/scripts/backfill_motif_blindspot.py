"""Backfill `motif_blindspot` on already-generated Game Reviews.

The 2026-08-07 Game Review integration (build_motif_blindspot_callout,
wired into routes/coach.py) only fires when a review is freshly
generated. It does NOT bump V5_COACHING_VERSION, so the ~12.5k reviews
already sitting in game_analyses.decryption_v5_data would otherwise
never pick it up -- users would have to somehow trigger a full
regeneration just to get one new field. This backfill sets ONLY that
field, directly, on already-generated reviews -- no regeneration of
captions/decryption_v5_data/CCT/habits/truth_line, nothing else touched.

Player profiles are cached per user_id within one run (many games share
a user) rather than refetched per game.

Usage:
    python scripts/backfill_motif_blindspot.py --dry-run
    python scripts/backfill_motif_blindspot.py
    python scripts/backfill_motif_blindspot.py --user-id user_8b599930d7ef
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.motif_profile_service import build_motif_blindspot_callout  # noqa: E402


async def main(dry_run: bool, user_id: str | None) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    print(f"Connected: {db_name}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    if user_id:
        print(f"Filtering to user: {user_id}")

    query = {
        "decryption_v5_data": {"$ne": None},
        "motif_blindspot": {"$exists": False},
    }
    if user_id:
        query["user_id"] = user_id

    cursor = db.game_analyses.find(query, {
        "game_id": 1, "user_id": 1,
        "stockfish_analysis.move_evaluations": 1, "_id": 0,
    })

    profile_cache: dict = {}
    scanned = 0
    found_callout = 0
    written = 0
    sample_lines = []

    async for a in cursor:
        scanned += 1
        gid = a.get("game_id")
        uid = a.get("user_id")
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []

        if uid not in profile_cache:
            p = await db.player_profiles.find_one(
                {"user_id": uid},
                {"_id": 0, "motif_profile": 1, "games_analyzed_count": 1},
            )
            profile_cache[uid] = p or {}

        p = profile_cache[uid]
        callout = build_motif_blindspot_callout(
            p.get("motif_profile"), p.get("games_analyzed_count") or 0, moves,
        )
        if callout:
            found_callout += 1
            if len(sample_lines) < 8:
                sample_lines.append(f"  {gid}: {callout}")

        if not dry_run:
            await db.game_analyses.update_one(
                {"game_id": gid},
                {"$set": {"motif_blindspot": callout}},
            )
            written += 1

    print("\nSamples (real callouts found):")
    for line in sample_lines:
        print(line)
    print(f"\nScanned:        {scanned}")
    print(f"Users profiled: {len(profile_cache)}")
    print(f"Real callout:   {found_callout}")
    print(f"No callout (None, still written for idempotency): {scanned - found_callout}")
    if not dry_run:
        print(f"Wrote:          {written}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.user_id))
