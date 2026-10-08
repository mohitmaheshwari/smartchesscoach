"""Relabel stored observations where the missed tactic was a checkmate.

Mohit 2026-10-05, on a card badged "Tactical - missed skewer" where the
engine's move was Rc8#: "It is missed mate not missed skewer."

v188 put the mate check in front of the geometry checks in
classify_missed_tactic, so every NEW analysis labels these correctly. The
badge on the review page does not come from that code path at read time: it
comes from `move_observations.subtype`, written once at analysis time. So a
card that was analysed before v188 keeps saying "missed skewer" no matter how
many times the caption re-renders -- which is exactly what Mohit saw after the
deploy, and a fair thing to be annoyed by.

This calls classify_missed_tactic itself rather than reimplementing the rule,
so the backfill and the live path cannot drift apart.

Dry run by default; --apply writes.

  docker exec -i chess-coach-backend python -m scripts.backfill_missed_mate_subtype
  ... --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from services.cognitive_gap_subtypes import classify_missed_tactic  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = every analysis")
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    counts: collections.Counter = collections.Counter()
    rows = []

    cursor = db.game_analyses.find(
        {},
        {"game_id": 1, "user_id": 1,
         "stockfish_analysis.move_evaluations.move": 1,
         "stockfish_analysis.move_evaluations.move_number": 1,
         "stockfish_analysis.move_evaluations.fen_before": 1,
         "stockfish_analysis.move_evaluations.best_move": 1,
         "stockfish_analysis.move_evaluations.best_move_uci": 1,
         "stockfish_analysis.move_evaluations.cp_loss": 1,
         "stockfish_analysis.move_evaluations.is_opponent_move": 1},
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    async for analysis in cursor:
        counts["analyses"] += 1
        game_id = analysis.get("game_id")
        for mv in (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if mv.get("is_opponent_move"):
                continue
            subtype, severity = classify_missed_tactic(mv, None, None)
            if subtype != "missed_mate":
                continue
            counts["moves the classifier now calls missed_mate"] += 1

            move_number = mv.get("move_number")
            try:
                move_number = int(move_number)
            except (TypeError, ValueError):
                counts["  unusable move_number"] += 1
                continue

            observation = await db.move_observations.find_one(
                {"game_id": game_id, "move_number": move_number,
                 "missed_pattern": "missed_tactic"},
                {"subtype": 1, "user_id": 1},
            )
            if not observation:
                counts["  no stored observation to fix"] += 1
                continue
            was = observation.get("subtype")
            if was == "missed_mate":
                counts["  already correct"] += 1
                continue
            counts[f"  RELABEL from {was}"] += 1
            if len(rows) < 12:
                rows.append((str(game_id)[:8], move_number, mv.get("move"),
                             mv.get("best_move"), was))
            if args.apply:
                await db.move_observations.update_one(
                    {"_id": observation["_id"]},
                    {"$set": {"subtype": "missed_mate",
                              "subtype_backfilled_at": "2026-10-06",
                              "subtype_backfill_was": was}},
                )
                counts["  WRITTEN"] += 1

    mode = "APPLIED" if args.apply else "DRY RUN (nothing written)"
    print(f"=== {mode} ===")
    for key, value in counts.most_common():
        print(f"  {key:<46} {value}")
    print("\n  rows (game, move#, played, engine best, old subtype):")
    for row in rows:
        print(f"    {row[0]} m{row[1]:<4} {str(row[2]):<7} best={str(row[3]):<7} was={row[4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
