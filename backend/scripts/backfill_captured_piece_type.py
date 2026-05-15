"""
Backfill `captured_piece_type` onto every move record in existing
game_analyses.decryption_v5_data.

Runs caption_facts._extract_caption_facts per move using the stored
fen_before / move_san / cp_loss etc., grabs ONLY the captured_piece_type
field, and patches it onto the move record. All other fields untouched.

Idempotent: skips moves that already have captured_piece_type set,
unless --force is passed.

Usage:
    docker exec -it chess-coach-backend python scripts/backfill_captured_piece_type.py
    docker exec -it chess-coach-backend python scripts/backfill_captured_piece_type.py --force
    docker exec -it chess-coach-backend python scripts/backfill_captured_piece_type.py --limit 5
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

try:
    from services.caption_facts import extract_facts as _extract_caption_facts
except Exception as e:
    print(f"[backfill] failed to import caption_facts: {e}", file=sys.stderr)
    raise


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _captured_piece_for_move(rec: Dict[str, Any]) -> Optional[str]:
    """Run caption_facts on the move record's stored inputs and return
    captured_piece_type (or None on failure)."""
    fen_before = rec.get("fen_before")
    move_san = rec.get("move_san")
    if not fen_before or not move_san:
        return None
    try:
        facts = _extract_caption_facts(
            fen_before=fen_before,
            played_san=move_san,
            best_move_san=rec.get("best_move_san"),
            eval_before_cp=rec.get("eval_before"),
            eval_after_cp=rec.get("eval_after"),
            cp_loss=rec.get("cp_loss") or 0,
            pv_after_played=[],
            pv_after_best=rec.get("pv_after_best") or [],
            move_history_san=[],
            full_move_number=rec.get("move_number"),
            mover_is_user=bool(rec.get("is_user_move")),
        )
    except Exception:
        return None
    return facts.get("captured_piece_type")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Process at most N games (default: all).")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing captured_piece_type values.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't write to DB; just report what would change.")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cursor = db.game_analyses.find(
        {},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    games_scanned = 0
    games_updated = 0
    moves_patched = 0
    moves_skipped = 0
    moves_no_input = 0
    start = time.time()

    async for game in cursor:
        games_scanned += 1
        gid = game.get("game_id")
        moves = game.get("decryption_v5_data") or []
        if not moves:
            continue

        set_ops: Dict[str, Optional[str]] = {}
        for idx, rec in enumerate(moves):
            if not args.force and "captured_piece_type" in rec:
                moves_skipped += 1
                continue
            cpt = _captured_piece_for_move(rec)
            if cpt is None and not rec.get("fen_before"):
                moves_no_input += 1
                continue
            set_ops[f"decryption_v5_data.{idx}.captured_piece_type"] = cpt
            moves_patched += 1

        if set_ops and not args.dry_run:
            await db.game_analyses.update_one({"game_id": gid}, {"$set": set_ops})
            games_updated += 1
        elif set_ops:
            games_updated += 1  # would have updated

        if games_scanned % 100 == 0:
            print(f"  ... {games_scanned} games scanned, {moves_patched} moves patched",
                  file=sys.stderr)

    elapsed = time.time() - start
    print("\n── Backfill summary ─────────────────────────────")
    print(f"  Games scanned:       {games_scanned}")
    print(f"  Games updated:       {games_updated}")
    print(f"  Moves patched:       {moves_patched}")
    print(f"  Moves skipped (already): {moves_skipped}")
    print(f"  Moves with no input: {moves_no_input}")
    print(f"  Elapsed:             {elapsed:.1f}s")
    print(f"  Mode:                {'DRY-RUN' if args.dry_run else 'WRITE'}")


if __name__ == "__main__":
    asyncio.run(main())
