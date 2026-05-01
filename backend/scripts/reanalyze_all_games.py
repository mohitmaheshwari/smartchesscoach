"""
Re-analyze every previously-analyzed game with the current Stockfish
pipeline.

Why: classify_move recently learned about winning-/losing-position
context (cp_loss alone no longer flags +900 → +500 as a blunder), and
the position-reader's castling insights now skip in endgame. Games
analyzed BEFORE that fix carry stale labels — the player_profiles
aggregates and game_analyses move evaluations show inflated blunder
counts and depressed accuracy. Re-running the pipeline regenerates
both with the new logic.

Strategy: enqueue each analyzed game as a fresh `analysis_queue` job.
The existing worker (analysis_worker.py:run_worker) picks them up FIFO
and runs the full pipeline (Stockfish + behavioral interpretation +
profile aggregation), so this script doesn't duplicate that logic.
We just have to make sure each game appears once on the queue, and
that the existing analysis records get overwritten when the worker
finishes (the worker already does this via upsert).

Usage (on the server):
  docker cp scripts/reanalyze_all_games.py chess-coach-backend:/app/backend/scripts/

  # Dry-run: show what would be queued, don't write
  docker exec -it chess-coach-backend python3 scripts/reanalyze_all_games.py

  # Apply for one user (test the pattern first)
  docker exec -it chess-coach-backend python3 scripts/reanalyze_all_games.py \
      --user user_1e2b7b2777bc --apply

  # Apply across the whole DB
  docker exec -it chess-coach-backend python3 scripts/reanalyze_all_games.py --apply

  # Limit the run (e.g., 5 games to confirm the worker picks them up)
  docker exec -it chess-coach-backend python3 scripts/reanalyze_all_games.py \
      --limit 5 --apply

After --apply, the worker processes the queue at its normal rate.
Watch progress with:
  docker exec -it chess-coach-backend python3 scripts/inspect_db.py queue
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("reanalyze_all_games")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually queue jobs. Without it, the script is dry-run.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="Limit to a single user_id. Useful for testing the pattern first.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap on number of games to enqueue. 0 = no cap.",
    )
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = MongoClient(mongo_url)[db_name]

    # All analyzed games. Filter on is_analyzed=True (the canonical
    # flag set by the worker on success). Per-user filter optional.
    query: dict = {"is_analyzed": True}
    if args.user:
        query["user_id"] = args.user

    total = db.games.count_documents(query)
    logger.info(f"Found {total} analyzed games matching filter")
    if total == 0:
        return 0

    cursor = db.games.find(
        query, {"_id": 0, "game_id": 1, "user_id": 1, "pgn": 1, "user_color": 1}
    )

    queued = 0
    skipped_no_pgn = 0
    already_pending = 0
    bumped_to_pending = 0

    for game in cursor:
        if args.limit and queued >= args.limit:
            break

        game_id = game.get("game_id")
        user_id = game.get("user_id")
        pgn = game.get("pgn", "")
        if not pgn:
            skipped_no_pgn += 1
            continue

        existing = db.analysis_queue.find_one({"game_id": game_id})

        if existing:
            # If a stale (completed/failed) job exists, flip it back to
            # pending so the worker picks it up again. Reset retry/error
            # state so the worker treats this as a fresh attempt.
            status = existing.get("status")
            if status == "pending":
                already_pending += 1
                continue

            if not args.apply:
                logger.info(
                    f"  [DRY] would re-queue {game_id} (current status={status})"
                )
                bumped_to_pending += 1
                continue

            db.analysis_queue.update_one(
                {"game_id": game_id},
                {
                    "$set": {
                        "status": "pending",
                        "queued_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "retry_count": 0,
                        "worker_id": None,
                        "error": None,
                        "reanalysis": True,
                    }
                },
            )
            bumped_to_pending += 1
            logger.info(f"  Re-queued {game_id} (was {status})")
            continue

        # No existing job — insert one.
        if not args.apply:
            logger.info(f"  [DRY] would queue {game_id} for {user_id}")
            queued += 1
            continue

        db.analysis_queue.insert_one(
            {
                "game_id": game_id,
                "user_id": user_id,
                "pgn": pgn,
                "user_color": game.get("user_color", "white"),
                "status": "pending",
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": 0,
                "reanalysis": True,
            }
        )
        queued += 1
        if queued % 10 == 0:
            logger.info(f"  Queued {queued} so far...")

    logger.info("─" * 60)
    logger.info(f"Total analyzed games:        {total}")
    logger.info(f"New jobs queued:             {queued}")
    logger.info(f"Existing jobs bumped:        {bumped_to_pending}")
    logger.info(f"Already pending (skipped):   {already_pending}")
    logger.info(f"Skipped (no PGN):            {skipped_no_pgn}")

    if not args.apply:
        logger.info("")
        logger.info("DRY RUN — no changes written.")
        logger.info("Re-run with --apply to enqueue these jobs.")
    else:
        logger.info("")
        logger.info(
            "Jobs are now in the queue. The worker processes them at its normal rate "
            "(typically minutes per game depending on STOCKFISH_DEPTH)."
        )
        logger.info(
            "Monitor progress: docker logs -f chess-coach-backend "
            "| grep '\\[STOCKFISH\\]'"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
