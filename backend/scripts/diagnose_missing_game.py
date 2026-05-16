"""
Diagnose why a specific game isn't showing on a user's Lab page.

Walks the data path top-to-bottom:
  1. Find the user by email
  2. List that user_id's recent games (matches what lab.py:237 queries)
  3. Find ANY game (across all users) involving the opponent name
  4. Cross-check: if such games exist, do they have the user's user_id?
  5. Check is_active / is_analyzed / analysis_status

Usage:
  docker exec chess-coach-backend python scripts/diagnose_missing_game.py <email> <opponent_substring>

Example:
  docker exec chess-coach-backend python scripts/diagnose_missing_game.py bhutramohit@gmail.com walloo21
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient


async def main(email: str, opp_substr: str) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"Looking up email: {email!r}")
    print(f"Opponent substring: {opp_substr!r}")
    print("=" * 70)

    # 1. Find user(s) by email — could be more than one if duplicates exist
    users = await db.users.find({"email": email}, {"_id": 0}).to_list(10)
    print(f"\n[1] Users matching email: {len(users)}")
    for u in users:
        print(f"    user_id={u.get('user_id')}  is_reviewer={u.get('is_reviewer')}  "
              f"is_admin={u.get('is_admin')}  chess_com_username={u.get('chess_com_username')}  "
              f"lichess_username={u.get('lichess_username')}  created_at={u.get('created_at')}")
    if not users:
        print("    NO USER FOUND — auth account doesn't exist under this email.")
        return

    user_ids = [u.get("user_id") for u in users if u.get("user_id")]

    # 2. List games for this user_id (matches lab.py filter)
    print(f"\n[2] Games owned by these user_ids (lab.py filter: is_active != False):")
    lab_visible = []
    async for g in db.games.find(
        {"user_id": {"$in": user_ids}, "is_active": {"$ne": False}},
        {"_id": 0, "game_id": 1, "white_player": 1, "black_player": 1,
         "user_color": 1, "opening": 1, "result": 1, "imported_at": 1,
         "is_analyzed": 1, "analysis_status": 1, "is_active": 1, "user_id": 1},
    ):
        lab_visible.append(g)
    print(f"    Total visible on lab: {len(lab_visible)}")

    # Filter to ones involving the opponent
    matching = [
        g for g in lab_visible
        if opp_substr.lower() in (g.get("white_player") or "").lower()
        or opp_substr.lower() in (g.get("black_player") or "").lower()
    ]
    print(f"    Of those, involving '{opp_substr}': {len(matching)}")
    for g in matching[:5]:
        print(f"      game_id={g.get('game_id')}  W={g.get('white_player')}  "
              f"B={g.get('black_player')}  is_analyzed={g.get('is_analyzed')}  "
              f"imported_at={g.get('imported_at')}")

    # 3. Cross-check: ANY game in the DB involving this opponent
    print(f"\n[3] Games anywhere in DB involving '{opp_substr}':")
    any_match = []
    async for g in db.games.find(
        {"$or": [
            {"white_player": {"$regex": opp_substr, "$options": "i"}},
            {"black_player": {"$regex": opp_substr, "$options": "i"}},
        ]},
        {"_id": 0, "game_id": 1, "white_player": 1, "black_player": 1,
         "user_id": 1, "is_active": 1, "is_analyzed": 1, "analysis_status": 1,
         "imported_at": 1, "platform": 1},
    ):
        any_match.append(g)
    print(f"    Total found across all users: {len(any_match)}")
    for g in any_match[:10]:
        owned_by_target = g.get("user_id") in user_ids
        marker = "OWNED" if owned_by_target else f"OTHER USER ({g.get('user_id')})"
        print(f"      [{marker}] game_id={g.get('game_id')}  "
              f"W={g.get('white_player')}  B={g.get('black_player')}  "
              f"is_active={g.get('is_active')}  is_analyzed={g.get('is_analyzed')}  "
              f"analysis_status={g.get('analysis_status')}  imported_at={g.get('imported_at')}")

    # 4. If no matches anywhere — clearly a sync issue
    if not any_match:
        print(f"\n[4] NO MATCHES anywhere. Game vs '{opp_substr}' was never synced.")
        print("    Next step: check journey_service / sync flow for this user.")
        for u in users:
            print(f"      Chess.com username on file: {u.get('chess_com_username')!r}")
            print(f"      Lichess username on file:   {u.get('lichess_username')!r}")
        return

    # 5. Matches exist somewhere — diagnose why not visible
    print("\n[5] Diagnosis:")
    owned = [g for g in any_match if g.get("user_id") in user_ids]
    other = [g for g in any_match if g.get("user_id") not in user_ids]
    if owned and matching:
        print("    Games exist, ARE owned, ARE visible. Refresh the lab page.")
    elif owned and not matching:
        print("    Games exist + owned, but flagged inactive (is_active=False).")
        for g in owned[:5]:
            print(f"      game_id={g.get('game_id')}  is_active={g.get('is_active')}")
    elif other:
        print(f"    Games exist but owned by a DIFFERENT user_id: {sorted({g.get('user_id') for g in other})}")
        print("    The chess.com username may be linked to that other account.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/diagnose_missing_game.py <email> <opponent_substring>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
