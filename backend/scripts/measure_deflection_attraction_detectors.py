"""Measure the deflection and attraction proofs against Lichess theme labels.

Lichess theme tags are the truth source. Recall is measured on puzzles that
carry the detector's own theme; cross-fire is measured on puzzles of two
OTHER themes with the detector's own theme excluded, because a detector that
fires on everything has no signal no matter how high its recall climbs.

Run inside the backend container, which has the 4.1M-row `lichess_puzzles`
collection:

    python backend/scripts/measure_deflection_attraction_detectors.py

Flags:
    --recall N        puzzles per theme for recall (default 1000)
    --crossfire N     puzzles per foreign theme (default 300)
    --misses N        print N missed puzzles per theme for cluster analysis
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.attraction_puzzle_proof import build_attraction_proof  # noqa: E402
from services.deflection_puzzle_proof import build_deflection_proof  # noqa: E402


# Any cp_loss above the 100 floor the proof families share. The Lichess
# puzzles carry no stored cp_loss, and the gate under test is the motif
# geometry, not the severity filter.
SYNTHETIC_CP_LOSS = 250

RATING_LO, RATING_HI = 600, 1500


def prep(puzzle):
    """Rebuild the solver position. The stored fen is BEFORE the opponent move."""
    board = chess.Board(puzzle["fen"])
    moves = puzzle.get("moves") or []
    if len(moves) < 2:
        return None
    try:
        first = chess.Move.from_uci(moves[0])
        if first not in board.legal_moves:
            return None
        board.push(first)
        solution = chess.Move.from_uci(moves[1])
        if solution not in board.legal_moves:
            return None
        best = board.san(solution)
        played = next(
            (board.san(m) for m in board.legal_moves if m != solution), None
        )
        if not played:
            return None
        pv = []
        probe = board.copy()
        for uci in moves[1:]:
            move = chess.Move.from_uci(uci)
            if move not in probe.legal_moves:
                break
            pv.append(probe.san(move))
            probe.push(move)
        return board, played, best, pv[1:]
    except (ValueError, AssertionError, KeyError):
        return None


async def load(db, theme, count, exclude=()):
    out = []
    cursor = db.lichess_puzzles.find(
        {"themes": theme, "rating": {"$gte": RATING_LO, "$lte": RATING_HI}}
    ).limit(count * 6)
    async for puzzle in cursor:
        themes = puzzle.get("themes") or []
        if exclude and any(x in themes for x in exclude):
            continue
        ready = prep(puzzle)
        if ready:
            out.append((puzzle, ready))
        if len(out) >= count:
            break
    return out


def fires(builder, ready):
    board, played, best, pv = ready
    try:
        bundle = builder(board, played, best, pv, SYNTHETIC_CP_LOSS)
    except Exception:
        return None
    if bundle is None or not bundle.verifier.verified:
        return None
    return bundle


def run(name, builder, samples):
    hits, misses = 0, []
    for puzzle, ready in samples:
        if fires(builder, ready) is not None:
            hits += 1
        else:
            misses.append((puzzle, ready))
    total = len(samples)
    pct = 100.0 * hits / total if total else 0.0
    print(f"  {name:<34} {hits:>4}/{total:<4} = {pct:5.1f}%")
    return hits, total, misses


def show_misses(misses, limit):
    for puzzle, ready in misses[:limit]:
        board, _played, best, pv = ready
        print(
            f"    MISS {puzzle.get('puzzle_id') or puzzle.get('_id')} "
            f"r{puzzle.get('rating')} {best} {pv} "
            f"themes={sorted(t for t in (puzzle.get('themes') or []))}"
        )
        print(f"         {board.fen()}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recall", type=int, default=1000)
    parser.add_argument("--crossfire", type=int, default=300)
    parser.add_argument("--misses", type=int, default=0)
    args = parser.parse_args()

    db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=30000
    )[os.environ.get("DB_NAME", "chess_coach")]

    detectors = (
        ("deflection", build_deflection_proof),
        ("attraction", build_attraction_proof),
    )

    for theme, builder in detectors:
        print(f"\n=== {theme} ===")
        recall_set = await load(db, theme, args.recall)
        _hits, _total, misses = run(f"recall on {theme}", builder, recall_set)
        if args.misses:
            show_misses(misses, args.misses)
        for foreign in ("mateIn2", "fork"):
            sample = await load(db, foreign, args.crossfire, exclude=(theme,))
            run(f"cross-fire on {foreign}", builder, sample)


if __name__ == "__main__":
    asyncio.run(main())
