"""
Audit existing community_puzzles against the new extraction quality gate.

Loose extraction shipped many positional/non-tactical puzzles into the
pool. This script applies the new `_is_puzzle_worthy` filter to every
existing community_puzzle and reports (or removes) ones that wouldn't
pass today's bar.

Usage:
    python scripts/audit_community_puzzles.py --dry-run
    python scripts/audit_community_puzzles.py --apply         # delete failing puzzles
    python scripts/audit_community_puzzles.py --apply --mark  # mark instead of delete
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from services.puzzle_extraction_service import _is_puzzle_worthy


async def main(apply: bool, mark_only: bool) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    print(f"DB: {db_name}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}{' (MARK ONLY)' if mark_only else ''}")
    print()

    cursor = db.community_puzzles.find({})
    total = 0
    pass_count = 0
    fail_count = 0
    fail_samples = []
    fail_reasons = {"no_forcing_no_pattern": 0, "endgame_low_rating": 0,
                    "out_of_bounds_cp": 0, "missing_data": 0}

    async for p in cursor:
        total += 1
        fen = p.get("fen", "")
        best_san = p.get("best_move_san") or p.get("best_move", "")
        best_uci = p.get("best_move_uci")
        pv = p.get("pv_after_best") or []
        move_num = int(p.get("move_number") or 0)
        rating = int(p.get("rating") or 1200)
        cp_loss = int(p.get("cp_loss") or 0)

        if not fen or not best_san:
            fail_count += 1
            fail_reasons["missing_data"] += 1
            continue

        worthy = _is_puzzle_worthy(
            fen_before=fen,
            best_move_san=best_san,
            best_move_uci=best_uci,
            pv_after_best=pv if isinstance(pv, list) else [],
            move_number=move_num,
            user_rating=rating,
            cp_loss=cp_loss,
        )

        if worthy:
            pass_count += 1
            continue

        fail_count += 1
        # Categorize failure for reporting
        if cp_loss <= 0 or cp_loss > 2000:
            fail_reasons["out_of_bounds_cp"] += 1
        elif rating < 1500 and move_num > 30:
            fail_reasons["endgame_low_rating"] += 1
        else:
            fail_reasons["no_forcing_no_pattern"] += 1

        if len(fail_samples) < 8:
            fail_samples.append(
                f"  {p.get('_id', '?')}: best={best_san}, move={move_num}, "
                f"rating={rating}, cp={cp_loss}, theme={p.get('theme', '?')}"
            )

        if apply:
            if mark_only:
                await db.community_puzzles.update_one(
                    {"_id": p["_id"]},
                    {"$set": {"approved": False, "rejected_reason": "quality_gate"}},
                )
            else:
                await db.community_puzzles.delete_one({"_id": p["_id"]})

    print("Sample failing puzzles:")
    for s in fail_samples:
        print(s)
    print()
    print(f"Total scanned: {total:,}")
    print(f"  Pass:  {pass_count:,} ({100*pass_count/max(total,1):.1f}%)")
    print(f"  Fail:  {fail_count:,} ({100*fail_count/max(total,1):.1f}%)")
    print(f"    no forcing + no tactical pattern: {fail_reasons['no_forcing_no_pattern']:,}")
    print(f"    endgame for low-rated user:       {fail_reasons['endgame_low_rating']:,}")
    print(f"    cp_loss out of bounds:            {fail_reasons['out_of_bounds_cp']:,}")
    print(f"    missing data:                     {fail_reasons['missing_data']:,}")
    if apply:
        action = "marked rejected" if mark_only else "deleted"
        print(f"\n{fail_count:,} puzzles {action}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Without this flag, runs as dry-run.")
    parser.add_argument("--mark", action="store_true",
                        help="With --apply: mark approved=False instead of delete.")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, mark_only=args.mark))
