"""Count trade offers on games analysed before the counter existed.

New games get `trade_offers` written by analysis_worker. The 19,921 already
analysed do not, and `compute_traits` deliberately treats an absent count as
no evidence rather than as a player who declines every trade -- so without
this backfill the trait speaks for nobody.

Idempotent: a game that already carries a count is skipped unless --force.
Batched and projected, because holding every game's move rows at once is what
caused four container OOM kills on 2026-10-17.

    python scripts/backfill_trade_offers.py            # everything missing
    python scripts/backfill_trade_offers.py --limit 500
    python scripts/backfill_trade_offers.py --dry-run
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient

from services.trade_offers import count_trade_offers

BATCH = 50


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]

    query = {} if args.force else {"trade_offers": {"$exists": False}}
    todo = await db.game_analyses.count_documents(query)
    print("analyses without a count: %d%s" % (todo, " (forcing all)" if args.force else ""))
    if args.limit:
        todo = min(todo, args.limit)
        print("limited to: %d" % todo)

    done = written = offers_total = taken_total = empty = 0
    started = time.time()

    cursor = db.game_analyses.find(
        query,
        {"_id": 0, "game_id": 1,
         "stockfish_analysis.move_evaluations.fen_before": 1,
         "stockfish_analysis.move_evaluations.move": 1,
         "stockfish_analysis.move_evaluations.eval_before": 1,
         "stockfish_analysis.move_evaluations.is_opponent_move": 1},
    )
    pending = []
    async for analysis in cursor:
        rows = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        counts = count_trade_offers(rows)
        done += 1
        offers_total += counts["offers"]
        taken_total += counts["taken"]
        if counts["offers"] == 0:
            empty += 1
        if not args.dry_run:
            pending.append((analysis["game_id"], counts))
            if len(pending) >= BATCH:
                for game_id, c in pending:
                    await db.game_analyses.update_one(
                        {"game_id": game_id}, {"$set": {"trade_offers": c}})
                    written += 1
                pending = []
        if done % 500 == 0:
            rate = done / max(time.time() - started, 0.001)
            print("   %d done, %d written, %.0f/s" % (done, written, rate), flush=True)
        if args.limit and done >= args.limit:
            break

    if pending and not args.dry_run:
        for game_id, c in pending:
            await db.game_analyses.update_one(
                {"game_id": game_id}, {"$set": {"trade_offers": c}})
            written += 1

    print()
    print("games read      : %d" % done)
    print("counts written  : %d%s" % (written, " (dry run)" if args.dry_run else ""))
    print("games with no offer at all: %d (%.0f%%)" % (empty, 100.0 * empty / max(done, 1)))
    print("offers %d, taken %d  -> corpus rate %.3f" % (
        offers_total, taken_total, taken_total / max(offers_total, 1)))
    print("elapsed: %.0fs" % (time.time() - started))


asyncio.run(main())
