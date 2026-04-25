"""
Backfill `move_time_stats` on already-analyzed games.

Re-extracts move-time discipline stats from each game's PGN clk tags
and joins with stockfish move_evaluations to identify the critical
move. Honest gating: games without clk tags are skipped silently.

Usage:
    python scripts/backfill_move_time_stats.py --dry-run
    python scripts/backfill_move_time_stats.py
    python scripts/backfill_move_time_stats.py --user-id user_8b599930d7ef
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

from services.move_time_analyzer import compute_move_time_stats  # noqa: E402


async def main(dry_run: bool, user_id: str | None) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Connected: {mongo_url} / {db_name}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    if user_id:
        print(f"Filtering to user: {user_id}")

    query = {"is_analyzed": True}
    if user_id:
        query["user_id"] = user_id

    cursor = db.games.find(query, {
        "game_id": 1, "user_id": 1, "user_color": 1, "pgn": 1,
        "time_control": 1, "move_time_stats": 1, "_id": 0,
    })

    scanned = 0
    skipped_no_clk = 0
    written = 0
    refresh_count = 0
    sample_lines = []

    async for g in cursor:
        scanned += 1
        gid = g.get("game_id")
        pgn = g.get("pgn") or ""
        user_color = g.get("user_color") or "white"

        # Pull TimeControl from PGN if present (chess.com/lichess both
        # include it). game_doc.time_control is the lichess "speed"
        # ("blitz") which doesn't carry increment.
        tc_match = re.search(r'\[TimeControl\s+"([^"]*)"\]', pgn)
        tc = tc_match.group(1) if tc_match else g.get("time_control")

        # Need stockfish moves for critical-move sub-stats.
        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        )
        sf_moves = (
            (analysis or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        )

        stats = compute_move_time_stats(pgn, user_color, tc, sf_moves)
        if not stats:
            skipped_no_clk += 1
            continue

        # If already present and equal, skip the write.
        existing = g.get("move_time_stats")
        if existing and existing == stats:
            refresh_count += 1
            continue

        if len(sample_lines) < 10:
            sample_lines.append(
                f"  {gid}: median={stats['median_user_move_s']}s "
                f"crit={stats.get('critical_move_time_s')}s rushed={stats['rushed_critical']}"
            )

        if not dry_run:
            await db.games.update_one(
                {"game_id": gid},
                {"$set": {"move_time_stats": stats}},
            )
            written += 1

    print("\nSamples:")
    for line in sample_lines:
        print(line)
    print(f"\nScanned:        {scanned}")
    print(f"No clk data:    {skipped_no_clk}")
    print(f"Already current: {refresh_count}")
    print(f"Would update:   {scanned - skipped_no_clk - refresh_count}")
    if not dry_run:
        print(f"Wrote:          {written}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.user_id))
