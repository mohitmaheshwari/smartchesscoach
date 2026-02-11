"""
Chess DNA Badge System - Player Skill Analysis

Calculates 8 skill badges based on game analysis:
1. Opening Mastery - Opening phase performance
2. Tactical Vision - Finding/missing tactics
3. Positional Sense - Piece placement, structure
4. Endgame Skills - Endgame technique
5. Defensive Resilience - Holding tough positions
6. Converting Wins - Closing out winning games
7. Focus & Discipline - Avoiding casual blunders
8. Time Management - Clock usage patterns

Each badge is rated 1-5 stars with trend tracking.
NEW: Each badge now tracks relevant moves for drill-down.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import statistics

logger = logging.getLogger(__name__)

# Badge definitions
BADGES = {
    "opening": {
        "name": "Opening Mastery",
        "icon": "🎯",
        "description": "Theory knowledge, development, avoiding early mistakes"
    },
    "tactical": {
        "name": "Tactical Vision",
        "icon": "⚔️",
        "description": "Finding tactics, spotting threats, combinations"
    },
    "positional": {
        "name": "Positional Sense",
        "icon": "🏰",
        "description": "Piece placement, pawn structure, long-term planning"
    },
    "endgame": {
        "name": "Endgame Skills",
        "icon": "👑",
        "description": "Converting advantages, technique, theoretical knowledge"
    },
    "defense": {
        "name": "Defensive Resilience",
        "icon": "🛡️",
        "description": "Holding tough positions, finding resources when worse"
    },
    "converting": {
        "name": "Converting Wins",
        "icon": "🎖️",
        "description": "Closing out games when winning, not throwing leads"
    },
    "focus": {
        "name": "Focus & Discipline",
        "icon": "🧘",
        "description": "Avoiding casual blunders, checking threats"
    },
    "time": {
        "name": "Time Management",
        "icon": "⏱️",
        "description": "Using clock wisely, not rushing or flagging"
    }
}


def calculate_badge_score(value: float, thresholds: List[float]) -> float:
    """Convert a metric value to a 1-5 star score based on thresholds."""
    if value >= thresholds[4]:
        return 5.0
    elif value >= thresholds[3]:
        return 4.0 + (value - thresholds[3]) / (thresholds[4] - thresholds[3])
    elif value >= thresholds[2]:
        return 3.0 + (value - thresholds[2]) / (thresholds[3] - thresholds[2])
    elif value >= thresholds[1]:
        return 2.0 + (value - thresholds[1]) / (thresholds[2] - thresholds[1])
    elif value >= thresholds[0]:
        return 1.0 + (value - thresholds[0]) / (thresholds[1] - thresholds[0])
    else:
        return max(0.5, value / thresholds[0])


def calculate_opening_badge(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate Opening Mastery badge.
    
    Measures:
    - Accuracy in first 10-15 moves
    - Development speed
    - Early blunders/mistakes
    - Castling timing
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    opening_accuracies = []
    early_blunders = 0
    total_games = len(analyses)
    castled_on_time = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Get accuracy for first 10 moves
        opening_moves = [m for m in move_evals if m.get("move_number", 0) <= 10]
        if opening_moves:
            good_moves = sum(1 for m in opening_moves if m.get("evaluation") in ["good", "solid", "excellent", "best"])
            opening_accuracies.append(good_moves / len(opening_moves) * 100)
        
        # Count early blunders (before move 15)
        commentary = analysis.get("commentary", [])
        for c in commentary:
            if c.get("move_number", 0) <= 15 and c.get("evaluation") == "blunder":
                early_blunders += 1
    
    # Calculate metrics
    avg_opening_accuracy = statistics.mean(opening_accuracies) if opening_accuracies else 50
    early_blunder_rate = (early_blunders / total_games) if total_games > 0 else 1
    
    # Score calculation (higher accuracy, fewer early blunders = better)
    accuracy_score = calculate_badge_score(avg_opening_accuracy, [30, 50, 65, 80, 90])
    blunder_penalty = min(early_blunder_rate * 0.5, 1.5)  # Max 1.5 star penalty
    
    final_score = max(1.0, min(5.0, accuracy_score - blunder_penalty))
    
    return {
        "score": round(final_score, 1),
        "metrics": {
            "avg_opening_accuracy": round(avg_opening_accuracy, 1),
            "early_blunders": early_blunders,
            "games_analyzed": total_games
        },
        "insight": _get_opening_insight(avg_opening_accuracy, early_blunders, total_games)
    }


def calculate_tactical_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Tactical Vision badge.
    
    Measures:
    - Tactics found vs missed
    - Complexity of tactics found
    - Threat awareness
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    tactics_found = 0
    tactics_missed = 0
    total_tactical_moments = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        for m in move_evals:
            # A tactical moment is when there's a significant eval swing possible
            eval_diff = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
            if eval_diff > 150:  # Significant tactical moment
                total_tactical_moments += 1
                if m.get("evaluation") in ["good", "excellent", "best"]:
                    tactics_found += 1
                elif m.get("evaluation") in ["blunder", "mistake"]:
                    tactics_missed += 1
    
    # Calculate tactical accuracy
    if total_tactical_moments > 0:
        tactical_accuracy = (tactics_found / total_tactical_moments) * 100
    else:
        tactical_accuracy = 50
    
    score = calculate_badge_score(tactical_accuracy, [20, 35, 50, 65, 80])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "tactics_found": tactics_found,
            "tactics_missed": tactics_missed,
            "tactical_accuracy": round(tactical_accuracy, 1)
        },
        "insight": _get_tactical_insight(tactics_found, tactics_missed, tactical_accuracy)
    }


def calculate_positional_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Positional Sense badge.
    
    Measures:
    - Middlegame accuracy
    - Piece activity
    - Pawn structure mistakes
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    middlegame_accuracies = []
    positional_mistakes = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Middlegame = moves 15-35
        mg_moves = [m for m in move_evals if 15 <= m.get("move_number", 0) <= 35]
        if mg_moves:
            good_moves = sum(1 for m in mg_moves if m.get("evaluation") in ["good", "solid", "excellent", "best"])
            middlegame_accuracies.append(good_moves / len(mg_moves) * 100)
        
        # Count positional mistakes from commentary
        for c in analysis.get("commentary", []):
            if "structure" in str(c.get("details", {})).lower() or "positional" in str(c.get("comment", "")).lower():
                if c.get("evaluation") in ["mistake", "inaccuracy"]:
                    positional_mistakes += 1
    
    avg_mg_accuracy = statistics.mean(middlegame_accuracies) if middlegame_accuracies else 50
    score = calculate_badge_score(avg_mg_accuracy, [30, 45, 60, 75, 85])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "middlegame_accuracy": round(avg_mg_accuracy, 1),
            "positional_mistakes": positional_mistakes
        },
        "insight": _get_positional_insight(avg_mg_accuracy)
    }


def calculate_endgame_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Endgame Skills badge.
    
    Measures:
    - Accuracy in endgame phase
    - Conversion rate from winning endgames
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    endgame_accuracies = []
    endgames_won = 0
    endgames_drawn_or_lost_from_winning = 0
    total_endgames = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Endgame = moves after 35 or when few pieces remain
        eg_moves = [m for m in move_evals if m.get("move_number", 0) > 35]
        if eg_moves:
            total_endgames += 1
            good_moves = sum(1 for m in eg_moves if m.get("evaluation") in ["good", "solid", "excellent", "best"])
            endgame_accuracies.append(good_moves / len(eg_moves) * 100)
            
            # Check if was winning and converted
            first_eg_eval = eg_moves[0].get("eval_before", 0) if eg_moves else 0
            game_result = analysis.get("result", "")
            user_color = analysis.get("user_color", "white")
            
            user_won = (user_color == "white" and "1-0" in game_result) or (user_color == "black" and "0-1" in game_result)
            was_winning = (user_color == "white" and first_eg_eval > 150) or (user_color == "black" and first_eg_eval < -150)
            
            if was_winning:
                if user_won:
                    endgames_won += 1
                else:
                    endgames_drawn_or_lost_from_winning += 1
    
    avg_eg_accuracy = statistics.mean(endgame_accuracies) if endgame_accuracies else 50
    conversion_rate = (endgames_won / (endgames_won + endgames_drawn_or_lost_from_winning) * 100) if (endgames_won + endgames_drawn_or_lost_from_winning) > 0 else 50
    
    combined_score = (avg_eg_accuracy * 0.6 + conversion_rate * 0.4)
    score = calculate_badge_score(combined_score, [30, 45, 60, 75, 85])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "endgame_accuracy": round(avg_eg_accuracy, 1),
            "conversion_rate": round(conversion_rate, 1),
            "endgames_analyzed": total_endgames
        },
        "insight": _get_endgame_insight(avg_eg_accuracy, conversion_rate)
    }


def calculate_defense_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Defensive Resilience badge.
    
    Measures:
    - Accuracy when position is worse
    - Games saved from losing positions
    - Finding defensive resources
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    defensive_accuracies = []
    games_saved = 0
    total_losing_positions = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        user_color = analysis.get("user_color", "white")
        
        # Find moves where player was worse
        defensive_moves = []
        for m in move_evals:
            eval_before = m.get("eval_before", 0)
            is_worse = (user_color == "white" and eval_before < -100) or (user_color == "black" and eval_before > 100)
            if is_worse:
                defensive_moves.append(m)
                total_losing_positions += 1
        
        if defensive_moves:
            good_defense = sum(1 for m in defensive_moves if m.get("evaluation") in ["good", "solid", "excellent", "best"])
            defensive_accuracies.append(good_defense / len(defensive_moves) * 100)
        
        # Check if game was saved from losing position
        game_result = analysis.get("result", "")
        was_losing = any(
            (user_color == "white" and m.get("eval_before", 0) < -200) or 
            (user_color == "black" and m.get("eval_before", 0) > 200)
            for m in move_evals
        )
        user_didnt_lose = not (
            (user_color == "white" and "0-1" in game_result) or 
            (user_color == "black" and "1-0" in game_result)
        )
        if was_losing and user_didnt_lose:
            games_saved += 1
    
    avg_def_accuracy = statistics.mean(defensive_accuracies) if defensive_accuracies else 50
    score = calculate_badge_score(avg_def_accuracy, [25, 40, 55, 70, 85])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "defensive_accuracy": round(avg_def_accuracy, 1),
            "games_saved": games_saved,
            "losing_positions_faced": total_losing_positions
        },
        "insight": _get_defense_insight(avg_def_accuracy, games_saved)
    }


def calculate_converting_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Converting Wins badge.
    
    Measures:
    - Win rate from winning positions
    - Accuracy when ahead
    - Games thrown from winning positions
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    winning_position_accuracies = []
    games_converted = 0
    games_thrown = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        user_color = analysis.get("user_color", "white")
        game_result = analysis.get("result", "")
        
        # Find moves where player was winning
        winning_moves = []
        was_significantly_winning = False
        
        for m in move_evals:
            eval_before = m.get("eval_before", 0)
            is_winning = (user_color == "white" and eval_before > 150) or (user_color == "black" and eval_before < -150)
            if is_winning:
                winning_moves.append(m)
            if (user_color == "white" and eval_before > 300) or (user_color == "black" and eval_before < -300):
                was_significantly_winning = True
        
        if winning_moves:
            good_moves = sum(1 for m in winning_moves if m.get("evaluation") in ["good", "solid", "excellent", "best"])
            winning_position_accuracies.append(good_moves / len(winning_moves) * 100)
        
        # Check conversion
        user_won = (user_color == "white" and "1-0" in game_result) or (user_color == "black" and "0-1" in game_result)
        if was_significantly_winning:
            if user_won:
                games_converted += 1
            else:
                games_thrown += 1
    
    avg_winning_accuracy = statistics.mean(winning_position_accuracies) if winning_position_accuracies else 50
    conversion_rate = (games_converted / (games_converted + games_thrown) * 100) if (games_converted + games_thrown) > 0 else 50
    
    combined = (avg_winning_accuracy * 0.5 + conversion_rate * 0.5)
    score = calculate_badge_score(combined, [30, 50, 65, 80, 90])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "accuracy_when_winning": round(avg_winning_accuracy, 1),
            "games_converted": games_converted,
            "games_thrown": games_thrown,
            "conversion_rate": round(conversion_rate, 1)
        },
        "insight": _get_converting_insight(avg_winning_accuracy, games_thrown, conversion_rate)
    }


def calculate_focus_badge(analyses: List[Dict]) -> Dict:
    """
    Calculate Focus & Discipline badge.
    
    Measures:
    - One-move blunders (simple misses)
    - Blunders below player's demonstrated level
    - Consistency across game phases
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    one_move_blunders = 0
    total_blunders = 0
    total_moves = 0
    
    # Track player's best tactical finds to establish capability
    best_tactical_complexity = 0
    simple_misses = 0  # Blunders that were obvious
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        for m in move_evals:
            total_moves += 1
            
            if m.get("evaluation") == "blunder":
                total_blunders += 1
                
                # Check if it was a simple one-move miss
                # (opponent could capture something for free)
                eval_drop = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
                if eval_drop > 200 and eval_drop < 500:  # Material loss, not complex
                    one_move_blunders += 1
                    simple_misses += 1
            
            # Track best finds
            if m.get("evaluation") in ["excellent", "best"]:
                eval_gain = abs(m.get("eval_after", 0) - m.get("eval_before", 0))
                best_tactical_complexity = max(best_tactical_complexity, eval_gain)
    
    # Calculate focus score - fewer simple blunders = better
    blunder_rate = (one_move_blunders / total_moves * 100) if total_moves > 0 else 5
    focus_score = 100 - (blunder_rate * 10)  # Penalize heavily for focus errors
    focus_score = max(0, min(100, focus_score))
    
    score = calculate_badge_score(focus_score, [40, 55, 70, 85, 95])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "one_move_blunders": one_move_blunders,
            "total_blunders": total_blunders,
            "blunder_rate_pct": round(blunder_rate, 2),
            "total_moves": total_moves
        },
        "insight": _get_focus_insight(one_move_blunders, total_blunders, best_tactical_complexity)
    }


def calculate_time_badge(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate Time Management badge.
    
    Measures:
    - Average move time
    - Time trouble frequency
    - Fast moves before blunders
    """
    if not analyses:
        return {"score": 2.5, "metrics": {}, "insight": "Not enough games analyzed"}
    
    # For now, estimate based on game time controls and blunder timing
    # In future, can parse actual clock times from PGN if available
    
    time_trouble_games = 0
    fast_blunders = 0  # Blunders that happened quickly
    total_games = len(analyses)
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Check for late-game blunders (likely time trouble)
        late_blunders = sum(1 for m in move_evals 
                          if m.get("move_number", 0) > 35 and m.get("evaluation") == "blunder")
        if late_blunders >= 2:
            time_trouble_games += 1
    
    time_trouble_rate = (time_trouble_games / total_games * 100) if total_games > 0 else 30
    time_score = 100 - time_trouble_rate
    
    score = calculate_badge_score(time_score, [40, 55, 70, 85, 95])
    
    return {
        "score": round(score, 1),
        "metrics": {
            "time_trouble_games": time_trouble_games,
            "time_trouble_rate": round(time_trouble_rate, 1)
        },
        "insight": _get_time_insight(time_trouble_rate)
    }


# Insight generators
def _get_opening_insight(accuracy: float, blunders: int, games: int) -> str:
    if accuracy >= 80 and blunders == 0:
        return "Excellent opening preparation! You're starting games well."
    elif blunders > games * 0.3:
        return "Too many early blunders. Slow down in the opening, check for threats."
    elif accuracy < 50:
        return "Opening accuracy needs work. Focus on basic development principles."
    else:
        return "Solid openings. Room to improve with specific repertoire study."


def _get_tactical_insight(found: int, missed: int, accuracy: float) -> str:
    if accuracy >= 70:
        return "Strong tactical vision! You're finding the key moments."
    elif missed > found:
        return "Missing more tactics than you find. Practice daily puzzles."
    else:
        return "Decent tactical awareness. Keep solving puzzles to improve pattern recognition."


def _get_positional_insight(accuracy: float) -> str:
    if accuracy >= 75:
        return "Good positional understanding. Your piece placement is strong."
    elif accuracy < 50:
        return "Positional play needs work. Focus on piece activity and pawn structure."
    else:
        return "Average positional sense. Study master games for better intuition."


def _get_endgame_insight(accuracy: float, conversion: float) -> str:
    if conversion >= 80:
        return "Excellent at converting endgames! You close out games well."
    elif conversion < 50:
        return "Throwing too many endgames. Study basic endgame technique."
    else:
        return "Decent endgame skills. Practice common endgame patterns."


def _get_defense_insight(accuracy: float, saved: int) -> str:
    if saved > 0 and accuracy >= 60:
        return f"Resilient defender! You've saved {saved} games from losing positions."
    elif accuracy < 40:
        return "Defense collapses under pressure. Practice defensive techniques."
    else:
        return "Average defensive skills. Stay calm when position gets tough."


def _get_converting_insight(accuracy: float, thrown: int, rate: float) -> str:
    if thrown > 0:
        return f"You've thrown {thrown} winning games. When ahead, slow down and check for threats."
    elif rate >= 85:
        return "Excellent at converting wins! You close out games professionally."
    else:
        return "Work on technique when winning. Don't relax too early."


def _get_focus_insight(one_move: int, total: int, best: float) -> str:
    if one_move > 0 and best > 300:
        return "You find complex tactics but miss simple threats. It's not skill, it's focus. Check every move."
    elif one_move == 0:
        return "Great focus! You're avoiding casual mistakes."
    else:
        return f"{one_move} simple blunders. Before each move, ask: 'Is my piece safe?'"


def _get_time_insight(trouble_rate: float) -> str:
    if trouble_rate < 15:
        return "Good time management. You pace yourself well."
    elif trouble_rate > 40:
        return "Too often in time trouble. Use your time more evenly throughout the game."
    else:
        return "Occasional time issues. Try to maintain a steady pace."


async def calculate_all_badges(db, user_id: str) -> Dict:
    """
    Calculate all 8 badges for a user.
    
    Returns:
        Dict with badge scores, metrics, and insights
    """
    # Fetch user's analyses and games
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(30).to_list(30)  # Last 30 games
    
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("imported_at", -1).limit(30).to_list(30)
    
    if not analyses:
        return {
            "badges": {},
            "overall_score": 0,
            "message": "No analyzed games yet. Import and analyze games to see your Chess DNA.",
            "games_analyzed": 0
        }
    
    # Calculate each badge
    badges = {
        "opening": calculate_opening_badge(analyses, games),
        "tactical": calculate_tactical_badge(analyses),
        "positional": calculate_positional_badge(analyses),
        "endgame": calculate_endgame_badge(analyses),
        "defense": calculate_defense_badge(analyses),
        "converting": calculate_converting_badge(analyses),
        "focus": calculate_focus_badge(analyses),
        "time": calculate_time_badge(analyses, games)
    }
    
    # Add metadata to each badge
    for key, badge in badges.items():
        badge["key"] = key
        badge["name"] = BADGES[key]["name"]
        badge["icon"] = BADGES[key]["icon"]
        badge["description"] = BADGES[key]["description"]
    
    # Calculate overall score
    overall = statistics.mean([b["score"] for b in badges.values()])
    
    # Find strengths and weaknesses
    sorted_badges = sorted(badges.items(), key=lambda x: x[1]["score"], reverse=True)
    strengths = [b[0] for b in sorted_badges[:2]]
    weaknesses = [b[0] for b in sorted_badges[-2:]]
    
    return {
        "badges": badges,
        "overall_score": round(overall, 1),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "games_analyzed": len(analyses),
        "calculated_at": datetime.now(timezone.utc).isoformat()
    }


async def get_badge_history(db, user_id: str) -> List[Dict]:
    """Get historical badge scores for trend analysis."""
    history = await db.badge_history.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("calculated_at", -1).limit(10).to_list(10)
    
    return history


async def save_badge_snapshot(db, user_id: str, badges: Dict):
    """Save current badge scores for historical tracking."""
    snapshot = {
        "user_id": user_id,
        "badges": {k: v["score"] for k, v in badges.get("badges", {}).items()},
        "overall_score": badges.get("overall_score", 0),
        "calculated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.badge_history.insert_one(snapshot)


def calculate_badge_trends(current: Dict, history: List[Dict]) -> Dict:
    """Calculate trends for each badge based on history."""
    if not history or len(history) < 2:
        return {k: "stable" for k in BADGES.keys()}
    
    trends = {}
    oldest = history[-1].get("badges", {})
    current_badges = current.get("badges", {})
    
    for key in BADGES.keys():
        current_score = current_badges.get(key, {}).get("score", 2.5)
        old_score = oldest.get(key, 2.5)
        diff = current_score - old_score
        
        if diff > 0.3:
            trends[key] = "improving"
        elif diff < -0.3:
            trends[key] = "declining"
        else:
            trends[key] = "stable"
    
    return trends



# ============================================================================
# BADGE DRILL-DOWN: Get relevant games/moves for each badge
# ============================================================================

async def get_badge_details(db, user_id: str, badge_key: str, user_rating: int = 1200) -> Dict:
    """
    Get detailed breakdown for a specific badge.
    
    Returns:
    - Badge score and insight
    - Last 5 relevant games
    - Specific moves that affected this badge (with FEN for board display)
    - Badge-specific commentary (adjusted for user's rating level)
    
    Rating levels:
    - Below 1000: Very basic explanations
    - 1000-1400: Beginner-friendly patterns
    - 1400-1800: Intermediate concepts
    - 1800+: Advanced ideas
    """
    if badge_key not in BADGES:
        return {"error": f"Unknown badge: {badge_key}"}
    
    # Fetch user's analyses with full move data
    analyses = await db.game_analyses.find(
        {
            "user_id": user_id,
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    # Get corresponding game data for PGN and opponent info
    game_ids = [a.get("game_id") for a in analyses]
    games = await db.games.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "pgn": 1, "opponent_name": 1, "user_color": 1, "result": 1, "played_at": 1}
    ).to_list(len(game_ids))
    
    games_map = {g["game_id"]: g for g in games}
    
    # Get relevant moves based on badge type
    badge_func = BADGE_DETAIL_FUNCTIONS.get(badge_key)
    if not badge_func:
        return {"error": "Badge detail function not implemented"}
    
    # Pass user_rating to badge function for rating-appropriate filtering and explanations
    result = badge_func(analyses, games_map, user_rating)
    
    # Add badge metadata
    result["badge_key"] = badge_key
    result["badge_name"] = BADGES[badge_key]["name"]
    result["badge_icon"] = BADGES[badge_key]["icon"]
    result["badge_description"] = BADGES[badge_key]["description"]
    result["user_rating"] = user_rating
    
    return result


def _get_opening_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Opening Mastery badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Get moves in opening phase (first 10 moves)
        opening_moves = [m for m in move_evals if m.get("move_number", 0) <= 10]
        
        game_opening_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": game.get("result", ""),
            "user_color": game.get("user_color", "white"),
            "played_at": game.get("played_at"),
            "moves": []
        }
        
        for m in opening_moves:
            evaluation = m.get("evaluation", "")
            
            # Track mistakes/blunders in opening
            if evaluation in ["blunder", "mistake", "inaccuracy"]:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": m.get("best_move"),
                    "evaluation": evaluation,
                    "cp_loss": m.get("cp_loss", 0),
                    "type": "mistake",
                    "pv_after_best": m.get("pv_after_best", []),
                    "threat": m.get("threat"),
                    "explanation": _generate_opening_explanation(m, evaluation)
                }
                game_opening_data["moves"].append(move_data)
                relevant_moves.append({**move_data, "game_id": game_id})
            
            # Track excellent opening moves
            elif evaluation in ["best", "excellent"]:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": m.get("best_move"),
                    "evaluation": evaluation,
                    "cp_loss": m.get("cp_loss", 0),
                    "type": "good",
                    "pv_after_best": m.get("pv_after_best", []),
                    "explanation": "Good opening move - solid development following classical principles"
                }
                # Only add to moves if it's notable
                if m.get("move_number", 0) <= 5:  # First 5 moves are always relevant
                    game_opening_data["moves"].append(move_data)
        
        # Only include games with notable moves
        if game_opening_data["moves"]:
            relevant_games.append(game_opening_data)
    
    # Sort by relevance (games with more mistakes first)
    relevant_games.sort(key=lambda x: sum(1 for m in x["moves"] if m["type"] == "mistake"), reverse=True)
    
    # Calculate badge-specific summary
    total_mistakes = len([m for m in relevant_moves if m["type"] == "mistake"])
    
    return {
        "score": _calculate_opening_score_simple(analyses),
        "relevant_games": relevant_games[:5],  # Last 5 relevant games
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "opening_mistakes": total_mistakes,
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("opening", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("opening", total_mistakes, len(analyses))
    }


def _get_tactical_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Tactical Vision badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        game_tactical_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": game.get("result", ""),
            "user_color": game.get("user_color", "white"),
            "played_at": game.get("played_at"),
            "moves": []
        }
        
        for m in move_evals:
            eval_diff = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
            evaluation = m.get("evaluation", "")
            
            # Tactical moment: significant eval swing (>150 cp)
            if eval_diff > 150:
                is_missed = evaluation in ["blunder", "mistake"]
                is_found = evaluation in ["best", "excellent"]
                
                if is_missed or is_found:
                    move_data = {
                        "move_number": m.get("move_number"),
                        "move_played": m.get("move"),
                        "fen": m.get("fen_before", ""),
                        "best_move": m.get("best_move"),
                        "evaluation": evaluation,
                        "cp_loss": m.get("cp_loss", 0),
                        "eval_swing": eval_diff,
                        "type": "missed" if is_missed else "found",
                        "threat": m.get("threat"),
                        "pv_after_best": m.get("pv_after_best", []),
                        "explanation": _generate_tactical_explanation(m, is_missed, eval_diff)
                    }
                    game_tactical_data["moves"].append(move_data)
                    relevant_moves.append({**move_data, "game_id": game_id})
        
        if game_tactical_data["moves"]:
            relevant_games.append(game_tactical_data)
    
    # Sort by relevance (games with missed tactics first, then by eval swing)
    relevant_games.sort(key=lambda x: (
        -sum(1 for m in x["moves"] if m["type"] == "missed"),
        -max((m.get("eval_swing", 0) for m in x["moves"]), default=0)
    ))
    
    tactics_found = len([m for m in relevant_moves if m["type"] == "found"])
    tactics_missed = len([m for m in relevant_moves if m["type"] == "missed"])
    
    return {
        "score": _calculate_tactical_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "tactics_found": tactics_found,
            "tactics_missed": tactics_missed,
            "accuracy": round(tactics_found / (tactics_found + tactics_missed) * 100, 1) if (tactics_found + tactics_missed) > 0 else 0
        },
        "insight": _generate_badge_insight("tactical", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("tactical", tactics_missed, len(analyses), tactics_found)
    }


def _get_positional_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Positional Sense badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        game_pos_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": game.get("result", ""),
            "user_color": game.get("user_color", "white"),
            "played_at": game.get("played_at"),
            "moves": []
        }
        
        # Middlegame = moves 15-35
        mg_moves = [m for m in move_evals if 15 <= m.get("move_number", 0) <= 35]
        
        for m in mg_moves:
            evaluation = m.get("evaluation", "")
            cp_loss = m.get("cp_loss", 0)
            
            # Track positional errors (moderate cp loss, not tactical blunders)
            if evaluation in ["mistake", "inaccuracy"] and 50 <= cp_loss <= 200:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": m.get("best_move"),
                    "evaluation": evaluation,
                    "cp_loss": cp_loss,
                    "type": "positional_error",
                    "explanation": _generate_positional_explanation(m, cp_loss)
                }
                game_pos_data["moves"].append(move_data)
                relevant_moves.append({**move_data, "game_id": game_id})
            
            # Track excellent positional play
            elif evaluation in ["best", "excellent"] and cp_loss <= 10:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "evaluation": evaluation,
                    "type": "good_positional",
                    "explanation": "Strong positional decision"
                }
                game_pos_data["moves"].append(move_data)
        
        if game_pos_data["moves"]:
            relevant_games.append(game_pos_data)
    
    relevant_games.sort(key=lambda x: sum(1 for m in x["moves"] if m["type"] == "positional_error"), reverse=True)
    
    errors = len([m for m in relevant_moves if m["type"] == "positional_error"])
    
    return {
        "score": _calculate_positional_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "positional_errors": errors,
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("positional", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("positional", errors, len(analyses))
    }


def _get_endgame_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Endgame Skills badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        result = game.get("result", "")
        
        game_eg_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": result,
            "user_color": user_color,
            "played_at": game.get("played_at"),
            "moves": []
        }
        
        # Endgame = moves after 35
        eg_moves = [m for m in move_evals if m.get("move_number", 0) > 35]
        
        if not eg_moves:
            continue
        
        # Check if was winning at start of endgame
        first_eg_eval = eg_moves[0].get("eval_before", 0) if eg_moves else 0
        was_winning = (user_color == "white" and first_eg_eval > 150) or (user_color == "black" and first_eg_eval < -150)
        user_won = (user_color == "white" and "1-0" in result) or (user_color == "black" and "0-1" in result)
        
        for m in eg_moves:
            evaluation = m.get("evaluation", "")
            cp_loss = m.get("cp_loss", 0)
            
            if evaluation in ["blunder", "mistake"]:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": m.get("best_move"),
                    "evaluation": evaluation,
                    "cp_loss": cp_loss,
                    "type": "endgame_error",
                    "was_winning": was_winning,
                    "explanation": _generate_endgame_explanation(m, was_winning, user_won)
                }
                game_eg_data["moves"].append(move_data)
                relevant_moves.append({**move_data, "game_id": game_id})
        
        game_eg_data["was_winning"] = was_winning
        game_eg_data["converted"] = was_winning and user_won
        
        if game_eg_data["moves"] or (was_winning and not user_won):
            relevant_games.append(game_eg_data)
    
    # Sort by thrown endgames first
    relevant_games.sort(key=lambda x: (not x.get("converted", True), len(x["moves"])), reverse=True)
    
    errors = len([m for m in relevant_moves])
    thrown_games = len([g for g in relevant_games if g.get("was_winning") and not g.get("converted")])
    
    return {
        "score": _calculate_endgame_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "endgame_errors": errors,
            "thrown_endgames": thrown_games,
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("endgame", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("endgame", errors, len(analyses), thrown=thrown_games)
    }


def _get_defense_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Defensive Resilience badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        result = game.get("result", "")
        
        game_def_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": result,
            "user_color": user_color,
            "played_at": game.get("played_at"),
            "moves": [],
            "was_losing": False,
            "saved_game": False
        }
        
        for m in move_evals:
            eval_before = m.get("eval_before", 0)
            evaluation = m.get("evaluation", "")
            
            # When player was worse (losing position)
            is_worse = (user_color == "white" and eval_before < -100) or (user_color == "black" and eval_before > 100)
            
            if is_worse:
                game_def_data["was_losing"] = True
                
                if evaluation in ["blunder", "mistake"]:
                    move_data = {
                        "move_number": m.get("move_number"),
                        "move_played": m.get("move"),
                        "fen": m.get("fen_before", ""),
                        "best_move": m.get("best_move"),
                        "evaluation": evaluation,
                        "cp_loss": m.get("cp_loss", 0),
                        "type": "defensive_collapse",
                        "explanation": "Made it worse when already in trouble"
                    }
                    game_def_data["moves"].append(move_data)
                    relevant_moves.append({**move_data, "game_id": game_id})
                
                elif evaluation in ["best", "excellent"]:
                    move_data = {
                        "move_number": m.get("move_number"),
                        "move_played": m.get("move"),
                        "fen": m.get("fen_before", ""),
                        "evaluation": evaluation,
                        "type": "good_defense",
                        "explanation": "Strong defensive resource found"
                    }
                    game_def_data["moves"].append(move_data)
        
        # Check if saved the game
        was_significantly_losing = any(
            (user_color == "white" and m.get("eval_before", 0) < -200) or 
            (user_color == "black" and m.get("eval_before", 0) > 200)
            for m in move_evals
        )
        user_didnt_lose = not (
            (user_color == "white" and "0-1" in result) or 
            (user_color == "black" and "1-0" in result)
        )
        game_def_data["saved_game"] = was_significantly_losing and user_didnt_lose
        
        if game_def_data["moves"] or game_def_data["was_losing"]:
            relevant_games.append(game_def_data)
    
    relevant_games.sort(key=lambda x: (-int(x.get("saved_game", False)), -len(x["moves"])))
    
    collapses = len([m for m in relevant_moves if m["type"] == "defensive_collapse"])
    saved = len([g for g in relevant_games if g.get("saved_game")])
    
    return {
        "score": _calculate_defense_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "defensive_collapses": collapses,
            "games_saved": saved,
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("defense", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("defense", collapses, len(analyses), saved=saved)
    }


def _get_converting_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Converting Wins badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        user_color = game.get("user_color", "white")
        result = game.get("result", "")
        
        game_conv_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": result,
            "user_color": user_color,
            "played_at": game.get("played_at"),
            "moves": [],
            "was_winning": False,
            "converted": False
        }
        
        user_won = (user_color == "white" and "1-0" in result) or (user_color == "black" and "0-1" in result)
        
        for m in move_evals:
            eval_before = m.get("eval_before", 0)
            evaluation = m.get("evaluation", "")
            
            # When player was winning
            is_winning = (user_color == "white" and eval_before > 150) or (user_color == "black" and eval_before < -150)
            
            if is_winning:
                game_conv_data["was_winning"] = True
                
                if evaluation in ["blunder", "mistake"]:
                    best = m.get("best_move", "")
                    pv = m.get("pv_after_best", [])
                    pv_str = f" The winning continuation was: {' → '.join(pv[:3])}" if pv else ""
                    move_data = {
                        "move_number": m.get("move_number"),
                        "move_played": m.get("move"),
                        "fen": m.get("fen_before", ""),
                        "best_move": best,
                        "evaluation": evaluation,
                        "cp_loss": m.get("cp_loss", 0),
                        "type": "threw_advantage",
                        "pv_after_best": pv,
                        "threat": m.get("threat"),
                        "explanation": f"You were winning but gave away your advantage! {best} would have kept the pressure.{pv_str} When ahead, slow down and look for simple, safe moves."
                    }
                    game_conv_data["moves"].append(move_data)
                    relevant_moves.append({**move_data, "game_id": game_id})
        
        game_conv_data["converted"] = game_conv_data["was_winning"] and user_won
        
        if game_conv_data["was_winning"]:
            relevant_games.append(game_conv_data)
    
    # Sort by thrown games first
    relevant_games.sort(key=lambda x: (not x.get("converted", True), len(x["moves"])), reverse=True)
    
    threw = len([m for m in relevant_moves])
    thrown_games = len([g for g in relevant_games if g.get("was_winning") and not g.get("converted")])
    converted = len([g for g in relevant_games if g.get("converted")])
    
    return {
        "score": _calculate_converting_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "advantages_thrown": threw,
            "games_thrown": thrown_games,
            "games_converted": converted
        },
        "insight": _generate_badge_insight("converting", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("converting", threw, len(analyses), thrown=thrown_games)
    }


def _get_focus_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Focus & Discipline badge."""
    relevant_moves = []
    relevant_games = []
    
    best_tactical_complexity = 0
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        game_focus_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": game.get("result", ""),
            "user_color": game.get("user_color", "white"),
            "played_at": game.get("played_at"),
            "moves": []
        }
        
        for m in move_evals:
            evaluation = m.get("evaluation", "")
            eval_drop = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
            
            # Track best finds for capability detection
            if evaluation in ["excellent", "best"]:
                eval_gain = abs(m.get("eval_after", 0) - m.get("eval_before", 0))
                best_tactical_complexity = max(best_tactical_complexity, eval_gain)
            
            # One-move blunders (simple misses, not complex tactics)
            if evaluation == "blunder" and 200 < eval_drop < 500:
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": m.get("best_move"),
                    "evaluation": evaluation,
                    "cp_loss": m.get("cp_loss", 0),
                    "eval_drop": eval_drop,
                    "type": "focus_error",
                    "threat": m.get("threat"),
                    "pv_after_best": m.get("pv_after_best", []),
                    "explanation": _generate_focus_explanation(m, eval_drop)
                }
                game_focus_data["moves"].append(move_data)
                relevant_moves.append({**move_data, "game_id": game_id})
        
        if game_focus_data["moves"]:
            relevant_games.append(game_focus_data)
    
    relevant_games.sort(key=lambda x: len(x["moves"]), reverse=True)
    
    simple_blunders = len(relevant_moves)
    has_capability = best_tactical_complexity > 300
    
    return {
        "score": _calculate_focus_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "simple_blunders": simple_blunders,
            "has_capability": has_capability,
            "best_tactical_find": best_tactical_complexity,
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("focus", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("focus", simple_blunders, len(analyses), has_capability=has_capability)
    }


def _get_time_badge_details(analyses: List[Dict], games_map: Dict) -> Dict:
    """Get detailed data for Time Management badge."""
    relevant_moves = []
    relevant_games = []
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = games_map.get(game_id, {})
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        game_time_data = {
            "game_id": game_id,
            "opponent": game.get("opponent_name", "Unknown"),
            "result": game.get("result", ""),
            "user_color": game.get("user_color", "white"),
            "played_at": game.get("played_at"),
            "moves": [],
            "time_trouble": False
        }
        
        # Check for late-game blunders (likely time trouble)
        late_blunders = [m for m in move_evals 
                       if m.get("move_number", 0) > 35 and m.get("evaluation") == "blunder"]
        
        if len(late_blunders) >= 2:
            game_time_data["time_trouble"] = True
            
            for m in late_blunders:
                best = m.get("best_move", "")
                pv = m.get("pv_after_best", [])
                pv_str = f" The correct move was {best}." if best else ""
                move_data = {
                    "move_number": m.get("move_number"),
                    "move_played": m.get("move"),
                    "fen": m.get("fen_before", ""),
                    "best_move": best,
                    "evaluation": "blunder",
                    "cp_loss": m.get("cp_loss", 0),
                    "type": "time_trouble_blunder",
                    "pv_after_best": pv,
                    "threat": m.get("threat"),
                    "explanation": f"Late-game blunder, likely due to time pressure.{pv_str} When low on time, play simple and safe moves. Don't complicate!"
                }
                game_time_data["moves"].append(move_data)
                relevant_moves.append({**move_data, "game_id": game_id})
        
        if game_time_data["moves"] or game_time_data["time_trouble"]:
            relevant_games.append(game_time_data)
    
    relevant_games.sort(key=lambda x: len(x["moves"]), reverse=True)
    
    time_trouble_games = len([g for g in relevant_games if g.get("time_trouble")])
    
    return {
        "score": _calculate_time_score_simple(analyses),
        "relevant_games": relevant_games[:5],
        "total_relevant_moves": len(relevant_moves),
        "summary": {
            "time_trouble_games": time_trouble_games,
            "late_blunders": len(relevant_moves),
            "games_analyzed": len(analyses)
        },
        "insight": _generate_badge_insight("time", relevant_moves, len(analyses)),
        "why_this_score": _generate_why_score("time", time_trouble_games, len(analyses))
    }


# ============================================================================
# Helper functions for explanations
# ============================================================================

def _generate_opening_explanation(move: Dict, evaluation: str) -> str:
    cp_loss = move.get("cp_loss", 0)
    best = move.get("best_move", "")
    pv = move.get("pv_after_best", [])
    
    if evaluation == "blunder":
        pv_str = f" After {best}, the game would continue: {' '.join(pv[:3])}" if pv else ""
        return f"Early blunder that damaged your position significantly! The correct move was {best}.{pv_str} This gave your opponent an early advantage that's hard to recover from."
    elif evaluation == "mistake":
        return f"This move disrupted your development. {best} was stronger because it keeps your pieces coordinated and maintains pressure. Opening mistakes often lead to passive positions later."
    else:
        return f"Small inaccuracy. {best} was slightly more precise. In the opening, small advantages accumulate."


def _generate_tactical_explanation(move: Dict, is_missed: bool, eval_swing: int) -> str:
    best = move.get("best_move", "")
    threat = move.get("threat", "")
    pv = move.get("pv_after_best", [])
    
    if is_missed:
        if eval_swing > 300:
            pv_str = f" The winning sequence was: {' → '.join(pv[:4])}" if pv else ""
            threat_str = f" Your opponent's threat was {threat}, but you could have struck first." if threat else ""
            return f"You missed a winning combination! {best} was the key move that would have won material or created a decisive attack.{pv_str}{threat_str}"
        else:
            return f"Tactical opportunity missed. {best} gave you a clear advantage. Look for checks, captures, and threats in these positions."
    else:
        pv_str = f" Nice continuation: {' → '.join(pv[:3])}" if pv else ""
        return f"Excellent tactical vision! You found {best}, a strong move that created real problems for your opponent.{pv_str}"


def _generate_positional_explanation(move: Dict, cp_loss: int) -> str:
    best = move.get("best_move", "")
    pv = move.get("pv_after_best", [])
    
    pv_str = f" The idea was: {' '.join(pv[:3])}" if pv else ""
    
    if cp_loss > 100:
        return f"This move gave away your positional advantage. {best} was stronger because it maintained piece activity and controlled key squares.{pv_str} Remember: active pieces are worth more than material sometimes."
    else:
        return f"Small positional slip. {best} was more accurate, keeping your pieces on optimal squares.{pv_str}"


def _generate_endgame_explanation(move: Dict, was_winning: bool, won: bool) -> str:
    best = move.get("best_move", "")
    pv = move.get("pv_after_best", [])
    
    pv_str = f" The winning technique: {' → '.join(pv[:4])}" if pv else ""
    
    if was_winning and not won:
        return f"This endgame error cost you the game! You were winning, but {best} was needed to convert.{pv_str} In endgames, precision is everything."
    elif was_winning:
        return f"Imprecise but you still won. However, {best} was the clean technique.{pv_str} Study this pattern to convert faster next time."
    else:
        return f"Endgame mistake under pressure. {best} was the best defense.{pv_str}"


def _generate_focus_explanation(move: Dict, eval_drop: int) -> str:
    best = move.get("best_move", "")
    threat = move.get("threat", "")
    pv = move.get("pv_after_best", [])
    
    if threat:
        return f"You missed a simple threat! Your opponent was threatening {threat}. The move {best} was necessary to defend. Before every move, ask: 'What is my opponent trying to do?'"
    else:
        pv_str = f" {best} leads to: {' '.join(pv[:2])}" if pv else ""
        return f"This was a focus error, not a skill problem. {best} was clearly better.{pv_str} You know this pattern - you just missed it in the moment. Take 5 seconds before each move."


def _generate_badge_insight(badge_key: str, moves: List[Dict], games_count: int) -> str:
    """Generate badge-specific insight based on moves data."""
    move_count = len(moves)
    
    insights = {
        "opening": f"In {games_count} games, you had {move_count} opening mistakes. {'Focus on basic development.' if move_count > games_count else 'Good opening preparation!'}",
        "tactical": f"{'Strong tactical vision!' if move_count < games_count / 2 else 'Practice tactics daily to spot more combinations.'}",
        "positional": f"Your middlegame has {move_count} positional errors. {'Solid play!' if move_count < games_count else 'Work on piece activity.'}",
        "endgame": f"{'Reliable endgame technique.' if move_count < games_count / 2 else 'Endgame practice needed - too many errors in winning positions.'}",
        "defense": f"{'Resilient defender!' if move_count < games_count / 2 else 'Defense collapses under pressure. Stay calm when worse.'}",
        "converting": f"{'You close out games well!' if move_count < games_count / 3 else 'Too many thrown advantages. Slow down when winning.'}",
        "focus": f"{'Great focus!' if move_count < games_count / 3 else 'Simple blunders are costing you. Check every move.'}",
        "time": f"{'Good clock management.' if move_count < games_count / 3 else 'Time trouble is hurting you. Pace yourself better.'}"
    }
    
    return insights.get(badge_key, "Keep analyzing more games for better insights.")


def _generate_why_score(badge_key: str, errors: int, games: int, found: int = 0, thrown: int = 0, saved: int = 0, has_capability: bool = False) -> str:
    """Generate explanation for why the badge has this score."""
    
    if badge_key == "opening":
        rate = errors / games if games > 0 else 0
        if rate < 0.2:
            return "Your score is high because you rarely make early mistakes."
        elif rate < 0.5:
            return f"Score reflects {errors} opening errors in {games} games. Room for improvement."
        else:
            return f"Low score due to {errors} opening mistakes. Early blunders are hurting your games."
    
    elif badge_key == "tactical":
        if found > errors:
            return f"You found {found} tactics and missed {errors}. Good tactical awareness."
        else:
            return f"You missed {errors} tactics vs {found} found. Puzzle practice will help."
    
    elif badge_key == "focus":
        if has_capability and errors > 0:
            return f"You can find complex tactics but missed {errors} simple moves. It's not skill - it's focus."
        elif errors == 0:
            return "Excellent focus! No simple blunders detected."
        else:
            return f"{errors} simple blunders. Check every move before playing."
    
    elif badge_key == "converting":
        if thrown > 0:
            return f"You threw {thrown} winning games. When ahead, slow down."
        return "You convert advantages well."
    
    elif badge_key == "defense":
        if saved > 0:
            return f"You saved {saved} games from losing positions. Resilient!"
        elif errors > 0:
            return f"Defense collapsed {errors} times when in trouble."
        return "Average defensive skills."
    
    elif badge_key == "endgame":
        if thrown > 0:
            return f"Threw {thrown} winning endgames. Study basic technique."
        return f"{errors} endgame errors. {'Solid technique.' if errors < games / 3 else 'Needs work.'}"
    
    elif badge_key == "time":
        if errors > games / 3:
            return f"Time trouble in {errors} games. Distribute your time better."
        return "Good time management."
    
    else:
        return f"{errors} issues found in {games} games."


# Simple score calculators (for badge details)
def _calculate_opening_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    errors = 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        for m in sf.get("move_evaluations", []):
            if m.get("move_number", 0) <= 10 and m.get("evaluation") in ["blunder", "mistake"]:
                errors += 1
    rate = errors / len(analyses) if analyses else 1
    return max(1.0, min(5.0, 5.0 - rate * 1.5))


def _calculate_tactical_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    found, missed = 0, 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        for m in sf.get("move_evaluations", []):
            swing = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
            if swing > 150:
                if m.get("evaluation") in ["best", "excellent"]:
                    found += 1
                elif m.get("evaluation") in ["blunder", "mistake"]:
                    missed += 1
    if found + missed == 0:
        return 2.5
    accuracy = found / (found + missed) * 100
    return max(1.0, min(5.0, accuracy / 20))


def _calculate_positional_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    errors = 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        for m in sf.get("move_evaluations", []):
            if 15 <= m.get("move_number", 0) <= 35:
                if m.get("evaluation") in ["mistake", "inaccuracy"]:
                    errors += 1
    rate = errors / len(analyses) if analyses else 1
    return max(1.0, min(5.0, 5.0 - rate * 0.3))


def _calculate_endgame_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    errors = 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        for m in sf.get("move_evaluations", []):
            if m.get("move_number", 0) > 35 and m.get("evaluation") in ["blunder", "mistake"]:
                errors += 1
    rate = errors / len(analyses) if analyses else 1
    return max(1.0, min(5.0, 4.5 - rate * 0.5))


def _calculate_defense_score_simple(analyses: List[Dict]) -> float:
    return 3.0  # Simplified


def _calculate_converting_score_simple(analyses: List[Dict]) -> float:
    return 3.0  # Simplified


def _calculate_focus_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    blunders = 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        for m in sf.get("move_evaluations", []):
            if m.get("evaluation") == "blunder":
                swing = abs(m.get("eval_before", 0) - m.get("eval_after", 0))
                if 200 < swing < 500:
                    blunders += 1
    rate = blunders / len(analyses) if analyses else 1
    return max(1.0, min(5.0, 5.0 - rate * 1.0))


def _calculate_time_score_simple(analyses: List[Dict]) -> float:
    if not analyses:
        return 2.5
    trouble_games = 0
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        late_blunders = sum(1 for m in sf.get("move_evaluations", [])
                          if m.get("move_number", 0) > 35 and m.get("evaluation") == "blunder")
        if late_blunders >= 2:
            trouble_games += 1
    rate = trouble_games / len(analyses) * 100 if analyses else 30
    return max(1.0, min(5.0, 5.0 - rate / 20))


# Map badge keys to detail functions
BADGE_DETAIL_FUNCTIONS = {
    "opening": _get_opening_badge_details,
    "tactical": _get_tactical_badge_details,
    "positional": _get_positional_badge_details,
    "endgame": _get_endgame_badge_details,
    "defense": _get_defense_badge_details,
    "converting": _get_converting_badge_details,
    "focus": _get_focus_badge_details,
    "time": _get_time_badge_details
}
