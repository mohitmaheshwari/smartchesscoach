"""
Backfill trap + opening recognition fields on existing game_analyses.

For every already-analyzed active game, walk decryption_v5_data with the
same stateful trap-line walker and opening-curriculum matcher that the
V5 service now runs inline for new analyses. Writes `trap` and `opening`
fields to each move record. Pure Python, NO LLM calls, no cost.

Why this exists:
  - services/game_decryption_v5_service.py now writes these fields for
    every NEW analysis, but the 1600 already-analyzed games don't have
    them. This script makes the schema uniform.
  - downstream consumers (LLM caption generator, future frontend
    surfacing of opening name / trap callouts) can assume the fields
    exist on every active analyzed game once this runs.

Idempotent: by default skips games where the FIRST move record already
has a `trap` field (presence = backfilled). Pass --force to overwrite.

Usage:
    docker exec -it chess-coach-backend python scripts/backfill_trap_opening.py
    docker exec -it chess-coach-backend python scripts/backfill_trap_opening.py --force
    docker exec -it chess-coach-backend python scripts/backfill_trap_opening.py --limit 10  # smoke-test
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.trap_recognition import detect_trap_setup, match_trap_line_step
from services.opening_lookup import match_opening_for_mover


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def annotate_moves(moves: List[Dict[str, Any]]) -> Dict[str, int]:
    """Walk moves in place, attach `trap` and `opening` fields. Returns
    per-game stats so the caller can summarize.
    """
    stats = {"trap_setups": 0, "trap_continuations": 0, "openings_named": 0}
    played_san_so_far: List[str] = []
    active_trap: Optional[Dict[str, Any]] = None
    active_trap_setup_completed_by_user: Optional[bool] = None
    active_trap_step_cursor: int = 0

    for m in moves:
        san = m.get("move_san")
        if not san:
            continue
        played_san_so_far.append(san)

        # Opening lookup — per move, for the side that just moved.
        mover_color = "white" if m.get("is_white") else "black"
        opening_match = match_opening_for_mover(played_san_so_far, mover_color)
        m["opening"] = opening_match  # explicit None if no match (so presence == backfilled)
        if opening_match:
            stats["openings_named"] += 1

        # Trap walker.
        trap_record = None
        if active_trap is None:
            hit = detect_trap_setup(played_san_so_far)
            if hit:
                active_trap = hit
                active_trap_setup_completed_by_user = bool(m.get("is_user_move"))
                active_trap_step_cursor = 0
                trap_record = {
                    "name": hit["name"],
                    "family": hit["family"],
                    "description": hit["description"],
                    "step": 0,
                    "step_label": "setup_completed",
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(m.get("is_user_move")),
                    "next_expected_move": hit["trap_line"][0] if hit["trap_line"] else None,
                }
                stats["trap_setups"] += 1
        else:
            step_index = active_trap_step_cursor
            if match_trap_line_step(active_trap, san, step_index):
                step_label = "victim_falls" if step_index % 2 == 0 else "trap_player_punishes"
                step_expl = ""
                steps = active_trap.get("trap_line_steps") or []
                if step_index < len(steps):
                    step_expl = steps[step_index].get("explanation", "")
                next_mv = None
                if step_index + 1 < len(active_trap["trap_line"]):
                    next_mv = active_trap["trap_line"][step_index + 1]
                trap_record = {
                    "name": active_trap["name"],
                    "family": active_trap["family"],
                    "description": active_trap["description"],
                    "step": step_index + 1,
                    "step_label": step_label,
                    "step_explanation": step_expl,
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(m.get("is_user_move")),
                    "next_expected_move": next_mv,
                }
                stats["trap_continuations"] += 1
                active_trap_step_cursor = step_index + 1
                if active_trap_step_cursor >= len(active_trap["trap_line"]):
                    active_trap = None
                    active_trap_step_cursor = 0
            else:
                active_trap = None
                active_trap_step_cursor = 0

        m["trap"] = trap_record
    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Overwrite even if fields already present.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Process at most N games (0 = no limit).")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Build the set of active analyzed game_ids.
    active_ids: List[str] = []
    async for g in db.games.find(
        {"is_active": {"$ne": False}, "is_analyzed": True},
        {"_id": 0, "game_id": 1},
    ):
        gid = g.get("game_id")
        if gid:
            active_ids.append(gid)
    print(f"[backfill] active analyzed games: {len(active_ids)}", file=sys.stderr)

    totals = {
        "games_total": 0, "games_processed": 0, "games_skipped": 0,
        "games_no_v5": 0, "trap_setups": 0, "trap_continuations": 0,
        "openings_named": 0,
    }

    async for analysis in db.game_analyses.find(
        {"game_id": {"$in": active_ids}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    ):
        gid = analysis.get("game_id")
        moves = analysis.get("decryption_v5_data") or []
        totals["games_total"] += 1

        if args.limit and totals["games_processed"] >= args.limit:
            continue

        if not moves:
            totals["games_no_v5"] += 1
            continue

        # Idempotency: presence of `trap` key on the first non-empty move
        # signals this game was already backfilled.
        if not args.force:
            first_real = next((m for m in moves if m.get("move_san")), None)
            if first_real and "trap" in first_real:
                totals["games_skipped"] += 1
                continue

        per_game = annotate_moves(moves)
        totals["trap_setups"] += per_game["trap_setups"]
        totals["trap_continuations"] += per_game["trap_continuations"]
        totals["openings_named"] += per_game["openings_named"]

        # Write the whole decryption_v5_data back — simplest path.
        await db.game_analyses.update_one(
            {"game_id": gid},
            {"$set": {"decryption_v5_data": moves}},
        )
        totals["games_processed"] += 1
        if totals["games_processed"] % 100 == 0:
            print(f"[backfill] processed {totals['games_processed']} games...", file=sys.stderr)

    print("\n── SUMMARY ────────────────────────────────────")
    print(f"games scanned         : {totals['games_total']}")
    print(f"games processed       : {totals['games_processed']}")
    print(f"games skipped (idemp.): {totals['games_skipped']}")
    print(f"games with no V5 data : {totals['games_no_v5']}")
    print(f"trap setups fired     : {totals['trap_setups']}")
    print(f"trap continuations    : {totals['trap_continuations']}")
    print(f"opening matches       : {totals['openings_named']}")


if __name__ == "__main__":
    asyncio.run(main())
