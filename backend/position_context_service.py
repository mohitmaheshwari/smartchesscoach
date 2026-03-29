"""
Position Context Service - Psychological Truth Layer

Converts raw engine evaluations into human-understandable game states.
This is the emotional context engine for the entire coaching system.

Used by:
- Coach moment selection (CRS scoring)
- Explanation engine (narrative context)
- Deep sessions (state-aware teaching)
- Behavioral maturity layer
- B2B dashboards

Principle: Stockfish speaks in centipawns. Coaches think in game states.
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class PositionState(str, Enum):
    """Human-readable position states from player's perspective"""
    WINNING = "winning"      # Clear advantage (≥ +250 cp)
    BETTER = "better"        # Comfortable edge (+80 to +250 cp)
    EQUAL = "equal"          # Balanced position (-80 to +80 cp)
    WORSE = "worse"          # Under pressure (-80 to -250 cp)
    LOSING = "losing"        # Critical situation (≤ -250 cp)


# Thresholds that match coaching reality
EVAL_THRESHOLDS = {
    "winning": 250,    # Clear winning advantage
    "better": 80,      # Comfortable edge
    "equal": 80,       # Within this range = equal
    "worse": -80,      # Starting to feel pressure
    "losing": -250     # Serious trouble
}


@dataclass
class PositionContext:
    """Complete psychological context for a position transition"""
    state_before: PositionState
    state_after: PositionState
    eval_before_normalized: int  # From player's perspective
    eval_after_normalized: int
    eval_shift: int              # Absolute change
    
    # Transition flags
    result_flipped: bool         # Winning→Losing or vice versa
    advantage_lost: bool         # Was better, now not
    pressure_released: bool      # Was worse, now better
    momentum_shift: bool         # Any significant state change
    
    # Coaching relevance
    is_decisive_moment: bool     # Changed game outcome trajectory
    emotional_weight: str        # "high" / "medium" / "low"
    
    def to_dict(self) -> Dict:
        return {
            "state_before": self.state_before.value,
            "state_after": self.state_after.value,
            "eval_before": self.eval_before_normalized,
            "eval_after": self.eval_after_normalized,
            "eval_shift": self.eval_shift,
            "result_flipped": self.result_flipped,
            "advantage_lost": self.advantage_lost,
            "pressure_released": self.pressure_released,
            "momentum_shift": self.momentum_shift,
            "is_decisive_moment": self.is_decisive_moment,
            "emotional_weight": self.emotional_weight
        }


def normalize_eval(eval_cp: int, user_color: str) -> int:
    """
    Normalize evaluation to player's perspective.
    
    Stockfish always reports from White's view.
    This converts to the user's perspective.
    
    Args:
        eval_cp: Centipawn evaluation (White's perspective)
        user_color: "white" or "black"
        
    Returns:
        Evaluation from user's perspective (positive = user winning)
    """
    if user_color == "black":
        return -eval_cp
    return eval_cp


def classify_position(eval_cp: int) -> PositionState:
    """
    Classify a position into human-understandable state.
    
    Args:
        eval_cp: Normalized evaluation (from player's perspective)
        
    Returns:
        PositionState enum value
    """
    if eval_cp >= EVAL_THRESHOLDS["winning"]:
        return PositionState.WINNING
    elif eval_cp >= EVAL_THRESHOLDS["better"]:
        return PositionState.BETTER
    elif eval_cp >= EVAL_THRESHOLDS["worse"]:
        return PositionState.EQUAL
    elif eval_cp >= EVAL_THRESHOLDS["losing"]:
        return PositionState.WORSE
    else:
        return PositionState.LOSING


def derive_position_context(
    eval_before: int,
    eval_after: int,
    user_color: str,
    mate_before: Optional[int] = None,
    mate_after: Optional[int] = None
) -> PositionContext:
    """
    Derive complete psychological context from evaluation change.
    
    This is the core function that converts engine numbers into
    coaching-relevant understanding.
    
    Args:
        eval_before: Centipawn eval before move (White's perspective)
        eval_after: Centipawn eval after move (White's perspective)
        user_color: "white" or "black"
        mate_before: Mate in X (if applicable)
        mate_after: Mate in X (if applicable)
        
    Returns:
        PositionContext with full psychological analysis
    """
    # Handle mate situations - convert to large eval
    if mate_before is not None:
        # Positive mate = White has mate, negative = Black has mate
        eval_before = 10000 if mate_before > 0 else -10000
    
    if mate_after is not None:
        eval_after = 10000 if mate_after > 0 else -10000
    
    # Normalize to player's perspective
    before = normalize_eval(eval_before, user_color)
    after = normalize_eval(eval_after, user_color)
    
    # Classify states
    state_before = classify_position(before)
    state_after = classify_position(after)
    
    # Calculate shift
    eval_shift = abs(after - before)
    
    # Determine transition flags
    winning_states = {PositionState.WINNING, PositionState.BETTER}
    losing_states = {PositionState.LOSING, PositionState.WORSE}
    
    result_flipped = (
        (state_before in winning_states and state_after in losing_states) or
        (state_before in losing_states and state_after in winning_states)
    )
    
    advantage_lost = (
        state_before in winning_states and 
        state_after not in winning_states
    )
    
    pressure_released = (
        state_before in losing_states and
        state_after not in losing_states
    )
    
    momentum_shift = state_before != state_after
    
    # Determine if this is a decisive moment
    is_decisive = result_flipped or (eval_shift >= 200)
    
    # Calculate emotional weight
    if result_flipped:
        emotional_weight = "high"
    elif advantage_lost or pressure_released:
        emotional_weight = "medium"
    elif momentum_shift:
        emotional_weight = "medium" if eval_shift >= 100 else "low"
    else:
        emotional_weight = "low"
    
    return PositionContext(
        state_before=state_before,
        state_after=state_after,
        eval_before_normalized=before,
        eval_after_normalized=after,
        eval_shift=eval_shift,
        result_flipped=result_flipped,
        advantage_lost=advantage_lost,
        pressure_released=pressure_released,
        momentum_shift=momentum_shift,
        is_decisive_moment=is_decisive,
        emotional_weight=emotional_weight
    )


def get_state_description(state: PositionState) -> str:
    """
    Get human-readable description for coaching narratives.
    
    Returns phrases suitable for direct use in explanations.
    """
    descriptions = {
        PositionState.WINNING: "clearly winning",
        PositionState.BETTER: "in a comfortable position",
        PositionState.EQUAL: "in an equal position",
        PositionState.WORSE: "under pressure",
        PositionState.LOSING: "in a difficult position"
    }
    return descriptions.get(state, "in play")


def get_transition_narrative(context: PositionContext) -> str:
    """
    Generate a narrative fragment describing the position change.
    
    Used by explanation engine for contextual framing.
    """
    if context.result_flipped:
        if context.state_before in {PositionState.WINNING, PositionState.BETTER}:
            return "This changed the nature of the game completely."
        else:
            return "You turned the game around here."
    
    elif context.advantage_lost:
        return "You were better, but this let the advantage slip."
    
    elif context.pressure_released:
        return "You escaped a difficult position."
    
    elif context.momentum_shift:
        if context.eval_shift >= 150:
            return "This was a significant shift in the position."
        else:
            return "The balance shifted slightly here."
    
    return ""


def compute_context_score(context: PositionContext) -> int:
    """
    Compute CRS context component from position context.
    
    Used by coach_moment_selector for ranking teaching moments.
    
    Returns:
        Context score (0-100 range typically)
    """
    score = 0
    
    # Major transitions
    if context.result_flipped:
        score += 70
    elif context.advantage_lost:
        score += 50
    elif context.pressure_released:
        score += 30
    
    # Decisive moments bonus
    if context.is_decisive_moment:
        score += 20
    
    # Emotional weight bonus
    if context.emotional_weight == "high":
        score += 15
    elif context.emotional_weight == "medium":
        score += 5
    
    return score


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def enrich_moves_with_context(
    moves: list,
    user_color: str
) -> list:
    """
    Add position context to all moves in a game.
    
    Should be called during analysis interpretation phase.
    Stores context per move for future use without recomputation.
    
    Args:
        moves: List of move evaluation dicts
        user_color: "white" or "black"
        
    Returns:
        Moves with position_context added
    """
    for move in moves:
        eval_before = move.get("eval_before", 0)
        eval_after = move.get("eval_after", 0)
        mate_info = move.get("mate_info", {})
        
        mate_before = mate_info.get("before") if mate_info else None
        mate_after = mate_info.get("after") if mate_info else None
        
        context = derive_position_context(
            eval_before=eval_before,
            eval_after=eval_after,
            user_color=user_color,
            mate_before=mate_before,
            mate_after=mate_after
        )
        
        move["position_context"] = context.to_dict()
    
    return moves
