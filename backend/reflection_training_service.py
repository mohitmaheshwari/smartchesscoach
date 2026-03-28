"""
Reflection-Driven Training Service

This module handles how reflections impact training focus.
Core Philosophy: YOUR mistakes and reflections determine training, not just your rating.

Key Changes:
1. Reflections boost the cost of the relevant layer (making it more likely to be active)
2. After enough reflections on a pattern, it becomes the training focus
3. Rating-based curriculum is a GUIDE, not a strict requirement
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Map reflection tags to training layers
TAG_TO_LAYER = {
    # Stability layer patterns
    "threat_blindness": "stability",
    "hanging_pieces": "stability", 
    "one_move_threats": "stability",
    "rushing": "stability",
    "missed_check": "stability",
    "missed_capture": "stability",
    
    # Conversion layer patterns
    "let_advantage_slip": "conversion",
    "drew_winning_position": "conversion",
    "missed_winning_move": "conversion",
    "premature_attack": "conversion",
    
    # Structure layer patterns
    "opening_deviation": "structure",
    "poor_pawn_structure": "structure",
    "passive_pieces": "structure",
    "aimless_play": "structure",
    
    # Precision layer patterns
    "calculation_error": "precision",
    "missed_tactic": "precision",
    "endgame_technique": "precision",
    "time_trouble": "precision",
}

# Reflection tags grouped by what they indicate
REFLECTION_CATEGORIES = {
    "threat_related": [
        "I didn't see the threat",
        "I missed what my opponent was planning", 
        "I didn't check what they could do",
        "threat_blindness",
        "one_move_threats",
    ],
    "rushing_related": [
        "I was rushing",
        "I moved too fast",
        "I didn't take time to think",
        "rushing",
    ],
    "tactical_related": [
        "I miscalculated",
        "I saw it but calculated wrong",
        "calculation_error",
        "missed_tactic",
    ],
    "positional_related": [
        "I had a different plan",
        "I didn't know what to do",
        "aimless_play",
        "passive_pieces",
    ],
    "piece_safety": [
        "I forgot about that piece",
        "I left my piece hanging",
        "hanging_pieces",
    ],
}


def categorize_reflection(user_thought: str, selected_tags: List[str] = None) -> Dict:
    """
    Categorize a reflection to determine which layer it affects.
    
    Returns:
        {
            "layer": "stability" | "conversion" | "structure" | "precision",
            "pattern": "threat_blindness" | "rushing" | etc.,
            "confidence": 0.0-1.0
        }
    """
    thought_lower = user_thought.lower() if user_thought else ""
    tags = selected_tags or []
    
    # Check tags first (more reliable)
    for tag in tags:
        if tag in TAG_TO_LAYER:
            return {
                "layer": TAG_TO_LAYER[tag],
                "pattern": tag,
                "confidence": 0.9
            }
    
    # Analyze text for keywords
    # Threat-related (Stability layer)
    threat_keywords = ["threat", "didn't see", "missed", "opponent", "attack", "capture"]
    if any(kw in thought_lower for kw in threat_keywords):
        return {"layer": "stability", "pattern": "threat_blindness", "confidence": 0.7}
    
    # Rushing-related (Stability layer)
    rushing_keywords = ["rush", "fast", "quick", "time", "hurry", "blitz"]
    if any(kw in thought_lower for kw in rushing_keywords):
        return {"layer": "stability", "pattern": "rushing", "confidence": 0.7}
    
    # Calculation-related (Precision layer)
    calc_keywords = ["calculat", "thought", "saw", "line", "variation", "moves ahead"]
    if any(kw in thought_lower for kw in calc_keywords):
        return {"layer": "precision", "pattern": "calculation_error", "confidence": 0.6}
    
    # Plan-related (Structure layer)
    plan_keywords = ["plan", "idea", "strategy", "position", "develop"]
    if any(kw in thought_lower for kw in plan_keywords):
        return {"layer": "structure", "pattern": "aimless_play", "confidence": 0.5}
    
    # Default to stability (most common issue)
    return {"layer": "stability", "pattern": "threat_blindness", "confidence": 0.3}


async def process_reflection_impact(
    db, 
    user_id: str, 
    reflection_text: str, 
    tags: List[str] = None,
    gap_type: str = None
) -> Dict:
    """
    Process a reflection and update training focus accordingly.
    
    This is the KEY function that makes reflections impact training.
    """
    # Categorize the reflection
    category = categorize_reflection(reflection_text, tags)
    layer = category["layer"]
    pattern = category["pattern"]
    confidence = category["confidence"]
    
    # If awareness gap was detected, use that info
    if gap_type:
        gap_to_layer = {
            "tactical_blindness": "stability",
            "positional_misunderstanding": "structure", 
            "calculation_error": "precision",
            "pattern_missed": "precision",
            "time_pressure": "stability",
        }
        if gap_type in gap_to_layer:
            layer = gap_to_layer[gap_type]
            confidence = 0.95  # High confidence from LLM analysis
    
    # Get or create reflection impact tracking
    impact_doc = await db.reflection_impacts.find_one({"user_id": user_id})
    
    if not impact_doc:
        impact_doc = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "layer_boosts": {
                "stability": 0,
                "conversion": 0,
                "structure": 0,
                "precision": 0,
            },
            "pattern_counts": {},
            "total_reflections": 0,
            "last_reflection_at": None,
        }
    
    # Update layer boost (this affects which layer becomes "active")
    # Each reflection adds a boost proportional to confidence
    boost_amount = 1000 * confidence  # Significant boost to layer cost
    layer_boosts = impact_doc.get("layer_boosts", {})
    layer_boosts[layer] = layer_boosts.get(layer, 0) + boost_amount
    
    # Update pattern count
    pattern_counts = impact_doc.get("pattern_counts", {})
    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    # Update document
    await db.reflection_impacts.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "layer_boosts": layer_boosts,
                "pattern_counts": pattern_counts,
                "last_reflection_at": datetime.now(timezone.utc).isoformat(),
            },
            "$inc": {"total_reflections": 1}
        },
        upsert=True
    )
    
    # Check if we should suggest changing training focus
    suggestion = None
    dominant_layer = max(layer_boosts.keys(), key=lambda k: layer_boosts[k])
    dominant_boost = layer_boosts[dominant_layer]
    
    # If one layer has significantly more reflections, suggest focusing there
    total_boosts = sum(layer_boosts.values())
    if total_boosts > 0 and dominant_boost / total_boosts > 0.5:
        suggestion = {
            "should_change_focus": True,
            "suggested_layer": dominant_layer,
            "reason": f"Your reflections show {pattern_counts.get(pattern, 0)}+ instances of {pattern.replace('_', ' ')}",
            "confidence": dominant_boost / total_boosts
        }
    
    return {
        "processed": True,
        "layer_affected": layer,
        "pattern": pattern,
        "boost_added": boost_amount,
        "suggestion": suggestion,
        "total_reflections": impact_doc.get("total_reflections", 0) + 1,
    }


async def get_reflection_adjusted_training(db, user_id: str, base_profile: Dict) -> Dict:
    """
    Adjust the training profile based on accumulated reflections.
    
    This modifies the layer costs based on reflection data, so that
    training focuses on what the USER actually struggles with.
    """
    # Get reflection impacts
    impact_doc = await db.reflection_impacts.find_one({"user_id": user_id})
    
    if not impact_doc or impact_doc.get("total_reflections", 0) < 3:
        # Not enough reflections to adjust - return base profile
        return base_profile
    
    layer_boosts = impact_doc.get("layer_boosts", {})
    pattern_counts = impact_doc.get("pattern_counts", {})
    
    # Get the base layer breakdown
    layer_breakdown = base_profile.get("layer_breakdown", {})
    
    # Adjust costs based on reflections
    adjusted_breakdown = {}
    for layer_id, layer_data in layer_breakdown.items():
        adjusted_data = layer_data.copy()
        base_cost = layer_data.get("cost", 0)
        boost = layer_boosts.get(layer_id, 0)
        
        # Add reflection boost to cost
        adjusted_data["cost"] = base_cost + boost
        adjusted_data["reflection_boost"] = boost
        adjusted_data["has_reflection_data"] = boost > 0
        
        adjusted_breakdown[layer_id] = adjusted_data
    
    # Determine new active layer based on adjusted costs
    active_layer = max(adjusted_breakdown.keys(), key=lambda k: adjusted_breakdown[k]["cost"])
    
    # Get dominant pattern from reflections
    if pattern_counts:
        dominant_pattern = max(pattern_counts.keys(), key=lambda k: pattern_counts[k])
    else:
        dominant_pattern = base_profile.get("micro_habit", "threat_blindness")
    
    # Build adjusted profile
    adjusted_profile = base_profile.copy()
    adjusted_profile["layer_breakdown"] = adjusted_breakdown
    adjusted_profile["active_phase"] = active_layer
    adjusted_profile["micro_habit"] = dominant_pattern
    adjusted_profile["reflection_adjusted"] = True
    adjusted_profile["reflection_count"] = impact_doc.get("total_reflections", 0)
    
    # Add a note explaining why this training was chosen
    adjusted_profile["training_reason"] = (
        f"Based on your {impact_doc.get('total_reflections', 0)} reflections, "
        f"your main challenge is {dominant_pattern.replace('_', ' ')} "
        f"in the {active_layer} area."
    )
    
    return adjusted_profile


async def get_data_driven_training_focus(db, user_id: str) -> Dict:
    """
    Get training focus based purely on data (mistakes + reflections).
    
    This bypasses the rating-based curriculum and gives you what
    YOUR games say you need to work on.
    """
    from training_profile_service import get_training_profile, TRAINING_LAYERS, PATTERN_INFO, RULES_DATABASE, get_rating_tier
    
    # Get base profile
    base_profile = await get_training_profile(db, user_id)
    if not base_profile or base_profile.get("status") == "insufficient_data":
        return base_profile
    
    # Apply reflection adjustments
    adjusted_profile = await get_reflection_adjusted_training(db, user_id, base_profile)
    
    # Get the active layer info
    active_layer = adjusted_profile.get("active_phase", "stability")
    micro_habit = adjusted_profile.get("micro_habit", "threat_blindness")
    
    # Get layer info
    layer_info = TRAINING_LAYERS.get(active_layer, {})
    pattern_info = PATTERN_INFO.get(micro_habit, {})
    
    # Get rules
    rating_tier = get_rating_tier(adjusted_profile.get("rating_at_computation", 1200))
    rules = RULES_DATABASE.get(active_layer, {}).get(micro_habit, {}).get(rating_tier, [
        "Focus on one concept per game",
        "Review your mistakes after each game"
    ])
    
    # Build data-driven focus
    return {
        "focus_type": "data_driven",
        "active_layer": active_layer,
        "active_layer_label": layer_info.get("label", active_layer),
        "active_layer_description": layer_info.get("description", ""),
        
        "micro_habit": micro_habit,
        "micro_habit_label": pattern_info.get("label", micro_habit),
        "micro_habit_description": pattern_info.get("description", ""),
        
        "rules": rules,
        
        "layer_breakdown": adjusted_profile.get("layer_breakdown", {}),
        "pattern_weights": adjusted_profile.get("pattern_weights", {}),
        
        "reflection_adjusted": adjusted_profile.get("reflection_adjusted", False),
        "reflection_count": adjusted_profile.get("reflection_count", 0),
        "training_reason": adjusted_profile.get("training_reason", "Based on your game data"),
        
        "example_positions": adjusted_profile.get("example_positions", []),
    }


async def should_override_curriculum(db, user_id: str) -> Dict:
    """
    Check if reflection data suggests overriding the rating-based curriculum.
    
    Returns recommendation on whether to use data-driven training.
    """
    impact_doc = await db.reflection_impacts.find_one({"user_id": user_id})
    
    if not impact_doc:
        return {
            "should_override": False,
            "reason": "No reflection data yet",
            "reflections_needed": 5,
        }
    
    total_reflections = impact_doc.get("total_reflections", 0)
    layer_boosts = impact_doc.get("layer_boosts", {})
    
    if total_reflections < 5:
        return {
            "should_override": False,
            "reason": f"Need more reflections ({total_reflections}/5)",
            "reflections_needed": 5 - total_reflections,
        }
    
    # Check if there's a clear dominant layer from reflections
    if layer_boosts:
        total_boost = sum(layer_boosts.values())
        dominant_layer = max(layer_boosts.keys(), key=lambda k: layer_boosts[k])
        dominant_pct = layer_boosts[dominant_layer] / total_boost if total_boost > 0 else 0
        
        if dominant_pct > 0.4:  # 40%+ of reflections point to one layer
            return {
                "should_override": True,
                "reason": f"Your reflections clearly indicate {dominant_layer} issues ({dominant_pct:.0%})",
                "dominant_layer": dominant_layer,
                "confidence": dominant_pct,
            }
    
    return {
        "should_override": False,
        "reason": "Reflections don't show a clear pattern yet",
        "reflections_needed": 0,
    }
