#!/usr/bin/env python3
"""
Test the CORRECT Promotion Threat Detector on valid positions.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from services.endgame_detectors.promotion_threat_correct import (
    identify_promotion_threats,
    detect_promotion_threat_move,
    build_promotion_threat_caption,
)


async def test_case(name, fen, move_san, expected_detection, expected_principle):
    """Test a single case"""
    print(f"\nTest: {name}")
    print(f"FEN: {fen}")
    print(f"Move: {move_san}")

    board = chess.Board(fen)

    # Parse move
    move = None
    for m in board.legal_moves:
        if board.san(m) == move_san:
            move = m
            break

    if not move:
        print(f"  [ERROR] Move {move_san} is illegal")
        print(f"  Legal: {[board.san(m) for m in list(board.legal_moves)[:10]]}")
        return False

    # Identify threats in current position
    user_color = board.turn
    threats = identify_promotion_threats(board, user_color)

    print(f"  Threats found: {len(threats)}")
    for threat in threats:
        pawn_sq = chess.square_name(threat["pawn_sq"])
        promo_sq = chess.square_name(threat["promotion_sq"])
        moves_left = threat["moves_to_promotion"]
        defended = threat["is_defended_now"]
        print(f"    Pawn {pawn_sq} -> {promo_sq} in {moves_left} moves, defended={defended}")

    # Detect impact of move
    detection = detect_promotion_threat_move(board, move, user_color)
    print(f"  Move impact: {detection}")
    print(f"  Expected: {expected_detection}")

    # Build caption
    caption = build_promotion_threat_caption(
        board=board,
        move=move,
        move_san=move_san,
        user_color=user_color,
        detection=detection,
        eval_before=100,
        eval_after=0,
    )

    if caption:
        print(f"  Caption: {caption}")
    else:
        print(f"  Caption: (none)")

    # Verify
    if detection == expected_detection:
        print(f"  [PASS]")
        return True
    else:
        print(f"  [FAIL] Expected {expected_detection}, got {detection}")
        return False


async def main():
    print("=" * 80)
    print("Test Promotion Threat Detector")
    print("=" * 80)

    tests = [
        {
            "name": "K+R vs K+P - Rook leaves a4 pawn undefended",
            "fen": "8/8/8/8/pk6/8/1R6/8 w - - 0 1",  # White Rb2, Black Kd4, pa4
            "move": "Ra2",  # Rook moves away from defending a4
            "expected_detection": "allows",
            "expected_principle": "allows_promotion",
        },
        {
            "name": "K+R vs K+P - Rook defends against pawn",
            "fen": "8/8/8/8/pk6/8/1R6/8 w - - 0 1",
            "move": "Ra2",  # Rook controls a-file where pawn wants to promote
            "expected_detection": "allows",
            "expected_principle": "allows_promotion",
        },
        {
            "name": "K+R vs K+P - Rook protects promotion square",
            "fen": "8/pk6/8/8/8/8/1R6/8 w - - 0 1",  # pa5 close to promoting
            "move": "Ra2",  # Rook defends a8 (promotion square)
            "expected_detection": "defends",
            "expected_principle": "promotion_defense",
        },
        {
            "name": "No promotion threat",
            "fen": "8/8/8/8/8/1k6/1R6/8 w - - 0 1",  # No pawns
            "move": "Ra2",
            "expected_detection": None,
            "expected_principle": None,
        },
    ]

    passed = 0
    for test in tests:
        if await test_case(
            test["name"],
            test["fen"],
            test["move"],
            test["expected_detection"],
            test["expected_principle"],
        ):
            passed += 1

    print()
    print("=" * 80)
    print(f"Results: {passed}/{len(tests)} passed")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
