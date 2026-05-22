"""Force-regenerate specific games at the current V5_COACHING_VERSION.

Runs the full V5 pipeline (detectors + LLM polish) on each game and
writes both `caption` (deterministic) and `caption_llm` (LLM-polished)
to mongo. After running this, the games are reviewable in
/admin/captions with the "Use LLM" toggle.

Usage (run inside container — already deployed at /app/backend/scripts/):

    docker exec chess-coach-backend python /app/backend/scripts/regen_specific_games.py \\
        --game-ids fc97ee1d-ba32-4118-802f-643a3497f0c9,\\
2e99850b-64be-456f-9faf-76020dad0133,\\
e7ce2c88-0087-4e62-9fab-a47c0539f7ab,\\
6569e93f-a901-4f7a-b078-5209c9fa5c34,\\
3e1a1a93-704a-4e6c-9c72-322f0e190667

If V5_POLISH_ENABLED=true (default) and the OpenAI key allows this
server's IP, LLM-polished captions populate alongside the deterministic
ones. If the LLM call fails, caption_llm stays None and the
deterministic caption is used as the fallback (no regression).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient

from services.game_decryption_v5_service import (
    generate_game_decryption_v5,
    V5_COACHING_VERSION,
)


async def regen_one(db, game_id: str) -> dict:
    """Force-regen a single game at the current V5 version. Returns a
    summary dict with the outcome."""
    full_game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1},
    )
    full_analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "stockfish_analysis": 1, "decryption_v5_version": 1},
    )
    if not full_game or not full_analysis:
        return {"game_id": game_id, "status": "skipped", "reason": "missing game or analysis"}
    sa = full_analysis.get("stockfish_analysis") or {}
    move_evals = sa.get("move_evaluations") or sa.get("moves") or []
    if not full_game.get("pgn") or not move_evals:
        return {"game_id": game_id, "status": "skipped", "reason": "missing pgn or move_evals"}
    try:
        new_v5 = await generate_game_decryption_v5(
            full_game["pgn"],
            full_game.get("user_color", "white"),
            move_evals,
            full_game.get("user_id") or "",
            db,
        )
    except Exception as exc:
        return {"game_id": game_id, "status": "error", "reason": str(exc)}
    if not new_v5:
        return {"game_id": game_id, "status": "error", "reason": "regen returned empty"}

    await db.game_analyses.update_one(
        {"game_id": game_id},
        {"$set": {
            "decryption_v5_data": new_v5,
            "decryption_v5_version": V5_COACHING_VERSION,
            "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    # Count moves with caption_llm populated (sanity check)
    llm_count = sum(
        1 for m in new_v5
        if m.get("is_user_move") and (m.get("caption_llm") or "").strip()
    )
    user_caption_count = sum(
        1 for m in new_v5
        if m.get("is_user_move") and (m.get("caption") or "").strip()
    )
    return {
        "game_id": game_id,
        "status": "ok",
        "user_moves_with_caption": user_caption_count,
        "user_moves_with_llm": llm_count,
    }


async def main_async(game_ids: list[str]):
    url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db = AsyncIOMotorClient(url)["chess_coach"]
    print(f"Regenerating {len(game_ids)} games at v{V5_COACHING_VERSION}...")
    print(f"V5_POLISH_ENABLED={os.environ.get('V5_POLISH_ENABLED', 'true')} "
          f"V5_POLISH_MODEL={os.environ.get('V5_POLISH_MODEL', 'gpt-4.1-mini')}")
    print()
    for gid in game_ids:
        result = await regen_one(db, gid)
        if result["status"] == "ok":
            print(f"  ✓ {gid[:12]} — {result['user_moves_with_caption']} captions, "
                  f"{result['user_moves_with_llm']} LLM-polished")
        else:
            print(f"  ✗ {gid[:12]} — {result['status']}: {result.get('reason', '')}")
    print()
    print("Done. Review in /admin/captions — search by game_id prefix or FEN.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--game-ids",
        required=True,
        help="Comma-separated game_ids to regenerate.",
    )
    args = p.parse_args()
    game_ids = [g.strip() for g in args.game_ids.split(",") if g.strip()]
    if not game_ids:
        print("No game_ids provided.")
        sys.exit(1)
    asyncio.run(main_async(game_ids))


if __name__ == "__main__":
    main()
