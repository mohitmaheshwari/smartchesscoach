"""
When we call a recommended capture a "trade", is it one?
========================================================


_recommended_move_why describes a recommended capture from the static exchange
value on the target square:

    SEE >= 200        -> "wins material"
    SEE >=  80        -> "wins a pawn" / "wins material"
    anything else     -> "trades his {piece}"      <- no floor underneath

Flagged live on game 46edaf7e move 8: "Play Nxb5 - it trades his pawn", where
SEE on b5 is -200 and the point of the move is that taking back with the a6
pawn hangs the rook on a8 to Rxa8. Measure the SEE distribution of every
capture this function calls a trade before choosing where the floor goes, and
count how often the board can prove the real reason.

Reference run, 2026-09-11, 500 games: 1,376 recommended captures get a why,
506 of them called a trade, and 128 of those (25.3%) sit at SEE <= -50 -- 110
below -100. Of the 128, the board can prove that every recapture costs the
opponent something >= 150cp in 30 cases; the other 98 fall through to the
board-verified threat/escape/defends/principle branches.

    docker exec chess-coach-backend python scripts/trade_claim_distribution.py
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from collections import Counter

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motor.motor_asyncio import AsyncIOMotorClient
from services.caption_facts import (
    _recommended_move_why,
    legally_hanging_pieces,
    static_exchange_eval,
)

DEFAULT_GAMES = 500
PROOF_FLOOR = 150


def bucket(see):
    if see is None:
        return "no SEE"
    for hi in (-400, -300, -200, -100, -50, 0, 50, 80):
        if see < hi:
            return f"< {hi}"
    return ">= 80"


def deflection_proof(board, move):
    """After the capture, does the opponent's recapture hang something bigger?

    Uses legally_hanging_pieces, the same exchange-truth authority the
    loose-piece card already trusts. Returns the biggest thing that falls.
    """
    after = board.copy(stack=False)
    after.push(move)
    best = None
    for reply in after.legal_moves:
        if not after.is_capture(reply) or reply.to_square != move.to_square:
            continue
        probe = after.copy(stack=False)
        probe.push(reply)
        for item in legally_hanging_pieces(probe, not board.turn, PROOF_FLOOR):
            loss = int(item.get("material_loss_cp") or 0)
            if best is None or loss > best[0]:
                best = (loss, item.get("piece_type"), item.get("square"))
    return best


async def main():
    parser = argparse.ArgumentParser(description="trade claim distribution")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES)
    args = parser.parse_args()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    seen = Counter()
    trades = Counter()
    provable = Counter()
    examples = []

    async for doc in db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).limit(args.games):
        for ev in doc["stockfish_analysis"]["move_evaluations"] or []:
            fen, best_san = ev.get("fen_before"), ev.get("best_move")
            if not fen or not best_san or best_san == ev.get("move"):
                continue
            try:
                board = chess.Board(fen)
                move = board.parse_san(best_san)
            except Exception:
                continue
            if not board.is_capture(move):
                continue
            why = _recommended_move_why(board, move)
            if not why:
                continue
            seen[why.split()[0]] += 1
            if not why.startswith("trades"):
                continue
            see = static_exchange_eval(board, move.to_square, board.turn)
            trades[bucket(see)] += 1
            if see is not None and see < -50:
                proof = deflection_proof(board, move)
                provable["board can prove a bigger loss" if proof
                         else "no proof available"] += 1
                if proof and len(examples) < 8:
                    examples.append(
                        (doc.get("game_id", "")[:8], best_san, see,
                         f"{proof[1]} on {proof[2]}", proof[0]))

    total_trades = sum(trades.values())
    print(f"recommended captures described over {args.games} games: {sum(seen.values())}")
    for k, v in seen.most_common():
        print(f"  {k:10} {v}")
    print(f"\n=== SEE on the target square for the {total_trades} called 'trades' ===")
    order = ["< -400", "< -300", "< -200", "< -100", "< -50", "< 0", "< 50",
             "< 80", ">= 80", "no SEE"]
    run = 0
    for k in order:
        n = trades.get(k, 0)
        if n:
            run += n
            print(f"  {k:>8}: {n:4}  cumulative {run:4} "
                  f"({run/max(total_trades,1)*100:5.1f}%)")
    bad = sum(v for k, v in trades.items()
              if k.startswith("<") and k != "< 80" and k != "< 50" and k != "< 0")
    print(f"\n  called a trade while SEE <= -50: {bad} "
          f"({bad/max(total_trades,1)*100:.1f}%)")
    print(f"  of those, {dict(provable)}")
    print("\n  examples (game, move, SEE, what falls after the recapture, cp):")
    for e in examples:
        print("   ", e)


if __name__ == "__main__":
    asyncio.run(main())
