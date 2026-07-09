#!/usr/bin/env python3
"""
Test verified captions on real moves.

Shows which detections pass Stockfish verification gates.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_facts_verified import extract_facts_verified


async def test_position(name, fen, move_san, eval_before, eval_after):
    """Test a single position"""
    print(f"Test: {name}")
    print(f"Eval: {eval_before} -> {eval_after} (cp_loss={eval_before - eval_after})")
    print()

    facts = await extract_facts_verified(
        fen_before=fen,
        played_san=move_san,
        best_move_san=None,
        eval_before_cp=eval_before,
        eval_after_cp=eval_after,
    )

    verified = facts.get("verified", False)
    reason = facts.get("verification_reason", "")
    details = facts.get("verification_details", {})

    print(f"Verified: {verified}")
    if reason:
        print(f"Reason: {reason}")
    print()

    if details:
        print("Detection verification:")
        for detection_type, is_ok in details.items():
            status = "[PASS]" if is_ok else "[FAIL]"
            print(f"  {status} {detection_type}")
        print()

    return verified


async def main():
    print("=" * 100)
    print("TESTING VERIFIED CAPTIONS")
    print("=" * 100)
    print()

    tests = [
        {
            "name": "Inaccuracy - e5 (20cp loss - BLOCKED by Gate 1)",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "move": "e5",
            "eval_before": 0,
            "eval_after": -20,
        },
        {
            "name": "Mistake - d5 (150cp loss - PASSES Gate 1)",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "move": "d5",
            "eval_before": 0,
            "eval_after": -150,
        },
        {
            "name": "Blunder - f6 (300cp loss - PASSES Gate 1)",
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "move": "f6",
            "eval_before": 0,
            "eval_after": -300,
        },
    ]

    verified_count = 0
    for test in tests:
        is_verified = await test_position(
            test["name"],
            test["fen"],
            test["move"],
            test["eval_before"],
            test["eval_after"],
        )
        if is_verified:
            verified_count += 1

    print("=" * 100)
    print(f"RESULTS: {verified_count}/{len(tests)} captions verified by Stockfish")
    print("=" * 100)
    print()
    print("GATE SUMMARY:")
    print("  Gate 1 (cp_loss >= 100): Blocks inaccuracies")
    print("  Gate 2 (fact-eval consistency): Blocks false positives")
    print()
    print("Result: Only high-confidence captions pass both gates")
    print()


if __name__ == "__main__":
    asyncio.run(main())
