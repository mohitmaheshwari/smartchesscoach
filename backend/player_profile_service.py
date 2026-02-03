"""
Player Profile & Coaching Service for Chess Coach

This module provides:
1. PlayerProfile management - stores coaching context, weaknesses, strengths
2. Deterministic habit tracking with time decay
3. Coaching explanation contract enforcement
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
import math

# ==================== CONSTANTS & ENUMS ====================

class LearningStyle(str, Enum):
    CONCISE = "concise"
    DETAILED = "detailed"

class CoachingTone(str, Enum):
    FIRM = "firm"
    ENCOURAGING = "encouraging"
    BALANCED = "balanced"

class ImprovementTrend(str, Enum):
    IMPROVING = "improving"
    STUCK = "stuck"
    REGRESSING = "regressing"

class PlayerLevel(str, Enum):
    BEGINNER = "beginner"       # <1000 ELO estimate
    INTERMEDIATE = "intermediate"  # 1000-1500
    ADVANCED = "advanced"       # 1500-1800
    EXPERT = "expert"           # 1800+

# Predefined weakness categories - DO NOT INVENT NEW ONES
WEAKNESS_CATEGORIES = {
    "tactical": [
        "one_move_blunders",
        "pin_blindness",
        "fork_misses",
        "skewer_blindness",
        "back_rank_weakness",
        "discovered_attack_misses",
        "removal_of_defender_misses"
    ],
    "strategic": [
        "center_control_neglect",
        "poor_piece_activity",
        "lack_of_plan",
        "pawn_structure_damage",
        "weak_square_creation",
        "piece_coordination_issues"
    ],
    "king_safety": [
        "delayed_castling",
        "exposing_own_king",
        "king_walk_blunders",
        "ignoring_king_safety_threats"
    ],
    "opening_principles": [
        "premature_queen_moves",
        "neglecting_development",
        "moving_same_piece_twice",
        "ignoring_center_control",
        "not_castling_early"
    ],
    "endgame_fundamentals": [
        "king_activity_neglect",
        "pawn_race_errors",
        "opposition_misunderstanding",
        "rook_endgame_errors",
        "stalemate_blunders"
    ],
    "psychological": [
        "impulsive_moves",
        "tunnel_vision",
        "hope_chess",
        "time_trouble_blunders",
        "resignation_too_early",
        "overconfidence"
    ]
}

# Flatten for easy lookup
ALL_WEAKNESSES = []
for category, subcats in WEAKNESS_CATEGORIES.items():
    for subcat in subcats:
        ALL_WEAKNESSES.append({"category": category, "subcategory": subcat})

# Time decay constant (30 days)
DECAY_WINDOW_DAYS = 30

# ==================== COACHING EXPLANATION CONTRACT ====================

COACHING_EXPLANATION_SCHEMA = {
    "thinking_error": {
        "description": "The mental mistake that occurred (what was the player thinking wrong)",
        "required": True,
        "max_length": 200
    },
    "why_it_happened": {
        "description": "Root cause - why the player made this error",
        "required": True,
        "max_length": 200
    },
    "what_to_focus_on_next_time": {
        "description": "Actionable focus point for future games",
        "required": True,
        "max_length": 150
    },
    "one_repeatable_rule": {
        "description": "A simple, memorable rule the player can apply",
        "required": True,
        "max_length": 100
    }
}

def build_explanation_prompt_contract() -> str:
    """
    Build the strict explanation contract that MUST be enforced BEFORE LLM runs.
    This ensures consistent, human-like explanations.
    """
    return """
=== COACHING EXPLANATION CONTRACT (STRICTLY ENFORCED) ===

For EACH mistake you identify, you MUST provide exactly this structure:
{
    "thinking_error": "What mental mistake led to this move (max 200 chars)",
    "why_it_happened": "The root cause - why this thinking occurred (max 200 chars)", 
    "what_to_focus_on_next_time": "One actionable thing to focus on (max 150 chars)",
    "one_repeatable_rule": "A simple rule to remember, like 'Always check for pins before moving' (max 100 chars)"
}

FORBIDDEN in explanations:
- Move lists or variations (e.g., "1.e4 e5 2.Nf3...")
- Engine language (e.g., "+0.3 advantage", "eval: -1.2")  
- Computer evaluations or centipawn scores
- Multiple lessons per mistake - ONE core lesson only
- Vague advice like "be more careful"

REQUIRED:
- Human, conversational language
- Specific, actionable advice
- Reference to the player's history when relevant
- Short, speakable sentences
"""


def validate_explanation(explanation: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate an explanation against the strict schema.
    Returns (is_valid, list_of_errors)
    """
    errors = []
    
    for field, spec in COACHING_EXPLANATION_SCHEMA.items():
        if spec["required"] and field not in explanation:
            errors.append(f"Missing required field: {field}")
        elif field in explanation:
            value = explanation[field]
            if not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif len(value) > spec["max_length"]:
                errors.append(f"Field '{field}' exceeds max length of {spec['max_length']}")
            elif len(value) < 10:
                errors.append(f"Field '{field}' is too short (min 10 chars)")
    
    # Check for forbidden patterns
    full_text = " ".join(str(v) for v in explanation.values())
    
    # Check for move lists
    import re
    if re.search(r'\d+\.\s*[A-Za-z]+\d*\s+[A-Za-z]+\d*\s+\d+\.', full_text):
        errors.append("Contains forbidden move list")
    
    # Check for engine language
    engine_patterns = [r'[+-]\d+\.\d+', r'eval:', r'centipawn', r'cp\s*=', r'stockfish']
    for pattern in engine_patterns:
        if re.search(pattern, full_text.lower()):
            errors.append(f"Contains forbidden engine language (pattern: {pattern})")
    
    return len(errors) == 0, errors


# ==================== PLAYER PROFILE SCHEMA ====================

def create_default_profile(user_id: str, user_name: str) -> Dict[str, Any]:
    """Create a default player profile for new users"""
    return {
        "profile_id": f"profile_{user_id}",
        "user_id": user_id,
        "user_name": user_name,
        
        # Dynamic level estimation
        "estimated_level": PlayerLevel.INTERMEDIATE.value,
        "estimated_elo": 1200,  # Default starting estimate
        
        # Ranked weaknesses with decay tracking
        "top_weaknesses": [],  # [{category, subcategory, score, last_occurrence, occurrence_count}]
        
        # Strengths - things the player does well
        "strengths": [],  # [{category, subcategory, evidence_count}]
        
        # Learning preferences (AI-inferred initially)
        "learning_style": LearningStyle.CONCISE.value,
        "coaching_tone": CoachingTone.ENCOURAGING.value,
        
        # Performance tracking
        "improvement_trend": ImprovementTrend.STUCK.value,
        "games_analyzed_count": 0,
        "total_blunders": 0,
        "total_mistakes": 0,
        "total_best_moves": 0,
        
        # Trend windows for calculating improvement
        "recent_performance": [],  # Last 10 games: [{game_id, blunders, mistakes, best_moves, date}]
        "historical_performance": [],  # 10-30 games ago
        
        # Challenge mode tracking
        "challenges_attempted": 0,
        "challenges_solved": 0,
        "weakness_challenge_success": {},  # {weakness_key: {attempts, successes}}
        
        # Timestamps
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


# ==================== DETERMINISTIC HABIT TRACKING ====================

def calculate_decay_score(
    base_count: int,
    last_occurrence: datetime,
    current_time: Optional[datetime] = None
) -> float:
    """
    Calculate decayed score for a weakness.
    Uses exponential decay over DECAY_WINDOW_DAYS.
    
    Score = base_count * decay_factor
    decay_factor = e^(-days_since / DECAY_WINDOW_DAYS)
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    # Ensure timezone awareness
    if last_occurrence.tzinfo is None:
        last_occurrence = last_occurrence.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    
    days_since = (current_time - last_occurrence).days
    
    # Exponential decay
    decay_factor = math.exp(-days_since / DECAY_WINDOW_DAYS)
    
    return base_count * decay_factor


def normalize_weakness_key(category: str, subcategory: str) -> str:
    """Create a normalized key for weakness lookup"""
    return f"{category}:{subcategory}".lower().replace(" ", "_")


def categorize_weakness(raw_category: str, raw_subcategory: str) -> tuple[str, str]:
    """
    Map raw weakness to predefined categories.
    Returns the closest matching predefined category and subcategory.
    """
    raw_category = raw_category.lower().replace(" ", "_")
    raw_subcategory = raw_subcategory.lower().replace(" ", "_")
    
    # Direct match
    if raw_category in WEAKNESS_CATEGORIES:
        if raw_subcategory in WEAKNESS_CATEGORIES[raw_category]:
            return raw_category, raw_subcategory
    
    # Fuzzy matching for common variations
    mapping = {
        # Tactical mappings
        "blunder": ("tactical", "one_move_blunders"),
        "one_move_blunder": ("tactical", "one_move_blunders"),
        "pin": ("tactical", "pin_blindness"),
        "pinning": ("tactical", "pin_blindness"),
        "missed_pin": ("tactical", "pin_blindness"),
        "fork": ("tactical", "fork_misses"),
        "missed_fork": ("tactical", "fork_misses"),
        "skewer": ("tactical", "skewer_blindness"),
        "back_rank": ("tactical", "back_rank_weakness"),
        
        # Strategic mappings
        "center": ("strategic", "center_control_neglect"),
        "center_control": ("strategic", "center_control_neglect"),
        "piece_activity": ("strategic", "poor_piece_activity"),
        "passive_pieces": ("strategic", "poor_piece_activity"),
        "no_plan": ("strategic", "lack_of_plan"),
        "planless": ("strategic", "lack_of_plan"),
        "pawn_structure": ("strategic", "pawn_structure_damage"),
        
        # King safety mappings
        "castling": ("king_safety", "delayed_castling"),
        "late_castling": ("king_safety", "delayed_castling"),
        "king_safety": ("king_safety", "exposing_own_king"),
        "exposed_king": ("king_safety", "exposing_own_king"),
        
        # Opening mappings
        "development": ("opening_principles", "neglecting_development"),
        "early_queen": ("opening_principles", "premature_queen_moves"),
        
        # Endgame mappings
        "endgame": ("endgame_fundamentals", "king_activity_neglect"),
        "king_endgame": ("endgame_fundamentals", "king_activity_neglect"),
        "opposition": ("endgame_fundamentals", "opposition_misunderstanding"),
        
        # Psychological mappings
        "impulsive": ("psychological", "impulsive_moves"),
        "time_trouble": ("psychological", "time_trouble_blunders"),
        "tunnel": ("psychological", "tunnel_vision"),
        "hope": ("psychological", "hope_chess"),
    }
    
    # Check subcategory first
    if raw_subcategory in mapping:
        return mapping[raw_subcategory]
    
    # Check combined
    combined_key = f"{raw_category}_{raw_subcategory}"
    if combined_key in mapping:
        return mapping[combined_key]
    
    # Default to tactical/one_move_blunders if no match
    return "tactical", "one_move_blunders"


async def update_weakness_tracking(
    db,
    user_id: str,
    weaknesses: List[Dict[str, str]],
    current_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Update deterministic weakness tracking.
    This is rule-based, NOT relying on embeddings.
    
    Returns the updated weakness rankings.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    # Get current profile
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"error": "Profile not found"}
    
    current_weaknesses = profile.get("top_weaknesses", [])
    weakness_map = {
        normalize_weakness_key(w["category"], w["subcategory"]): w 
        for w in current_weaknesses
    }
    
    # Process each new weakness
    for weakness in weaknesses:
        # Categorize to predefined categories
        category, subcategory = categorize_weakness(
            weakness.get("category", "tactical"),
            weakness.get("subcategory", "one_move_blunders")
        )
        
        key = normalize_weakness_key(category, subcategory)
        
        if key in weakness_map:
            # Update existing weakness
            weakness_map[key]["occurrence_count"] += 1
            weakness_map[key]["last_occurrence"] = current_time.isoformat()
        else:
            # Add new weakness
            weakness_map[key] = {
                "category": category,
                "subcategory": subcategory,
                "occurrence_count": 1,
                "last_occurrence": current_time.isoformat(),
                "first_occurrence": current_time.isoformat()
            }
    
    # Calculate decayed scores for all weaknesses
    ranked_weaknesses = []
    for key, w in weakness_map.items():
        last_occ = w["last_occurrence"]
        if isinstance(last_occ, str):
            last_occ = datetime.fromisoformat(last_occ.replace('Z', '+00:00'))
        
        decayed_score = calculate_decay_score(
            w["occurrence_count"],
            last_occ,
            current_time
        )
        
        ranked_weaknesses.append({
            **w,
            "decayed_score": round(decayed_score, 2)
        })
    
    # Sort by decayed score (highest first)
    ranked_weaknesses.sort(key=lambda x: x["decayed_score"], reverse=True)
    
    # Keep top 10 weaknesses
    top_weaknesses = ranked_weaknesses[:10]
    
    # Update profile
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "top_weaknesses": top_weaknesses,
            "last_updated": current_time.isoformat()
        }}
    )
    
    return {"top_weaknesses": top_weaknesses[:3]}  # Return top 3 for immediate use


async def check_weakness_resolution(
    db,
    user_id: str,
    weakness_key: str
) -> bool:
    """
    Check if a weakness should be resolved (auto-demoted) based on challenge success.
    Weakness resolves when challenge success rate exceeds 70%.
    """
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not profile:
        return False
    
    challenge_success = profile.get("weakness_challenge_success", {})
    
    if weakness_key not in challenge_success:
        return False
    
    stats = challenge_success[weakness_key]
    attempts = stats.get("attempts", 0)
    successes = stats.get("successes", 0)
    
    if attempts < 5:  # Need at least 5 attempts
        return False
    
    success_rate = successes / attempts
    return success_rate > 0.7


async def record_challenge_result(
    db,
    user_id: str,
    weakness_category: str,
    weakness_subcategory: str,
    success: bool
) -> Dict[str, Any]:
    """
    Record a challenge result and potentially resolve weakness.
    """
    weakness_key = normalize_weakness_key(weakness_category, weakness_subcategory)
    current_time = datetime.now(timezone.utc)
    
    # Get current profile
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"error": "Profile not found"}
    
    # Update challenge stats
    challenge_success = profile.get("weakness_challenge_success", {})
    
    if weakness_key not in challenge_success:
        challenge_success[weakness_key] = {"attempts": 0, "successes": 0}
    
    challenge_success[weakness_key]["attempts"] += 1
    if success:
        challenge_success[weakness_key]["successes"] += 1
    
    # Check if weakness should be resolved
    should_resolve = False
    stats = challenge_success[weakness_key]
    if stats["attempts"] >= 5:
        success_rate = stats["successes"] / stats["attempts"]
        if success_rate > 0.7:
            should_resolve = True
    
    # Update profile
    update_data = {
        "weakness_challenge_success": challenge_success,
        "challenges_attempted": profile.get("challenges_attempted", 0) + 1,
        "last_updated": current_time.isoformat()
    }
    
    if success:
        update_data["challenges_solved"] = profile.get("challenges_solved", 0) + 1
    
    # If weakness should be resolved, demote it significantly
    if should_resolve:
        top_weaknesses = profile.get("top_weaknesses", [])
        for w in top_weaknesses:
            if normalize_weakness_key(w["category"], w["subcategory"]) == weakness_key:
                # Reduce occurrence count significantly
                w["occurrence_count"] = max(1, w["occurrence_count"] // 2)
                w["decayed_score"] = round(w["decayed_score"] / 2, 2)
                break
        
        # Re-sort
        top_weaknesses.sort(key=lambda x: x.get("decayed_score", 0), reverse=True)
        update_data["top_weaknesses"] = top_weaknesses
    
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    return {
        "success": success,
        "weakness_key": weakness_key,
        "resolved": should_resolve,
        "current_stats": challenge_success[weakness_key]
    }


# ==================== PROFILE MANAGEMENT ====================

async def get_or_create_profile(db, user_id: str, user_name: str) -> Dict[str, Any]:
    """Get existing profile or create a new one"""
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if profile:
        return profile
    
    # Create new profile
    new_profile = create_default_profile(user_id, user_name)
    await db.player_profiles.insert_one(new_profile)
    
    # Remove _id added by MongoDB
    new_profile.pop('_id', None)
    
    return new_profile


async def update_profile_after_analysis(
    db,
    user_id: str,
    game_id: str,
    blunders: int,
    mistakes: int,
    best_moves: int,
    identified_weaknesses: List[Dict[str, str]],
    identified_strengths: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Update player profile after a game analysis.
    This is called after every game to keep the profile current.
    """
    current_time = datetime.now(timezone.utc)
    
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not profile:
        return {"error": "Profile not found"}
    
    # Update game counts
    games_analyzed = profile.get("games_analyzed_count", 0) + 1
    total_blunders = profile.get("total_blunders", 0) + blunders
    total_mistakes = profile.get("total_mistakes", 0) + mistakes
    total_best_moves = profile.get("total_best_moves", 0) + best_moves
    
    # Update recent performance window
    recent_performance = profile.get("recent_performance", [])
    game_performance = {
        "game_id": game_id,
        "blunders": blunders,
        "mistakes": mistakes,
        "best_moves": best_moves,
        "date": current_time.isoformat()
    }
    
    recent_performance.insert(0, game_performance)
    
    # Move old games to historical
    historical_performance = profile.get("historical_performance", [])
    if len(recent_performance) > 10:
        # Move games 11-20 to historical
        historical_performance = recent_performance[10:20] + historical_performance
        recent_performance = recent_performance[:10]
        historical_performance = historical_performance[:20]  # Keep last 20 in historical
    
    # Calculate improvement trend
    improvement_trend = calculate_improvement_trend(recent_performance, historical_performance)
    
    # Estimate player level
    estimated_level, estimated_elo = estimate_player_level(
        games_analyzed,
        total_blunders,
        total_mistakes,
        total_best_moves
    )
    
    # Infer learning style and coaching tone
    learning_style, coaching_tone = infer_coaching_preferences(
        profile,
        games_analyzed,
        improvement_trend
    )
    
    # Update weaknesses
    await update_weakness_tracking(db, user_id, identified_weaknesses, current_time)
    
    # Update strengths if provided
    strengths = profile.get("strengths", [])
    if identified_strengths:
        for strength in identified_strengths:
            strength_key = normalize_weakness_key(
                strength.get("category", "tactical"),
                strength.get("subcategory", "general")
            )
            
            # Check if strength already exists
            found = False
            for s in strengths:
                if normalize_weakness_key(s["category"], s["subcategory"]) == strength_key:
                    s["evidence_count"] = s.get("evidence_count", 1) + 1
                    found = True
                    break
            
            if not found:
                strengths.append({
                    "category": strength.get("category"),
                    "subcategory": strength.get("subcategory"),
                    "evidence_count": 1
                })
        
        # Sort and keep top 5 strengths
        strengths.sort(key=lambda x: x.get("evidence_count", 0), reverse=True)
        strengths = strengths[:5]
    
    # Build update document
    update_data = {
        "games_analyzed_count": games_analyzed,
        "total_blunders": total_blunders,
        "total_mistakes": total_mistakes,
        "total_best_moves": total_best_moves,
        "recent_performance": recent_performance,
        "historical_performance": historical_performance,
        "improvement_trend": improvement_trend,
        "estimated_level": estimated_level,
        "estimated_elo": estimated_elo,
        "learning_style": learning_style,
        "coaching_tone": coaching_tone,
        "strengths": strengths,
        "last_updated": current_time.isoformat()
    }
    
    await db.player_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    # Get updated profile
    updated_profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    return updated_profile


def calculate_improvement_trend(
    recent: List[Dict],
    historical: List[Dict]
) -> str:
    """
    Calculate improvement trend by comparing recent to historical performance.
    """
    if len(recent) < 3:
        return ImprovementTrend.STUCK.value
    
    if not historical:
        # Only recent games, compare first half to second half
        half = len(recent) // 2
        recent_half = recent[:half]
        older_half = recent[half:]
    else:
        recent_half = recent[:5]
        older_half = historical[:5] if len(historical) >= 5 else recent[5:10]
    
    if not older_half:
        return ImprovementTrend.STUCK.value
    
    # Calculate error rates
    recent_errors = sum(g.get("blunders", 0) + g.get("mistakes", 0) for g in recent_half)
    recent_best = sum(g.get("best_moves", 0) for g in recent_half)
    
    older_errors = sum(g.get("blunders", 0) + g.get("mistakes", 0) for g in older_half)
    older_best = sum(g.get("best_moves", 0) for g in older_half)
    
    # Calculate improvement ratio
    recent_ratio = recent_best / max(recent_errors + recent_best, 1)
    older_ratio = older_best / max(older_errors + older_best, 1)
    
    # Determine trend
    if recent_ratio > older_ratio * 1.1:  # 10% improvement threshold
        return ImprovementTrend.IMPROVING.value
    elif recent_ratio < older_ratio * 0.9:  # 10% regression threshold
        return ImprovementTrend.REGRESSING.value
    else:
        return ImprovementTrend.STUCK.value


def estimate_player_level(
    games_analyzed: int,
    total_blunders: int,
    total_mistakes: int,
    total_best_moves: int
) -> tuple[str, int]:
    """
    Estimate player level based on error and best move rates.
    Returns (level, estimated_elo)
    """
    if games_analyzed < 3:
        return PlayerLevel.INTERMEDIATE.value, 1200
    
    # Calculate per-game averages
    avg_blunders = total_blunders / games_analyzed
    avg_mistakes = total_mistakes / games_analyzed
    avg_best = total_best_moves / games_analyzed
    
    # Error score (lower is better)
    error_score = avg_blunders * 3 + avg_mistakes * 1.5
    
    # Best move ratio
    total_eval_moves = avg_blunders + avg_mistakes + avg_best
    best_ratio = avg_best / max(total_eval_moves, 1)
    
    # Estimate ELO and level
    if error_score > 5 or best_ratio < 0.2:
        return PlayerLevel.BEGINNER.value, max(600, int(1000 - error_score * 30))
    elif error_score > 3 or best_ratio < 0.35:
        return PlayerLevel.INTERMEDIATE.value, int(1200 + (0.35 - error_score/10) * 500)
    elif error_score > 1.5 or best_ratio < 0.5:
        return PlayerLevel.ADVANCED.value, int(1500 + (0.5 - error_score/10) * 400)
    else:
        return PlayerLevel.EXPERT.value, int(1800 + best_ratio * 200)


def infer_coaching_preferences(
    profile: Dict[str, Any],
    games_analyzed: int,
    improvement_trend: str
) -> tuple[str, str]:
    """
    Infer learning style and coaching tone based on player behavior.
    """
    # Default values
    learning_style = profile.get("learning_style", LearningStyle.CONCISE.value)
    coaching_tone = profile.get("coaching_tone", CoachingTone.ENCOURAGING.value)
    
    # If player is regressing, be more encouraging
    if improvement_trend == ImprovementTrend.REGRESSING.value:
        coaching_tone = CoachingTone.ENCOURAGING.value
    
    # If player is improving, can be more balanced/firm
    if improvement_trend == ImprovementTrend.IMPROVING.value:
        if games_analyzed > 10:
            coaching_tone = CoachingTone.BALANCED.value
    
    # Experienced players might prefer detailed explanations
    if games_analyzed > 20:
        learning_style = LearningStyle.DETAILED.value
    
    return learning_style, coaching_tone


# ==================== PROMPT BUILDING ====================

def build_profile_context_for_prompt(profile: Dict[str, Any]) -> str:
    """
    Build the player profile context that MUST be injected into every AI prompt.
    """
    if not profile:
        return "New player - no coaching history yet."
    
    context_parts = ["=== PLAYER COACHING PROFILE ==="]
    
    # Level and trend
    context_parts.append(f"Player Level: {profile.get('estimated_level', 'intermediate').upper()} (Est. ELO: {profile.get('estimated_elo', 1200)})")
    
    trend = profile.get('improvement_trend', 'stuck')
    trend_emoji = {"improving": "📈", "stuck": "➡️", "regressing": "📉"}.get(trend, "➡️")
    context_parts.append(f"Trend: {trend_emoji} {trend.upper()}")
    
    # Top weaknesses
    top_weaknesses = profile.get('top_weaknesses', [])[:3]
    if top_weaknesses:
        context_parts.append("\nTOP 3 WEAKNESSES (ranked by frequency with time decay):")
        for i, w in enumerate(top_weaknesses, 1):
            context_parts.append(
                f"  {i}. {w['subcategory'].replace('_', ' ').title()} ({w['category']}) "
                f"- Score: {w.get('decayed_score', 0):.1f}"
            )
    else:
        context_parts.append("\nNo weaknesses identified yet.")
    
    # Strengths
    strengths = profile.get('strengths', [])[:3]
    if strengths:
        context_parts.append("\nSTRENGTHS:")
        for s in strengths:
            context_parts.append(f"  - {s['subcategory'].replace('_', ' ').title()} ({s['category']})")
    
    # Coaching preferences
    learning_style = profile.get('learning_style', 'concise')
    coaching_tone = profile.get('coaching_tone', 'encouraging')
    
    context_parts.append("\nCOACHING PREFERENCES:")
    context_parts.append(f"  - Learning style: {learning_style.upper()} (keep explanations {'brief and actionable' if learning_style == 'concise' else 'detailed with examples'})")
    context_parts.append(f"  - Tone: {coaching_tone.upper()}")
    
    # Games analyzed
    games = profile.get('games_analyzed_count', 0)
    context_parts.append(f"\nGames Analyzed: {games}")
    
    # Recent performance
    if trend == "improving":
        context_parts.append("Note: Player is IMPROVING - acknowledge their progress!")
    elif trend == "regressing":
        context_parts.append("Note: Player is struggling - be extra supportive and focus on fundamentals.")
    
    return "\n".join(context_parts)


def build_full_coaching_prompt(
    profile_context: str,
    rag_context: str,
    explanation_contract: str,
    user_name: str,
    user_color: str
) -> str:
    """
    Build the complete system prompt for AI coaching.
    Combines profile, RAG context, and explanation contract.
    """
    return f"""You are a personal chess coach for {user_name}. They played as {user_color} in this game.

{profile_context}

{rag_context}

{explanation_contract}

Your coaching approach:
- If this player has shown a weakness before, EXPLICITLY reference it: "This is your {profile_context.split('WEAKNESSES')[1].split('.')[0] if 'WEAKNESSES' in profile_context else 'recurring'} issue - let's address it."
- If they're improving, celebrate: "Great to see you avoiding the {'{weakness}'} issue we talked about!"
- Keep explanations {profile_context.split('Learning style:')[1].split()[0].lower() if 'Learning style:' in profile_context else 'concise'}
- Be {profile_context.split('Tone:')[1].split()[0].lower() if 'Tone:' in profile_context else 'encouraging'}

Remember: One core lesson per mistake. No move lists. No engine language. Human, speakable advice only."""
