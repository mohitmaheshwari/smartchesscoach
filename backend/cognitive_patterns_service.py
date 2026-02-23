"""
Cognitive Pattern Aggregation Service

This is NOT a new engine. It's aggregation logic over existing mistake classifications.

Computes:
1. Cognitive pattern frequency/severity from existing GameAnalysis documents
2. Trend direction (last 5 vs previous 5 games)
3. Thinking Stability Index (TSI)

No new collections. Only two persisted fields:
- module_activation_timestamp
- active_focus_category
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class CognitiveCategory(str, Enum):
    """Cognitive pattern categories - mapped from existing mistake types"""
    MISSED_FORCING = "missed_forcing_move"
    IGNORED_OPPONENT_FORCING = "ignored_opponent_forcing"
    PHANTOM_THREAT = "phantom_threat_reaction"
    ADVANTAGE_MISMANAGEMENT = "advantage_mismanagement"
    STRUCTURAL_MISJUDGMENT = "structural_misjudgment"
    RANDOM_CRITICAL = "random_move_critical"
    TIME_PRESSURE = "time_pressure_collapse"


# ============================================================
# BEHAVIORAL FRAMING - Makes analytics actionable
# ============================================================

BEHAVIORAL_FRAMING = {
    "missed_forcing_move": {
        "behavioral_diagnosis": "You are not scanning checks and captures consistently.",
        "corrective_protocol": "Before every move: check all forcing moves for both sides.",
        "micro_protocol": [
            "Check all checks",
            "Check all captures", 
            "Check all threats"
        ],
        "lab_prompt": "Did you scan forcing moves before each decision?"
    },
    "ignored_opponent_forcing": {
        "behavioral_diagnosis": "You are not asking 'What's my opponent's best reply?' before moving.",
        "corrective_protocol": "After deciding your move, pause and ask: what will they do?",
        "micro_protocol": [
            "Decide your candidate move",
            "Ask: what's their best reply?",
            "If dangerous, reconsider"
        ],
        "lab_prompt": "Did you check your opponent's threats before each move?"
    },
    "phantom_threat_reaction": {
        "behavioral_diagnosis": "You are defending against threats that aren't actually forcing.",
        "corrective_protocol": "Before defending, verify: is this threat actually forcing?",
        "micro_protocol": [
            "Identify the 'threat'",
            "Ask: what happens if I ignore it?",
            "Only defend if truly forcing"
        ],
        "lab_prompt": "Did you verify threats were real before defending?"
    },
    "advantage_mismanagement": {
        "behavioral_diagnosis": "You are relaxing when you should be pressing your advantage.",
        "corrective_protocol": "When ahead, increase tension—don't release it.",
        "micro_protocol": [
            "Recognize you're winning",
            "Look for forcing continuations",
            "Don't trade into a drawn endgame"
        ],
        "lab_prompt": "When ahead, did you maintain pressure or relax?"
    },
    "structural_misjudgment": {
        "behavioral_diagnosis": "You are not evaluating piece coordination and pawn structure.",
        "corrective_protocol": "Before pawn moves, ask: what squares am I weakening?",
        "micro_protocol": [
            "Check pawn structure impact",
            "Verify piece coordination",
            "Consider long-term weaknesses"
        ],
        "lab_prompt": "Did you consider structural consequences of your moves?"
    },
    "random_move_critical": {
        "behavioral_diagnosis": "You are moving without a plan in positions that require calculation.",
        "corrective_protocol": "In critical positions, calculate before moving—never guess.",
        "micro_protocol": [
            "Recognize the position is critical",
            "Calculate concrete variations",
            "Choose based on analysis, not instinct"
        ],
        "lab_prompt": "In critical moments, did you calculate or guess?"
    },
    "time_pressure_collapse": {
        "behavioral_diagnosis": "Your decision quality collapses under time pressure.",
        "corrective_protocol": "Practice quick pattern recognition and pre-move routines.",
        "micro_protocol": [
            "Use increment wisely",
            "Have a default thought process",
            "Simplify when short on time"
        ],
        "lab_prompt": "Did time pressure affect your decision quality?"
    }
}


# TSI Interpretation Bands
TSI_BANDS = {
    "stable": {"min": 80, "max": 100, "label": "Stable decision process", "color": "green"},
    "moderate": {"min": 65, "max": 79, "label": "Moderate instability", "color": "yellow"},
    "frequent": {"min": 50, "max": 64, "label": "Frequent cognitive lapses", "color": "orange"},
    "volatile": {"min": 0, "max": 49, "label": "High volatility", "color": "red"}
}


def get_tsi_interpretation(tsi: int) -> Dict:
    """Get interpretation band for TSI score"""
    if tsi >= 80:
        return TSI_BANDS["stable"]
    elif tsi >= 65:
        return TSI_BANDS["moderate"]
    elif tsi >= 50:
        return TSI_BANDS["frequent"]
    else:
        return TSI_BANDS["volatile"]


def get_behavioral_framing(category: str) -> Dict:
    """Get behavioral framing for a cognitive category"""
    return BEHAVIORAL_FRAMING.get(category, {
        "behavioral_diagnosis": "Review your decision-making process.",
        "corrective_protocol": "Focus on deliberate practice.",
        "micro_protocol": ["Analyze", "Plan", "Execute"],
        "lab_prompt": "Did you follow your protocol?"
    })


# Mapping from existing mistake_type to cognitive category
MISTAKE_TO_COGNITIVE = {
    # Missed Forcing Move
    "missed_mate": CognitiveCategory.MISSED_FORCING,
    "missed_checkmate": CognitiveCategory.MISSED_FORCING,
    "missed_fork": CognitiveCategory.MISSED_FORCING,
    "missed_pin": CognitiveCategory.MISSED_FORCING,
    "missed_skewer": CognitiveCategory.MISSED_FORCING,
    "missed_tactic": CognitiveCategory.MISSED_FORCING,
    "missed_piece_trap": CognitiveCategory.MISSED_FORCING,
    "missed_attack_valuable": CognitiveCategory.MISSED_FORCING,
    "tactical_mistake": CognitiveCategory.MISSED_FORCING,
    
    # Ignored Opponent Forcing Move
    "allowed_mate_threat": CognitiveCategory.IGNORED_OPPONENT_FORCING,
    "allowed_tactic": CognitiveCategory.IGNORED_OPPONENT_FORCING,
    "allows_mate_in_1": CognitiveCategory.IGNORED_OPPONENT_FORCING,
    "allows_mate_in_2": CognitiveCategory.IGNORED_OPPONENT_FORCING,
    "ignored_threat": CognitiveCategory.IGNORED_OPPONENT_FORCING,
    
    # Phantom Threat Reaction
    "phantom_threat": CognitiveCategory.PHANTOM_THREAT,
    "unnecessary_defense": CognitiveCategory.PHANTOM_THREAT,
    
    # Advantage Mismanagement  
    "advantage_mismanagement": CognitiveCategory.ADVANTAGE_MISMANAGEMENT,
    "winning_to_equal": CognitiveCategory.ADVANTAGE_MISMANAGEMENT,
    "equal_to_losing": CognitiveCategory.ADVANTAGE_MISMANAGEMENT,
    
    # Structural Misjudgment
    "positional_error": CognitiveCategory.STRUCTURAL_MISJUDGMENT,
    "strategic_slip": CognitiveCategory.STRUCTURAL_MISJUDGMENT,
    "pawn_structure_damage": CognitiveCategory.STRUCTURAL_MISJUDGMENT,
    "piece_coordination": CognitiveCategory.STRUCTURAL_MISJUDGMENT,
    
    # Random Move in Critical Position
    "no_plan_critical": CognitiveCategory.RANDOM_CRITICAL,
    "blunder": CognitiveCategory.RANDOM_CRITICAL,
    
    # Time Pressure (if tracked)
    "time_pressure": CognitiveCategory.TIME_PRESSURE,
}

# Severity weights based on cp_loss ranges
def get_severity_weight(cp_loss: int) -> float:
    """Convert cp_loss to severity weight (0-1 scale)"""
    if cp_loss >= 500:
        return 1.0
    elif cp_loss >= 300:
        return 0.8
    elif cp_loss >= 150:
        return 0.6
    elif cp_loss >= 100:
        return 0.4
    elif cp_loss >= 50:
        return 0.2
    return 0.0


def classify_move_to_cognitive(
    mistake_type: str,
    cp_loss: int,
    best_move_was_forcing: bool = False,
    opponent_reply_was_forcing: bool = False,
    was_defensive_against_phantom: bool = False
) -> Optional[CognitiveCategory]:
    """
    Classify a move's mistake into a cognitive category.
    
    Uses existing mistake_type + simple position metadata.
    No heavy detection logic.
    """
    # Rule 1: If cp_loss >= 150 AND best_move was forcing → Missed Forcing Move
    if cp_loss >= 150 and best_move_was_forcing:
        return CognitiveCategory.MISSED_FORCING
    
    # Rule 2: If opponent best reply was forcing AND ignored → Ignored Opponent Forcing
    if opponent_reply_was_forcing:
        return CognitiveCategory.IGNORED_OPPONENT_FORCING
    
    # Rule 3: Defensive move against non-existent threat → Phantom Threat
    if was_defensive_against_phantom:
        return CognitiveCategory.PHANTOM_THREAT
    
    # Default: Use the mapping table
    return MISTAKE_TO_COGNITIVE.get(mistake_type)


async def aggregate_cognitive_patterns(
    db,
    user_id: str,
    num_games: int = 20
) -> Dict:
    """
    Aggregate cognitive patterns from user's last N games.
    
    Returns:
    {
        "patterns": {
            "missed_forcing_move": {
                "frequency": 12,
                "avg_severity": 0.65,
                "weighted_score": 7.8,
                "trend": "worsening"  # improving/worsening/stable
            },
            ...
        },
        "total_mistakes": 45,
        "games_analyzed": 20,
        "thinking_stability_index": 72,
        "tsi_trend": "improving"
    }
    """
    # Get last N game analyses
    analyses = await db.game_analyses.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(num_games).to_list(num_games)
    
    if not analyses:
        return {
            "patterns": {},
            "total_mistakes": 0,
            "games_analyzed": 0,
            "thinking_stability_index": 100,
            "tsi_trend": "stable"
        }
    
    # Split into recent (last 5) and previous (5-10) for trend
    recent_analyses = analyses[:5] if len(analyses) >= 5 else analyses
    previous_analyses = analyses[5:10] if len(analyses) >= 10 else []
    
    # Aggregate patterns
    patterns = {}
    total_mistakes = 0
    
    for analysis in analyses:
        sf_analysis = analysis.get("stockfish_analysis", {})
        moves = sf_analysis.get("move_evaluations", [])
        
        for move in moves:
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 50:
                continue  # Not a significant mistake
            
            mistake_type = move.get("mistake_type", "")
            
            # Determine if best move was forcing (check/capture)
            best_move = move.get("best_move", "")
            best_move_forcing = "+" in best_move or "x" in best_move or "#" in best_move
            
            # Classify to cognitive category
            category = classify_move_to_cognitive(
                mistake_type=mistake_type,
                cp_loss=cp_loss,
                best_move_was_forcing=best_move_forcing
            )
            
            if not category:
                # Default to structural if can't classify
                if cp_loss >= 150:
                    category = CognitiveCategory.RANDOM_CRITICAL
                else:
                    category = CognitiveCategory.STRUCTURAL_MISJUDGMENT
            
            cat_key = category.value
            if cat_key not in patterns:
                patterns[cat_key] = {
                    "frequency": 0,
                    "total_severity": 0.0,
                    "recent_frequency": 0,
                    "previous_frequency": 0
                }
            
            patterns[cat_key]["frequency"] += 1
            patterns[cat_key]["total_severity"] += get_severity_weight(cp_loss)
            total_mistakes += 1
    
    # Calculate trend for each pattern (last 5 vs previous 5 games)
    recent_patterns = _aggregate_for_games(recent_analyses)
    previous_patterns = _aggregate_for_games(previous_analyses) if previous_analyses else {}
    
    # Finalize pattern data
    for cat_key, data in patterns.items():
        freq = data["frequency"]
        data["avg_severity"] = data["total_severity"] / freq if freq > 0 else 0
        data["weighted_score"] = freq * data["avg_severity"]
        
        # Calculate trend
        recent_freq = recent_patterns.get(cat_key, {}).get("frequency", 0)
        previous_freq = previous_patterns.get(cat_key, {}).get("frequency", 0)
        
        data["recent_frequency"] = recent_freq
        data["previous_frequency"] = previous_freq
        data["trend"] = _calculate_trend(recent_freq, previous_freq)
        
        # Clean up temp fields
        del data["total_severity"]
    
    # Calculate Thinking Stability Index
    tsi, tsi_trend = _calculate_tsi(patterns, recent_patterns, previous_patterns)
    
    return {
        "patterns": patterns,
        "total_mistakes": total_mistakes,
        "games_analyzed": len(analyses),
        "thinking_stability_index": tsi,
        "tsi_trend": tsi_trend
    }


def _aggregate_for_games(analyses: List) -> Dict:
    """Helper to aggregate patterns for a subset of games"""
    patterns = {}
    
    for analysis in analyses:
        sf_analysis = analysis.get("stockfish_analysis", {})
        moves = sf_analysis.get("move_evaluations", [])
        
        for move in moves:
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 50:
                continue
            
            mistake_type = move.get("mistake_type", "")
            best_move = move.get("best_move", "")
            best_move_forcing = "+" in best_move or "x" in best_move or "#" in best_move
            
            category = classify_move_to_cognitive(
                mistake_type=mistake_type,
                cp_loss=cp_loss,
                best_move_was_forcing=best_move_forcing
            )
            
            if not category:
                category = CognitiveCategory.STRUCTURAL_MISJUDGMENT
            
            cat_key = category.value
            if cat_key not in patterns:
                patterns[cat_key] = {"frequency": 0, "total_severity": 0.0}
            
            patterns[cat_key]["frequency"] += 1
            patterns[cat_key]["total_severity"] += get_severity_weight(cp_loss)
    
    # Calculate avg_severity for each pattern (needed for weighted TSI)
    for cat_key, data in patterns.items():
        freq = data["frequency"]
        data["avg_severity"] = data["total_severity"] / freq if freq > 0 else 0
    
    return patterns


def _calculate_trend(recent: int, previous: int) -> str:
    """
    Calculate trend direction.
    
    Compare last 5 games vs previous 5 games.
    If weighted severity decreases by > 20%, mark improving.
    If increases > 20%, mark worsening.
    Else stable.
    
    GUARD: Minimum baseline floor to prevent noise from small numbers.
    """
    # Minimum floor - prevents meaningless trends like 0.02 → 0.04 = "100% worsening"
    MIN_BASELINE_FLOOR = 2
    
    if previous < MIN_BASELINE_FLOOR:
        if recent < MIN_BASELINE_FLOOR:
            return "stable"  # Both below threshold - no meaningful pattern
        elif recent >= MIN_BASELINE_FLOOR + 2:
            return "worsening"  # New significant pattern appearing
        return "stable"  # Not enough signal
    
    change_pct = (recent - previous) / previous * 100
    
    if change_pct < -20:
        return "improving"
    elif change_pct > 20:
        return "worsening"
    return "stable"


# ============================================================
# WEIGHTED ROLLING WINDOW TSI - Dampens single-game spikes
# ============================================================
# Weight distribution for 20 games:
#   Games 1-5 (most recent): weight 3
#   Games 6-10: weight 2
#   Games 11-20: weight 1
# This responds to recent changes but dampens isolated bad games.

GAME_WEIGHTS = {
    "recent": 3.0,      # Games 1-5
    "middle": 2.0,      # Games 6-10
    "older": 1.0        # Games 11-20
}


def _calculate_tsi(
    all_patterns: Dict,
    recent_patterns: Dict,
    previous_patterns: Dict
) -> Tuple[int, str]:
    """
    Calculate Thinking Stability Index using Weighted Rolling Window.
    
    Weight distribution:
        Games 1-5 (recent): weight 3
        Games 6-10 (middle): weight 2
        Games 11-20 (older): weight 1
    
    This dampens single-game spikes while responding to sustained patterns.
    
    TSI = 100 - normalized_weighted_sum
    Clamp between 0-100.
    """
    if not all_patterns:
        return 100, "stable"
    
    # Calculate weighted score using the tiered approach
    # recent_patterns = games 1-5, previous_patterns = games 6-10
    # all_patterns contains games 1-20 (but not split by tier)
    
    # We'll compute weighted severity for recent vs older patterns
    recent_weighted = 0.0
    previous_weighted = 0.0
    older_weighted = 0.0
    
    for cat_key, data in all_patterns.items():
        # Recent (games 1-5)
        recent_freq = recent_patterns.get(cat_key, {}).get("frequency", 0)
        recent_sev = recent_patterns.get(cat_key, {}).get("avg_severity", 0)
        recent_weighted += recent_freq * recent_sev * GAME_WEIGHTS["recent"]
        
        # Middle (games 6-10)
        prev_freq = previous_patterns.get(cat_key, {}).get("frequency", 0)
        prev_sev = previous_patterns.get(cat_key, {}).get("avg_severity", 0)
        previous_weighted += prev_freq * prev_sev * GAME_WEIGHTS["middle"]
        
        # Older (games 11-20) - approximate from total minus recent/previous
        total_freq = data.get("frequency", 0)
        total_sev = data.get("avg_severity", 0)
        older_freq = max(0, total_freq - recent_freq - prev_freq)
        older_weighted += older_freq * total_sev * GAME_WEIGHTS["older"]
    
    # Total weighted score
    total_weighted = recent_weighted + previous_weighted + older_weighted
    
    # Dynamic max calculation based on actual game volume
    # Use 10 significant mistakes per game at severity 0.5 as max (very bad player)
    # This gives a reasonable ceiling that scales with actual data
    games_analyzed = 20  # We analyze last 20 games
    
    # Max possible: 10 mistakes/game * 0.6 avg severity
    # Weighted across tiers: 5*3 + 5*2 + 10*1 = 35 game-weights
    max_mistakes_per_weighted_game = 10 * 0.6
    max_expected = 35 * max_mistakes_per_weighted_game  # = 210
    
    # Normalize: 0-100 scale
    # 0 weighted = TSI 100 (perfect)
    # max_expected weighted = TSI 0 (very bad)
    if max_expected > 0:
        normalized = min(100, (total_weighted / max_expected) * 100)
    else:
        normalized = 0
    
    # TSI = 100 - normalized (higher is better)
    tsi = max(0, min(100, int(100 - normalized)))
    
    # Calculate TSI trend using weighted recent vs previous
    # Higher score = more mistakes = WORSE
    # So we DON'T invert the trend - if recent is worse (higher), trend is "worsening"
    recent_score = sum(
        p.get("frequency", 0) * p.get("avg_severity", 0.5) * GAME_WEIGHTS["recent"]
        for p in recent_patterns.values()
    )
    previous_score = sum(
        p.get("frequency", 0) * p.get("avg_severity", 0.5) * GAME_WEIGHTS["middle"]
        for p in previous_patterns.values()
    )
    
    # Normalize both to same weight for fair comparison
    if GAME_WEIGHTS["recent"] != GAME_WEIGHTS["middle"]:
        previous_score = previous_score * (GAME_WEIGHTS["recent"] / GAME_WEIGHTS["middle"])
    
    # Compare: higher recent = worsening, lower recent = improving
    # Scale up to make _calculate_trend thresholds meaningful
    tsi_trend = _calculate_trend(int(recent_score * 10), int(previous_score * 10))
    # NO inversion needed - trend correctly reflects mistake direction
    
    return tsi, tsi_trend


async def get_prioritized_weaknesses(
    db,
    user_id: str,
    threshold_frequency: int = 3,
    threshold_severity: float = 0.4
) -> List[Dict]:
    """
    Get prioritized list of cognitive weaknesses for training prescription.
    
    Returns weaknesses sorted by priority (weighted_score descending).
    Only includes patterns that cross threshold.
    """
    aggregation = await aggregate_cognitive_patterns(db, user_id)
    patterns = aggregation.get("patterns", {})
    
    # Filter and sort by weighted_score
    prioritized = []
    
    for cat_key, data in patterns.items():
        freq = data.get("frequency", 0)
        avg_sev = data.get("avg_severity", 0)
        
        # Check if crosses threshold
        if freq >= threshold_frequency or avg_sev >= threshold_severity:
            prioritized.append({
                "category": cat_key,
                "frequency": freq,
                "avg_severity": avg_sev,
                "weighted_score": data.get("weighted_score", 0),
                "trend": data.get("trend", "stable"),
                "display_name": _get_display_name(cat_key)
            })
    
    # Sort by weighted_score (highest priority first)
    prioritized.sort(key=lambda x: x["weighted_score"], reverse=True)
    
    return prioritized


def _get_display_name(category_key: str) -> str:
    """Get human-readable name for cognitive category"""
    names = {
        "missed_forcing_move": "Missed Forcing Moves",
        "ignored_opponent_forcing": "Ignored Opponent Threats",
        "phantom_threat_reaction": "Phantom Threat Reactions",
        "advantage_mismanagement": "Advantage Mismanagement",
        "structural_misjudgment": "Structural Misjudgments",
        "random_move_critical": "Random Moves in Critical Positions",
        "time_pressure_collapse": "Time Pressure Collapse"
    }
    return names.get(category_key, category_key.replace("_", " ").title())


# ============================================================
# AUDIT LAYER - Module activation and tracking
# ============================================================

async def activate_focus_module(
    db,
    user_id: str,
    focus_category: str
) -> Dict:
    """
    Activate a focus module for the user.
    
    Stores only:
    - module_activation_timestamp
    - active_focus_category
    
    Baseline will be computed dynamically (last 10 games before activation).
    """
    activation_time = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "focus_module.active_category": focus_category,
                "focus_module.activated_at": activation_time
            }
        },
        upsert=True
    )
    
    return {
        "active_category": focus_category,
        "activated_at": activation_time.isoformat(),
        "audit_window": "Next 5 games will be evaluated"
    }


async def get_focus_module_status(db, user_id: str) -> Optional[Dict]:
    """Get current focus module status"""
    user = await db.users.find_one({"user_id": user_id})
    if not user or "focus_module" not in user:
        return None
    
    return user.get("focus_module")


async def evaluate_focus_progress(
    db,
    user_id: str
) -> Optional[Dict]:
    """
    Evaluate progress on active focus module.
    
    Compares:
    - Baseline: Last 10 games BEFORE module activation
    - Current: 5 most recent games AFTER module activation
    """
    user = await db.users.find_one({"user_id": user_id})
    if not user or "focus_module" not in user:
        return None
    
    focus = user["focus_module"]
    category = focus.get("active_category")
    activated_at = focus.get("activated_at")
    
    if not category or not activated_at:
        return None
    
    # Get games before activation (baseline)
    baseline_games = await db.game_analyses.find({
        "user_id": user_id,
        "created_at": {"$lt": activated_at}
    }).sort("created_at", -1).limit(10).to_list(10)
    
    # Get games after activation (audit window)
    audit_games = await db.game_analyses.find({
        "user_id": user_id,
        "created_at": {"$gte": activated_at}
    }).sort("created_at", -1).limit(5).to_list(5)
    
    if not baseline_games:
        return {
            "status": "insufficient_baseline",
            "message": "Need more games before activation for comparison"
        }
    
    if not audit_games:
        return {
            "status": "no_games_yet",
            "message": "Play some games to see your progress"
        }
    
    # Calculate pattern frequency in baseline vs audit
    baseline_patterns = _aggregate_for_games(baseline_games)
    audit_patterns = _aggregate_for_games(audit_games)
    
    baseline_freq = baseline_patterns.get(category, {}).get("frequency", 0)
    audit_freq = audit_patterns.get(category, {}).get("frequency", 0)
    
    # Normalize by number of games
    baseline_per_game = baseline_freq / len(baseline_games) if baseline_games else 0
    audit_per_game = audit_freq / len(audit_games) if audit_games else 0
    
    # Calculate improvement
    if baseline_per_game > 0:
        change_pct = ((audit_per_game - baseline_per_game) / baseline_per_game) * 100
    else:
        change_pct = 0 if audit_per_game == 0 else 100
    
    if change_pct < -20:
        status = "improving"
        message = f"Great progress! {category.replace('_', ' ').title()} reduced by {abs(int(change_pct))}%"
    elif change_pct > 20:
        status = "needs_work"
        message = f"Keep practicing. {category.replace('_', ' ').title()} increased by {int(change_pct)}%"
    else:
        status = "stable"
        message = f"Holding steady on {category.replace('_', ' ').title()}"
    
    return {
        "status": status,
        "message": message,
        "category": category,
        "baseline_per_game": round(baseline_per_game, 2),
        "audit_per_game": round(audit_per_game, 2),
        "change_percent": round(change_pct, 1),
        "baseline_games": len(baseline_games),
        "audit_games": len(audit_games)
    }


# ============================================================
# TRAINING PRIORITIZATION
# ============================================================

# Mapping from cognitive category to relevant training content
CATEGORY_TO_TRAINING = {
    "missed_forcing_move": {
        "puzzle_types": ["tactical_mistake", "missed_fork", "missed_pin", "missed_mate"],
        "trap_categories": ["tactical"],
        "focus_message": "Practice spotting forcing moves (checks, captures, threats)"
    },
    "ignored_opponent_forcing": {
        "puzzle_types": ["allowed_tactic", "allows_mate"],
        "trap_categories": ["defensive"],
        "focus_message": "Practice asking 'What's my opponent's best reply?'"
    },
    "phantom_threat_reaction": {
        "puzzle_types": [],  # No specific puzzles, more about awareness
        "trap_categories": [],
        "focus_message": "Before defending, verify: is the threat actually forcing?"
    },
    "advantage_mismanagement": {
        "puzzle_types": ["advantage_mismanagement", "winning_to_equal"],
        "trap_categories": ["conversion"],
        "focus_message": "Practice converting advantages into wins"
    },
    "structural_misjudgment": {
        "puzzle_types": ["positional_error", "strategic_slip"],
        "trap_categories": ["positional"],
        "focus_message": "Focus on pawn structure and piece coordination"
    },
    "random_move_critical": {
        "puzzle_types": ["blunder", "no_plan"],
        "trap_categories": ["tactical"],
        "focus_message": "In critical positions, calculate before moving"
    },
    "time_pressure_collapse": {
        "puzzle_types": [],
        "trap_categories": [],
        "focus_message": "Practice quick pattern recognition"
    }
}


def get_training_prioritization(weaknesses: List[Dict]) -> Dict:
    """
    Get training content prioritization based on weaknesses.
    
    Returns:
    {
        "primary_focus": {...},
        "secondary_focus": [...],
        "puzzle_priority_order": [...],
        "trap_priority_order": [...],
        "general_drills": True/False
    }
    """
    if not weaknesses:
        return {
            "primary_focus": None,
            "secondary_focus": [],
            "puzzle_priority_order": [],
            "trap_priority_order": [],
            "general_drills": True,
            "message": "No specific weaknesses detected. General improvement drills recommended."
        }
    
    primary = weaknesses[0]
    secondary = weaknesses[1:3] if len(weaknesses) > 1 else []
    
    # Build priority order
    puzzle_types = []
    trap_categories = []
    
    # Primary weakness content first
    primary_content = CATEGORY_TO_TRAINING.get(primary["category"], {})
    puzzle_types.extend(primary_content.get("puzzle_types", []))
    trap_categories.extend(primary_content.get("trap_categories", []))
    
    # Secondary weakness content
    for sec in secondary:
        sec_content = CATEGORY_TO_TRAINING.get(sec["category"], {})
        for pt in sec_content.get("puzzle_types", []):
            if pt not in puzzle_types:
                puzzle_types.append(pt)
        for tc in sec_content.get("trap_categories", []):
            if tc not in trap_categories:
                trap_categories.append(tc)
    
    return {
        "primary_focus": {
            "category": primary["category"],
            "display_name": primary["display_name"],
            "message": primary_content.get("focus_message", ""),
            "trend": primary["trend"]
        },
        "secondary_focus": [
            {
                "category": s["category"],
                "display_name": s["display_name"],
                "trend": s["trend"]
            }
            for s in secondary
        ],
        "puzzle_priority_order": puzzle_types,
        "trap_priority_order": trap_categories,
        "general_drills": False
    }
