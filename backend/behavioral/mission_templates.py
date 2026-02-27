"""
Mission Templates Module

Defines parameter tables for each mission type at each difficulty level.

Structure:
- EASY: Reduced friction, fewer positions, longer time
- STANDARD: Balanced challenge
- HARD: Full challenge, more positions, shorter time

All parameters are deterministic — no randomness.
"""

from typing import Dict, Any


# ==================== MISSION PARAMETER TABLES ====================

MISSION_PARAMS: Dict[str, Dict[str, Dict[str, Any]]] = {
    
    # Time Decision Drill
    "TIME_DECISION_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 30,
            "candidate_moves": 2,
            "required_reps": 2,
            "show_opponent_threat": False,
            "instruction_suffix": "Take your time. Pick the safest option."
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 20,
            "candidate_moves": 3,
            "required_reps": 3,
            "show_opponent_threat": False,
            "instruction_suffix": "Compare 3 candidates before deciding."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 15,
            "candidate_moves": 3,
            "required_reps": 4,
            "show_opponent_threat": True,
            "instruction_suffix": "Check opponent's threat first, then pick your move."
        }
    },
    
    # Candidate Move Drill
    "CANDIDATE_MOVE_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 45,
            "candidate_moves": 2,
            "required_reps": 2,
            "eliminate_by_reply": False,
            "instruction_suffix": "Find 2 reasonable moves."
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 30,
            "candidate_moves": 3,
            "required_reps": 3,
            "eliminate_by_reply": False,
            "instruction_suffix": "List 3 candidates, then pick the best."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 25,
            "candidate_moves": 3,
            "required_reps": 4,
            "eliminate_by_reply": True,
            "instruction_suffix": "Find 3 candidates, eliminate 1 by opponent's reply."
        }
    },
    
    # Defensive Resilience Drill
    "DEFENSIVE_RESILIENCE_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 40,
            "focus": "survive",
            "required_reps": 2,
            "show_threat_highlight": True,
            "instruction_suffix": "Find the most solid move. Don't try to win material."
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 30,
            "focus": "defend_and_counterplay",
            "required_reps": 3,
            "show_threat_highlight": False,
            "instruction_suffix": "Defend the threat, then look for counterplay."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 25,
            "focus": "defend_and_counterplay",
            "required_reps": 4,
            "show_threat_highlight": False,
            "instruction_suffix": "Find opponent's idea first, then defend with activity."
        }
    },
    
    # Conversion Discipline Drill
    "CONVERSION_DISCIPLINE_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 45,
            "focus": "simplify",
            "required_reps": 2,
            "show_eval_bar": True,
            "instruction_suffix": "You're winning. Find the cleanest way to convert."
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 35,
            "focus": "simplify_or_press",
            "required_reps": 3,
            "show_eval_bar": True,
            "instruction_suffix": "Maintain your advantage. Don't overpress."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 25,
            "focus": "technical_conversion",
            "required_reps": 4,
            "show_eval_bar": False,
            "instruction_suffix": "Convert without the engine eval. Trust your technique."
        }
    },
    
    # Advice Enforcement Mission
    "ADVICE_ENFORCEMENT": {
        "EASY": {
            "rules_to_enforce": 1,
            "checkpoint_reminder": False,
            "require_annotation": False,
            "timebox_seconds": None,  # Full game
            "required_reps": 1,
            "instruction_suffix": "Focus on just this one rule next game."
        },
        "STANDARD": {
            "rules_to_enforce": 1,
            "checkpoint_reminder": True,
            "checkpoint_move": 6,
            "require_annotation": False,
            "timebox_seconds": None,
            "required_reps": 1,
            "instruction_suffix": "At move 6, pause and check: am I following the rule?"
        },
        "HARD": {
            "rules_to_enforce": 1,
            "checkpoint_reminder": True,
            "checkpoint_move": 6,
            "require_annotation": True,
            "timebox_seconds": None,
            "required_reps": 1,
            "instruction_suffix": "After the game, note why you followed or broke the rule."
        }
    },
    
    # Opening Plan Drill
    "OPENING_PLAN_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 60,
            "moves_to_plan": 3,
            "required_reps": 2,
            "show_typical_plans": True,
            "instruction_suffix": "What are your next 3 developing moves?"
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 45,
            "moves_to_plan": 5,
            "required_reps": 3,
            "show_typical_plans": False,
            "instruction_suffix": "Plan your next 5 moves without help."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 35,
            "moves_to_plan": 5,
            "required_reps": 4,
            "show_typical_plans": False,
            "instruction_suffix": "Plan 5 moves and anticipate opponent's response."
        }
    },
    
    # Tactical Awareness Drill
    "TACTICAL_AWARENESS_DRILL": {
        "EASY": {
            "positions": 1,
            "timebox_seconds": 45,
            "scan_type": "hanging_pieces",
            "required_reps": 2,
            "highlight_targets": True,
            "instruction_suffix": "Before moving, scan: is anything hanging?"
        },
        "STANDARD": {
            "positions": 2,
            "timebox_seconds": 30,
            "scan_type": "full_board",
            "required_reps": 3,
            "highlight_targets": False,
            "instruction_suffix": "Scan the whole board before every move."
        },
        "HARD": {
            "positions": 3,
            "timebox_seconds": 20,
            "scan_type": "full_board_plus_threats",
            "required_reps": 4,
            "highlight_targets": False,
            "instruction_suffix": "Find your threats and opponent's threats."
        }
    },
}


def get_mission_params(mission_type: str, difficulty: str) -> Dict[str, Any]:
    """
    Get mission parameters for a specific type and difficulty.
    
    Args:
        mission_type: e.g., "TIME_DECISION_DRILL"
        difficulty: "EASY" | "STANDARD" | "HARD"
        
    Returns:
        Dict of parameters for the mission
    """
    type_params = MISSION_PARAMS.get(mission_type, {})
    params = type_params.get(difficulty, type_params.get("STANDARD", {}))
    
    # Add common fields
    params["difficulty"] = difficulty
    params["mission_type"] = mission_type
    
    return params


def get_available_mission_types() -> list:
    """Get list of all available mission types"""
    return list(MISSION_PARAMS.keys())


def get_difficulty_description(difficulty: str) -> str:
    """Get human-readable description of difficulty level"""
    descriptions = {
        "EASY": "Gentle start — fewer positions, more time",
        "STANDARD": "Balanced challenge — build consistency",
        "HARD": "Full challenge — test your skills"
    }
    return descriptions.get(difficulty, "Standard challenge")
