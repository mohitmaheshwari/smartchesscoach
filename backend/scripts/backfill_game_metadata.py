"""
backfill_game_metadata.py — populate canonical game-doc fields on EXISTING games.

Built 2026-06-06 (PROGRESS_BACKLOG #4). New games get these at sync time
(journey_service.sync_user_games); this backfills the ~6600 already-imported
games so Dashboard.jsx / LabV2 (which read g.opponent / g.white / g.black /
g.date_played) stop rendering blank.

Sets, only when missing:
  - opponent  = opponent_name (already populated)
  - white     = white_player
  - black     = black_player
  - date_played = parsed from PGN [UTCDate]/[Date]

Run ON a host with Mongo access (tunnel or server):
  docker exec chess-coach-backend python /app/backend/scripts/backfill_game_metadata.py --apply
Dry-run (default) prints counts without writing.
"""
import os, re, sys, asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

APPLY = "--apply" in sys.argv


def parse_pgn_date(pgn):
    if not pgn:
        return None
    dm = re.search(r'\[UTCDate\s+"(\d{4})\.(\d{2})\.(\d{2})"\]', pgn) \
        or re.search(r'\[Date\s+"(\d{4})\.(\d{2})\.(\d{2})"\]', pgn)
    if not dm:
        return None
    tm = re.search(r'\[UTCTime\s+"(\d{2}):(\d{2}):(\d{2})"\]', pgn)
    try:
        if tm:
            return datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                            int(tm.group(1)), int(tm.group(2)), int(tm.group(3)),
                            tzinfo=timezone.utc).isoformat()
        return datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                        tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    scanned = updated = 0
    set_opp = set_white = set_black = set_date = 0
    async for g in db.games.find({}, {"pgn": 1, "white_player": 1, "black_player": 1,
                                      "opponent_name": 1, "opponent": 1, "white": 1,
                                      "black": 1, "date_played": 1, "game_id": 1}):
        scanned += 1
        upd = {}
        if not g.get("opponent") and g.get("opponent_name"):
            upd["opponent"] = g["opponent_name"]; set_opp += 1
        if not g.get("white") and g.get("white_player"):
            upd["white"] = g["white_player"]; set_white += 1
        if not g.get("black") and g.get("black_player"):
            upd["black"] = g["black_player"]; set_black += 1
        if not g.get("date_played"):
            d = parse_pgn_date(g.get("pgn"))
            if d:
                upd["date_played"] = d; set_date += 1
        if upd:
            updated += 1
            if APPLY:
                await db.games.update_one({"game_id": g["game_id"]}, {"$set": upd})
    mode = "APPLIED" if APPLY else "DRY-RUN (use --apply to write)"
    print(f"[{mode}] scanned={scanned} games_needing_update={updated}")
    print(f"  would set: opponent={set_opp} white={set_white} black={set_black} date_played={set_date}")


if __name__ == "__main__":
    asyncio.run(main())
