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
        return f"You find complex tactics but miss simple threats. It's not skill, it's focus. Check every move."
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
