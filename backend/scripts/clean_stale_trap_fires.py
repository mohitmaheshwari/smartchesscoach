"""Strip stale trap_fires entries that no longer exist in current traps.json.

Used 2026-06-04 to clean up "London Move Order" — a misclassified trap
removed from traps.json on 2026-05-28, but the 52 historical fires
remained fossilized in stored trap_fires arrays. Removing the source
prevents NEW fires; this script cleans the OLD ones.

Idempotent. Reads traps.json, computes the current valid trap-name
set, and pulls anything outside that set from each game's trap_fires
array.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/clean_stale_trap_fires.py        # dry-run
  docker exec chess-coach-backend python \\
    /app/backend/scripts/clean_stale_trap_fires.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")
TRAPS_FILE = BACKEND_DIR / "data" / "captions"  # not here; fix below
TRAPS_FILE = BACKEND_DIR / "data" / "traps.json"


def load_valid_trap_names() -> set[str]:
    with open(TRAPS_FILE) as f:
        traps = json.load(f)
    names: set[str] = set()
    for opening_key, trap_list in traps.items():
        if not isinstance(trap_list, list):
            continue
        for t in trap_list:
            if isinstance(t, dict):
                name = t.get("name") or t.get("trap_name")
                if name:
                    names.add(name)
    return names


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    valid = load_valid_trap_names()
    print(f"Valid trap names from traps.json: {len(valid)}")

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)[DB_NAME]

    stale_counts: Counter[str] = Counter()
    affected_games = 0
    total_games = 0

    cursor = db.game_analyses.find(
        {"trap_fires": {"$exists": True, "$ne": []}},
        {"_id": 1, "game_id": 1, "trap_fires": 1},
    )
    async for ga in cursor:
        total_games += 1
        fires = ga.get("trap_fires") or []
        kept = []
        stale_here = []
        for t in fires:
            if not isinstance(t, dict):
                continue
            name = t.get("name") or t.get("trap_name") or t.get("trap_id") or ""
            if name in valid:
                kept.append(t)
            else:
                stale_here.append(name)
                stale_counts[name] += 1
        if stale_here:
            affected_games += 1
            if args.apply:
                await db.game_analyses.update_one(
                    {"_id": ga["_id"]},
                    {"$set": {"trap_fires": kept}},
                )

    print(f"Games with trap_fires:  {total_games}")
    print(f"Games with STALE fires: {affected_games}")
    print()
    print("Stale trap names and counts:")
    for name, count in stale_counts.most_common():
        print(f"  {name!r}: {count}")
    if not args.apply:
        print()
        print("DRY RUN — rerun with --apply to clean up.")
    else:
        print()
        print("APPLIED.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
