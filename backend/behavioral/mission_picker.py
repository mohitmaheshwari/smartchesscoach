"""
Mission Picker Module

Selects ONE mission (next action) that directly matches the root cause.

Rules:
- Mission must directly match root cause
- Instruction must be specific with move numbers
- Maximum 1 mission per game
- P1.6: Mission difficulty adapts to learner profile
"""

from typing import Dict, Optional


class Mission:
    """A single next action for the user"""
    def __init__(self, type: str, title: str, instruction: str, payload: Dict = None):
        self.type = type
        self.title = title
        self.instruction = instruction
        self.payload = payload or {}
    
    def to_dict(self):
        return {
            "type": self.type,
            "title": self.title,
            "instruction": self.instruction,
            "payload": self.payload
        }


def choose_mission(
    features,
    scorecard: Dict,
    game_id: str,
    root_cause: str,
    difficulty: str = "STANDARD"
) -> Mission:
    """
    Choose ONE mission that directly matches the root cause.
    
    Root cause → Mission mapping:
    - TIME_TRIGGERED → TIME_DECISION_DRILL
    - OVERCONFIDENCE → CONVERSION_DISCIPLINE_DRILL
    - CALCULATION_GAP → CANDIDATE_MOVE_DRILL
    - DEFENSIVE_STRESS → DEFENSIVE_RESILIENCE_DRILL
    
    P1.6: difficulty parameter (EASY/STANDARD/HARD) affects instructions
    """
    
    # Root cause based mission selection
    if root_cause == "TIME_TRIGGERED":
        return _time_decision_drill(features, game_id, difficulty)
    
    elif root_cause == "OVERCONFIDENCE":
        return _conversion_discipline_drill(features, game_id, difficulty)
    
    elif root_cause == "CALCULATION_GAP":
        return _candidate_move_drill(features, game_id, difficulty)
    
    elif root_cause == "DEFENSIVE_STRESS":
        return _defensive_resilience_drill(features, game_id, difficulty)
    
    # Fallback based on scorecard
    if _get_label(scorecard, "decision_stability") in ["Concern", "Mixed"]:
        if features.collapse_move:
            return _stability_drill(features, game_id, difficulty)
    
    if _get_label(scorecard, "plan_discipline") in ["Concern", "Mixed"]:
        return _opening_discipline_drill(features, game_id, difficulty)
    
    # Default: tactical drill
    return _tactical_fuel_drill(features, game_id, difficulty)


def _get_label(scorecard: Dict, key: str) -> str:
    """Helper to get label from scorecard"""
    item = scorecard.get(key, {})
    if hasattr(item, 'label'):
        return item.label
    return item.get('label', '')


def _get_difficulty_suffix(difficulty: str) -> str:
    """Get instruction suffix based on difficulty"""
    suffixes = {
        "EASY": "Take your time.",
        "STANDARD": "",
        "HARD": "Challenge: do this in half the normal time."
    }
    return suffixes.get(difficulty, "")


def _time_decision_drill(features, game_id: str, difficulty: str = "STANDARD") -> Mission:
    """
    For TIME_TRIGGERED root cause.
    Train calm decision-making under time pressure.
    """
    move_no = features.collapse_move or features.first_blunder_move or 20
    
    # Difficulty-scaled parameters
    time_limits = {"EASY": 30, "STANDARD": 20, "HARD": 15}
    candidate_counts = {"EASY": 2, "STANDARD": 3, "HARD": 3}
    
    time_limit = time_limits.get(difficulty, 20)
    candidates = candidate_counts.get(difficulty, 3)
    suffix = _get_difficulty_suffix(difficulty)
    
    instruction = f"Replay the position at move {move_no}. Set {time_limit} seconds. Choose {candidates} candidate moves. Pick the safest one."
    if suffix:
        instruction = f"{instruction} {suffix}"
    
    return Mission(
        type="TIME_DECISION_DRILL",
        title="Time Pressure Drill (5 min)",
        instruction=instruction,
        payload={
            "game_id": game_id,
            "move_no": move_no,
            "time_limit": time_limit,
            "focus": "time_management",
            "difficulty": difficulty
        }
    )


def _conversion_discipline_drill(features, game_id: str, difficulty: str = "STANDARD") -> Mission:
    """
    For OVERCONFIDENCE root cause.
    Train careful play when winning.
    """
    # Find the position where user was winning
    winning_move = None
    for error in features.error_moves:
        if error.get("eval_before", 0) > 1.5:
            winning_move = error.get("move_number")
            break
    
    move_no = winning_move or features.first_blunder_move or 20
    
    return Mission(
        type="CONVERSION_DISCIPLINE_DRILL",
        title="Conversion Discipline (5 min)",
        instruction=f"Review the position at move {move_no} where you were +2.0. Identify opponent counterplay before choosing your move.",
        payload={
            "game_id": game_id,
            "move_no": move_no,
            "focus": "conversion"
        }
    )


def _candidate_move_drill(features, game_id: str) -> Mission:
    """
    For CALCULATION_GAP root cause.
    Train systematic candidate move generation.
    """
    move_no = features.first_blunder_move or 20
    
    return Mission(
        type="CANDIDATE_MOVE_DRILL",
        title="Candidate Move Drill (5 min)",
        instruction=f"For the position at move {move_no}, write 3 candidate moves before calculating. Then calculate each for 2 moves deep.",
        payload={
            "game_id": game_id,
            "move_no": move_no,
            "focus": "calculation"
        }
    )


def _defensive_resilience_drill(features, game_id: str) -> Mission:
    """
    For DEFENSIVE_STRESS root cause.
    Train calm defensive play.
    """
    # Find position where user was defending
    defense_move = None
    for error in features.error_moves:
        if error.get("eval_before", 0) < -1.0:
            defense_move = error.get("move_number")
            break
    
    move_no = defense_move or features.collapse_move or 20
    
    return Mission(
        type="DEFENSIVE_RESILIENCE_DRILL",
        title="Defensive Resilience (5 min)",
        instruction=f"Replay the position at move {move_no}. Find the most solid defensive move, not the most aggressive one. Hold the position.",
        payload={
            "game_id": game_id,
            "move_no": move_no,
            "focus": "defense"
        }
    )


def _stability_drill(features, game_id: str) -> Mission:
    """Generic stability drill"""
    move_no = features.collapse_move or 20
    
    return Mission(
        type="STABILITY_DRILL",
        title="Decision Stability Drill (5 min)",
        instruction=f"Replay the position at move {move_no}. Take 30 seconds. Find 3 candidate moves. Pick the safest one.",
        payload={
            "game_id": game_id,
            "move_no": move_no,
            "focus": "stability"
        }
    )


def _opening_discipline_drill(features, game_id: str) -> Mission:
    """Opening discipline drill"""
    return Mission(
        type="OPENING_DISCIPLINE",
        title="Opening Review (3 min)",
        instruction="Look at your first 10 moves. Find ONE move where you broke development rules. What should you have played?",
        payload={
            "game_id": game_id,
            "moves_range": [1, 10],
            "focus": "opening"
        }
    )


def _tactical_fuel_drill(features, game_id: str) -> Mission:
    """Default tactical drill"""
    return Mission(
        type="TACTICAL_FUEL",
        title="Fix Your Mistakes (5 min)",
        instruction="Solve 3 positions from your biggest errors in this game.",
        payload={
            "game_id": game_id,
            "focus": "tactics"
        }
    )
