"""
Backfill the `result` field on imported Lichess games.

Every Lichess game historically had `result = game.status` ("mate",
"resign", "outoftime", etc.) instead of the PGN's canonical
"1-0"/"0-1"/"1/2-1/2". This broke every W/L/D derivation downstream.

This script re-parses `[Result "..."]` from each game's PGN and
overwrites the stored `result`. Run once after deploying the fix at
journey_service.py:1062.

Usage:
    # dry-run first
    python scripts/backfill_lichess_result.py --dry-run

    # apply
    python scripts/backfill_lichess_result.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


_PGN_RESULT_VALUES = {"1-0", "0-1", "1/2-1/2"}
_BOGUS_RESULT_VALUES = {"mate", "resign", "outoftime", "draw",
                        "stalemate", "timeout", "cheat", "variantEnd", ""}


def _pgn_result(pgn: str) -> str:
    m = re.search(r'\[Result\s+"([^"]*)"\]', pgn or "")
    return m.group(1) if m else ""


async def main(dry_run: bool) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Connected: {mongo_url} / {db_name}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}\n")

    cursor = db.games.find({"platform": "lichess"})
    scanned = 0
    needs_fix = 0
    fixed = 0
    skipped_no_pgn = 0
    skipped_already_canonical = 0

    async for g in cursor:
        scanned += 1
        current = g.get("result") or ""
        pgn = g.get("pgn") or ""

        # If already canonical, skip.
        if current in _PGN_RESULT_VALUES:
            skipped_already_canonical += 1
            continue

        parsed = _pgn_result(pgn)
        if not parsed or parsed not in _PGN_RESULT_VALUES:
            skipped_no_pgn += 1
            continue

        needs_fix += 1
        gid = g.get("game_id")
        if scanned <= 20 or needs_fix <= 20:
            print(f"  {gid}: {current!r} -> {parsed!r}")
        if not dry_run:
            await db.games.update_one(
                {"game_id": gid},
                {"$set": {"result": parsed}},
            )
            fixed += 1

    print(f"\nScanned:                    {scanned}")
    print(f"Already canonical:          {skipped_already_canonical}")
    print(f"No PGN / unparseable:       {skipped_no_pgn}")
    print(f"Would fix:                  {needs_fix}")
    if not dry_run:
        print(f"Applied updates:            {fixed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
