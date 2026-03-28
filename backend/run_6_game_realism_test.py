"""
6-Game Memory Realism Test

This is NOT a QA test. This is psychological believability validation.

Tests memory continuity across a sequence designed to force memory + narrative interaction:
  Game 1: Clear mistake
  Game 2: Similar mistake  
  Game 3: Slight improvement
  Game 4: Clean/stable game
  Game 5: Regression
  Game 6: Recovery

Evaluation criteria (1-5 each):
  1. Felt Understood - Does coach sound like it watched THIS game?
  2. Memory Naturalness - Does reference to past feel organic?
  3. Emotional Timing - Is praise/correction emotionally correct?
  4. Non-Repetition - Does explanation structure feel fresh?
  5. Coaching Authority - Would I trust this coach after 20 games?

PASS CONDITIONS:
  - Average >= 4.0/5
  - No category < 3

NOTE: Only read final coach text. Do not read metadata.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient

# Import coaching components
from coach_state_service import CoachState, CoachTheme, GameCoachSummary
from coach_moment_selector import select_teaching_moment
from analysis_interpreter import interpret_game_analysis
from coach_narrative_engine import generate_coaching_narrative
from coach_memory_service import get_memory_service
import lesson_resolver


# Sample games with precomputed analysis for reliable testing
# This bypasses Stockfish timing issues while testing memory continuity
TEST_GAMES = [
    # Game 1: Clear mistake (threat blindness) - BLUNDER
    {
        "description": "Clear tactical oversight - missed Rxf2 threat",
        "expected_type": "clear_mistake",
        "result": "0-1",
        "user_color": "white",
        "precomputed_analysis": {
            "accuracy": 52.3,
            "blunders": 2,
            "mistakes": 1,
            "inaccuracies": 3,
            "move_evaluations": [
                {"move_number": 7, "is_user_move": True, "classification": "normal", "centipawn_loss": 20, "cognitive_gap": None},
                {"move_number": 10, "is_user_move": True, "classification": "mistake", "centipawn_loss": 120, "cognitive_gap": "THREAT_BLINDNESS"},
                {"move_number": 13, "is_user_move": True, "classification": "blunder", "centipawn_loss": 450, "cognitive_gap": "THREAT_BLINDNESS"},
            ]
        }
    },
    # Game 2: Similar mistake (threat blindness again) - BLUNDER
    {
        "description": "Similar pattern - didn't see Re6 threat building",
        "expected_type": "similar_mistake",
        "result": "1-0",
        "user_color": "black",
        "precomputed_analysis": {
            "accuracy": 58.1,
            "blunders": 1,
            "mistakes": 2,
            "inaccuracies": 2,
            "move_evaluations": [
                {"move_number": 14, "is_user_move": True, "classification": "inaccuracy", "centipawn_loss": 65, "cognitive_gap": None},
                {"move_number": 18, "is_user_move": True, "classification": "mistake", "centipawn_loss": 180, "cognitive_gap": "THREAT_BLINDNESS"},
                {"move_number": 21, "is_user_move": True, "classification": "blunder", "centipawn_loss": 380, "cognitive_gap": "THREAT_BLINDNESS"},
            ]
        }
    },
    # Game 3: Slight improvement - still error but better
    {
        "description": "Better play - won with fewer errors",
        "expected_type": "slight_improvement",
        "result": "1-0",
        "user_color": "white",
        "precomputed_analysis": {
            "accuracy": 74.2,
            "blunders": 0,
            "mistakes": 1,
            "inaccuracies": 2,
            "move_evaluations": [
                {"move_number": 12, "is_user_move": True, "classification": "inaccuracy", "centipawn_loss": 55, "cognitive_gap": None},
                {"move_number": 19, "is_user_move": True, "classification": "mistake", "centipawn_loss": 160, "cognitive_gap": "CALCULATION_DEPTH"},
            ]
        }
    },
    # Game 4: Clean/stable game - no critical errors
    {
        "description": "Solid game - held position without major errors",
        "expected_type": "clean_game",
        "result": "1/2-1/2",
        "user_color": "black",
        "precomputed_analysis": {
            "accuracy": 88.5,
            "blunders": 0,
            "mistakes": 0,
            "inaccuracies": 1,
            "move_evaluations": [
                {"move_number": 22, "is_user_move": True, "classification": "inaccuracy", "centipawn_loss": 45, "cognitive_gap": None},
            ]
        }
    },
    # Game 5: Regression - back to threat blindness
    {
        "description": "Regression - returned to threat blindness pattern",
        "expected_type": "regression",
        "result": "0-1",
        "user_color": "white",
        "precomputed_analysis": {
            "accuracy": 48.7,
            "blunders": 2,
            "mistakes": 2,
            "inaccuracies": 1,
            "move_evaluations": [
                {"move_number": 15, "is_user_move": True, "classification": "mistake", "centipawn_loss": 140, "cognitive_gap": "THREAT_BLINDNESS"},
                {"move_number": 19, "is_user_move": True, "classification": "blunder", "centipawn_loss": 520, "cognitive_gap": "THREAT_BLINDNESS"},
                {"move_number": 23, "is_user_move": True, "classification": "blunder", "centipawn_loss": 400, "cognitive_gap": "CALCULATION_DEPTH"},
            ]
        }
    },
    # Game 6: Recovery - applying lessons
    {
        "description": "Recovery - clean play, applying threat awareness",
        "expected_type": "recovery",
        "result": "0-1",
        "user_color": "black",
        "precomputed_analysis": {
            "accuracy": 82.3,
            "blunders": 0,
            "mistakes": 0,
            "inaccuracies": 2,
            "move_evaluations": [
                {"move_number": 16, "is_user_move": True, "classification": "inaccuracy", "centipawn_loss": 50, "cognitive_gap": None},
                {"move_number": 28, "is_user_move": True, "classification": "inaccuracy", "centipawn_loss": 40, "cognitive_gap": None},
            ]
        }
    }
]


async def setup_test_environment(db) -> str:
    """Create test user and reset memory for clean test"""
    user_id = "realism_test_user_v2"
    
    # Clear existing test data
    await db.users.delete_many({"user_id": user_id})
    await db.games.delete_many({"user_id": user_id})
    await db.game_analyses.delete_many({"user_id": user_id})
    await db.game_coach_summaries.delete_many({"user_id": user_id})
    await db.coach_states.delete_many({"user_id": user_id})
    await db.coach_memory.delete_many({"user_id": user_id})
    
    # Create test user
    await db.users.insert_one({
        "user_id": user_id,
        "email": "test@chessguru.com",
        "created_at": datetime.now(timezone.utc)
    })
    
    # Initialize coach state
    coach_state = CoachState(
        user_id=user_id,
        active_theme=CoachTheme.THREAT_VERIFICATION,
        theme_started_at=datetime.now(timezone.utc),
        theme_confidence=0.7,
        theme_reason="Initial assessment",
        micro_rules=["Before committing to any move, scan for checks, captures, and threats."],
        recent_coach_sentences=[],
        games_on_theme=0,
        behavioral_maturity_level="Developing",
        good_game_streak=0
    )
    await db.coach_states.insert_one(coach_state.to_dict())
    
    print(f"Test environment setup complete for {user_id}")
    return user_id


async def analyze_game_quick(pgn: str, user_color: str) -> Dict:
    """
    Quick analysis using Stockfish for test purposes.
    Returns simplified analysis structure.
    """
    import chess
    import chess.pgn
    import io
    from training_profile_service import analyze_position_with_stockfish
    
    # Parse PGN
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return {"error": "Could not parse PGN"}
    
    board = game.board()
    moves = list(game.mainline_moves())
    
    move_evaluations = []
    prev_score = 0
    
    for i, move in enumerate(moves):
        move_num = (i // 2) + 1
        is_white_move = (i % 2 == 0)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        # Get position evaluation before move
        fen_before = board.fen()
        
        try:
            analysis = await analyze_position_with_stockfish(fen_before, depth=15)
            score = analysis.get("score_cp", 0)
            best_move = analysis.get("best_move", "")
            pv = analysis.get("pv", [])
        except Exception as e:
            score = 0
            best_move = ""
            pv = []
        
        # Make the move
        san = board.san(move)
        board.push(move)
        fen_after = board.fen()
        
        # Calculate score loss for user moves
        score_loss = 0
        if is_user_move:
            # Get position score after move
            try:
                post_analysis = await analyze_position_with_stockfish(fen_after, depth=15)
                post_score = post_analysis.get("score_cp", 0)
                
                # Score loss from user's perspective
                if user_color == "white":
                    score_loss = prev_score - post_score
                else:
                    score_loss = -prev_score - (-post_score)
            except Exception as e:
                post_score = score
                score_loss = 0
        
        # Classify move
        classification = "normal"
        if is_user_move:
            if score_loss > 300:
                classification = "blunder"
            elif score_loss > 150:
                classification = "mistake"
            elif score_loss > 50:
                classification = "inaccuracy"
        
        move_eval = {
            "move_number": move_num,
            "move_san": san,
            "move_uci": move.uci(),
            "is_white_move": is_white_move,
            "is_user_move": is_user_move,
            "fen_before": fen_before,
            "fen_after": fen_after,
            "score_before": prev_score,
            "score_after": score,
            "centipawn_loss": max(0, score_loss) if is_user_move else 0,
            "classification": classification,
            "engine_best_move": best_move,
            "engine_pv": pv[:3],
            "played_best": (san == best_move) if is_user_move else True
        }
        
        move_evaluations.append(move_eval)
        prev_score = score
    
    # Calculate stats
    user_moves = [m for m in move_evaluations if m["is_user_move"]]
    blunders = sum(1 for m in user_moves if m["classification"] == "blunder")
    mistakes = sum(1 for m in user_moves if m["classification"] == "mistake")
    inaccuracies = sum(1 for m in user_moves if m["classification"] == "inaccuracy")
    
    # Simple accuracy calculation
    total_loss = sum(m["centipawn_loss"] for m in user_moves)
    avg_loss = total_loss / len(user_moves) if user_moves else 0
    accuracy = max(0, min(100, 100 - (avg_loss / 5)))
    
    return {
        "stockfish_analysis": {
            "move_evaluations": move_evaluations,
            "blunders": blunders,
            "mistakes": mistakes,
            "inaccuracies": inaccuracies,
            "accuracy": accuracy
        }
    }


async def process_single_game(
    db,
    game_num: int,
    game_data: Dict,
    user_id: str
) -> Tuple[Optional[Dict], str]:
    """
    Process a single game through the complete coaching pipeline.
    Returns (coach_output, assembled_text).
    """
    from coach_state_service import CoachStateService
    
    game_id = f"test_game_{game_num}"
    
    print(f"\n{'='*70}")
    print(f"GAME {game_num}: {game_data['expected_type'].upper()}")
    print(f"{'='*70}")
    print(f"Description: {game_data['description']}")
    
    # Use precomputed analysis if available, otherwise analyze
    print("\n[Using precomputed analysis...]")
    
    if "precomputed_analysis" in game_data:
        sf = game_data["precomputed_analysis"]
    else:
        # Fallback to quick analysis
        analysis = await analyze_game_quick(game_data.get("pgn", ""), game_data["user_color"])
        sf = analysis.get("stockfish_analysis", {})
    
    accuracy = sf.get("accuracy", 0)
    blunders = sf.get("blunders", 0)
    moves = sf.get("move_evaluations", [])
    
    print(f"  Accuracy: {accuracy:.1f}% | Blunders: {blunders}")
    
    # Store game and analysis
    await db.games.insert_one({
        "game_id": game_id,
        "user_id": user_id,
        "pgn": game_data.get("pgn", ""),
        "result": game_data["result"],
        "user_color": game_data["user_color"],
        "played_at": datetime.now(timezone.utc),
        "is_analyzed": True
    })
    
    await db.game_analyses.insert_one({
        "analysis_id": f"analysis_{game_id}",
        "game_id": game_id,
        "user_id": user_id,
        "stockfish_analysis": sf,
        "analyzed_at": datetime.now(timezone.utc)
    })
    
    # Get coach state
    service = CoachStateService(db)
    coach_state = await service.get_coach_state(user_id)
    
    # Get memory context
    memory_service = get_memory_service(db)
    
    # Run interpretation
    user_color = game_data["user_color"]
    result = game_data["result"]
    enriched_moves, _ = interpret_game_analysis(moves, user_color)
    
    # Select teaching moment
    selection = select_teaching_moment(enriched_moves, user_color, result)
    
    selected_move = {}
    selection_reason = "no_critical_moves"
    max_crs = 0
    position_ctx = {}
    
    if selection:
        selected_move = selection.get("selected_move", {})
        selection_reason = selection.get("selection_reason", "tactical_error")
        max_crs = selection.get("selection_score", 0)
        position_ctx = selected_move.get("position_context", {})
    
    # Resolve lesson
    cognitive_gap = selected_move.get("cognitive_gap") if selected_move else None
    is_positive = selection_reason in ("positive_coaching", "no_critical_moves") or (max_crs < 100 and blunders == 0)
    
    lesson_resolution = lesson_resolver.resolve(
        cognitive_gap=cognitive_gap,
        selection_reason=selection_reason,
        crs_score=max_crs,
        is_positive_game=is_positive
    )
    
    # Build memory context
    memory_context = await memory_service.build_context(
        user_id=user_id,
        current_lesson_key=lesson_resolution.lesson_key,
        current_streak=coach_state.good_game_streak if coach_state else 0
    )
    
    # Generate narrative WITH memory context
    narrative_result = generate_coaching_narrative(
        selected_move=selected_move,
        selection_reason=selection_reason,
        position_context=position_ctx,
        maturity_level=coach_state.behavioral_maturity_level if coach_state else "Developing",
        active_theme=coach_state.active_theme.value if coach_state else None,
        recent_sentences=coach_state.recent_coach_sentences if coach_state else [],
        max_crs_score=max_crs,
        good_game_streak=coach_state.good_game_streak if coach_state else 0,
        blunders_count=blunders,
        memory_context=memory_context.to_dict() if memory_context else None,
        games_on_theme=coach_state.games_on_theme if coach_state else 0
    )
    
    assembled = narrative_result.get("assembled_text", "")
    strategy = narrative_result.get("narrative_strategy", "")
    memory_mods = narrative_result.get("memory_modifications_applied", 0)
    
    # Update memory AFTER generating narrative
    await memory_service.update_memory_after_game(
        user_id=user_id,
        game_id=game_id,
        lesson_key=lesson_resolution.lesson_key,
        lesson_category=lesson_resolution.lesson_category,
        lesson_intensity=lesson_resolution.lesson_intensity,
        is_positive_game=is_positive,
        current_streak=(coach_state.good_game_streak if coach_state else 0) + (1 if is_positive else 0)
    )
    
    # Update coach state
    if coach_state:
        if strategy == "positive_coaching":
            coach_state.good_game_streak += 1
        else:
            coach_state.good_game_streak = 0
        
        coach_state.games_on_theme += 1
        
        if assembled:
            coach_state.recent_coach_sentences.append(assembled[:50])
            coach_state.recent_coach_sentences = coach_state.recent_coach_sentences[-10:]
        
        await service.update_coach_state(coach_state)
    
    # Display coach output (ONLY THE FINAL TEXT - no metadata)
    print(f"\n{'~'*70}")
    print("COACH SAYS:")
    print(f"{'~'*70}")
    print(f"\n{assembled}")
    print(f"\n{'~'*70}")
    
    return {
        "strategy": strategy,
        "lesson_key": lesson_resolution.lesson_key,
        "memory_mods": memory_mods,
        "assembled": assembled
    }, assembled


async def run_6_game_realism_test():
    """
    Run the 6-game realism test.
    
    This tests psychological believability, not code correctness.
    """
    print("\n" + "="*70)
    print("6-GAME MEMORY REALISM TEST")
    print("="*70)
    print("""
PURPOSE: Validate psychological believability of memory-aware coaching.

SEQUENCE:
  Game 1: Clear mistake
  Game 2: Similar mistake  
  Game 3: Slight improvement
  Game 4: Clean/stable game
  Game 5: Regression
  Game 6: Recovery

EVALUATE EACH GAME (1-5):
  1. Felt Understood - Does coach sound like it watched THIS game?
  2. Memory Naturalness - Does reference to past feel organic?
  3. Emotional Timing - Is praise/correction emotionally correct?
  4. Non-Repetition - Does explanation structure feel fresh?
  5. Coaching Authority - Would I trust this coach?
    """)
    
    # Connect to DB
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    
    # Setup test environment
    user_id = await setup_test_environment(db)
    
    results = []
    assembled_texts = []
    
    # Process each game sequentially
    for i, game_data in enumerate(TEST_GAMES, 1):
        result, text = await process_single_game(db, i, game_data, user_id)
        if result:
            results.append(result)
            assembled_texts.append(text)
        
        # Pause between games (simulates real play)
        await asyncio.sleep(0.5)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST COMPLETE - SUMMARY")
    print("="*70)
    
    # Strategy distribution
    strategies = {}
    lesson_keys = {}
    total_memory_mods = 0
    
    for r in results:
        if r:
            s = r.get("strategy", "unknown")
            strategies[s] = strategies.get(s, 0) + 1
            
            lk = r.get("lesson_key", "unknown")
            lesson_keys[lk] = lesson_keys.get(lk, 0) + 1
            
            total_memory_mods += r.get("memory_mods", 0)
    
    print("\nNarrative Strategy Distribution:")
    for s, count in sorted(strategies.items(), key=lambda x: -x[1]):
        print(f"  {s}: {count}")
    
    print("\nLesson Key Distribution:")
    for lk, count in sorted(lesson_keys.items(), key=lambda x: -x[1]):
        print(f"  {lk}: {count}")
    
    print(f"\nTotal Memory Modifications: {total_memory_mods}")
    
    # Check memory state
    memory_service = get_memory_service(db)
    memory = await memory_service.get_memory_state(user_id)
    
    if memory:
        print("\nFinal Memory State:")
        print(f"  Total games analyzed: {memory.get('total_games_analyzed', 0)}")
        print(f"  Milestones achieved: {[m.get('milestone_type') for m in memory.get('milestones', [])]}")
        
        pattern_progress = memory.get("pattern_progress", {})
        print(f"  Patterns tracked: {list(pattern_progress.keys())}")
    
    # Evaluation form
    print("\n" + "="*70)
    print("EVALUATION SCORECARD")
    print("="*70)
    print("""
Rate each game 1-5 on these criteria:

| # | Type             | Understood | Memory | Emotion | Fresh | Trust |
|---|------------------|------------|--------|---------|-------|-------|
| 1 | Clear mistake    |    /5      |   /5   |   /5    |  /5   |  /5   |
| 2 | Similar mistake  |    /5      |   /5   |   /5    |  /5   |  /5   |
| 3 | Improvement      |    /5      |   /5   |   /5    |  /5   |  /5   |
| 4 | Clean game       |    /5      |   /5   |   /5    |  /5   |  /5   |
| 5 | Regression       |    /5      |   /5   |   /5    |  /5   |  /5   |
| 6 | Recovery         |    /5      |   /5   |   /5    |  /5   |  /5   |
|---|------------------|------------|--------|---------|-------|-------|
| AVG                  |    /5      |   /5   |   /5    |  /5   |  /5   |

PASS CONDITIONS:
  - Overall average >= 4.0/5
  - No category < 3.0

NOTES:
- "Understood": Does coach sound like it watched THIS game?
- "Memory": Does reference to past feel natural, not robotic?
- "Emotion": Is praise/correction emotionally appropriate for trajectory?
- "Fresh": Does explanation feel different from previous games?
- "Trust": Would you continue with this coach?
    """)
    
    # Print all coach texts for easy comparison
    print("\n" + "="*70)
    print("ALL COACH OUTPUTS (for comparison)")
    print("="*70)
    
    for i, text in enumerate(assembled_texts, 1):
        print(f"\n--- GAME {i} ---")
        print(text)


if __name__ == "__main__":
    asyncio.run(run_6_game_realism_test())
