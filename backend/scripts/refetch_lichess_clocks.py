"""Re-fetch lichess PGNs that were stored without clocks; dry-run by default.

The manual import (routes/analysis.py, used by onboarding) asked lichess for
games without `clocks=true`, so 577 lichess games (15 users) were stored with
no [%clk] and no think-time (measured 2026-11-09). Lichess still serves the
clocks for those games by id.

A game is updated only when the re-fetched PGN has clocks AND its mainline is
move-for-move the stored one, so the stored analysis still matches the moves.
The old PGN is written to --undo-file before anything changes.

    python scripts/refetch_lichess_clocks.py                 # dry run
    python scripts/refetch_lichess_clocks.py --write --undo-file /tmp/x.json

Afterwards run backfill_move_think_time.py and backfill_move_time_stats.py so
the analyses and the game-level stats pick the clocks up.
"""
import argparse
import asyncio
import io
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import chess.pgn
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

EXPORT_URL = "https://lichess.org/api/games/export/_ids"
BATCH = 300  # lichess limit for this endpoint
HEADERS = {"Accept": "application/x-ndjson", "User-Agent": "ChessCoachAI/1.0"}


def mainline_uci(pgn: str):
    game = chess.pgn.read_game(io.StringIO(pgn or ""))
    if game is None:
        return None
    return [m.uci() for m in game.mainline_moves()]


async def fetch_batch(client, ids):
    for attempt in range(4):
        resp = await client.post(
            EXPORT_URL,
            params={"clocks": "true", "pgnInJson": "true", "evals": "false"},
            content=",".join(ids),
            headers=HEADERS,
        )
        if resp.status_code == 429:
            await asyncio.sleep(60)
            continue
        resp.raise_for_status()
        out = {}
        for line in resp.text.splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("id") and row.get("pgn"):
                    out[row["id"]] = row["pgn"]
        return out
    raise RuntimeError("lichess kept answering 429")


async def main(args):
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")]
    rows = [g async for g in db.games.find(
        {"platform": "lichess", "pgn": {"$not": re.compile("%clk")},
         "platform_game_id": {"$nin": [None, ""]}},
        {"_id": 1, "game_id": 1, "user_id": 1, "platform_game_id": 1, "pgn": 1})]
    if args.limit:
        rows = rows[: args.limit]

    counts = Counter(candidates=len(rows))
    undo, users = [], set()
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i: i + BATCH]
            fetched = await fetch_batch(client, [r["platform_game_id"] for r in chunk])
            for r in chunk:
                new = fetched.get(r["platform_game_id"])
                if not new:
                    counts["not_returned"] += 1
                    continue
                if "%clk" not in new:
                    counts["no_clock_on_lichess"] += 1
                    continue
                old_moves, new_moves = mainline_uci(r["pgn"]), mainline_uci(new)
                if not old_moves or old_moves != new_moves:
                    counts["moves_differ_skipped"] += 1
                    continue
                counts["will_update"] += 1
                users.add(r["user_id"])
                if args.write:
                    undo.append({"game_id": r["game_id"], "user_id": r["user_id"], "pgn": r["pgn"]})
            if args.write:
                if args.undo_file and undo:
                    Path(args.undo_file).write_text(json.dumps(undo))
                for r in chunk:
                    new = fetched.get(r["platform_game_id"])
                    if not new or "%clk" not in new:
                        continue
                    if mainline_uci(r["pgn"]) != mainline_uci(new):
                        continue
                    res = await db.games.update_one(
                        {"_id": r["_id"], "pgn": r["pgn"]},
                        {"$set": {"pgn": new,
                                  "pgn_clocks_refetched_at": datetime.now(timezone.utc).isoformat()}})
                    counts["updated"] += res.modified_count
            await asyncio.sleep(1)

    print(json.dumps({"mode": "write" if args.write else "dry_run", **counts,
                      "users": len(users)}, indent=2))
    if args.users_file:
        Path(args.users_file).write_text("\n".join(sorted(users)))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--undo-file", default="")
    p.add_argument("--users-file", default="")
    a = p.parse_args()
    if a.write and not a.undo_file:
        sys.exit("--write needs --undo-file")
    asyncio.run(main(a))
