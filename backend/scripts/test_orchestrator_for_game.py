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
    from services.decryption_voice.truth_line import (
        detect_pivot_move, pick_critical_move, generate_truth_line
    )
    pivot = detect_pivot_move(v5)
    crit = pick_critical_move(v5)
    print(f"detect_pivot_move    -> {pivot.get('move_san') if pivot else 'NONE'}"
          + (f" on move {pivot.get('move_number')}" if pivot else ""), flush=True)
    print(f"pick_critical_move   -> {crit}", flush=True)
    print(flush=True)

    # ── Phase 1: classifier (sync, fast) ─────────────────────────────
    print("[1/4] classifier...", flush=True)
    try:
        from services.game_reason_classifier import classify_game_reason
        reason_result = classify_game_reason(
            move_evaluations=move_evals,
            game_result=game_result,
            user_color=user_color,
            termination=game.get("termination", "unknown"),
            accuracy=(analysis.get("stockfish_analysis") or {}).get("accuracy", 0),
        )
        game_reason = reason_result.get("category", "")
        print(f"      game_reason = {game_reason}", flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        client.close()
        return

    # ── Phase 2: Truth (deterministic) ───────────────────────────────
    print("[2/4] Truth (deterministic)...", flush=True)
    try:
        truth = generate_truth_line(
            decryption_v5_data=v5, game_reason=game_reason, game_id=game_id, user_won=False
        )
        print(f"      identity : {truth.get('identity') if truth else None}", flush=True)
        print(f"      anchor   : {truth.get('anchor') if truth else None}", flush=True)
        print(f"      trigger  : {truth.get('trigger') if truth else None}", flush=True)
        print(f"      scenario : {truth.get('scenario') if truth else None}", flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        client.close()
        return

    # ── Phase 3: Player Decryption (deterministic) ──────────────────
    print("[3/4] Player Decryption (deterministic)...", flush=True)
    try:
        from services.decryption_voice.player_decryption import build_player_decryption
        player = build_player_decryption(
            decryption_v5_data=v5, game_reason=game_reason, game_id=game_id
        )
        if player:
            print(f"      story         : {player.get('story')}", flush=True)
            print(f"      pattern       : {player.get('pattern')}", flush=True)
            print(f"      carry_forward : {player.get('carry_forward')}", flush=True)
            print(f"      scenario      : {player.get('scenario')}", flush=True)
        else:
            print("      (None)", flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        client.close()
        return

    # ── Phase 4: Plan Decryption (LLM — may be slow) ────────────────
    print("[4/4] Plan Decryption (LLM call, may take 5-15s)...", flush=True)
    try:
        from services.decryption_voice.orchestrator import generate_post_game_voice
        _, _, plan = await generate_post_game_voice(
            decryption_v5_data=v5,
            move_evaluations=move_evals,
            game_id=game_id,
            game_result=game_result,
            user_color=user_color,
            termination=game.get("termination", "unknown"),
            accuracy=(analysis.get("stockfish_analysis") or {}).get("accuracy", 0),
        )
        if plan:
            print(f"      text: {plan.get('text', '')}", flush=True)
            print(f"      source: {plan.get('source')}  attempts: {plan.get('attempts')}", flush=True)
        else:
            print("      (None)", flush=True)
    except Exception:
        import traceback
        traceback.print_exc()

    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("game_id")
    args = p.parse_args()
    asyncio.run(main(args.game_id))
