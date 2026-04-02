"""
Mistake-Free Streak Service - P0: Carry-Forward + Behavioral Proof

Tracks games without the user's specific focus mistake.
This is NOT gamification - it's proof of behavior change.

Key Rules:
- Streak tied to ONE focus mistake (not generic)
- Strict detection (Stockfish + rule-based, no fake wins)
- Soft reset (current → 0, best stays)
- Minimum 15 moves OR tactical opportunity to count
- Compensation check (recovery within 2 plies = ignore)

Data Model:
{
    current_focus_mistake: "THREAT_VERIFICATION",
    mistake_streak: {
        current: 3,           # Games without focus mistake
        best: 7,              # Personal best
        last_game_had_mistake: false,
        streak_started_at: "2026-03-21"
    },
    last_5_games: [
        { game_id: "...", had_mistake: true/false, mistake_count: 3 }
    ],
    mistake_trend: {
        before_avg: 6.2,      # Avg mistakes/game before training
        recent_avg: 2.1,      # Last 5 games
        improvement_pct: 66   # % improvement
    }
}

NO LLM. NO RAG. Fully deterministic.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Minimum game quality for streak counting
MIN_GAME_MOVES = 15

# Eval thresholds (centipawns)
CP_LOSS_MISTAKE = 200         # Significant mistake threshold
CP_LOSS_COMPENSATION = 100    # Recovery threshold (within 2 plies)
CP_LOSS_TACTICAL_OPP = 100    # Minimum eval swing for "tactical opportunity existed"

# Piece values for hanging piece detection
PIECE_VALUES = {
    "p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0
}

# Focus mistake types (maps to lesson keys from focus_lock_service)
FOCUS_MISTAKE_TYPES = {
    "THREAT_VERIFICATION": {
        "name": "Threat Awareness",
        "short_name": "Threats",
        "description": "You miss opponent's threats",
        "rule": "Before EVERY move, ask: What is my opponent threatening?"
    },
    "FORCING_BLIND": {
        "name": "Forcing Move Blindness", 
        "short_name": "Forcing",
        "description": "You miss forcing moves (checks, captures, threats)",
        "rule": "Before EVERY move, check: Is there a check, capture, or threat?"
    },
    "STOPPED_CALCULATION_EARLY": {
        "name": "Shallow Calculation",
        "short_name": "Calculation",
        "description": "You stop calculating too early",
        "rule": "At critical moments, calculate ONE move deeper."
    },
    "HANGING_PIECE": {
        "name": "Hanging Pieces",
        "short_name": "Hanging",
        "description": "You leave pieces undefended",
        "rule": "Before EVERY move, ask: Is my piece safe after this?"
    },
    "TACTICAL_MISS": {
        "name": "Tactical Blindness",
        "short_name": "Tactics",
        "description": "You miss winning tactics",
        "rule": "Before EVERY move, check: Is there a tactic here?"
    }
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class GameStreakData:
    """Streak-relevant data for a single game."""
    game_id: str
    had_focus_mistake: bool
    focus_mistake_count: int
    total_moves: int
    is_valid_for_streak: bool
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "had_mistake": self.had_focus_mistake,
            "mistake_count": self.focus_mistake_count,
            "total_moves": self.total_moves,
            "is_valid": self.is_valid_for_streak,
            "detected_at": self.detected_at.isoformat()
        }


@dataclass
class MistakeStreak:
    """Current streak state for a user."""
    current: int = 0
    best: int = 0
    last_game_had_mistake: bool = False
    streak_started_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": self.current,
            "best": self.best,
            "last_game_had_mistake": self.last_game_had_mistake,
            "streak_started_at": self.streak_started_at.isoformat() if self.streak_started_at else None
        }


@dataclass
class MistakeTrend:
    """Improvement trend tracking."""
    before_avg: Optional[float] = None  # Baseline avg mistakes/game
    recent_avg: Optional[float] = None  # Last 5 games avg
    improvement_pct: Optional[int] = None
    baseline_locked: bool = False  # True after first 5 games
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_avg": round(self.before_avg, 2) if self.before_avg else None,
            "recent_avg": round(self.recent_avg, 2) if self.recent_avg else None,
            "improvement_pct": self.improvement_pct,
            "baseline_locked": self.baseline_locked
        }


@dataclass  
class UserStreakState:
    """Complete streak state for a user."""
    current_focus_mistake: str  # e.g., "THREAT_VERIFICATION"
    streak: MistakeStreak
    trend: MistakeTrend
    last_5_games: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        focus_info = FOCUS_MISTAKE_TYPES.get(self.current_focus_mistake, {})
        return {
            "current_focus_mistake": self.current_focus_mistake,
            "focus_mistake_name": focus_info.get("name", self.current_focus_mistake),
            "focus_mistake_rule": focus_info.get("rule", ""),
            "streak": self.streak.to_dict(),
            "trend": self.trend.to_dict(),
            "last_5_games": self.last_5_games
        }


# =============================================================================
# EVAL NORMALIZATION (Production-safe with mate handling)
# =============================================================================

def normalize_eval(eval_value: Any, user_color: str) -> int:
    """
    Normalize evaluation to user's perspective.
    Handles both centipawn scores and mate scores.
    
    Args:
        eval_value: Raw eval (int for cp, or dict with 'mate_in')
        user_color: "white" or "black"
    
    Returns:
        Normalized centipawn value (positive = good for user)
    """
    if eval_value is None:
        return 0
    
    # Handle mate scores (stored as large values or dict)
    if isinstance(eval_value, dict):
        mate_in = eval_value.get("mate_in")
        if mate_in is not None:
            # Positive mate = white wins, negative = black wins
            val = 10000 if mate_in > 0 else -10000
        else:
            val = eval_value.get("cp", 0)
    elif abs(eval_value) >= 9000:
        # Already a mate score in centipawn form
        val = eval_value
    else:
        val = eval_value
    
    # Normalize to user perspective
    if user_color == "black":
        val = -val
    
    return val


# =============================================================================
# GAME VALIDITY CHECK
# =============================================================================

def is_valid_game_for_streak(
    move_evaluations: List[Dict],
    total_moves: int,
    user_color: str
) -> bool:
    """
    Check if game is valid for streak counting.
    
    Rules:
    1. Minimum 15 moves played
    2. OR at least one tactical opportunity existed (eval swing >= 100)
    
    Prevents fake streak inflation from:
    - Very short games
    - "Nothing happened" games
    """
    # Rule 1: Minimum moves
    if total_moves >= MIN_GAME_MOVES:
        return True
    
    # Rule 2: Check for tactical opportunities
    for move in move_evaluations:
        if not move.get("is_user_move"):
            continue
        
        cp_loss = abs(move.get("cp_loss", 0))
        eval_swing = abs(move.get("eval_swing", 0))
        
        # If there was any significant tactical opportunity, game is valid
        if cp_loss >= CP_LOSS_TACTICAL_OPP or eval_swing >= CP_LOSS_TACTICAL_OPP:
            return True
    
    # No tactical content and too short
    logger.info(f"Game rejected for streak: {total_moves} moves, no tactical opportunities")
    return False


# =============================================================================
# FOCUS MISTAKE DETECTION
# =============================================================================

def detect_focus_mistake(
    move_evaluations: List[Dict],
    focus_type: str,
    user_color: str
) -> GameStreakData:
    """
    Detect if user committed their focus mistake in this game.
    
    Uses strict Stockfish-based detection with compensation check.
    
    Returns:
        GameStreakData with detection results
    """
    focus_mistakes_found = 0
    total_user_moves = 0
    
    for i, move in enumerate(move_evaluations):
        if not move.get("is_user_move"):
            continue
        
        total_user_moves += 1
        
        # Get move data
        cp_loss = abs(move.get("cp_loss", 0))
        
        # Skip if not a significant mistake
        if cp_loss < CP_LOSS_MISTAKE:
            continue
        
        # Check for compensation (recovery within next 2 plies)
        if _check_compensation(move_evaluations, i, user_color):
            logger.debug(f"Move {move.get('move_number')} compensated, ignoring")
            continue
        
        # Detect based on focus type
        is_focus_mistake = False
        
        if focus_type == "THREAT_VERIFICATION":
            is_focus_mistake = _is_threat_miss(move)
        elif focus_type == "FORCING_BLIND":
            is_focus_mistake = _is_forcing_miss(move)
        elif focus_type == "STOPPED_CALCULATION_EARLY":
            is_focus_mistake = _is_calculation_error(move)
        elif focus_type == "HANGING_PIECE":
            is_focus_mistake = _is_hanging_piece(move)
        elif focus_type == "TACTICAL_MISS":
            is_focus_mistake = _is_tactical_miss(move)
        else:
            # Generic: any significant blunder counts
            is_focus_mistake = cp_loss >= CP_LOSS_MISTAKE
        
        if is_focus_mistake:
            focus_mistakes_found += 1
            logger.info(f"Focus mistake detected at move {move.get('move_number')}: {focus_type}, cp_loss={cp_loss}")
    
    # Check game validity
    is_valid = is_valid_game_for_streak(move_evaluations, total_user_moves * 2, user_color)
    
    return GameStreakData(
        game_id="",  # Will be set by caller
        had_focus_mistake=focus_mistakes_found > 0,
        focus_mistake_count=focus_mistakes_found,
        total_moves=total_user_moves * 2,
        is_valid_for_streak=is_valid
    )


def _check_compensation(
    move_evaluations: List[Dict],
    current_index: int,
    user_color: str
) -> bool:
    """
    Check if player recovered within next 2 plies.
    
    If eval recovers within 100cp of position before mistake,
    it's considered compensated (opponent blundered back).
    """
    if current_index >= len(move_evaluations) - 2:
        return False  # Not enough moves to check
    
    current_move = move_evaluations[current_index]
    eval_before = normalize_eval(current_move.get("eval_before", 0), user_color)
    
    # Check next 2 moves for recovery
    for offset in [1, 2]:
        if current_index + offset >= len(move_evaluations):
            break
        
        future_move = move_evaluations[current_index + offset]
        future_eval = normalize_eval(future_move.get("eval_after", 0), user_color)
        
        # If eval recovered close to original position
        if abs(future_eval - eval_before) < CP_LOSS_COMPENSATION:
            return True
    
    return False


def _is_threat_miss(move: Dict) -> bool:
    """
    Detect THREAT_VERIFICATION mistake (missed opponent threat).
    
    Indicators:
    - Opponent's reply was check, capture, or fork
    - Player didn't address the threat
    - Significant material or positional loss
    """
    threat = move.get("threat_after_played", "").lower()
    opponent_reply = move.get("opponent_best_reply", {})
    
    # Check for immediate threats
    reply_is_check = opponent_reply.get("gives_check", False)
    reply_is_capture = opponent_reply.get("is_capture", False)
    reply_material = opponent_reply.get("material_gain", 0)
    
    # Also check threat description
    threat_indicators = ["check", "capture", "fork", "pin", "hanging", "undefended", "mate"]
    has_threat_indicator = any(ind in threat for ind in threat_indicators)
    
    return reply_is_check or reply_is_capture or reply_material >= 100 or has_threat_indicator


def _is_forcing_miss(move: Dict) -> bool:
    """
    Detect FORCING_BLIND mistake (missed forcing move).
    
    Indicators:
    - Best move was check, capture, or mate threat
    - Player played something else with significant loss
    """
    best_move_data = move.get("engine_best_move_data", {})
    
    is_check = best_move_data.get("gives_check", False) or move.get("best_gives_check", False)
    is_capture = best_move_data.get("is_capture", False) or move.get("best_is_capture", False)
    mate_in = best_move_data.get("mate_in") or move.get("mate_in_best")
    
    # Best move was forcing but player missed it
    return is_check or is_capture or mate_in is not None


def _is_calculation_error(move: Dict) -> bool:
    """
    Detect STOPPED_CALCULATION_EARLY mistake.
    
    Indicators:
    - Critical position (high eval swing)
    - Player move not in top 2 engine moves
    """
    eval_swing = abs(move.get("eval_swing", 0))
    player_move = move.get("move_uci", "")
    top_moves = move.get("engine_top_moves", [])
    best_move = move.get("engine_best_move", move.get("best_move_uci", ""))
    
    # Get top 2
    top_2 = [best_move]
    if isinstance(top_moves, list) and len(top_moves) >= 2:
        top_2 = [m.get("move", m) if isinstance(m, dict) else m for m in top_moves[:2]]
    
    # Critical position + not in top 2
    return eval_swing >= 150 and player_move not in top_2


def _is_hanging_piece(move: Dict) -> bool:
    """
    Detect hanging piece mistake.
    
    Indicators:
    - Opponent's best reply is capture
    - Material loss without compensation
    - No tactical sequence justifying the "sacrifice"
    """
    opponent_reply = move.get("opponent_best_reply", {})
    threat = move.get("threat_after_played", "").lower()
    
    is_capture = opponent_reply.get("is_capture", False)
    material_gain = opponent_reply.get("material_gain", 0)
    
    # Check threat description for hanging indicators
    hanging_indicators = ["hanging", "undefended", "takes", "wins", "capture"]
    has_hanging = any(ind in threat for ind in hanging_indicators)
    
    return (is_capture and material_gain >= 200) or has_hanging


def _is_tactical_miss(move: Dict) -> bool:
    """
    Detect missed tactic.
    
    Indicators:
    - Best move was winning tactic
    - Significant eval swing available
    """
    best_move_data = move.get("engine_best_move_data", {})
    eval_after_best = move.get("eval_after_best", 0)
    eval_after_played = move.get("eval_after", 0)
    
    # Calculate what was missed
    missed_advantage = eval_after_best - eval_after_played if eval_after_best and eval_after_played else 0
    
    # Was there a winning tactic available?
    mate_in = best_move_data.get("mate_in") or move.get("mate_in_best")
    
    return mate_in is not None or missed_advantage >= 300


# =============================================================================
# STREAK UPDATE LOGIC
# =============================================================================

def update_streak_after_game(
    user_streak_data: Dict[str, Any],
    game_analysis: Dict[str, Any],
    game_id: str,
    user_color: str
) -> Dict[str, Any]:
    """
    Update user's streak state after a game is analyzed.
    
    This is the SAFE update function that:
    1. Validates game quality
    2. Detects focus mistake
    3. Updates streak (current/best)
    4. Updates last_5_games
    5. Updates trend
    
    Args:
        user_streak_data: Current streak state from DB
        game_analysis: Stockfish analysis results
        game_id: Game identifier
        user_color: "white" or "black"
    
    Returns:
        Updated streak state dict
    """
    # Parse current state
    focus_type = user_streak_data.get("current_focus_mistake", "THREAT_VERIFICATION")
    
    streak = MistakeStreak(
        current=user_streak_data.get("mistake_streak", {}).get("current", 0),
        best=user_streak_data.get("mistake_streak", {}).get("best", 0),
        last_game_had_mistake=user_streak_data.get("mistake_streak", {}).get("last_game_had_mistake", False),
        streak_started_at=user_streak_data.get("mistake_streak", {}).get("streak_started_at")
    )
    
    trend = MistakeTrend(
        before_avg=user_streak_data.get("mistake_trend", {}).get("before_avg"),
        recent_avg=user_streak_data.get("mistake_trend", {}).get("recent_avg"),
        improvement_pct=user_streak_data.get("mistake_trend", {}).get("improvement_pct"),
        baseline_locked=user_streak_data.get("mistake_trend", {}).get("baseline_locked", False)
    )
    
    last_5 = user_streak_data.get("last_5_games", [])
    
    # Get move evaluations
    stockfish_data = game_analysis.get("stockfish_analysis", game_analysis)
    move_evals = stockfish_data.get("move_evaluations", [])
    
    if not move_evals:
        logger.warning(f"No move evaluations for game {game_id}, skipping streak update")
        return user_streak_data
    
    # Detect focus mistake
    game_data = detect_focus_mistake(move_evals, focus_type, user_color)
    game_data.game_id = game_id
    
    # Check if game is valid for streak
    if not game_data.is_valid_for_streak:
        logger.info(f"Game {game_id} not valid for streak (too short/no tactical content)")
        # Still record in last_5 but mark as invalid
        last_5.append({**game_data.to_dict(), "skipped": True})
        last_5 = last_5[-5:]  # Keep only last 5
        
        return {
            "current_focus_mistake": focus_type,
            "mistake_streak": streak.to_dict(),
            "mistake_trend": trend.to_dict(),
            "last_5_games": last_5
        }
    
    # Update streak based on result
    if game_data.had_focus_mistake:
        # ❌ STREAK BROKEN
        logger.info(f"Streak broken! Game {game_id} had {game_data.focus_mistake_count} focus mistakes")
        streak.current = 0
        streak.last_game_had_mistake = True
        streak.streak_started_at = None
    else:
        # ✅ STREAK CONTINUES
        streak.current += 1
        streak.last_game_had_mistake = False
        
        if streak.streak_started_at is None:
            streak.streak_started_at = datetime.now(timezone.utc)
        
        # Update best if new record
        if streak.current > streak.best:
            streak.best = streak.current
            logger.info(f"New best streak: {streak.best} games!")
    
    # Update last_5_games
    last_5.append(game_data.to_dict())
    last_5 = last_5[-5:]  # Keep only last 5
    
    # Update trend
    trend = _update_trend(trend, last_5)
    
    return {
        "current_focus_mistake": focus_type,
        "mistake_streak": streak.to_dict(),
        "mistake_trend": trend.to_dict(),
        "last_5_games": last_5
    }


def _update_trend(trend: MistakeTrend, last_5: List[Dict]) -> MistakeTrend:
    """
    Update improvement trend based on last 5 games.
    
    Rules:
    1. Baseline locked after first 5 games
    2. Trend only shown after 5 games
    """
    valid_games = [g for g in last_5 if g.get("is_valid", True) and not g.get("skipped", False)]
    
    if len(valid_games) < 5:
        return trend  # Not enough data yet
    
    # Calculate recent average
    mistake_counts = [g.get("mistake_count", 0) for g in valid_games]
    recent_avg = sum(mistake_counts) / len(mistake_counts)
    trend.recent_avg = recent_avg
    
    # Lock baseline if not already
    if not trend.baseline_locked:
        trend.before_avg = recent_avg
        trend.baseline_locked = True
        logger.info(f"Baseline locked at {trend.before_avg:.2f} mistakes/game")
    
    # Calculate improvement
    if trend.before_avg and trend.before_avg > 0:
        improvement = ((trend.before_avg - recent_avg) / trend.before_avg) * 100
        trend.improvement_pct = max(0, int(improvement))  # Don't show negative
    
    return trend


# =============================================================================
# PRE-GAME CARRY-FORWARD DATA
# =============================================================================

def get_pregame_streak_data(user_streak_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get data for pre-game popup (carry-forward pressure).
    
    Returns:
        Dict with streak info and messaging for pre-game display
    """
    focus_type = user_streak_data.get("current_focus_mistake")  # Can be None!
    streak = user_streak_data.get("mistake_streak", {})
    trend = user_streak_data.get("mistake_trend", {})
    
    current = streak.get("current", 0)
    best = streak.get("best", 0)
    last_had_mistake = streak.get("last_game_had_mistake", False)
    
    # Handle case where no focus has been detected yet
    if focus_type is None:
        return {
            "focus_mistake_type": None,
            "focus_mistake_name": None,
            "rule": None,
            "current_streak": 0,
            "best_streak": 0,
            "last_game_had_mistake": False,
            "headline": "No Focus Yet",
            "message": "Play and analyze some games first. We'll detect your biggest weakness.",
            "tone": "needs_detection",
            "needs_detection": True,
            "trend": {
                "before_avg": None,
                "recent_avg": None,
                "improvement_pct": None,
                "show_trend": False
            }
        }
    
    focus_info = FOCUS_MISTAKE_TYPES.get(focus_type, {})
    
    # Generate messaging based on state
    if current == 0 and last_had_mistake:
        # Just broke streak
        headline = "Streak Broken"
        message = "You repeated your core mistake last game. Start fresh."
        tone = "warning"
    elif current == 0:
        # New user or just starting
        headline = "Start Your Streak"
        message = f"Play a game without {focus_info.get('short_name', 'this mistake').lower()} mistakes."
        tone = "neutral"
    elif current >= best and current > 0:
        # On a best streak
        headline = f"🔥 {current}-Game Streak"
        message = "This is your best! Don't break it."
        tone = "success"
    else:
        # Active streak
        headline = f"{current}-Game Streak"
        message = f"Keep going. Best is {best}."
        tone = "active"
    
    return {
        "focus_mistake_type": focus_type,
        "focus_mistake_name": focus_info.get("name", "Focus Mistake"),
        "rule": focus_info.get("rule", ""),
        "current_streak": current,
        "best_streak": best,
        "last_game_had_mistake": last_had_mistake,
        "headline": headline,
        "message": message,
        "tone": tone,
        "needs_detection": False,
        "trend": {
            "before_avg": trend.get("before_avg"),
            "recent_avg": trend.get("recent_avg"),
            "improvement_pct": trend.get("improvement_pct"),
            "show_trend": trend.get("baseline_locked", False)
        }
    }


def get_postgame_streak_result(
    streak_before: Dict[str, Any],
    streak_after: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get messaging for post-game streak display.
    
    Compares before/after to generate appropriate celebration or break message.
    """
    focus_type = streak_after.get("current_focus_mistake", "THREAT_VERIFICATION")
    focus_info = FOCUS_MISTAKE_TYPES.get(focus_type, {})
    
    before = streak_before.get("mistake_streak", {})
    after = streak_after.get("mistake_streak", {})
    
    current_before = before.get("current", 0)
    current_after = after.get("current", 0)
    best_after = after.get("best", 0)
    
    if current_after > current_before:
        # Streak continued
        if current_after > before.get("best", 0):
            # New best!
            return {
                "result": "new_best",
                "headline": f"🔥 New Best: {current_after} Games!",
                "message": f"You've never gone this long without {focus_info.get('short_name', 'this').lower()} mistakes.",
                "streak": current_after,
                "best": best_after,
                "tone": "celebration"
            }
        else:
            return {
                "result": "continued",
                "headline": f"✅ Streak: {current_after} Games",
                "message": "Clean game. Keep it up!",
                "streak": current_after,
                "best": best_after,
                "tone": "success"
            }
    else:
        # Streak broken
        return {
            "result": "broken",
            "headline": f"❌ Streak Broken at {current_before}",
            "message": "You repeated your core mistake. Start fresh.",
            "streak": 0,
            "best": best_after,
            "previous_streak": current_before,
            "tone": "warning"
        }


# =============================================================================
# BACKEND ANALYSIS INTEGRATION (Phase 8)
# Called by analysis_worker.py after Stockfish analysis completes
# =============================================================================

def update_streak_from_analysis(
    db,
    user_id: str,
    game_id: str,
    move_evaluations: List[Dict],
    user_color: str,
    game_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Update user's streak from backend analysis (SOURCE OF TRUTH).
    
    This is called by analysis_worker.py after Stockfish analysis completes.
    Frontend should NOT call streak update - backend is authoritative.
    
    Args:
        db: MongoDB database connection
        user_id: User identifier
        game_id: Game identifier  
        move_evaluations: Full move evaluations from Stockfish
        user_color: "white" or "black"
        game_metadata: Optional metadata (result, rating, etc.)
    
    Returns:
        Dict with:
        - streak_data: Updated streak state
        - game_summary: Summary of this game for display
        - postgame_result: Message data for UI
    """
    logger.info(f"[STREAK] Updating streak from backend analysis for {user_id}, game {game_id}")
    
    # Get user's current streak data
    user = db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "streak_data": 1}
    )
    
    streak_before = user.get("streak_data") if user else None
    if not streak_before:
        streak_before = _get_default_streak_data()
    
    focus_type = streak_before.get("current_focus_mistake", "THREAT_VERIFICATION")
    
    # Detect focus mistake with strict rules
    game_data = detect_focus_mistake(move_evaluations, focus_type, user_color)
    game_data.game_id = game_id
    
    # Build game summary for storage and display
    game_summary = {
        "game_id": game_id,
        "focus_mistake_occurred": game_data.had_focus_mistake,
        "mistake_count": game_data.focus_mistake_count,
        "total_moves": game_data.total_moves,
        "is_valid_for_streak": game_data.is_valid_for_streak,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "source": "engine_verified",
        "analysis_version": "v1.3"
    }
    
    # Find critical moment (highest cp_loss move for focus type)
    critical_moment = _find_critical_moment(move_evaluations, focus_type, user_color)
    if critical_moment:
        game_summary["critical_moment_move"] = critical_moment.get("move_number")
        game_summary["critical_moment_fen"] = critical_moment.get("fen_before")
        game_summary["critical_moment_loss"] = critical_moment.get("cp_loss")
    
    # Check game validity
    if not game_data.is_valid_for_streak:
        logger.info(f"[STREAK] Game {game_id} not valid for streak (too short/no tactical content)")
        game_summary["skipped"] = True
        
        # Still store in last_5 but don't update streak
        last_5 = streak_before.get("last_5_games", [])
        last_5.append(game_summary)
        last_5 = last_5[-5:]
        
        streak_before["last_5_games"] = last_5
        
        # Save without changing streak
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "streak_data": streak_before,
                "streak_data.updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
        return {
            "streak_data": streak_before,
            "game_summary": game_summary,
            "postgame_result": None,
            "streak_changed": False
        }
    
    # Update streak using core logic
    streak_after = update_streak_after_game(
        user_streak_data=streak_before,
        game_analysis={"move_evaluations": move_evaluations},
        game_id=game_id,
        user_color=user_color
    )
    
    # Save to database
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "streak_data": streak_after,
            "streak_data.updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    # Also store game summary in game_analyses for easy access
    db.game_analyses.update_one(
        {"game_id": game_id, "user_id": user_id},
        {"$set": {"streak_summary": game_summary}},
        upsert=False  # Only update if analysis exists
    )
    
    # Generate post-game result
    postgame_result = get_postgame_streak_result(streak_before, streak_after)
    
    # Enhance messaging based on game state + improvement comparison
    postgame_result = _enhance_postgame_messaging(
        postgame_result, 
        game_summary, 
        focus_type,
        last_5_games=streak_after.get("last_5_games", [])
    )
    
    logger.info(f"[STREAK] Updated for {user_id}: {postgame_result['result']} - {game_summary['mistake_count']} focus mistakes")
    
    return {
        "streak_data": streak_after,
        "game_summary": game_summary,
        "postgame_result": postgame_result,
        "streak_changed": True
    }


def _find_critical_moment(
    move_evaluations: List[Dict],
    focus_type: str,
    user_color: str
) -> Optional[Dict]:
    """
    Find the most critical moment related to the focus mistake.
    Returns the move with highest cp_loss that matches the focus type.
    """
    critical = None
    max_loss = 0
    
    for move in move_evaluations:
        if not move.get("is_user_move"):
            continue
        
        cp_loss = abs(move.get("cp_loss", 0))
        if cp_loss < CP_LOSS_MISTAKE:
            continue
        
        # Check if this is a focus-type mistake
        is_focus = False
        if focus_type == "THREAT_VERIFICATION":
            is_focus = _is_threat_miss(move)
        elif focus_type == "FORCING_BLIND":
            is_focus = _is_forcing_miss(move)
        elif focus_type == "HANGING_PIECE":
            is_focus = _is_hanging_piece(move)
        elif focus_type == "TACTICAL_MISS":
            is_focus = _is_tactical_miss(move)
        else:
            is_focus = cp_loss >= CP_LOSS_MISTAKE
        
        if is_focus and cp_loss > max_loss:
            max_loss = cp_loss
            critical = {
                "move_number": move.get("move_number"),
                "fen_before": move.get("fen_before"),
                "cp_loss": cp_loss,
                "played_move": move.get("move_san"),
                "best_move": move.get("best_move_san")
            }
    
    return critical


def _enhance_postgame_messaging(
    postgame_result: Dict,
    game_summary: Dict,
    focus_type: str,
    last_5_games: List[Dict] = None
) -> Dict:
    """
    Enhance post-game messaging with emotional, specific copy.
    
    This is the RETENTION ENGINE - makes users feel accountability + progress.
    
    IMPROVEMENT PROOF: Compare to last game (not average)
    - "You missed 4 threats this game (last: 6)" + "Good. You're improving."
    """
    focus_info = FOCUS_MISTAKE_TYPES.get(focus_type, {})
    focus_short = focus_info.get("short_name", "this").lower()
    mistake_count = game_summary.get("mistake_count", 0)
    
    # Get last game's mistake count for comparison
    last_game_mistakes = None
    if last_5_games and len(last_5_games) >= 2:
        # Get second-to-last game (last is current)
        last_game = last_5_games[-2] if len(last_5_games) >= 2 else None
        if last_game and last_game.get("is_valid", True):
            last_game_mistakes = last_game.get("mistake_count")
    
    # Build improvement comparison
    improvement_text = None
    improvement_verdict = None
    
    if last_game_mistakes is not None:
        if mistake_count < last_game_mistakes:
            improvement_text = f"You missed {mistake_count} {focus_short} (last: {last_game_mistakes})"
            improvement_verdict = "improving"
        elif mistake_count > last_game_mistakes:
            improvement_text = f"You missed {mistake_count} {focus_short} (last: {last_game_mistakes})"
            improvement_verdict = "slipping"
        else:
            improvement_text = f"You missed {mistake_count} {focus_short} again"
            improvement_verdict = "same"
    elif mistake_count > 0:
        improvement_text = f"You missed {mistake_count} {focus_short}"
        improvement_verdict = "first_tracked"
    
    # Add improvement data to result
    postgame_result["improvement"] = {
        "this_game": mistake_count,
        "last_game": last_game_mistakes,
        "text": improvement_text,
        "verdict": improvement_verdict
    }
    
    if postgame_result["result"] == "broken":
        # STREAK BROKEN - Emotional hit
        if mistake_count >= 3:
            postgame_result["headline"] = "❌ Streak Broken"
            postgame_result["message"] = f"You made {mistake_count} {focus_short} mistakes. This is exactly why you're stuck."
        elif mistake_count >= 2:
            postgame_result["headline"] = "❌ Streak Broken"  
            postgame_result["message"] = f"You ignored {focus_short} warnings twice. You saw it coming."
        else:
            postgame_result["headline"] = "❌ Streak Broken"
            postgame_result["message"] = f"You broke your streak by ignoring {focus_short} again. Start fresh."
        
        # Add critical moment reference
        if game_summary.get("critical_moment_move"):
            postgame_result["critical_hint"] = f"Move {game_summary['critical_moment_move']} was your turning point."
        
        # Add improvement context for broken streaks
        if improvement_verdict == "slipping":
            postgame_result["improvement_message"] = "You're slipping. Focus."
        elif improvement_verdict == "same":
            postgame_result["improvement_message"] = "You're not improving yet. Fix this."
    
    elif postgame_result["result"] == "new_best":
        # NEW BEST - Big celebration
        postgame_result["headline"] = "🔥 New Personal Best!"
        postgame_result["message"] = f"You played {postgame_result['streak']} clean games. This is how your rating improves."
        if improvement_verdict == "improving":
            postgame_result["improvement_message"] = "Good. You're improving."
    
    elif postgame_result["result"] == "continued":
        # STREAK CONTINUES - Positive reinforcement
        streak = postgame_result.get("streak", 0)
        if streak >= 5:
            postgame_result["message"] = f"5+ games without {focus_short} mistakes. You're building real habits."
        elif streak >= 3:
            postgame_result["message"] = f"Good. {streak} clean games. Keep building."
        else:
            postgame_result["message"] = f"Clean game. No {focus_short} mistakes. This is how you climb."
        
        if improvement_verdict == "improving":
            postgame_result["improvement_message"] = "Good. You're improving."
    
    return postgame_result


def _get_default_streak_data() -> Dict[str, Any]:
    """Get default streak data for new users.
    
    IMPORTANT: current_focus_mistake is None until actual detection.
    We don't assume a problem - we detect it from game analysis.
    """
    return {
        "current_focus_mistake": None,  # No default! Must be detected from games
        "mistake_streak": {
            "current": 0,
            "best": 0,
            "last_game_had_mistake": False,
            "streak_started_at": None
        },
        "mistake_trend": {
            "before_avg": None,
            "recent_avg": None,
            "improvement_pct": None,
            "baseline_locked": False
        },
        "last_5_games": []
    }
