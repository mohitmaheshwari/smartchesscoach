"""Relabel stored "a pin you could have played" observations that were no pin.

Game 56b6c294, 2026-10-21. The story told Mohit "A pin you could have played"
for 13...Nxg5, whose better move was 13...Bxc3. The prover's pin was the
bishop on c3 against White's b2 pawn and a1 rook -- and the b2 pawn simply
takes the bishop. `aligned_tactic_puzzle_proof.front_can_break_alignment`
now refuses any line the front piece can break by capturing the attacker and
winning material, unless the capture walks into mate in one.

New analyses label these correctly. Stored rows do not change on their own:
`move_observations.subtype` is written once at analysis time and is what the
story, the move badge and the focus picker read. So this asks the LIVE
classifier again, exactly as `backfill_missed_mate_subtype` does, and only
touches rows stored as missed_pin that the classifier no longer calls a pin.

Run AFTER the fix is deployed: data must never be newer than the code that
reads it.

Dry run by default; --apply writes.

  docker exec -i chess-coach-backend python -m scripts.backfill_false_pin_subtype
  ... --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
from datetime import datetime, timezone
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from services.cognitive_gap_subtypes import classify_missed_tactic  # noqa: E402

_PROJECTION = {
    "game_id": 1,
    "stockfish_analysis.move_evaluations.move": 1,
    "stockfish_analysis.move_evaluations.move_number": 1,
    "stockfish_analysis.move_evaluations.fen_before": 1,
    "stockfish_analysis.move_evaluations.best_move": 1,
    "stockfish_analysis.move_evaluations.best_move_uci": 1,
    "stockfish_analysis.move_evaluations.cp_loss": 1,
    "stockfish_analysis.move_evaluations.eval_before": 1,
    "stockfish_analysis.move_evaluations.eval_after": 1,
    # The classifier's mate branch reads mate_info; leaving it out silently
    # changes its answer (see backfill_missed_mate_subtype).
    "stockfish_analysis.move_evaluations.mate_info": 1,
    "stockfish_analysis.move_evaluations.pv_after_played": 1,
    "stockfish_analysis.move_evaluations.is_opponent_move": 1,
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    counts: collections.Counter = collections.Counter()
    samples = []

    stored = await db.move_observations.find(
        {"subtype": "missed_pin"},
        {"_id": 1, "game_id": 1, "move_number": 1, "move_san": 1},
    ).to_list(length=None)
    counts["stored missed_pin rows"] = len(stored)
    by_game = collections.defaultdict(list)
    for row in stored:
        by_game[row["game_id"]].append(row)

    for game_id, rows in by_game.items():
        analysis = await db.game_analyses.find_one({"game_id": game_id}, _PROJECTION)
        evaluations = ((analysis or {}).get("stockfish_analysis") or {}).get(
            "move_evaluations") or []
        index = {(e.get("move_number"), e.get("move")): e for e in evaluations
                 if not e.get("is_opponent_move")}
        for row in rows:
            mv = index.get((row.get("move_number"), row.get("move_san")))
            if mv is None:
                counts["  no matching stored evaluation"] += 1
                continue
            subtype, severity = classify_missed_tactic(mv, None, None)
            if subtype == "missed_pin":
                counts["  still a pin"] += 1
                continue
            new = subtype or "missed_generic_tactic"
            counts[f"  RELABEL to {new}"] += 1
            if len(samples) < 12:
                samples.append((str(game_id)[:8], row.get("move_number"),
                                row.get("move_san"), mv.get("best_move"), new))
            if args.apply:
                update = {
                    "subtype": new,
                    "subtype_backfilled_at": datetime.now(timezone.utc).date().isoformat(),
                    "subtype_backfill_was": "missed_pin",
                    "subtype_backfill_reason": "front_piece_can_break_alignment",
                }
                if severity:
                    update["severity"] = severity
                await db.move_observations.update_one(
                    {"_id": row["_id"], "subtype": "missed_pin"}, {"$set": update})
                counts["  WRITTEN"] += 1

    mode = "APPLIED" if args.apply else "DRY RUN (nothing written)"
    print(f"=== {mode} ===")
    for key, value in counts.most_common():
        print(f"  {key:<46} {value}")
    print("\n  rows (game, move#, played, engine best, new subtype):")
    for sample in samples:
        print(f"    {sample[0]} m{sample[1]:<4} {str(sample[2]):<7} best={str(sample[3]):<7} -> {sample[4]}")
    print(f"\n  games touched: {len({g for g in by_game})} with a stored pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
