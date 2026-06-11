"""
Regen cognitive-gap enrichment on EXISTING Play-with-Coach games.

Why a dedicated script (not backfill_cognitive_gaps.py): coach games were
promoted with a degraded schema — their stored move_evaluations lack `move_uci`,
so re-running the classifier over the STORED moves can't fire the hanging/drops
detectors. We instead rebuild the move_evaluations from the intact
`coach_sessions.move_history` (which has `uci`) via the same enriched builder the
live promotion now uses, and UPDATE the game_analyses in place.

In place (not delete/re-promote) so `imported_at` stays stable and the Mirror
window doesn't shift under the user.

Touches: stockfish_analysis.move_evaluations / accuracy / blunders / mistakes on
coach (platform="coach") game_analyses. Nothing else.

Usage (on the server):
  docker cp scripts/regen_coach_game_gaps.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/regen_coach_game_gaps.py            # dry run
  docker exec -it chess-coach-backend python3 scripts/regen_coach_game_gaps.py --apply
  docker exec -it chess-coach-backend python3 scripts/regen_coach_game_gaps.py --user user_8b599930d7ef --apply
"""
import argparse
import asyncio
import logging
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

from routes.coach_play import _build_enriched_coach_move_evaluations

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("regen_coach_game_gaps")


async def process_one(db, game, apply: bool) -> dict:
    game_id = game.get("game_id", "")
    user_id = game.get("user_id", "")
    user_color = (game.get("user_color") or "white").lower()
    session_id = game.get("coach_session_id")

    stats = {"game_id": game_id, "moves": 0, "gaps_before": 0, "gaps_after": 0, "ok": False}

    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0, "move_history": 1})
    if not session:
        logger.warning(f"  {game_id[:16]}: no session {session_id} — skipped")
        return stats
    mh = session.get("move_history") or []
    if len(mh) < 4:
        return stats

    # gaps before (from stored analysis)
    an = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0, "stockfish_analysis.move_evaluations": 1})
    before_moves = ((an or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
    stats["gaps_before"] = sum(1 for m in before_moves if m.get("cognitive_gap"))

    move_evaluations, accuracy, blunders, mistakes = _build_enriched_coach_move_evaluations(mh, user_color)
    stats["moves"] = len(move_evaluations)
    stats["gaps_after"] = sum(1 for m in move_evaluations if m.get("is_user_move") and m.get("cognitive_gap"))
    stats["ok"] = True

    if apply:
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {
                "stockfish_analysis.accuracy": accuracy,
                "stockfish_analysis.blunders": blunders,
                "stockfish_analysis.mistakes": mistakes,
                "stockfish_analysis.move_evaluations": move_evaluations,
            }},
        )
    return stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist updates (default: dry run).")
    parser.add_argument("--user", type=str, default="", help="Only this user_id.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N coach games.")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    db = AsyncIOMotorClient(url)[db_name]

    query = {"platform": "coach"}
    if args.user:
        query["user_id"] = args.user

    games = await db.games.find(
        query, {"_id": 0, "game_id": 1, "user_id": 1, "user_color": 1, "coach_session_id": 1}
    ).to_list(length=100000)
    if args.limit:
        games = games[: args.limit]

    logger.info(f"Coach games matched: {len(games)} | apply={args.apply}")
    if not args.apply:
        logger.info("DRY RUN — no writes. Pass --apply to persist.")

    tot_before = Counter()
    tot_after = Counter()
    touched = 0
    recovered = 0
    for g in games:
        try:
            s = await process_one(db, g, apply=args.apply)
        except Exception as e:
            logger.warning(f"  {g.get('game_id','?')[:16]}: FAILED {e}")
            continue
        if not s["ok"]:
            continue
        touched += 1
        tot_before["gaps"] += s["gaps_before"]
        tot_after["gaps"] += s["gaps_after"]
        if s["gaps_after"] > s["gaps_before"]:
            recovered += 1
        logger.info(f"  {s['game_id'][:16]}: {s['moves']} moves | gaps {s['gaps_before']} -> {s['gaps_after']}")

    logger.info("=" * 60)
    logger.info(f"Processed {touched} coach games | gaps {tot_before['gaps']} -> {tot_after['gaps']} "
                f"| games with recovered signal: {recovered}")
    if not args.apply:
        logger.info("DRY RUN — re-run with --apply to persist.")


if __name__ == "__main__":
    asyncio.run(main())
