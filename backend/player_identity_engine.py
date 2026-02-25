"""
Player Identity Engine

A sophisticated, data-driven identity system that feels:
- Intelligent
- Personal  
- Sharp
- Emotionally accurate

NOT:
- Dashboard-like
- Psychological jargon
- Static personality test

The identity evolves as the player improves.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import math
import logging

logger = logging.getLogger(__name__)


# ============================================
# IDENTITY INTERPRETATION MAPPINGS
# ============================================

# Decision Stability → Human-readable interpretation
STABILITY_INTERPRETATIONS = {
    "stable": {
        "label": "Consistently Reliable",
        "summary_desc": "maintains a steady level",
        "explanation": "Your performance is predictable. You rarely have unexpectedly bad games, and your accuracy stays within a tight range.",
    },
    "mixed": {
        "label": "Inconsistent but Capable",
        "summary_desc": "fluctuates between sessions",
        "explanation": "You can play at a high level, but your performance varies. Some days are sharp, others less focused.",
    },
    "volatile": {
        "label": "Unstable Under Pressure",
        "summary_desc": "swings significantly between games",
        "explanation": "You can play at a high level, but your accuracy drops sharply after one mistake or in critical positions.",
    },
}

# Primary Pattern → Human-readable interpretation
LEAK_INTERPRETATIONS = {
    "calculation_depth": {
        "label": "Stopping Calculation Too Early",
        "summary_desc": "shallow calculation",
        "explanation": "Most of your serious mistakes happen because opponent responses are not fully calculated before committing to a move.",
    },
    "threat_blindness": {
        "label": "Missing Opponent Threats",
        "summary_desc": "overlooked threats",
        "explanation": "Your errors often come from not seeing what your opponent wants to do. The threat was there, but you didn't check.",
    },
    "hanging_piece_blindness": {
        "label": "Loose Piece Oversight",
        "summary_desc": "undefended pieces",
        "explanation": "Many of your losses involve leaving pieces without protection. A final safety check would prevent most of these.",
    },
    "tactical_oversight": {
        "label": "Tactical Blindspots",
        "summary_desc": "missed tactics",
        "explanation": "You miss forcing sequences that were available. The patterns are there, but not being recognized in time.",
    },
    "time_pressure": {
        "label": "Time Pressure Breakdown",
        "summary_desc": "clock trouble",
        "explanation": "Your accuracy collapses when the clock gets low. Good moves earlier become rushed mistakes under time pressure.",
    },
    "advantage_collapse": {
        "label": "Winning Position Collapse",
        "summary_desc": "failing to convert",
        "explanation": "You build winning advantages but struggle to close out games. Precision drops when the win seems secured.",
    },
    "positional_misread": {
        "label": "Positional Misjudgment",
        "summary_desc": "wrong plans",
        "explanation": "Your strategic decisions sometimes miss what the position requires. The right idea isn't always found.",
    },
    "defensive_lapse": {
        "label": "Defensive Breakdown",
        "summary_desc": "defensive errors",
        "explanation": "When under pressure, your defense cracks. Holding difficult positions is where games slip away.",
    },
    "overconfidence": {
        "label": "Overconfident Play",
        "summary_desc": "overconfidence",
        "explanation": "When ahead, you sometimes play too quickly or ambitiously. The win is assumed before it's achieved.",
    },
}

# Phase → Human-readable interpretation
PHASE_INTERPRETATIONS = {
    "opening": {
        "label": "Opening Discipline",
        "summary_desc": "the opening",
        "explanation": "Your performance drops in the first 12-15 moves. Early inaccuracies create problems for the rest of the game.",
    },
    "middlegame": {
        "label": "Middlegame Complexity",
        "summary_desc": "complex middlegames",
        "explanation": "When the position gets complicated, your error rate increases. Navigating tension is where games slip.",
    },
    "endgame": {
        "label": "Endgame Conversion",
        "summary_desc": "the endgame",
        "explanation": "Your performance drops most in simplified positions. Winning advantages are not consistently converted into full points.",
    },
}

# Risk Style → Human-readable interpretation  
STYLE_INTERPRETATIONS = {
    "low": {
        "label": "Cautious and Controlled",
        "summary_desc": "cautious",
        "explanation": "You rarely lose from reckless attacks. Most losses come from precision gaps, not excessive risk.",
    },
    "medium": {
        "label": "Balanced but Reactive",
        "summary_desc": "balanced",
        "explanation": "You take calculated risks when positions demand it. Neither overly aggressive nor overly passive.",
    },
    "high": {
        "label": "Aggressive and Enterprising",
        "summary_desc": "aggressive",
        "explanation": "You seek complications and aren't afraid of sharp positions. This creates winning chances but also volatility.",
    },
}


async def compute_player_identity(db, user_id: str, games: List[Dict] = None) -> Dict:
    """
    Compute a comprehensive, dynamic player identity.
    
    Returns a rich identity object with:
    - Collapsed summary (2-3 lines, powerful)
    - Expanded sections (4 structured areas)
    - Confidence score
    - All interpretations
    """
    
    # Fetch games if not provided
    if games is None:
        raw_games = await db.games.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        
        analyses = await db.game_analyses.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("analyzed_at", -1).limit(50).to_list(50)
        
        analysis_map = {a.get("game_id"): a for a in analyses}
        games = []
        for game in raw_games:
            game_id = game.get("game_id")
            if game_id in analysis_map:
                games.append({**game, "analysis": analysis_map[game_id]})
    
    # Minimum data check
    if len(games) < 8:
        return {
            "has_identity": False,
            "games_analyzed": len(games),
            "minimum_required": 8,
            "collapsed_summary": "Analyze more games to build your playing identity.",
            "can_expand": False,
        }
    
    # Get cognitive gap data for richer analysis
    cognitive_gaps = await db.cognitive_gap_history.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    
    # Compute all identity components with recency weighting
    stability = compute_decision_stability(games)
    primary_leak = compute_primary_leak(games, cognitive_gaps)
    phase_vulnerability = compute_phase_vulnerability(games)
    risk_style = compute_risk_style(games)
    
    # Calculate identity confidence
    confidence = calculate_identity_confidence(len(games))
    
    # Generate collapsed summary
    collapsed_summary = generate_collapsed_summary(
        stability, primary_leak, phase_vulnerability, risk_style
    )
    
    # Generate expanded sections
    expanded = generate_expanded_sections(
        stability, primary_leak, phase_vulnerability, risk_style
    )
    
    return {
        "has_identity": True,
        "games_analyzed": len(games),
        "confidence": confidence,
        "collapsed_summary": collapsed_summary,
        "can_expand": True,
        "expanded": expanded,
        # Raw values for other components that need them
        "raw": {
            "stability": stability["raw"],
            "leak": primary_leak["raw"],
            "phase": phase_vulnerability["raw"],
            "style": risk_style["raw"],
        },
    }


def compute_decision_stability(games: List[Dict]) -> Dict:
    """
    Compute decision stability using variance analysis with recency weighting.
    """
    
    # Calculate accuracy per game with recency weights
    accuracies = []
    weights = []
    
    for i, game in enumerate(games[:30]):
        analysis = game.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        if moves:
            cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
            if cp_losses:
                avg_cp = sum(cp_losses) / len(cp_losses)
                accuracies.append(avg_cp)
                
                # Recency weight: last 10 games = 1.5, previous = 1.0
                weight = 1.5 if i < 10 else 1.0
                weights.append(weight)
    
    if len(accuracies) < 5:
        return {
            "raw": "mixed",
            "interpretation": STABILITY_INTERPRETATIONS["mixed"],
        }
    
    # Weighted standard deviation
    weighted_mean = sum(a * w for a, w in zip(accuracies, weights)) / sum(weights)
    weighted_variance = sum(w * (a - weighted_mean) ** 2 for a, w in zip(accuracies, weights)) / sum(weights)
    std_dev = math.sqrt(weighted_variance)
    
    # Classify
    if std_dev < 15:
        level = "stable"
    elif std_dev < 35:
        level = "mixed"
    else:
        level = "volatile"
    
    return {
        "raw": level,
        "std_dev": round(std_dev, 1),
        "interpretation": STABILITY_INTERPRETATIONS[level],
    }


def compute_primary_leak(games: List[Dict], cognitive_gaps: List[Dict]) -> Dict:
    """
    Find the highest-impact recurring error pattern.
    Uses cognitive gap data if available, falls back to game analysis.
    """
    
    # Priority 1: Use cognitive gap data (most accurate)
    if cognitive_gaps and len(cognitive_gaps) >= 5:
        gap_counts = defaultdict(lambda: {"count": 0, "weight": 0})
        
        for i, gap in enumerate(cognitive_gaps[:50]):
            gap_type = gap.get("gap_type")
            severity = gap.get("severity", "medium")
            
            if gap_type:
                # Severity weights
                severity_weight = {"critical": 3, "high": 2, "medium": 1, "low": 0.5}.get(severity, 1)
                # Recency weight
                recency_weight = 1.5 if i < 15 else 1.0
                
                gap_counts[gap_type]["count"] += 1
                gap_counts[gap_type]["weight"] += severity_weight * recency_weight
        
        if gap_counts:
            primary = max(gap_counts.items(), key=lambda x: x[1]["weight"])
            gap_type = primary[0]
            
            if gap_type in LEAK_INTERPRETATIONS:
                return {
                    "raw": gap_type,
                    "count": primary[1]["count"],
                    "interpretation": LEAK_INTERPRETATIONS[gap_type],
                }
    
    # Priority 2: Derive from game analysis
    leak_signals = defaultdict(lambda: {"count": 0, "weight": 0})
    
    for i, game in enumerate(games[:25]):
        analysis = game.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        recency_weight = 1.5 if i < 10 else 1.0
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            if cp_loss < 50:
                continue
            
            eval_before = m.get("eval_before", 0)
            move_num = m.get("move_number", 0)
            
            # Classify the error type
            severity = 2 if cp_loss >= 100 else 1
            
            if eval_before > 150:
                # Was winning
                leak_signals["advantage_collapse"]["count"] += 1
                leak_signals["advantage_collapse"]["weight"] += severity * recency_weight * 1.5
            elif move_num <= 12:
                # Opening error
                leak_signals["positional_misread"]["count"] += 1
                leak_signals["positional_misread"]["weight"] += severity * recency_weight
            else:
                # General calculation
                leak_signals["calculation_depth"]["count"] += 1
                leak_signals["calculation_depth"]["weight"] += severity * recency_weight
    
    if leak_signals:
        primary = max(leak_signals.items(), key=lambda x: x[1]["weight"])
        leak_type = primary[0]
        
        if leak_type in LEAK_INTERPRETATIONS:
            return {
                "raw": leak_type,
                "count": primary[1]["count"],
                "interpretation": LEAK_INTERPRETATIONS[leak_type],
            }
    
    # Fallback
    return {
        "raw": "calculation_depth",
        "count": 0,
        "interpretation": LEAK_INTERPRETATIONS["calculation_depth"],
    }


def compute_phase_vulnerability(games: List[Dict]) -> Dict:
    """
    Determine which game phase has the highest normalized error rate.
    """
    
    phases = {
        "opening": {"errors": 0, "moves": 0, "weight": 0},
        "middlegame": {"errors": 0, "moves": 0, "weight": 0},
        "endgame": {"errors": 0, "moves": 0, "weight": 0},
    }
    
    for i, game in enumerate(games[:25]):
        analysis = game.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        total_moves = len(moves)
        
        recency_weight = 1.5 if i < 10 else 1.0
        
        for m in moves:
            move_num = m.get("move_number", 0)
            cp_loss = m.get("cp_loss", 0)
            
            # Determine phase
            if move_num <= 12:
                phase = "opening"
            elif move_num <= max(30, total_moves * 0.7):
                phase = "middlegame"
            else:
                phase = "endgame"
            
            phases[phase]["moves"] += 1
            if cp_loss >= 30:
                phases[phase]["errors"] += 1
                phases[phase]["weight"] += (cp_loss / 50) * recency_weight
    
    # Calculate normalized error rates
    rates = {}
    for phase, data in phases.items():
        if data["moves"] > 0:
            rates[phase] = data["weight"] / data["moves"]
        else:
            rates[phase] = 0
    
    # Find worst phase
    worst_phase = max(rates.items(), key=lambda x: x[1])[0]
    
    return {
        "raw": worst_phase,
        "rates": {k: round(v, 3) for k, v in rates.items()},
        "interpretation": PHASE_INTERPRETATIONS[worst_phase],
    }


def compute_risk_style(games: List[Dict]) -> Dict:
    """
    Determine playing style based on eval volatility and game dynamics.
    """
    
    volatility_scores = []
    
    for i, game in enumerate(games[:20]):
        analysis = game.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        if len(moves) < 10:
            continue
        
        # Calculate eval swings caused by player's moves
        swings = []
        for m in moves:
            eval_change = abs(m.get("eval_change", 0))
            swings.append(eval_change)
        
        if swings:
            avg_swing = sum(swings) / len(swings)
            # Check for large swings (aggressive/risky play)
            big_swings = sum(1 for s in swings if s > 50)
            volatility = avg_swing + (big_swings * 5)
            volatility_scores.append(volatility)
    
    if not volatility_scores:
        return {
            "raw": "medium",
            "interpretation": STYLE_INTERPRETATIONS["medium"],
        }
    
    avg_volatility = sum(volatility_scores) / len(volatility_scores)
    
    if avg_volatility < 25:
        style = "low"
    elif avg_volatility < 45:
        style = "medium"
    else:
        style = "high"
    
    return {
        "raw": style,
        "volatility": round(avg_volatility, 1),
        "interpretation": STYLE_INTERPRETATIONS[style],
    }


def calculate_identity_confidence(game_count: int) -> Dict:
    """
    Calculate how confident we are in the identity assessment.
    """
    
    if game_count < 10:
        return {"level": "low", "label": "Building", "games_needed": 10 - game_count}
    elif game_count < 25:
        return {"level": "medium", "label": "Forming", "games_needed": 25 - game_count}
    elif game_count < 50:
        return {"level": "high", "label": "Established", "games_needed": 0}
    else:
        return {"level": "very_high", "label": "Definitive", "games_needed": 0}


def generate_collapsed_summary(stability: Dict, leak: Dict, phase: Dict, style: Dict) -> str:
    """
    Generate the powerful 2-3 line collapsed summary.
    
    Template: "You are a {style} player whose level {stability}. 
    Most losses come from {leak} in {phase}."
    """
    
    style_desc = style["interpretation"]["summary_desc"]
    stability_desc = stability["interpretation"]["summary_desc"]
    leak_desc = leak["interpretation"]["summary_desc"]
    phase_desc = phase["interpretation"]["summary_desc"]
    
    # Build the summary
    summary = f"You are a {style_desc} player whose level {stability_desc}. "
    summary += f"Most losses come from {leak_desc} in {phase_desc}."
    
    return summary


def generate_expanded_sections(stability: Dict, leak: Dict, phase: Dict, style: Dict) -> Dict:
    """
    Generate the 4 structured expanded sections.
    """
    
    return {
        "consistency": {
            "title": "Consistency Level",
            "label": stability["interpretation"]["label"],
            "explanation": stability["interpretation"]["explanation"],
        },
        "main_leak": {
            "title": "Main Leak",
            "label": leak["interpretation"]["label"],
            "explanation": leak["interpretation"]["explanation"],
        },
        "phase_vulnerability": {
            "title": "Where Games Slip",
            "label": phase["interpretation"]["label"],
            "explanation": phase["interpretation"]["explanation"],
        },
        "playing_style": {
            "title": "Playing Style",
            "label": style["interpretation"]["label"],
            "explanation": style["interpretation"]["explanation"],
        },
    }
