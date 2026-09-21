"""Harvest specific-question onboarding puzzles from real games.

Mohit, 2026-09-20: ask "find a fork here" / "save your king from mate" rather
than "find the best move", start easy, get harder when they answer right.

This walks real games position by position and keeps only those where exactly
ONE legal move satisfies the question the player will read. Supply is reported
per family so the question set is decided by what we can actually grade, not
by what sounds good -- the families that yield nothing do not ship.

    python scripts/harvest_onboarding_puzzles.py --games 300
    python scripts/harvest_onboarding_puzzles.py --games 2000 --write

Without --write it only counts. With --write it upserts into
`onboarding_puzzles`, keyed on (fen, family) so a re-run is idempotent.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import io
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

from services.onboarding_puzzle_builder import build_puzzle, families

COLLECTION = "onboarding_puzzles"

# Skip the opening: book positions have no tactics and every game shares them,
# so they would flood the pool with duplicates.
MIN_PLY = 12

PROBE_ERRORS: collections.Counter = collections.Counter()


def _positions(pgn: str, limit: int = 120):
    """Every position in the game, with the ply that reached it."""
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception as exc:  # noqa: BLE001
        PROBE_ERRORS[f"pgn: {type(exc).__name__}"] += 1
        return
    if game is None:
        return
    board = game.board()
    for ply, move in enumerate(game.mainline_moves()):
        board.push(move)
        if ply >= MIN_PLY and ply < limit:
            yield ply, board.fen()


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=300)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    found: Dict[str, int] = collections.Counter()
    samples: Dict[str, List] = collections.defaultdict(list)
    positions = 0
    scanned = 0
    written = 0

    cursor = db.games.find({"pgn": {"$exists": True, "$ne": None}},
                           {"game_id": 1, "pgn": 1}).limit(args.games)
    async for game in cursor:
        scanned += 1
        for ply, fen in _positions(game.get("pgn") or ""):
            positions += 1
            for family in families():
                try:
                    puzzle = build_puzzle(fen, family)
                except Exception as exc:  # noqa: BLE001
                    PROBE_ERRORS[f"{family}: {type(exc).__name__}: {exc}"[:80]] += 1
                    continue
                if not puzzle:
                    continue
                found[family] += 1
                if len(samples[family]) < 3:
                    samples[family].append(puzzle)
                if args.write:
                    await db[COLLECTION].update_one(
                        {"fen": puzzle.fen, "family": puzzle.family},
                        {"$set": {
                            "fen": puzzle.fen,
                            "family": puzzle.family,
                            "question": puzzle.question,
                            "answer_uci": puzzle.answer_uci,
                            "answer_san": puzzle.answer_san,
                            "explanation": puzzle.explanation,
                            "difficulty": puzzle.difficulty,
                            "source_game_id": game.get("game_id"),
                            "source_ply": ply,
                        }},
                        upsert=True)
                    written += 1

    print(f"games scanned    : {scanned}")
    print(f"positions tested : {positions}")
    print()
    print(f"{'family':24s} {'puzzles':>8s} {'per game':>9s}")
    for family in families():
        n = found[family]
        print(f"{family:24s} {n:8d} {n / max(scanned, 1):9.2f}")
    print()
    for family, rows in samples.items():
        print(f"-- {family}")
        for p in rows:
            print(f"     {p.answer_san:7s}  {p.question}")
            print(f"              {p.explanation}")
    if PROBE_ERRORS:
        print()
        print("PROBE FAILURES -- these are a bug, not a finding:")
        for detail, n in PROBE_ERRORS.most_common(6):
            print(f"   {n:5d}x  {detail}")
    if args.write:
        print()
        print(f"upserted into {COLLECTION}: {written}")
    return 1 if PROBE_ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
