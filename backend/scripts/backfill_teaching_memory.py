"""
One-shot backfill: populate user_teaching_memory from existing
decryption_v5_data + trap_fires across all analyzed games.

Phase 2.0. Materializes the per-user memory index that the live
cross-game recall layer (Phase 2.2) reads from.

Usage:
  MONGO_URL=mongodb://user:pass@host:27018/?authSource=admin \\
    docker exec -i chess-coach-backend python \\
    scripts/backfill_teaching_memory.py [--limit N] [--user USER_ID] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--user", type=str, default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default="/tmp/teaching_memory_backfill.json")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required.", file=sys.stderr)
        sys.exit(1)

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.teaching_memory_index import (
        ensure_indexes,
        index_game_v5_data,
        index_game_trap_fires,
        TEACHING_MEMORY_VERSION,
    )

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    if not args.dry_run:
        print("Ensuring indexes on user_teaching_memory…", file=sys.stderr)
        await ensure_indexes(db)

    # Build games lookup (user_color, opponent, time_control, rating at time, result)
    print("Loading games metadata…", file=sys.stderr)
    games_meta: dict = {}
    games_q: dict = {"is_analyzed": True}
    if args.user:
        games_q["user_id"] = args.user
    async for g in db.games.find(games_q, {
        "_id": 0, "game_id": 1, "user_id": 1, "user_color": 1,
        "opponent_username": 1, "opponent": 1, "result": 1,
        "time_control": 1, "user_rating": 1, "user_rating_at_time": 1,
        "ended_at": 1, "imported_at": 1, "created_at": 1,
    }):
        games_meta[g["game_id"]] = g

    print(f"  → {len(games_meta)} candidate games", file=sys.stderr)

    if not games_meta:
        print("No games to backfill.", file=sys.stderr)
        return

    # Iterate game_analyses for those games
    total_scanned = 0
    total_v5_entries = 0
    total_trap_entries = 0
    by_principle = Counter()
    by_source = Counter()
    by_gold_class = Counter()
    games_with_entries = 0
    failures: list = []
    t0 = time.time()

    cursor = db.game_analyses.find(
        {"game_id": {"$in": list(games_meta.keys())}},
        {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "decryption_v5_data": 1,
            "trap_fires": 1,
        },
    )

    async for a in cursor:
        if args.limit and total_scanned >= args.limit:
            break
        total_scanned += 1
        gid = a.get("game_id")
        uid = a.get("user_id")
        if not uid:
            uid = (games_meta.get(gid) or {}).get("user_id")
        if not (gid and uid):
            continue

        meta = games_meta.get(gid) or {}
        user_color = (meta.get("user_color") or "white").lower()
        opponent = meta.get("opponent_username") or meta.get("opponent")
        time_control = meta.get("time_control")
        result = meta.get("result")
        user_rating_at_time = (
            meta.get("user_rating_at_time")
            or meta.get("user_rating")
            or None
        )
        occurred_at = (
            meta.get("ended_at")
            or meta.get("imported_at")
            or meta.get("created_at")
            or datetime.now(timezone.utc)
        )
        if isinstance(occurred_at, str):
            try:
                occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            except Exception:
                occurred_at = datetime.now(timezone.utc)
        if isinstance(occurred_at, datetime) and occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        v5_data = a.get("decryption_v5_data") or []
        trap_fires = a.get("trap_fires") or []

        if args.dry_run:
            # Just count what WOULD be written
            from services.teaching_memory_index import _gold_classify_v5_move
            v5_count_for_game = 0
            for m in v5_data:
                gc = _gold_classify_v5_move(m, user_color)
                if gc in ("none", "warning"):
                    continue
                if m.get("principle_id_used") or m.get("principle_id") or m.get("shape_pattern_id"):
                    v5_count_for_game += 1
                    by_principle[m.get("principle_id_used") or m.get("principle_id") or f"SHAPE:{m.get('shape_pattern_id')}"] += 1
                    by_gold_class[gc] += 1
                    by_source["v5"] += 1
            trap_count_for_game = 0
            for t in trap_fires:
                if t.get("gold_class") in ("gold", "lucky"):
                    trap_count_for_game += 1
                    by_principle[f"TRAP:{t.get('trap_name')}"] += 1
                    by_gold_class[t["gold_class"]] += 1
                    by_source["trap"] += 1
            if v5_count_for_game + trap_count_for_game > 0:
                games_with_entries += 1
                total_v5_entries += v5_count_for_game
                total_trap_entries += trap_count_for_game
            continue

        try:
            n_v5 = await index_game_v5_data(
                db,
                user_id=uid,
                game_id=gid,
                user_color=user_color,
                user_rating_at_time=user_rating_at_time,
                opponent=opponent,
                time_control=time_control,
                result=result,
                occurred_at=occurred_at,
                decryption_v5_data=v5_data,
            )
            n_trap = await index_game_trap_fires(
                db,
                user_id=uid,
                game_id=gid,
                user_rating_at_time=user_rating_at_time,
                opponent=opponent,
                time_control=time_control,
                result=result,
                occurred_at=occurred_at,
                trap_fires=trap_fires,
            )
            total_v5_entries += n_v5
            total_trap_entries += n_trap
            if (n_v5 + n_trap) > 0:
                games_with_entries += 1
        except Exception as e:
            failures.append({"game_id": gid, "reason": str(e)[:200]})

        if total_scanned % 200 == 0:
            elapsed = time.time() - t0
            rate = total_scanned / elapsed if elapsed > 0 else 0
            print(
                f"  progress: {total_scanned}/{len(games_meta)}  "
                f"v5={total_v5_entries} trap={total_trap_entries} games_with={games_with_entries}  "
                f"rate={rate:.1f} g/s",
                file=sys.stderr,
            )

    elapsed = time.time() - t0

    # Roll up the report
    out = {
        "elapsed_seconds": round(elapsed, 1),
        "scanned_games": total_scanned,
        "games_with_entries": games_with_entries,
        "total_v5_entries": total_v5_entries,
        "total_trap_entries": total_trap_entries,
        "total_entries": total_v5_entries + total_trap_entries,
        "by_source": dict(by_source),
        "by_gold_class": dict(by_gold_class),
        "top_principles": dict(by_principle.most_common(30)),
        "failure_count": len(failures),
        "failure_samples": failures[:10],
        "version": TEACHING_MEMORY_VERSION,
        "dry_run": args.dry_run,
    }
    Path(args.output).write_text(json.dumps(out, indent=2))

    print()
    print("=" * 60)
    print(f"Teaching-memory backfill {'(DRY RUN)' if args.dry_run else ''}")
    print(f"  scanned games:       {total_scanned}")
    print(f"  games with entries:  {games_with_entries}")
    print(f"  v5 entries written:  {total_v5_entries}")
    print(f"  trap entries written:{total_trap_entries}")
    print(f"  total entries:       {total_v5_entries + total_trap_entries}")
    print(f"  by source:           {dict(by_source)}")
    print(f"  by gold class:       {dict(by_gold_class)}")
    print(f"  failures:            {len(failures)}")
    print(f"  elapsed:             {elapsed:.1f}s")
    print()
    print("Top 15 principles by frequency:")
    for pid, n in by_principle.most_common(15):
        print(f"  {pid:40s}  {n}")
    print(f"\nFull report: {args.output}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
