"""
Force-regenerate decryption_v5_data on N games at the current
V5_COACHING_VERSION. Use after bumping the version for caption/text
changes that flow through the renderer (R15, narrator, resolver, etc.).

Differs from batch_voice_regen.py: that one only refreshes the voice
layer (truth_line / player_decryption / decryption_block). This one
re-runs generate_game_decryption_v5 so the per-move `caption` fields
inside decryption_v5_data pick up the new text.

Usage:
    python scripts/batch_v5_regen.py --user-id <uid> --limit 50
    python scripts/batch_v5_regen.py --user-id <uid> --limit 50 --dry-run
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def regen_one(db, game_id: str, user_id: str, *, dry_run: bool) -> dict:
    from services.game_decryption_v5_service import (
        generate_game_decryption_v5,
        V5_COACHING_VERSION,
    )

    game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
    if not game or not analysis:
        return {"status": "missing"}

    pgn = game.get("pgn", "")
    user_color = game.get("user_color") or game.get("user_plays_as", "white")
    move_evaluations = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []

    if not pgn or not move_evaluations:
        return {"status": "no_inputs"}

    stored_version = analysis.get("decryption_v5_version", 0)

    # game_id is REQUIRED: without it the service skips
    # authored_caption_overrides for every move and silently drops
    # hand-authored captions (190 docs over 29 games). It warns about
    # exactly this, and this script is a production caller -- it
    # rewrites the stored cards.
    #
    # opponent_move_evaluations likewise: 71% of games carry them, and
    # without them the regenerated game has no opponent cards at all.
    decryption_data = await generate_game_decryption_v5(
        pgn,
        user_color,
        move_evaluations,
        user_id,
        db,
        game_id=game_id,
        opponent_move_evaluations=(
            (analysis.get("stockfish_analysis") or {})
            .get("opponent_move_evaluations") or []
        ),
    )
    if not decryption_data:
        return {"status": "no_output", "prev_version": stored_version}

    if not dry_run:
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {
                "decryption_v5_data": decryption_data,
                "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
                "decryption_v5_generating": False,
                "decryption_v5_version": V5_COACHING_VERSION,
            }},
        )

    return {
        "status": "ok",
        "prev_version": stored_version,
        "new_version": V5_COACHING_VERSION,
        "moves": len(decryption_data),
    }


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    query = {"decryption_v5_data": {"$exists": True, "$ne": []}}
    if args.user_id:
        query["user_id"] = args.user_id
    # Only games stuck below the current version
    from services.game_decryption_v5_service import V5_COACHING_VERSION
    if not args.force_all:
        query["$or"] = [
            {"decryption_v5_version": {"$exists": False}},
            {"decryption_v5_version": {"$lt": V5_COACHING_VERSION}},
        ]

    cursor = db.game_analyses.find(
        query, {"_id": 0, "game_id": 1, "user_id": 1}).sort("game_id", 1)
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)

    # Carry each game's OWN user_id. Without --user-id this passed "" for
    # every game, and user_id is what the service uses to load the player
    # model -- conductor threads, motif/opening/concept memory, authored
    # overrides. A corpus-wide run would have re-rendered 19k games with
    # no player context and written the result over the stored cards.
    targets = [(d["game_id"], d.get("user_id") or "") async for d in cursor]
    total = len(targets)
    print(f"Target V5_COACHING_VERSION = {V5_COACHING_VERSION}", flush=True)
    print(f"Found {total} game(s) to regen. dry_run={args.dry_run}", flush=True)
    if total == 0:
        client.close()
        return

    summary = {"ok": 0, "no_inputs": 0, "no_output": 0, "missing": 0, "error": 0}
    started = time.time()

    for i, (gid, gid_user) in enumerate(targets, 1):
        try:
            res = await regen_one(
                db, gid, args.user_id or gid_user, dry_run=args.dry_run)
        except Exception as e:
            res = {"status": "error", "error": str(e)}

        status = res.get("status", "error")
        summary[status] = summary.get(status, 0) + 1

        elapsed = time.time() - started
        rate = i / elapsed if elapsed > 0 else 0
        line = (
            f"[{i:4d}/{total}] {gid}  status={status}"
            f"  v{res.get('prev_version', '?')}->v{res.get('new_version', '?')}"
            f"  moves={res.get('moves', '-')}  ({rate:.2f}/s)"
        )
        if status == "error":
            line += f"  err={res.get('error', '?')[:80]}"
        print(line, flush=True)

    elapsed = time.time() - started
    print("", flush=True)
    print("=" * 70, flush=True)
    print(f"Done in {elapsed:.1f}s.", flush=True)
    for k, v in summary.items():
        print(f"  {k}: {v}", flush=True)
    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="only first N games (0 = all)")
    p.add_argument("--user-id", default=None, help="only this user_id")
    p.add_argument("--dry-run", action="store_true", help="don't write to DB")
    p.add_argument("--force-all", action="store_true", help="ignore version gate; redo every match")
    args = p.parse_args()
    asyncio.run(main(args))
