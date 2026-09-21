"""Measure `defensive_move_puzzle_proof` against Lichess's own theme labels.

Lichess's theme tags are the truth source: every `defensiveMove` puzzle the
detector stays silent on is a bug report, and every `fork` or `mateIn2` puzzle
it fires on is cross-fire.

Run it inside the backend container, which has the puzzle corpus:

    docker cp backend/scripts/measure_defensive_move_detector.py \
        chess-coach-backend:/tmp/m.py
    docker exec chess-coach-backend python /tmp/m.py

Options: --recall N (default 1000), --crossfire N (default 300), --show N to
print that many misses as boards so they can be played rather than counted.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.defensive_move_puzzle_proof import (  # noqa: E402
    build_defensive_move_proof,
)

# The stored `fen` is the position BEFORE the opponent's setup move, so
# moves[0] has to be pushed before the solver is on move. Getting this wrong
# silently measures the wrong side of every puzzle.
SYNTHETIC_CP_LOSS = 250


def prepare(puzzle):
    board = chess.Board(puzzle["fen"])
    moves = puzzle.get("moves") or []
    if len(moves) < 2:
        return None
    try:
        setup = chess.Move.from_uci(moves[0])
        if setup not in board.legal_moves:
            return None
        board.push(setup)
        best = chess.Move.from_uci(moves[1])
        if best not in board.legal_moves:
            return None
        best_san = board.san(best)
        played = next(
            (board.san(m) for m in board.legal_moves if m != best), None
        )
        if played is None:
            return None
        line = []
        replay = board.copy()
        for uci in moves[1:]:
            move = chess.Move.from_uci(uci)
            if move not in replay.legal_moves:
                break
            line.append(replay.san(move))
            replay.push(move)
        return board, played, best_san, line[1:]
    except (ValueError, AssertionError):
        return None


async def sample(db, theme, limit, exclude=()):
    out = []
    cursor = db.lichess_puzzles.find(
        {"themes": theme, "rating": {"$gte": 600, "$lte": 1500}}
    ).limit(limit * 5)
    async for puzzle in cursor:
        if any(tag in (puzzle.get("themes") or []) for tag in exclude):
            continue
        prepared = prepare(puzzle)
        if prepared:
            out.append((puzzle, prepared))
        if len(out) >= limit:
            break
    return out


def run_batch(batch, show=0):
    stats = Counter()
    payoffs = Counter()
    shown = 0
    for puzzle, (board, played, best, line) in batch:
        stats["n"] += 1
        bundle = build_defensive_move_proof(
            board, played, best, line, SYNTHETIC_CP_LOSS
        )
        if bundle is None:
            if shown < show:
                shown += 1
                print("-" * 66)
                print("MISS", puzzle["puzzle_id"], puzzle["rating"], puzzle["themes"])
                print(board.unicode(invert_color=True, empty_square="."))
                print("line:", " ".join([best] + list(line)))
            continue
        stats["detector"] += 1
        if bundle.verifier.verified:
            stats["verified"] += 1
            payoffs[bundle.detector.facts[0]["threat_kind"]] += 1
            holding = bundle.detector.facts[0]["holding_move_count"]
            if holding == 1:
                stats["only_move"] += 1
        else:
            stats["detector_only"] += 1
            if shown < show:
                shown += 1
                print("-" * 66)
                print(
                    "UNVERIFIED", puzzle["puzzle_id"], puzzle["rating"],
                    puzzle["themes"],
                )
                print(board.unicode(invert_color=True, empty_square="."))
                print("line:", " ".join([best] + list(line)))
                print("facts:", bundle.detector.facts[0])
    return stats, payoffs


def report(label, stats, payoffs=None):
    n = max(stats["n"], 1)
    print(f"\n{label}  n={stats['n']}")
    print(f"  detector fires   {stats['detector'] / n * 100:5.1f}%")
    print(f"  verifier proves  {stats['verified'] / n * 100:5.1f}%")
    print(f"  only move holds  {stats['only_move'] / n * 100:5.1f}%")
    if payoffs:
        for kind, count in payoffs.most_common():
            print(f"      {kind:26s} {count / n * 100:5.1f}%")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recall", type=int, default=1000)
    parser.add_argument("--crossfire", type=int, default=300)
    parser.add_argument("--show", type=int, default=0)
    args = parser.parse_args()

    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    )
    db = client[os.environ.get("DB_NAME", "test_database")]

    batch = await sample(db, "defensiveMove", args.recall)
    stats, payoffs = run_batch(batch, show=args.show)
    report("RECALL  defensiveMove", stats, payoffs)

    for theme in ("fork", "mateIn2"):
        batch = await sample(
            db, theme, args.crossfire, exclude=("defensiveMove",)
        )
        stats, payoffs = run_batch(batch, show=args.show)
        report(f"CROSS-FIRE  {theme} (excluding defensiveMove)", stats, payoffs)


if __name__ == "__main__":
    asyncio.run(main())
