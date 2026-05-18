"""
One-shot backfill: populate `decryption_v5_data` + `decryption_v5_version`
on game_analyses docs that are missing it. Twin of backfill_trap_fires.py.

Scope: Path A — only the two V5 fields are written. The downstream
pipeline (cct_narrative, habits_report, truth_line, player_decryption,
decryption_block, pattern_evidence, game_summary) continues to be
generated lazily on first Lab/Reflect read for these games — that
matches the existing behavior, just unblocks corpus-wide queries on
detector fires.

Idempotent: skips rows where decryption_v5_data already exists and is at
current V5_COACHING_VERSION, unless --force.

Usage:
  MONGO_URL=mongodb://user:pass@host:27018/?authSource=admin \\
    docker exec -i chess-coach-backend python \\
    scripts/backfill_v5_fires.py [--limit N] [--user USER_ID] [--force]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Cap at N games (0 = all).")
    parser.add_argument("--user", type=str, default="", help="Restrict to a single user_id.")
    parser.add_argument("--force", action="store_true", help="Re-run even if version current.")
    parser.add_argument("--output", type=str, default="/tmp/v5_fires_backfill.json")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required.", file=sys.stderr)
        sys.exit(1)

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.game_decryption_v5_service import (
        generate_game_decryption_v5, V5_COACHING_VERSION
    )

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    # Find candidates: missing decryption_v5_data OR stale version (when --force)
    query: dict = {}
    if not args.force:
        query["$or"] = [
            {"decryption_v5_data": {"$exists": False}},
            {"decryption_v5_data": None},
            {"decryption_v5_version": {"$lt": V5_COACHING_VERSION}},
            {"decryption_v5_version": {"$exists": False}},
        ]
    if args.user:
        query["user_id"] = args.user

    # We need game PGN + user_color from games collection too
    targets = []
    async for a in db.game_analyses.find(query, {"_id": 0, "game_id": 1, "user_id": 1, "stockfish_analysis": 1}):
        targets.append(a)
        if args.limit and len(targets) >= args.limit:
            break

    print(f"V5 backfill targets: {len(targets)} game_analyses docs (current version={V5_COACHING_VERSION})", file=sys.stderr)

    if not targets:
        print("Nothing to backfill.", file=sys.stderr)
        return

    successes = 0
    failures = 0
    skipped_no_pgn = 0
    skipped_no_evals = 0
    fire_counts = []  # total fires per game (for sanity)
    failure_samples = []

    t0 = time.time()

    for i, a in enumerate(targets, 1):
        gid = a.get("game_id")
        uid = a.get("user_id")
        move_evals = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not move_evals:
            skipped_no_evals += 1
            continue

        game = await db.games.find_one(
            {"game_id": gid},
            {"_id": 0, "pgn": 1, "user_color": 1, "user_plays_as": 1}
        )
        if not game or not game.get("pgn"):
            skipped_no_pgn += 1
            continue

        pgn = game["pgn"]
        user_color = (game.get("user_color") or game.get("user_plays_as") or "white")

        try:
            decryption_data = await generate_game_decryption_v5(
                pgn, user_color, move_evals, uid, db
            )
            if not decryption_data:
                failures += 1
                failure_samples.append({"game_id": gid, "reason": "empty result"})
                continue

            await db.game_analyses.update_one(
                {"game_id": gid, "user_id": uid},
                {"$set": {
                    "decryption_v5_data": decryption_data,
                    "decryption_v5_version": V5_COACHING_VERSION,
                    "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            successes += 1
            # Count principle/shape fires for sanity
            fire_count = sum(
                1 for m in decryption_data
                if m.get("principle_id_used") or m.get("shape_pattern_id")
            )
            fire_counts.append(fire_count)
        except Exception as e:
            failures += 1
            if len(failure_samples) < 10:
                failure_samples.append({"game_id": gid, "reason": str(e)[:300]})

        if i % 50 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  progress: {i}/{len(targets)}  ok={successes} fail={failures}  rate={rate:.1f} g/s", file=sys.stderr)

    elapsed = time.time() - t0
    total_fires = sum(fire_counts)
    avg_fires = total_fires / max(len(fire_counts), 1)

    out = {
        "elapsed_seconds": round(elapsed, 1),
        "candidates": len(targets),
        "successes": successes,
        "failures": failures,
        "skipped_no_pgn": skipped_no_pgn,
        "skipped_no_evals": skipped_no_evals,
        "total_fires_across_successes": total_fires,
        "avg_fires_per_game": round(avg_fires, 1),
        "failure_samples": failure_samples,
        "v5_version": V5_COACHING_VERSION,
    }
    Path(args.output).write_text(json.dumps(out, indent=2))

    print()
    print("=" * 60)
    print(f"V5 backfill complete in {elapsed:.1f}s ({V5_COACHING_VERSION=})")
    print(f"  candidates:       {len(targets)}")
    print(f"  successes:        {successes}")
    print(f"  failures:         {failures}")
    print(f"  skipped no PGN:   {skipped_no_pgn}")
    print(f"  skipped no evals: {skipped_no_evals}")
    print(f"  total new fires:  {total_fires}  (avg {avg_fires:.1f}/game)")
    if failure_samples:
        print(f"  first failure:    {failure_samples[0]}")
    print(f"\nFull report: {args.output}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
