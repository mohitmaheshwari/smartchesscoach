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
    coach_prescription: Optional[Dict] = None,
) -> Dict:
    """
    Generate actionable advice based on the user's current phase and data.

    If the curriculum brain has a prescription (from post-game analysis),
    that takes priority — the coach knows what the student needs.
    """

    # === CURRICULUM BRAIN PRESCRIPTION OVERRIDES EVERYTHING ===
    # The coach analyzed your games and picked ONE thing. That's the advice.
    if coach_prescription and coach_prescription.get("focus"):
        focus = coach_prescription["focus"]
        reason = coach_prescription.get("reason", "")
        ptype = coach_prescription.get("type", "pattern_drill")

        # Map prescription to human-readable advice
        focus_label = focus.replace("_", " ").title()

        # Map prescription type to drill type
        drill_map = {
            "endgame_lesson": "calculation",
            "pattern_drill": "pattern_recognition",
            "habit": "threat_detection",
            "trap_lesson": "pattern_recognition",
            "opening_lesson": "positional",
        }
        drill_type = drill_map.get(ptype, "pattern_recognition")

        # Map prescription to actionable content
        if ptype == "endgame_lesson":
            primary = f"Coach's focus: Learn the {focus_label} technique."
            action = {"type": "endgame_lesson", "lesson_key": focus, "label": f"Practice {focus_label}"}
        elif ptype == "trap_lesson":
            # focus format: "trap:italian-game:fried_liver_attack"
            parts = focus.split(":", 2)
            opening_key = parts[1] if len(parts) > 1 else ""
            trap_name = (parts[2] if len(parts) > 2 else focus).replace("_", " ").title()
            primary = reason if reason else f"Coach's focus: Learn the {trap_name} trap."
            action = {"type": "trap_lesson", "opening_key": opening_key, "trap_name": trap_name, "label": f"Learn {trap_name}"}
        elif ptype == "opening_lesson":
            # focus format: "opening:italian_game"
            opening_key = focus.replace("opening:", "")
            opening_name = opening_key.replace("_", " ").replace("-", " ").title()
            primary = reason if reason else f"Coach's focus: Study the {opening_name}."
            action = {"type": "opening_lesson", "opening_key": opening_key, "label": f"Study {opening_name}"}
        elif focus in ("hanging_piece", "missed_fork", "missed_pin", "missed_skewer"):
            pattern_key = focus.replace("missed_", "")
            primary = f"Coach's focus: {focus_label}. {reason}" if reason else f"Coach's focus: Stop {focus_label.lower()} mistakes."
            action = {"type": "pattern_puzzle", "pattern": pattern_key, "label": f"Train {focus_label}"}
        else:
            primary = f"Coach's focus: {focus_label}." + (f" {reason}" if reason else "")
            action = {"type": "habit_drill", "habit": focus, "label": f"Work on {focus_label}"}

        return {
            "primary": primary,
            "secondary": None,
            "drill_type": drill_type,
            "last_game_context": reason if reason else None,
            "coach_prescription": {
                "focus": focus,
                "type": ptype,
                "action": action,
            },
        }

    # === FALLBACK: Generic phase-based advice (no prescription) ===
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

async def _get_training_recommendation(db, user_id: str, recurring_patterns: list) -> Optional[Dict]:
    """
    Combine game weakness data + puzzle solve data to recommend what to train.
    Returns a focused recommendation the coach can use.
    """
    try:
        from services.community_training_service import get_user_pattern_stats

        puzzle_stats = await get_user_pattern_stats(db, user_id)
        puzzle_map = {s["pattern"]: s for s in puzzle_stats}

        if not recurring_patterns:
            return None

        for rp in recurring_patterns[:3]:
            pattern = rp.get("pattern", "")
            game_count = rp.get("count", 0)
            ps = puzzle_map.get(pattern)

            if ps and ps.get("total_attempts", 0) >= 3:
                solve_rate = ps.get("solve_rate", 0)
                if solve_rate >= 75:
                    # They know it in training but still fail in games
                    return {
                        "pattern": pattern,
                        "label": pattern.replace("_", " ").title(),
                        "status": "knowledge_gap",
                        "message": f"You can solve {pattern.replace('_', ' ')} puzzles — but it's still showing up in your games. Play slower and look for it.",
                    }
                else:
                    # They can't solve it AND it shows in games — needs practice
                    return {
                        "pattern": pattern,
                        "label": pattern.replace("_", " ").title(),
                        "status": "needs_practice",
                        "message": f"{pattern.replace('_', ' ').title()} keeps showing up. Train it until it clicks.",
                    }
            else:
                # No puzzle data — hasn't trained this yet
                return {
                    "pattern": pattern,
                    "label": pattern.replace("_", " ").title(),
                    "status": "untrained",
                    "message": f"You keep making {pattern.replace('_', ' ')} mistakes. Start training it — puzzles from your own games are waiting.",
                }
    except Exception:
        pass
    return None


async def _get_learning_progress(db, user_id: str) -> Dict:
    """
    Get what the student has learned — openings, traps, endgames, concepts.
    Shown on home page as "Things you've learned with your coach."
    """
    try:
        from services.coach_memory import get_or_create_memory
        memory = await get_or_create_memory(db, user_id)
        learning = memory.learning

        items = []
        for opening in learning.openings_learned:
            items.append({"type": "opening", "name": opening.replace("_", " ").replace("-", " ").title(), "key": opening})
        for trap in learning.traps_learned:
            items.append({"type": "trap", "name": trap.replace("_", " ").title(), "key": trap})
        for endgame in learning.endgames_learned:
            items.append({"type": "endgame", "name": endgame.replace("_", " ").title(), "key": endgame})
        for concept in learning.concepts_mastered:
            items.append({"type": "concept", "name": concept.replace("_", " ").title(), "key": concept})

        return {
            "items": items,
            "total": len(items),
            "current_focus": learning.current_focus,
            "suggested_next": learning.suggested_next,
        }
    except Exception:
        return {"items": [], "total": 0, "current_focus": None, "suggested_next": []}


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
    
    # === CURRICULUM BRAIN: Get coach's prescription from memory ===
    coach_prescription_data = None
    try:
        from services.coach_memory import get_or_create_memory
        memory = await get_or_create_memory(db, user_id)
        current_focus = memory.learning.current_focus
        if current_focus:
            # Get the latest postgame analysis for prescription reason
            latest_analysis = await db.postgame_analyses.find_one(
                {"user_id": user_id, "coach_prescription": {"$exists": True}},
                sort=[("created_at", -1)]
            )
            prescription_reason = ""
            prescription_type = ""
            if latest_analysis:
                prescription_reason = latest_analysis.get("prescription_reason", "")
                prescription_type = latest_analysis.get("prescription_type", "")

            coach_prescription_data = {
                "focus": current_focus,
                "reason": prescription_reason,
                "type": prescription_type,
            }
    except Exception:
        pass

    # Generate active advice — use coach prescription if available
    active_advice = generate_active_advice(
        phase=development_phase["phase_key"],
        recurring_patterns=recurring_patterns,
        last_game_issues=last_game_issues[:3],
        focus_capacity=focus_capacity["level"],
        coach_prescription=coach_prescription_data,
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
    
    # Get games needing reflection (last 3 days, max 5 games)
    from reflect_service import get_games_needing_reflection
    games_needing_reflection = await get_games_needing_reflection(db, user_id, limit=5)
    
    # NEW: Get specific mistake patterns from recent games
    specific_patterns = await get_specific_mistake_patterns(db, user_id, games_needing_reflection)
    
    # NEW: Get progress trends (comparing last 5 games vs previous 5)
    progress_trend = await get_progress_trend(db, user_id)
    
    # NEW: Get last session info for continuity
    last_session_info = await get_last_session_info(db, user_id)
    
    # P1-3: Calculate win streak from recent coach sessions
    win_streak_data = await _calculate_win_streak(db, user_id)
    
    # If user has 3+ consecutive wins, suppress negative profiling
    mood_override = None
    if win_streak_data["current_streak"] >= 3:
        mood_override = {
            "type": "positive_momentum",
            "streak": win_streak_data["current_streak"],
            "message": f"You're on a {win_streak_data['current_streak']}-game win streak! Your recent form is strong.",
            "suppress_negative": True,
        }
        # Soften the development phase description
        if development_phase.get("phase_key") in ("tactical_discipline", "pattern_control"):
            development_phase["momentum_override"] = {
                "name": "Building Momentum",
                "description": f"Your {win_streak_data['current_streak']}-game win streak shows real improvement. Keep this energy going!",
                "color": "emerald",
                "icon": "trending-up",
            }
    
    return {
        "has_data": True,
        "games_analyzed": total_games,
        "development_phase": development_phase,
        "focus_capacity": focus_capacity,
        "active_advice": active_advice,
        "last_game": last_game_summary,
        "games_needing_reflection": games_needing_reflection,
        "recommended_drill": recommended_drill,
        "recurring_patterns": recurring_patterns[:3],
        "specific_patterns": specific_patterns,
        "progress_trend": progress_trend,
        "last_session": last_session_info,
        "win_streak": win_streak_data,
        "mood_override": mood_override,
        "coach_prescription": coach_prescription_data,
        "learning_progress": await _get_learning_progress(db, user_id),
        "training_recommendation": await _get_training_recommendation(db, user_id, recurring_patterns),
        "stats": {
            "blunders_per_game": round(blunders_per_game, 2),
            "mistakes_per_game": round(mistakes_per_game, 2),
            "time_trouble_rate": round(time_trouble_rate * 100, 1),
        },
    }


async def _calculate_win_streak(db, user_id: str) -> Dict:
    """
    Calculate the user's current consecutive win streak from coach sessions.

    Looks at the most recent completed sessions (up to 20) and counts
    consecutive wins from the latest game backward.
    """
    sessions = await db.coach_sessions.find(
        {
            "user_id": user_id,
            "status": {"$in": ["completed", "resigned"]},
            "result": {"$exists": True},
        },
        {"_id": 0, "result": 1, "created_at": 1},
    ).sort("created_at", -1).limit(20).to_list(20)

    current_streak = 0
    for s in sessions:
        if s.get("result") == "win":
            current_streak += 1
        else:
            break

    total_wins = sum(1 for s in sessions if s.get("result") == "win")

    return {
        "current_streak": current_streak,
        "recent_wins": total_wins,
        "recent_total": len(sessions),
    }



async def get_specific_mistake_patterns(db, user_id: str, recent_games: List[Dict]) -> Dict:
    """
    Analyze recent games to find specific tactical patterns the user is struggling with.
    
    Returns:
    - dominant_pattern: The most common mistake type (e.g., "walked into fork")
    - pattern_count: How many times it happened
    - pattern_description: Human-readable description
    """
    if not recent_games:
        return {"has_pattern": False}
    
    # Get game IDs
    game_ids = [g.get("game_id") for g in recent_games if g.get("game_id")]
    
    if not game_ids:
        return {"has_pattern": False}
    
    # Fetch analyses for these games
    pattern_counts = defaultdict(int)
    
    for game_id in game_ids:
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id, "user_id": user_id},
            {"stockfish_analysis.move_evaluations": 1, "_id": 0}
        )
        
        if not analysis:
            continue
        
        evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        
        for move in evals:
            cp_loss = move.get("cp_loss", 0)
            if cp_loss < 100:  # Only look at significant mistakes
                continue
            
            threat = move.get("threat", "")
            pv = move.get("pv_after_played", [])
            
            # Analyze the pattern
            pattern = classify_mistake_pattern(move, threat, pv)
            if pattern:
                pattern_counts[pattern] += 1
    
    if not pattern_counts:
        return {"has_pattern": False}
    
    # Find dominant pattern
    dominant_pattern, count = max(pattern_counts.items(), key=lambda x: x[1])
    
    pattern_descriptions = {
        "missed_threat": "You missed opponent's threats",
        "walked_into_fork": "You walked into forks",
        "walked_into_pin": "You walked into pins",
        "left_piece_hanging": "You left pieces undefended",
        "missed_tactic": "You missed winning tactics",
        "calculation_error": "You miscalculated sequences",
        "positional_drift": "You made small positional mistakes",
    }
    
    return {
        "has_pattern": True,
        "dominant_pattern": dominant_pattern,
        "pattern_count": count,
        "pattern_description": pattern_descriptions.get(dominant_pattern, "tactical mistakes"),
        "total_mistakes": sum(pattern_counts.values()),
        "all_patterns": dict(pattern_counts),
    }


def classify_mistake_pattern(move: Dict, threat: str, pv: List[str]) -> Optional[str]:
    """
    Classify a mistake into a specific pattern based on available data.
    """
    cp_loss = move.get("cp_loss", 0)
    
    # Check for threat-related mistakes
    if threat:
        threat_lower = threat.lower()
        if "fork" in threat_lower:
            return "walked_into_fork"
        if "pin" in threat_lower:
            return "walked_into_pin"
        if threat:  # Any other threat
            return "missed_threat"
    
    # Check PV for patterns
    if pv and len(pv) >= 2:
        # If opponent's response in PV involves captures, likely tactical
        if cp_loss > 200:
            return "missed_tactic"
        elif cp_loss > 100:
            return "calculation_error"
    
    # Significant loss without clear tactical reason = positional
    if cp_loss > 50:
        return "positional_drift"
    
    return None


async def get_progress_trend(db, user_id: str) -> Dict:
    """
    Compare recent performance vs previous period to show progress.
    
    Returns:
    - trend: "improving", "stable", "declining"
    - blunder_delta: Change in blunders per game
    - message: Human-readable progress message
    """
    # Get last 10 games
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "blunders": 1, "mistakes": 1, "accuracy": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(10).to_list(10)
    
    if len(games) < 4:
        return {"has_trend": False, "message": "Play a few more games to see your progress."}
    
    # Split into recent (first 5) and previous (next 5)
    recent = games[:5]
    previous = games[5:10] if len(games) >= 10 else games[5:]
    
    if len(previous) < 2:
        return {"has_trend": False, "message": "Keep playing to track your progress!"}
    
    recent_blunders = sum(g.get("blunders", 0) for g in recent) / len(recent)
    previous_blunders = sum(g.get("blunders", 0) for g in previous) / len(previous)
    
    recent_accuracy = [g.get("accuracy") for g in recent if g.get("accuracy")]
    previous_accuracy = [g.get("accuracy") for g in previous if g.get("accuracy")]
    
    avg_recent_acc = sum(recent_accuracy) / len(recent_accuracy) if recent_accuracy else None
    avg_previous_acc = sum(previous_accuracy) / len(previous_accuracy) if previous_accuracy else None
    
    blunder_delta = previous_blunders - recent_blunders  # Positive = improvement
    
    # Determine trend
    if blunder_delta > 0.5:
        trend = "improving"
        if blunder_delta >= 1:
            message = f"Excellent! {blunder_delta:.1f} fewer blunders per game than before."
        else:
            message = "You're blundering less. Keep it up!"
    elif blunder_delta < -0.5:
        trend = "declining"
        message = "Blunders are creeping up. Let's slow down and focus."
    else:
        trend = "stable"
        if avg_recent_acc and avg_previous_acc and avg_recent_acc > avg_previous_acc:
            message = "Consistent play, and your accuracy is improving!"
        else:
            message = "Steady progress. Stay focused on your habits."
    
    return {
        "has_trend": True,
        "trend": trend,
        "blunder_delta": round(blunder_delta, 1),
        "recent_blunders_avg": round(recent_blunders, 1),
        "previous_blunders_avg": round(previous_blunders, 1),
        "recent_accuracy_avg": round(avg_recent_acc, 1) if avg_recent_acc else None,
        "message": message,
    }


async def get_last_session_info(db, user_id: str) -> Dict:
    """
    Get info about the user's last coaching session for continuity.
    
    Returns what we worked on last time so we can follow up.
    """
    # Check for recent activity
    last_reflection = await db.reflections.find_one(
        {"user_id": user_id},
        {"_id": 0, "created_at": 1}
    )
    has_recent_reflection = last_reflection is not None
    
    # Get the most recent coach state interaction
    coach_state = await db.coach_state.find_one(
        {"user_id": user_id},
        {"_id": 0, "active_theme": 1, "games_on_theme": 1, "last_deep_session_at": 1}
    )
    
    if not coach_state:
        return {"has_session": False}
    
    games_on_theme = coach_state.get("games_on_theme", 0)
    active_theme = coach_state.get("active_theme", "")
    
    # Format theme name - add spaces before capitals
    import re
    theme_name = re.sub(r'([A-Z])', r' \1', active_theme).strip() if active_theme else "improvement"
    
    if games_on_theme == 0:
        message = f"Starting fresh with {theme_name}."
    elif games_on_theme < 3:
        message = f"We've been working on {theme_name} for {games_on_theme} game{'s' if games_on_theme != 1 else ''}."
    elif games_on_theme < 10:
        message = f"Good progress on {theme_name}! {games_on_theme} games in."
    else:
        message = f"You've been focused on {theme_name} for {games_on_theme} games. Let's see how it's paying off."
    
    return {
        "has_session": True,
        "theme": active_theme,
        "games_on_theme": games_on_theme,
        "message": message,
    }
