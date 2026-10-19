"""Rewind sync watermarks so games already lost behind them come back.

The old sync stamped `last_game_sync = now()`. Lichess's `since` filters on
when a game STARTED and the API does not return a game still being played, so
any game in progress during a sync fell permanently behind the watermark.
Measured 2026-10-19 on user_8b599930d7ef: the last game started 08:10:15 and
ended 08:21:34, the sync ran at 08:14:28, and `since=08:14:28` now returns
nothing while `since=08:00:00` still returns the game. 7 of 61 games eligible
by our own filters since Oct 1 were missing -- 11% of everything played.

Fixing the watermark forward stops new loss but does not recover the old. This
moves each platform watermark back so the next sync re-reads the window.
Re-reading is safe only once `migrate_platform_game_id.py --apply` has built
the unique index -- otherwise re-importing is how duplicates were made in the
first place. The script refuses to run without it.

    python scripts/rewind_sync_watermarks.py                  # dry run
    python scripts/rewind_sync_watermarks.py --days 30 --apply
    python scripts/rewind_sync_watermarks.py --user user_8b599930d7ef --apply

Watermarks are only ever moved BACK, never forward.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

INDEX_NAME = "games_platform_game_id_unique"

PLATFORM_FIELDS = {
    "lichess": ("lichess_username", "last_game_sync_lichess"),
    "chess.com": ("chess_com_username", "last_game_sync_chesscom"),
}


def _as_epoch(value) -> int | None:
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    if isinstance(value, str) and value:
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    if isinstance(value, datetime):
        stamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(stamp.timestamp())
    return None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30,
                        help="how far back to rewind each watermark (default 30)")
    parser.add_argument("--user", help="limit to one user_id")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--db", default=os.environ.get("DB_NAME", "chess_coach"))
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[args.db]

    # The guard. Re-reading a window without the unique index is exactly the
    # condition that produced 13 duplicate rows on one account.
    index_names = [ix["name"] async for ix in db.games.list_indexes()]
    if INDEX_NAME not in index_names:
        print(f"REFUSING: {INDEX_NAME} is not present on games.")
        print("Run scripts/migrate_platform_game_id.py --apply first, or a rewind")
        print("will re-import games as duplicates instead of recognising them.")
        return 1

    target = int((datetime.now(timezone.utc) - timedelta(days=args.days)).timestamp())
    readable = datetime.fromtimestamp(target, timezone.utc).strftime("%Y-%m-%d %H:%M")
    mode = "APPLY" if args.apply else "DRY RUN (nothing is written)"
    print(f"database: {args.db}   mode: {mode}")
    print(f"rewinding watermarks to {readable} UTC ({args.days} days back)\n")

    query = {"user_id": args.user} if args.user else {}
    query["$or"] = [{"lichess_username": {"$nin": [None, ""]}},
                    {"chess_com_username": {"$nin": [None, ""]}}]

    touched = 0
    unchanged = 0
    async for user in db.users.find(query, {"_id": 0}):
        updates = {}
        notes = []
        for platform, (username_field, watermark_field) in PLATFORM_FIELDS.items():
            if not user.get(username_field):
                continue
            current = _as_epoch(user.get(watermark_field)) or _as_epoch(user.get("last_game_sync"))
            if current is None:
                # No watermark at all means the next sync is a first sync and
                # already reaches back FIRST_SYNC_MONTHS. Leave it alone.
                notes.append(f"{platform}: no watermark, first sync will cover it")
                continue
            if current <= target:
                notes.append(f"{platform}: already at or behind target")
                continue
            updates[watermark_field] = target
            moved = (current - target) / 86400.0
            notes.append(f"{platform}: {datetime.fromtimestamp(current, timezone.utc):%Y-%m-%d %H:%M}"
                         f" -> {readable}  (back {moved:.1f}d)")

        if not updates:
            unchanged += 1
            continue

        touched += 1
        if touched <= 15 or args.user:
            print(f"{user['user_id']}")
            for note in notes:
                print(f"   {note}")

        if args.apply:
            # The shared field is the first-sync sentinel, so it must stay set
            # and must not sit ahead of the per-platform ones.
            updates["last_game_sync"] = datetime.fromtimestamp(target, timezone.utc).isoformat()
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})

    print(f"\nusers {'rewound' if args.apply else 'that would be rewound'}: {touched:,}")
    print(f"users left alone: {unchanged:,}")
    if not args.apply:
        print("\nnothing was written. re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
