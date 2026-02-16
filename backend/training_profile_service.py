"""
Training Profile Service - Adaptive Behavioral Correction System
================================================================

This service implements a fully data-driven training system that:
1. Computes Cost Scores for 4 Training Layers from last N games
2. Selects Active Phase = Highest Cost Layer (not rating-based)
3. Identifies Micro Habit within the phase
4. Generates 2 rules tailored to rating + micro habit
5. Sources drills from user + similar users' mistakes

Core Philosophy:
- Pure data, no hardcoded rating bands for phase selection
- One leak at a time (1 Phase, 1 Habit, 2 Rules)
- Reflection reinforcement updates pattern weights
- Cross-user drill sourcing for variety

Training Layers:
1. STABILITY - Blunders, hanging pieces, rushed moves, threat blindness
2. CONVERSION - Win-state detection, eval drops when ahead, conversion rate
3. STRUCTURE - Opening deviation, equal-position stability
4. PRECISION - Complex position errors, calculation depth, endgame accuracy
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Analysis window
DEFAULT_GAME_WINDOW = 20
MIN_GAMES_REQUIRED = 5
RECALC_THRESHOLD = 7  # Recalculate every 7 games

# Phase graduation settings
GRADUATION_GAMES = 10  # Games to analyze for graduation
GRADUATION_IMPROVEMENT_THRESHOLD = 0.30  # 30% improvement required
CLEAN_GAMES_FOR_GRADUATION = 3  # Or 3 clean games

# Clean game thresholds per phase
CLEAN_GAME_THRESHOLDS = {
    "stability": {"max_blunders": 0, "max_cp_loss_total": 400},  # No blunders, max 4 pawns total loss
    "conversion": {"max_eval_drops_when_winning": 1},  # Max 1 eval drop when ahead
    "structure": {"max_opening_mistakes": 1},  # Max 1 opening inaccuracy
    "precision": {"max_tactical_misses": 2},  # Max 2 tactical misses
}

# Thresholds
WINNING_THRESHOLD = 150      # +1.5 pawns = winning
LARGE_ADVANTAGE = 200        # +2 pawns = large advantage
BLUNDER_THRESHOLD = 200      # 2 pawns = blunder
SIGNIFICANT_DROP = 100       # 1 pawn = significant
HANGING_PIECE_THRESHOLD = 300  # 3 pawns = hanging piece

# Phase definitions (by half-move number)
OPENING_END = 24      # First 12 moves per side
MIDDLEGAME_END = 60   # Moves 13-30 per side

# =============================================================================
# TRAINING PROGRESSION SYSTEM - Rating Adaptive
# =============================================================================

# Training tiers based on rating bands
# Each tier has multiple phases user must complete before "graduating"
TRAINING_TIERS = {
    # Tier 1: Absolute Beginners (200-600)
    "fundamentals": {
        "rating_range": (0, 600),
        "label": "Fundamentals",
        "phases": [
            {
                "id": "piece_safety",
                "label": "Piece Safety",
                "description": "Stop hanging pieces for free",
                "focus": "Don't leave pieces undefended",
                "metric": "hanging_pieces_per_game",
                "target": 1.0,  # Max 1 per game
                "clean_game_threshold": 0,
            },
            {
                "id": "check_awareness",
                "label": "Check Awareness",
                "description": "Always see checks before they happen",
                "focus": "Scan for checks after every move",
                "metric": "missed_checks_per_game",
                "target": 0.5,
                "clean_game_threshold": 0,
            },
            {
                "id": "capture_awareness",
                "label": "Capture Awareness",
                "description": "See all captures on the board",
                "focus": "Check what pieces can be taken",
                "metric": "missed_captures_per_game",
                "target": 1.0,
                "clean_game_threshold": 1,
            },
        ]
    },
    
    # Tier 2: Beginners (600-1000)
    "stability": {
        "rating_range": (600, 1000),
        "label": "Stability",
        "phases": [
            {
                "id": "blunder_reduction",
                "label": "Blunder Reduction",
                "description": "Cut down on major mistakes",
                "focus": "Think twice before moving",
                "metric": "blunders_per_game",
                "target": 1.5,
                "clean_game_threshold": 0,
            },
            {
                "id": "threat_detection",
                "label": "Threat Detection",
                "description": "See opponent's one-move threats",
                "focus": "Ask: What does my opponent want?",
                "metric": "threats_missed_per_game",
                "target": 1.0,
                "clean_game_threshold": 0,
            },
            {
                "id": "piece_activity",
                "label": "Piece Activity",
                "description": "Keep all your pieces active",
                "focus": "No piece left behind",
                "metric": "inactive_pieces_avg",
                "target": 1.0,
                "clean_game_threshold": 1,
            },
        ]
    },
    
    # Tier 3: Intermediate (1000-1400)
    "structure": {
        "rating_range": (1000, 1400),
        "label": "Structure",
        "phases": [
            {
                "id": "opening_principles",
                "label": "Opening Principles",
                "description": "Develop pieces, control center, castle",
                "focus": "Follow opening fundamentals",
                "metric": "opening_mistakes_per_game",
                "target": 1.0,
                "clean_game_threshold": 0,
            },
            {
                "id": "pawn_structure",
                "label": "Pawn Structure",
                "description": "Create healthy pawn formations",
                "focus": "Avoid weak pawns",
                "metric": "pawn_weaknesses_created",
                "target": 2.0,
                "clean_game_threshold": 1,
            },
            {
                "id": "piece_coordination",
                "label": "Piece Coordination",
                "description": "Make your pieces work together",
                "focus": "Pieces should support each other",
                "metric": "coordination_score",
                "target": 0.6,
                "clean_game_threshold": 1,
            },
        ]
    },
    
    # Tier 4: Club Players (1400-1800)
    "conversion": {
        "rating_range": (1400, 1800),
        "label": "Conversion",
        "phases": [
            {
                "id": "advantage_maintenance",
                "label": "Advantage Maintenance",
                "description": "Keep your winning positions",
                "focus": "Don't let advantages slip",
                "metric": "eval_drops_when_winning",
                "target": 1.0,
                "clean_game_threshold": 0,
            },
            {
                "id": "winning_technique",
                "label": "Winning Technique",
                "description": "Convert winning positions to wins",
                "focus": "Simplify when ahead",
                "metric": "wins_from_winning_positions_pct",
                "target": 0.75,
                "clean_game_threshold": 1,
            },
            {
                "id": "endgame_basics",
                "label": "Endgame Basics",
                "description": "Know fundamental endgames",
                "focus": "King activity, passed pawns",
                "metric": "endgame_mistakes_per_game",
                "target": 1.0,
                "clean_game_threshold": 0,
            },
        ]
    },
    
    # Tier 5: Advanced (1800-2200)
    "precision": {
        "rating_range": (1800, 2200),
        "label": "Precision",
        "phases": [
            {
                "id": "calculation_depth",
                "label": "Calculation Depth",
                "description": "See deeper into positions",
                "focus": "Calculate 3+ moves ahead",
                "metric": "tactical_misses_per_game",
                "target": 0.5,
                "clean_game_threshold": 0,
            },
            {
                "id": "positional_understanding",
                "label": "Positional Understanding",
                "description": "Evaluate positions accurately",
                "focus": "Feel the position",
                "metric": "positional_mistakes_per_game",
                "target": 1.0,
                "clean_game_threshold": 1,
            },
            {
                "id": "complex_tactics",
                "label": "Complex Tactics",
                "description": "Find multi-move combinations",
                "focus": "Pattern recognition",
                "metric": "missed_tactics_per_game",
                "target": 0.5,
                "clean_game_threshold": 0,
            },
        ]
    },
    
    # Tier 6: Expert (2200+)
    "mastery": {
        "rating_range": (2200, 9999),
        "label": "Mastery",
        "phases": [
            {
                "id": "deep_preparation",
                "label": "Deep Preparation",
                "description": "Opening theory and novelties",
                "focus": "Surprise your opponents",
                "metric": "opening_advantage_pct",
                "target": 0.55,
                "clean_game_threshold": 2,
            },
            {
                "id": "time_management",
                "label": "Time Management",
                "description": "Use your clock wisely",
                "focus": "No time trouble blunders",
                "metric": "time_trouble_mistakes",
                "target": 0.5,
                "clean_game_threshold": 0,
            },
            {
                "id": "psychological_resilience",
                "label": "Psychological Resilience",
                "description": "Stay strong in difficult positions",
                "focus": "Fight back from worse positions",
                "metric": "comeback_rate",
                "target": 0.3,
                "clean_game_threshold": 1,
            },
        ]
    },
}

def get_tier_for_rating(rating: int) -> str:
    """Get the appropriate training tier for a rating."""
    for tier_id, tier in TRAINING_TIERS.items():
        min_r, max_r = tier["rating_range"]
        if min_r <= rating < max_r:
            return tier_id
    return "mastery"  # Default for very high ratings


def get_phase_in_tier(tier_id: str, phase_index: int) -> Dict:
    """Get a specific phase within a tier."""
    tier = TRAINING_TIERS.get(tier_id, TRAINING_TIERS["stability"])
    phases = tier["phases"]
    if phase_index < len(phases):
        return phases[phase_index]
    return phases[-1]  # Return last phase if index out of bounds


def get_total_phases_in_tier(tier_id: str) -> int:
    """Get total number of phases in a tier."""
    tier = TRAINING_TIERS.get(tier_id, TRAINING_TIERS["stability"])
    return len(tier["phases"])


# Legacy mapping for backward compatibility
TRAINING_LAYERS = {
    "stability": {
        "label": "Stability",
        "description": "Avoiding blunders and keeping pieces safe",
        "icon": "shield",
        "patterns": ["rushing", "threat_blindness", "hanging_pieces", "one_move_threats"],
    },
    "conversion": {
        "label": "Conversion",
        "description": "Converting advantages into wins",
        "icon": "trending-up",
        "patterns": ["overconfidence", "premature_attack", "missing_simplification", "allowing_counterplay"],
    },
    "structure": {
        "label": "Structure",
        "description": "Opening preparation and positional play",
        "icon": "layers",
        "patterns": ["opening_deviation", "passive_pieces", "poor_pawn_structure", "aimless_play"],
    },
    "precision": {
        "label": "Precision",
        "description": "Accurate calculation in critical moments",
        "icon": "crosshair",
        "patterns": ["shallow_calculation", "missing_tactics", "endgame_technique", "time_pressure"],
    },
}

# Pattern descriptions for UI
PATTERN_INFO = {
    "rushing": {
        "label": "Rushing",
        "description": "Moving too quickly in critical positions",
        "question": "Did you feel rushed or impatient?",
    },
    "threat_blindness": {
        "label": "Threat Blindness",
        "description": "Missing opponent's threats",
        "question": "Did you miss what your opponent was planning?",
    },
    "hanging_pieces": {
        "label": "Hanging Pieces",
        "description": "Leaving pieces undefended",
        "question": "Did you forget to protect a piece?",
    },
    "one_move_threats": {
        "label": "One-Move Threats",
        "description": "Missing simple tactical threats",
        "question": "Did you miss a simple tactic?",
    },
    "overconfidence": {
        "label": "Overconfidence",
        "description": "Relaxing when ahead",
        "question": "Did you think you were winning and relax?",
    },
    "premature_attack": {
        "label": "Premature Attack",
        "description": "Attacking before ready",
        "question": "Did you attack before your position was ready?",
    },
    "missing_simplification": {
        "label": "Missing Simplification",
        "description": "Not trading when ahead",
        "question": "Should you have simplified the position?",
    },
    "allowing_counterplay": {
        "label": "Allowing Counterplay",
        "description": "Giving opponent chances when winning",
        "question": "Did you give your opponent unnecessary chances?",
    },
    "opening_deviation": {
        "label": "Opening Deviation",
        "description": "Going off-book too early",
        "question": "Did you deviate from your opening preparation?",
    },
    "passive_pieces": {
        "label": "Passive Pieces",
        "description": "Not activating pieces",
        "question": "Were your pieces actively placed?",
    },
    "poor_pawn_structure": {
        "label": "Poor Pawn Structure",
        "description": "Creating pawn weaknesses",
        "question": "Did you damage your pawn structure?",
    },
    "aimless_play": {
        "label": "Aimless Play",
        "description": "Moving without a plan",
        "question": "Did you have a clear plan?",
    },
    "shallow_calculation": {
        "label": "Shallow Calculation",
        "description": "Not calculating deep enough",
        "question": "Did you calculate far enough ahead?",
    },
    "missing_tactics": {
        "label": "Missing Tactics",
        "description": "Missing winning tactics",
        "question": "Did you miss a tactical opportunity?",
    },
    "endgame_technique": {
        "label": "Endgame Technique",
        "description": "Poor endgame play",
        "question": "Did you struggle in the endgame?",
    },
    "time_pressure": {
        "label": "Time Pressure",
        "description": "Mistakes due to time trouble",
        "question": "Were you in time trouble?",
    },
}

# =============================================================================
# RULES BY LAYER + PATTERN + RATING
# =============================================================================

RULES_DATABASE = {
    "stability": {
        "rushing": {
            "low": [  # < 1000
                "Before moving, count to 3 and ask: Is this safe?",
                "Check if your piece can be captured on its new square",
            ],
            "mid": [  # 1000-1600
                "In critical positions, identify at least 2 candidate moves",
                "Before playing, ask: What is my opponent's best response?",
            ],
            "high": [  # 1600+
                "Use 20% of your remaining time on critical decisions",
                "Verify your calculation by checking opponent's forcing moves",
            ],
        },
        "threat_blindness": {
            "low": [
                "After every opponent move, ask: What does this attack?",
                "CCT: Check for Checks, Captures, and Threats",
            ],
            "mid": [
                "Before your move, find your opponent's top 2 threats",
                "Look at every piece your opponent moved - what can it now do?",
            ],
            "high": [
                "Calculate your opponent's most dangerous continuation",
                "Consider prophylaxis before attacking",
            ],
        },
        "hanging_pieces": {
            "low": [
                "Before moving, count attackers vs defenders on each piece",
                "After moving, check: Is this piece protected?",
            ],
            "mid": [
                "Scan the board after each move for undefended pieces",
                "Use the 'Blunder Check': Can any of my pieces be taken?",
            ],
            "high": [
                "Evaluate piece safety as part of every calculation",
                "Consider indirect attacks through discovered threats",
            ],
        },
        "one_move_threats": {
            "low": [
                "Check if opponent can take anything for free",
                "Look for checks and captures before every move",
            ],
            "mid": [
                "Scan for forks, pins, and skewers after opponent moves",
                "Ask: Does my opponent have a one-move winner?",
            ],
            "high": [
                "Include defensive resources in your calculation tree",
                "Visualize the board after forced exchanges",
            ],
        },
    },
    "conversion": {
        "overconfidence": {
            "low": [
                "When ahead, keep playing carefully - don't rush",
                "Trade pieces when you're winning, not pawns",
            ],
            "mid": [
                "Winning requires technique, not just advantage",
                "Simplify by trading your worst piece for their best",
            ],
            "high": [
                "Convert advantages by eliminating counterplay",
                "Calculate the winning line, don't assume it exists",
            ],
        },
        "premature_attack": {
            "low": [
                "Develop all your pieces before attacking",
                "Castle before launching an attack",
            ],
            "mid": [
                "Ensure your pieces coordinate before attacking",
                "Build your position before committing to an attack",
            ],
            "high": [
                "Verify attacking prerequisites: king safety, piece activity",
                "Time your attack when opponent's pieces are misplaced",
            ],
        },
        "missing_simplification": {
            "low": [
                "When ahead in material, trade pieces (not pawns)",
                "Fewer pieces = easier to win when ahead",
            ],
            "mid": [
                "Look for favorable exchanges that reduce complexity",
                "When +2, prioritize exchanges over attacks",
            ],
            "high": [
                "Calculate the resulting endgame before trading",
                "Simplify into theoretical wins, not just 'easier' positions",
            ],
        },
        "allowing_counterplay": {
            "low": [
                "Don't give checks or captures for free",
                "Keep your pieces protected even when winning",
            ],
            "mid": [
                "Restrict opponent's active pieces before expanding",
                "Prophylaxis: prevent opponent's plan before executing yours",
            ],
            "high": [
                "Calculate opponent's best practical chances",
                "Deny counterplay even at the cost of slower conversion",
            ],
        },
    },
    "structure": {
        "opening_deviation": {
            "low": [
                "Follow basic opening principles: control center, develop, castle",
                "Don't move the same piece twice in the opening",
            ],
            "mid": [
                "Know 6-8 moves of your main openings",
                "Understand WHY each opening move is played",
            ],
            "high": [
                "Prepare specific lines against common responses",
                "Understand typical middlegame plans for your openings",
            ],
        },
        "passive_pieces": {
            "low": [
                "Develop knights and bishops before moving pawns",
                "Put pieces on active squares where they attack things",
            ],
            "mid": [
                "Identify your worst-placed piece and improve it",
                "Every piece should have a job - what is each piece doing?",
            ],
            "high": [
                "Optimize piece placement before committing to plans",
                "Coordinate pieces toward strategic targets",
            ],
        },
        "poor_pawn_structure": {
            "low": [
                "Don't create doubled or isolated pawns without reason",
                "Pawns can't move backward - think before pushing",
            ],
            "mid": [
                "Consider pawn structure before captures",
                "Use pawns to control key squares, not just grab space",
            ],
            "high": [
                "Evaluate long-term pawn structure consequences",
                "Create pawn weaknesses in opponent's camp, not yours",
            ],
        },
        "aimless_play": {
            "low": [
                "Have a simple goal each move: develop, control center, or defend",
                "Ask: What does this move accomplish?",
            ],
            "mid": [
                "Form a plan based on position's characteristics",
                "Every move should improve your position or weaken opponent's",
            ],
            "high": [
                "Identify the critical factor in the position and play to it",
                "Formulate multi-move plans based on imbalances",
            ],
        },
    },
    "precision": {
        "shallow_calculation": {
            "low": [
                "Calculate at least 2 moves ahead before playing",
                "Check what happens after opponent's most obvious reply",
            ],
            "mid": [
                "In tactical positions, calculate until the position is quiet",
                "Verify your line by checking opponent's forcing moves",
            ],
            "high": [
                "Calculate all forcing lines to their conclusion",
                "Use elimination: if all quiet moves lose, there must be a tactic",
            ],
        },
        "missing_tactics": {
            "low": [
                "Look for checks and captures first",
                "Practice tactics puzzles 15 minutes daily",
            ],
            "mid": [
                "Scan for tactical motifs: pins, forks, skewers, discovered attacks",
                "When ahead, look for forcing wins, not just good moves",
            ],
            "high": [
                "Calculate tactical sequences with precision",
                "Look for quiet moves that create unstoppable threats",
            ],
        },
        "endgame_technique": {
            "low": [
                "In endgames, activate your king immediately",
                "Push passed pawns - they want to become queens",
            ],
            "mid": [
                "Know basic king and pawn endgame principles",
                "Calculate pawn races accurately",
            ],
            "high": [
                "Master theoretical endgames: Lucena, Philidor, etc.",
                "Convert with precision - calculate to mate or promotion",
            ],
        },
        "time_pressure": {
            "low": [
                "Use at least 30 seconds on important moves",
                "Don't blitz through critical positions",
            ],
            "mid": [
                "Allocate time by game phase: opening=fast, middlegame=thoughtful",
                "When low on time, play solid moves, not complicated ones",
            ],
            "high": [
                "Build a time reserve for critical moments",
                "Practice rapid pattern recognition for common positions",
            ],
        },
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_rating_tier(rating: int) -> str:
    """Get rating tier for rule selection."""
    if rating < 1000:
        return "low"
    elif rating < 1600:
        return "mid"
    return "high"


def get_move_phase(move_number: int) -> str:
    """Determine game phase from move number (half-moves)."""
    if move_number <= OPENING_END:
        return "opening"
    elif move_number <= MIDDLEGAME_END:
        return "middlegame"
    return "endgame"


def get_position_context(eval_before: int) -> str:
    """Determine context from evaluation."""
    if eval_before >= WINNING_THRESHOLD:
        return "winning"
    elif eval_before <= -WINNING_THRESHOLD:
        return "losing"
    return "equal"


# =============================================================================
# LAYER COST COMPUTATION
# =============================================================================

def compute_stability_cost(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Compute Stability Layer cost.
    
    Measures:
    - Blunders per game
    - Hanging piece frequency (cp_loss >= 300)
    - Threat blindness (opponent had threat, user missed)
    """
    total_games = len(analyses) if analyses else 1
    
    blunder_count = 0
    hanging_piece_count = 0
    threat_blindness_count = 0
    one_move_threat_count = 0
    total_cost = 0
    
    pattern_events = {
        "rushing": [],
        "threat_blindness": [],
        "hanging_pieces": [],
        "one_move_threats": [],
    }
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            evaluation = m.get("evaluation", "")
            has_threat = m.get("threat") is not None
            
            event = {
                "game_id": game_id,
                "move_number": m.get("move_number"),
                "cp_loss": cp_loss,
                "fen": m.get("fen_before"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
            }
            
            # Blunders (any large mistake)
            if evaluation == "blunder" or cp_loss >= BLUNDER_THRESHOLD:
                blunder_count += 1
                total_cost += cp_loss * 1.2
                
                # Classify pattern
                if cp_loss >= HANGING_PIECE_THRESHOLD:
                    hanging_piece_count += 1
                    pattern_events["hanging_pieces"].append(event)
                elif has_threat:
                    threat_blindness_count += 1
                    pattern_events["threat_blindness"].append(event)
                else:
                    # Assume rushing if no other explanation
                    pattern_events["rushing"].append(event)
            
            # One-move threats (simple tactics missed)
            if cp_loss >= SIGNIFICANT_DROP and cp_loss < HANGING_PIECE_THRESHOLD:
                if has_threat:
                    one_move_threat_count += 1
                    pattern_events["one_move_threats"].append(event)
    
    # Compute pattern weights
    total_events = blunder_count + one_move_threat_count
    if total_events == 0:
        pattern_weights = {p: 0.25 for p in pattern_events.keys()}
    else:
        pattern_weights = {
            "rushing": len(pattern_events["rushing"]) / max(total_events, 1),
            "threat_blindness": (threat_blindness_count + len(pattern_events["one_move_threats"])) / max(total_events, 1),
            "hanging_pieces": hanging_piece_count / max(total_events, 1),
            "one_move_threats": one_move_threat_count / max(total_events, 1),
        }
        # Normalize
        total_weight = sum(pattern_weights.values())
        if total_weight > 0:
            pattern_weights = {k: round(v / total_weight, 3) for k, v in pattern_weights.items()}
    
    return {
        "cost": round(total_cost, 2),
        "blunders_per_game": round(blunder_count / total_games, 2),
        "hanging_pieces_per_game": round(hanging_piece_count / total_games, 2),
        "threat_misses_per_game": round(threat_blindness_count / total_games, 2),
        "pattern_weights": pattern_weights,
        "example_positions": sorted(
            pattern_events["hanging_pieces"] + pattern_events["threat_blindness"] + pattern_events["rushing"],
            key=lambda x: x["cp_loss"],
            reverse=True
        )[:5],
    }


def compute_conversion_cost(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Compute Conversion Layer cost.
    
    Measures:
    - Games where user had +2 advantage but didn't win
    - Eval drops when ahead (losing advantage)
    - Win conversion rate
    """
    total_games = len(analyses) if analyses else 1
    game_map = {g.get("game_id"): g for g in games}
    
    conversion_failures = 0
    eval_drops_when_winning = 0
    total_cost = 0
    
    pattern_events = {
        "overconfidence": [],
        "premature_attack": [],
        "missing_simplification": [],
        "allowing_counterplay": [],
    }
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = game_map.get(game_id, {})
        result = game.get("result", "")
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        had_winning_position = False
        max_advantage = 0
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            cp_loss = m.get("cp_loss", 0)
            phase = get_move_phase(m.get("move_number", 0))
            
            # Track maximum advantage
            if eval_before >= LARGE_ADVANTAGE:
                had_winning_position = True
                max_advantage = max(max_advantage, eval_before)
            
            # Eval drops when winning
            if eval_before >= WINNING_THRESHOLD and cp_loss >= SIGNIFICANT_DROP:
                eval_drops_when_winning += 1
                total_cost += cp_loss * 1.5  # Higher weight for conversion errors
                
                event = {
                    "game_id": game_id,
                    "move_number": m.get("move_number"),
                    "cp_loss": cp_loss,
                    "fen": m.get("fen_before"),
                    "move": m.get("move"),
                    "best_move": m.get("best_move"),
                    "eval_before": eval_before,
                }
                
                # Classify pattern
                if cp_loss >= BLUNDER_THRESHOLD:
                    pattern_events["overconfidence"].append(event)
                elif phase == "opening" or phase == "middlegame":
                    pattern_events["premature_attack"].append(event)
                else:
                    pattern_events["allowing_counterplay"].append(event)
        
        # Check if game was won despite having winning position
        won_game = result in ["1-0", "0-1"] and (
            (result == "1-0" and game.get("user_color") == "white") or
            (result == "0-1" and game.get("user_color") == "black")
        )
        
        if had_winning_position and not won_game:
            conversion_failures += 1
            total_cost += 500  # Penalty for not converting
    
    # Compute pattern weights
    total_events = sum(len(events) for events in pattern_events.values())
    if total_events == 0:
        pattern_weights = {p: 0.25 for p in pattern_events.keys()}
    else:
        pattern_weights = {k: len(v) / total_events for k, v in pattern_events.items()}
    
    return {
        "cost": round(total_cost, 2),
        "conversion_failures": conversion_failures,
        "eval_drops_when_winning": eval_drops_when_winning,
        "conversion_failure_rate": round(conversion_failures / total_games, 3),
        "pattern_weights": {k: round(v, 3) for k, v in pattern_weights.items()},
        "example_positions": sorted(
            sum(pattern_events.values(), []),
            key=lambda x: x["cp_loss"],
            reverse=True
        )[:5],
    }


def compute_structure_cost(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Compute Structure Layer cost.
    
    Measures:
    - Opening deviation (mistakes in first 12 moves)
    - Equal-position instability (mistakes when eval is close to 0)
    """
    total_games = len(analyses) if analyses else 1
    
    opening_mistakes = 0
    equal_position_mistakes = 0
    total_cost = 0
    
    pattern_events = {
        "opening_deviation": [],
        "passive_pieces": [],
        "poor_pawn_structure": [],
        "aimless_play": [],
    }
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            eval_before = m.get("eval_before", 0)
            move_number = m.get("move_number", 0)
            phase = get_move_phase(move_number)
            
            if cp_loss < SIGNIFICANT_DROP:
                continue
            
            event = {
                "game_id": game_id,
                "move_number": move_number,
                "cp_loss": cp_loss,
                "fen": m.get("fen_before"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
            }
            
            # Opening mistakes
            if phase == "opening":
                opening_mistakes += 1
                total_cost += cp_loss * 1.1
                pattern_events["opening_deviation"].append(event)
            
            # Equal position mistakes (structural issues)
            elif abs(eval_before) <= 50:  # Truly equal
                equal_position_mistakes += 1
                total_cost += cp_loss * 0.9
                pattern_events["aimless_play"].append(event)
    
    # Pattern weights
    total_events = sum(len(events) for events in pattern_events.values())
    if total_events == 0:
        pattern_weights = {p: 0.25 for p in pattern_events.keys()}
    else:
        pattern_weights = {k: len(v) / max(total_events, 1) for k, v in pattern_events.items()}
    
    return {
        "cost": round(total_cost, 2),
        "opening_mistakes": opening_mistakes,
        "equal_position_mistakes": equal_position_mistakes,
        "opening_mistake_rate": round(opening_mistakes / total_games, 3),
        "pattern_weights": {k: round(v, 3) for k, v in pattern_weights.items()},
        "example_positions": sorted(
            sum(pattern_events.values(), []),
            key=lambda x: x["cp_loss"],
            reverse=True
        )[:5],
    }


def compute_precision_cost(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Compute Precision Layer cost.
    
    Measures:
    - Eval drops in complex/tactical positions
    - Endgame errors
    - Late-game mistakes (time pressure proxy)
    """
    tactical_misses = 0
    endgame_errors = 0
    time_pressure_errors = 0
    total_cost = 0
    
    pattern_events = {
        "shallow_calculation": [],
        "missing_tactics": [],
        "endgame_technique": [],
        "time_pressure": [],
    }
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            move_number = m.get("move_number", 0)
            phase = get_move_phase(move_number)
            evaluation = m.get("evaluation", "")
            
            if cp_loss < SIGNIFICANT_DROP:
                continue
            
            event = {
                "game_id": game_id,
                "move_number": move_number,
                "cp_loss": cp_loss,
                "fen": m.get("fen_before"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
            }
            
            # Tactical misses (blunders in middlegame)
            if phase == "middlegame" and evaluation in ["blunder", "mistake"]:
                tactical_misses += 1
                total_cost += cp_loss
                pattern_events["missing_tactics"].append(event)
            
            # Endgame errors
            elif phase == "endgame":
                endgame_errors += 1
                total_cost += cp_loss * 1.1
                pattern_events["endgame_technique"].append(event)
            
            # Late-game errors (time pressure proxy)
            if move_number > 40:
                time_pressure_errors += 1
                pattern_events["time_pressure"].append(event)
    
    # Pattern weights
    total_events = sum(len(events) for events in pattern_events.values())
    if total_events == 0:
        pattern_weights = {p: 0.25 for p in pattern_events.keys()}
    else:
        pattern_weights = {k: len(v) / max(total_events, 1) for k, v in pattern_events.items()}
    
    return {
        "cost": round(total_cost, 2),
        "tactical_misses": tactical_misses,
        "endgame_errors": endgame_errors,
        "time_pressure_errors": time_pressure_errors,
        "pattern_weights": {k: round(v, 3) for k, v in pattern_weights.items()},
        "example_positions": sorted(
            sum(pattern_events.values(), []),
            key=lambda x: x["cp_loss"],
            reverse=True
        )[:5],
    }


# =============================================================================
# PHASE-FILTERED EXAMPLE POSITIONS
# =============================================================================

def get_phase_filter_criteria(phase_id: str) -> Dict:
    """
    Get the move filtering criteria for a specific training phase.
    Returns move_range and other criteria for filtering example positions.
    """
    # Phase-specific criteria based on what the phase is training
    PHASE_FILTERS = {
        # Fundamentals tier
        "piece_safety": {"min_cp_loss": 200, "move_range": None},  # Any move
        "check_awareness": {"min_cp_loss": 150, "move_range": None},
        "capture_awareness": {"min_cp_loss": 150, "move_range": None},
        
        # Stability tier
        "blunder_reduction": {"min_cp_loss": 200, "move_range": None},
        "threat_detection": {"min_cp_loss": 100, "move_range": None, "requires_threat": True},
        "piece_activity": {"min_cp_loss": 100, "move_range": (1, 20)},  # Early-mid game
        
        # Structure tier - OPENING focused phases should only show opening moves
        "opening_principles": {"min_cp_loss": 80, "move_range": (1, 12)},  # Opening only!
        "pawn_structure": {"min_cp_loss": 100, "move_range": (1, 25)},
        "piece_coordination": {"min_cp_loss": 100, "move_range": (10, 30)},  # Early middlegame
        
        # Conversion tier
        "advantage_maintenance": {"min_cp_loss": 100, "move_range": None, "was_winning": True},
        "winning_technique": {"min_cp_loss": 100, "move_range": None, "was_winning": True},
        "endgame_basics": {"min_cp_loss": 100, "move_range": (30, 999)},  # Endgame only
        
        # Precision tier
        "calculation_depth": {"min_cp_loss": 80, "move_range": (15, 40)},  # Middlegame
        "positional_understanding": {"min_cp_loss": 80, "move_range": (12, 35)},
        "complex_tactics": {"min_cp_loss": 100, "move_range": (12, 45)},
        
        # Mastery tier
        "deep_preparation": {"min_cp_loss": 50, "move_range": (1, 15)},
        "time_management": {"min_cp_loss": 100, "move_range": (25, 999)},  # Late game
        "psychological_resilience": {"min_cp_loss": 100, "move_range": None, "was_losing": True},
    }
    
    return PHASE_FILTERS.get(phase_id, {"min_cp_loss": 100, "move_range": None})


def filter_positions_for_phase(all_positions: List[Dict], phase_id: str) -> List[Dict]:
    """
    Filter example positions to only include those relevant to the training phase.
    """
    criteria = get_phase_filter_criteria(phase_id)
    move_range = criteria.get("move_range")
    min_cp = criteria.get("min_cp_loss", 100)
    requires_threat = criteria.get("requires_threat", False)
    was_winning = criteria.get("was_winning", False)
    was_losing = criteria.get("was_losing", False)
    
    filtered = []
    for pos in all_positions:
        move_num = pos.get("move_number", 0)
        cp_loss = abs(pos.get("cp_loss", 0))
        
        # Check move range
        if move_range:
            min_move, max_move = move_range
            if not (min_move <= move_num <= max_move):
                continue
        
        # Check minimum cp loss
        if cp_loss < min_cp:
            continue
        
        # Check if threat was missed (for threat-focused phases)
        if requires_threat and not pos.get("threat"):
            continue
        
        # Check if user was winning (for conversion phases)
        eval_before = pos.get("eval_before", 0)
        if was_winning and eval_before < 150:  # Need to be at least +1.5 to be "winning"
            continue
        
        # Check if user was losing (for resilience phases)
        if was_losing and eval_before > -150:
            continue
        
        filtered.append(pos)
    
    return filtered


def collect_all_phase_relevant_positions(analyses: List[Dict], games: List[Dict], phase_id: str) -> List[Dict]:
    """
    Collect ALL mistake positions that match the phase criteria from all analyses.
    This gives us phase-relevant examples regardless of the "layer" they came from.
    """
    criteria = get_phase_filter_criteria(phase_id)
    move_range = criteria.get("move_range")
    min_cp = criteria.get("min_cp_loss", 100)
    
    all_positions = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = abs(m.get("cp_loss", 0))
            move_number = m.get("move_number", 0)
            
            # Check minimum cp loss
            if cp_loss < min_cp:
                continue
            
            # Check move range for phase
            if move_range:
                min_move, max_move = move_range
                if not (min_move <= move_number <= max_move):
                    continue
            
            position = {
                "game_id": game_id,
                "move_number": move_number,
                "cp_loss": cp_loss,
                "fen": m.get("fen_before"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
                "eval_before": m.get("eval_before", 0),
                "eval_after": m.get("eval_after", 0),
                "threat": m.get("threat"),
            }
            all_positions.append(position)
    
    # Sort by cp_loss (worst first) and return
    return sorted(all_positions, key=lambda x: x["cp_loss"], reverse=True)


# =============================================================================
# MAIN TRAINING PROFILE GENERATION
# =============================================================================

async def generate_training_profile(db, user_id: str, rating: int = 1200, preserve_phase: bool = False) -> Dict:
    """
    Generate a complete training profile for a user.
    
    Returns:
    - active_phase: highest cost layer (or preserved from graduation)
    - micro_habit: dominant pattern within phase
    - rules: 2 actionable rules for the week
    - layer_breakdown: costs for all 4 layers
    - drill_positions: positions for practice
    
    If preserve_phase=True, keeps the existing active_phase from graduation.
    """
    # Get existing profile to check for graduation status
    existing_profile = await get_training_profile(db, user_id)
    graduated_phase = None
    phase_started_at = None
    
    if existing_profile and preserve_phase:
        # Check if there's a graduation in progress
        graduated_phase = existing_profile.get("active_phase")
        phase_started_at = existing_profile.get("phase_started_at")
    
    # Fetch analyzed games
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"stockfish_analysis": 1, "game_id": 1}
    ).sort("analyzed_at", -1).limit(DEFAULT_GAME_WINDOW).to_list(length=DEFAULT_GAME_WINDOW)
    
    # Filter to games with valid analysis
    valid_analyses = [
        a for a in analyses
        if a.get("stockfish_analysis", {}).get("move_evaluations")
        and len(a.get("stockfish_analysis", {}).get("move_evaluations", [])) >= 3
    ]
    
    if len(valid_analyses) < MIN_GAMES_REQUIRED:
        return {
            "status": "insufficient_data",
            "games_analyzed": len(valid_analyses),
            "games_required": MIN_GAMES_REQUIRED,
            "message": f"Need at least {MIN_GAMES_REQUIRED} analyzed games"
        }
    
    game_ids = [a["game_id"] for a in valid_analyses]
    games = await db.games.find(
        {"game_id": {"$in": game_ids}},
        {"game_id": 1, "result": 1, "user_color": 1}
    ).to_list(length=len(game_ids))
    
    # Compute layer costs
    stability = compute_stability_cost(valid_analyses, games)
    conversion = compute_conversion_cost(valid_analyses, games)
    structure = compute_structure_cost(valid_analyses, games)
    precision = compute_precision_cost(valid_analyses, games)
    
    layer_costs = {
        "stability": stability,
        "conversion": conversion,
        "structure": structure,
        "precision": precision,
    }
    
    # Select active phase (highest cost OR preserved from graduation)
    if graduated_phase and preserve_phase:
        active_phase = graduated_phase
    else:
        active_phase = max(layer_costs.keys(), key=lambda k: layer_costs[k]["cost"])
    active_layer = layer_costs[active_phase]
    
    # Select micro habit (highest pattern weight in active layer)
    pattern_weights = active_layer.get("pattern_weights", {})
    if pattern_weights:
        micro_habit = max(pattern_weights.keys(), key=lambda k: pattern_weights[k])
    else:
        micro_habit = TRAINING_LAYERS[active_phase]["patterns"][0]
    
    # Get rules for micro habit
    rating_tier = get_rating_tier(rating)
    rules = RULES_DATABASE.get(active_phase, {}).get(micro_habit, {}).get(rating_tier, [
        "Focus on one concept per game",
        "Review your mistakes after each game"
    ])
    
    # Build training profile
    profile = {
        "user_id": user_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "games_analyzed": len(valid_analyses),
        "rating_at_computation": rating,
        "rating_tier": rating_tier,
        
        # Core training focus
        "active_phase": active_phase,
        "active_phase_label": TRAINING_LAYERS[active_phase]["label"],
        "active_phase_description": TRAINING_LAYERS[active_phase]["description"],
        "phase_cost": active_layer["cost"],
        "phase_started_at": phase_started_at or datetime.now(timezone.utc).isoformat(),
        
        # Micro habit
        "micro_habit": micro_habit,
        "micro_habit_label": PATTERN_INFO.get(micro_habit, {}).get("label", micro_habit),
        "micro_habit_description": PATTERN_INFO.get(micro_habit, {}).get("description", ""),
        "pattern_weights": pattern_weights,
        
        # Rules
        "rules": rules,
        
        # Full breakdown
        "layer_breakdown": {
            phase: {
                "cost": data["cost"],
                "label": TRAINING_LAYERS[phase]["label"],
                "is_active": phase == active_phase,
            }
            for phase, data in layer_costs.items()
        },
        
        # Example positions for drills
        "example_positions": active_layer.get("example_positions", [])[:5],
        
        # Reflection question
        "reflection_question": PATTERN_INFO.get(micro_habit, {}).get("question", "What happened in this game?"),
    }
    
    # Store profile
    await db.training_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )
    
    return profile


async def get_training_profile(db, user_id: str) -> Optional[Dict]:
    """Get existing training profile for user."""
    return await db.training_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )


async def get_or_generate_training_profile(db, user_id: str, rating: int = 1200, force_regenerate: bool = False) -> Dict:
    """
    Get existing profile or generate new one.
    
    Regenerates if:
    - No profile exists
    - force_regenerate is True
    - Profile is older than 7 games
    
    When regenerating after graduation, preserves the active_phase.
    """
    existing = await get_training_profile(db, user_id)
    
    if not force_regenerate:
        if existing and existing.get("status") != "insufficient_data":
            # Check if we need to recalculate
            games_at_calc = existing.get("games_analyzed", 0)
            current_games = await db.game_analyses.count_documents({"user_id": user_id})
            
            if current_games - games_at_calc < RECALC_THRESHOLD:
                return existing
    
    # Check if there was a recent graduation - preserve phase
    preserve_phase = False
    if existing and existing.get("graduation_history"):
        grad_time = existing.get("graduation_history", {}).get("graduated_at")
        if grad_time:
            # If graduated within last day, preserve phase
            try:
                grad_dt = datetime.fromisoformat(grad_time.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) - grad_dt < timedelta(days=1):
                    preserve_phase = True
            except Exception:
                pass
    
    return await generate_training_profile(db, user_id, rating, preserve_phase=preserve_phase)


# =============================================================================
# REFLECTION SYSTEM
# =============================================================================

async def save_reflection(db, user_id: str, game_id: str, reflection_data: Dict) -> Dict:
    """
    Save a user reflection for a game.
    
    reflection_data should contain:
    - selected_tags: list of pattern tags user selected
    - free_text: optional free-form reflection
    """
    reflection = {
        "user_id": user_id,
        "game_id": game_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_tags": reflection_data.get("selected_tags", []),
        "free_text": reflection_data.get("free_text", ""),
    }
    
    await db.reflections.insert_one(reflection)
    
    # Update pattern weights based on reflection
    profile = await get_training_profile(db, user_id)
    if profile:
        pattern_weights = profile.get("pattern_weights", {})
        for tag in reflection_data.get("selected_tags", []):
            if tag in pattern_weights:
                # Nudge the weight up slightly
                pattern_weights[tag] = min(1.0, pattern_weights[tag] + 0.02)
        
        # Normalize weights
        total = sum(pattern_weights.values())
        if total > 0:
            pattern_weights = {k: round(v / total, 3) for k, v in pattern_weights.items()}
        
        await db.training_profiles.update_one(
            {"user_id": user_id},
            {"$set": {"pattern_weights": pattern_weights}}
        )
    
    return {"status": "saved", "reflection_id": str(reflection.get("_id", ""))}


async def get_reflection_options(db, user_id: str) -> Dict:
    """Get reflection options based on user's active phase."""
    profile = await get_training_profile(db, user_id)
    if not profile:
        return {"options": []}
    
    active_phase = profile.get("active_phase", "stability")
    patterns = TRAINING_LAYERS.get(active_phase, {}).get("patterns", [])
    
    options = []
    for pattern in patterns:
        info = PATTERN_INFO.get(pattern, {})
        options.append({
            "tag": pattern,
            "label": info.get("label", pattern),
            "question": info.get("question", ""),
        })
    
    return {
        "phase": active_phase,
        "phase_label": TRAINING_LAYERS.get(active_phase, {}).get("label", ""),
        "options": options,
    }


# =============================================================================
# DRILL SOURCING
# =============================================================================

async def get_drill_positions(db, user_id: str, limit: int = 5) -> List[Dict]:
    """
    Get drill positions for user.
    
    Sources:
    1. User's own mistakes (priority)
    2. Similar users' mistakes (same rating band, same micro habit)
    """
    profile = await get_training_profile(db, user_id)
    if not profile or profile.get("status") == "insufficient_data":
        return []
    
    drills = []
    
    # 1. User's own mistakes
    own_positions = profile.get("example_positions", [])
    for pos in own_positions[:3]:
        drills.append({
            "source": "own_game",
            "game_id": pos.get("game_id"),
            "fen": pos.get("fen"),
            "correct_move": pos.get("best_move"),
            "user_move": pos.get("move"),
            "cp_loss": pos.get("cp_loss"),
        })
    
    # 2. Similar users' mistakes (if we need more)
    if len(drills) < limit:
        rating = profile.get("rating_at_computation", 1200)
        rating_min = rating - 200
        rating_max = rating + 200
        micro_habit = profile.get("micro_habit", "")
        
        # Find similar users
        similar_profiles = await db.training_profiles.find({
            "user_id": {"$ne": user_id},
            "micro_habit": micro_habit,
            "rating_at_computation": {"$gte": rating_min, "$lte": rating_max},
        }).limit(10).to_list(length=10)
        
        for sp in similar_profiles:
            for pos in sp.get("example_positions", [])[:2]:
                if len(drills) >= limit:
                    break
                drills.append({
                    "source": "similar_user",
                    "fen": pos.get("fen"),
                    "correct_move": pos.get("best_move"),
                    "user_move": pos.get("move"),
                    "cp_loss": pos.get("cp_loss"),
                })
    
    return drills[:limit]



# =============================================================================
# ENHANCED REFLECTION SYSTEM - Per-Position, Contextual
# =============================================================================

# Rating-based thresholds for what counts as "relevant" mistake
RATING_MISTAKE_THRESHOLDS = {
    "beginner": {  # < 1000
        "min_cp_loss": 200,  # Only blunders
        "categories": ["blunder"],
    },
    "intermediate": {  # 1000-1400
        "min_cp_loss": 150,  # Blunders and big mistakes
        "categories": ["blunder", "mistake"],
    },
    "club": {  # 1400-1800
        "min_cp_loss": 100,  # All mistakes
        "categories": ["blunder", "mistake"],
    },
    "advanced": {  # 1800+
        "min_cp_loss": 50,  # Including inaccuracies
        "categories": ["blunder", "mistake", "inaccuracy"],
    },
}

def get_rating_category(rating: int) -> str:
    """Get rating category for filtering mistakes."""
    if rating < 1000:
        return "beginner"
    elif rating < 1400:
        return "intermediate"
    elif rating < 1800:
        return "club"
    return "advanced"


def generate_contextual_options(position_data: Dict, phase: str) -> List[Dict]:
    """
    Generate contextual reflection options based on the specific position.
    Not generic "rushing" but position-specific options.
    """
    options = []
    cp_loss = position_data.get("cp_loss", 0)
    eval_before = position_data.get("eval_before", 0)
    eval_after = position_data.get("eval_after", 0)
    has_threat = position_data.get("threat") is not None
    move_number = position_data.get("move_number", 0)
    game_phase = "opening" if move_number <= 12 else "middlegame" if move_number <= 30 else "endgame"
    
    # Position-specific options based on what happened
    if has_threat:
        options.append({
            "tag": "missed_threat",
            "label": "I didn't see their threat",
            "contextual": True,
        })
    
    if cp_loss >= 300:  # Hanging piece level
        options.append({
            "tag": "piece_safety",
            "label": "I forgot to check if my piece was safe",
            "contextual": True,
        })
    
    if eval_before >= 150 and eval_after < 50:  # Lost winning position
        options.append({
            "tag": "lost_advantage",
            "label": "I was winning and got careless",
            "contextual": True,
        })
    
    if game_phase == "opening":
        options.append({
            "tag": "opening_unfamiliar",
            "label": "I wasn't sure what to do in this opening",
            "contextual": True,
        })
    
    if game_phase == "endgame":
        options.append({
            "tag": "endgame_technique",
            "label": "I didn't know the right endgame plan",
            "contextual": True,
        })
    
    # Always include these general options
    options.append({
        "tag": "time_pressure",
        "label": "I was low on time",
        "contextual": False,
    })
    options.append({
        "tag": "saw_but_miscalculated",
        "label": "I saw the move but miscalculated the line",
        "contextual": False,
    })
    options.append({
        "tag": "didnt_consider",
        "label": "I didn't even consider the better move",
        "contextual": False,
    })
    options.append({
        "tag": "tunnel_vision",
        "label": "I was focused on my own plan",
        "contextual": False,
    })
    
    return options


async def get_game_milestones_for_reflection(
    db, 
    user_id: str, 
    game_id: str, 
    rating: int = 1200
) -> Dict:
    """
    Get ALL relevant mistakes/milestones from a specific game for reflection.
    Filtered by rating (higher rated = finer grained feedback).
    
    Returns rich context per position:
    - FEN, move played, better move
    - Why better (from Stockfish data, to be humanized by GPT)
    - What was the threat
    - Contextual reflection options
    - PV lines for interactive board
    """
    # Get rating category
    rating_cat = get_rating_category(rating)
    thresholds = RATING_MISTAKE_THRESHOLDS[rating_cat]
    min_cp = thresholds["min_cp_loss"]
    categories = thresholds["categories"]
    
    # Fetch the analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"stockfish_analysis": 1, "game_id": 1}
    )
    
    if not analysis:
        return {"milestones": [], "error": "Game analysis not found"}
    
    # Fetch game info
    game = await db.games.find_one(
        {"game_id": game_id},
        {"user_color": 1, "result": 1}
    )
    user_color = game.get("user_color", "white") if game else "white"
    
    sf = analysis.get("stockfish_analysis", {})
    move_evals = sf.get("move_evaluations", [])
    
    milestones = []
    
    for m in move_evals:
        # Only user's moves
        is_user_move = m.get("is_user_move", False)
        if not is_user_move:
            # Check by FEN if is_user_move not set
            fen = m.get("fen_before", "")
            parts = fen.split(" ")
            if len(parts) > 1:
                turn = parts[1]
                is_user_move = (user_color == "white" and turn == "w") or (user_color == "black" and turn == "b")
        
        if not is_user_move:
            continue
        
        cp_loss = abs(m.get("cp_loss", 0))
        evaluation = m.get("evaluation", "")
        if hasattr(evaluation, "value"):
            evaluation = evaluation.value
        
        # Filter by rating threshold
        if cp_loss < min_cp:
            continue
        
        # Check category
        if evaluation.lower() not in categories and cp_loss < 200:
            continue
        
        # Build rich milestone data
        milestone = {
            "move_number": m.get("move_number"),
            "fen": m.get("fen_before"),
            "user_move": m.get("move"),
            "best_move": m.get("best_move"),
            "cp_loss": cp_loss,
            "eval_before": m.get("eval_before", 0),
            "eval_after": m.get("eval_after", 0),
            "evaluation_type": evaluation,
            
            # For interactive board
            "pv_after_best": m.get("pv_after_best", []),
            "pv_after_played": m.get("pv_after_played", []),
            
            # Threat info
            "threat": m.get("threat"),
            "threat_line": m.get("details", {}).get("threat_line") if m.get("details") else None,
            
            # Contextual options (generated per position)
            "reflection_options": generate_contextual_options(m, "stability"),
            
            # Context for GPT explanation
            "context_for_explanation": {
                "move_played": m.get("move"),
                "best_move": m.get("best_move"),
                "cp_loss": cp_loss,
                "eval_before": m.get("eval_before", 0),
                "eval_after": m.get("eval_after", 0),
                "threat": m.get("threat"),
                "pv_best": m.get("pv_after_best", [])[:5],  # First 5 moves of best line
                "pv_played": m.get("pv_after_played", [])[:5],
            }
        }
        
        milestones.append(milestone)
    
    # Sort by cp_loss (worst mistakes first)
    milestones.sort(key=lambda x: x["cp_loss"], reverse=True)
    
    return {
        "game_id": game_id,
        "user_color": user_color,
        "rating_category": rating_cat,
        "min_cp_threshold": min_cp,
        "milestones": milestones,
        "total_count": len(milestones),
    }


async def generate_position_explanation(
    db,
    milestone: Dict,
    use_llm: bool = True
) -> Dict:
    """
    Generate human-readable explanation for why the better move is better.
    Uses Stockfish data (deterministic) + GPT for natural language.
    """
    context = milestone.get("context_for_explanation", {})
    
    # Build deterministic chess context from Stockfish
    move_played = context.get("move_played", "?")
    best_move = context.get("best_move", "?")
    cp_loss = context.get("cp_loss", 0)
    eval_before = context.get("eval_before", 0) / 100
    eval_after = context.get("eval_after", 0) / 100
    threat = context.get("threat")
    pv_best = context.get("pv_best", [])
    pv_played = context.get("pv_played", [])
    
    # Deterministic analysis
    stockfish_explanation = {
        "eval_swing": f"Position went from {eval_before:+.1f} to {eval_after:+.1f}",
        "cp_lost": f"Lost {cp_loss/100:.1f} pawns worth of advantage",
    }
    
    if threat:
        stockfish_explanation["threat_missed"] = f"You missed the threat: {threat}"
    
    if pv_best:
        stockfish_explanation["better_line"] = f"Better continuation: {' '.join(pv_best[:4])}"
    
    if pv_played:
        stockfish_explanation["played_line_consequence"] = f"Your move leads to: {' '.join(pv_played[:4])}"
    
    # Position type
    if eval_before >= 1.5:
        stockfish_explanation["position_context"] = "You were winning"
    elif eval_before <= -1.5:
        stockfish_explanation["position_context"] = "You were losing"
    else:
        stockfish_explanation["position_context"] = "Position was roughly equal"
    
    return {
        "stockfish_analysis": stockfish_explanation,
        "move_played": move_played,
        "best_move": best_move,
        "needs_llm_humanization": use_llm,
        "llm_prompt": f"""Based on this chess position analysis, write a clear 2-3 sentence explanation for a {milestone.get('rating_category', 'club')} level player:

Position: {stockfish_explanation.get('position_context', 'unclear')}
You played: {move_played}
Better was: {best_move}
{stockfish_explanation.get('threat_missed', '')}
{stockfish_explanation.get('better_line', '')}
What happens after your move: {stockfish_explanation.get('played_line_consequence', '')}

Explain WHY {best_move} is better in simple terms. Focus on the concrete consequence, not abstract concepts."""
    }


async def save_position_reflection(
    db,
    user_id: str,
    game_id: str,
    move_number: int,
    reflection_data: Dict
) -> Dict:
    """
    Save reflection for a SPECIFIC position (not whole game).
    
    reflection_data:
    - selected_tags: List of contextual tags selected
    - user_plan: What the user was thinking/planning
    - understood: Whether user understood the explanation
    """
    reflection = {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": move_number,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_tags": reflection_data.get("selected_tags", []),
        "user_plan": reflection_data.get("user_plan", ""),  # What was user thinking
        "understood": reflection_data.get("understood", True),
        "fen": reflection_data.get("fen", ""),
    }
    
    await db.position_reflections.insert_one(reflection)
    
    # Update pattern weights based on tags
    profile = await get_training_profile(db, user_id)
    if profile:
        pattern_weights = profile.get("pattern_weights", {})
        
        # Map contextual tags to patterns
        tag_to_pattern = {
            "missed_threat": "threat_blindness",
            "piece_safety": "hanging_pieces",
            "lost_advantage": "overconfidence",
            "time_pressure": "time_pressure",
            "saw_but_miscalculated": "shallow_calculation",
            "didnt_consider": "rushing",
            "tunnel_vision": "aimless_play",
            "opening_unfamiliar": "opening_deviation",
            "endgame_technique": "endgame_technique",
        }
        
        for tag in reflection_data.get("selected_tags", []):
            pattern = tag_to_pattern.get(tag)
            if pattern and pattern in pattern_weights:
                pattern_weights[pattern] = min(1.0, pattern_weights[pattern] + 0.03)
        
        # Normalize
        total = sum(pattern_weights.values())
        if total > 0:
            pattern_weights = {k: round(v / total, 3) for k, v in pattern_weights.items()}
        
        await db.training_profiles.update_one(
            {"user_id": user_id},
            {"$set": {"pattern_weights": pattern_weights}}
        )
    
    return {"status": "saved", "move_number": move_number}



# =============================================================================
# REFLECTION HISTORY & AI INSIGHTS
# =============================================================================

async def get_reflection_history(db, user_id: str, limit: int = 50) -> Dict:
    """
    Get user's reflection history with pattern evolution over time.
    
    Returns:
    - reflections: List of past reflections with context
    - pattern_evolution: How pattern weights changed over time
    - summary_stats: Aggregated statistics
    """
    # Fetch reflections
    cursor = db.position_reflections.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    
    reflections = await cursor.to_list(length=limit)
    
    # Calculate pattern evolution (aggregate tags over time)
    tag_counts = {}
    plans = []
    
    for r in reflections:
        for tag in r.get("selected_tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        if r.get("user_plan"):
            plans.append({
                "plan": r["user_plan"],
                "tags": r.get("selected_tags", []),
                "created_at": r.get("created_at"),
                "move_number": r.get("move_number"),
            })
    
    # Calculate percentages
    total_tags = sum(tag_counts.values())
    tag_percentages = {}
    if total_tags > 0:
        tag_percentages = {k: round(v / total_tags * 100, 1) for k, v in tag_counts.items()}
    
    # Sort by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "reflections": reflections,
        "total_reflections": len(reflections),
        "tag_counts": dict(sorted_tags),
        "tag_percentages": tag_percentages,
        "top_patterns": sorted_tags[:5],
        "user_plans": plans,
    }


async def analyze_user_thinking_patterns(db, user_id: str) -> Dict:
    """
    Use AI to analyze common phrases and patterns in user's written plans.
    
    Returns insights about:
    - Common themes in their thinking
    - Recurring mistakes in reasoning
    - Specific suggestions based on their patterns
    """
    # Get reflection history
    history = await get_reflection_history(db, user_id, limit=30)
    plans = history.get("user_plans", [])
    tag_counts = history.get("tag_counts", {})
    
    if len(plans) < 3:
        return {
            "has_enough_data": False,
            "message": "Need at least 3 reflections to analyze patterns",
            "reflections_count": len(plans),
        }
    
    # Build context for AI
    plans_text = "\n".join([
        f"- Move {p['move_number']}: \"{p['plan']}\" (Tags: {', '.join(p['tags'])})"
        for p in plans[:20]
    ])
    
    top_tags = ", ".join([f"{tag} ({count}x)" for tag, count in list(tag_counts.items())[:5]])
    
    return {
        "has_enough_data": True,
        "plans_for_analysis": plans_text,
        "top_tags": top_tags,
        "total_reflections": len(plans),
        "analysis_prompt": f"""Analyze this chess player's thinking patterns from their reflections:

WHAT THEY WROTE DURING MISTAKES:
{plans_text}

MOST COMMON ISSUES THEY IDENTIFIED:
{top_tags}

Based on this data:
1. THINKING PATTERNS: What recurring themes or habits do you see in their thought process? (2-3 key patterns)
2. ROOT CAUSE: What seems to be the underlying issue causing their mistakes?
3. SPECIFIC SUGGESTIONS: Give 2-3 concrete, actionable suggestions tailored to THEIR specific patterns. Reference their actual words.

Keep response under 200 words. Be direct and specific, not generic."""
    }


async def generate_personalized_suggestions(db, user_id: str) -> Dict:
    """
    Generate AI-powered suggestions based on user's reflection history.
    """
    analysis_data = await analyze_user_thinking_patterns(db, user_id)
    
    if not analysis_data.get("has_enough_data"):
        return analysis_data
    
    # This will be called by the API endpoint which uses GPT
    return {
        "ready_for_ai": True,
        "prompt": analysis_data["analysis_prompt"],
        "context": {
            "total_reflections": analysis_data["total_reflections"],
            "top_tags": analysis_data["top_tags"],
        }
    }



# =============================================================================
# PHASE PROGRESS TRACKING & AUTO-GRADUATION
# =============================================================================

async def get_phase_progress(db, user_id: str) -> Dict:
    """
    Calculate user's progress within their current training phase.
    Automatically graduates user when criteria met.
    
    Returns:
    - tier: Current tier info
    - phase: Current phase within tier
    - progress: Progress metrics
    - stats: Phase-specific statistics
    """
    # Get user rating
    user_doc = await db.users.find_one({"user_id": user_id})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    
    # Get current profile
    profile = await get_training_profile(db, user_id)
    if not profile:
        return {"error": "No training profile found"}
    
    # Determine tier based on rating
    current_tier_id = get_tier_for_rating(rating)
    current_tier = TRAINING_TIERS[current_tier_id]
    
    # Get current phase index (stored in profile or default to 0)
    phase_index = profile.get("phase_index", 0)
    if phase_index >= len(current_tier["phases"]):
        phase_index = 0  # Reset if tier changed
    
    current_phase = current_tier["phases"][phase_index]
    
    # Fetch recent analyses
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1, "analyzed_at": 1, "metrics": 1}
    ).sort("analyzed_at", -1).limit(GRADUATION_GAMES)
    
    analyses = await cursor.to_list(length=GRADUATION_GAMES)
    
    if len(analyses) < 3:
        return {
            "tier_id": current_tier_id,
            "tier_label": current_tier["label"],
            "tier_rating_range": current_tier["rating_range"],
            "phase": current_phase,
            "phase_index": phase_index,
            "total_phases": len(current_tier["phases"]),
            "games_played": len(analyses),
            "games_needed": GRADUATION_GAMES,
            "progress_percent": int((len(analyses) / GRADUATION_GAMES) * 100),
            "message": f"Play {GRADUATION_GAMES - len(analyses)} more games to track progress",
            "stats": {},
            "ready_to_graduate": False,
        }
    
    # Calculate phase-specific stats
    stats = await _calculate_phase_specific_stats(analyses, current_phase, rating)
    
    # Check graduation criteria
    metric_value = stats.get("metric_value", 999)
    target = current_phase.get("target", 1.0)
    clean_games = stats.get("clean_games", 0)
    
    # Progress calculation
    if target > 0:
        metric_progress = max(0, min(100, int((1 - metric_value / (target * 2)) * 100)))
    else:
        metric_progress = 100 if metric_value <= target else 0
    
    games_progress = int((len(analyses) / GRADUATION_GAMES) * 100)
    clean_progress = int((clean_games / max(CLEAN_GAMES_FOR_GRADUATION, 1)) * 100)
    
    overall_progress = int((metric_progress * 0.5 + games_progress * 0.2 + clean_progress * 0.3))
    
    # Check if ready to graduate
    meets_metric = metric_value <= target
    meets_clean = clean_games >= CLEAN_GAMES_FOR_GRADUATION
    ready_to_graduate = len(analyses) >= GRADUATION_GAMES and (meets_metric or meets_clean)
    
    # AUTO-GRADUATE if ready
    graduation_result = None
    if ready_to_graduate:
        graduation_result = await _auto_graduate_phase(db, user_id, current_tier_id, phase_index, stats)
    
    return {
        "tier_id": current_tier_id,
        "tier_label": current_tier["label"],
        "tier_rating_range": current_tier["rating_range"],
        "phase": current_phase,
        "phase_index": phase_index,
        "total_phases": len(current_tier["phases"]),
        "games_played": len(analyses),
        "games_needed": GRADUATION_GAMES,
        "progress_percent": overall_progress,
        "stats": stats,
        "meets_metric": meets_metric,
        "meets_clean": meets_clean,
        "ready_to_graduate": ready_to_graduate,
        "graduated": graduation_result,
        "rating": rating,
    }


async def _calculate_phase_specific_stats(analyses: List[Dict], phase: Dict, rating: int) -> Dict:
    """Calculate stats specific to the current phase."""
    phase_id = phase.get("id", "")
    metric = phase.get("metric", "")
    target = phase.get("target", 1.0)
    clean_threshold = phase.get("clean_game_threshold", 0)
    
    stats = {
        "phase_id": phase_id,
        "metric_name": metric,
        "target": target,
        "games_analyzed": len(analyses),
        "clean_games": 0,
        "metric_value": 0,
        "trend": "stable",
        "trend_icon": "→",
    }
    
    # Calculate based on phase type
    total_metric = 0
    clean_count = 0
    per_game_values = []
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        game_metrics = analysis.get("metrics", {})
        game_value = 0
        
        if phase_id in ["piece_safety", "hanging_pieces", "blunder_reduction"]:
            # Count blunders/hanging pieces
            game_value = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= BLUNDER_THRESHOLD)
            
        elif phase_id in ["check_awareness", "threat_detection"]:
            # Count missed threats
            game_value = sum(1 for m in move_evals if m.get("threat") and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            
        elif phase_id in ["capture_awareness"]:
            # Count missed winning captures
            game_value = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP and "x" in (m.get("best_move", "") or ""))
            
        elif phase_id in ["opening_principles", "opening_mistakes"]:
            # Count opening mistakes (first 12 moves)
            game_value = sum(1 for m in move_evals if m.get("move_number", 100) <= 12 and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            
        elif phase_id in ["advantage_maintenance", "eval_drops"]:
            # Count eval drops when winning
            game_value = game_metrics.get("eval_drops_when_winning", 0)
            
        elif phase_id in ["calculation_depth", "tactical_misses", "complex_tactics"]:
            # Count tactical misses
            game_value = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            
        elif phase_id in ["endgame_basics", "endgame_mistakes"]:
            # Count endgame mistakes (after move 30)
            game_value = sum(1 for m in move_evals if m.get("move_number", 0) > 30 and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            
        else:
            # Default: count significant mistakes
            game_value = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
        
        per_game_values.append(game_value)
        total_metric += game_value
        
        # Check if this is a "clean" game for this phase
        if game_value <= clean_threshold:
            clean_count += 1
    
    # Calculate average
    avg_value = total_metric / len(analyses) if analyses else 0
    stats["metric_value"] = round(avg_value, 2)
    stats["clean_games"] = clean_count
    
    # Calculate trend (first half vs second half)
    if len(per_game_values) >= 4:
        half = len(per_game_values) // 2
        first_half = sum(per_game_values[half:]) / half
        second_half = sum(per_game_values[:half]) / half
        
        if first_half > 0:
            improvement = (first_half - second_half) / first_half
            stats["improvement_percent"] = int(improvement * 100)
            
            if improvement > 0.1:
                stats["trend"] = "improving"
                stats["trend_icon"] = "↓"
            elif improvement < -0.1:
                stats["trend"] = "regressing"
                stats["trend_icon"] = "↑"
    
    # Human-readable stat description
    stats["stat_description"] = f"{avg_value:.1f} {metric.replace('_', ' ')} (target: ≤{target})"
    
    return stats


async def _auto_graduate_phase(db, user_id: str, tier_id: str, phase_index: int, stats: Dict) -> Dict:
    """Automatically graduate user to next phase."""
    tier = TRAINING_TIERS[tier_id]
    total_phases = len(tier["phases"])
    
    # Check if there's a next phase in this tier
    if phase_index + 1 < total_phases:
        # Move to next phase in same tier
        next_phase_index = phase_index + 1
        next_phase = tier["phases"][next_phase_index]
        
        await db.training_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "phase_index": next_phase_index,
                    "phase_started_at": datetime.now(timezone.utc).isoformat(),
                },
                "$push": {
                    "graduation_log": {
                        "tier": tier_id,
                        "from_phase": phase_index,
                        "to_phase": next_phase_index,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "stats": stats,
                    }
                }
            }
        )
        
        return {
            "graduated": True,
            "type": "phase",
            "from_phase": tier["phases"][phase_index]["label"],
            "to_phase": next_phase["label"],
            "tier": tier["label"],
            "message": f"Phase complete! Moving from {tier['phases'][phase_index]['label']} to {next_phase['label']}",
        }
    else:
        # Completed all phases in tier - ready for next tier
        # Don't auto-advance tier - that depends on rating improvement
        await db.training_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "tier_completed": True,
                    "tier_completed_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        )
        
        return {
            "graduated": True,
            "type": "tier_complete",
            "tier": tier["label"],
            "message": f"Congratulations! You've mastered all {tier['label']} phases! Keep playing to increase your rating and unlock the next tier.",
        }


async def _calculate_phase_metrics(analyses: List[Dict], phase: str) -> Dict:
    """Calculate phase-specific metrics from game analyses."""
    metrics = {
        "total_games": len(analyses),
        "avg_errors_per_game": 0,
        "total_errors": 0,
    }
    
    total_errors = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        game_metrics = analysis.get("metrics", {})
        
        if phase == "stability":
            # Count blunders and hanging pieces
            blunders = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= BLUNDER_THRESHOLD)
            total_errors += blunders
        
        elif phase == "conversion":
            # Count eval drops when winning
            drops = game_metrics.get("eval_drops_when_winning", 0)
            total_errors += drops
        
        elif phase == "structure":
            # Count opening mistakes (first 24 half-moves)
            opening_mistakes = sum(
                1 for m in move_evals 
                if m.get("move_number", 100) <= 12 and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP
            )
            total_errors += opening_mistakes
        
        elif phase == "precision":
            # Count tactical misses (complex positions)
            tactical = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            total_errors += tactical
    
    metrics["total_errors"] = total_errors
    metrics["avg_errors_per_game"] = round(total_errors / len(analyses), 2) if analyses else 0
    
    return metrics


def _count_clean_games(analyses: List[Dict], phase: str) -> int:
    """Count games that meet 'clean' criteria for the phase."""
    thresholds = CLEAN_GAME_THRESHOLDS.get(phase, {})
    clean_count = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        game_metrics = analysis.get("metrics", {})
        
        is_clean = True
        
        if phase == "stability":
            blunders = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= BLUNDER_THRESHOLD)
            total_loss = sum(abs(m.get("cp_loss", 0)) for m in move_evals)
            
            if blunders > thresholds.get("max_blunders", 0):
                is_clean = False
            if total_loss > thresholds.get("max_cp_loss_total", 400):
                is_clean = False
        
        elif phase == "conversion":
            drops = game_metrics.get("eval_drops_when_winning", 0)
            if drops > thresholds.get("max_eval_drops_when_winning", 1):
                is_clean = False
        
        elif phase == "structure":
            opening_mistakes = sum(
                1 for m in move_evals 
                if m.get("move_number", 100) <= 12 and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP
            )
            if opening_mistakes > thresholds.get("max_opening_mistakes", 1):
                is_clean = False
        
        elif phase == "precision":
            tactical = sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
            if tactical > thresholds.get("max_tactical_misses", 2):
                is_clean = False
        
        if is_clean:
            clean_count += 1
    
    return clean_count


def _get_phase_error_rate(analyses: List[Dict], phase: str) -> float:
    """Get average error rate for phase across games."""
    if not analyses:
        return 0
    
    total_errors = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        game_metrics = analysis.get("metrics", {})
        
        if phase == "stability":
            total_errors += sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= BLUNDER_THRESHOLD)
        elif phase == "conversion":
            total_errors += game_metrics.get("eval_drops_when_winning", 0)
        elif phase == "structure":
            total_errors += sum(
                1 for m in move_evals 
                if m.get("move_number", 100) <= 12 and abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP
            )
        elif phase == "precision":
            total_errors += sum(1 for m in move_evals if abs(m.get("cp_loss", 0)) >= SIGNIFICANT_DROP)
    
    return total_errors / len(analyses)


async def check_and_graduate_phase(db, user_id: str) -> Dict:
    """
    Check if user is ready to graduate from current phase.
    If ready, automatically move them to the next phase.
    """
    progress = await get_phase_progress(db, user_id)
    
    if not progress.get("ready_to_graduate"):
        return {
            "graduated": False,
            "current_phase": progress.get("active_phase"),
            "progress": progress,
        }
    
    # Graduation logic - move to next phase
    current_phase = progress.get("active_phase")
    
    # Get fresh cost scores to determine next phase
    profile = await get_training_profile(db, user_id)
    layer_breakdown = profile.get("layer_breakdown", {})
    
    # Find next highest cost phase (excluding current)
    phases_by_cost = sorted(
        [(phase, data.get("cost", 0)) for phase, data in layer_breakdown.items() if phase != current_phase],
        key=lambda x: x[1],
        reverse=True
    )
    
    next_phase = phases_by_cost[0][0] if phases_by_cost else "stability"
    
    # Update profile with new phase
    await db.training_profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "active_phase": next_phase,
                "phase_started_at": datetime.now(timezone.utc).isoformat(),
                "previous_phase": current_phase,
                "graduation_history": {
                    "from_phase": current_phase,
                    "to_phase": next_phase,
                    "graduated_at": datetime.now(timezone.utc).isoformat(),
                    "games_played": progress.get("games_in_phase"),
                    "improvement": progress.get("improvement_percent"),
                }
            },
            "$push": {
                "graduation_log": {
                    "from": current_phase,
                    "to": next_phase,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            }
        }
    )
    
    # Force recalculate profile for new phase
    await get_or_generate_training_profile(db, user_id, force_regenerate=True)
    
    return {
        "graduated": True,
        "from_phase": current_phase,
        "to_phase": next_phase,
        "message": f"Congratulations! You've graduated from {current_phase.title()} to {next_phase.title()}!",
    }
