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
# LAYER DEFINITIONS
# =============================================================================

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
            eval_before = m.get("eval_before", 0)
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
            eval_after = m.get("eval_after", 0)
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
    total_games = len(analyses) if analyses else 1
    
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
# MAIN TRAINING PROFILE GENERATION
# =============================================================================

async def generate_training_profile(db, user_id: str, rating: int = 1200) -> Dict:
    """
    Generate a complete training profile for a user.
    
    Returns:
    - active_phase: highest cost layer
    - micro_habit: dominant pattern within phase
    - rules: 2 actionable rules for the week
    - layer_breakdown: costs for all 4 layers
    - drill_positions: positions for practice
    """
    # Fetch analyzed games
    analyses = await db.analyses.find(
        {"user_id": user_id},
        {"stockfish_analysis": 1, "game_id": 1}
    ).sort("analyzed_at", -1).limit(DEFAULT_GAME_WINDOW).to_list(length=DEFAULT_GAME_WINDOW)
    
    if len(analyses) < MIN_GAMES_REQUIRED:
        return {
            "status": "insufficient_data",
            "games_analyzed": len(analyses),
            "games_required": MIN_GAMES_REQUIRED,
            "message": f"Need at least {MIN_GAMES_REQUIRED} analyzed games"
        }
    
    game_ids = [a["game_id"] for a in analyses]
    games = await db.games.find(
        {"game_id": {"$in": game_ids}},
        {"game_id": 1, "result": 1, "user_color": 1}
    ).to_list(length=len(game_ids))
    
    # Compute layer costs
    stability = compute_stability_cost(analyses, games)
    conversion = compute_conversion_cost(analyses, games)
    structure = compute_structure_cost(analyses, games)
    precision = compute_precision_cost(analyses, games)
    
    layer_costs = {
        "stability": stability,
        "conversion": conversion,
        "structure": structure,
        "precision": precision,
    }
    
    # Select active phase (highest cost)
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
        "games_analyzed": len(analyses),
        "rating_at_computation": rating,
        "rating_tier": rating_tier,
        
        # Core training focus
        "active_phase": active_phase,
        "active_phase_label": TRAINING_LAYERS[active_phase]["label"],
        "active_phase_description": TRAINING_LAYERS[active_phase]["description"],
        "phase_cost": active_layer["cost"],
        
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
    """
    if not force_regenerate:
        existing = await get_training_profile(db, user_id)
        if existing and existing.get("status") != "insufficient_data":
            # Check if we need to recalculate
            games_at_calc = existing.get("games_analyzed", 0)
            current_games = await db.analyses.count_documents({"user_id": user_id})
            
            if current_games - games_at_calc < RECALC_THRESHOLD:
                return existing
    
    return await generate_training_profile(db, user_id, rating)


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
