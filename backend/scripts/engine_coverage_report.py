#!/usr/bin/env python3
"""How much of a review page can the engine explain?

Every faulted card on /game/:gameId asks the same question -- why was this
move worse than the engine's -- and move_purposes is what answers it. When
it answers nothing, write_caption refuses and the deterministic caption
stands: not silence, but not teaching either.

That number has never been watched. It was found by hand three times in
one week, each time because Mohit opened a card and read something wrong,
and each time the measurement afterwards showed a gap that had been there
for months. A gap should arrive as a falling number, not as a screenshot.

It also catches the opposite, which is easier to miss. The threat fix on
2026-10-22 LOWERED coverage from 76.2% to 74.0%, because those 2.2 points
were `answers_threat` firing on replies that threatened nothing -- 79.6%
of stored threats do. A rising number is not automatically good and a
falling one is not automatically bad; the per-kind table below is what
tells them apart.

Reads with a projection and in batches. game_analyses documents average
301 KB and an unprojected sweep of them has OOM-killed uvicorn in this
container before, so the projection is not a nicety:

    python scripts/engine_coverage_report.py               # 900 games
    python scripts/engine_coverage_report.py --games 200
    python scripts/engine_coverage_report.py --min-cp 100  # bigger faults

It prints its own peak memory on the last line rather than carrying a
figure in this docstring, which would be a number nobody re-measures after
the projection changes.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.move_purposes import purposes_for  # noqa: E402

PROJECTION = {
    "stockfish_analysis.move_evaluations": 1,
    "stockfish_analysis.opponent_move_evaluations": 1,
    "_id": 0,
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=900)
    ap.add_argument("--min-cp", type=int, default=40,
                    help="the review page shows cards down to 40cp, which "
                         "is why that is the default and not 100")
    ap.add_argument("--batch", type=int, default=100)
    args = ap.parse_args()

    url = os.environ.get("MONGO_URL")
    if not url:
        print("MONGO_URL is not set", file=sys.stderr)
        return 2
    db = AsyncIOMotorClient(url, serverSelectionTimeoutMS=20000)[
        os.environ.get("DB_NAME", "chess_coach")]

    kinds: collections.Counter = collections.Counter()
    by_band = collections.defaultdict(lambda: [0, 0])
    by_phase = collections.defaultdict(lambda: [0, 0])
    by_side = collections.defaultdict(lambda: [0, 0])
    n = covered = 0
    done = 0
    while done < args.games:
        batch = await db.game_analyses.find({}, PROJECTION) \
            .skip(done).limit(args.batch).to_list(args.batch)
        if not batch:
            break
        for d in batch:
            sa = d.get("stockfish_analysis") or {}
            for arr, is_user in (("move_evaluations", True),
                                 ("opponent_move_evaluations", False)):
                for m in (sa.get(arr) or []):
                    cp = int(m.get("cp_loss") or 0)
                    fen = m.get("fen_before")
                    if cp < args.min_cp or not fen or not m.get("best_move"):
                        continue
                    n += 1
                    ps = purposes_for(
                        fen, str(m.get("move") or ""),
                        str(m.get("best_move") or ""),
                        list(m.get("pv_after_played") or []),
                        list(m.get("pv_after_best") or []),
                        m.get("threat"), m.get("mate_info"),
                        eval_line=m.get("eval_line_played"))
                    for p in ps:
                        kinds[p["kind"]] += 1
                    hit = 1 if ps else 0
                    covered += hit
                    band = ("40-99" if cp < 100 else
                            "100-299" if cp < 300 else "300+")
                    by_band[band][0] += 1
                    by_band[band][1] += hit
                    try:
                        b = chess.Board(fen)
                        phase = ("endgame" if len(b.piece_map()) <= 12 else
                                 "opening" if b.fullmove_number <= 12
                                 else "middlegame")
                    except Exception:
                        phase = "unreadable"
                    by_phase[phase][0] += 1
                    by_phase[phase][1] += hit
                    side = "player" if is_user else "opponent"
                    by_side[side][0] += 1
                    by_side[side][1] += hit
        done += len(batch)

    if not n:
        print("no faulted cards found -- that is a fault in this script or "
              "in the corpus, not a clean bill of health")
        return 1

    print(f"games read            : {done}")
    print(f"faulted cards         : {n}  (cp_loss >= {args.min_cp}, "
          f"both sides)")
    print(f"the engine can explain: {covered}  "
          f"{100.0 * covered / n:.1f}%\n")
    print("by kind -- a kind that vanishes is a regression even when the "
          "headline holds:")
    for k, v in kinds.most_common():
        print(f"   {k:32s} {v:7d}  {100.0 * v / n:5.1f}%")
    for label, table, order in (
            ("by size of the loss", by_band, ("40-99", "100-299", "300+")),
            ("by phase", by_phase, ("opening", "middlegame", "endgame")),
            ("by whose move", by_side, ("player", "opponent"))):
        print(f"\n{label}:")
        for key in order:
            total, hit = table[key]
            if total:
                print(f"   {key:11s} n={total:7d}  "
                      f"explained {100.0 * hit / total:5.1f}%")
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(f"\npeak memory: {peak / 1024:.0f} MB over {done} games "
              f"-- an unprojected sweep of these documents has OOM-killed "
              f"uvicorn in this container before")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
