"""Import a player's missing game history from both sites, through the sync's own path.

Run INSIDE chess-coach-backend:  python scripts/backfill_game_history.py <user_id> [...]
DRY=1 counts without writing. Pipe the output to a file on the HOST: every
imported game prints an "UNDO <game_id>" line (undo = delete those game_ids
from games, analysis_queue and game_analyses).

Why (2026-11-17, Mohit's account): 152 games that should have been imported
were lost before the import fixes of 09fa78d9, and everything older than the
first sync's three-month window was never fetched (261 Lichess, 159
Chess.com). Each game goes through journey_service.import_one_game, the same
code the sync runs; skipped games (bullet, casual, short) get result records
only. Analysis is queued at BACKFILL_PRIORITY, behind routine syncs (5..9) and
just-finished games (10), so history never delays a game the player is waiting on.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import journey_service as js  # noqa: E402
from services.skipped_games import store_skipped_games  # noqa: E402

BACKFILL_PRIORITY = 1
H = {"User-Agent": "ChessGuru coach (history backfill)"}
DRY = os.environ.get("DRY") == "1"


def lichess_history(username):
    r = httpx.get(f"https://lichess.org/api/games/user/{username}",
                  params={"pgnInJson": "true", "clocks": "true", "evals": "false", "sort": "dateAsc"},
                  headers={**H, "Accept": "application/x-ndjson"}, timeout=600)
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


async def held_ids(db, uid):
    ids = set()
    async for g in db.games.find({"user_id": uid}, {"platform_game_id": 1, "url": 1}):
        ids.add(g.get("platform_game_id"))
        ids.add(g.get("url"))
    return ids


async def main(argv):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for uid in [a for a in argv if not a.startswith("--")]:
        u = await db.users.find_one({"user_id": uid}, {"lichess_username": 1, "chess_com_username": 1, "chesscom_username": 1})
        if not u:
            print(f"..{uid[-6:]} no such user")
            continue
        held = await held_ids(db, uid)
        for platform, name, fetch in (("lichess", u.get("lichess_username"), lichess_history),
                                      ("chess.com", u.get("chess_com_username") or u.get("chesscom_username"), chesscom_history)):
            if not name:
                continue
            games = fetch(name)
            eligible = [g for g in games if js.should_analyze_game(g, platform)]
            new = [g for g in eligible
                   if js.extract_platform_game_id(g, platform) not in held
                   and (g.get("url") if platform == "chess.com" else f"https://lichess.org/{g.get('id')}") not in held]
            print(f"..{uid[-6:]} {platform}: {len(games)} on the site, {len(eligible)} eligible, {len(new)} not held")
            if DRY:
                continue
            await store_skipped_games(db, uid, games, platform, name, js.should_analyze_game)
            imported = 0
            for g in new:
                doc = await js.import_one_game(db, uid, g, platform, name)
                if doc is None:
                    continue
                imported += 1
                print(f"UNDO {doc['game_id']}")
                if not await db.analysis_queue.find_one({"game_id": doc["game_id"]}):
                    await db.analysis_queue.insert_one({
                        "game_id": doc["game_id"], "user_id": uid, "pgn": doc.get("pgn", ""),
                        "user_color": doc.get("user_color", "white"), "status": "pending",
                        "priority": BACKFILL_PRIORITY, "queued_at": datetime.now(timezone.utc).isoformat(),
                        "auto_synced": True, "source": "history_backfill",
                    })
            print(f"..{uid[-6:]} {platform}: imported and queued {imported}")
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
