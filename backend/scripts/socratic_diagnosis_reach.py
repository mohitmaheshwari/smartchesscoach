"""
How far does the Socratic diagnosis actually reach?
===================================================


Run the deployed pipeline over real Socratic-eligible moves and record what
fundamental each one ends up with, alongside the stored gap. If the board
label 'hanging_pieces' is being proposed and then refuted far more often than
a piece really hangs, the gap fallback never gets a turn.

Reference run, 2026-09-11, 60 games, 396 eligible moves, on the code BEFORE
the fallback moved below the guard:

    fundamental=None              187   47.2%
    suppressed before R18         172   43.4%
    fundamental=hanging_pieces     21    5.3%
    fundamental=king_safety         9    2.3%
    fundamental=calculate           7    1.8%

    generic DESPITE a mappable gap: king_safety 44, missed_tactic 21,
    piece_safety 19, tactical_oversight 3  -- 87 moves, all of them thrown
    away by the hanging-piece guard before the gap was ever consulted.

    docker exec chess-coach-backend python scripts/socratic_diagnosis_reach.py
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motor.motor_asyncio import AsyncIOMotorClient
from services.caption_pipeline import (
    GAP_TO_FUNDAMENTAL,
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

DEFAULT_GAMES = 60
GATE_CP = 80


async def main():
    parser = argparse.ArgumentParser(description="socratic diagnosis reach")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES)
    args = parser.parse_args()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    outcome = Counter()
    lost = Counter()
    seen = 0

    async for doc in db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True}},
        {"_id": 0, "user_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).limit(args.games):
        for ev in doc["stockfish_analysis"]["move_evaluations"] or []:
            if ev.get("is_opponent_move"):
                continue
            if int(ev.get("cp_loss") or 0) < GATE_CP:
                continue
            fen, san, best = ev.get("fen_before"), ev.get("move"), ev.get("best_move")
            if not fen or not san:
                continue
            gap = ev.get("cognitive_gap")
            white_to_move = " w " in fen
            try:
                d = build_move_teaching_decision(
                    MoveInputs(
                        fen_before=fen, played_san=san,
                        mover_is_user=True, mover_is_white=white_to_move,
                        user_color="white" if white_to_move else "black",
                        full_move_number=int(ev.get("move_number") or 10),
                        move_history_san=[],
                        best_move_san=best,
                        eval_before_cp=ev.get("eval_before"),
                        eval_after_cp=ev.get("eval_after"),
                        cp_loss=int(ev.get("cp_loss") or 0),
                        user_rating=1200,
                        cognitive_gap=gap,
                        pv_after_played=list(ev.get("pv_after_played") or []),
                        pv_after_best=list(ev.get("pv_after_best") or []),
                        allow_fresh_engine_verification=False,
                    ),
                    CrossMoveState(),
                )
            except Exception:
                continue
            seen += 1
            facts = d.debug_facts or {}
            if not facts.get("socratic_is_active"):
                outcome["suppressed before R18"] += 1
                continue
            fundamental = facts.get("socratic_fundamental_violated")
            outcome[f"fundamental={fundamental}"] += 1
            if fundamental is None and GAP_TO_FUNDAMENTAL.get(str(gap or "").lower()):
                lost[gap] += 1

    print(f"socratic-eligible moves run through the pipeline: {seen}\n")
    for k, v in outcome.most_common():
        print(f"  {k:36} {v:5}  ({v/max(seen,1)*100:5.1f}%)")
    if lost:
        print("\n  generic DESPITE a mappable gap (the loss):")
        for gap, n in lost.most_common():
            print(f"    {gap:24} {n}")


if __name__ == "__main__":
    asyncio.run(main())
