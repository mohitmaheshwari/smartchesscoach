"""Is the shape spread real, and is "took it" scoring it fairly?

The gate reports 83% on free material against 44% on pins and 42% on skewers,
and its docstring says a single pattern's rate does not describe a person. That
caution was measured at bars of 10, 20 and 30 chances per half. This player has
1,471 pin chances and 855 free-piece chances, where the standard error is about
a point, so the caution may simply not apply at this volume. Measured, not
assumed, either way.

TWO THINGS COULD FAKE THE SPREAD.

Stability. If his pin rate swings between halves of his own games, the number
describes positions he happened to meet, not him.

Exact-match scoring. "Took it" means he played the engine's exact move. If pin
positions usually have several near-equal good moves and free material usually
has one, then he loses credit on pins for playing something just as good, and
the gap is an artefact of the scoring rather than his eyesight. This is the one
that would quietly invert the finding, so it gets the MultiPV data: how often
was a second move within 30cp of the best, per shape.

The tie check can only run on the enriched games, which are the only ones with
alternatives stored. Its counts are therefore small and it is read as a
direction, not a rate.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.opportunity_gate import observe, shape_of_best_move  # noqa: E402

GAP = 30
MIN_PER_HALF = 50


async def main_async(user_id: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    moves = await db.move_observations.find(
        {"user_id": user_id, "fen_before": {"$ne": None}, "move_uci": {"$ne": None}},
        {"_id": 0, "game_id": 1, "fen_before": 1, "move_uci": 1}).to_list(80000)
    game_ids = list({m["game_id"] for m in moves if m.get("game_id")})
    best = {}
    async for doc in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for row in ((doc.get("stockfish_analysis") or {}).get("move_evaluations") or []):
            if row.get("fen_before"):
                best[(doc["game_id"], row["fen_before"])] = (
                    row.get("best_move_uci") or row.get("best_move"))

    games = sorted(game_ids)
    half_of = {g: i % 2 for i, g in enumerate(games)}
    halves = collections.defaultdict(lambda: [[0, 0], [0, 0]])
    for m in moves:
        seen = observe(m["fen_before"],
                       best.get((m.get("game_id"), m["fen_before"])),
                       m.get("move_uci"))
        if not seen:
            continue
        slot = halves[seen["pattern"]][half_of[m["game_id"]]]
        slot[0] += 1
        slot[1] += 1 if seen["took"] else 0

    print("=" * 72)
    print("  CONTROL 1 -- does each shape hold up across his own games")
    print("=" * 72)
    for name, (a, b) in sorted(halves.items(), key=lambda kv: -sum(
            h[0] for h in kv[1])):
        tot = a[0] + b[0]
        if min(a[0], b[0]) < MIN_PER_HALF:
            print("   %-18s %4d chances -- halves too small to split" % (name, tot))
            continue
        ra, rb = a[1] / a[0], b[1] / b[0]
        print("   %-18s %4d chances   odd %.0f%% (%d) / even %.0f%% (%d)   %s"
              % (name, tot, 100 * ra, a[0], 100 * rb, b[0],
                 "steady" if abs(ra - rb) <= 0.08 else "DISAGREE"))

    print("\n" + "=" * 72)
    print("  CONTROL 2 -- is exact-match scoring unfair to some shapes")
    print("=" * 72)
    rows = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": True}, {"_id": 0}).to_list(20000)
    ties = collections.defaultdict(lambda: [0, 0, 0])   # shape -> [n, tied, sound-but-not-best]
    for r in rows:
        scored = [(a["cp"], a["move_uci"]) for a in (r.get("root_alternatives") or [])
                  if isinstance(a.get("cp"), (int, float)) and a.get("mate") is None]
        if not scored:
            continue
        top_cp, best_uci = max(scored)
        shape = shape_of_best_move(r["fen"], best_uci)
        if shape is None:
            continue
        sound = [u for cp, u in scored if top_cp - cp <= GAP]
        slot = ties[shape]
        slot[0] += 1
        if len(sound) > 1:
            slot[1] += 1
        played = str(r.get("played_uci"))
        if played != str(best_uci) and played in sound:
            slot[2] += 1
    print("   of the chances of each shape, how often another move was just as")
    print("   good -- and how often he played one of those instead of the best")
    for name, (n, tied, alt) in sorted(ties.items(), key=lambda kv: -kv[1][0]):
        if n < 20:
            print("   %-18s %3d chances -- too few" % (name, n))
            continue
        print("   %-18s %3d chances   another move just as good in %3d (%.0f%%)"
              "   he played one in %2d (%.0f%%)"
              % (name, n, tied, 100.0 * tied / n, alt, 100.0 * alt / n))
    print("\n   If pins showed many more ties than free material, the shape gap")
    print("   would be a scoring artefact. Read the two tie columns, not the")
    print("   take rates, to decide that.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    return asyncio.run(main_async(args.user))


if __name__ == "__main__":
    raise SystemExit(main())
