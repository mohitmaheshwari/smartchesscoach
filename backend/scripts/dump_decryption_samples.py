"""
Dump real game decryption samples for voice evaluation.

Pulls 3 most-recent analyzed games that have decryption_data populated,
prints the LLM-generated narratives in a readable format. Run inside
the backend container so MONGO_URL points at the live Mongo.

Usage (inside the backend container):
    python scripts/dump_decryption_samples.py
    python scripts/dump_decryption_samples.py --limit 5
    python scripts/dump_decryption_samples.py --user user_xxxxx

Output is plain text on stdout. Pipe to a file if you want to share:
    python scripts/dump_decryption_samples.py > /tmp/samples.txt
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


SEP = "=" * 78
SUBSEP = "-" * 78


def _truncate(text, max_len=400):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


async def dump_samples(limit: int, user_filter: str | None) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Find game_analyses that have decryption_data populated. Sort by
    # created_at desc so we get recent ones.
    query = {"decryption_data": {"$exists": True, "$ne": None}}
    if user_filter:
        query["user_id"] = user_filter

    cursor = db.game_analyses.find(query).sort("created_at", -1).limit(limit)
    games = []
    async for g in cursor:
        games.append(g)

    if not games:
        print("No games with decryption_data found.")
        client.close()
        return

    print(f"Found {len(games)} games with decryption_data.\n")

    for i, ga in enumerate(games, 1):
        print(SEP)
        print(f"GAME {i} of {len(games)}")
        print(SEP)
        gid = ga.get("game_id")
        uid = ga.get("user_id")
        print(f"game_id  : {gid}")
        print(f"user_id  : {uid}")

        # Pull the matching game record for context.
        g = await db.games.find_one({"game_id": gid}, {"_id": 0}) if gid else None
        if g:
            print(f"opening  : {g.get('opening', 'unknown')}")
            print(f"result   : {g.get('result', '?')}  user_color: {g.get('user_color', '?')}")
            print(f"platform : {g.get('platform', '?')}  imported : {g.get('imported_at', '?')}")

        decryption = ga.get("decryption_data") or {}

        # decryption_data shape can vary across v4/v5. Common fields:
        # - moves: list of per-move dicts with narrative, mistake_analysis, etc.
        # - game_summary / overview: top-level text
        for top_key in ("game_summary", "overview", "headline", "summary"):
            if decryption.get(top_key):
                print()
                print(f"[{top_key}]")
                print(_truncate(decryption[top_key], 500))

        moves = decryption.get("moves") or decryption.get("move_data") or []
        if not moves:
            print()
            print("(no per-move decryption present)")
            continue

        # Filter to moves that have an LLM narrative (mistakes/blunders).
        narrated = [
            m for m in moves
            if (m.get("mistake_analysis") or m.get("narrative")
                or m.get("thinking_gap") or m.get("better_plan"))
        ]

        if not narrated:
            print()
            print("(no narrated moves — only deterministic placeholders)")
            continue

        print()
        print(f"Narrated moves: {len(narrated)} of {len(moves)} total")

        # Print up to 3 narrated moves per game so the dump stays readable.
        for n, m in enumerate(narrated[:3], 1):
            print()
            print(SUBSEP)
            print(f"MOVE {n}: ply={m.get('ply', '?')}  san={m.get('move_san', '?')}  "
                  f"best={m.get('best_move_san', '?')}  cp_loss={m.get('cp_loss', '?')}")
            for key in (
                "narrative",
                "mistake_analysis",
                "thinking_gap",
                "better_plan",
                "principle",
                "position_breakdown",
            ):
                v = m.get(key)
                if v:
                    print(f"\n[{key}]")
                    print(_truncate(v, 600))

    print()
    print(SEP)
    print("END")
    client.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=3, help="how many games to dump")
    p.add_argument("--user", default=None, help="filter to a specific user_id")
    args = p.parse_args()
    asyncio.run(dump_samples(args.limit, args.user))


if __name__ == "__main__":
    main()
