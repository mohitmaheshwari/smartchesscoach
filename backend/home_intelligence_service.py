"""
Home Intelligence Service

Provides deterministic, data-driven context for the Coach Home page.
Computes the user's development phase, focus capacity, and actionable advice.

Key Concepts:
- Development Phase: Where the user is in their chess journey
- Focus Capacity: How much cognitive load the user can handle
- Active Advice: The ONE thing to do next

Based on analysis of last 20 games with recency weighting.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ============================================
# DEVELOPMENT PHASES (Deterministic Model)
# ============================================

DEVELOPMENT_PHASES = {
    "tactical_discipline": {
        "name": "Tactical Discipline",
        "description": "Building solid foundations - reducing blunders and seeing threats",
        "color": "amber",
        "icon": "shield",
        "requirement": "Average 2+ blunders per game",
    },
    "pattern_control": {
        "name": "Pattern Control",
        "description": "Recognizing and avoiding repeated mistake patterns",
        "color": "blue",
        "icon": "brain",
        "requirement": "Same mistake pattern 3+ times in 10 games",
    },
    "calculation_depth": {
        "name": "Calculation Depth",
        "description": "Thinking deeper before committing to moves",
        "color": "violet",
        "icon": "sparkles",
        "requirement": "Missing winning tactics or allowing forced sequences",
    },
    "positional_sense": {
        "name": "Positional Understanding",
        "description": "Developing long-term strategic vision",
        "color": "emerald",
        "icon": "target",
        "requirement": "Strong tactically but struggling in quiet positions",
    },
    "time_mastery": {
        "name": "Time Mastery",
        "description": "Balancing speed and accuracy under the clock",
        "color": "orange",
        "icon": "clock",
        "requirement": "Frequent time trouble or impulsive moves",
    },
    "advanced_refinement": {
        "name": "Advanced Refinement",
        "description": "Polishing subtle aspects of play",
        "color": "primary",
        "icon": "star",
        "requirement": "Solid fundamentals, working on nuances",
    },
}


# ============================================
# FOCUS CAPACITY MODEL
# ============================================

def calculate_focus_capacity(
    blunders_per_game: float,
    mistakes_per_game: float,
    games_analyzed: int,
    recent_reflection_count: int,
) -> Dict:
    """
    Calculate how much cognitive load the user can handle.
    
    Returns a focus capacity level:
    - "single": Can handle ONE focus point (high error rate)
    - "dual": Can handle TWO focus points (moderate error rate)
    - "multi": Can handle multiple focus points (low error rate)
    """
    
    # Error score (lower is better)
    error_score = (blunders_per_game * 2) + mistakes_per_game
    
    # Reflection engagement score
    engagement = min(recent_reflection_count / 10, 1.0)  # Max out at 10 reflections
    
    # Confidence based on sample size
    confidence = min(games_analyzed / 15, 1.0)
    
    # Determine capacity
    if error_score >= 4.0:
        capacity = "single"
        advice_count = 1
        message = "Focus on one thing at a time"
    elif error_score >= 2.0:
        capacity = "dual"
        advice_count = 2
        message = "You can handle two focus points"
    else:
        capacity = "multi"
        advice_count = 3
        message = "You're ready for deeper work"
    
    return {
        "level": capacity,
        "advice_count": advice_count,
        "message": message,
        "error_score": round(error_score, 2),
        "engagement": round(engagement, 2),
        "confidence": round(confidence, 2),
    }


# ============================================
# DEVELOPMENT PHASE DETECTION
# ============================================

def detect_development_phase(
    blunders_per_game: float,
    mistakes_per_game: float,
    recurring_patterns: List[Dict],
    missed_tactics_rate: float,
    time_trouble_rate: float,
    positional_errors_rate: float,
) -> Dict:
    """
    Detect the user's current development phase based on their data.
    Returns the phase that needs the most attention.
    """
    
    scores = {}
    
    # Phase 1: Tactical Discipline (high blunder rate)
    if blunders_per_game >= 2.0:
        scores["tactical_discipline"] = blunders_per_game * 20
    elif blunders_per_game >= 1.0:
        scores["tactical_discipline"] = blunders_per_game * 10
    else:
        scores["tactical_discipline"] = blunders_per_game * 5
    
    # Phase 2: Pattern Control (recurring mistakes)
    recurring_count = len([p for p in recurring_patterns if p.get("count", 0) >= 3])
    scores["pattern_control"] = recurring_count * 15
    
    # Phase 3: Calculation Depth (missed tactics)
    scores["calculation_depth"] = missed_tactics_rate * 25
    
    # Phase 4: Positional Sense
    scores["positional_sense"] = positional_errors_rate * 20
    
    # Phase 5: Time Mastery
    scores["time_mastery"] = time_trouble_rate * 30
    
    # Find the highest scoring (most problematic) phase
    if not scores or all(v == 0 for v in scores.values()):
        primary_phase = "advanced_refinement"
        primary_score = 0
    else:
        primary_phase = max(scores.items(), key=lambda x: x[1])[0]
        primary_score = scores[primary_phase]
    
    phase_info = DEVELOPMENT_PHASES[primary_phase]
    
    return {
        "phase_key": primary_phase,
        "phase_name": phase_info["name"],
        "description": phase_info["description"],
        "color": phase_info["color"],
        "icon": phase_info["icon"],
        "score": round(primary_score, 1),
        "all_scores": {k: round(v, 1) for k, v in scores.items()},
    }


# ============================================
# ACTIVE ADVICE GENERATION
# ============================================

ADVICE_TEMPLATES = {
    "tactical_discipline": [
        {
            "primary": "Before every move, ask: 'What can my opponent do to me?'",
            "secondary": "After choosing your move, do a final safety check.",
            "drill_type": "threat_detection",
        },
    ],
    "pattern_control": [
        {
            "primary": "Watch for {pattern} - you've made this mistake {count} times recently.",
            "secondary": "Set a mental alarm for this specific situation.",
            "drill_type": "pattern_recognition",
        },
    ],
    "calculation_depth": [
        {
            "primary": "Force yourself to calculate ONE move deeper before deciding.",
            "secondary": "Use CCT: Checks, Captures, Threats every move.",
            "drill_type": "calculation",
        },
    ],
    "positional_sense": [
        {
            "primary": "Before moving, ask: 'What's the plan for the next 3 moves?'",
            "secondary": "Identify the weak squares in the position.",
            "drill_type": "positional",
        },
    ],
    "time_mastery": [
        {
            "primary": "Set a rule: No move takes more than 1 minute.",
            "secondary": "Play the first 10 moves faster to save time.",
            "drill_type": "speed",
        },
    ],
    "advanced_refinement": [
        {
            "primary": "Focus on precision - small improvements add up.",
            "secondary": "Study master games in your favorite openings.",
            "drill_type": "precision",
        },
    ],
}


def generate_active_advice(
    phase: str,
    recurring_patterns: List[Dict],
    last_game_issues: List[Dict],
    focus_capacity: str,
) -> Dict:
    """
    Generate actionable advice based on the user's current phase and data.
    """
    
    advice_template = ADVICE_TEMPLATES.get(phase, ADVICE_TEMPLATES["advanced_refinement"])[0]
    
    primary_advice = advice_template["primary"]
    secondary_advice = advice_template["secondary"]
    drill_type = advice_template["drill_type"]
    
    # Personalize for pattern_control phase
    if phase == "pattern_control" and recurring_patterns:
        top_pattern = recurring_patterns[0]
        pattern_name = top_pattern.get("pattern", "this pattern").replace("_", " ").title()
        count = top_pattern.get("count", 3)
        primary_advice = primary_advice.format(pattern=pattern_name, count=count)
    
    # Add last game context if available
    last_game_context = None
    if last_game_issues:
        top_issue = last_game_issues[0]
        last_game_context = f"In your last game, you {top_issue.get('description', 'made a key error')}."
    
    return {
        "primary": primary_advice,
        "secondary": secondary_advice if focus_capacity != "single" else None,
        "drill_type": drill_type,
        "last_game_context": last_game_context,
    }


# ============================================
# MAIN SERVICE FUNCTION
# ============================================

async def get_home_intelligence(db, user_id: str) -> Dict:
    """
    Generate the complete home intelligence data for a user.
    
    Returns:
    {
        "has_data": bool,
        "development_phase": {...},
        "focus_capacity": {...},
        "active_advice": {...},
        "last_game": {...},
        "recommended_drill": {...},
    }
    """
    
    # Fetch recent analyses (last 20 games)
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("analyzed_at", -1).limit(20).to_list(20)
    
    if len(analyses) < 3:
        return {
            "has_data": False,
            "games_analyzed": len(analyses),
            "minimum_required": 3,
            "message": "Analyze at least 3 games to unlock personalized coaching.",
        }
    
    # Fetch cognitive gap patterns
    gap_aggregates = await db.cognitive_gap_aggregates.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    # Fetch recent reflections count
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_reflections = await db.reflection_sessions.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": one_week_ago}
    })
    
    # Calculate metrics from analyses
    total_blunders = 0
    total_mistakes = 0
    total_games = len(analyses)
    time_trouble_games = 0
    positional_error_games = 0
    missed_tactics_games = 0
    
    for a in analyses:
        # Read blunders/mistakes from stockfish_analysis (correct location)
        sf = a.get("stockfish_analysis", {})
        total_blunders += sf.get("blunders", 0) or a.get("blunders", 0)
        total_mistakes += sf.get("mistakes", 0) or a.get("mistakes", 0)
        
        # Check for time trouble markers
        moves = sf.get("move_evaluations", [])
        
        # Time trouble: mistakes in last 10 moves
        late_mistakes = sum(1 for m in moves if m.get("move_number", 0) > (len(moves) - 10) and m.get("evaluation") in ["blunder", "mistake"])
        if late_mistakes >= 2:
            time_trouble_games += 1
        
        # Missed tactics: had winning move but didn't play it
        missed = sum(1 for m in moves if m.get("missed_win") or m.get("cp_loss", 0) >= 200)
        if missed >= 1:
            missed_tactics_games += 1
        
        # Positional errors: slow positional decline
        positional_drops = sum(1 for m in moves if 50 <= m.get("cp_loss", 0) < 150)
        if positional_drops >= 3:
            positional_error_games += 1
    
    blunders_per_game = total_blunders / total_games
    mistakes_per_game = total_mistakes / total_games
    time_trouble_rate = time_trouble_games / total_games
    missed_tactics_rate = missed_tactics_games / total_games
    positional_errors_rate = positional_error_games / total_games
    
    # Get recurring patterns from gap aggregates
    recurring_patterns = []
    if gap_aggregates:
        patterns = gap_aggregates.get("patterns", {})
        for pattern_key, pattern_data in patterns.items():
            count = pattern_data.get("total_count", 0)
            if count >= 3:
                recurring_patterns.append({
                    "pattern": pattern_key,
                    "count": count,
                    "trend": pattern_data.get("trend", "stable"),
                })
        recurring_patterns.sort(key=lambda x: x["count"], reverse=True)
    
    # Calculate focus capacity
    focus_capacity = calculate_focus_capacity(
        blunders_per_game=blunders_per_game,
        mistakes_per_game=mistakes_per_game,
        games_analyzed=total_games,
        recent_reflection_count=recent_reflections,
    )
    
    # Detect development phase
    development_phase = detect_development_phase(
        blunders_per_game=blunders_per_game,
        mistakes_per_game=mistakes_per_game,
        recurring_patterns=recurring_patterns,
        missed_tactics_rate=missed_tactics_rate,
        time_trouble_rate=time_trouble_rate,
        positional_errors_rate=positional_errors_rate,
    )
    
    # Get last game issues
    last_game = analyses[0] if analyses else None
    last_game_issues = []
    if last_game:
        sf = last_game.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        for m in moves:
            if m.get("evaluation") in ["blunder", "mistake"]:
                last_game_issues.append({
                    "move_number": m.get("move_number"),
                    "description": f"made a {m.get('evaluation')} on move {m.get('move_number')}",
                    "cp_loss": m.get("cp_loss", 0),
                })
        last_game_issues.sort(key=lambda x: x.get("cp_loss", 0), reverse=True)
    
    # Generate active advice
    active_advice = generate_active_advice(
        phase=development_phase["phase_key"],
        recurring_patterns=recurring_patterns,
        last_game_issues=last_game_issues[:3],
        focus_capacity=focus_capacity["level"],
    )
    
    # Last game summary
    last_game_summary = None
    if last_game:
        sf_data = last_game.get("stockfish_analysis", {})
        blunders = sf_data.get("blunders", 0) or last_game.get("blunders", 0)
        mistakes = sf_data.get("mistakes", 0) or last_game.get("mistakes", 0)
        analyzed_at = last_game.get("analyzed_at")
        
        # Get game details (result, opponent) from games collection
        game_doc = await db.games.find_one(
            {"game_id": last_game.get("game_id")},
            {"opponent_name": 1, "white_player": 1, "black_player": 1, "user_color": 1, "result": 1}
        )
        
        result = "unknown"
        opponent = "Unknown"
        if game_doc:
            result = game_doc.get("result", "unknown")
            opponent = game_doc.get("opponent_name")
            if not opponent:
                # Fallback: derive from white/black players
                user_color = game_doc.get("user_color", "white")
                if user_color == "white":
                    opponent = game_doc.get("black_player", "Unknown")
                else:
                    opponent = game_doc.get("white_player", "Unknown")
        
        # Check if it's a "new" game (within last 24 hours)
        is_new = False
        if analyzed_at:
            if isinstance(analyzed_at, str):
                analyzed_at = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
            # Ensure timezone-aware comparison
            if analyzed_at.tzinfo is None:
                analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)
            is_new = (datetime.now(timezone.utc) - analyzed_at).total_seconds() < 86400  # 24 hours
        
        last_game_summary = {
            "game_id": last_game.get("game_id"),
            "result": result,
            "opponent": opponent,
            "blunders": blunders,
            "mistakes": mistakes,
            "is_new": is_new,
            "analyzed_at": analyzed_at.isoformat() if analyzed_at else None,
        }
        
        # Add recurring pattern context to last game
        # Check if any issues in this game match recurring patterns
        if recurring_patterns and last_game_issues:
            recurring_names = [p.get("name") for p in recurring_patterns]
            for issue in last_game_issues[:3]:
                issue_category = issue.get("category", "")
                # Match patterns like "blunder_when_winning" -> "Losing focus when ahead"
                if "winning" in issue_category.lower() and any("winning" in r.lower() or "ahead" in r.lower() for r in recurring_names):
                    last_game_summary["recurring_match"] = {
                        "is_recurring": True,
                        "pattern": "losing focus when ahead",
                        "times_this_week": recurring_patterns[0].get("count", 0),
                    }
                    break
                elif "threat" in issue_category.lower() and any("threat" in r.lower() for r in recurring_names):
                    last_game_summary["recurring_match"] = {
                        "is_recurring": True,
                        "pattern": "missing opponent threats",
                        "times_this_week": recurring_patterns[0].get("count", 0),
                    }
                    break
    
    # Recommended drill
    drill_map = {
        "threat_detection": {"title": "Threat Awareness", "description": "Practice spotting opponent's threats"},
        "pattern_recognition": {"title": "Pattern Drill", "description": "Reinforce correct patterns"},
        "calculation": {"title": "Calculation Depth", "description": "Practice calculating deeper"},
        "positional": {"title": "Positional Puzzle", "description": "Find the best strategic move"},
        "speed": {"title": "Speed Drill", "description": "Make good decisions faster"},
        "precision": {"title": "Precision Puzzle", "description": "Find the most accurate move"},
    }
    
    recommended_drill = drill_map.get(
        active_advice.get("drill_type", "threat_detection"),
        drill_map["threat_detection"]
    )
    recommended_drill["type"] = active_advice.get("drill_type", "threat_detection")
    
    return {
        "has_data": True,
        "games_analyzed": total_games,
        "development_phase": development_phase,
        "focus_capacity": focus_capacity,
        "active_advice": active_advice,
        "last_game": last_game_summary,
        "recommended_drill": recommended_drill,
        "recurring_patterns": recurring_patterns[:3],
        "stats": {
            "blunders_per_game": round(blunders_per_game, 2),
            "mistakes_per_game": round(mistakes_per_game, 2),
            "time_trouble_rate": round(time_trouble_rate * 100, 1),
        },
    }
