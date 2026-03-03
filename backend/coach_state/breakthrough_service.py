"""
Breakthrough & Plateau Detection Service - Step 8

Detects human-meaningful progress states:
- PLATEAU: stuck despite effort
- BREAKTHROUGH: real improvement
- CONFIDENCE_ILLUSION: accuracy ok but same core mistake repeats
- TILT_RISK: performance swings, emotional instability
- STABLE_GROWTH: less volatility, building trust
- NORMAL: no special state

Output drives:
- Home "Coach message of the week"
- Deep Session focus
- Training prescription changes
- Reward moments (milestones)

NO LLM. NO RAG. Fully deterministic.
"""

import statistics
from dataclasses import dataclass, field
from typing import Dict, Any, List, Literal, Optional


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

BreakthroughState = Literal[
    "BREAKTHROUGH",
    "PLATEAU",
    "CONFIDENCE_ILLUSION",
    "TILT_RISK",
    "STABLE_GROWTH",
    "NORMAL",
]

ImprovementTrajectory = Literal["improving", "stable", "declining"]


# =============================================================================
# THRESHOLD CONSTANTS (Tuned for early-stage product)
# =============================================================================

# Volatility thresholds
LOW_VOLATILITY = 1.5
HIGH_VOLATILITY = 3.0

# Improvement thresholds
BREAKTHROUGH_BLUNDER_DROP = 0.30  # 30% decrease triggers breakthrough
VOLATILITY_IMPROVEMENT = 0.20     # 20% drop in volatility

# Lesson repeat thresholds
LESSON_REPEAT_HIGH = 0.50
LESSON_REPEAT_PLATEAU = 0.45

# Tilt detection
BLUNDER_SPIKE = 0.40  # 40% increase triggers tilt risk

# Window sizes
W1_SIZE = 5   # Last 5 games
W2_SIZE = 10  # Last 10 games
W3_SIZE = 20  # Last 20 games


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class WindowMetrics:
    """Metrics snapshot for a rolling window of games."""
    games: int
    win_rate: float = 0.0
    blunders_per_game: float = 0.0
    mistakes_per_game: float = 0.0
    avg_cp_loss: float = 0.0
    volatility: float = 0.0
    lesson_repeat_rate: float = 0.0
    discipline_score: float = 0.0


@dataclass(frozen=True)
class BreakthroughSignal:
    """Output signal for breakthrough/plateau detection."""
    state: BreakthroughState
    confidence: float              # 0..1 deterministic mapping
    headline: str                  # 1 line coach headline
    coach_message: str             # 2-3 lines max (tier-aware)
    evidence: Dict[str, Any]       # Numbers for debugging (not user-facing)
    recommended_action: str        # "Deep session", "Focus lock", etc.
    cta: str                       # Button text
    dominant_lesson_key: Optional[str] = None


# =============================================================================
# RECOMMENDED ACTION MAPPING
# =============================================================================

RECOMMENDED_ACTIONS = {
    "TILT_RISK": {
        "action": "RECOVERY_MODE",
        "cta": "Start Recovery Mission",
        "duration_games": 3,
        "lock_theme": True,
    },
    "BREAKTHROUGH": {
        "action": "LEVEL_UP",
        "cta": "Start Advanced Drill",
        "increase_difficulty": True,
    },
    "CONFIDENCE_ILLUSION": {
        "action": "FOCUS_LOCK",
        "cta": "Lock One Rule for 5 Games",
        "lock_lesson_key": True,
        "duration_games": 5,
    },
    "PLATEAU": {
        "action": "DEEP_SESSION",
        "cta": "Start Deep Review",
        "force_theme": True,
    },
    "STABLE_GROWTH": {
        "action": "CONTINUE_PATH",
        "cta": "Continue Training",
    },
    "NORMAL": {
        "action": "STANDARD_FLOW",
        "cta": "Play Next Game",
    },
}


# =============================================================================
# COACH COPY (Indian Coach Style, Tier-aware)
# =============================================================================

# Headlines per state
HEADLINES = {
    "TILT_RISK": {
        "Novice": "Take a breath. Let's reset.",
        "Developing": "Rough stretch. Time to stabilize.",
        "Disciplined": "Tilt detected. Recovery mode.",
        "Advanced": "Reset. Short missions only.",
    },
    "BREAKTHROUGH": {
        "Novice": "This week was real progress!",
        "Developing": "Real improvement this week.",
        "Disciplined": "Breakthrough confirmed.",
        "Advanced": "Leveling up.",
    },
    "CONFIDENCE_ILLUSION": {
        "Novice": "You're playing okay but missing the same punch.",
        "Developing": "Accuracy looks fine, but the pattern repeats.",
        "Disciplined": "Same mistake cycle despite stable accuracy.",
        "Advanced": "Pattern blind spot detected.",
    },
    "PLATEAU": {
        "Novice": "You're working hard but stuck in the same loop.",
        "Developing": "Same lesson keeps repeating.",
        "Disciplined": "You're stuck in the same mistake loop.",
        "Advanced": "Plateau. Lock one rule.",
    },
    "STABLE_GROWTH": {
        "Novice": "You're building steady habits!",
        "Developing": "Consistency is improving.",
        "Disciplined": "Stable growth detected.",
        "Advanced": "On track.",
    },
    "NORMAL": {
        "Novice": "Keep going — you're on the right path.",
        "Developing": "Continue your current focus.",
        "Disciplined": "Standard progress.",
        "Advanced": "Continue.",
    },
}

# Messages per state (tier-aware length)
MESSAGES = {
    "TILT_RISK": {
        "Novice": "Too many blunders in a short stretch. We're switching to recovery mode — short missions, one rule only. No pressure.",
        "Developing": "Performance is spiking. Let's simplify: one rule, three games, no analysis spam.",
        "Disciplined": "Volatility is high. Recovery mode: short missions, one rule only.",
        "Advanced": "High volatility. Lock one rule for 3 games.",
    },
    "BREAKTHROUGH": {
        "Novice": "Fewer blunders and more stability. Keep the same habit — it's working. Don't change anything.",
        "Developing": "Blunders down, volatility down. Keep the same approach — it's paying off.",
        "Disciplined": "Measurable improvement. Time to increase difficulty slightly.",
        "Advanced": "Progress confirmed. Difficulty up.",
    },
    "CONFIDENCE_ILLUSION": {
        "Novice": "Your games look okay, but the same mistake keeps happening. Let's lock one rule for 5 games: check forcing replies before committing.",
        "Developing": "Accuracy isn't the issue — pattern is. Fix one thing: check forcing replies before committing.",
        "Disciplined": "Same lesson repeating despite stable cp_loss. Lock one rule for 5 games.",
        "Advanced": "Pattern repeating. Lock rule: forcing replies first.",
    },
    "PLATEAU": {
        "Novice": "You're playing a lot, which is great. But the same mistake keeps showing up. Let's do a Deep Session and lock one rule for a week.",
        "Developing": "Same lesson cycle. We lock one rule for 7 days: forcing moves first.",
        "Disciplined": "Same lesson repeating. Deep Session + Focus Lock for 7 days.",
        "Advanced": "Plateau. Deep Session. Lock rule.",
    },
    "STABLE_GROWTH": {
        "Novice": "Your games are getting more consistent. Less swings, fewer repeats. Keep this up!",
        "Developing": "Volatility down, lesson repeats down. Stay on the current theme.",
        "Disciplined": "Stable trajectory. Continue current path.",
        "Advanced": "On track. Continue.",
    },
    "NORMAL": {
        "Novice": "Nothing unusual this week. Keep playing and building your habits.",
        "Developing": "No special signal. Continue your current training.",
        "Disciplined": "Standard week. Continue.",
        "Advanced": "Continue.",
    },
}


# =============================================================================
# SEVERITY & VOLATILITY CALCULATION
# =============================================================================

def calculate_game_severity(blunders: int, mistakes: int, avg_cp_loss: float) -> float:
    """
    Calculate per-game severity score.
    
    Formula:
        severity = blunders * 3 + mistakes * 1 + (avg_cp_loss / 100)
    
    Example:
        2 blunders, 3 mistakes, avg_cp_loss 180
        → 2*3 + 3*1 + 1.8 = 6 + 3 + 1.8 = 10.8
    """
    return (blunders * 3) + (mistakes * 1) + (avg_cp_loss / 100)


def calculate_volatility(severity_scores: List[float]) -> float:
    """
    Calculate window volatility using population standard deviation.
    
    Deterministic and cheap.
    """
    if len(severity_scores) < 2:
        return 0.0
    return statistics.pstdev(severity_scores)


def build_window_metrics(
    games: List[Dict[str, Any]],
    lesson_keys: List[str] = None,
) -> WindowMetrics:
    """
    Build WindowMetrics from a list of game summaries.
    
    Each game dict should have:
        - blunders: int
        - mistakes: int
        - avg_cp_loss: float
        - result: "win" | "loss" | "draw"
        - discipline_score: float (optional)
    """
    if not games:
        return WindowMetrics(games=0)
    
    n = len(games)
    
    # Win rate
    wins = sum(1 for g in games if g.get("result") == "win")
    win_rate = wins / n
    
    # Blunders and mistakes per game
    total_blunders = sum(g.get("blunders", 0) for g in games)
    total_mistakes = sum(g.get("mistakes", 0) for g in games)
    blunders_per_game = total_blunders / n
    mistakes_per_game = total_mistakes / n
    
    # Average cp_loss
    cp_losses = [g.get("avg_cp_loss", 0) for g in games]
    avg_cp_loss = sum(cp_losses) / n
    
    # Volatility
    severity_scores = [
        calculate_game_severity(
            g.get("blunders", 0),
            g.get("mistakes", 0),
            g.get("avg_cp_loss", 0)
        )
        for g in games
    ]
    volatility = calculate_volatility(severity_scores)
    
    # Lesson repeat rate
    lesson_repeat_rate = 0.0
    if lesson_keys and len(lesson_keys) >= 2:
        # Count how many consecutive games have the same lesson
        repeats = sum(1 for i in range(1, len(lesson_keys)) if lesson_keys[i] == lesson_keys[i-1])
        # Also count most common lesson frequency
        from collections import Counter
        lesson_counts = Counter(lesson_keys)
        most_common_count = lesson_counts.most_common(1)[0][1] if lesson_counts else 0
        lesson_repeat_rate = most_common_count / len(lesson_keys)
    
    # Discipline score (average if available)
    discipline_scores = [g.get("discipline_score", 0.5) for g in games if "discipline_score" in g]
    discipline_score = sum(discipline_scores) / len(discipline_scores) if discipline_scores else 0.5
    
    return WindowMetrics(
        games=n,
        win_rate=win_rate,
        blunders_per_game=blunders_per_game,
        mistakes_per_game=mistakes_per_game,
        avg_cp_loss=avg_cp_loss,
        volatility=volatility,
        lesson_repeat_rate=lesson_repeat_rate,
        discipline_score=discipline_score,
    )


# =============================================================================
# STATE DETECTION (Exact order matters)
# =============================================================================

def detect_tilt_risk(
    w1: WindowMetrics,
    w2: WindowMetrics,
    consecutive_losses: int = 0,
) -> bool:
    """
    TILT_RISK detection.
    
    Trigger if ANY:
    - (W1.volatility >= HIGH_VOLATILITY AND W1.blunders_per_game >= W2.blunders_per_game * 1.4)
    - OR (consecutive_losses >= 2 AND W1.blunders_per_game >= 2)
    """
    # Condition 1: High volatility + blunder spike
    cond1 = (
        w1.volatility >= HIGH_VOLATILITY and
        w2.blunders_per_game > 0 and
        w1.blunders_per_game >= w2.blunders_per_game * (1 + BLUNDER_SPIKE)
    )
    
    # Condition 2: Losing streak with blunders
    cond2 = (
        consecutive_losses >= 2 and
        w1.blunders_per_game >= 2
    )
    
    return cond1 or cond2


def detect_breakthrough(
    w1: WindowMetrics,
    w2: WindowMetrics,
    good_game_streak: int = 0,
    milestone_recent: bool = False,
) -> bool:
    """
    BREAKTHROUGH detection.
    
    Trigger if ALL:
    - W1.games >= 5
    - W1.blunders_per_game <= W2.blunders_per_game * 0.7 (30% drop)
    - W1.volatility <= W2.volatility * 0.8 (20% drop)
    - (good_game_streak >= 2 OR milestone_recent)
    """
    if w1.games < 5:
        return False
    
    if w2.blunders_per_game == 0:
        # Can't compute ratio, check absolute
        blunder_improved = w1.blunders_per_game <= 0.5
    else:
        blunder_improved = w1.blunders_per_game <= w2.blunders_per_game * (1 - BREAKTHROUGH_BLUNDER_DROP)
    
    if w2.volatility == 0:
        volatility_improved = w1.volatility <= LOW_VOLATILITY
    else:
        volatility_improved = w1.volatility <= w2.volatility * (1 - VOLATILITY_IMPROVEMENT)
    
    has_streak_or_milestone = (good_game_streak >= 2 or milestone_recent)
    
    return blunder_improved and volatility_improved and has_streak_or_milestone


def detect_confidence_illusion(
    w1: WindowMetrics,
    w2: WindowMetrics,
    dominant_lesson_intensity: int = 0,
) -> bool:
    """
    CONFIDENCE_ILLUSION detection.
    
    Trigger if ALL:
    - W1.avg_cp_loss <= W2.avg_cp_loss * 1.05 (stable/improving)
    - W1.lesson_repeat_rate >= 0.50
    - dominant_lesson_intensity >= 2
    - W1.win_rate <= W2.win_rate + 0.05
    """
    if w2.avg_cp_loss == 0:
        cp_stable = w1.avg_cp_loss <= 150
    else:
        cp_stable = w1.avg_cp_loss <= w2.avg_cp_loss * 1.05
    
    high_repeat = w1.lesson_repeat_rate >= LESSON_REPEAT_HIGH
    
    high_intensity = dominant_lesson_intensity >= 2
    
    win_rate_flat = w1.win_rate <= w2.win_rate + 0.05
    
    return cp_stable and high_repeat and high_intensity and win_rate_flat


def detect_plateau(
    w1: WindowMetrics,
    w2: WindowMetrics,
    improvement_trajectory: ImprovementTrajectory = "stable",
) -> bool:
    """
    PLATEAU detection.
    
    Trigger if ALL:
    - W2.games >= 10
    - improvement_trajectory == "stable"
    - W1.lesson_repeat_rate >= 0.45
    - W1.blunders_per_game >= W2.blunders_per_game * 0.9
    """
    enough_games = w2.games >= 10
    
    trajectory_flat = improvement_trajectory == "stable"
    
    high_repeat = w1.lesson_repeat_rate >= LESSON_REPEAT_PLATEAU
    
    blunders_not_improving = (
        w2.blunders_per_game == 0 or
        w1.blunders_per_game >= w2.blunders_per_game * 0.9
    )
    
    return enough_games and trajectory_flat and high_repeat and blunders_not_improving


def detect_stable_growth(
    w1: WindowMetrics,
    w2: WindowMetrics,
    w3: WindowMetrics,
    discipline_improving: bool = False,
) -> bool:
    """
    STABLE_GROWTH detection.
    
    Trigger if ALL:
    - W1.volatility < W2.volatility < W3.volatility
    - W1.lesson_repeat_rate < W2.lesson_repeat_rate
    - discipline_score improving
    """
    volatility_decreasing = (
        w1.volatility < w2.volatility < w3.volatility
    )
    
    repeat_decreasing = w1.lesson_repeat_rate < w2.lesson_repeat_rate
    
    return volatility_decreasing and repeat_decreasing and discipline_improving


# =============================================================================
# MAIN DETECTION FUNCTION
# =============================================================================

def detect_breakthrough_state(
    w1: WindowMetrics,
    w2: WindowMetrics,
    w3: WindowMetrics = None,
    consecutive_losses: int = 0,
    good_game_streak: int = 0,
    milestone_recent: bool = False,
    dominant_lesson_intensity: int = 0,
    dominant_lesson_key: str = None,
    improvement_trajectory: ImprovementTrajectory = "stable",
    discipline_improving: bool = False,
    maturity_tier: str = "Developing",
) -> BreakthroughSignal:
    """
    Main detection function. Evaluates states in order:
    1. TILT_RISK
    2. BREAKTHROUGH
    3. CONFIDENCE_ILLUSION
    4. PLATEAU
    5. STABLE_GROWTH
    6. NORMAL
    
    Returns BreakthroughSignal with state, headline, message, and recommended action.
    """
    # Default W3 if not provided
    if w3 is None:
        w3 = WindowMetrics(games=0, volatility=w2.volatility * 1.2 if w2.volatility > 0 else 2.0)
    
    state: BreakthroughState = "NORMAL"
    confidence = 0.5
    evidence = {}
    
    # Order matters - evaluate in priority order
    
    # 1. TILT_RISK (highest priority - safety first)
    if detect_tilt_risk(w1, w2, consecutive_losses):
        state = "TILT_RISK"
        confidence = min(0.9, 0.6 + (w1.volatility / 10))
        evidence = {
            "w1_volatility": w1.volatility,
            "w2_volatility": w2.volatility,
            "blunder_spike": w1.blunders_per_game / max(w2.blunders_per_game, 0.1),
            "consecutive_losses": consecutive_losses,
        }
    
    # 2. BREAKTHROUGH
    elif detect_breakthrough(w1, w2, good_game_streak, milestone_recent):
        state = "BREAKTHROUGH"
        blunder_drop = 1 - (w1.blunders_per_game / max(w2.blunders_per_game, 0.1))
        confidence = min(0.95, 0.7 + blunder_drop * 0.3)
        evidence = {
            "blunder_drop_pct": blunder_drop,
            "volatility_drop_pct": 1 - (w1.volatility / max(w2.volatility, 0.1)),
            "good_game_streak": good_game_streak,
            "milestone_recent": milestone_recent,
        }
    
    # 3. CONFIDENCE_ILLUSION
    elif detect_confidence_illusion(w1, w2, dominant_lesson_intensity):
        state = "CONFIDENCE_ILLUSION"
        confidence = min(0.85, 0.6 + w1.lesson_repeat_rate * 0.3)
        evidence = {
            "lesson_repeat_rate": w1.lesson_repeat_rate,
            "dominant_lesson_intensity": dominant_lesson_intensity,
            "cp_loss_stable": w1.avg_cp_loss <= w2.avg_cp_loss * 1.05,
            "win_rate_flat": w1.win_rate <= w2.win_rate + 0.05,
        }
    
    # 4. PLATEAU
    elif detect_plateau(w1, w2, improvement_trajectory):
        state = "PLATEAU"
        confidence = min(0.8, 0.5 + w1.lesson_repeat_rate * 0.4)
        evidence = {
            "w2_games": w2.games,
            "lesson_repeat_rate": w1.lesson_repeat_rate,
            "improvement_trajectory": improvement_trajectory,
            "blunders_ratio": w1.blunders_per_game / max(w2.blunders_per_game, 0.1),
        }
    
    # 5. STABLE_GROWTH
    elif detect_stable_growth(w1, w2, w3, discipline_improving):
        state = "STABLE_GROWTH"
        confidence = 0.75
        evidence = {
            "volatility_trend": [w3.volatility, w2.volatility, w1.volatility],
            "lesson_repeat_trend": [w2.lesson_repeat_rate, w1.lesson_repeat_rate],
            "discipline_improving": discipline_improving,
        }
    
    # 6. NORMAL (fallback)
    else:
        state = "NORMAL"
        confidence = 0.5
        evidence = {
            "w1_games": w1.games,
            "w1_volatility": w1.volatility,
            "w1_blunders_per_game": w1.blunders_per_game,
        }
    
    # Get tier-aware copy
    headline = HEADLINES.get(state, HEADLINES["NORMAL"]).get(maturity_tier, HEADLINES[state]["Developing"])
    message = MESSAGES.get(state, MESSAGES["NORMAL"]).get(maturity_tier, MESSAGES[state]["Developing"])
    
    # Get recommended action
    action_info = RECOMMENDED_ACTIONS.get(state, RECOMMENDED_ACTIONS["NORMAL"])
    
    return BreakthroughSignal(
        state=state,
        confidence=round(confidence, 2),
        headline=headline,
        coach_message=message,
        evidence=evidence,
        recommended_action=action_info["action"],
        cta=action_info["cta"],
        dominant_lesson_key=dominant_lesson_key,
    )


# =============================================================================
# CONVENIENCE FUNCTION FOR API
# =============================================================================

def get_breakthrough_signal_for_user(
    recent_games: List[Dict[str, Any]],
    lesson_keys: List[str] = None,
    consecutive_losses: int = 0,
    good_game_streak: int = 0,
    milestone_recent: bool = False,
    dominant_lesson_key: str = None,
    dominant_lesson_intensity: int = 0,
    improvement_trajectory: ImprovementTrajectory = "stable",
    discipline_improving: bool = False,
    maturity_tier: str = "Developing",
) -> BreakthroughSignal:
    """
    Convenience function to compute breakthrough signal from raw game data.
    
    Args:
        recent_games: List of game dicts (most recent first), up to 20 games
        lesson_keys: List of lesson keys for each game
        ... other context from CoachState
    
    Returns:
        BreakthroughSignal
    """
    # Build windows
    w1_games = recent_games[:W1_SIZE] if len(recent_games) >= W1_SIZE else recent_games
    w2_games = recent_games[:W2_SIZE] if len(recent_games) >= W2_SIZE else recent_games
    w3_games = recent_games[:W3_SIZE] if len(recent_games) >= W3_SIZE else recent_games
    
    w1_lessons = lesson_keys[:W1_SIZE] if lesson_keys and len(lesson_keys) >= W1_SIZE else (lesson_keys or [])
    w2_lessons = lesson_keys[:W2_SIZE] if lesson_keys and len(lesson_keys) >= W2_SIZE else (lesson_keys or [])
    
    w1 = build_window_metrics(w1_games, w1_lessons)
    w2 = build_window_metrics(w2_games, w2_lessons)
    w3 = build_window_metrics(w3_games)
    
    return detect_breakthrough_state(
        w1=w1,
        w2=w2,
        w3=w3,
        consecutive_losses=consecutive_losses,
        good_game_streak=good_game_streak,
        milestone_recent=milestone_recent,
        dominant_lesson_intensity=dominant_lesson_intensity,
        dominant_lesson_key=dominant_lesson_key,
        improvement_trajectory=improvement_trajectory,
        discipline_improving=discipline_improving,
        maturity_tier=maturity_tier,
    )
