"""
Merge duplicate users that share the same chess.com username.

Background: there's no unique-index on `users.chess_com_username`, so the
same chess.com handle can be linked to two separate user_ids. Confirmed
cases as of writing:
  - chesstesterone → 2 user_ids
  - parthgilda     → 2 user_ids

Both users get the same games synced and their coach memory diverges.
This script reports all duplicate handles and (with --apply) merges the
newer account into the older one.

USAGE:
    python merge_duplicate_chesscom_users.py            # dry-run report
    python merge_duplicate_chesscom_users.py --apply    # actually merge
    python merge_duplicate_chesscom_users.py --apply --handle chesstesterone   # specific

SAFETY:
  - Default is DRY RUN. Prints what would change. No DB writes.
  - --apply still requires --handle for one-at-a-time runs in production.
  - Always picks the OLDER user (by created_at) as the surviving one.
  - Migrates references in: games, game_analyses, coach_sessions,
    coach_messages, puzzle_attempts, player_profiles, player_identities,
    coach_memory, notifications, postgame_analyses, journey_stats,
    behavioral_missions, thinking_scores, user_concept_understanding,
    coaching_feedback_cache, training_solve_attempts, module_injections,
    trap_tracking.
  - Marks the merged-from user as deleted: sets users.merged_into = <surviving uid>
    and users.deleted_at instead of removing the row (rollback safety).
"""
import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


COLLECTIONS_WITH_USER_ID = [
    "games", "game_analyses", "coach_sessions", "coach_messages",
    "puzzle_attempts", "player_profiles", "player_identities",
    "coach_memory", "notifications", "postgame_analyses",
    "journey_stats", "behavioral_missions", "thinking_scores",
    "user_concept_understanding", "coaching_feedback_cache",
    "training_solve_attempts", "module_injections", "trap_tracking",
    "community_puzzles", "community_training_positions",
    "user_sessions", "coaching_phrases",
]


async def find_duplicate_handles(db) -> dict:
    """Return {handle: [user_doc, user_doc, ...]} for handles owned by >1 user."""
    by_handle = defaultdict(list)
    async for u in db.users.find(
        {"chess_com_username": {"$ne": None}},
        {"user_id": 1, "chess_com_username": 1, "name": 1, "email": 1, "created_at": 1, "_id": 0},
    ):
        by_handle[u["chess_com_username"]].append(u)
    return {h: users for h, users in by_handle.items() if len(users) > 1}


def pick_surviving(users: list) -> tuple:
    """The user with earliest created_at wins. Returns (winner, [losers])."""
    def _ts(u):
        v = u.get("created_at")
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                pass
        if isinstance(v, datetime):
            return v
        return datetime.max.replace(tzinfo=timezone.utc)
    sorted_users = sorted(users, key=_ts)
    return sorted_users[0], sorted_users[1:]


async def merge_pair(db, winner_uid: str, loser_uid: str, apply: bool):
    """Move all DB references from loser_uid to winner_uid."""
    moved = {}
    for coll in COLLECTIONS_WITH_USER_ID:
        n = await db[coll].count_documents({"user_id": loser_uid})
        if n == 0:
            continue
        moved[coll] = n
        if apply:
            await db[coll].update_many(
                {"user_id": loser_uid},
                {"$set": {"user_id": winner_uid}},
            )
    # Mark the loser user as merged (don't delete — keep audit trail).
    if apply:
        await db.users.update_one(
            {"user_id": loser_uid},
            {"$set": {
                "merged_into": winner_uid,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    return moved


async def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true",
                   help="Actually do the merge. Default is dry-run report only.")
    p.add_argument("--handle", default=None,
                   help="Limit to a single chess.com handle (required with --apply).")
    args = p.parse_args()

    if args.apply and not args.handle:
        sys.exit("--apply requires --handle <chesscom_username> "
                 "to avoid accidental bulk merges. Run dry-run first.")

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        sys.exit("MONGO_URL not set")
    db_name = os.environ.get("DB_NAME", "chess_coach")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    dupes = await find_duplicate_handles(db)
    if args.handle:
        dupes = {args.handle: dupes[args.handle]} if args.handle in dupes else {}

    if not dupes:
        print("No duplicate chess.com handles found.")
        return

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== {mode} — {len(dupes)} duplicate handle(s) found ===\n")

    for handle, users in dupes.items():
        winner, losers = pick_surviving(users)
        print(f"chess.com handle: {handle}")
        print(f"  KEEP:   {winner['user_id']}  ({winner.get('name')}, {winner.get('email')}, created={winner.get('created_at')})")
        for L in losers:
            print(f"  MERGE:  {L['user_id']}  ({L.get('name')}, {L.get('email')}, created={L.get('created_at')})")
            moved = await merge_pair(db, winner["user_id"], L["user_id"], apply=args.apply)
            if moved:
                lines = ", ".join(f"{k}={v}" for k, v in sorted(moved.items()))
                print(f"     refs to migrate: {lines}")
            else:
                print(f"     (no references to migrate)")
        print()

    if not args.apply:
        print("\nNothing was changed. Re-run with --apply --handle <name> to do it.")


if __name__ == "__main__":
    asyncio.run(main())
