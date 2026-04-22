"""
Diagnose what `compute_game_summary` produces for a specific game, and why.

Prints the stored Stockfish analysis, the top moves by cp_loss across both
sides, the user-move filter result, and the final summary output. Used to
trace cases where the coach verdict disagrees with the human read of the
game (e.g. "slow bleed" on a game where the user clearly hung a queen).

Usage:
  docker cp scripts/diagnose_game_summary.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/diagnose_game_summary.py <game_id>

Example:
  docker exec -it chess-coach-backend python3 scripts/diagnose_game_summary.py 7064bd25-7462-442c-ae8c-1ad2f01b475e
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    parser = argparse.ArgumentParser(description="Diagnose compute_game_summary for one game.")
    parser.add_argument("game_id", help="The game_id to diagnose.")
    parser.add_argument("--top", type=int, default=8, help="How many top moves to list (default 8).")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")

    client = AsyncIOMotorClient(url)
    db = client[db_name]

    g = await db.games.find_one(
        {"game_id": args.game_id},
        {"_id": 0, "user_id": 1, "user_color": 1, "user_plays_as": 1, "result": 1, "opening": 1, "platform": 1},
    )
    print(f"game: {g}")
    if not g:
        print("no game doc found")
        return

    a = await db.game_analyses.find_one(
        {"game_id": args.game_id},
        {
            "_id": 0,
            "stockfish_analysis.move_evaluations": 1,
            "stockfish_analysis.blunders": 1,
            "stockfish_analysis.mistakes": 1,
            "stockfish_analysis.accuracy": 1,
        },
    )
    if not a:
        print("no analysis doc found")
        return

    sf = a.get("stockfish_analysis") or {}
    moves = sf.get("move_evaluations") or []
    print(f"total move_evaluations: {len(moves)}")
    print(f"stored stats — blunders: {sf.get('blunders')}  mistakes: {sf.get('mistakes')}  accuracy: {sf.get('accuracy')}")

    if not moves:
        print("move_evaluations is empty — nothing to diagnose")
        return

    # Top N by cp_loss across BOTH sides
    ranked = sorted(enumerate(moves), key=lambda kv: (kv[1].get("cp_loss") or 0), reverse=True)[: args.top]
    print(f"\ntop {args.top} by cp_loss (across BOTH sides):")
    print(f"  {'idx':>4}  {'move_no':>7}  {'san':>8}  {'cp_loss':>7}  {'best':>8}  {'eval_before':>12}  {'eval_after':>11}")
    for idx, m in ranked:
        print(
            f"  {idx:>4}  "
            f"{str(m.get('move_number','?')):>7}  "
            f"{str(m.get('move','?')):>8}  "
            f"{str(m.get('cp_loss',0)):>7}  "
            f"{str(m.get('best_move','?')):>8}  "
            f"{str(m.get('eval_before','?')):>12}  "
            f"{str(m.get('eval_after','?')):>11}"
        )

    uc = (g.get("user_color") or g.get("user_plays_as") or "white").lower()
    user_is_white = uc == "white"

    # Reproduce compute_game_summary's user-move filter (i % 2 parity)
    user_moves_by_parity = [(i, m) for i, m in enumerate(moves) if (i % 2 == 0) == user_is_white]
    print(f"\nuser_color = {uc}")
    print(f"user_moves count via i%2 parity = {len(user_moves_by_parity)} (of {len(moves)} total)")
    if user_moves_by_parity:
        biggest = max(user_moves_by_parity, key=lambda kv: kv[1].get("cp_loss") or 0)
        print(
            f"biggest user cp_loss by parity filter: idx={biggest[0]}  "
            f"move_no={biggest[1].get('move_number')}  san={biggest[1].get('move')}  "
            f"cp_loss={biggest[1].get('cp_loss')}"
        )

    # Show whether move_evaluations looks like [W,B,W,B,...] or user-only
    # (Use the first few moves' raw 'move' SAN — White opens on a pawn/knight
    # square from rank 2/1; if moves[1] also looks like a white move, the
    # array is probably user-only.)
    first_few = [m.get("move", "?") for m in moves[:6]]
    print(f"\nfirst 6 stored SANs: {first_few}")
    print("(if these look like [white, black, white, black, ...] the parity filter is correct;")
    print(" if they all look like one side's moves, the array is user-only and the filter is wrong)")

    # Show what compute_game_summary returns
    from services.game_coach_summary import compute_game_summary

    summary = compute_game_summary(moves, g.get("result", ""), uc, g.get("opening", "") or "")
    print("\ncompute_game_summary result:")
    print(f"  diagnosis:   {summary.get('diagnosis')}")
    print(f"  root_cause:  {summary.get('root_cause')}")
    print(f"  critical_move: {summary.get('critical_move')}")
    for i, c in enumerate(summary.get("context") or []):
        print(f"  context[{i}]: {c}")


if __name__ == "__main__":
    asyncio.run(main())
