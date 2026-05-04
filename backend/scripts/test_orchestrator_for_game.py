"""
Run the voice orchestrator directly on a game's stored V5 data.

Bypasses the lazy-regeneration route. If this prints the pivot-aware
TRUTH for Game 2085 ("Move 31 — they blundered, you blundered right
back."), the new logic works and the issue is route/regeneration timing.

Usage:
    python scripts/test_orchestrator_for_game.py <game_id>
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def main(game_id: str) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})

    if not game or not analysis:
        print(f"Missing game or analysis for {game_id}")
        client.close()
        return

    v5 = analysis.get("decryption_v5_data") or []
    move_evals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    user_color = game.get("user_color") or "white"
    game_result = game.get("result") or "*"

    if not v5:
        print(f"No decryption_v5_data on {game_id}")
        client.close()
        return

    print(f"V5 data has {len(v5)} entries")
    user_count = sum(1 for m in v5 if m.get("is_user_move"))
    print(f"  user moves: {user_count}")
    print(f"  user_color={user_color}  result={game_result}")
    print()

    # Probe pivot detector directly.
    from services.decryption_voice.truth_line import detect_pivot_move, pick_critical_move
    pivot = detect_pivot_move(v5)
    crit = pick_critical_move(v5)
    print(f"detect_pivot_move    -> {pivot.get('move_san') if pivot else 'NONE'}"
          + (f" on move {pivot.get('move_number')}" if pivot else ""))
    print(f"pick_critical_move   -> {crit}")
    print()

    # Run the full orchestrator.
    from services.decryption_voice.orchestrator import generate_post_game_voice
    truth, player, plan = await generate_post_game_voice(
        decryption_v5_data=v5,
        move_evaluations=move_evals,
        game_id=game_id,
        game_result=game_result,
        user_color=user_color,
        termination=game.get("termination", "unknown"),
        accuracy=(analysis.get("stockfish_analysis") or {}).get("accuracy", 0),
    )

    print("─── ORCHESTRATOR LIVE OUTPUT ───")
    print()
    print("TRUTH:")
    if truth:
        for k, v in truth.items():
            print(f"  {k}: {v}")
    else:
        print("  (None)")
    print()
    print("PLAYER DECRYPTION:")
    if player:
        for k, v in player.items():
            print(f"  {k}: {v}")
    else:
        print("  (None)")
    print()
    print("PLAN DECRYPTION:")
    if plan:
        print(f"  text: {plan.get('text', '')}")
        print(f"  source: {plan.get('source')}  attempts: {plan.get('attempts')}")
    else:
        print("  (None)")

    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("game_id")
    args = p.parse_args()
    asyncio.run(main(args.game_id))
