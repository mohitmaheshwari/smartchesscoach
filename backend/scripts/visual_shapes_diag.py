"""Diagnostic — inspect real game data to find why queen_too_early doesn't fire."""
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

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def diagnose():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Pull 5 games with move_evaluations, inspect first few moves
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).limit(5)

    games_inspected = 0
    queen_move_examples = []
    field_keys_seen = set()
    move_number_distribution = {}

    async for ga in cursor:
        games_inspected += 1
        moves = (ga.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if games_inspected == 1:
            print(f"\n=== Sample move_evaluations[0] from game {ga.get('game_id')} ===")
            if moves:
                m0 = moves[0]
                print(f"Keys present: {sorted(m0.keys())}")
                for k in sorted(m0.keys()):
                    val = m0[k]
                    val_str = str(val)[:80]
                    print(f"  {k}: {val_str}")

        # Track field shapes across the first 10 moves
        for m in moves[:10]:
            field_keys_seen.update(m.keys())
            mn = m.get("move_number", "MISSING")
            move_number_distribution[mn] = move_number_distribution.get(mn, 0) + 1

        # Find queen moves in opening (any move where queen moves from starting square)
        for idx, m in enumerate(moves[:20]):
            uci = m.get("move_uci", "") or m.get("uci", "") or ""
            san = m.get("move_san", "") or m.get("move", "")
            fen_before = m.get("fen_before", "")
            if not fen_before or not uci:
                continue
            try:
                board = chess.Board(fen_before)
                if len(uci) < 4:
                    continue
                mv = chess.Move.from_uci(uci)
                piece = board.piece_at(mv.from_square)
                if piece and piece.piece_type == chess.QUEEN:
                    if len(queen_move_examples) < 8:
                        queen_move_examples.append({
                            "game": ga.get("game_id"),
                            "idx": idx,
                            "move_number": m.get("move_number"),
                            "san": san,
                            "uci": uci,
                            "fen_before": fen_before,
                        })
            except Exception as e:
                pass

    client.close()

    print(f"\n=== {games_inspected} games inspected ===")
    print(f"\nField keys seen across move_evaluations: {sorted(field_keys_seen)}")
    print(f"\nmove_number values seen (first 10 moves of each game):")
    for k in sorted(move_number_distribution.keys(), key=lambda x: (str(type(x)), x)):
        print(f"  {k!r}: {move_number_distribution[k]} occurrences")

    print(f"\n=== Queen-move examples found in opening (first 20 plies of each game) ===")
    if not queen_move_examples:
        print("  (NONE — no queen moves detected in any of the inspected games)")
    for q in queen_move_examples:
        print(f"  game={q['game']} idx={q['idx']} move_number={q['move_number']!r}")
        print(f"    san={q['san']!r}  uci={q['uci']!r}")
        print(f"    fen_before={q['fen_before'][:60]}")


if __name__ == "__main__":
    asyncio.run(diagnose())
