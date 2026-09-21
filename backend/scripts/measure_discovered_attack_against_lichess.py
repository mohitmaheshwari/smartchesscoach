"""Recall and cross-fire for the discovered-attack proof, against Lichess.

Lichess's theme labels are the truth source: every `discoveredAttack` puzzle
the detector stays silent on is a bug report, and every puzzle of an unrelated
theme it DOES fire on is a precision leak.

    python scripts/measure_discovered_attack_against_lichess.py [recall_n] [crossfire_n]

Run it inside the backend container, which has the puzzle corpus:

    docker exec chess-coach-backend python \
        /app/backend/scripts/measure_discovered_attack_against_lichess.py 1000 300

The FEN convention is load-bearing. A Lichess puzzle's `fen` is the position
BEFORE the opponent's move, and `moves[0]` is that move. The solver's position
is therefore `fen` with `moves[0]` pushed, and `moves[1]` is the solution. Get
this wrong and the measurement asks the detector about a position the puzzle
was never about.

Measured 2026-09-22, rated 600-1500, `discovered_attack_puzzle_proof.v2` ->
`.v3`:

    discoveredAttack recall   54.0% -> 80.0%   (n=1000)
    discoveredCheck  recall    0.6% -> 92.8%   (n=1000)
    fork         cross-fire    0.3% ->  0.3%   (n=300, discovered themes out)
    mateIn2      cross-fire    0.0% ->  0.0%
    backRankMate cross-fire    0.0% ->  0.0%
    pin          cross-fire    0.0% ->  0.0%
"""

from __future__ import annotations

import asyncio
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.discovered_attack_puzzle_proof import (  # noqa: E402
    build_discovered_attack_proof,
)

# The detector ignores anything under 100, and the puzzle corpus carries no
# cp_loss of its own. A fixed, comfortably-above-threshold value keeps the
# measurement about the motif rather than about the severity gate.
CP_LOSS = 250
RATING_RANGE = {"$gte": 600, "$lte": 1500}
DISCOVERED_THEMES = ("discoveredAttack", "discoveredCheck")


def prepare(puzzle):
    """(solver_board, a_played_move, solution_san, rest_of_line) or None."""
    board = chess.Board(puzzle["fen"])
    moves = puzzle.get("moves") or []
    if len(moves) < 2:
        return None
    try:
        opponent = chess.Move.from_uci(moves[0])
        if opponent not in board.legal_moves:
            return None
        board.push(opponent)
        solution = chess.Move.from_uci(moves[1])
        if solution not in board.legal_moves:
            return None
        best = board.san(solution)
        played = next(
            (board.san(m) for m in board.legal_moves if m != solution), None)
        if played is None:
            return None
        line = []
        walk = board.copy()
        for uci in moves[1:]:
            move = chess.Move.from_uci(uci)
            if move not in walk.legal_moves:
                break
            line.append(walk.san(move))
            walk.push(move)
        return board, played, best, line[1:]
    except (ValueError, AssertionError, KeyError):
        return None


async def sample(db, theme, wanted, exclude=()):
    out = []
    cursor = db.lichess_puzzles.find(
        {"themes": theme, "rating": RATING_RANGE}).limit(wanted * 4)
    async for puzzle in cursor:
        if exclude and any(t in (puzzle.get("themes") or []) for t in exclude):
            continue
        prepared = prepare(puzzle)
        if prepared:
            out.append(prepared)
        if len(out) >= wanted:
            break
    return out


def fires(prepared):
    board, played, best, line = prepared
    try:
        bundle = build_discovered_attack_proof(
            board.copy(stack=False), played, best, line, CP_LOSS)
    except Exception:  # noqa: BLE001
        return None
    if not (bundle and bundle.verifier.verified):
        return None
    detector = (list(bundle.detector.facts) or [{}])[0] or {}
    verifier = (list(bundle.verifier.facts) or [{}])[0] or {}
    return (detector.get("discovery_kind"),
            verifier.get("discovery_ply_in_line") or 0)


async def report(db, theme, wanted, exclude, label):
    puzzles = await sample(db, theme, wanted, exclude)
    kinds = collections.Counter()
    plies = collections.Counter()
    hit = 0
    for prepared in puzzles:
        got = fires(prepared)
        if got:
            hit += 1
            kinds[got[0]] += 1
            plies[got[1]] += 1
    total = max(len(puzzles), 1)
    print("%-28s n=%4d  fired=%4d  %5.1f%%  kinds=%s plies=%s"
          % (label, len(puzzles), hit, 100.0 * hit / total,
             dict(kinds), dict(sorted(plies.items()))), flush=True)


async def main():
    recall_n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    crossfire_n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    await report(db, "discoveredAttack", recall_n, (), "RECALL discoveredAttack")
    await report(db, "discoveredCheck", recall_n, (), "RECALL discoveredCheck")
    for theme in ("fork", "mateIn2", "backRankMate", "pin"):
        await report(db, theme, crossfire_n, DISCOVERED_THEMES,
                     "CROSSFIRE %s" % theme)


if __name__ == "__main__":
    asyncio.run(main())
