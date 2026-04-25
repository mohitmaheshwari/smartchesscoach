"""
Diagnose a single game's result/color discrepancy.

Usage:
    python scripts/diagnose_game_result.py <game_id>

Prints the stored fields in the DB, the PGN headers, the user's stored
username, and compares — so you can see exactly why a won game is being
labeled as a loss (or vice versa).

No guesses — just prints what's on disk.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# Ensure we can import backend modules when run from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


def _grab(header: str, pgn: str) -> str:
    m = re.search(rf'\[{header}\s+"([^"]*)"\]', pgn or "")
    return m.group(1) if m else ""


async def main(game_id: str) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Connected: {mongo_url} / {db_name}")
    print(f"Looking up game_id={game_id}\n")

    game = await db.games.find_one({"game_id": game_id})
    if not game:
        print("NOT FOUND in db.games")
        return

    print("=" * 60)
    print("DB FIELDS (db.games)")
    print("=" * 60)
    for key in (
        "user_id", "platform", "user_color", "result", "opponent",
        "termination", "white_username", "black_username",
        "chess_com_url", "lichess_url", "opening", "created_at",
        "imported_at", "is_analyzed",
    ):
        if key in game:
            print(f"  {key}: {game[key]!r}")

    pgn = game.get("pgn") or ""
    print("\n" + "=" * 60)
    print("PGN HEADERS")
    print("=" * 60)
    for h in ("White", "Black", "Result", "Termination", "WhiteElo", "BlackElo", "Site"):
        print(f"  [{h}]: {_grab(h, pgn)!r}")

    # Look up the user's stored usernames
    user_id = game.get("user_id")
    if user_id:
        user = await db.users.find_one(
            {"user_id": user_id},
            {"_id": 0, "email": 1, "chess_com_username": 1, "chesscom_username": 1, "lichess_username": 1},
        )
        print("\n" + "=" * 60)
        print("USER RECORD (db.users)")
        print("=" * 60)
        if user:
            for k, v in user.items():
                print(f"  {k}: {v!r}")
        else:
            print("  not found")

    # Compute what user_color SHOULD be based on PGN headers vs stored username
    stored_lichess = (user or {}).get("lichess_username", "") if user_id else ""
    stored_chesscom = (user or {}).get("chess_com_username") or (user or {}).get("chesscom_username") or ""
    pgn_white = _grab("White", pgn).lower()
    pgn_black = _grab("Black", pgn).lower()

    print("\n" + "=" * 60)
    print("MATCH ANALYSIS")
    print("=" * 60)
    print(f"  PGN White: {pgn_white!r}")
    print(f"  PGN Black: {pgn_black!r}")
    print(f"  Stored lichess_username:  {stored_lichess!r}")
    print(f"  Stored chess.com_username: {stored_chesscom!r}")

    derived_color = None
    for candidate in (stored_lichess, stored_chesscom):
        if candidate:
            c = candidate.lower()
            if c == pgn_white:
                derived_color = "white"
                print(f"  -> MATCH white via {candidate!r}")
                break
            if c == pgn_black:
                derived_color = "black"
                print(f"  -> MATCH black via {candidate!r}")
                break

    if not derived_color:
        print("  -> NO MATCH against White/Black headers")

    stored_color = game.get("user_color")
    print(f"\n  Stored user_color: {stored_color!r}")
    print(f"  Derived user_color: {derived_color!r}")
    print(f"  PGN Result: {_grab('Result', pgn)!r}")
    print(f"  Stored result: {game.get('result')!r}")

    if derived_color and stored_color and derived_color != stored_color:
        print(
            f"\n  ⚠ MISMATCH: stored {stored_color!r} but PGN says user was {derived_color!r}."
            " This flips W/L in the UI."
        )
    elif not derived_color:
        print(
            "\n  ⚠ CANNOT DERIVE — no username match against PGN. "
            "Stored value came from fallback logic, may be wrong."
        )
    else:
        print(
            f"\n  Stored {stored_color!r} agrees with PGN-derived {derived_color!r}. "
            "If UI still says 'Lost' when user won, the bug is downstream of user_color."
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_game_result.py <game_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
