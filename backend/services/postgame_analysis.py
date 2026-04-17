"""
Post-Game Deep Analysis Service
================================

Provides comprehensive game analysis including:
1. Performance Rating - Estimate player's rating based on move quality
2. Habit Check - Track if user is improving on known weaknesses
3. Mistake Breakdown - Categorize and explain errors
4. Personalized Recommendations - Based on this game + history
5. MEMORY INTEGRATION - Uses coach_memory for personalized, history-aware feedback

This integrates with coach memory to provide continuity across sessions.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import logging

# Import coach memory for personalization
from services.coach_memory import (
    get_or_create_memory,
    get_coaching_context,
    update_memory_after_game
)

logger = logging.getLogger(__name__)


class MistakeType(str, Enum):
    """Types of chess mistakes"""
    BLUNDER = "blunder"
    MISTAKE = "mistake"
    INACCURACY = "inaccuracy"
    MISSED_WIN = "missed_win"
    TACTICAL_MISS = "tactical_miss"
    POSITIONAL_ERROR = "positional_error"
    TIME_TROUBLE = "time_trouble"
    OPENING_ERROR = "opening_error"


class HabitType(str, Enum):
    """Trackable chess habits"""
    EARLY_QUEEN = "early_queen"
    ONE_MOVE_BLUNDER = "one_move_blunder"
    WEAK_ENDGAME = "weak_endgame"
    POOR_PIECE_ACTIVITY = "poor_piece_activity"
    KING_SAFETY = "king_safety"
    PAWN_STRUCTURE = "pawn_structure"
    CALCULATION_ERRORS = "calculation_errors"
    TIME_MANAGEMENT = "time_management"
    IMPATIENCE = "impatience"
    OVERCONFIDENCE = "overconfidence"


@dataclass
class MistakeAnalysis:
    """Analysis of a single mistake"""
    move_number: int
    move_played: str
    mistake_type: MistakeType
    severity: str
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
    is_improvement: bool = False


@dataclass
class PerformanceRating:
    """Estimated performance rating for this game"""
    estimated_rating: int
    confidence: str
    comparison_to_actual: str
    rating_change_suggested: int
    key_factors: List[str] = field(default_factory=list)


@dataclass
class MemoryInsight:
    """Insight from coach memory - makes the coach feel human"""
    insight_type: str  # "recurring_pattern", "improvement", "first_time", "habit_check"
    message: str  # The actual personalized message
    pattern_name: Optional[str] = None
    occurrence_count: int = 0
    is_improving: bool = False


@dataclass
class PostGameAnalysis:
    """Complete post-game analysis"""
    session_id: str
    user_id: str
    game_result: str
    
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
    priority_focus: str
    training_suggestions: List[str]
    
    # Summary
    coach_summary: str
    encouragement: str
    
    # Phase-by-phase breakdown
    phase_analysis: Optional[Dict] = None

    # Fields with defaults must come last
    # MEMORY-BASED PERSONALIZATION
    memory_insights: List[MemoryInsight] = field(default_factory=list)
    games_together: int = 0
    coach_knows_you: bool = False
    opening_to_learn: Optional[str] = None

    # Endgame detection
    endgame_type: Optional[str] = None  # e.g., "king_rook", "king_pawn"
    endgame_lesson_needed: Optional[str] = None  # e.g., "Rook Checkmate"

    # Curriculum brain prescription — THE one thing to work on next
    coach_prescription: Optional[str] = None  # e.g., "hanging_piece", "rook_checkmate"
    prescription_type: Optional[str] = None  # "habit", "endgame_lesson", "pattern_drill"
    prescription_reason: Optional[str] = None  # Why this was prescribed


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
    Perform comprehensive post-game analysis WITH MEMORY INTEGRATION.
    
    This is the key function that makes the coach feel human by:
    1. Fetching user's history BEFORE analysis
    2. Cross-referencing current mistakes with past patterns
    3. Generating personalized insights based on memory
    4. Updating memory AFTER analysis for future sessions
    """
    
    # ========== STEP 0: FETCH COACH MEMORY ==========
    # This is what makes the coach REMEMBER the player
    memory_context = await get_coaching_context(db, user_id)
    await get_or_create_memory(db, user_id)
    
    games_together = memory_context.get("games_played", 0)
    known_weaknesses = memory_context.get("watch_for", [])
    avg_accuracy = memory_context.get("avg_accuracy", 0)
    avg_blunders = memory_context.get("avg_blunders", 0)
    is_improving = memory_context.get("improving", False)
    
    logger.info(f"Coach memory loaded: {games_together} games, {len(known_weaknesses)} known weaknesses")
    
    # ========== STEP 1: ANALYZE MISTAKES ==========
    mistakes = await _analyze_mistakes(move_history, evaluations, user_color)
    
    # ========== STEP 2: CALCULATE PERFORMANCE RATING ==========
    perf_rating = _calculate_performance_rating(
        mistakes, move_history, evaluations, user_rating, game_result
    )
    
    # ========== STEP 3: CHECK HABITS WITH MEMORY ==========
    habit_violations, habits_improved, habits_weak = await _check_habits_with_memory(
        db, user_id, move_history, evaluations, user_color, time_controls, known_weaknesses
    )
    
    # ========== STEP 4: GENERATE MEMORY INSIGHTS ==========
    # This is what makes the coach feel like it KNOWS you
    memory_insights = _generate_memory_insights(
        mistakes, habit_violations, habits_improved, 
        known_weaknesses, games_together, avg_accuracy, avg_blunders,
        perf_rating.estimated_rating, user_rating
    )
    
    # ========== STEP 5: GENERATE RECOMMENDATIONS ==========
    priority_focus, training_suggestions = _generate_recommendations(
        mistakes, habit_violations, habits_weak, perf_rating, known_weaknesses
    )
    
    # ========== STEP 6: SUGGEST OPENING ==========
    opening_to_learn = await _suggest_opening(db, user_id, move_history, user_color)
    
    # ========== STEP 7: GENERATE PERSONALIZED SUMMARY ==========
    summary, encouragement = _generate_personalized_summary(
        game_result, perf_rating, mistakes, habits_improved, 
        user_rating, memory_insights, games_together, is_improving
    )
    
    # ========== STEP 8: CALCULATE ACCURACY ==========
    # Count user moves correctly based on color
    user_move_count = sum(
        1 for i, m in enumerate(move_history)
        if ((i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black"))
    )
    accuracy = _calculate_accuracy(mistakes, user_move_count)
    
    # Count mistakes
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    mistake_count = len([m for m in mistakes if m.mistake_type == MistakeType.MISTAKE])
    inaccuracies = len([m for m in mistakes if m.mistake_type == MistakeType.INACCURACY])
    
    # ========== STEP 8.5: PHASE ANALYSIS ==========
    session_doc = await db.coach_sessions.find_one(
        {"session_id": session_id}, {"_id": 0, "opening_name": 1, "opening_to_teach": 1, "opening_branch": 1}
    )
    phase_analysis = _analyze_phases(move_history, evaluations, mistakes, user_color, session_doc)

    # ========== STEP 8.6: ENDGAME TYPE DETECTION ==========
    # If the game reached an endgame, detect the type so the curriculum brain
    # can prescribe the right endgame lesson (e.g., "learn K+R mate")
    endgame_type_detected = None
    endgame_lesson_needed = None
    try:
        from services.endgame_teaching import detect_endgame_type, get_relevant_lesson
        import chess as _chess

        # Check the final position and positions in the last 20 moves
        for m in reversed(move_history[-20:]):
            fen = m.get("fen_after") or m.get("fen_before")
            if fen:
                board = _chess.Board(fen)
                etype = detect_endgame_type(board)
                if etype:
                    endgame_type_detected = etype.value
                    # Did the student fail to convert? (had winning endgame but didn't win)
                    if game_result != "win":
                        lesson = get_relevant_lesson(etype, board)
                        if lesson:
                            endgame_lesson_needed = lesson.name
                    break
    except Exception:
        pass

    # ========== STEP 8.7: CURRICULUM BRAIN — PICK ONE PRESCRIPTION ==========
    # Get current focus from coach memory to check for graduation
    current_focus = None
    try:
        from services.coach_memory import get_or_create_memory
        memory = await get_or_create_memory(db, user_id)
        current_focus = memory.learning.current_focus
    except Exception:
        pass

    # Detect what opening was played (for trap/opening prescription)
    opening_played_key = None
    try:
        from services.opening_mastery import detect_opening_from_moves
        moves_list = [m.get("move", "") for m in move_history if m.get("move")]
        opening_info = detect_opening_from_moves(moves_list[:10])
        if opening_info:
            opening_played_key = opening_info.get("opening_key")
    except Exception:
        pass

    coach_prescription, prescription_type, prescription_reason = _pick_prescription(
        mistakes=mistakes,
        habit_violations=habit_violations,
        game_result=game_result,
        endgame_type=endgame_type_detected,
        endgame_lesson_needed=endgame_lesson_needed,
        user_rating=user_rating,
        current_focus=current_focus,
        phase_analysis=phase_analysis,
        opening_to_learn=opening_to_learn,
        opening_played=opening_played_key,
    )

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
        memory_insights=memory_insights,
        games_together=games_together + 1,
        coach_knows_you=games_together >= 3,
        priority_focus=priority_focus,
        training_suggestions=training_suggestions,
        opening_to_learn=opening_to_learn,
        coach_summary=summary,
        encouragement=encouragement,
        phase_analysis=phase_analysis,
        endgame_type=endgame_type_detected,
        endgame_lesson_needed=endgame_lesson_needed,
        coach_prescription=coach_prescription,
        prescription_type=prescription_type,
        prescription_reason=prescription_reason,
    )
    
    # ========== STEP 9: SAVE ANALYSIS ==========
    await _save_analysis(db, analysis)
    
    # ========== STEP 10: UPDATE COACH MEMORY ==========
    # This is critical - saves patterns for NEXT game's personalization
    await _update_coach_memory_after_game(
        db, user_id, game_result, accuracy, blunders, mistake_count,
        habit_violations, habits_improved, move_history, perf_rating.estimated_rating,
        coach_prescription=coach_prescription,
        prescription_type=prescription_type,
    )
    
    return analysis


def _analyze_phases(
    move_history: List[Dict],
    evaluations: List[Dict],
    mistakes: List[MistakeAnalysis],
    user_color: str,
    session_doc: Dict = None,
) -> Dict:
    """
    Break the game into Opening / Middlegame / Endgame phases.
    Return accuracy, key moments, and verdict for each.
    """
    import chess

    total_moves = len(move_history)
    user_move_indices = []
    for i, m in enumerate(move_history):
        if m.get("by") == "player":
            user_move_indices.append(i)

    # Detect phase boundaries from the positions
    # Opening: moves 1-12 (or until most pieces are developed)
    # Middlegame: moves 13-30 (or until few pieces remain)
    # Endgame: moves 31+ (or when queens are off + few pieces)
    opening_end = min(24, total_moves)  # plies (12 full moves)
    endgame_start = total_moves  # default: no endgame detected

    for i, m in enumerate(move_history):
        fen = m.get("fen_after", "")
        if fen and i > 20:
            try:
                board = chess.Board(fen)
                # Endgame: no queens or very few pieces
                white_pieces = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.WHITE))
                black_pieces = len(board.pieces(chess.QUEEN, chess.BLACK)) + len(board.pieces(chess.ROOK, chess.BLACK)) + len(board.pieces(chess.BISHOP, chess.BLACK)) + len(board.pieces(chess.KNIGHT, chess.BLACK))
                total_pieces = white_pieces + black_pieces
                has_queens = bool(board.pieces(chess.QUEEN, chess.WHITE)) or bool(board.pieces(chess.QUEEN, chess.BLACK))
                if total_pieces <= 6 or (not has_queens and total_pieces <= 8):
                    endgame_start = i
                    break
            except Exception:
                pass

    middlegame_end = endgame_start

    # Classify each mistake into a phase
    def _get_phase(move_num):
        # move_num is 1-indexed full move, convert to ply index
        ply = (move_num - 1) * 2 if user_color == "white" else (move_num - 1) * 2 + 1
        if ply < opening_end:
            return "opening"
        elif ply < middlegame_end:
            return "middlegame"
        else:
            return "endgame"

    phases = {
        "opening": {"name": "Opening", "moves": 0, "user_moves": 0, "mistakes": 0, "blunders": 0, "accuracy": 0, "key_moments": [], "verdict": ""},
        "middlegame": {"name": "Middlegame", "moves": 0, "user_moves": 0, "mistakes": 0, "blunders": 0, "accuracy": 0, "key_moments": [], "verdict": ""},
        "endgame": {"name": "Endgame", "moves": 0, "user_moves": 0, "mistakes": 0, "blunders": 0, "accuracy": 0, "key_moments": [], "verdict": ""},
    }

    # Count moves per phase
    for i, m in enumerate(move_history):
        if i < opening_end:
            phases["opening"]["moves"] += 1
            if m.get("by") == "player":
                phases["opening"]["user_moves"] += 1
        elif i < middlegame_end:
            phases["middlegame"]["moves"] += 1
            if m.get("by") == "player":
                phases["middlegame"]["user_moves"] += 1
        else:
            phases["endgame"]["moves"] += 1
            if m.get("by") == "player":
                phases["endgame"]["user_moves"] += 1

    # Assign mistakes to phases
    for mistake in mistakes:
        phase = _get_phase(mistake.move_number)
        if mistake.mistake_type == MistakeType.BLUNDER:
            phases[phase]["blunders"] += 1
        elif mistake.mistake_type in (MistakeType.MISTAKE, MistakeType.TACTICAL_MISS, MistakeType.POSITIONAL_ERROR):
            phases[phase]["mistakes"] += 1
        # Key moments (top 2 per phase)
        if len(phases[phase]["key_moments"]) < 2:
            phases[phase]["key_moments"].append({
                "move": mistake.move_number,
                "played": mistake.move_played,
                "type": mistake.mistake_type.value,
                "explanation": mistake.explanation[:100],
                "better": mistake.better_move,
            })

    # Calculate per-phase accuracy
    for key, phase in phases.items():
        user_moves = phase["user_moves"]
        if user_moves == 0:
            phase["accuracy"] = None  # Phase didn't happen
            continue
        errors = phase["mistakes"] + phase["blunders"]
        phase["accuracy"] = round(max(0, (1 - errors / user_moves)) * 100)

    # Generate verdicts
    for key, phase in phases.items():
        if phase["accuracy"] is None:
            phase["verdict"] = ""
            continue
        acc = phase["accuracy"]
        blunders = phase["blunders"]
        mistakes_ct = phase["mistakes"]
        if blunders == 0 and mistakes_ct == 0:
            phase["verdict"] = "Clean play. No significant errors."
        elif blunders == 0 and mistakes_ct <= 1:
            phase["verdict"] = "Solid. One small slip."
        elif blunders >= 2:
            phase["verdict"] = f"Rough. {blunders} blunders cost you here."
        elif blunders == 1:
            phase["verdict"] = "One critical moment changed the game."
        else:
            phase["verdict"] = f"{mistakes_ct} inaccuracies. Room to sharpen."

    # Add opening-specific info if available
    if session_doc:
        opening_name = session_doc.get("opening_name") or session_doc.get("opening_to_teach")
        if opening_name:
            phases["opening"]["opening_name"] = opening_name
        branch = session_doc.get("opening_branch")
        if branch:
            phases["opening"]["variation"] = branch

    # Remove phases that didn't happen
    result = {}
    for key, phase in phases.items():
        if phase["moves"] > 0:
            result[key] = phase

    return result


def _generate_memory_insights(
    mistakes: List[MistakeAnalysis],
    habit_violations: List[HabitViolation],
    habits_improved: List[str],
    known_weaknesses: List[Dict],
    games_together: int,
    avg_accuracy: float,
    avg_blunders: float,
    perf_rating: int,
    actual_rating: int
) -> List[MemoryInsight]:
    """
    Generate personalized insights based on coach memory.
    
    This is what makes the coach feel HUMAN - it remembers patterns,
    acknowledges improvement, and gives context-aware feedback.
    """
    insights = []
    
    # Count current game stats
    current_blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    100 - (len(mistakes) * 5)  # Rough estimate
    
    # ===== RECURRING PATTERN CHECK =====
    # Check if current mistakes match known weaknesses
    for weakness in known_weaknesses:
        weakness_name = weakness.get("name", "")
        weakness_count = weakness.get("count", 0)
        weakness_improving = weakness.get("improving", False)
        
        # Check if this weakness appeared again
        weakness_appeared = False
        for violation in habit_violations:
            habit_name = violation.habit_type.value.replace("_", " ")
            if habit_name.lower() in weakness_name.lower() or weakness_name.lower() in habit_name.lower():
                weakness_appeared = True
                break
        
        if weakness_appeared and weakness_count >= 2:
            # This is a RECURRING pattern - the coach remembers!
            if weakness_count >= 5:
                msg = f"I've seen '{weakness_name}' in {weakness_count} of your games now. This is your main habit to fix."
            elif weakness_count >= 3:
                msg = f"'{weakness_name}' again - that's {weakness_count} times now. Let's focus on this."
            else:
                msg = f"We've seen '{weakness_name}' before. Stay aware of this pattern."
            
            insights.append(MemoryInsight(
                insight_type="recurring_pattern",
                message=msg,
                pattern_name=weakness_name,
                occurrence_count=weakness_count + 1,
                is_improving=weakness_improving
            ))
    
    # ===== IMPROVEMENT ACKNOWLEDGMENT =====
    for habit in habits_improved:
        habit_name = habit.replace("_", " ")
        # Check if this was a known weakness
        was_known = any(w.get("name", "").lower() in habit_name.lower() for w in known_weaknesses)
        
        if was_known:
            msg = f"You avoided '{habit_name}' this game - that's real progress!"
            insights.append(MemoryInsight(
                insight_type="improvement",
                message=msg,
                pattern_name=habit_name,
                is_improving=True
            ))
    
    # ===== PERFORMANCE COMPARISON =====
    if games_together >= 3:
        if current_blunders == 0 and avg_blunders > 0.5:
            insights.append(MemoryInsight(
                insight_type="performance_comparison",
                message=f"Zero blunders! You usually average {avg_blunders:.1f} per game. Excellent discipline today.",
                is_improving=True
            ))
        elif current_blunders > avg_blunders + 1:
            insights.append(MemoryInsight(
                insight_type="performance_comparison",
                message=f"More blunders than usual ({current_blunders} vs your avg {avg_blunders:.1f}). What happened?",
                is_improving=False
            ))
        
        # Rating performance
        if perf_rating > actual_rating + 100:
            insights.append(MemoryInsight(
                insight_type="performance_comparison",
                message=f"You played above your level today ({perf_rating} vs {actual_rating}). This is what improvement looks like!",
                is_improving=True
            ))
    
    # ===== FIRST-TIME PATTERNS =====
    for violation in habit_violations:
        habit_name = violation.habit_type.value.replace("_", " ")
        is_new = not any(w.get("name", "").lower() in habit_name.lower() for w in known_weaknesses)
        
        if is_new and len(insights) < 4:
            insights.append(MemoryInsight(
                insight_type="first_time",
                message=f"New pattern spotted: '{habit_name}'. I'll watch for this in future games.",
                pattern_name=habit_name,
                occurrence_count=1
            ))
    
    # ===== GAMES TOGETHER MILESTONE =====
    if games_together in [5, 10, 25, 50]:
        insights.append(MemoryInsight(
            insight_type="milestone",
            message=f"This was game #{games_together} together! I'm starting to understand your style.",
            occurrence_count=games_together
        ))
    
    return insights[:5]  # Max 5 insights


async def _check_habits_with_memory(
    db,
    user_id: str,
    move_history: List[Dict],
    evaluations: List[Dict],
    user_color: str,
    time_controls: Optional[Dict],
    known_weaknesses: List[Dict]
) -> Tuple[List[HabitViolation], List[str], List[str]]:
    """Check for habit violations using coach memory for context."""
    
    violations = []
    improved = []
    still_weak = []
    
    # Get known weakness names for comparison
    known_weakness_names = [w.get("name", "").lower() for w in known_weaknesses]
    
    # Check for early queen moves
    queen_moved_early = False
    for i, move in enumerate(move_history[:12]):
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
    
    # Track habit status with memory
    if any("early queen" in name or "queen" in name for name in known_weakness_names):
        if not queen_moved_early:
            improved.append("early_queen")
        else:
            still_weak.append("early_queen")
    elif queen_moved_early:
        still_weak.append("early_queen")
    
    # Check for blunders when winning (overconfidence)
    winning_blunders = 0
    
    # Build eval lookup by move SAN
    eval_by_san = {ev.get("move", ""): ev for ev in evaluations if ev.get("move")}
    
    for i, move in enumerate(move_history):
        move_san = move.get("move", "")
        
        # Determine if this is user's move
        is_white_move = (i % 2 == 0)
        is_user_move = (is_white_move and user_color == "white") or (not is_white_move and user_color == "black")
        
        if not is_user_move:
            continue
        
        # Get evaluation
        eval_before = 0
        eval_after = 0
        
        if move_san in eval_by_san:
            ev = eval_by_san[move_san]
            eval_before = ev.get("eval_before") or 0
            eval_after = ev.get("eval_after") or 0
        elif move.get("eval_before") is not None:
            eval_before = move.get("eval_before") or 0
            eval_after = move.get("eval_after") or 0
        
        if eval_before == 0 and eval_after == 0:
            continue
        
        # Evals are already from user's perspective
        # For user's advantage: positive eval is good
        user_advantage_before = eval_before
        user_advantage_after = eval_after
        
        # Was user winning (>1.5) but made a big mistake (lost >1.5)?
        if user_advantage_before > 1.5 and (user_advantage_before - user_advantage_after) > 1.5:
            winning_blunders += 1
    
    if winning_blunders > 0:
        violations.append(HabitViolation(
            habit_type=HabitType.OVERCONFIDENCE,
            move_number=0,
            description=f"Made {winning_blunders} big mistake(s) while winning. Stay focused when ahead!"
        ))
        
        if any("overconfidence" in name or "winning" in name for name in known_weakness_names):
            still_weak.append("overconfidence")
        else:
            still_weak.append("overconfidence")
    elif any("overconfidence" in name for name in known_weakness_names):
        improved.append("overconfidence")
    
    # Check for one-move blunders
    one_move_blunders = 0
    for move in move_history:
        if move.get("by") == "player" and move.get("missed_threat"):
            one_move_blunders += 1
            violations.append(HabitViolation(
                habit_type=HabitType.ONE_MOVE_BLUNDER,
                move_number=move.get("move_number", 0),
                description="Missed an immediate threat from opponent"
            ))
    
    if one_move_blunders == 0 and any("one move" in name or "blunder" in name for name in known_weakness_names):
        improved.append("one_move_blunder")
    elif one_move_blunders > 0:
        still_weak.append("one_move_blunder")
    
    # Check time management
    if time_controls:
        fast_moves = sum(1 for t in time_controls.values() if t < 3)
        if fast_moves > 5:
            violations.append(HabitViolation(
                habit_type=HabitType.IMPATIENCE,
                move_number=0,
                description=f"Made {fast_moves} moves in under 3 seconds each. Slow down!"
            ))
            still_weak.append("impatience")
        elif any("impatience" in name or "time" in name for name in known_weakness_names):
            improved.append("impatience")
    
    return violations, improved, still_weak


async def _analyze_mistakes(
    move_history: List[Dict],
    evaluations: List[Dict],
    user_color: str
) -> List[MistakeAnalysis]:
    """Analyze all mistakes in the game using stored evaluations."""
    mistakes = []
    
    # Build evaluation lookup by actual move SAN
    eval_by_move = {}
    for ev in evaluations:
        move_san = ev.get("move", "")
        eval_by_move[move_san] = ev
    
    # Check each move in history
    player_move_count = 0
    for i, move in enumerate(move_history):
        move_san = move.get("move", "")
        
        # Determine if this is user's move based on position in game and user color
        # In a standard game: move 0 = White, move 1 = Black, move 2 = White, etc.
        is_white_move = (i % 2 == 0)
        is_user_move = (is_white_move and user_color == "white") or (not is_white_move and user_color == "black")
        
        if not is_user_move:
            continue
        
        player_move_count += 1
        
        # Get evaluation data
        eval_before = 0
        eval_after = 0
        best_move = None
        
        # First try direct lookup by move SAN
        if move_san in eval_by_move:
            ev = eval_by_move[move_san]
            eval_before = ev.get("eval_before") or 0
            eval_after = ev.get("eval_after") or 0
            best_move = ev.get("best_move")
        # Fallback to move_history eval data
        elif move.get("eval_before") is not None:
            eval_before = move.get("eval_before") or 0
            eval_after = move.get("eval_after") or 0
            best_move = move.get("best_move")
        
        if eval_before == 0 and eval_after == 0:
            continue
        
        # Calculate eval change FROM USER'S PERSPECTIVE
        # The stored evals are ALREADY from user's perspective (due to flip in coach_commentary)
        # So for both colors: negative change = lost advantage
        eval_change = eval_after - eval_before
        
        # Classify mistake (eval_change < 0 means user lost advantage)
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
            continue
        
        mistakes.append(MistakeAnalysis(
            move_number=player_move_count,
            move_played=move_san,
            mistake_type=mistake_type,
            severity=severity,
            explanation=explanation,
            better_move=best_move,
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
    """Calculate estimated performance rating."""
    
    user_moves = len([m for m in move_history if m.get("by") == "player"])
    if user_moves == 0:
        user_moves = 1
    
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    mistake_count = len([m for m in mistakes if m.mistake_type == MistakeType.MISTAKE])
    inaccuracies = len([m for m in mistakes if m.mistake_type == MistakeType.INACCURACY])
    
    error_rate = (blunders * 3 + mistake_count * 2 + inaccuracies) / user_moves
    
    rating_adjustment = int((0.1 - error_rate) * 1000)
    rating_adjustment = max(-400, min(300, rating_adjustment))
    
    estimated = user_rating + rating_adjustment
    
    if game_result == "win":
        estimated += 50
    elif game_result == "loss":
        estimated -= 50
    
    if user_moves >= 30:
        confidence = "high"
    elif user_moves >= 15:
        confidence = "medium"
    else:
        confidence = "low"
    
    diff = estimated - user_rating
    if diff > 100:
        comparison = "above"
    elif diff < -100:
        comparison = "below"
    else:
        comparison = "at"
    
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


def _generate_recommendations(
    mistakes: List[MistakeAnalysis],
    habit_violations: List[HabitViolation],
    habits_weak: List[str],
    perf_rating: PerformanceRating,
    known_weaknesses: List[Dict]
) -> Tuple[str, List[str]]:
    """Generate personalized recommendations based on memory."""
    
    suggestions = []
    priority = "general_improvement"
    
    blunders = [m for m in mistakes if m.mistake_type == MistakeType.BLUNDER]
    
    # Check for recurring weaknesses first (memory-based)
    recurring = [w for w in known_weaknesses if w.get("count", 0) >= 3]
    if recurring:
        worst = max(recurring, key=lambda w: w.get("count", 0))
        priority = f"fixing_{worst.get('name', 'habit').replace(' ', '_').lower()}"
        suggestions.append(f"Priority: Fix '{worst.get('name')}' - it's appeared {worst.get('count')} times")
    
    if len(blunders) >= 2:
        priority = "reducing_blunders"
        suggestions.append("Practice tactics puzzles for 15 minutes daily")
        suggestions.append("Before each move, ask: 'What is my opponent threatening?'")
    
    if "early_queen" in habits_weak:
        suggestions.append("Focus on developing knights and bishops before the queen")
    
    if "impatience" in habits_weak:
        suggestions.append("Set a rule: spend at least 10 seconds on each move")
        if priority == "general_improvement":
            priority = "time_management"
    
    if "overconfidence" in habits_weak:
        suggestions.append("When ahead, ask yourself: 'What could go wrong?'")
    
    if "one_move_blunder" in habits_weak:
        suggestions.append("Practice 'blunder check' - verify your move doesn't hang a piece")
    
    if perf_rating.comparison_to_actual == "below":
        suggestions.append("Consider playing longer time controls to improve accuracy")
    
    if not suggestions:
        suggestions = [
            "Good game! Keep practicing to maintain consistency",
            "Try analyzing your games to find patterns in your play"
        ]
    
    return priority, suggestions[:4]


def _generate_personalized_summary(
    game_result: str,
    perf_rating: PerformanceRating,
    mistakes: List[MistakeAnalysis],
    habits_improved: List[str],
    user_rating: int,
    memory_insights: List[MemoryInsight],
    games_together: int,
    is_overall_improving: bool
) -> Tuple[str, str]:
    """Generate personalized summary using memory insights."""
    
    blunders = len([m for m in mistakes if m.mistake_type == MistakeType.BLUNDER])
    
    # Build summary
    summary_parts = []
    
    # Performance comparison
    if perf_rating.comparison_to_actual == "above":
        summary_parts.append(f"You played like a {perf_rating.estimated_rating} player today - above your {user_rating} rating!")
    elif perf_rating.comparison_to_actual == "below":
        summary_parts.append(f"This was a bit below your usual level ({perf_rating.estimated_rating} vs {user_rating}).")
    else:
        summary_parts.append(f"Solid performance at your level ({perf_rating.estimated_rating}).")
    
    # Blunder comment
    if blunders == 0:
        summary_parts.append("No blunders - excellent discipline!")
    elif blunders == 1:
        summary_parts.append("One blunder to learn from.")
    else:
        summary_parts.append(f"{blunders} blunders to work on.")
    
    # Add memory insight if available
    for insight in memory_insights:
        if insight.insight_type == "recurring_pattern":
            summary_parts.append(insight.message)
            break
        elif insight.insight_type == "improvement":
            summary_parts.append(insight.message)
            break
    
    # Habits improved
    if habits_improved:
        habit_names = {
            "early_queen": "early queen moves",
            "impatience": "rushing",
            "overconfidence": "overconfidence",
            "one_move_blunder": "one-move blunders"
        }
        improved_text = ", ".join(habit_names.get(h, h.replace("_", " ")) for h in habits_improved)
        summary_parts.append(f"Good news: you avoided {improved_text} this game!")
    
    summary = " ".join(summary_parts[:4])
    
    # Generate encouragement based on context
    if game_result == "win":
        if is_overall_improving:
            encouragement = "You're on an upward trend! Keep this momentum going."
        elif perf_rating.comparison_to_actual == "above":
            encouragement = "Brilliant game! This is your true potential."
        else:
            encouragement = "A win is a win! Nice job closing out the game."
    elif game_result == "loss":
        if blunders > 0:
            encouragement = "Losses are lessons. Let's review those blunders and turn them into wins."
        else:
            encouragement = "Close game! You played well but chess is tough. Keep grinding!"
    else:
        if games_together >= 5:
            encouragement = "Solid draw. I'm watching your patterns - you're getting more consistent."
        else:
            encouragement = "A solid draw. Every game teaches something."
    
    return summary, encouragement


async def _suggest_opening(
    db,
    user_id: str,
    move_history: List[Dict],
    user_color: str
) -> Optional[str]:
    """Suggest an opening to learn based on game and history."""
    try:
        from services.opening_mastery import detect_opening_from_moves, OPENING_DATABASE
        
        moves = [m.get("move", "") for m in move_history if m.get("move")]
        opening_info = detect_opening_from_moves(moves[:10])
        
        if opening_info:
            opening_key = opening_info.get("opening_key")
            opening = OPENING_DATABASE.get(opening_key)
            if opening and opening.variations:
                progress = await db.user_opening_progress.find_one({
                    "user_id": user_id,
                    "opening_name": opening.name
                })
                
                if not progress or progress.get("mastery_level") in ["unknown", "introduced"]:
                    return f"Learn the {opening.name} - you played it but may not know the key ideas!"
    except Exception as e:
        logger.warning(f"Opening suggestion error: {e}")
    
    return None


def _calculate_accuracy(mistakes: List[MistakeAnalysis], total_moves: int) -> float:
    """
    Calculate accuracy percentage based on centipawn loss.
    
    This mimics chess.com/lichess accuracy calculation:
    - Perfect play = 100%
    - Average centipawn loss determines accuracy
    - Blunders heavily penalize accuracy
    """
    if total_moves == 0:
        return 100.0
    
    # Calculate total centipawn loss
    total_cp_loss = 0
    for m in mistakes:
        # eval_change is negative for mistakes, so negate it
        cp_loss = abs(m.evaluation_change) * 100  # Convert to centipawns
        total_cp_loss += cp_loss
    
    # Average centipawn loss per move
    avg_cp_loss = total_cp_loss / total_moves
    
    # Convert to accuracy using a formula similar to chess.com
    # 0 cp loss = 100%, 50 avg cp loss ≈ 80%, 100 avg cp loss ≈ 60%
    # Formula: accuracy = 103.1668 * exp(-0.04354 * avg_cp_loss) - 3.1669
    # Simplified version:
    if avg_cp_loss <= 0:
        accuracy = 100.0
    elif avg_cp_loss < 10:
        accuracy = 100 - (avg_cp_loss * 0.5)  # 95-100%
    elif avg_cp_loss < 25:
        accuracy = 95 - ((avg_cp_loss - 10) * 1.0)  # 80-95%
    elif avg_cp_loss < 50:
        accuracy = 80 - ((avg_cp_loss - 25) * 0.8)  # 60-80%
    elif avg_cp_loss < 100:
        accuracy = 60 - ((avg_cp_loss - 50) * 0.4)  # 40-60%
    else:
        accuracy = max(20, 40 - ((avg_cp_loss - 100) * 0.2))  # 20-40%
    
    return round(max(0, min(100, accuracy)), 1)


def _pick_prescription(
    mistakes: List[MistakeAnalysis],
    habit_violations: List,
    game_result: str,
    endgame_type: Optional[str],
    endgame_lesson_needed: Optional[str],
    user_rating: int,
    current_focus: Optional[str] = None,
    phase_analysis: Optional[Dict] = None,
    opening_to_learn: Optional[str] = None,
    opening_played: Optional[str] = None,
) -> tuple:
    """
    The curriculum brain. Looks at everything that happened in one game
    and picks THE ONE THING the student should work on next.

    Priority order (what a human coach would do):
    1. Failed endgame conversion → prescribe the endgame lesson
    2. Opening disaster (lost in the opening) → prescribe opening lesson or trap
    3. Hanging pieces (most common, most costly for beginners)
    4. Missed fork/pin/skewer (tactical pattern)
    5. King safety error
    6. Positional drift (least urgent)

    Graduation: if the student had a current_focus and this game was clean
    for that focus (no violations of that pattern), keep the focus so the
    clean streak counter increments. After 3 clean games, the focus will
    naturally shift when the pattern becomes FADING in the decay model.

    Returns (prescription, type, reason) or (None, None, None) for clean games.
    """
    try:
        from mistake_classifier import MistakeType
    except ImportError:
        return None, None, None

    # === 1. Failed endgame conversion → prescribe endgame lesson ===
    if endgame_lesson_needed and game_result != "win":
        return (
            endgame_lesson_needed.lower().replace(" ", "_"),
            "endgame_lesson",
            f"You reached a {endgame_type} endgame but couldn't convert. Let's practice this technique."
        )

    # === 1.5. Opening disaster → prescribe opening lesson or trap ===
    # If the student lost and the opening phase was bad, teach the opening.
    # Check if there's a relevant trap they should know.
    if game_result == "loss" and phase_analysis:
        opening_phase = phase_analysis.get("opening", {})
        opening_blunders = opening_phase.get("blunders", 0)
        opening_mistakes = opening_phase.get("mistakes", 0)
        opening_verdict = (opening_phase.get("verdict") or "").lower()

        # If 2+ blunders in opening or verdict says it was bad
        if opening_blunders >= 2 or "poor" in opening_verdict or "bad" in opening_verdict:
            # Check if there's a trap for this opening they should learn
            if opening_played:
                try:
                    from services.trap_library import TRAP_LIBRARY
                    # Normalize opening key (e.g., "italian_game" -> "italian-game")
                    trap_key = opening_played.lower().replace("_", "-").replace(" ", "-")
                    traps = TRAP_LIBRARY.get(trap_key, [])
                    if traps:
                        trap_name = traps[0]["name"]
                        return (
                            f"trap:{trap_key}:{trap_name.lower().replace(' ', '_')}",
                            "trap_lesson",
                            f"You lost in the opening. Learn the {trap_name} — it's a common pattern in the {opening_played.replace('_', ' ').replace('-', ' ').title()}."
                        )
                except Exception:
                    pass

            # No trap available — prescribe the opening itself
            if opening_to_learn:
                return (
                    f"opening:{opening_played or 'general'}",
                    "opening_lesson",
                    opening_to_learn,
                )
            elif opening_played:
                return (
                    f"opening:{opening_played}",
                    "opening_lesson",
                    f"You struggled in the {opening_played.replace('_', ' ').replace('-', ' ').title()} opening. Let's study the key ideas."
                )

    # === 2. Count mistake types and find the costliest ===
    # Map MistakeType enum values to prescription keys
    MISTAKE_TYPE_MAP = {
        "hanging_piece": "hanging_piece",
        "material_blunder": "hanging_piece",
        "missed_fork": "missed_fork",
        "missed_pin": "missed_pin",
        "missed_skewer": "missed_skewer",
        "missed_discovered_attack": "missed_discovery",
        "missed_overloaded_defender": "missed_overload",
        "walked_into_fork": "missed_fork",  # Walked into = needs to learn this pattern
        "walked_into_pin": "missed_pin",
        "walked_into_skewer": "missed_skewer",
        "king_safety_error": "king_safety",
        "ignored_threat": "hanging_piece",
        "missed_winning_tactic": "tactical_error",
        "blunder_when_ahead": "tactical_error",
        "failed_conversion": "tactical_error",
    }

    mistake_counts = {}
    total_cp_by_type = {}
    for m in mistakes:
        severity = getattr(m, 'severity', '') or ''
        cp_loss = abs(getattr(m, 'evaluation_change', 0) or 0)
        mtype = None

        # 1. Try the structured mistake_type field first (most reliable)
        mt = getattr(m, 'mistake_type', None)
        if mt:
            mt_value = mt.value if hasattr(mt, 'value') else str(mt)
            mtype = MISTAKE_TYPE_MAP.get(mt_value)

        # 2. Fall back to explanation text if no structured type
        if not mtype:
            explanation = (getattr(m, 'explanation', '') or '').lower()
            if 'hang' in explanation or 'undefended' in explanation:
                mtype = 'hanging_piece'
            elif 'fork' in explanation:
                mtype = 'missed_fork'
            elif 'pin' in explanation:
                mtype = 'missed_pin'
            elif 'skewer' in explanation:
                mtype = 'missed_skewer'
            elif 'king' in explanation and 'safe' in explanation:
                mtype = 'king_safety'

        # 3. Last resort: severity-based
        if not mtype and severity in ('blunder', 'mistake'):
            mtype = 'tactical_error'

        if mtype:
            mistake_counts[mtype] = mistake_counts.get(mtype, 0) + 1
            total_cp_by_type[mtype] = total_cp_by_type.get(mtype, 0) + cp_loss

    # Also count from habit violations
    for hv in habit_violations:
        htype = getattr(hv, 'habit_type', None)
        if htype:
            htype_str = htype.value if hasattr(htype, 'value') else str(htype)
            if 'hanging' in htype_str.lower() or 'piece_safety' in htype_str.lower():
                mistake_counts['hanging_piece'] = mistake_counts.get('hanging_piece', 0) + 1
            elif 'one_move' in htype_str.lower():
                mistake_counts['tactical_error'] = mistake_counts.get('tactical_error', 0) + 1

    if not mistake_counts:
        # Clean game — no prescription needed
        # But if student had a focus, keep it so clean streak grows
        if current_focus:
            return (
                current_focus,
                "pattern_drill",
                "Clean game for this pattern! Keep it up."
            )
        return None, None, None

    # === 3. Graduation check ===
    # If the student has a current focus and this game was CLEAN for that focus,
    # keep the same focus (the pattern_decay_service will graduate them when
    # the pattern becomes FADING after enough clean games).
    # But if the focus WAS violated this game, it stays ACTIVE — no graduation.
    if current_focus and current_focus not in mistake_counts:
        # Clean for current focus — keep it, don't switch topics
        return (
            current_focus,
            "pattern_drill",
            "You avoided this pattern! Keep practicing."
        )

    # === 4. Pick the most impactful mistake type ===
    # Priority order for beginners (under 1200): hanging > forks > pins > king safety > general
    # For higher ratings: whatever cost the most centipawns
    priority_order = [
        'hanging_piece', 'missed_fork', 'missed_pin', 'missed_skewer',
        'king_safety', 'tactical_error',
    ]

    if user_rating < 1200:
        # For beginners: follow priority order strictly
        for mtype in priority_order:
            if mistake_counts.get(mtype, 0) >= 1:
                count = mistake_counts[mtype]
                return (
                    mtype,
                    "pattern_drill",
                    f"This happened {count} time{'s' if count > 1 else ''} this game. Let's work on it."
                )
    else:
        # For higher-rated: pick by total centipawn loss
        if total_cp_by_type:
            worst = max(total_cp_by_type.keys(), key=lambda k: total_cp_by_type[k])
            count = mistake_counts[worst]
            cp = total_cp_by_type[worst]
            return (
                worst,
                "pattern_drill",
                f"Cost you {cp:.0f} centipawns across {count} occurrence{'s' if count > 1 else ''}."
            )

    # Fallback: most frequent mistake
    worst = max(mistake_counts.keys(), key=lambda k: mistake_counts[k])
    count = mistake_counts[worst]
    return (
        worst,
        "pattern_drill",
        f"Happened {count} time{'s' if count > 1 else ''} this game."
    )


async def _save_analysis(db, analysis: PostGameAnalysis):
    """Save analysis to database."""
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
        "memory_insights": [asdict(i) for i in analysis.memory_insights],
        "games_together": analysis.games_together,
        "created_at": datetime.now(timezone.utc),
        # Curriculum brain
        "endgame_type": analysis.endgame_type,
        "endgame_lesson_needed": analysis.endgame_lesson_needed,
        "coach_prescription": analysis.coach_prescription,
        "prescription_type": analysis.prescription_type,
        "prescription_reason": analysis.prescription_reason,
    }
    
    await db.postgame_analyses.update_one(
        {"session_id": analysis.session_id},
        {"$set": doc},
        upsert=True
    )


async def _update_coach_memory_after_game(
    db,
    user_id: str,
    game_result: str,
    accuracy: float,
    blunders: int,
    mistakes: int,
    habit_violations: List[HabitViolation],
    habits_improved: List[str],
    move_history: List[Dict],
    performance_rating: int,
    coach_prescription: Optional[str] = None,
    prescription_type: Optional[str] = None,
):
    """
    Update coach memory after game analysis.
    
    This is CRITICAL for making the coach remember patterns across games.
    Now also updates the NEW PlayerIdentity system for deep memory.
    """
    # Extract habit IDs that were violated
    habits_violated = [v.habit_type.value for v in habit_violations]
    
    # Check if opening was played
    opening_played = None
    try:
        from services.opening_mastery import detect_opening_from_moves
        moves = [m.get("move", "") for m in move_history if m.get("move")]
        opening_info = detect_opening_from_moves(moves[:10])
        if opening_info:
            opening_played = opening_info.get("opening_name")
    except:
        pass
    
    # Check if endgame was reached (roughly, if game went >40 moves and few pieces left)
    endgame_reached = len(move_history) > 80  # 40 moves each side
    
    # Call the LEGACY coach memory update function
    await update_memory_after_game(
        db=db,
        user_id=user_id,
        game_result=game_result,
        accuracy=accuracy,
        blunders=blunders,
        mistakes=mistakes,
        habits_violated=habits_violated,
        habits_improved=habits_improved,
        opening_played=opening_played,
        endgame_reached=endgame_reached,
        performance_rating=performance_rating,
        coach_prescription=coach_prescription,
        prescription_type=prescription_type,
    )
    
    # === NEW: Update PlayerIdentity system for deep memory ===
    try:
        from services.player_identity import record_game_to_memory
        
        # Build moves analysis for the new system
        moves_analysis = []
        for i, m in enumerate(move_history):
            if m.get("by") == "player":  # Only user moves
                moves_analysis.append({
                    "move_number": m.get("move_number", i // 2 + 1),
                    "move": m.get("move", ""),
                    "fen_before": m.get("fen_before", ""),
                    "best_move": m.get("best_move", ""),
                    "cp_loss": m.get("cp_loss", 0),
                    "eval_before": m.get("eval_before", 0),
                    "time_spent": m.get("time_spent", 10),
                    "time_remaining": m.get("time_remaining", 300)
                })
        
        # Determine user color
        user_color = "white"  # Default
        if move_history and len(move_history) > 0:
            first_player_move = next((m for m in move_history if m.get("by") == "player"), None)
            if first_player_move:
                first_player_move.get("move_number", 1)
                # If first player move has even index in history, they're black
                idx = move_history.index(first_player_move)
                user_color = "white" if idx % 2 == 0 else "black"
        
        # Game phases estimation
        total_moves = len(move_history)
        game_phases = {
            "opening": min(20, total_moves // 4),
            "middlegame": min(50, total_moves // 2),
            "endgame": max(0, total_moves - 70)
        }
        
        await record_game_to_memory(
            db=db,
            user_id=user_id,
            game_id=f"game_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            game_result=game_result,
            user_color=user_color,
            opponent="Coach",
            moves_analysis=moves_analysis,
            opening_played=opening_played,
            game_phases=game_phases,
            rating_after=performance_rating
        )
        logger.info(f"PlayerIdentity updated for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to update PlayerIdentity: {e}")
    
    logger.info(f"Coach memory updated for user {user_id}: result={game_result}, blunders={blunders}, habits_violated={habits_violated}")
