"""
One-shot corpus backfill: scan every analyzed game against the 41-trap
library and persist `trap_fires` onto each game_analyses doc.

Future games are auto-populated by analysis_worker.py invoking the same
trap_scanner module — see [[worker-side-detector-migration]].

Usage:
  MONGO_URL=mongodb://user:pass@host:27018/?authSource=admin \\
    docker exec -i chess-coach-backend python \\
    scripts/backfill_trap_fires.py [--limit N] [--user USER_ID]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Allow running both as `python -m scripts.backfill_trap_fires` and as a
# script. Adds /app/backend to sys.path when needed.
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from pymongo import MongoClient

from services.trap_scanner import scan_pgn_for_traps, TRAP_SCANNER_VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Cap at N games (0 = all).")
    parser.add_argument("--user", type=str, default="", help="Restrict to a single user_id.")
    parser.add_argument("--force", action="store_true", help="Re-scan even if trap_fires_version already current.")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB.")
    parser.add_argument("--output", type=str, default="/tmp/trap_fires_backfill.json")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required.", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    # Load game metadata once so we can attach user_color/result/opponent
    # without per-game joins.
    game_meta = {}
    meta_query = {"is_analyzed": True}
    if args.user:
        meta_query["user_id"] = args.user
    for g in db.games.find(meta_query, {"_id": 0, "game_id": 1, "user_color": 1, "opponent_username": 1, "result": 1, "user_id": 1, "pgn": 1}):
        game_meta[g["game_id"]] = g

    print(f"Backfill targets: {len(game_meta)} analyzed games", file=sys.stderr)

    total_scanned = 0
    total_with_fires = 0
    total_fires = 0
    gold_counts = Counter()
    by_trap = Counter()
    by_trap_gold = defaultdict(lambda: Counter())  # trap → gold/celebration/lucky/warning
    sample_gold = []  # first 20 GOLD fires for the report

    bulk_writes = 0
    t0 = time.time()

    for gid, g in game_meta.items():
        if args.limit and total_scanned >= args.limit:
            break

        # Check if already current (skip unless --force)
        if not args.force:
            existing = db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "trap_fires_version": 1})
            if existing and existing.get("trap_fires_version") == TRAP_SCANNER_VERSION:
                continue

        total_scanned += 1
        fires = scan_pgn_for_traps(g.get("pgn") or "", g.get("user_color") or "white")

        if fires:
            total_with_fires += 1
            total_fires += len(fires)
            for f in fires:
                gc = f.get("gold_class", "none")
                gold_counts[gc] += 1
                by_trap[f["trap_name"]] += 1
                by_trap_gold[f["trap_name"]][gc] += 1
                if gc == "gold" and len(sample_gold) < 20:
                    sample_gold.append({
                        "game_id": gid,
                        "user_color": f["user_color"],
                        "opponent": g.get("opponent_username"),
                        "result": g.get("result"),
                        "trap_name": f["trap_name"],
                        "opening_key": f["opening_key"],
                        "training_weakness": f["training_weakness"],
                    })

        if not args.dry_run:
            db.game_analyses.update_one(
                {"game_id": gid},
                {"$set": {
                    "trap_fires": fires,
                    "trap_fires_version": TRAP_SCANNER_VERSION,
                    "trap_fires_scanned_at": time.time(),
                }},
                upsert=False,
            )
            bulk_writes += 1

        if total_scanned % 500 == 0:
            print(f"  progress: {total_scanned} scanned · {total_with_fires} with fires · {total_fires} total fires", file=sys.stderr)

    elapsed = time.time() - t0

    out = {
        "elapsed_seconds": round(elapsed, 1),
        "scanned_games": total_scanned,
        "writes": bulk_writes,
        "games_with_fires": total_with_fires,
        "total_fires": total_fires,
        "gold_class_counts": dict(gold_counts),
        "fires_by_trap": dict(by_trap.most_common()),
        "fires_by_trap_gold_breakdown": {k: dict(v) for k, v in by_trap_gold.items()},
        "sample_gold_first_20": sample_gold,
    }
    Path(args.output).write_text(json.dumps(out, indent=2))

    # Stdout summary
    print()
    print("=" * 60)
    print(f"Scanned: {total_scanned}  ·  with fires: {total_with_fires}  ·  total fires: {total_fires}  ·  elapsed: {elapsed:.1f}s")
    print(f"DB writes: {bulk_writes}{' (DRY RUN)' if args.dry_run else ''}")
    print()
    print("Teaching-gold breakdown:")
    for gc in ("gold", "celebration", "lucky", "warning"):
        print(f"  {gc:12s}  {gold_counts.get(gc, 0)}")
    print()
    print("Top 20 traps by fire count:")
    for name, cnt in by_trap.most_common(20):
        gbg = by_trap_gold[name]
        print(f"  {name:38s}  total={cnt:>4}  gold={gbg.get('gold',0):>3}  celeb={gbg.get('celebration',0):>3}  lucky={gbg.get('lucky',0):>3}  warn={gbg.get('warning',0):>3}")

    if sample_gold:
        print()
        print("Sample GOLD fires (you had a trap setup but missed the trap):")
        for s in sample_gold[:10]:
            print(f"  game {s['game_id'][:14]}  {s['trap_name']:30s}  as {s['user_color']:5s}  vs {s['opponent']}  ({s['result']})")

    print()
    print(f"Full report: {args.output}")


if __name__ == "__main__":
    main()
