"""
Backfill PV-tactical narratives on cached `decryption_v5_data` entries.

Why this exists:
  `decryption_v5_data` is cached on each game_analyses doc after its first
  generation. Old cached entries carry LLM-written narratives like "Nxf2
  attacks their queen — forces them to respond" — accurate but one-move
  deep. We now have `pv_tactical_analyzer` which walks Stockfish's PV and
  produces grounded tactical explanations ("forks queen and rook — wins a
  rook"). This script replaces the cached narrative on existing mistakes
  where the deterministic analyzer has something concrete to say. Moves
  without a clean tactical signal keep their LLM narrative.

What it touches per decryption entry:
  narrative (replaced if deterministic analyzer returns a string)
  narrative_source (set to "pv_tactical" for replaced entries; others
                    untouched)

What it does NOT touch:
  move-level stockfish stats, coach_summary, player profiles, games docs,
  entries that aren't mistakes/blunders/inaccuracies, entries where the
  analyzer returns None.

Usage:
  docker cp scripts/backfill_pv_tactical_narratives.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/backfill_pv_tactical_narratives.py
  docker exec -it chess-coach-backend python3 scripts/backfill_pv_tactical_narratives.py --apply
  docker exec -it chess-coach-backend python3 scripts/backfill_pv_tactical_narratives.py --user user_8b599930d7ef --apply
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

from services.pv_tactical_analyzer import explain_best_move_tactically

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("backfill_pv_tactical")

PROGRESS_EVERY = 25


def _build_eval_lookup(move_evaluations):
    """Map fen_before → {pv_after_best, best_move_uci, best_move_san} for cross-ref."""
    lookup = {}
    for ev in move_evaluations or []:
        fb = ev.get("fen_before")
        if not fb:
            continue
        lookup[fb] = {
            "pv_after_best": ev.get("pv_after_best") or [],
            "best_move_uci": ev.get("best_move_uci") or "",
            "best_move_san": ev.get("best_move") or "",
        }
    return lookup


async def process_one(db, analysis_doc: dict, apply: bool) -> dict:
    """Re-annotate a single analysis doc's cached decryption narratives."""
    game_id = analysis_doc.get("game_id", "")
    user_id = analysis_doc.get("user_id", "")
    decryption = analysis_doc.get("decryption_v5_data")

    stats = {
        "game_id": game_id,
        "user_id": user_id,
        "entries": 0,
        "eligible": 0,
        "replaced": 0,
        "source_before": Counter(),
        "source_after": Counter(),
    }

    if not decryption or not isinstance(decryption, list):
        stats["skipped"] = "no_decryption"
        return stats

    sf = analysis_doc.get("stockfish_analysis") or {}
    eval_lookup = _build_eval_lookup(sf.get("move_evaluations"))
    if not eval_lookup:
        stats["skipped"] = "no_move_evaluations"
        return stats

    stats["entries"] = len(decryption)

    for entry in decryption:
        severity = entry.get("severity")
        if severity not in ("mistake", "blunder", "inaccuracy"):
            continue
        if not entry.get("plan"):
            continue
        if entry.get("priority") == "silent":
            continue

        stats["eligible"] += 1
        stats["source_before"][entry.get("narrative_source") or "llm_or_rulebased"] += 1

        fen_before = entry.get("fen_before") or ""
        ev = eval_lookup.get(fen_before)
        if not ev:
            # No matching stockfish row for this position — leave narrative as-is.
            stats["source_after"][entry.get("narrative_source") or "llm_or_rulebased"] += 1
            continue

        try:
            new_narrative = explain_best_move_tactically(
                fen_before=fen_before,
                best_move_uci=ev["best_move_uci"],
                best_move_san=ev["best_move_san"] or entry.get("best_move_san", ""),
                pv_after_best=ev["pv_after_best"],
            )
        except Exception as e:
            logger.debug(f"analyzer error on {game_id} entry: {e}")
            new_narrative = None

        if new_narrative:
            entry["narrative"] = new_narrative
            entry["narrative_source"] = "pv_tactical"
            stats["replaced"] += 1
            stats["source_after"]["pv_tactical"] += 1
        else:
            # Keep whatever narrative was there — deterministic had nothing
            # grounded to say.
            stats["source_after"][entry.get("narrative_source") or "llm_or_rulebased"] += 1

    if apply and stats["replaced"] > 0:
        await db.game_analyses.update_one(
            {"game_id": game_id, "user_id": user_id},
            {"$set": {"decryption_v5_data": decryption}},
        )

    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Replace LLM narratives with PV-tactical narratives where possible."
    )
    parser.add_argument("--apply", action="store_true", help="Persist changes. Without this, dry run.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N analyses (0 = all).")
    parser.add_argument("--user", type=str, default="", help="Only process this user_id.")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")

    logger.info(f"Connecting to {db_name} at {url}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    query = {"decryption_v5_data": {"$exists": True, "$ne": None}}
    if args.user:
        query["user_id"] = args.user

    total = await db.game_analyses.count_documents(query)
    logger.info(f"Analyses with cached decryption: {total}")
    if args.limit:
        logger.info(f"Limit: {args.limit}")
    if not args.apply:
        logger.info("DRY RUN — no writes. Pass --apply to persist.")

    cursor = db.game_analyses.find(
        query,
        {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "decryption_v5_data": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    ).sort("analyzed_at", -1)

    processed = 0
    touched_docs = 0
    total_eligible = 0
    total_replaced = 0
    source_before = Counter()
    source_after = Counter()
    skipped_reasons = Counter()

    async for doc in cursor:
        if args.limit and processed >= args.limit:
            break
        try:
            stats = await process_one(db, doc, apply=args.apply)
        except Exception as e:
            logger.warning(f"Failed on {doc.get('game_id')}: {e}")
            continue

        processed += 1
        if stats.get("skipped"):
            skipped_reasons[stats["skipped"]] += 1
            continue

        total_eligible += stats["eligible"]
        total_replaced += stats["replaced"]
        source_before.update(stats["source_before"])
        source_after.update(stats["source_after"])
        if stats["replaced"] > 0:
            touched_docs += 1

        if processed % PROGRESS_EVERY == 0:
            logger.info(
                f"  progress: {processed}/{total if not args.limit else args.limit} "
                f"analyses · {touched_docs} touched · {total_replaced} narratives replaced"
            )

    logger.info("=" * 60)
    logger.info(f"Processed: {processed} analyses")
    logger.info(f"Docs touched: {touched_docs}")
    logger.info(f"Eligible entries: {total_eligible}")
    logger.info(f"Narratives replaced: {total_replaced}")
    if skipped_reasons:
        logger.info("")
        logger.info("Skipped reasons:")
        for reason, cnt in skipped_reasons.most_common():
            logger.info(f"  {reason:30s} {cnt}")
    logger.info("")
    logger.info("Narrative source — before:")
    for src, cnt in source_before.most_common():
        logger.info(f"  {src:30s} {cnt}")
    logger.info("Narrative source — after:")
    for src, cnt in source_after.most_common():
        logger.info(f"  {src:30s} {cnt}")

    if not args.apply:
        logger.info("")
        logger.info("This was a DRY RUN. Re-run with --apply to persist.")


if __name__ == "__main__":
    asyncio.run(main())
