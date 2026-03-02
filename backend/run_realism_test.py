"""
10-Game Human Realism Test Script

Processes games sequentially through the coaching narrative engine
and outputs coach summaries for evaluation.

Uses synchronous operations with pymongo.
"""

import os
import sys

# Set environment
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "test_database"

sys.path.insert(0, '/app/backend')

from pymongo import MongoClient
from coach_state_service import CoachState, NarrativeComponents
from coach_moment_selector import select_teaching_moment
from analysis_interpreter import interpret_game_analysis
from coach_narrative_engine import generate_coaching_narrative

client = MongoClient(os.environ.get("MONGO_URL"))
db = client[os.environ.get("DB_NAME")]

USER_ID = "user_bdd07038f9c0"

# Get 10 most recent analyzed games
games = list(db.games.find(
    {"user_id": USER_ID, "is_analyzed": True}
).sort("played_at", -1).limit(10))


def process_game(game_num: int, game: dict, coach_state: CoachState):
    """Process a single game and display coach summary"""
    game_id = game.get("game_id")
    result = game.get("result")
    user_color = game.get("user_color")
    
    # Get analysis
    analysis = db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        print(f"  No analysis found")
        return None, coach_state
    
    sf = analysis.get("stockfish_analysis", {})
    accuracy = sf.get("accuracy", 0)
    blunders = sf.get("blunders", 0)
    moves = sf.get("move_evaluations", [])
    
    user_won = (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1")
    outcome = "WIN" if user_won else "LOSS"
    
    print(f"\n{'='*70}")
    print(f"GAME {game_num}: {outcome} | Accuracy: {accuracy:.1f}% | Blunders: {blunders}")
    print(f"{'='*70}")
    
    if coach_state:
        print(f"\nCoach Context:")
        print(f"  Theme: {coach_state.active_theme.value}")
        print(f"  Maturity: {coach_state.behavioral_maturity_level}")
        print(f"  Good game streak: {coach_state.good_game_streak}")
    
    # Run interpretation
    print(f"\nProcessing through narrative engine...")
    
    try:
        # Interpret moves
        enriched_moves, interp_summary = interpret_game_analysis(moves, user_color)
        
        # Select teaching moment
        selection = select_teaching_moment(enriched_moves, user_color, result)
        
        selected_move = {}
        selection_reason = "no_critical_moves"
        max_crs = 0
        
        if selection:
            selected_move = selection.get("selected_move", {})
            selection_reason = selection.get("selection_reason", "tactical_error")
            max_crs = selection.get("selection_score", 0)
            
            print(f"\n  Selected Move: #{selected_move.get('move_number', 'N/A')}")
            print(f"  Selection Reason: {selection_reason}")
            print(f"  CRS Score: {max_crs:.1f}")
            print(f"  Cognitive Gap: {selected_move.get('cognitive_gap', 'None')}")
        else:
            print(f"\n  No critical moves - POSITIVE COACHING path")
        
        # Get position context
        position_ctx = selected_move.get("position_context", {}) if selected_move else {}
        
        # Generate narrative using the engine
        narrative_result = generate_coaching_narrative(
            selected_move=selected_move,
            selection_reason=selection_reason,
            position_context=position_ctx,
            maturity_level=coach_state.behavioral_maturity_level if coach_state else "Developing",
            active_theme=coach_state.active_theme.value if coach_state else None,
            recent_sentences=coach_state.recent_coach_sentences if coach_state else [],
            max_crs_score=max_crs,
            good_game_streak=coach_state.good_game_streak if coach_state else 0
        )
        
        # Display coach output
        print(f"\n{'~'*70}")
        print("COACH SAYS:")
        print(f"{'~'*70}")
        
        assembled = narrative_result.get("assembled_text", "")
        strategy = narrative_result.get("narrative_strategy", "")
        tone = narrative_result.get("tone_profile_used", "")
        confidence = narrative_result.get("explanation_confidence", 0)
        
        print(f"\n{assembled}")
        
        components = narrative_result.get("narrative_components", {})
        print(f"\n[Structured Components]")
        print(f"  Intent: {components.get('intent_mirror_line', '')[:60]}...")
        print(f"  Break: {components.get('thinking_break_line', '')[:60]}...")
        print(f"  Teaching: {components.get('teaching_line', '')[:60]}...")
        print(f"  Rule: {components.get('rule_line', '')[:60]}...")
        
        print(f"\nNarrative Strategy: {strategy}")
        print(f"Tone Profile: {tone}")
        print(f"Explanation Confidence: {confidence:.2f}")
        
        # Update coach state for next game (simulate evolution)
        if coach_state:
            if strategy == "positive_coaching":
                coach_state.good_game_streak += 1
            else:
                coach_state.good_game_streak = 0
            
            # Add to recent sentences for anti-repetition
            if assembled:
                coach_state.recent_coach_sentences.append(assembled[:50])
                coach_state.recent_coach_sentences = coach_state.recent_coach_sentences[-10:]
        
        return {
            "strategy": strategy,
            "tone": tone,
            "confidence": confidence,
            "assembled": assembled
        }, coach_state
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None, coach_state


def run_test():
    """Run the 10-game realism test"""
    print("\n" + "="*70)
    print("10-GAME HUMAN REALISM TEST")
    print("="*70)
    print(f"\nUser: {USER_ID}")
    print(f"Games to process: {len(games)}")
    
    # Get initial coach state
    coach_state_doc = db.coach_states.find_one({"user_id": USER_ID})
    coach_state = CoachState.from_dict(coach_state_doc) if coach_state_doc else None
    
    results = []
    
    for i, game in enumerate(games, 1):
        result, coach_state = process_game(i, game, coach_state)
        if result:
            results.append(result)
        
        print(f"\n" + "-"*70)
    
    print("\n" + "="*70)
    print("TEST COMPLETE - Summary")
    print("="*70)
    
    strategies = {}
    for r in results:
        if r and r.get("strategy"):
            s = r["strategy"]
            strategies[s] = strategies.get(s, 0) + 1
    
    print("\nNarrative Strategy Distribution:")
    total = len(results)
    for s, count in sorted(strategies.items(), key=lambda x: -x[1]):
        print(f"  {s}: {count} ({count/total*100:.0f}%)")
    
    print("\n" + "="*70)
    print("EVALUATION LOG")
    print("="*70)
    print("""
| Game | Strategy           | Felt Understood | Repetition? | Helpful? |
|------|--------------------| --------------- |-------------|----------|
|   1  |                    |     /5          |             |          |
|   2  |                    |     /5          |             |          |
|   3  |                    |     /5          |             |          |
|   4  |                    |     /5          |             |          |
|   5  |                    |     /5          |             |          |
|   6  |                    |     /5          |             |          |
|   7  |                    |     /5          |             |          |
|   8  |                    |     /5          |             |          |
|   9  |                    |     /5          |             |          |
|  10  |                    |     /5          |             |          |
""")


if __name__ == "__main__":
    run_test()
