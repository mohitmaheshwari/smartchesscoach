"""
Force-regenerate Truth + Player + Plan Decryption for a game and write
back to MongoDB. Bypasses the route's regen path entirely.

Use when the route's lazy-regeneration didn't pick up new code (e.g.,
the doc still has stale truth_line/player_decryption from a previous
regen). Reads the existing decryption_v5_data unchanged — only updates
the voice surfaces.

Usage:
    python scripts/force_voice_regen.py <game_id>
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
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
        print(f"No decryption_v5_data on {game_id} — cannot regenerate voice without it")
        client.close()
        return

    print(f"Regenerating voice for {game_id} (v5 has {len(v5)} moves)...", flush=True)

    from services.decryption_voice.orchestrator import generate_post_game_voice
    truth, player, plan, evidence = await generate_post_game_voice(
        decryption_v5_data=v5,
        move_evaluations=move_evals,
        game_id=game_id,
        game_result=game_result,
        user_color=user_color,
        termination=game.get("termination", "unknown"),
        accuracy=(analysis.get("stockfish_analysis") or {}).get("accuracy", 0),
    )

    print(f"  truth_line       : {'OK' if truth else 'None'}", flush=True)
    print(f"  player_decryption: {'OK' if player else 'None'}", flush=True)
    print(f"  decryption_block : {'OK' if plan else 'None'}", flush=True)
    print(f"  pattern_evidence : {'OK' if evidence else 'None'}", flush=True)

    result = await db.game_analyses.update_one(
        {"game_id": game_id},
        {"$set": {
            "truth_line": truth,
            "player_decryption": player,
            "decryption_block": plan,
            "pattern_evidence": evidence,
            "voice_regenerated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    print(f"  modified: {result.modified_count}", flush=True)

    if truth:
        print(flush=True)
        print("TRUTH (now in DB):", flush=True)
        print(f"  {truth.get('identity')}", flush=True)
        print(f"  {truth.get('anchor')}", flush=True)
        print(f"  {truth.get('trigger')}", flush=True)

    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("game_id")
    args = p.parse_args()
    asyncio.run(main(args.game_id))
