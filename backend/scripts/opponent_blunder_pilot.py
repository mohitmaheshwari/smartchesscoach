"""
PILOT: does opponent play explain the "unexplained" rating gains?
================================================================


We analyse only the user's moves -- 3 of 14,806 analyses contain an opponent
move -- so "did my opponents get worse?" is unanswerable from stored data. This
evaluates BOTH sides on a sample of games for users whose rating moved with no
measurable change in their own accuracy.

Validity check built in: the user blunder rate computed here must roughly match
the rate already stored for the same games. If it doesn't, the method is wrong
and the opponent numbers mean nothing either.

Depth 12 (the codebase's QUICK_DEPTH) -- adequate for a >=150cp blunder RATE,
not for fine judgement of a single move.

Reference run, 2026-09-11, 3 users, 25 games per half:
  opponent blunders per game, early half -> late half
    user_76ee10b87522   3.56 -> 3.12
    user_614cc832fc89   4.04 -> 3.32
    user_a66b5bb10c86   2.80 -> 2.64
  All three fell. "My opponents got worse" does not explain these gains --
  the opponents got BETTER and the players climbed anyway.

The incidental finding is the more valuable one: opponents blunder 2.6-4.0
times per game and we analyse none of it (3 opponent moves across 14,806
stored analyses), so "you had a chance here and missed it" is a whole
coaching category the product cannot currently see.

    docker exec chess-coach-backend python scripts/opponent_blunder_pilot.py \n        --users user_76ee10b87522,user_614cc832fc89
"""
import argparse
import asyncio
import io
import os
import random
import sys
from collections import Counter
from pathlib import Path

import chess
import chess.engine
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.game_dates import game_played_at

DEPTH = 12
BLUNDER_CP = 150
GAMES_PER_HALF = 25
MAX_PLIES = 90
ENGINE = "/usr/games/stockfish"


def cp_from(info, pov):
    score = info["score"].pov(pov)
    return score.score(mate_score=10000)


def analyse_game(engine, pgn_text, user_is_white):
    """Return (user_blunders, opp_blunders, user_moves, opp_moves)."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return None
    board = game.board()
    moves = list(game.mainline_moves())[:MAX_PLIES]
    if len(moves) < 10:
        return None

    counts = Counter()
    prev_cp = None
    prev_mover = None
    for move in moves:
        mover = board.turn
        info = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
        best_cp = cp_from(info, mover)
        board.push(move)
        after = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
        after_cp = cp_from(after, mover)  # same POV as the mover
        loss = max(0, best_cp - after_cp)
        is_user = (mover == chess.WHITE) == user_is_white
        counts["user_moves" if is_user else "opp_moves"] += 1
        if loss >= BLUNDER_CP:
            counts["user_blunders" if is_user else "opp_blunders"] += 1
    return counts


async def main():
    parser = argparse.ArgumentParser(description="opponent blunder pilot")
    parser.add_argument("--users", required=True,
                        help="comma-separated user_ids")
    parser.add_argument("--games-per-half", type=int,
                        default=GAMES_PER_HALF)
    args = parser.parse_args()
    users = [u.strip() for u in args.users.split(",") if u.strip()]
    per_half = args.games_per_half

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE)
    random.seed(7)

    print(f"depth {DEPTH}, blunder >= {BLUNDER_CP}cp, "
          f"{per_half} games per half\n")
    for uid in users:
        games = await db.games.find(
            {"user_id": uid, "is_analyzed": True, "pgn": {"$exists": True}},
            {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1,
             "date_played": 1, "date_played_iso": 1},
        ).to_list(length=None)
        dated = [(w, g) for g in games if (w := game_played_at(g))]
        if len(dated) < 100:
            print(f"{uid}: too few dated games ({len(dated)})")
            continue
        dated.sort(key=lambda p: p[0])
        half = len(dated) // 2
        halves = {"early": dated[:half], "late": dated[half:]}

        print(f"=== {uid} ({len(dated)} games) ===")
        for label, rows in halves.items():
            sample = random.sample(rows, min(per_half, len(rows)))
            totals = Counter()
            stored_blunders = 0
            stored_moves = 0
            for _, g in sample:
                white = str(g.get("user_color") or "").lower().startswith("w")
                try:
                    counts = analyse_game(engine, g.get("pgn") or "", white)
                except Exception:
                    counts = None
                if counts:
                    totals.update(counts)
                doc = await db.game_analyses.find_one(
                    {"game_id": g.get("game_id")},
                    {"_id": 0, "stockfish_analysis.move_evaluations": 1},
                )
                for m in ((doc or {}).get("stockfish_analysis") or {}).get(
                        "move_evaluations", []) or []:
                    if m.get("is_opponent_move"):
                        continue
                    stored_moves += 1
                    if int(m.get("cp_loss") or 0) >= BLUNDER_CP:
                        stored_blunders += 1

            n = max(1, len(sample))
            u_rate = totals["user_blunders"] / n
            o_rate = totals["opp_blunders"] / n
            stored_rate = stored_blunders / n
            print(f"  {label:6} n={n:3}  "
                  f"user {u_rate:5.2f}/game   OPPONENT {o_rate:5.2f}/game   "
                  f"(stored user rate {stored_rate:5.2f} — validity check)")
        print()

    engine.quit()


if __name__ == "__main__":
    asyncio.run(main())
