"""
Backfill TIER 3 shape-pattern fields on existing game_analyses docs.

For every game_analyses document with a decryption_v5_data array, this
script runs the shape detector against each per-move record using the
fen_before + best_move_uci already stored there. The result patches
five fields back onto each move record:

    shape_pattern_id
    shape_pattern_name
    shape_pattern_desc
    shape_pattern_mover
    shape_pattern_targets
    shape_pattern_executing_move

Suppression is enforced game-by-game (each pattern surfaces at most
once per game) so the backfilled state matches what the live V5
pipeline emits going forward.

This is additive: games that already have shape_pattern_id set on
their first move are skipped unless --force is passed.

Usage (inside the backend container or with backend/.env loadable):

    python scripts/backfill_shape_patterns.py
    python scripts/backfill_shape_patterns.py --limit 5
    python scripts/backfill_shape_patterns.py --user-id <uid>
    python scripts/backfill_shape_patterns.py --dry-run
    python scripts/backfill_shape_patterns.py --force
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

from services.shape_layer import select_shape_for_position


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _backfill_game(decryption_v5_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run shape detection over every move in a single game's V5 data.
    Mutates the list in place. Returns a stats dict.
    """
    shapes_fired_this_game: set = set()
    fires = 0
    skipped_no_fen = 0
    detector_errors = 0
    prev_move_uci: Optional[chess.Move] = None
    for rec in decryption_v5_data:
        fen_before = rec.get("fen_before")
        best_move_uci = rec.get("best_move_uci") or ""
        if not fen_before:
            skipped_no_fen += 1
            # Still clear the fields so the schema is uniform
            rec["shape_pattern_id"] = None
            rec["shape_pattern_name"] = None
            rec["shape_pattern_desc"] = None
            rec["shape_pattern_mover"] = None
            rec["shape_pattern_targets"] = []
            rec["shape_pattern_executing_move"] = None
            continue
        try:
            pre_board = chess.Board(fen_before)
        except Exception:
            detector_errors += 1
            continue
        try:
            shape_rec = select_shape_for_position(
                pre_board,
                eval_data={"best_move_uci": best_move_uci} if best_move_uci else None,
                shapes_fired_this_game=shapes_fired_this_game,
                prev_move=prev_move_uci,
            )
        except Exception:
            detector_errors += 1
            shape_rec = None
        if shape_rec:
            fires += 1
            rec["shape_pattern_id"]   = shape_rec["pattern_id"]
            rec["shape_pattern_name"] = shape_rec["pattern_name"]
            rec["shape_pattern_desc"] = shape_rec["pattern_desc"]
            rec["shape_pattern_mover"] = shape_rec.get("mover")
            rec["shape_pattern_targets"] = shape_rec.get("targets") or []
            rec["shape_pattern_executing_move"] = shape_rec.get("executing_move")
        else:
            rec["shape_pattern_id"]   = None
            rec["shape_pattern_name"] = None
            rec["shape_pattern_desc"] = None
            rec["shape_pattern_mover"] = None
            rec["shape_pattern_targets"] = []
            rec["shape_pattern_executing_move"] = None
        # Track prev_move for in_between_move detector.
        played_uci = rec.get("played_move_uci") or rec.get("user_move_uci") or ""
        if played_uci:
            try:
                prev_move_uci = chess.Move.from_uci(played_uci)
            except Exception:
                prev_move_uci = None
    return {
        "moves":           len(decryption_v5_data),
        "fires":           fires,
        "patterns_unique": len(shapes_fired_this_game),
        "skipped_no_fen":  skipped_no_fen,
        "detector_errors": detector_errors,
    }


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--user-id", type=str, default=None,
                    help="Limit to a single user_id")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process at most N games (most-recent first)")
    ap.add_argument("--force", action="store_true",
                    help="Re-detect even if shape_pattern_id is already set")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute but don't write back to MongoDB")
    ap.add_argument("--include-inactive", action="store_true",
                    help="Also process games marked is_active=False. Default: "
                         "active games only (skips the deactivated 2000+ that "
                         "mark_active_games.py archived).")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # By default, restrict to active games only — the 1600 the user kept
    # active via mark_active_games.py. Avoids re-processing the archived
    # 2000+ games on every audit run.
    active_game_ids: Optional[set] = None
    if not args.include_inactive:
        active_cursor = db.games.find(
            {"is_active": {"$ne": False}},
            {"_id": 0, "game_id": 1},
        )
        active_game_ids = {d["game_id"] async for d in active_cursor if d.get("game_id")}
        print(f"[backfill] active filter: {len(active_game_ids)} game_ids", file=sys.stderr, flush=True)

    query: Dict[str, Any] = {"decryption_v5_data": {"$exists": True, "$ne": []}}
    if args.user_id:
        query["user_id"] = args.user_id
    if active_game_ids is not None:
        query["game_id"] = {"$in": list(active_game_ids)}

    cursor = db.game_analyses.find(query, {"_id": 1, "game_id": 1, "user_id": 1, "decryption_v5_data": 1})
    cursor = cursor.sort("analyzed_at", -1)
    if args.limit:
        cursor = cursor.limit(args.limit)

    total_games = 0
    games_skipped_already_done = 0
    games_updated = 0
    games_no_fires = 0
    total_moves = 0
    total_fires = 0
    pattern_histogram: Counter = Counter()

    start = time.time()
    async for doc in cursor:
        total_games += 1
        v5 = doc.get("decryption_v5_data") or []
        if not v5:
            continue

        # Additive skip: if first record already has shape_pattern_id, this
        # game was processed by the post-integration V5 pipeline (or a prior
        # backfill run). Skip unless --force.
        if not args.force:
            first = v5[0] if v5 else {}
            if "shape_pattern_id" in first:
                games_skipped_already_done += 1
                continue

        stats = _backfill_game(v5)
        total_moves += stats["moves"]
        total_fires += stats["fires"]
        if stats["fires"] == 0:
            games_no_fires += 1
        for rec in v5:
            pid = rec.get("shape_pattern_id")
            if pid:
                pattern_histogram[pid] += 1

        if not args.dry_run:
            await db.game_analyses.update_one(
                {"_id": doc["_id"]},
                {"$set": {"decryption_v5_data": v5}},
            )
            games_updated += 1

        if total_games % 25 == 0:
            elapsed = time.time() - start
            print(f"[backfill] {total_games} games processed in {elapsed:.1f}s "
                  f"({games_updated} updated, {games_skipped_already_done} skipped, "
                  f"{total_fires} fires)", file=sys.stderr, flush=True)

    elapsed = time.time() - start
    print(f"\n── Backfill summary ─────────────────────────────")
    print(f"  Games scanned:           {total_games}")
    print(f"  Games skipped (already): {games_skipped_already_done}")
    print(f"  Games updated:           {games_updated}")
    print(f"  Games with no fires:     {games_no_fires}")
    print(f"  Total moves:             {total_moves}")
    print(f"  Total shape fires:       {total_fires}")
    print(f"  Elapsed:                 {elapsed:.1f}s")
    print(f"  Mode:                    {'DRY-RUN' if args.dry_run else 'WRITE'}")
    if pattern_histogram:
        print(f"\n  Pattern histogram (sorted):")
        for pid, n in pattern_histogram.most_common():
            print(f"    {pid:28s} {n:5d}")


if __name__ == "__main__":
    asyncio.run(main())
