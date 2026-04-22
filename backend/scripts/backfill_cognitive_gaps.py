"""
Backfill `cognitive_gap` (and related fields) on every move evaluation stored
in `game_analyses`, using the updated analysis_interpreter.

Why: the classifier was rewritten to emit the full 10-tag CLAUDE.md taxonomy
instead of the 2-tag collapse that existed in prod. Freshly analyzed games
get the new tags automatically; this script retroactively re-classifies every
move in every existing game_analysis so users see diversified patterns on
Home / Lab / Training without having to re-import or re-analyze anything.

What it touches per move (subset of what analysis_worker writes):
  cognitive_gap, is_critical, critical_reason,
  gap_confidence, gap_evidence, coaching_focus

What it does NOT touch:
  Stockfish fields (cp_loss, eval_before, best_move, etc.),
  other top-level analysis fields, games collection, user records.

Usage (on the server):
  docker cp scripts/backfill_cognitive_gaps.py chess-coach-backend:/app/backend/scripts/
  # Dry-run first (no writes, prints before/after distribution):
  docker exec -it chess-coach-backend python3 scripts/backfill_cognitive_gaps.py
  # When the plan looks right:
  docker exec -it chess-coach-backend python3 scripts/backfill_cognitive_gaps.py --apply
  # Scoped runs for testing:
  docker exec -it chess-coach-backend python3 scripts/backfill_cognitive_gaps.py --limit 20
  docker exec -it chess-coach-backend python3 scripts/backfill_cognitive_gaps.py --user user_1e2b7b2777bc --apply
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

from analysis_interpreter import interpret_game_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("backfill_cognitive_gaps")

PROGRESS_EVERY = 25


async def resolve_user_color(db, game_id: str, user_id: str) -> str:
    """Look up the user's color for a game; fall back to 'white' if unknown."""
    g = await db.games.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "user_color": 1, "user_plays_as": 1},
    )
    if not g:
        return "white"
    return (g.get("user_color") or g.get("user_plays_as") or "white").lower()


async def process_one(db, analysis_doc: dict, apply: bool) -> dict:
    """Re-classify one analysis doc. Returns a stats dict of before/after tag counts."""
    game_id = analysis_doc.get("game_id", "")
    user_id = analysis_doc.get("user_id", "")
    sf = analysis_doc.get("stockfish_analysis") or {}
    moves = sf.get("move_evaluations") or []

    stats = {"game_id": game_id, "user_id": user_id, "moves": len(moves), "changed": 0, "before": Counter(), "after": Counter()}

    if not moves:
        return stats

    user_color = await resolve_user_color(db, game_id, user_id)

    # Snapshot old tags for diff reporting
    for mv in moves:
        tag = mv.get("cognitive_gap")
        if tag:
            stats["before"][tag] += 1

    enriched_moves, _summary = interpret_game_analysis(moves, user_color)

    for i, move in enumerate(moves):
        if i >= len(enriched_moves):
            break
        new = enriched_moves[i]
        new_tag = new.get("cognitive_gap")
        old_tag = move.get("cognitive_gap")
        if new_tag != old_tag:
            stats["changed"] += 1
        move["cognitive_gap"] = new_tag
        move["is_critical"] = new.get("is_critical", False)
        move["critical_reason"] = new.get("critical_reason")
        move["gap_confidence"] = new.get("gap_confidence", 0)
        move["gap_evidence"] = new.get("gap_evidence", "")
        move["coaching_focus"] = new.get("coaching_focus", "")
        if new_tag:
            stats["after"][new_tag] += 1

    if apply and stats["changed"] > 0:
        await db.game_analyses.update_one(
            {"game_id": game_id, "user_id": user_id},
            {"$set": {"stockfish_analysis.move_evaluations": moves}},
        )

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Re-classify cognitive_gap across existing game_analyses.")
    parser.add_argument("--apply", action="store_true", help="Actually write updates. Without this flag runs in dry-run mode.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N analyses (0 = all).")
    parser.add_argument("--user", type=str, default="", help="Only process this user_id.")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")

    logger.info(f"Connecting to {db_name} at {url}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    query: dict = {}
    if args.user:
        query["user_id"] = args.user

    total = await db.game_analyses.count_documents(query)
    logger.info(f"Matching analyses: {total}")
    if args.limit:
        logger.info(f"Limit: {args.limit}")
    if not args.apply:
        logger.info("DRY RUN — no writes will be made. Pass --apply to persist changes.")

    cursor = db.game_analyses.find(query, {"_id": 0, "game_id": 1, "user_id": 1, "stockfish_analysis.move_evaluations": 1}).sort("analyzed_at", -1)

    total_before: Counter = Counter()
    total_after: Counter = Counter()
    processed = 0
    touched = 0
    empty = 0

    async for doc in cursor:
        if args.limit and processed >= args.limit:
            break
        try:
            stats = await process_one(db, doc, apply=args.apply)
        except Exception as e:
            logger.warning(f"Failed on {doc.get('game_id')}: {e}")
            continue

        processed += 1
        total_before.update(stats["before"])
        total_after.update(stats["after"])
        if stats["changed"] > 0:
            touched += 1
        elif stats["moves"] == 0:
            empty += 1

        if processed % PROGRESS_EVERY == 0:
            logger.info(f"  progress: {processed}/{total if not args.limit else args.limit} analyses · {touched} touched")

    logger.info("=" * 60)
    logger.info(f"Processed: {processed} | touched: {touched} | no-moves: {empty}")
    logger.info("")
    logger.info("Before (tag distribution across all processed moves):")
    for tag, cnt in total_before.most_common():
        logger.info(f"  {tag:30s} {cnt}")
    logger.info("")
    logger.info("After:")
    for tag, cnt in total_after.most_common():
        logger.info(f"  {tag:30s} {cnt}")

    before_unique = len(total_before)
    after_unique = len(total_after)
    logger.info("")
    logger.info(f"Distinct tag types — before: {before_unique}, after: {after_unique}")

    if not args.apply:
        logger.info("")
        logger.info("This was a DRY RUN. Re-run with --apply to persist.")


if __name__ == "__main__":
    asyncio.run(main())
