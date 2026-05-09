"""Step-through trace — run detector on the Qxd5 game and print every check."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import chess

from services.visual_shapes import (
    detect_queen_too_early,
    _count_developed_minors,
    _queen_chased_in_future,
    SHAPE_QUEEN_TOO_EARLY,
)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def trace():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Pull the specific game with the known Qxd5
    ga = await db.game_analyses.find_one(
        {"game_id": "game_85bd0169aa4f"},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1},
    )
    client.close()

    if not ga:
        print("Game not found.")
        return

    moves = (ga.get("stockfish_analysis") or {}).get("move_evaluations") or []
    print(f"Total moves in game: {len(moves)}")

    # Print first 8 moves
    print("\n=== First 8 moves of the game ===")
    for i, m in enumerate(moves[:8]):
        print(f"  idx={i} mn={m.get('move_number')} {m.get('move'):>6}  uci={m.get('move_uci')}  fen_before={m.get('fen_before','')[:50]}")

    # Walk every move and try the detector with verbose output
    print("\n=== Per-move detector trace (first 12 moves) ===")
    for idx, m in enumerate(moves[:12]):
        fen_before = m.get("fen_before", "")
        move_uci = m.get("move_uci", "")
        move_number = m.get("move_number", 0) or 0
        future = moves[idx + 1: idx + 1 + 6]

        # Mirror detector logic
        if not fen_before or not move_uci or len(move_uci) < 4:
            print(f"  idx={idx} SKIP: missing fen/uci")
            continue
        if move_number <= 0 or move_number > 10:
            print(f"  idx={idx} SKIP: move_number {move_number} out of opening window")
            continue

        try:
            board = chess.Board(fen_before)
            mv = chess.Move.from_uci(move_uci)
            if mv not in board.legal_moves:
                print(f"  idx={idx} SKIP: move not legal ({move_uci} on {fen_before[:40]})")
                continue
            moving = board.piece_at(mv.from_square)
            if moving is None:
                print(f"  idx={idx} SKIP: no piece at from_square")
                continue
            if moving.piece_type != chess.QUEEN:
                # Not a queen move — fine, skip silently to keep output clean
                continue
            user_color = moving.color
            color_name = "WHITE" if user_color else "BLACK"
        except Exception as e:
            print(f"  idx={idx} EXCEPTION pre-detector: {e}")
            continue

        # Queen move found
        print(f"\n  --- idx={idx} mn={move_number} {m.get('move')} ({color_name} queen move) ---")

        try:
            board2 = chess.Board(fen_before)
            board2.push(mv)
            developed = _count_developed_minors(board2, user_color)
            print(f"    minors developed after push: {developed}")
        except Exception as e:
            print(f"    EXCEPTION counting minors: {e}")
            continue

        if developed >= 2:
            print(f"    DETECTOR REJECT: 2+ minors already developed")
            continue

        # Verifier
        try:
            chased = _queen_chased_in_future(fen_before, move_uci, future, user_color, max_plies=4)
            print(f"    verifier (next 4 plies): chased={chased}")
            future_san = [(fm.get('move'), fm.get('move_uci')) for fm in future[:4]]
            print(f"    next 4 plies were: {future_san}")
        except Exception as e:
            print(f"    EXCEPTION in verifier: {e}")
            continue

        # Final result
        result = detect_queen_too_early(fen_before, move_uci, move_number, future)
        print(f"    DETECTOR RESULT: {'FIRED' if result else 'suppressed'}")
        if result:
            print(f"      shape: {result['type']} on {result['square']}")
            print(f"      coach: {result['coach_line']}")


if __name__ == "__main__":
    asyncio.run(trace())
