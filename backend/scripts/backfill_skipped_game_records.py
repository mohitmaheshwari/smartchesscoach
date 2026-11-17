"""Fill skipped_game_records from each player's full history on both sites.

Run INSIDE chess-coach-backend:  python scripts/backfill_skipped_game_records.py <user_id> [...]
or --all for every user with a linked account. DRY=1 counts without writing.

Only result records for games the import skips (bullet, casual, very short)
are written, to their own collection; `games` is never touched. The rows are
new, so the undo is: db.skipped_game_records.deleteMany({user_id: <id>}).
Requests are sequential with a pause, the same public endpoints the sync uses.
"""
import asyncio
import json
import os
import sys
import time

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from journey_service import should_analyze_game  # noqa: E402
from services.skipped_games import COLLECTION, skipped_game_record, store_skipped_games  # noqa: E402

H = {"User-Agent": "ChessGuru coach (history backfill)"}
DRY = os.environ.get("DRY") == "1"


def lichess_history(username):
    r = httpx.get(f"https://lichess.org/api/games/user/{username}",
                  params={"moves": "true", "pgnInJson": "false", "clocks": "false", "evals": "false"},
                  headers={**H, "Accept": "application/x-ndjson"}, timeout=300)
    r.raise_for_status()
    return [json.loads(line) for line in r.text.splitlines() if line.strip()]


def chesscom_history(username):
    out = []
    arch = httpx.get(f"https://api.chess.com/pub/player/{username}/games/archives", headers=H, timeout=30)
    arch.raise_for_status()
    for url in arch.json().get("archives", []):
        out += httpx.get(url, headers=H, timeout=60).json().get("games", [])
        time.sleep(0.5)
    return out


async def main(argv):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if not DRY:
        await db[COLLECTION].create_index([("user_id", 1), ("platform", 1), ("platform_game_id", 1)], unique=True)
    query = {"$or": [{"lichess_username": {"$nin": [None, ""]}}, {"chess_com_username": {"$nin": [None, ""]}},
                     {"chesscom_username": {"$nin": [None, ""]}}]}
    if "--all" not in argv:
        query = {"user_id": {"$in": [a for a in argv if not a.startswith("--")]}}
    async for u in db.users.find(query, {"user_id": 1, "lichess_username": 1, "chess_com_username": 1, "chesscom_username": 1}):
        uid = u["user_id"]
        for platform, name, fetch in (("lichess", u.get("lichess_username"), lichess_history),
                                      ("chess.com", u.get("chess_com_username") or u.get("chesscom_username"), chesscom_history)):
            if not name:
                continue
            try:
                games = fetch(name)
            except Exception as err:
                print(f"..{uid[-6:]} {platform}: fetch failed ({type(err).__name__})")
                continue
            skipped = [g for g in games if not should_analyze_game(g, platform)]
            if DRY:
                recs = [skipped_game_record(g, platform, name, uid) for g in skipped]
                by = {}
                for r in recs:
                    if r:
                        by[r["reason"]] = by.get(r["reason"], 0) + 1
                print(f"..{uid[-6:]} {platform}: {len(games)} games, would record {by}")
            else:
                n = await store_skipped_games(db, uid, games, platform, name, should_analyze_game)
                print(f"..{uid[-6:]} {platform}: {len(games)} games, recorded {n}")
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
