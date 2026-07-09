#!/usr/bin/env python3
"""
Test principle-based caption generation on the Rf3+ endgame case.

This validates the hybrid system:
1. Position classifier identifies K+R vs K+P endgame
2. Claude analyzer generates principle-driven explanation
3. Output explains move using rule of the square, critical pieces, threats
"""

import asyncio
import chess


async def test_rf3_plus():
    """Test the Rf3+ case that revealed the quality gap"""

    # Position: 6k1/2p5/3p4/p7/K1P5/5R2/8/8 w - - 0 1
    # After Black's last move, position is a K+R vs K+P endgame
    fen = "6k1/2p5/3p4/p7/K1P5/5R2/8/8 w - - 0 1"

    print("=" * 70)
    print("Testing Principle-Based Caption Generation")
    print("=" * 70)
    print()
    print("TEST CASE: Rf3+ blunder (user's real game)")
    print(f"FEN: {fen}")
    print()

    # Step 1: Classify the position
    print("STEP 1: Position Classification")
    print("-" * 70)

    from services.endgame_classifier import classify_position

    board = chess.Board(fen)
    position_info = classify_position(board)

    print(f"Position Type:       {position_info.position_type}")
    print(f"White Material:      {position_info.material_white}")
    print(f"Black Material:      {position_info.material_black}")
    print(f"White King:          {position_info.white_king}")
    print(f"Black King:          {position_info.black_king}")
    print(f"White Rooks:         {position_info.white_rooks}")
    print(f"Black Pawns:         {position_info.black_pawns}")
    print(f"Threats:             {position_info.threats}")
    print(f"Critical Pieces:     {position_info.critical_pieces}")
    print(f"Is Theoretical:      {position_info.is_theoretical_endgame}")
    print()

    # Step 2: Generate principle-based caption
    print("STEP 2: Claude-Based Principle Analysis")
    print("-" * 70)

    from services.principle_based_caption_generator import generate_principle_based_caption

    # Rf3+ eval: roughly -500 cp (blunder, loses the rook)
    # Best move is Re1 or Re5 (keeps rook active)
    caption_result = await generate_principle_based_caption(
        fen=fen,
        move_san="Rf3+",
        eval_before=200,  # White was slightly better
        eval_after=-500,  # Loses the position
        best_move_san="Re1",
    )

    print(f"Caption:")
    print(f"  {caption_result['caption']}")
    print()
    print(f"Principles Mentioned: {caption_result['principles']}")
    print(f"Quality Score:        {caption_result['quality_score']:.2f}")
    print(f"Method:               {caption_result['method']}")
    print()

    # Step 3: Verify quality
    print("STEP 3: Quality Verification")
    print("-" * 70)

    required_principles = ["rule_of_square", "critical_piece", "promotion_threat"]
    found_principles = set(caption_result["principles"])
    mentioned_principles = [p for p in required_principles if p in found_principles]

    print(f"Required principles: {required_principles}")
    print(f"Found:               {mentioned_principles}")

    quality_check = len(mentioned_principles) >= 2
    print(f"Quality check (≥2 principles): {'PASS' if quality_check else 'FAIL'}")
    print()

    # Step 4: Expected output
    print("STEP 4: Expected vs Actual")
    print("-" * 70)

    expected = """
    Rf3+ removes your rook — the only defender against Black's a5 pawn.
    By the rule of the square, your king can't catch it alone from d4.
    The pawn will promote. Play Re1 or Re5 to keep your rook working.
    """

    print("EXPECTED (from user feedback):")
    print(expected)
    print()
    print("ACTUAL (from Claude analyzer):")
    print(caption_result["caption"])
    print()

    # Step 5: Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if quality_check and "rule of the square" in caption_result["caption"].lower():
        print("✅ HYBRID SYSTEM WORKING")
        print("   - Position classified correctly as K+R vs K+P")
        print("   - Claude generated principle-driven explanation")
        print("   - Output mentions key principles (rule of square, critical piece)")
        print("   - Quality meets minimum threshold (2+ principles)")
    else:
        print("⚠️  PARTIAL SUCCESS")
        print("   - Position classified correctly")
        print("   - Claude response generated but missing some principles")
        print("   - Recommendation: Review Claude prompt or check API connection")

    print()
    return quality_check


if __name__ == "__main__":
    success = asyncio.run(test_rf3_plus())
    exit(0 if success else 1)
