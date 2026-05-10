"""
Re-run V5 decryption on every analyzed game and overwrite the stored
decryption_v5_data. Use after shipping fixes to extract_plan_from_pv,
the vacuous detector, or any other V5 generation logic, so reviewers
(Parth, Mohit) see the CURRENT output of the pipeline instead of stale
data baked in days ago.

Run inside the backend container:
    python scripts/regen_v5_decryption.py                      # all games
    python scripts/regen_v5_decryption.py --limit 20           # first N
    python scripts/regen_v5_decryption.py --user-id <uid>      # one owner
    python scripts/regen_v5_decryption.py --since-days 30      # recent only
    python scripts/regen_v5_decryption.py --dry-run            # no DB writes

Behaviour:
  - Iterates `games` where is_analyzed=true (filters apply on top)
  - Loads pgn from games + move_evaluations from
    game_analyses.stockfish_analysis.move_evaluations
  - Runs generate_game_decryption_v5 fresh
  - Writes the result to game_analyses.decryption_v5_data
  - Updates game_analyses.decryption_v5_regen_at timestamp
  - Skips games the script just regenerated (--skip-recent-hours)

Skipping logic mirrors batch_voice_regen.py so you can re-run safely
without redoing the whole DB if the script crashed mid-run.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0,
                   help="Process only first N games (0 = all).")
    p.add_argument("--user-id", default=None,
                   help="Only games for this user_id.")
    p.add_argument("--since-days", type=int, default=0,
                   help="Only games imported in the last N days (0 = all).")
    p.add_argument("--skip-recent-hours", type=int, default=0,
                   help="Skip games whose decryption_v5_regen_at is < N hours old.")
    p.add_argument("--dry-run", action="store_true",
                   help="Run V5 generation but don't write anything to MongoDB.")
    p.add_argument("--game-id", default=None,
                   help="Regenerate just this game (overrides other filters).")
    args = p.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Build filter for `games` collection
    flt = {"is_analyzed": True}
    if args.game_id:
        flt = {"game_id": args.game_id}
    else:
        if args.user_id:
            flt["user_id"] = args.user_id
        if args.since_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.since_days)
            flt["imported_at"] = {"$gte": cutoff.isoformat()}

    cursor = db.games.find(flt, {"_id": 0}).sort("imported_at", -1)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    games = await cursor.to_list(args.limit if args.limit > 0 else 10000)

    if not games:
        print("No games match the filters.")
        client.close()
        return 0

    print(f"Found {len(games)} game(s) to process.")
    print(f"  dry_run={args.dry_run}  skip_recent_hours={args.skip_recent_hours}")
    print()

    # Lazy import — heavy module
    from services.game_decryption_v5_service import generate_game_decryption_v5

    total = len(games)
    n_regenerated = 0
    n_skipped_recent = 0
    n_skipped_no_data = 0
    n_failed = 0
    n_dry = 0

    skip_cutoff: Optional[datetime] = None
    if args.skip_recent_hours > 0:
        skip_cutoff = datetime.now(timezone.utc) - timedelta(hours=args.skip_recent_hours)

    t0 = time.time()
    for i, game in enumerate(games, 1):
        game_id = game.get("game_id")
        user_id = game.get("user_id") or "unknown"
        analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
        if not analysis:
            n_skipped_no_data += 1
            continue

        # Skip if recently regenerated
        if skip_cutoff is not None:
            regen_at = analysis.get("decryption_v5_regen_at")
            if regen_at:
                if isinstance(regen_at, str):
                    try:
                        regen_at = datetime.fromisoformat(regen_at.replace("Z", "+00:00"))
                    except Exception:
                        regen_at = None
                if regen_at and regen_at >= skip_cutoff:
                    n_skipped_recent += 1
                    continue

        pgn = game.get("pgn") or ""
        sf = analysis.get("stockfish_analysis") or {}
        move_evaluations = sf.get("move_evaluations") or []
        user_color = (game.get("user_color") or "white").lower()

        if not pgn or not move_evaluations:
            n_skipped_no_data += 1
            continue

        try:
            decryption = await generate_game_decryption_v5(
                pgn=pgn,
                user_color=user_color,
                move_evaluations=move_evaluations,
                user_id=user_id,
                db=db,
            )
        except Exception as exc:
            print(f"  [{i}/{total}] {game_id}  FAIL: {exc}")
            n_failed += 1
            continue

        if args.dry_run:
            n_dry += 1
            print(f"  [{i}/{total}] {game_id}  (dry, would write {len(decryption)} move records)")
            continue

        try:
            await db.game_analyses.update_one(
                {"game_id": game_id},
                {"$set": {
                    "decryption_v5_data": decryption,
                    "decryption_v5_regen_at": datetime.now(timezone.utc),
                }},
            )
            n_regenerated += 1
            if i % 5 == 0 or i == total:
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                print(f"  [{i}/{total}] {game_id}  OK  ({len(decryption)} records, {rate:.1f}/s)")
        except Exception as exc:
            print(f"  [{i}/{total}] {game_id}  WRITE-FAIL: {exc}")
            n_failed += 1

    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(f"Total games examined:        {total}")
    print(f"  regenerated + written:     {n_regenerated}")
    print(f"  dry-run (would write):     {n_dry}")
    print(f"  skipped (recent regen):    {n_skipped_recent}")
    print(f"  skipped (no data/pgn):     {n_skipped_no_data}")
    print(f"  failed:                    {n_failed}")
    print(f"Elapsed:                     {elapsed:.1f}s")
    print("=" * 60)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
