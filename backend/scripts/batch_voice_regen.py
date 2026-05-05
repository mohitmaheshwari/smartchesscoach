"""
Batch voice-regenerator. Walks every analyzed game, runs
generate_post_game_voice, writes back the new truth_line +
player_decryption + decryption_block (with confidence scores +
needs_review flags on each moment).

Use this once after deploying new dispatcher / score / template code so
the review queue picks up flagged moments across the whole DB.

Usage (inside the backend container):
    python scripts/batch_voice_regen.py
    python scripts/batch_voice_regen.py --limit 10            # only first N games
    python scripts/batch_voice_regen.py --since-days 30       # only games imported in last N days
    python scripts/batch_voice_regen.py --skip-recent-hours 6 # skip games regen'd in last N hours
    python scripts/batch_voice_regen.py --user-id <uid>       # only this user's games
    python scripts/batch_voice_regen.py --dry-run             # don't write to DB
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def regen_one(db, game_id: str, *, dry_run: bool) -> dict:
    """Regenerate voice for one game. Returns a small status dict."""
    game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
    if not game or not analysis:
        return {"game_id": game_id, "status": "missing"}

    v5 = analysis.get("decryption_v5_data") or []
    if not v5:
        return {"game_id": game_id, "status": "no_v5"}

    move_evals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    user_color = game.get("user_color") or "white"
    game_result = game.get("result") or "*"

    user_won = (
        (user_color == "white" and game_result == "1-0")
        or (user_color == "black" and game_result == "0-1")
    )
    if user_won:
        return {"game_id": game_id, "status": "user_won_skipped"}

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

    moments = ((plan or {}).get("moments") or [])
    flagged = sum(1 for m in moments if m.get("needs_review"))

    if not dry_run:
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {
                "truth_line": truth,
                "player_decryption": player,
                "decryption_block": plan,
                "pattern_evidence": evidence,
                "voice_regenerated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    return {
        "game_id": game_id,
        "status": "ok",
        "moments": len(moments),
        "flagged": flagged,
        "truth": bool(truth),
    }


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Build the list of game_ids to process — only games that have a
    # decryption_v5_data array (otherwise voice regen is a no-op).
    query = {"decryption_v5_data": {"$exists": True, "$ne": []}}
    if args.user_id:
        query["user_id"] = args.user_id
    if args.skip_recent_hours and args.skip_recent_hours > 0:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=args.skip_recent_hours)
        ).isoformat()
        query["$or"] = [
            {"voice_regenerated_at": {"$exists": False}},
            {"voice_regenerated_at": {"$lt": cutoff}},
        ]

    cursor = db.game_analyses.find(query, {"_id": 0, "game_id": 1}).sort("game_id", 1)
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)

    game_ids = [doc["game_id"] async for doc in cursor]

    # Optional filter: only games imported in the last N days.
    if args.since_days and args.since_days > 0:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=args.since_days)
        ).isoformat()
        recent_ids = []
        async for g in db.games.find(
            {"game_id": {"$in": game_ids}, "imported_at": {"$gte": cutoff}},
            {"_id": 0, "game_id": 1},
        ):
            recent_ids.append(g["game_id"])
        game_ids = [gid for gid in game_ids if gid in recent_ids]

    total = len(game_ids)
    print(f"Found {total} game(s) to regen. dry_run={args.dry_run}", flush=True)
    if total == 0:
        client.close()
        return

    summary = {
        "ok": 0, "user_won_skipped": 0, "no_v5": 0, "missing": 0, "error": 0,
        "total_moments": 0, "total_flagged": 0,
    }
    started = time.time()

    for i, gid in enumerate(game_ids, 1):
        try:
            res = await regen_one(db, gid, dry_run=args.dry_run)
        except Exception as e:
            res = {"game_id": gid, "status": "error", "error": str(e)}

        status = res.get("status", "error")
        summary[status] = summary.get(status, 0) + 1
        if status == "ok":
            summary["total_moments"] += res.get("moments", 0)
            summary["total_flagged"] += res.get("flagged", 0)

        elapsed = time.time() - started
        rate = i / elapsed if elapsed > 0 else 0
        line = (
            f"[{i:4d}/{total}] {gid}  status={status}"
            f"  moments={res.get('moments', '-')}  flagged={res.get('flagged', '-')}"
            f"  ({rate:.1f}/s)"
        )
        print(line, flush=True)

    elapsed = time.time() - started
    print("", flush=True)
    print("=" * 70, flush=True)
    print(f"Done in {elapsed:.1f}s.", flush=True)
    print(f"  ok:               {summary['ok']}", flush=True)
    print(f"  user_won_skipped: {summary['user_won_skipped']}", flush=True)
    print(f"  no_v5:            {summary['no_v5']}", flush=True)
    print(f"  missing:          {summary['missing']}", flush=True)
    print(f"  error:            {summary['error']}", flush=True)
    print(f"  total moments:    {summary['total_moments']}", flush=True)
    print(f"  flagged moments:  {summary['total_flagged']}  (queue size in /admin → Review)", flush=True)
    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="only first N games (0 = all)")
    p.add_argument("--since-days", type=int, default=0, help="only games imported in last N days")
    p.add_argument("--skip-recent-hours", type=int, default=0, help="skip games regen'd in last N hours")
    p.add_argument("--user-id", default=None, help="only this user_id")
    p.add_argument("--dry-run", action="store_true", help="do everything except DB write")
    args = p.parse_args()
    asyncio.run(main(args))
