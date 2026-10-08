"""The two halves of "how good am I with tactics".

Half one, FINDING THEM, over every game with analysis. Runs the existing
opportunity gate, which is the only honest denominator we have: a count of
missed forks means nothing, a count of missed forks out of the forks that were
on the board is knowledge. The loose question ("a fork-shaped move exists")
measures how generous the detector is, not the player -- 11.2% taken against
51.7% for the gated question, measured 2026-09-28.

Half two, GIVING THEM AWAY, over the enriched games only. The same gate, turned
round: after the player moves, does the OPPONENT'S best move create a tactical
shape? This half is impossible on the main corpus because move_evaluations
stores only the player's own moves, so the opponent has no engine truth there.
The enriched games analysed both sides, which is what makes it askable at all.

NO PER-MOTIF VERDICT IS PRINTED, and that is deliberate. The gate's own
measurement says a single pattern's take rate does not describe a person -- fork
take-rate across halves of a player's games runs r = +0.41, +0.33, +0.57,
non-monotonic, which is noise. Pooled it is r = +0.70 to +0.73, flat at every
bar. So "you are good at forks and bad at pins" is exactly the sentence the data
refuses to support, however much it sounds like an answer. The per-pattern
counts are printed as what the gate calls them -- how a drill gets chosen.
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

from services.opportunity_gate import (  # noqa: E402
    GATE_VERSION, MIN_CHANCES_TO_JUDGE, observe, pooled_knowledge,
    shape_of_best_move,
)


def line(label, chances, took, width=18):
    if not chances:
        print("   %-*s no chances found" % (width, label))
        return
    print("   %-*s %5d chances   took %4d   (%.0f%%)%s"
          % (width, label, chances, took, 100.0 * took / chances,
             "" if chances >= MIN_CHANCES_TO_JUDGE else "   <- too few to judge"))


async def main_async(user_id: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    print("gate: %s" % GATE_VERSION)

    # ── half one: did he find them ──────────────────────────────────────
    moves = await db.move_observations.find(
        {"user_id": user_id, "fen_before": {"$ne": None},
         "move_uci": {"$ne": None}},
        {"_id": 0, "game_id": 1, "fen_before": 1, "move_uci": 1},
    ).to_list(80000)
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

    rows = []
    per_game = collections.defaultdict(lambda: [0, 0])
    for m in moves:
        seen = observe(m["fen_before"],
                       best.get((m.get("game_id"), m["fen_before"])),
                       m.get("move_uci"))
        if seen:
            rows.append(seen)
            per_game[m["game_id"]][0] += 1
            per_game[m["game_id"]][1] += 1 if seen["took"] else 0
    pooled = pooled_knowledge(rows)

    print("\n" + "=" * 70)
    print("  FINDING THEM -- %d of your moves, across %d games"
          % (len(moves), len(game_ids)))
    print("=" * 70)
    line("all shapes", pooled["chances"], pooled["took"])
    print("   judgeable: %s" % pooled["judgeable"])

    # Stability on HIS OWN games, odd against even. The gate measured this
    # across players; this re-measures it for him, because a population trait
    # is not a promise about any one person in it.
    games = sorted(per_game)
    halves = [[0, 0], [0, 0]]
    for i, g in enumerate(games):
        c, t = per_game[g]
        halves[i % 2][0] += c
        halves[i % 2][1] += t
    if min(h[0] for h in halves) >= MIN_CHANCES_TO_JUDGE:
        a = halves[0][1] / halves[0][0]
        b = halves[1][1] / halves[1][0]
        print("   odd games %.0f%% (%d chances) against even %.0f%% (%d) -> %s"
              % (100 * a, halves[0][0], 100 * b, halves[1][0],
                 "steady" if abs(a - b) <= 0.08 else "HALVES DISAGREE"))

    print("\n   by shape -- the gate's words: this chooses a drill, it does not")
    print("   describe you. One pattern's rate is noise at these counts.")
    for name, slot in sorted(pooled["by_pattern"].items(),
                             key=lambda kv: -kv[1]["chances"]):
        line(name, slot["chances"], slot["took"], 18)

    # ── half two: did he hand them over ────────────────────────────────
    opp = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": False},
        {"_id": 0, "game_id": 1, "ply": 1, "fen": 1, "played_uci": 1,
         "root_alternatives": 1}).to_list(20000)
    print("\n" + "=" * 70)
    print("  GIVING THEM AWAY -- %d opponent positions (enriched games only)"
          % len(opp))
    print("=" * 70)
    if not opp:
        print("   no enriched opponent positions for this player")
        return 0
    given = collections.Counter()
    taken_by_them = collections.Counter()
    for o in opp:
        scored = [(a["cp"], a["move_uci"]) for a in (o.get("root_alternatives") or [])
                  if isinstance(a.get("cp"), (int, float)) and a.get("mate") is None]
        if not scored:
            continue
        best_uci = max(scored)[1]
        shape = shape_of_best_move(o["fen"], best_uci)
        if shape is None:
            continue
        given[shape] += 1
        if str(o.get("played_uci")) == str(best_uci):
            taken_by_them[shape] += 1
    total = sum(given.values())
    tot_taken = sum(taken_by_them.values())
    print("   you handed the opponent a tactical shape %d times" % total)
    print("   they played it %d times  (%.0f%%)"
          % (tot_taken, 100.0 * tot_taken / max(total, 1)))
    print("   per 100 of your moves: %.1f handed over"
          % (100.0 * total / max(len(opp), 1)))
    print()
    for name, n in given.most_common():
        line(name, n, taken_by_them[name], 18)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    return asyncio.run(main_async(args.user))


if __name__ == "__main__":
    raise SystemExit(main())
