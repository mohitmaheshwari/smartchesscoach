"""
Dump every move of a single game in a format suitable for human review:
the engine facts + the currently-stored V5 caption, side by side.

Used during caption-quality design sessions. We read through the output
together, identify what's wrong with each caption, and use that to
design the fact extractor + renderer.

Usage (in container):
    python scripts/inspect_game_for_review.py --game-id <uuid>
    python scripts/inspect_game_for_review.py --game-id <uuid> --user-only
    python scripts/inspect_game_for_review.py --game-id <uuid> --mistakes-only
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _fmt_pv(pv):
    if not pv:
        return "(none)"
    return " ".join(str(m) for m in pv[:5])


def _fmt_eval(v):
    if v is None:
        return "—"
    if v >= 9000:
        return "+M"
    if v <= -9000:
        return "-M"
    return f"{v / 100:+.1f}"


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--game-id", required=True)
    p.add_argument("--user-only", action="store_true",
                   help="Skip opponent moves (still show context if useful)")
    p.add_argument("--mistakes-only", action="store_true",
                   help="Only mistakes, blunders, inaccuracies + opp_blunders")
    args = p.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    game = await db.games.find_one({"game_id": args.game_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": args.game_id}, {"_id": 0})
    if not game:
        print(f"No game found with game_id={args.game_id}")
        client.close()
        return 1
    if not analysis:
        print(f"No analysis found for game_id={args.game_id}")
        client.close()
        return 1

    user_color = (game.get("user_color") or "white").lower()
    opening = game.get("opening_name") or game.get("opening") or "—"
    eco = game.get("eco") or "—"
    result = game.get("user_result") or game.get("result") or "—"
    user_id = game.get("user_id")

    # Look up owner display name
    owner = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1, "email": 1})
    owner_name = (owner or {}).get("name") or (owner or {}).get("email") or user_id

    print("=" * 78)
    print(f"GAME: {args.game_id}")
    print(f"  Owner       : {owner_name}  ({user_id})")
    print(f"  User color  : {user_color}")
    print(f"  Opening     : {opening} ({eco})")
    print(f"  Result      : {result}")
    print(f"  Imported    : {game.get('imported_at', '—')}")
    regen_at = analysis.get("decryption_v5_regen_at") or "— (not regenerated)"
    print(f"  Regen at    : {regen_at}")
    print("=" * 78)
    print()

    decryption = analysis.get("decryption_v5_data") or []
    if not decryption:
        print("No decryption_v5_data — the analysis hasn't run V5 generation yet.")
        client.close()
        return 1

    # Build a lookup from move_evaluations so we can pull engine facts.
    sf = analysis.get("stockfish_analysis") or {}
    move_evals_list = sf.get("move_evaluations") or []
    eval_by_fen = {}
    for me in move_evals_list:
        fen = me.get("fen_before") or ""
        if fen:
            eval_by_fen[" ".join(fen.split()[:4])] = me

    SEVERITIES_INTEREST = {"mistake", "blunder", "inaccuracy", "opp_blunder", "opp_mistake"}

    for item in decryption:
        is_user = item.get("is_user_move", False)
        severity = (item.get("severity") or "").strip().lower()
        if args.user_only and not is_user:
            continue
        if args.mistakes_only and severity not in SEVERITIES_INTEREST:
            continue

        move_number = item.get("move_number")
        move_san = item.get("move_san")
        is_white = item.get("is_white", True)
        side = "W" if is_white else "B"
        who = "USER" if is_user else "OPP"

        fen_before = item.get("fen_before", "")
        fen_key = " ".join(fen_before.split()[:4])
        me = eval_by_fen.get(fen_key, {})

        eval_before = me.get("eval_before") if is_user else item.get("eval_before")
        eval_after = me.get("eval_after") if is_user else item.get("eval_after")
        cp_loss = item.get("cp_loss", 0)
        best_move = item.get("best_move_san") or me.get("best_move")
        best_move_uci = item.get("best_move_uci", "")
        pv_after_played = me.get("pv_after_played") or item.get("pv_after_played", [])
        pv_after_best = me.get("pv_after_best") or item.get("pv_after_best", [])

        print("─" * 78)
        print(f"  Move {move_number}{'.' if is_white else '...'} {move_san}   ({side}, {who}, {severity or 'context'})")
        print(f"  FEN(before): {fen_before[:60]}{'…' if len(fen_before) > 60 else ''}")
        print(f"  eval_before={_fmt_eval(eval_before)}  eval_after={_fmt_eval(eval_after)}  cp_loss={cp_loss}")
        if best_move:
            played_clean = (move_san or "").rstrip("!?+#")
            best_clean = (best_move or "").rstrip("!?+#")
            tag = "  ← USER PLAYED BEST" if played_clean == best_clean else ""
            print(f"  best_move:   {best_move}{tag}")
        print(f"  pv_after_played: {_fmt_pv(pv_after_played)}")
        print(f"  pv_after_best:   {_fmt_pv(pv_after_best)}")

        # ── Stored captions ──
        print()
        print(f"  STORED narrative   : {item.get('narrative') or '(empty)'}")
        plan = item.get("plan") or {}
        if plan:
            cp = plan.get("current_problem")
            cs = plan.get("consequence")
            ba = plan.get("better_approach")
            tl = plan.get("transferable_learning")
            if cp: print(f"  STORED problem     : {cp}")
            if cs: print(f"  STORED consequence : {cs}")
            if ba: print(f"  STORED better      : {ba}")
            if tl: print(f"  STORED learning    : {tl}")
        ypn = item.get("your_plan_now")
        if ypn:
            print(f"  STORED your_plan_now: {ypn}")
        print()

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
