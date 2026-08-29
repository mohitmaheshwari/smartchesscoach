"""
Cross-validate fork detector against Lichess-tagged fork puzzles.

Sample N puzzles from `lichess_puzzles` where themes contains "fork".
For each, replay the full solution and run evaluate_fork on every player move.
Lichess themes describe the combination, not necessarily the first solution
move. Tally:
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


def evaluate_tagged_puzzle(p: dict) -> dict:
    """Locate the first player solution ply our fork detector recognizes."""
    fen = p.get("fen", "")
    moves = p.get("moves") or []
    if not fen or len(moves) < 2:
        return {"setup_error": True, "reason": "missing FEN or solution moves"}

    try:
        board = chess.Board(fen)
    except Exception:
        return {"setup_error": True, "reason": "invalid FEN"}

    checks = []
    for move_index, uci in enumerate(moves):
        try:
            move = chess.Move.from_uci(uci)
        except Exception:
            return {"setup_error": True, "reason": f"invalid UCI at index {move_index}"}
        if move not in board.legal_moves:
            return {"setup_error": True, "reason": f"illegal move at index {move_index}"}

        # Index 0 is the opponent's setup move. Player solution moves are
        # indexes 1, 3, 5, ... in the alternating Lichess line.
        if move_index % 2 == 1:
            try:
                san = board.san(move)
            except Exception:
                san = uci
            result = evaluate_fork(board, move)
            checks.append({
                "solution_ply": (move_index + 1) // 2,
                "move_index": move_index,
                "move_san": san,
                "move_uci": uci,
                "fen": board.fen(),
                "detected": bool(result.get("detected")),
                "tier": result.get("tier"),
                "reason": result.get("reason"),
            })
            if result.get("detected"):
                return {
                    "setup_error": False,
                    "detected": True,
                    "match": checks[-1],
                    "checks": checks,
                }
        board.push(move)

    return {
        "setup_error": False,
        "detected": False,
        "checks": checks,
        "reason": "no player solution ply matched the fork claim",
    }


async def main(n: int, show_mismatches: int, negative_n: int = 0) -> None:
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
    detected_first = 0
    detected_later = 0
    not_detected = 0
    setup_errors = 0
    mismatches = []

    for p in samples:
        evaluated = evaluate_tagged_puzzle(p)
        if evaluated.get("setup_error"):
            setup_errors += 1
            continue
        if not evaluated.get("detected"):
            not_detected += 1
            if len(mismatches) < show_mismatches:
                mismatches.append({
                    "puzzle_id": p.get("puzzle_id"),
                    "rating": p.get("rating"),
                    "themes": p.get("themes"),
                    "fen": p.get("fen"),
                    "moves": p.get("moves") or [],
                    "checks": evaluated.get("checks") or [],
                    "reason": evaluated.get("reason"),
                })
            continue

        match = evaluated["match"]
        if match["solution_ply"] == 1:
            detected_first += 1
        else:
            detected_later += 1
        tier = match.get("tier")
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
    print(f"  first player ply: {detected_first}")
    print(f"  later player ply: {detected_later}")
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
            print(f"    moves:  {' '.join(m['moves'])}")
            for check in m["checks"]:
                print(
                    f"    player ply {check['solution_ply']}: "
                    f"{check['move_san']} ({check['move_uci']}) — "
                    f"{check.get('reason')}"
                )
            print(f"    reason: {m['reason']}")
            print()

    if negative_n > 0:
        negative_pipeline = [
            {"$match": {"themes": {"$ne": "fork"}}},
            {"$sample": {"size": negative_n}},
        ]
        negative_samples = []
        async for p in db.lichess_puzzles.aggregate(negative_pipeline):
            negative_samples.append(p)

        negative_fires = []
        negative_setup_errors = 0
        for p in negative_samples:
            evaluated = evaluate_tagged_puzzle(p)
            if evaluated.get("setup_error"):
                negative_setup_errors += 1
                continue
            if evaluated.get("detected"):
                negative_fires.append({
                    "puzzle_id": p.get("puzzle_id"),
                    "rating": p.get("rating"),
                    "themes": p.get("themes"),
                    "match": evaluated.get("match"),
                })

        negative_evaluated = len(negative_samples) - negative_setup_errors
        print()
        print("── Negative-control sample (no Lichess fork tag) ──")
        print(f"Sampled:             {len(negative_samples)}")
        print(f"Setup errors:        {negative_setup_errors}")
        print(f"Evaluated:           {negative_evaluated}")
        print(
            f"Detector fires:      {len(negative_fires)} "
            f"({100*len(negative_fires)/max(negative_evaluated,1):.1f}%)"
        )
        print(
            "These are review candidates, not automatic false positives: "
            "Lichess tags can omit secondary themes."
        )
        for item in negative_fires[:show_mismatches]:
            match = item["match"] or {}
            print(
                f"  ID {item['puzzle_id']} rating={item['rating']} "
                f"themes={item['themes']}"
            )
            print(
                f"    player ply {match.get('solution_ply')}: "
                f"{match.get('move_san')} ({match.get('move_uci')}) "
                f"tier={match.get('tier')}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--show-mismatches", type=int, default=10)
    parser.add_argument(
        "--negative-n",
        type=int,
        default=0,
        help="Also sample N puzzles without a fork tag as a specificity control.",
    )
    args = parser.parse_args()
    asyncio.run(main(
        n=args.n,
        show_mismatches=args.show_mismatches,
        negative_n=args.negative_n,
    ))
