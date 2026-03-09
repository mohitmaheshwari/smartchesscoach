"""
Post-Game Deep Analysis Service
================================

Provides comprehensive game analysis including:
1. Performance Rating - Estimate player's rating based on move quality
2. Habit Check - Track if user is improving on known weaknesses
3. Mistake Breakdown - Categorize and explain errors
4. Personalized Recommendations - Based on this game + history

This integrates with coach memory to provide continuity across sessions.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import logging
import chess

logger = logging.getLogger(__name__)


class MistakeType(str, Enum):
    """Types of chess mistakes"""
    BLUNDER = "blunder"           # Loses significant material or game
    MISTAKE = "mistake"           # Loses some advantage
    INACCURACY = "inaccuracy"     # Suboptimal but not losing
    MISSED_WIN = "missed_win"     # Missed winning opportunity
    TACTICAL_MISS = "tactical_miss"  # Missed tactic
    POSITIONAL_ERROR = "positional_error"  # Structural weakness
    TIME_TROUBLE = "time_trouble"  # Mistake due to time pressure
    OPENING_ERROR = "opening_error"  # Theory deviation


class HabitType(str, Enum):
    """Trackable chess habits"""
    EARLY_QUEEN = "early_queen"           # Moving queen too early
    ONE_MOVE_BLUNDER = "one_move_blunder"  # Missing immediate threats
    WEAK_ENDGAME = "weak_endgame"          # Poor endgame technique
    POOR_PIECE_ACTIVITY = "poor_piece_activity"  # Passive pieces
    KING_SAFETY = "king_safety"            # Neglecting king safety
    PAWN_STRUCTURE = "pawn_structure"      # Weakening pawns
    CALCULATION_ERRORS = "calculation_errors"  # Miscalculations
    TIME_MANAGEMENT = "time_management"    # Using time poorly
    IMPATIENCE = "impatience"              # Moving too fast
    OVERCONFIDENCE = "overconfidence"      # Playing risky in winning positions


@dataclass
class MistakeAnalysis:
    """Analysis of a single mistake"""
    move_number: int
    move_played: str
    mistake_type: MistakeType
    severity: str  # "critical", "moderate", "minor"
    explanation: str
    better_move: Optional[str] = None
    evaluation_change: float = 0.0
    fen_before: str = ""


@dataclass
class HabitViolation:
    """Record of a habit violation in this game"""
    habit_type: HabitType
    move_number: int
    description: str
    is_improvement: bool = False  # True if user showed improvement


@dataclass
class PerformanceRating:
    """Estimated performance rating for this game"""
    estimated_rating: int
    confidence: str  # "high", "medium", "low"
    comparison_to_actual: str  # "above", "at", "below"
    rating_change_suggested: int  # +/- from actual
    key_factors: List[str] = field(default_factory=list)


@dataclass
class PostGameAnalysis:
    """Complete post-game analysis"""
    session_id: str
    user_id: str
    game_result: str  # "win", "loss", "draw"
    
    # Performance
    performance_rating: PerformanceRating
    accuracy_percentage: float
    
    # Mistakes
    mistakes: List[MistakeAnalysis]
    total_blunders: int
    total_mistakes: int
    total_inaccuracies: int
    
    # Habits
    habit_violations: List[HabitViolation]
    habits_improved: List[str]
    habits_still_weak: List[str]
    
    # Recommendations
    priority_focus: str  # Main thing to work on
    training_suggestions: List[str]
    
    # Summary
    coach_summary: str
    encouragement: str
    
    # Optional
    opening_to_learn: Optional[str] = None


async def analyze_postgame(
    db,
    session_id: str,
    user_id: str,
    move_history: List[Dict],
    evaluations: List[Dict],
    game_result: str,
    user_rating: int,
    user_color: str,
    time_controls: Optional[Dict] = None
) -> PostGameAnalysis:
    """
    Perform comprehensive post-game analysis.
    
    Args:
        db: Database connection
        session_id: Game session ID
        user_id: User ID
        move_history: List of moves with metadata
        evaluations: Position evaluations for each move
        game_result: "win", "loss", "draw"
        user_rating: User's actual rating
        user_color: "white" or "black"
        time_controls: Time spent on each move
    
    Returns:
        PostGameAnalysis with all components
    """
    
    # 1. Analyze mistakes
    mistakes = await _analyze_mistakes(move_history, evaluations, user_color)
    
    # 2. Calculate performance rating
    perf_rating = _calculate_performance_rating(
        mistakes, 
        move_history, 
        evaluations, 
        user_rating,
        game_result
    )
    
    # 3. Check habits against user's known weaknesses
    habit_violations, habits_improved, habits_weak = await _check_habits(
        db, user_id, move_history, evaluations, user_color, time_controls
    )
    
    # 4. Generate recommendations
    priority_focus, training_suggestions = _generate_recommendations(
        mistakes, habit_violations, habits_weak, perf_rating
    )
    
    # 5. Determine if opening study is needed
    opening_to_learn = await _suggest_opening(db, user_id, move_history, user_color)
    
    # 6. Generate coach summary and encouragement
    summary, encouragement = _generate_summary(
        game_result, perf_rating, mistakes, habits_improved, user_rating
    )
    
    # 7. Calculate accuracy
    accuracy = _calculate_accuracy(mistakes, len(move_history) // 2)
    
    # Count mistake types
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    mistake_count = len([m for m in mistakes if m.mistake_type == MistakeType.MISTAKE])
    inaccuracies = len([m for m in mistakes if m.mistake_type == MistakeType.INACCURACY])
    
    analysis = PostGameAnalysis(
        session_id=session_id,
        user_id=user_id,
        game_result=game_result,
        performance_rating=perf_rating,
        accuracy_percentage=accuracy,
        mistakes=mistakes,
        total_blunders=blunders,
        total_mistakes=mistake_count,
        total_inaccuracies=inaccuracies,
        habit_violations=habit_violations,
        habits_improved=habits_improved,
        habits_still_weak=habits_weak,
        priority_focus=priority_focus,
        training_suggestions=training_suggestions,
        opening_to_learn=opening_to_learn,
        coach_summary=summary,
        encouragement=encouragement
    )
    
    # Save analysis to database for future reference
    await _save_analysis(db, analysis)
    
    # Update user's habit tracking
    await _update_habit_tracking(db, user_id, habit_violations, habits_improved)
    
    return analysis


async def _analyze_mistakes(
    move_history: List[Dict],
    evaluations: List[Dict],
    user_color: str
) -> List[MistakeAnalysis]:
    """Analyze all mistakes in the game using stored evaluations."""
    mistakes = []
    
    # Build evaluation lookup by move number (evaluations only contain player moves)
    eval_by_move = {}
    for ev in evaluations:
        if ev.get("by") == "player":
            eval_by_move[ev.get("move_number")] = ev
    
    # Check each player move
    for i, move in enumerate(move_history):
        if move.get("by") != "player":
            continue
        
        # Get evaluation data from the move itself or from evaluations list
        eval_before = move.get("eval_before", 0)
        eval_after = move.get("eval_after", 0)
        
        # Also check evaluations list if move doesn't have eval data
        move_num = (i // 2) + 1  # Calculate move number
        if eval_before == 0 and eval_after == 0 and move_num in eval_by_move:
            ev = eval_by_move[move_num]
            eval_before = ev.get("eval_before", 0)
            eval_after = ev.get("eval_after", 0)
        
        # Skip if no evaluation data
        if eval_before == 0 and eval_after == 0:
            continue
        
        # Normalize scores for black (negative is good for black)
        if user_color == "black":
            eval_before = -eval_before
            eval_after = -eval_after
        
        # Calculate centipawn loss (in pawns)
        eval_change = eval_after - eval_before
        
        # Classify mistake based on centipawn loss
        if eval_change < -2.0:
            mistake_type = MistakeType.BLUNDER
            severity = "critical"
            explanation = f"Lost {abs(eval_change):.1f} pawns worth of advantage."
        elif eval_change < -1.0:
            mistake_type = MistakeType.MISTAKE
            severity = "moderate"
            explanation = f"Gave away {abs(eval_change):.1f} pawns of advantage."
        elif eval_change < -0.3:
            mistake_type = MistakeType.INACCURACY
            severity = "minor"
            explanation = f"Small inaccuracy - lost {abs(eval_change):.1f} pawns."
        else:
            continue  # Good move, skip
        
        # Get better move suggestion
        better_move = move.get("best_move")
        
        mistakes.append(MistakeAnalysis(
            move_number=(i // 2) + 1,
            move_played=move.get("move", "?"),
            mistake_type=mistake_type,
            severity=severity,
            explanation=explanation,
            better_move=better_move,
            evaluation_change=eval_change,
            fen_before=move.get("fen_before", "")
        ))
    
    return mistakes


def _calculate_performance_rating(
    mistakes: List[MistakeAnalysis],
    move_history: List[Dict],
    evaluations: List[Dict],
    user_rating: int,
    game_result: str
) -> PerformanceRating:
    """Calculate estimated performance rating based on move quality."""
    
    # Base rating adjustment based on mistake count
    user_moves = len([m for m in move_history if m.get("by") == "player"])
    if user_moves == 0:
        user_moves = 1
    
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    mistake_count = len([m for m in mistakes if m.mistake_type == MistakeType.MISTAKE])
    inaccuracies = len([m for m in mistakes if m.mistake_type == MistakeType.INACCURACY])
    
    # Calculate error rate
    error_rate = (blunders * 3 + mistake_count * 2 + inaccuracies) / user_moves
    
    # Base performance estimate
    # 0 errors = +200 from rating, 1 error per 10 moves = at rating, more = below
    rating_adjustment = int((0.1 - error_rate) * 1000)
    rating_adjustment = max(-400, min(300, rating_adjustment))  # Cap adjustment
    
    estimated = user_rating + rating_adjustment
    
    # Adjust for game result
    if game_result == "win":
        estimated += 50
    elif game_result == "loss":
        estimated -= 50
    
    # Determine confidence
    if user_moves >= 30:
        confidence = "high"
    elif user_moves >= 15:
        confidence = "medium"
    else:
        confidence = "low"
    
    # Comparison
    diff = estimated - user_rating
    if diff > 100:
        comparison = "above"
    elif diff < -100:
        comparison = "below"
    else:
        comparison = "at"
    
    # Key factors
    factors = []
    if blunders == 0:
        factors.append("No blunders - excellent discipline!")
    elif blunders >= 3:
        factors.append(f"{blunders} blunders significantly impacted your score")
    
    if error_rate < 0.05:
        factors.append("Very accurate play throughout")
    elif error_rate > 0.2:
        factors.append("Consider slowing down - many inaccuracies")
    
    return PerformanceRating(
        estimated_rating=estimated,
        confidence=confidence,
        comparison_to_actual=comparison,
        rating_change_suggested=rating_adjustment,
        key_factors=factors
    )


async def _check_habits(
    db,
    user_id: str,
    move_history: List[Dict],
    evaluations: List[Dict],
    user_color: str,
    time_controls: Optional[Dict]
) -> tuple[List[HabitViolation], List[str], List[str]]:
    """Check for habit violations and improvements."""
    
    # Get user's known weaknesses from memory
    user_memory = await db.user_memory.find_one({"user_id": user_id})
    known_weaknesses = user_memory.get("weaknesses", []) if user_memory else []
    
    violations = []
    improved = []
    still_weak = []
    
    # Check for early queen moves
    queen_moved_early = False
    for i, move in enumerate(move_history[:12]):  # First 6 moves per side
        if move.get("by") == "player":
            move_san = move.get("move", "")
            if move_san.startswith("Q") and i < 10:
                queen_moved_early = True
                violations.append(HabitViolation(
                    habit_type=HabitType.EARLY_QUEEN,
                    move_number=(i // 2) + 1,
                    description=f"Queen moved early ({move_san}). Develop minor pieces first!"
                ))
                break
    
    # Track habit status
    if "early_queen" in known_weaknesses:
        if not queen_moved_early:
            improved.append("early_queen")
        else:
            still_weak.append("early_queen")
    elif queen_moved_early:
        still_weak.append("early_queen")
    
    # Check for one-move blunders (missing immediate threats)
    for i, move in enumerate(move_history):
        if move.get("by") == "player" and move.get("missed_threat"):
            violations.append(HabitViolation(
                habit_type=HabitType.ONE_MOVE_BLUNDER,
                move_number=(i // 2) + 1,
                description="Missed an immediate threat from opponent"
            ))
    
    # Check time management if data available
    if time_controls:
        fast_moves = sum(1 for t in time_controls.values() if t < 3)
        if fast_moves > 5:
            violations.append(HabitViolation(
                habit_type=HabitType.IMPATIENCE,
                move_number=0,
                description=f"Made {fast_moves} moves in under 3 seconds each. Slow down!"
            ))
            still_weak.append("impatience")
    
    return violations, improved, still_weak


def _generate_recommendations(
    mistakes: List[MistakeAnalysis],
    habit_violations: List[HabitViolation],
    habits_weak: List[str],
    perf_rating: PerformanceRating
) -> tuple[str, List[str]]:
    """Generate personalized recommendations."""
    
    suggestions = []
    priority = "general_improvement"
    
    # Analyze mistake patterns
    blunders = [m for m in mistakes if m.mistake_type == MistakeType.BLUNDER]
    
    if len(blunders) >= 2:
        priority = "reducing_blunders"
        suggestions.append("Practice tactics puzzles for 15 minutes daily - your blunder rate is too high")
        suggestions.append("Before each move, ask: 'What is my opponent threatening?'")
    
    # Habit-based recommendations
    if "early_queen" in habits_weak:
        suggestions.append("Focus on developing knights and bishops before the queen")
    
    if "impatience" in habits_weak:
        suggestions.append("Set a rule: spend at least 10 seconds on each move")
        priority = "time_management"
    
    if "one_move_blunder" in habits_weak:
        suggestions.append("Practice 'blunder check' - verify your move doesn't hang a piece")
    
    # Performance-based recommendations
    if perf_rating.comparison_to_actual == "below":
        suggestions.append("Consider playing longer time controls to improve accuracy")
    
    if not suggestions:
        suggestions = [
            "Good game! Keep practicing to maintain consistency",
            "Try analyzing your games to find patterns in your play"
        ]
    
    return priority, suggestions[:4]  # Max 4 suggestions


async def _suggest_opening(
    db,
    user_id: str,
    move_history: List[Dict],
    user_color: str
) -> Optional[str]:
    """Suggest an opening to learn based on game and history."""
    from services.opening_mastery import detect_opening_from_moves, OPENING_DATABASE
    
    moves = [m.get("move", "") for m in move_history if m.get("move")]
    opening_info = detect_opening_from_moves(moves[:10])  # Check first 10 moves
    
    if opening_info:
        opening_key = opening_info.get("opening_key")
        opening = OPENING_DATABASE.get(opening_key)
        if opening and opening.variations:
            # Check if user knows this opening
            progress = await db.user_opening_progress.find_one({
                "user_id": user_id,
                "opening_name": opening.name
            })
            
            if not progress or progress.get("mastery_level") in ["unknown", "introduced"]:
                return f"Learn the {opening.name} - you played it but may not know the key ideas!"
    
    return None


def _generate_summary(
    game_result: str,
    perf_rating: PerformanceRating,
    mistakes: List[MistakeAnalysis],
    habits_improved: List[str],
    user_rating: int
) -> tuple[str, str]:
    """Generate coach summary and encouragement."""
    
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    
    # Summary
    if perf_rating.comparison_to_actual == "above":
        summary = f"You played like a {perf_rating.estimated_rating} player today - that's above your rating of {user_rating}! "
    elif perf_rating.comparison_to_actual == "below":
        summary = f"This game was a bit below your usual level ({perf_rating.estimated_rating} vs your {user_rating} rating). "
    else:
        summary = f"You played right at your level ({perf_rating.estimated_rating}). "
    
    if blunders == 0:
        summary += "No blunders - excellent discipline! "
    elif blunders == 1:
        summary += "One blunder to learn from. "
    else:
        summary += f"{blunders} blunders - let's work on reducing these. "
    
    if habits_improved:
        habit_names = {"early_queen": "early queen moves", "impatience": "rushing"}
        improved_text = ", ".join(habit_names.get(h, h) for h in habits_improved)
        summary += f"Great news: you avoided {improved_text} this game!"
    
    # Encouragement based on result and performance
    if game_result == "win":
        if perf_rating.comparison_to_actual == "above":
            encouragement = "Brilliant game! You're definitely improving. Keep this up!"
        else:
            encouragement = "A win is a win! Nice job closing out the game."
    elif game_result == "loss":
        if blunders > 0:
            encouragement = "Losses are lessons. Let's review those blunders and turn them into wins next time."
        else:
            encouragement = "Close game! You played well but chess is tough. Keep grinding!"
    else:
        encouragement = "A solid draw. Every game teaches something - what did you learn from this one?"
    
    return summary, encouragement


def _calculate_accuracy(mistakes: List[MistakeAnalysis], total_moves: int) -> float:
    """Calculate accuracy percentage."""
    if total_moves == 0:
        return 100.0
    
    error_points = sum(
        3 if m.mistake_type == MistakeType.BLUNDER else
        2 if m.mistake_type == MistakeType.MISTAKE else
        1
        for m in mistakes
    )
    
    # Each move can contribute up to 3 error points, so max = total_moves * 3
    max_error = total_moves * 3
    accuracy = max(0, (1 - (error_points / max_error))) * 100
    
    return round(accuracy, 1)


async def _save_analysis(db, analysis: PostGameAnalysis):
    """Save analysis to database for future reference."""
    doc = {
        "session_id": analysis.session_id,
        "user_id": analysis.user_id,
        "game_result": analysis.game_result,
        "performance_rating": asdict(analysis.performance_rating),
        "accuracy": analysis.accuracy_percentage,
        "blunders": analysis.total_blunders,
        "mistakes": analysis.total_mistakes,
        "inaccuracies": analysis.total_inaccuracies,
        "habits_improved": analysis.habits_improved,
        "habits_weak": analysis.habits_still_weak,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.game_analyses.update_one(
        {"session_id": analysis.session_id},
        {"$set": doc},
        upsert=True
    )


async def _update_habit_tracking(
    db,
    user_id: str,
    violations: List[HabitViolation],
    improved: List[str]
):
    """Update user's habit tracking in memory."""
    
    # Get current memory
    memory = await db.user_memory.find_one({"user_id": user_id})
    if not memory:
        memory = {"user_id": user_id, "weaknesses": [], "strengths": [], "habit_history": []}
    
    weaknesses = set(memory.get("weaknesses", []))
    strengths = set(memory.get("strengths", []))
    
    # Add new weaknesses from violations
    for v in violations:
        weaknesses.add(v.habit_type.value)
    
    # Track improvements
    for habit in improved:
        # If improved 3 games in a row, move to strength
        # For now, just remove from weaknesses
        if habit in weaknesses:
            weaknesses.discard(habit)
    
    await db.user_memory.update_one(
        {"user_id": user_id},
        {"$set": {
            "weaknesses": list(weaknesses),
            "strengths": list(strengths),
            "last_analysis": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
