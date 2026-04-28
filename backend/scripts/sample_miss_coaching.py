"""
Sample the puzzle-miss coaching output against real puzzles.

Picks N random Lichess puzzles from the DB, simulates the user
"playing the wrong move" by choosing a plausible-looking but
incorrect alternative, then runs build_miss_coaching and prints
each output for human review.

Usage:
    python scripts/sample_miss_coaching.py            # 10 samples
    python scripts/sample_miss_coaching.py --n 25
    python scripts/sample_miss_coaching.py --themes fork,pin,skewer
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
from motor.motor_asyncio import AsyncIOMotorClient

from services.puzzle_miss_coaching import build_miss_coaching


def _pick_wrong_move(fen: str, correct_uci: str) -> tuple:
    """Pick a plausible but wrong move from the position. Prefer a
    quiet developing move; fall back to any legal move that isn't
    the correct one."""
    board = chess.Board(fen)
    legal = list(board.legal_moves)
    correct = chess.Move.from_uci(correct_uci) if correct_uci else None
    candidates = [m for m in legal if m != correct]
    if not candidates:
        return ("", "")
    # Prefer non-captures (more "I missed the tactic" feel)
    non_captures = [m for m in candidates if not board.is_capture(m)]
    pick = random.choice(non_captures or candidates)
    san = board.san(pick)
    return (san, pick.uci())


async def main(n: int, theme_filter: list[str] | None) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    query = {}
    if theme_filter:
        query["themes"] = {"$in": theme_filter}

    total = await db.lichess_puzzles.count_documents(query)
    if total == 0:
        print("No puzzles match the filter.")
        return
    print(f"Sampling {n} of {total:,} puzzles "
          + (f"(themes: {theme_filter})" if theme_filter else "(all themes)"))
    print("=" * 70)

    # Use $sample for a true random pull
    pipeline = [{"$match": query}, {"$sample": {"size": n}}]
    samples = []
    async for p in db.lichess_puzzles.aggregate(pipeline):
        samples.append(p)

    for i, p in enumerate(samples, 1):
        fen = p.get("fen", "")
        moves = p.get("moves") or []
        if not fen or len(moves) < 2:
            continue
        # Lichess: first move is opponent's setup. Apply it; the rest
        # is the user's solution.
        try:
            board = chess.Board(fen)
            opp = chess.Move.from_uci(moves[0])
            board.push(opp)
        except Exception:
            continue
        challenge_fen = board.fen()
        solution_uci = moves[1]
        try:
            solution_san = board.san(chess.Move.from_uci(solution_uci))
        except Exception:
            continue

        wrong_san, wrong_uci = _pick_wrong_move(challenge_fen, solution_uci)
        if not wrong_san:
            continue

        themes = p.get("themes") or []
        # Pick a representative cognitive_gap for takeaway flavor.
        gap = None
        if "fork" in themes:
            gap = "missed_tactic"
        elif "pin" in themes or "skewer" in themes:
            gap = "tactical_oversight"
        elif "hangingPiece" in themes:
            gap = "piece_safety"
        elif "endgame" in themes:
            gap = "endgame_technique"

        pv_after_best = moves[1:]  # solution sequence

        coaching = build_miss_coaching(
            fen_before=challenge_fen,
            played_move_san=wrong_san,
            played_move_uci=wrong_uci,
            best_move_san=solution_san,
            best_move_uci=solution_uci,
            pv_after_best=pv_after_best,
            cognitive_gap=gap,
            themes=themes,
        )

        print(f"\n── Sample {i}/{len(samples)} ─────────────────────")
        print(f"Themes: {themes[:5]}")
        print(f"Rating: {p.get('rating')}")
        print(f"FEN:    {challenge_fen}")
        print(f"User played: {wrong_san}    Best: {solution_san}")
        print(f"Gap (mapped): {gap}")
        print()
        if not coaching:
            print("  (build_miss_coaching returned None)")
            continue
        print(f"  Position:    {coaching['position_summary']}")
        if coaching["opponent_threats"]:
            print("  Threats:")
            for t in coaching["opponent_threats"]:
                print(f"    - {t}")
        else:
            print("  Threats:     (none — quiet position)")
        print(f"  Critique:    {coaching['played_critique']}")
        print(f"  Best idea:   {coaching['best_move_idea']}")
        print(f"  Takeaway:    {coaching['takeaway']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--themes", default="",
                        help="Comma-separated themes to filter by")
    args = parser.parse_args()
    themes = [t.strip() for t in args.themes.split(",") if t.strip()] or None
    asyncio.run(main(n=args.n, theme_filter=themes))
