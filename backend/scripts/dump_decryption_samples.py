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

    # First, an inventory: how many games have V4 vs V5 data?
    total = await db.game_analyses.count_documents({})
    v4_count = await db.game_analyses.count_documents(
        {"decryption_data": {"$exists": True, "$ne": None}}
    )
    v5_count = await db.game_analyses.count_documents(
        {"decryption_v5_data": {"$exists": True, "$ne": None}}
    )
    print(f"INVENTORY: {total} game_analyses total | "
          f"V4 populated: {v4_count} | V5 populated: {v5_count}")
    print()

    # Prefer V5 — that's the live system. Fall back to V4 if no V5 data exists.
    if v5_count > 0:
        query = {"decryption_v5_data": {"$exists": True, "$ne": None}}
        active_field = "decryption_v5_data"
        print(f"Using V5 ({active_field})")
    else:
        query = {"decryption_data": {"$exists": True, "$ne": None}}
        active_field = "decryption_data"
        print(f"No V5 data exists — falling back to V4 ({active_field})")

    if user_filter:
        query["user_id"] = user_filter

    cursor = db.game_analyses.find(query).sort("created_at", -1).limit(limit)
    games = []
    async for g in cursor:
        # Normalize: copy the active field to "decryption_data" so the rest
        # of the script reads from a single key.
        g["decryption_data"] = g.get(active_field)
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

        decryption = ga.get("decryption_data")

        # decryption_data shape varies: sometimes a dict with "moves" inside,
        # sometimes the list of moves directly. Handle both.
        if isinstance(decryption, list):
            moves = decryption
        elif isinstance(decryption, dict):
            for top_key in ("game_summary", "overview", "headline", "summary"):
                if decryption.get(top_key):
                    print()
                    print(f"[{top_key}]")
                    print(_truncate(decryption[top_key], 500))
            moves = decryption.get("moves") or decryption.get("move_data") or []
        else:
            moves = []
        if not moves:
            print()
            print("(no per-move decryption present)")
            continue

        # Field-population audit — what's actually present in production data?
        all_keys = set()
        populated_count = {}
        for m in moves:
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                all_keys.add(k)
                if v not in (None, "", [], {}):
                    populated_count[k] = populated_count.get(k, 0) + 1

        print()
        print("Field population (% of moves with non-empty value):")
        for k in sorted(all_keys):
            pct = round(100 * populated_count.get(k, 0) / max(1, len(moves)))
            print(f"  {k:30s} {pct}%  ({populated_count.get(k, 0)}/{len(moves)})")

        # Find decisive moments: top 3 moves by cp_loss.
        def _cp_loss(m):
            try:
                return float(m.get("cp_loss") or 0)
            except (TypeError, ValueError):
                return 0

        ranked = sorted(moves, key=lambda m: -_cp_loss(m))
        decisive = [m for m in ranked if _cp_loss(m) >= 50][:3]

        if not decisive:
            print()
            print("(no moves with cp_loss >= 50 — game had no real blunders to narrate)")
            continue

        print()
        print(f"Top {len(decisive)} decisive moments (cp_loss >= 50):")

        for n, m in enumerate(decisive, 1):
            print()
            print(SUBSEP)
            print(f"DECISIVE {n}: san={m.get('move_san', '?')}  "
                  f"best={m.get('best_move_san', '?')}  cp_loss={m.get('cp_loss', '?')}  "
                  f"ply={m.get('ply', '?')}")
            # Print every field that has content — don't pre-decide which matter.
            for key in sorted(m.keys()):
                v = m.get(key)
                if v in (None, "", [], {}):
                    continue
                if key in ("move_san", "best_move_san", "cp_loss", "ply",
                           "fen", "eval_before", "eval_after"):
                    continue  # already shown above
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
