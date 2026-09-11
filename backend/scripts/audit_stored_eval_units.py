"""
Are eval_before/eval_after always centipawns?
=============================================

Any gate or report that reads them needs to know, and the answer is no.

Spotted while sampling loose-piece cards: one row printed "eval 4.5 -> 3.96"
with cp_loss 54. 0.54 pawns == 54cp, so that document stores PAWNS while
cp_loss stays in centipawns. Any eval-magnitude gate would read +4.5 as a level
game when it is actually White up a bishop and a half.

Reference run, 2026-09-11, 2,000 analyses: 1,922 (96.1%) centipawns, 78 (3.9%)
pawns. cp_loss is centipawns in both, so the two fields disagree on units
inside the same document. Consumers that compare an eval to a centipawn
threshold silently mis-read those 3.9%.

    docker exec chess-coach-backend python scripts/audit_stored_eval_units.py
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    parser = argparse.ArgumentParser(description="stored eval unit audit")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    verdict = Counter()
    total = 0
    async for doc in db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).limit(args.limit):
        moves = doc["stockfish_analysis"]["move_evaluations"] or []
        values = [float(m[k]) for m in moves for k in ("eval_before", "eval_after")
                  if isinstance(m.get(k), (int, float))]
        if not values:
            verdict["no eval stored"] += 1
            continue
        total += 1
        # A centipawn eval is always a whole number. A fractional value can
        # only be pawns, and that is the reliable discriminator -- "never
        # exceeds 40" is not, because a quiet game genuinely stays near zero.
        if any(abs(v - round(v)) > 1e-9 for v in values):
            verdict["fractional values -> PAWNS"] += 1
        elif max(abs(v) for v in values) < 40:
            verdict["integer but never exceeds 40 -> ambiguous"] += 1
        else:
            verdict["integer, large -> CENTIPAWNS"] += 1

    print(f"analyses inspected: {total}")
    for key, value in verdict.most_common():
        print(f"  {key:42} {value:5}  ({value/max(total, 1)*100:4.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
