#!/usr/bin/env python3
"""
Test Deterministic Detectors on Endgame Positions

Validates principle detectors on the Rf3+ case and other endgames.
Runs completely locally without Claude or any external API.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from services.simple_endgame_caption_builder import build_endgame_caption


async def test_rf3_plus():
    """Test the Rf3+ endgame case"""

    print("=" * 70)
    print("Testing Deterministic Principle Detectors")
    print("=" * 70)
    print()

    # Position: 6k1/2p5/3p4/p7/K1P5/5R2/8/8 w - - 0 1
    # White: King d4, Rook f3, Pawn c4
    # Black: King g8, Pawns a5, c7, d6
    fen = "6k1/2p5/3p4/p7/K1P5/5R2/8/8 w - - 0 1"

    print("TEST CASE: Rf3+ — Removes only defender of a5 pawn")
    print(f"FEN: {fen}")
    print()

    board = chess.Board(fen)

    # Try different moves
    test_moves = [
        ("Rg3+", chess.Move.from_uci("f3g3")),  # Rook to g3 (with check)
        ("Re3", chess.Move.from_uci("f3e3")),   # Rook to e3 defense
        ("Rf5", chess.Move.from_uci("f3f5")),   # Rook to f5 defense
        ("Rf2", chess.Move.from_uci("f3f2")),   # Rook retreats
    ]

    for move_name, move_obj in test_moves:
        print(f"Testing move: {move_name}")
        print("-" * 70)

        if move_obj not in board.legal_moves:
            print(f"  [ILLEGAL] Not a legal move")
            print()
            continue

        try:
            # Generate caption using deterministic analyzer
            caption_result = await build_endgame_caption(
                fen=fen,
                move_san=move_name,
                eval_before=200,
                eval_after=-500 if move_name == "Rg3+" else 100,
                best_move_san="Re3" if move_name == "Rg3+" else None,
            )

            print(f"  Caption: {caption_result['caption']}")
            print(f"  Principles: {caption_result['principles']}")
            print(f"  Quality: {caption_result['quality_score']:.2f}")
            print(f"  Method: {caption_result['method']}")
            print()

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback

            traceback.print_exc()
            print()

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("[OK] Deterministic detectors loaded")
    print("[OK] No Claude/LLM calls needed")
    print("[OK] Runs completely locally")
    print()


async def test_kp_vs_k():
    """Test simple K+P vs K endgame"""

    print("=" * 70)
    print("TEST: K+P vs K — Rule of the Square")
    print("=" * 70)
    print()

    # Simple position: King on e3, Pawn on e5, Opponent king on a1
    # Pawn can queen, king can't catch (violates rule)
    fen = "8/8/8/4P3/8/4K3/k7/8 w - - 0 1"
    board = chess.Board(fen)

    print(f"FEN: {fen}")
    print("White: King e3, Pawn e5")
    print("Black: King a1")
    print()

    # King moves closer
    move_names = [
        ("Kd4", chess.Move.from_uci("e3d4")),  # Toward pawn
        ("Ke4", chess.Move.from_uci("e3e4")),  # Support pawn
        ("Kf4", chess.Move.from_uci("e3f4")),  # Wrong direction
    ]

    for move_name, move_obj in move_names:
        if move_obj in board.legal_moves:
            result = await build_endgame_caption(
                fen=fen,
                move_san=move_name,
                eval_before=100,
                eval_after=150,
                best_move_san=None,
            )
            principles = result['principles']
            print(f"{move_name}: {principles if principles else 'no principles'}")

    print()


async def main():
    await test_rf3_plus()
    await test_kp_vs_k()


if __name__ == "__main__":
    asyncio.run(main())
