"""
Intent Recognition Realism Test - Step 6 Validation

Tests the 3 exact archetypes specified by the user to validate that
the intent recognition and calibration produces human-like coaching.

Game Archetypes:
1. Early Queen Aggression (Qh5 type) - Equal, mild cp_loss, opening
2. Missed Tactic While Winning - User +300, miss mate/big tactic
3. Attack While Worse (Counterplay) - User -150, attacks king

What we evaluate (FEEL, not technical correctness):
- Does this sound like a human coach who watched the game?
- Does the coach avoid praising queen too early?
- Does it say "position demanded something forcing"?
- Does it say "looking for counterplay makes sense" when losing?
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.intent_recognition_service import recognize_intent, get_game_phase, IntentType
from analysis.intent_quality_calibrator import (
    calibrate_with_forcing_context, 
    build_full_intent_explanation,
    classify_pressure
)
import chess

def test_archetype_1_early_queen_aggression():
    """
    Game 1 - Early Queen Aggression (Qh5 type)
    
    Position: Equal (near 0 cp)
    Move: Qh5 (queen out early)
    CP Loss: 30-70 (mild)
    Phase: Opening
    
    Expected behavior:
    - Does NOT praise the queen move
    - Says "timing early" or "queen can become target"
    """
    print("\n" + "="*70)
    print("ARCHETYPE 1: Early Queen Aggression (Qh5 type)")
    print("="*70)
    
    # Position: After 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 - White plays Qh5 (premature)
    fen_before = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    move_uci = "d1h5"  # Qh5 - early queen
    best_move_uci = "d2d3"  # Better: d3 (development)
    eval_before = 35  # Slightly better for white (equal-ish)
    eval_after = 5  # Slight loss after premature queen move
    user_color = "white"
    cp_loss = 30
    
    # Get game phase
    board = chess.Board(fen_before)
    phase = get_game_phase(board)
    print(f"Phase: {phase}")
    
    # Get piece type
    move = chess.Move.from_uci(move_uci)
    piece = board.piece_at(move.from_square)
    piece_type = "queen" if piece and piece.piece_type == chess.QUEEN else None
    print(f"Piece type: {piece_type}")
    
    # Step 1: Intent recognition
    intent_result = recognize_intent(
        fen_before=fen_before,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        eval_before=eval_before,
        eval_after=eval_after,
        player_color_str=user_color
    )
    
    print(f"\nIntent Type: {intent_result.intent_type}")
    print(f"Intent Description: {intent_result.intent_description}")
    print(f"Intent Confidence: {intent_result.intent_confidence}")
    
    # Step 2: Calibrate with forcing context
    calibrated = calibrate_with_forcing_context(
        intent_type=intent_result.intent_type,
        cp_loss=cp_loss,
        eval_before=eval_before,
        user_color=user_color,
        phase=phase,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        board_fen=fen_before
    )
    
    print(f"\nCalibrated Quality: {calibrated.calibrated_quality}")
    print(f"Pressure: {calibrated.pressure}")
    print(f"Timing Score: {calibrated.timing_score}")
    print(f"Base CP Score: {calibrated.base_cp_score}")
    
    # Step 3: Build full explanation
    intent_sentence = build_full_intent_explanation(
        intent_description=intent_result.intent_description,
        calibrated_quality=calibrated.calibrated_quality,
        intent_type=intent_result.intent_type,
        pressure=calibrated.pressure,
        phase=phase,
        piece_type=piece_type
    )
    
    print(f"\n{'='*70}")
    print("FULL COACH EXPLANATION:")
    print(f"{'='*70}")
    print(intent_sentence)
    print(f"{'='*70}")
    
    # Validation checks
    print("\n[VALIDATION]")
    passed = True
    
    # Should NOT praise queen move
    praise_words = ["excellent", "very good", "good"]
    has_praise = any(word in intent_sentence.lower() for word in praise_words)
    if has_praise:
        print("  [WARN] Contains praise for early queen - should be cautious")
        passed = False
    else:
        print("  [PASS] No inappropriate praise for early queen")
    
    # Should mention timing or target
    timing_words = ["timing", "early", "target", "premature", "aggressive"]
    has_timing = any(word in intent_sentence.lower() for word in timing_words)
    if has_timing:
        print("  [PASS] Mentions timing/early/target concern")
    else:
        print("  [WARN] Should mention timing concern for queen in opening")
        passed = False
    
    return passed, intent_sentence


def test_archetype_2_missed_tactic_while_winning():
    """
    Game 2 - Missed Tactic While Winning
    
    Position: User +300 (winning)
    Move: Develops instead of winning tactic
    CP Loss: 150+ (missed forcing move)
    Phase: Middlegame
    
    Expected behavior:
    - Says "position demanded something forcing"
    - Avoids robotic language
    - Acknowledges the quiet development wasn't wrong in principle
    """
    print("\n" + "="*70)
    print("ARCHETYPE 2: Missed Tactic While Winning")
    print("="*70)
    
    # Position: White is +300, has a winning tactic (Nxf7!) but plays Bd3 instead
    # Simplified position where white has a knight fork opportunity
    fen_before = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/5N2/PPPP1PPP/RNB1K2R w KQkq - 0 5"
    move_uci = "c4d3"  # Bd3 - quiet development (misses tactic)
    best_move_uci = "c4f7"  # Bxf7+! - winning tactic (scholar's mate threat)
    eval_before = 300  # Winning for white
    eval_after = 50  # Still better but missed the win
    user_color = "white"
    cp_loss = 250
    
    # Get game phase
    board = chess.Board(fen_before)
    phase = get_game_phase(board)
    print(f"Phase: {phase}")
    
    # Get piece type
    move = chess.Move.from_uci(move_uci)
    piece = board.piece_at(move.from_square)
    piece_type = None
    if piece:
        piece_type = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king"
        }.get(piece.piece_type)
    print(f"Piece type: {piece_type}")
    
    # Step 1: Intent recognition
    intent_result = recognize_intent(
        fen_before=fen_before,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        eval_before=eval_before,
        eval_after=eval_after,
        player_color_str=user_color
    )
    
    print(f"\nIntent Type: {intent_result.intent_type}")
    print(f"Intent Description: {intent_result.intent_description}")
    
    # Step 2: Calibrate
    calibrated = calibrate_with_forcing_context(
        intent_type=intent_result.intent_type,
        cp_loss=cp_loss,
        eval_before=eval_before,
        user_color=user_color,
        phase=phase,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        board_fen=fen_before
    )
    
    print(f"\nCalibrated Quality: {calibrated.calibrated_quality}")
    print(f"Pressure: {calibrated.pressure}")
    print(f"Timing Score: {calibrated.timing_score}")
    
    # Step 3: Build full explanation
    intent_sentence = build_full_intent_explanation(
        intent_description=intent_result.intent_description,
        calibrated_quality=calibrated.calibrated_quality,
        intent_type=intent_result.intent_type,
        pressure=calibrated.pressure,
        phase=phase,
        piece_type=piece_type
    )
    
    print(f"\n{'='*70}")
    print("FULL COACH EXPLANATION:")
    print(f"{'='*70}")
    print(intent_sentence)
    print(f"{'='*70}")
    
    # Validation
    print("\n[VALIDATION]")
    passed = True
    
    # Should mention forcing move was needed
    forcing_words = ["forcing", "demanded", "action", "quiet", "wasn't the moment"]
    has_forcing = any(word in intent_sentence.lower() for word in forcing_words)
    if has_forcing:
        print("  [PASS] Mentions position demanded action/forcing moves")
    else:
        print("  [WARN] Should indicate forcing move was available")
        passed = False
    
    # Should not be robotic
    robotic_words = ["error detected", "suboptimal", "deviation from optimal"]
    is_robotic = any(word in intent_sentence.lower() for word in robotic_words)
    if is_robotic:
        print("  [FAIL] Language is too robotic")
        passed = False
    else:
        print("  [PASS] Language is human-like")
    
    return passed, intent_sentence


def test_archetype_3_attack_while_worse():
    """
    Game 3 - Attack While Worse (Counterplay)
    
    Position: User -150 (worse, not lost)
    Move: Attacks king aggressively
    CP Loss: 120-180 (not terrible)
    Phase: Middlegame
    
    Expected behavior:
    - Says "looking for counterplay makes sense"
    - Does NOT scold the player
    - Acknowledges the aggressive attempt given the position
    """
    print("\n" + "="*70)
    print("ARCHETYPE 3: Attack While Worse (Counterplay)")
    print("="*70)
    
    # Position: Black is worse (white +150), decides to attack
    # NOTE: eval_before is always from WHITE's perspective
    fen_before = "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2BPP3/2N2N2/PPP2PPP/R1BQK2R b KQkq - 0 6"
    move_uci = "c5f2"  # Bxf2+ - aggressive sacrifice attempt
    best_move_uci = "e8g8"  # O-O - safer castling
    eval_before = 150  # White is +150 (from white's POV), so black is WORSE
    eval_after = 10  # Position becomes more unclear
    user_color = "black"
    cp_loss = 140  # Lost some eval but created chaos
    
    # Get game phase
    board = chess.Board(fen_before)
    phase = get_game_phase(board)
    print(f"Phase: {phase}")
    
    # Get piece type
    move = chess.Move.from_uci(move_uci)
    piece = board.piece_at(move.from_square)
    piece_type = None
    if piece:
        piece_type = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king"
        }.get(piece.piece_type)
    print(f"Piece type: {piece_type}")
    
    # Step 1: Intent recognition
    intent_result = recognize_intent(
        fen_before=fen_before,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        eval_before=eval_before,
        eval_after=eval_after,
        player_color_str=user_color
    )
    
    print(f"\nIntent Type: {intent_result.intent_type}")
    print(f"Intent Description: {intent_result.intent_description}")
    
    # Step 2: Calibrate
    calibrated = calibrate_with_forcing_context(
        intent_type=intent_result.intent_type,
        cp_loss=cp_loss,
        eval_before=eval_before,
        user_color=user_color,
        phase=phase,
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        board_fen=fen_before
    )
    
    print(f"\nCalibrated Quality: {calibrated.calibrated_quality}")
    print(f"Pressure: {calibrated.pressure}")
    print(f"Timing Score: {calibrated.timing_score}")
    
    # Step 3: Build full explanation
    intent_sentence = build_full_intent_explanation(
        intent_description=intent_result.intent_description,
        calibrated_quality=calibrated.calibrated_quality,
        intent_type=intent_result.intent_type,
        pressure=calibrated.pressure,
        phase=phase,
        piece_type=piece_type
    )
    
    print(f"\n{'='*70}")
    print("FULL COACH EXPLANATION:")
    print(f"{'='*70}")
    print(intent_sentence)
    print(f"{'='*70}")
    
    # Validation
    print("\n[VALIDATION]")
    passed = True
    
    # Should acknowledge counterplay is reasonable when losing
    counterplay_words = ["counterplay", "worse", "makes sense", "understandable", "courage", "aggression"]
    has_counterplay = any(word in intent_sentence.lower() for word in counterplay_words)
    if has_counterplay:
        print("  [PASS] Acknowledges counterplay/aggression when worse")
    else:
        print("  [WARN] Should acknowledge counterplay makes sense when worse")
        passed = False
    
    # Should NOT scold
    scold_words = ["wrong", "bad move", "mistake", "error", "you should never"]
    is_scolding = any(word in intent_sentence.lower() for word in scold_words)
    if is_scolding:
        print("  [FAIL] Should not scold for counterplay attempt when worse")
        passed = False
    else:
        print("  [PASS] Does not scold the player")
    
    return passed, intent_sentence


def main():
    """Run all 3 archetype tests"""
    print("\n" + "="*70)
    print("STEP 6: INTENT RECOGNITION REALISM TEST")
    print("3-Game Archetype Validation")
    print("="*70)
    
    results = []
    explanations = []
    
    # Test each archetype
    passed1, exp1 = test_archetype_1_early_queen_aggression()
    results.append(("Archetype 1: Early Queen", passed1))
    explanations.append(exp1)
    
    passed2, exp2 = test_archetype_2_missed_tactic_while_winning()
    results.append(("Archetype 2: Missed Tactic", passed2))
    explanations.append(exp2)
    
    passed3, exp3 = test_archetype_3_attack_while_worse()
    results.append(("Archetype 3: Counterplay", passed3))
    explanations.append(exp3)
    
    # Summary
    print("\n" + "="*70)
    print("REALISM TEST SUMMARY")
    print("="*70)
    
    total_passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[NEEDS TUNING]"
        print(f"  {status} {name}")
    
    print(f"\nOverall: {total_passed}/{total} archetypes passed")
    
    print("\n" + "="*70)
    print("FULL EXPLANATIONS FOR USER REVIEW")
    print("="*70)
    
    for i, (name, _) in enumerate(results):
        print(f"\n{name}:")
        print(f"  \"{explanations[i]}\"")
    
    print("\n" + "="*70)
    print("USER EVALUATION PROMPT:")
    print("="*70)
    print("""
Read each explanation above and ask:
  - Does this sound like a human coach who watched the game?
  - NOT: Does this sound technically correct?

If explanation feels:
  - too neutral
  - too safe
  - too templated
Then Step 6 still needs tuning.
""")
    
    return total_passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
