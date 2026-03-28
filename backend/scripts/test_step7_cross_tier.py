"""
Step 7 Cross-Tier Realism Test

Tests the same coaching moment across different maturity tiers to verify:
1. Same truth, different delivery depth
2. Sentence limits are enforced
3. No repetition problems
4. Users don't feel "talked down to" at higher tiers

Acceptance Criteria:
- Novice gets full explanation + encouragement
- Disciplined gets crisp, direct feedback
- Advanced gets minimal coach shorthand
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach_narrative_engine import (
    generate_coaching_narrative,
    NarrativeComponents,
    ToneRenderer,
)
from coach_state.teaching_style_service import (
    get_style_directive,
    maturity_to_tier,
)


def create_test_move():
    """Create a standard test move - missed tactic scenario."""
    return {
        "move_number": 15,
        "move_uci": "c4d3",
        "move_san": "Bd3",
        "cp_loss": 250,
        "score_before": 300,
        "score_after": 50,
        "is_blunder": False,
        "is_mistake": True,
        "engine_best_move": "c4f7",
        "cognitive_gap": "FORCING_BLIND",
        "gap_confidence": 0.85,
        "crs_score": 180,
        # Step 6 intent fields
        "intent_type": "POSITIONAL_MANEUVER",
        "intent_quality": "premature",
        "intent_sentence": "Adjusting the position is fine, but here the position demanded something forcing.",
        "intent_pressure": "winning",
    }


def create_test_context():
    """Create test position context."""
    return {
        "state_before": "winning",
        "state_after": "equal",
        "result_flipped": False,
        "advantage_lost": True,
        "momentum_shift": True,
        "eval_before": 300,
        "eval_after": 50,
    }


def test_tier_output(tier: str, move: dict, context: dict):
    """Generate output for a specific tier and analyze it."""
    result = generate_coaching_narrative(
        selected_move=move,
        selection_reason="tactical_error",
        position_context=context,
        maturity_level=tier,
        active_theme="FORCING_BLIND",
        game_id="test_game_123",
        lesson_key="FORCING_BLIND",
        recent_accuracies=[65.0, 68.0, 70.0, 72.0, 75.0],  # Improving
        lesson_repeated=False,
    )
    
    text = result["assembled_text"]
    sentence_count = len([s for s in text.split(". ") if s.strip()])
    
    return {
        "tier": tier,
        "text": text,
        "sentence_count": sentence_count,
        "strategy": result["narrative_strategy"],
        "style_tier": result.get("style_directive_tier", tier),
    }


def print_tier_comparison(results: list):
    """Print formatted comparison of tier outputs."""
    print("\n" + "="*80)
    print("STEP 7: CROSS-TIER REALISM TEST")
    print("Same Coaching Moment → Different Delivery")
    print("="*80)
    
    for r in results:
        print(f"\n{'─'*80}")
        print(f"TIER: {r['tier']} (StyleDirective: {r['style_tier']})")
        print(f"Strategy: {r['strategy']}")
        print(f"Sentences: ~{r['sentence_count']}")
        print(f"{'─'*80}")
        print(f"\n\"{r['text']}\"\n")


def validate_results(results: list) -> bool:
    """Validate that outputs meet Step 7 acceptance criteria."""
    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)
    
    all_passed = True
    
    novice = next((r for r in results if r['tier'] == 'Novice'), None)
    developing = next((r for r in results if r['tier'] == 'Developing'), None)
    disciplined = next((r for r in results if r['tier'] == 'Disciplined'), None)
    advanced = next((r for r in results if r['tier'] == 'Advanced'), None)
    
    # 1. Sentence count decreases with tier
    if novice and advanced:
        if novice['sentence_count'] > advanced['sentence_count']:
            print("[PASS] Novice has more sentences than Advanced")
        else:
            print("[FAIL] Novice should have more sentences than Advanced")
            all_passed = False
    
    # 2. Advanced should NOT have intent phrase "You tried..."
    if advanced:
        if "You tried" not in advanced['text'] and "You aimed" not in advanced['text']:
            print("[PASS] Advanced skips intent phrasing")
        else:
            print("[WARN] Advanced may have unnecessary intent phrasing")
    
    # 3. Novice should have encouragement
    if novice:
        encouragement_words = ["habit", "process", "practice", "patient", "building"]
        has_encouragement = any(word in novice['text'].lower() for word in encouragement_words)
        if has_encouragement:
            print("[PASS] Novice has encouragement")
        else:
            print("[WARN] Novice may be missing encouragement")
    
    # 4. Disciplined should be short and direct
    if disciplined:
        if disciplined['sentence_count'] <= 4:
            print("[PASS] Disciplined is concise")
        else:
            print("[FAIL] Disciplined should be 3-4 sentences max")
            all_passed = False
    
    # 5. All should contain the core truth (forcing move missed)
    truth_indicators = ["forcing", "demanded", "position"]
    for r in results:
        has_truth = any(word in r['text'].lower() for word in truth_indicators)
        if has_truth:
            print(f"[PASS] {r['tier']} contains core truth")
        else:
            print(f"[WARN] {r['tier']} may be missing core truth")
    
    return all_passed


def main():
    """Run cross-tier realism test."""
    move = create_test_move()
    context = create_test_context()
    
    tiers = ["Novice", "Developing", "Disciplined", "Advanced"]
    results = []
    
    for tier in tiers:
        result = test_tier_output(tier, move, context)
        results.append(result)
    
    print_tier_comparison(results)
    
    passed = validate_results(results)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if passed:
        print("\n[PASS] Step 7 Cross-Tier Test: All criteria met")
        print("\nThe coach now adapts delivery based on user maturity.")
        print("Same truth → Different depth + firmness")
    else:
        print("\n[NEEDS TUNING] Some criteria need adjustment")
    
    print("\n" + "="*80)
    print("USER EVALUATION PROMPT")
    print("="*80)
    print("""
Read each tier's output and ask:

For Novice:
  - Does it feel supportive without being condescending?
  - Is there enough context for a beginner?

For Disciplined:
  - Does it feel direct without being harsh?
  - Is it actionable?

For Advanced:
  - Does it feel like coach shorthand?
  - Would an experienced player find it efficient?

If any tier feels wrong, report which one and why.
""")
    
    return passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
