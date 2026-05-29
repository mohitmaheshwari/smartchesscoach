"""
Backfill: replay every analyzed game for a user through the registered
concept detectors and persist their grades to coach_memory.

Why this exists: detectors only run at game-analysis time. Games
analyzed BEFORE a detector existed never received its grade. This
script walks the existing library so historical performance counts.

Usage (inside the backend container):
  python /app/backend/scripts/backfill_concept_detectors.py --user user_8b599930d7ef
  python /app/backend/scripts/backfill_concept_detectors.py --all
  python /app/backend/scripts/backfill_concept_detectors.py --user X --dry-run

Idempotent-ish: each game's grades land via record_skill_attempt which
appends to outcomes and bumps counts. If a user has already had a
grade recorded for a game (because the game was processed live), the
backfill will re-record — that double-counts. The intended workflow
is to run the backfill ONCE per detector launch.

Mohit 2026-05-29: shipped alongside defend_scholars_mate so the two
'applied' grades sitting on real game positions actually reach his
Progress page.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient

from services.coach_memory import (
    get_or_create_memory,
    record_concept_applications_from_game,
    _memory_to_doc,
)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def backfill_for_user(db, user_id: str, dry_run: bool = False) -> dict:
    """Run every registered detector across user's analyzed games."""
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1}
    ).to_list(2000)

    if not games:
        return {"user_id": user_id, "games": 0, "grades": []}

    memory = await get_or_create_memory(db, user_id)

    total_grades = []
    games_with_grades = 0
    for g in games:
        gid = g["game_id"]
        user_color = (g.get("user_color") or "white").lower()
        a = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )
        if not a:
            continue
        mes = a.get("stockfish_analysis", {}).get("move_evaluations", [])
        if not mes:
            continue
        recorded = record_concept_applications_from_game(
            memory=memory,
            move_evaluations=mes,
            user_color=user_color,
        )
        if recorded:
            games_with_grades += 1
            for skill_id, outcome in recorded:
                total_grades.append({
                    "game_id": gid,
                    "skill_id": skill_id,
                    "outcome": outcome,
                })

    if not dry_run and total_grades:
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {"$set": _memory_to_doc(memory)},
            upsert=True,
        )

    return {
        "user_id": user_id,
        "games": len(games),
        "games_with_grades": games_with_grades,
        "grades": total_grades,
        "applied": memory.learning,
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", help="Single user_id")
    ap.add_argument("--all", action="store_true",
                    help="Backfill every user with at least one analyzed game")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results without saving")
    args = ap.parse_args()

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=8000)[DB_NAME]

    user_ids: list = []
    if args.user:
        user_ids = [args.user]
    elif args.all:
        user_ids = await db.games.distinct(
            "user_id", {"is_analyzed": True}
        )
    else:
        ap.print_help()
        return

    for uid in user_ids:
        if not uid:
            continue
        report = await backfill_for_user(db, uid, dry_run=args.dry_run)
        n_grades = len(report["grades"])
        print(f"[{uid}] games={report['games']} "
              f"games_with_grades={report['games_with_grades']} "
              f"grades_recorded={n_grades}"
              f"{' (dry-run, NOT saved)' if args.dry_run else ''}")
        for g in report["grades"]:
            print(f"  {g['game_id']:40} {g['skill_id']:30} {g['outcome']}")

        # Per-skill summary from coach_memory
        from collections import Counter
        cnt = Counter()
        for s in report["applied"].skills:
            if s.applied > 0:
                cnt[s.skill_id] = (s.correct, s.applied, s.wrong)
        if cnt:
            print(f"  -> final per-skill counts (correct/applied/wrong):")
            for sid, (c, a, w) in cnt.items():
                print(f"     {sid:35} {c}/{a}/{w}")


asyncio.run(main())
