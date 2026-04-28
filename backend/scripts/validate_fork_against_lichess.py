"""
Cross-validate fork detector against Lichess-tagged fork puzzles.

Sample N puzzles from `lichess_puzzles` where themes contains "fork".
For each, apply our solution-move and run evaluate_fork. Tally:
  • detected as fork (matches Lichess tag)
  • not detected (we say "no fork" but Lichess tagged it)
  • setup error (move illegal etc.)
Plus tier breakdown for detected ones (HIGH/MEDIUM/LOW).

Output:
  Counts and a sample of disagreements (we say "no fork" but Lichess
  said yes — these are either our bug, Lichess miss-tag, or a
  pattern we haven't built yet — needs human review).

Usage:
    python scripts/validate_fork_against_lichess.py --n 100
    python scripts/validate_fork_against_lichess.py --n 200 --show-mismatches 20
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
from motor.motor_asyncio import AsyncIOMotorClient

from services.pattern_confidence.fork import evaluate_fork


async def main(n: int, show_mismatches: int) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    print(f"Cross-validating fork detector against {n} Lichess fork puzzles")
    print("=" * 65)

    # Random sample of fork-tagged puzzles
    pipeline = [
        {"$match": {"themes": "fork"}},
        {"$sample": {"size": n}},
    ]
    samples = []
    async for p in db.lichess_puzzles.aggregate(pipeline):
        samples.append(p)

    if not samples:
        print("No fork-tagged puzzles found in db.lichess_puzzles. Has the importer run?")
        return

    detected_high = 0
    detected_medium = 0
    detected_low = 0
    not_detected = 0
    setup_errors = 0
    mismatches = []

    for p in samples:
        fen = p.get("fen", "")
        moves = p.get("moves") or []
        if not fen or len(moves) < 2:
            setup_errors += 1
            continue

        try:
            board = chess.Board(fen)
            # Lichess: first move is opponent's setup move; advance.
            opp = chess.Move.from_uci(moves[0])
            if opp not in board.legal_moves:
                setup_errors += 1
                continue
            board.push(opp)

            # The second move IS the fork solution. Evaluate it.
            fork_move = chess.Move.from_uci(moves[1])
            if fork_move not in board.legal_moves:
                setup_errors += 1
                continue
        except Exception:
            setup_errors += 1
            continue

        result = evaluate_fork(board, fork_move)

        if not result.get("detected"):
            not_detected += 1
            if len(mismatches) < show_mismatches:
                # Build a visual position for the human reviewer
                fork_san = ""
                try:
                    fork_san = board.san(fork_move)
                except Exception:
                    pass
                mismatches.append({
                    "puzzle_id": p.get("puzzle_id"),
                    "rating": p.get("rating"),
                    "themes": p.get("themes"),
                    "fen": board.fen(),
                    "fork_move_san": fork_san,
                    "fork_move_uci": moves[1],
                    "reason": result.get("reason"),
                })
            continue

        tier = result.get("tier")
        if tier == "HIGH":
            detected_high += 1
        elif tier == "MEDIUM":
            detected_medium += 1
        else:
            detected_low += 1

    total_evaluated = len(samples) - setup_errors
    detected_total = detected_high + detected_medium + detected_low

    print()
    print(f"Sampled:            {len(samples)}")
    print(f"Setup errors:       {setup_errors}")
    print(f"Evaluated:          {total_evaluated}")
    print()
    print(f"Detected as fork:   {detected_total}  "
          f"({100*detected_total/max(total_evaluated,1):.1f}% of evaluated)")
    print(f"  HIGH tier:        {detected_high}")
    print(f"  MEDIUM tier:      {detected_medium}")
    print(f"  LOW tier:         {detected_low}")
    print()
    print(f"Not detected:       {not_detected}  "
          f"(Lichess says fork, we don't)")

    if mismatches:
        print()
        print(f"── Sample mismatches ({len(mismatches)}) ──")
        print("These are puzzles Lichess tagged 'fork' that our detector")
        print("rejected. Each is either:")
        print("  (a) a real fork we missed (our bug)")
        print("  (b) Lichess mis-tag (puzzle isn't really a fork)")
        print("  (c) a fork pattern we haven't built (pinned forker, etc.)")
        print()
        for m in mismatches:
            print(f"  ID {m['puzzle_id']}  rating={m['rating']}")
            print(f"    themes: {m['themes']}")
            print(f"    fen:    {m['fen']}")
            print(f"    move:   {m['fork_move_san']} ({m['fork_move_uci']})")
            print(f"    reason: {m['reason']}")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--show-mismatches", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(main(n=args.n, show_mismatches=args.show_mismatches))
