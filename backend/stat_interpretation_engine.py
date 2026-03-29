"""
Stat Interpretation Engine - Journey Page Foundation

Purpose: Convert raw metrics into stable "signals" and decide when to show/hide numbers.
NO text generation here. Just signals.

Key Rules:
- Same input → same signals every time (deterministic)
- Micro-deltas are hidden (hide-noise rule)
- Blunders override accuracy (priority: blunders > mistakes > accuracy > winrate)
- Confidence based on games count

Output feeds Coach Voice Generator + UI.
"""

from typing import Dict, Optional
from enum import Enum


class SignalLevel(Enum):
    MAJOR_IMPROVEMENT = "major_improvement"
    IMPROVING = "improving"
    SLIGHT_IMPROVEMENT = "slight_improvement"
    STABLE = "stable"
    DECLINING = "declining"
    MAJOR_DECLINE = "major_decline"


class StabilityBand(Enum):
    STABLE = "stable"
    MODERATE = "moderate"
    VOLATILE = "volatile"


class OverallChange(Enum):
    VISIBLE = "visible"           # Show deltas
    STABLE_HIDDEN = "stable_hidden"  # Hide deltas, show "stable" only
    NOT_READY = "not_ready"       # Not enough games


# ============================================
# THRESHOLD CONSTANTS (DO NOT CHANGE MID-CODING)
# ============================================

# Accuracy thresholds
ACCURACY_MAJOR_IMPROVEMENT = 4.0
ACCURACY_IMPROVING = 2.0
ACCURACY_STABLE_UPPER = 1.9
ACCURACY_STABLE_LOWER = -1.9
ACCURACY_DECLINING = -2.0
ACCURACY_MAJOR_DECLINE = -4.0

# Blunders/Game thresholds (PRIMARY - lower is better, so reduction is positive)
BLUNDER_MAJOR_IMPROVEMENT = 0.8   # Reduced by 0.8+
BLUNDER_IMPROVING = 0.3           # Reduced by 0.3-0.79
BLUNDER_STABLE_UPPER = 0.29
BLUNDER_STABLE_LOWER = -0.29
BLUNDER_DECLINING = -0.3          # Increased by 0.3-0.79
BLUNDER_MAJOR_DECLINE = -0.8      # Increased by 0.8+

# Mistakes/Game thresholds
MISTAKE_MAJOR_IMPROVEMENT = 1.0
MISTAKE_IMPROVING = 0.4
MISTAKE_STABLE_UPPER = 0.39
MISTAKE_STABLE_LOWER = -0.39
MISTAKE_DECLINING = -0.4

# Winrate thresholds (SECONDARY ONLY - never drives headline alone)
WINRATE_IMPROVING = 12
WINRATE_SLIGHT_IMPROVEMENT = 5
WINRATE_STABLE_UPPER = 4
WINRATE_STABLE_LOWER = -4
WINRATE_DECLINING = -5

# Hide-noise thresholds (if ALL are small, hide everything)
NOISE_ACCURACY = 2.0
NOISE_BLUNDER = 0.3
NOISE_MISTAKE = 0.4
NOISE_WINRATE = 5

# Stability band thresholds (based on current blunders/game)
STABILITY_STABLE_THRESHOLD = 0.4
STABILITY_MODERATE_THRESHOLD = 1.0

# Minimum games for reliable evaluation
MIN_GAMES_FOR_EVAL = 5
CONFIDENCE_FULL_GAMES = 15


# ============================================
# SIGNAL CALCULATION FUNCTIONS
# ============================================

def calculate_accuracy_signal(delta: float) -> SignalLevel:
    """Calculate accuracy signal from delta (now - then)."""
    if delta >= ACCURACY_MAJOR_IMPROVEMENT:
        return SignalLevel.MAJOR_IMPROVEMENT
    elif delta >= ACCURACY_IMPROVING:
        return SignalLevel.IMPROVING
    elif delta >= ACCURACY_STABLE_LOWER and delta <= ACCURACY_STABLE_UPPER:
        return SignalLevel.STABLE
    elif delta >= ACCURACY_MAJOR_DECLINE:
        return SignalLevel.DECLINING
    else:
        return SignalLevel.MAJOR_DECLINE


def calculate_blunder_signal(delta: float) -> SignalLevel:
    """
    Calculate blunder signal from delta (then - now).
    Note: delta is REDUCTION (positive = improvement, negative = worse)
    """
    if delta >= BLUNDER_MAJOR_IMPROVEMENT:
        return SignalLevel.MAJOR_IMPROVEMENT
    elif delta >= BLUNDER_IMPROVING:
        return SignalLevel.IMPROVING
    elif delta >= BLUNDER_STABLE_LOWER and delta <= BLUNDER_STABLE_UPPER:
        return SignalLevel.STABLE
    elif delta >= BLUNDER_MAJOR_DECLINE:
        return SignalLevel.DECLINING
    else:
        return SignalLevel.MAJOR_DECLINE


def calculate_mistake_signal(delta: float) -> SignalLevel:
    """
    Calculate mistake signal from delta (then - now).
    Note: delta is REDUCTION (positive = improvement, negative = worse)
    """
    if delta >= MISTAKE_MAJOR_IMPROVEMENT:
        return SignalLevel.MAJOR_IMPROVEMENT
    elif delta >= MISTAKE_IMPROVING:
        return SignalLevel.IMPROVING
    elif delta >= MISTAKE_STABLE_LOWER and delta <= MISTAKE_STABLE_UPPER:
        return SignalLevel.STABLE
    else:
        return SignalLevel.DECLINING


def calculate_winrate_signal(delta: float) -> SignalLevel:
    """Calculate winrate signal from delta (now - then)."""
    if delta >= WINRATE_IMPROVING:
        return SignalLevel.IMPROVING
    elif delta >= WINRATE_SLIGHT_IMPROVEMENT:
        return SignalLevel.SLIGHT_IMPROVEMENT
    elif delta >= WINRATE_STABLE_LOWER and delta <= WINRATE_STABLE_UPPER:
        return SignalLevel.STABLE
    else:
        return SignalLevel.DECLINING


def calculate_stability_band(blunders_per_game: float) -> StabilityBand:
    """Derive stability band from CURRENT blunders/game."""
    if blunders_per_game <= STABILITY_STABLE_THRESHOLD:
        return StabilityBand.STABLE
    elif blunders_per_game <= STABILITY_MODERATE_THRESHOLD:
        return StabilityBand.MODERATE
    else:
        return StabilityBand.VOLATILE


def calculate_confidence(games: int) -> float:
    """Calculate confidence score based on games count."""
    return min(1.0, games / CONFIDENCE_FULL_GAMES)


def is_noise(accuracy_delta: float, blunder_delta: float, 
             mistake_delta: float, winrate_delta: float) -> bool:
    """Check if all deltas are below noise threshold."""
    return (
        abs(accuracy_delta) < NOISE_ACCURACY and
        abs(blunder_delta) < NOISE_BLUNDER and
        abs(mistake_delta) < NOISE_MISTAKE and
        abs(winrate_delta) < NOISE_WINRATE
    )


def get_headline_signal(blunder_signal: SignalLevel, mistake_signal: SignalLevel,
                        accuracy_signal: SignalLevel, winrate_signal: SignalLevel) -> SignalLevel:
    """
    Determine headline signal based on priority.
    Priority: blunders > mistakes > accuracy > winrate
    
    Key rule: accuracy up but blunders worse → overall = decline
    """
    # Priority 1: Blunders
    if blunder_signal in [SignalLevel.MAJOR_IMPROVEMENT, SignalLevel.MAJOR_DECLINE]:
        return blunder_signal
    if blunder_signal in [SignalLevel.IMPROVING, SignalLevel.DECLINING]:
        return blunder_signal
    
    # Priority 2: Mistakes
    if mistake_signal in [SignalLevel.MAJOR_IMPROVEMENT, SignalLevel.MAJOR_DECLINE]:
        return mistake_signal
    if mistake_signal in [SignalLevel.IMPROVING, SignalLevel.DECLINING]:
        return mistake_signal
    
    # Priority 3: Accuracy
    if accuracy_signal in [SignalLevel.MAJOR_IMPROVEMENT, SignalLevel.MAJOR_DECLINE]:
        return accuracy_signal
    if accuracy_signal in [SignalLevel.IMPROVING, SignalLevel.DECLINING]:
        return accuracy_signal
    
    # Priority 4: Winrate (secondary only)
    if winrate_signal in [SignalLevel.IMPROVING, SignalLevel.DECLINING]:
        return winrate_signal
    
    # All stable
    return SignalLevel.STABLE


# ============================================
# MAIN INTERPRETATION FUNCTION
# ============================================

def interpret_stats(then_metrics: Dict, now_metrics: Dict) -> Dict:
    """
    Main entry point for Stat Interpretation Engine.
    
    Inputs:
    - then_metrics: {games, accuracy, blunders_per_game, mistakes_per_game, winrate}
    - now_metrics:  {games, accuracy, blunders_per_game, mistakes_per_game, winrate}
    
    Returns:
    {
        evaluation_ready: bool,
        confidence: float,
        overall_change: OverallChange,
        stability_band: StabilityBand,
        signals: {
            accuracy: SignalLevel,
            blunders: SignalLevel,
            mistakes: SignalLevel,
            winrate: SignalLevel,
            headline: SignalLevel
        },
        deltas: {
            accuracy: float,
            blunders: float,  # reduction (positive = better)
            mistakes: float,  # reduction (positive = better)
            winrate: float
        },
        show_deltas: bool
    }
    """
    # Check if we have enough games
    now_games = now_metrics.get("games", 0)
    then_games = then_metrics.get("games", 0)
    
    if now_games < MIN_GAMES_FOR_EVAL:
        return {
            "evaluation_ready": False,
            "confidence": 0,
            "overall_change": OverallChange.NOT_READY.value,
            "stability_band": None,
            "signals": None,
            "deltas": None,
            "show_deltas": False,
            "message": f"Play {MIN_GAMES_FOR_EVAL - now_games} more games to see reliable progress."
        }
    
    # Extract metrics
    then_accuracy = then_metrics.get("accuracy", 0)
    now_accuracy = now_metrics.get("accuracy", 0)
    
    then_blunders = then_metrics.get("blunders_per_game", 0)
    now_blunders = now_metrics.get("blunders_per_game", 0)
    
    then_mistakes = then_metrics.get("mistakes_per_game", 0)
    now_mistakes = now_metrics.get("mistakes_per_game", 0)
    
    then_winrate = then_metrics.get("winrate", 0)
    now_winrate = now_metrics.get("winrate", 0)
    
    # Calculate deltas
    accuracy_delta = now_accuracy - then_accuracy
    blunder_delta = then_blunders - now_blunders  # REDUCTION (positive = improvement)
    mistake_delta = then_mistakes - now_mistakes  # REDUCTION (positive = improvement)
    winrate_delta = now_winrate - then_winrate
    
    # Calculate signals
    accuracy_signal = calculate_accuracy_signal(accuracy_delta)
    blunder_signal = calculate_blunder_signal(blunder_delta)
    mistake_signal = calculate_mistake_signal(mistake_delta)
    winrate_signal = calculate_winrate_signal(winrate_delta)
    
    # Get headline signal (priority-based)
    headline_signal = get_headline_signal(blunder_signal, mistake_signal, 
                                          accuracy_signal, winrate_signal)
    
    # Calculate stability band from CURRENT blunders
    stability_band = calculate_stability_band(now_blunders)
    
    # Calculate confidence
    confidence = calculate_confidence(now_games)
    
    # Check hide-noise rule
    if is_noise(accuracy_delta, blunder_delta, mistake_delta, winrate_delta):
        overall_change = OverallChange.STABLE_HIDDEN
        show_deltas = False
    else:
        overall_change = OverallChange.VISIBLE
        show_deltas = True
    
    return {
        "evaluation_ready": True,
        "confidence": round(confidence, 2),
        "overall_change": overall_change.value,
        "stability_band": stability_band.value,
        "signals": {
            "accuracy": accuracy_signal.value,
            "blunders": blunder_signal.value,
            "mistakes": mistake_signal.value,
            "winrate": winrate_signal.value,
            "headline": headline_signal.value
        },
        "deltas": {
            "accuracy": round(accuracy_delta, 1),
            "blunders": round(blunder_delta, 2),  # reduction
            "mistakes": round(mistake_delta, 2),  # reduction
            "winrate": round(winrate_delta, 1)
        },
        "show_deltas": show_deltas
    }


def interpret_momentum(previous5_metrics: Dict, recent5_metrics: Dict) -> Dict:
    """
    Interpret 5 vs 5 momentum (for Trend tab).
    
    Same logic as interpret_stats but for shorter windows.
    """
    return interpret_stats(previous5_metrics, recent5_metrics)


# ============================================
# HELPER FOR EXTRACTING METRICS FROM ANALYSES
# ============================================

def extract_metrics_from_analyses(analyses: list) -> Dict:
    """
    Extract metrics from a list of game analyses.
    
    Returns: {games, accuracy, blunders_per_game, mistakes_per_game, winrate}
    """
    if not analyses:
        return {
            "games": 0,
            "accuracy": 0,
            "blunders_per_game": 0,
            "mistakes_per_game": 0,
            "winrate": 0
        }
    
    total_accuracy = 0
    total_blunders = 0
    total_mistakes = 0
    wins = 0
    accuracy_count = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        
        # Accuracy
        accuracy = sf.get("accuracy", 0)
        if accuracy > 0:
            total_accuracy += accuracy
            accuracy_count += 1
        
        # Blunders and mistakes
        total_blunders += sf.get("blunders", 0)
        total_mistakes += sf.get("mistakes", 0)
        
        # Win rate
        result = analysis.get("user_result", "")
        if result == "win":
            wins += 1
    
    games = len(analyses)
    
    return {
        "games": games,
        "accuracy": round(total_accuracy / accuracy_count, 1) if accuracy_count > 0 else 0,
        "blunders_per_game": round(total_blunders / games, 2) if games > 0 else 0,
        "mistakes_per_game": round(total_mistakes / games, 2) if games > 0 else 0,
        "winrate": round((wins / games) * 100, 1) if games > 0 else 0
    }
