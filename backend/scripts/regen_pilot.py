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


def _p(*args, **kwargs):
    """Unbuffered print so progress shows up immediately in `docker exec`."""
    print(*args, **kwargs, flush=True)


async def regen_one(db, gid: str, idx: int, total: int) -> None:
    t0 = time.time()
    _p(f"\n[{idx}/{total}] {gid[:8]} — loading game record...")
    game = await db.games.find_one(
        {"game_id": gid},
        {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1},
    )
    a = await db.game_analyses.find_one(
        {"game_id": gid},
        {"_id": 0, "stockfish_analysis": 1, "user_id": 1},
    )
    if not game or not a:
        _p(f"  {gid[:8]} SKIP (game or analysis missing)")
        return

    user_id = game.get("user_id") or a.get("user_id")
    user_color = game.get("user_color") or "white"
    pgn = game.get("pgn", "")
    move_evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
    _p(f"  user_color={user_color}  stockfish_moves={len(move_evals)}")

    from services.game_decryption_v5_service import (
        generate_game_decryption_v5,
        V5_COACHING_VERSION,
    )

    _p(f"  running generate_game_decryption_v5 (this is the slow part)...")
    t_v5 = time.time()
    decryption_data = await generate_game_decryption_v5(
        pgn, user_color, move_evals, user_id, db
    )
    _p(f"  V5 generation done in {time.time() - t_v5:.1f}s, {len(decryption_data or [])} move records")

    await db.game_analyses.update_one(
        {"game_id": gid},
        {"$set": {
            "decryption_v5_data": decryption_data,
            "decryption_v5_version": V5_COACHING_VERSION,
            "decryption_v5_generated_at": datetime.now(timezone.utc),
            "decryption_v5_generating": False,
        }},
    )
    _p(f"  saved decryption_v5_data with version={V5_COACHING_VERSION}")

    from services.llm_caption_generator import (
        annotate_runtime_facts,
        has_teaching_signal,
        generate_caption_for_move,
    )

    annotate_runtime_facts(decryption_data)

    # Count moves needing captions first, so progress is meaningful.
    teaching_indices = [i for i, m in enumerate(decryption_data) if has_teaching_signal(m)]
    _p(f"  regenerating captions on {len(teaching_indices)} teaching moves...")

    pawn_fork_hits = []
    for n, i in enumerate(teaching_indices, 1):
        m = decryption_data[i]
        cap = await generate_caption_for_move(m)
        await db.game_analyses.update_one(
            {"game_id": gid},
            {"$set": {f"decryption_v5_data.{i}.caption_llm": cap}},
        )
        if m.get("shape_pattern_id") == "pawn_fork":
            pawn_fork_hits.append((m.get("move_number"), m.get("move_san"), cap))
        # Print every 10 captions so progress is visible.
        if n % 10 == 0 or n == len(teaching_indices):
            _p(f"    {n}/{len(teaching_indices)} captions written")

    elapsed = time.time() - t0
    _p(
        f"  DONE {gid[:8]}  v{V5_COACHING_VERSION}  total_moves={len(decryption_data)}  "
        f"captions={len(teaching_indices)}  elapsed={elapsed:.1f}s"
    )
    for mn, san, cap in pawn_fork_hits:
        _p(f"    PAWN FORK on {mn}.{san}:  {cap}")


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    _p(f"Regenerating {len(GAME_IDS)} pilot games...")
    overall_start = time.time()
    for n, gid in enumerate(GAME_IDS, 1):
        try:
            await regen_one(db, gid, n, len(GAME_IDS))
        except Exception as e:
            _p(f"  {gid[:8]} FAILED: {e}")
    _p(f"\nAll games done in {time.time() - overall_start:.1f}s total.")


if __name__ == "__main__":
    asyncio.run(main())
