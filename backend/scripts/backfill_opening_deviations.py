"""
One-shot backfill: compute opening_deviation for every analyzed game.
Phase-3 Component 2.

After this runs, downstream surfaces (Lab game review, user opening
profile recurring-deviations aggregation) have data to work with.

Usage:
  MONGO_URL=... docker exec -i chess-coach-backend python \\
    scripts/backfill_opening_deviations.py [--limit N] [--force]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="Re-compute even if already current.")
    parser.add_argument("--out", type=str, default="/tmp/opening_deviations_backfill.json")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required.", file=sys.stderr)
        sys.exit(1)

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.opening_deviation import (
        detect_opening_deviation, OPENING_DEVIATION_VERSION,
    )

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    # Build games metadata lookup so we have pgn + user_color
    print("Loading games metadata…", file=sys.stderr)
    games_meta: dict = {}
    cursor = db.games.find(
        {"is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
    )
    async for g in cursor:
        games_meta[g["game_id"]] = g
    print(f"  → {len(games_meta)} analyzed games", file=sys.stderr)

    # Iterate game_analyses
    successes = 0
    failures = 0
    deviations_found = 0
    in_book_max = 0
    by_opening = Counter()
    skipped_current = 0
    skipped_no_meta = 0
    t0 = time.time()

    q: dict = {}
    if not args.force:
        q["$or"] = [
            {"opening_deviation": {"$exists": False}},
            {"opening_deviation.version": {"$lt": OPENING_DEVIATION_VERSION}},
        ]
    ga_cursor = db.game_analyses.find(q, {"_id": 0, "game_id": 1})

    processed = 0
    async for a in ga_cursor:
        if args.limit and processed >= args.limit:
            break
        gid = a.get("game_id")
        if not gid:
            continue
        meta = games_meta.get(gid)
        if not meta or not meta.get("pgn"):
            skipped_no_meta += 1
            continue
        try:
            result = detect_opening_deviation(meta["pgn"], meta.get("user_color") or "white")
            await db.game_analyses.update_one(
                {"game_id": gid},
                {"$set": {"opening_deviation": result}},
            )
            successes += 1
            if result.get("deviation"):
                deviations_found += 1
                lon = result["deviation"].get("last_opening_name") or "Unknown"
                by_opening[lon] += 1
            in_book_max = max(in_book_max, result.get("in_book_through_user_move", 0))
        except Exception as e:
            failures += 1
        processed += 1
        if processed % 200 == 0:
            print(f"  progress: {processed}  ok={successes} fail={failures} deviations={deviations_found}", file=sys.stderr)

    elapsed = time.time() - t0

    out = {
        "elapsed_seconds": round(elapsed, 1),
        "processed": processed,
        "successes": successes,
        "failures": failures,
        "skipped_no_meta": skipped_no_meta,
        "skipped_current": skipped_current,
        "deviations_found": deviations_found,
        "max_in_book_through": in_book_max,
        "top_opening_families_deviated_from": dict(by_opening.most_common(15)),
        "version": OPENING_DEVIATION_VERSION,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))

    print()
    print(f"Backfill complete in {elapsed:.1f}s")
    print(f"  processed:        {processed}")
    print(f"  successes:        {successes}")
    print(f"  failures:         {failures}")
    print(f"  skipped_no_meta:  {skipped_no_meta}")
    print(f"  deviations found: {deviations_found}  ({100*deviations_found/max(1,successes):.1f}% of successful scans)")
    print(f"  max in_book depth: {in_book_max}")
    print()
    print("Top 10 openings deviated from:")
    for name, n in by_opening.most_common(10):
        print(f"  {name:40s}  {n}")
    print(f"\nFull report: {args.out}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
