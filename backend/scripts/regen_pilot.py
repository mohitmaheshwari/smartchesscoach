"""
Force-regenerate decryption_v5_data + LLM captions for the 6 pilot
games used to validate the bounded-improvisation pipeline + pawn_fork
shape pattern (Mohit feedback fb_eb1d11ba227f).

Why this exists: decryption_v5_data is built lazily by routes/coach.py
keyed on V5_COACHING_VERSION. Re-queuing a game runs Stockfish but
NOT the V5 service — so new fields like pv_after_played and new
shape detectors like pawn_fork stay invisible on existing records
until someone hits the per-move endpoint via the UI. This script
bypasses that, calls generate_game_decryption_v5 directly, then
re-runs the LLM caption for every move with a teaching signal.

Usage (on prod server):
  cd /root/repos/smartchesscoach && git pull origin working-code
  docker exec chess-coach-backend python scripts/regen_pilot.py

Cost: ~250 LLM calls total → ~$0.05 on gpt-4.1-mini.
Time: ~3-5 minutes (V5 service runs Stockfish-derived analysis per move).

Output: one summary line per game, plus a PAWN FORK callout for every
move where the new detector fires (cross-game audit of false positives).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient


GAME_IDS = [
    "357901fa-a2c1-4add-a51e-480862330ea6",  # Mohit-flagged (Caro-Kann Qd6, the pawn fork test case)
    "2f178f1b-7f1d-495a-96db-603452676a91",  # TACTICAL_BLUNDER (round v3)
    "d87da8cd-a3fd-4145-8175-2da80a25de34",  # POSITIONAL_MISTAKE
    "1b196a4f-cc41-434b-9d11-112acad2906b",  # ENDGAME
    "a50ddf30-c154-4486-81d9-0219eb621440",  # OPENING_DRIFT
    "aa60d98c-acc2-453f-bde5-62f29cc4a123",  # WON_WITH_BLUNDER
]


async def regen_one(db, gid: str) -> None:
    t0 = time.time()
    game = await db.games.find_one(
        {"game_id": gid},
        {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1},
    )
    a = await db.game_analyses.find_one(
        {"game_id": gid},
        {"_id": 0, "stockfish_analysis": 1, "user_id": 1},
    )
    if not game or not a:
        print(f"  {gid[:8]} SKIP (game or analysis missing)")
        return

    user_id = game.get("user_id") or a.get("user_id")
    user_color = game.get("user_color") or "white"
    pgn = game.get("pgn", "")
    move_evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])

    from services.game_decryption_v5_service import (
        generate_game_decryption_v5,
        V5_COACHING_VERSION,
    )

    decryption_data = await generate_game_decryption_v5(
        pgn, user_color, move_evals, user_id, db
    )

    await db.game_analyses.update_one(
        {"game_id": gid},
        {"$set": {
            "decryption_v5_data": decryption_data,
            "decryption_v5_version": V5_COACHING_VERSION,
            "decryption_v5_generated_at": datetime.now(timezone.utc),
            "decryption_v5_generating": False,
        }},
    )

    from services.llm_caption_generator import (
        annotate_runtime_facts,
        has_teaching_signal,
        generate_caption_for_move,
    )

    annotate_runtime_facts(decryption_data)

    called = 0
    pawn_fork_hits = []
    for idx, m in enumerate(decryption_data):
        if not has_teaching_signal(m):
            continue
        cap = await generate_caption_for_move(m)
        called += 1
        await db.game_analyses.update_one(
            {"game_id": gid},
            {"$set": {f"decryption_v5_data.{idx}.caption_llm": cap}},
        )
        if m.get("shape_pattern_id") == "pawn_fork":
            pawn_fork_hits.append((m.get("move_number"), m.get("move_san"), cap))

    elapsed = time.time() - t0
    print(
        f"  {gid[:8]}  v{V5_COACHING_VERSION}  moves={len(decryption_data)}  "
        f"captions={called}  elapsed={elapsed:.1f}s"
    )
    for mn, san, cap in pawn_fork_hits:
        print(f"    PAWN FORK on {mn}.{san}:  {cap}")


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"Regenerating {len(GAME_IDS)} pilot games...")
    for gid in GAME_IDS:
        try:
            await regen_one(db, gid)
        except Exception as e:
            print(f"  {gid[:8]} FAILED: {e}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
