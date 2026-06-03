"""Force-regenerate decryption_v5_data for a sample of games.

Wires up the same generate_game_decryption_v5 path the analysis worker uses,
runs it against game_analyses rows whose stored captions are at older V5
versions, and overwrites decryption_v5_data + decryption_v5_version.

Used to validate whether stale-caption fixes (template edits + V5 bumps) have
actually improved the audit-for-WHY fail rate without waiting for organic
lazy regen via user views.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/regen_v5_sample.py --n 100 --seed 42
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from services.game_decryption_v5_service import (
    generate_game_decryption_v5,
    V5_COACHING_VERSION,
)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-stale-version", type=int, default=V5_COACHING_VERSION - 1,
                    help="Skip games already at this version or newer")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if already at current version (useful after a "
                         "container code sync that fixes a silently-crashing pipeline)")
    args = ap.parse_args()
    random.seed(args.seed)

    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    print(f"[regen] Current V5_COACHING_VERSION = {V5_COACHING_VERSION}", file=sys.stderr)

    # Same sampling as the audit — random N from games with v5 data.
    all_gids = await db.game_analyses.distinct(
        "game_id", {"decryption_v5_data": {"$type": "array"}}
    )
    all_gids.sort()  # stable ordering — must match audit_captions_for_why.py
    print(f"[regen] Pool with v5 data: {len(all_gids)}", file=sys.stderr)
    sample_gids = (
        random.sample(all_gids, args.n)
        if len(all_gids) > args.n
        else all_gids
    )
    print(f"[regen] Sampled {len(sample_gids)} game_ids", file=sys.stderr)

    regenerated = 0
    skipped_fresh = 0
    skipped_no_data = 0
    errors = 0
    t0 = time.time()

    for idx, gid in enumerate(sample_gids, 1):
        # Skip if already at current version
        meta = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_version": 1, "stockfish_analysis": 1},
        )
        if not meta:
            skipped_no_data += 1
            continue
        cur_ver = meta.get("decryption_v5_version")
        if not args.force and cur_ver and cur_ver >= V5_COACHING_VERSION:
            skipped_fresh += 1
            continue

        # Need pgn + user_color + move_evaluations
        game_doc = await db.games.find_one(
            {"game_id": gid},
            {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1},
        )
        if not game_doc or not game_doc.get("pgn"):
            skipped_no_data += 1
            continue

        move_evals = (meta.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not move_evals:
            skipped_no_data += 1
            continue

        try:
            new_v5 = await generate_game_decryption_v5(
                pgn=game_doc["pgn"],
                user_color=game_doc.get("user_color") or "white",
                move_evaluations=move_evals,
                user_id=game_doc.get("user_id") or "unknown",
                db=db,
                game_id=gid,
            )
            if not new_v5:
                errors += 1
                print(f"  [{idx:>3}/{len(sample_gids)}] {gid[:18]} → empty result", file=sys.stderr)
                continue
            await db.game_analyses.update_one(
                {"game_id": gid},
                {"$set": {
                    "decryption_v5_data": new_v5,
                    "decryption_v5_version": V5_COACHING_VERSION,
                    "decryption_v5_regen_at": datetime.now(timezone.utc),
                }},
            )
            regenerated += 1
            if idx % 25 == 0 or idx == len(sample_gids):
                elapsed = time.time() - t0
                rate = idx / elapsed if elapsed else 0
                print(
                    f"  [{idx:>3}/{len(sample_gids)}] regen'd {regenerated}, "
                    f"skipped {skipped_fresh + skipped_no_data}, errors {errors} "
                    f"({rate:.1f}/s)",
                    file=sys.stderr,
                )
        except Exception as e:
            errors += 1
            print(f"  [{idx:>3}/{len(sample_gids)}] {gid[:18]} → {type(e).__name__}: {e}", file=sys.stderr)

    elapsed = time.time() - t0
    print()
    print(f"Done in {elapsed:.1f}s.")
    print(f"  regenerated:  {regenerated}")
    print(f"  skipped (already fresh):   {skipped_fresh}")
    print(f"  skipped (no pgn/data):     {skipped_no_data}")
    print(f"  errors:       {errors}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
