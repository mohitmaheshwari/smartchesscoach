"""
Skill Calibration Service

Calculates assessed skill rating from game history.
NOT a rating engine - just calibration for puzzle difficulty and expectations.

Algorithm:
1. Median opponent rating (reduces outliers)
2. Clamped performance formula
3. Time control weighting (rapid > blitz > bullet)
4. Recency weighting (recent games count more)
5. Cross-platform weighted mean
"""

import math
from typing import List, Dict, Optional, Tuple
from statistics import median


# Time control weights
TIME_CONTROL_WEIGHTS = {
    "rapid": 1.0,
    "classical": 1.0,
    "blitz": 0.7,
    "bullet": 0.4
}

# Default weight for unknown time controls
DEFAULT_TC_WEIGHT = 0.5


def classify_time_control(time_control: str) -> str:
    """Classify time control string into category."""
    if not time_control:
        return "blitz"  # Default assumption
    
    tc = time_control.lower()
    
    # Chess.com format: "600" (seconds) or "600+5"
    # Lichess format: "rapid", "blitz", "bullet", "classical"
    
    if tc in TIME_CONTROL_WEIGHTS:
        return tc
    
    # Parse numeric time controls
    try:
        base_time = int(tc.split("+")[0].split("/")[0])
        if base_time >= 900:  # 15+ minutes
            return "rapid"
        elif base_time >= 600:  # 10+ minutes
            return "rapid"
        elif base_time >= 180:  # 3+ minutes
            return "blitz"
        else:
            return "bullet"
    except:
        return "blitz"


def calculate_performance_rating(
    games: List[Dict],
    platform: str = "chess.com"
) -> Tuple[Optional[float], str]:
    """
    Calculate performance rating from games.
    
    Args:
        games: List of game dicts with opponent_rating, result, time_control
        platform: 'chess.com' or 'lichess'
    
    Returns:
        (performance_rating, confidence)
    """
    if not games or len(games) < 5:
        return None, "insufficient"
    
    # Collect weighted data
    opponent_ratings = []
    weighted_scores = []
    total_weight = 0
    
    for i, game in enumerate(games[:25]):  # Max 25 games
        opp_rating = game.get("opponent_rating")
        result = game.get("result")  # "win", "loss", "draw"
        tc = game.get("time_control", "")
        
        if opp_rating is None or result is None:
            continue
        
        # Time control weight
        tc_category = classify_time_control(tc)
        tc_weight = TIME_CONTROL_WEIGHTS.get(tc_category, DEFAULT_TC_WEIGHT)
        
        # Recency weight: first 10 games = 2, rest = 1
        recency_weight = 2.0 if i < 10 else 1.0
        
        # Combined weight
        weight = tc_weight * recency_weight
        
        # Score (1 = win, 0.5 = draw, 0 = loss)
        if result == "win":
            score = 1.0
        elif result == "draw":
            score = 0.5
        else:
            score = 0.0
        
        opponent_ratings.append(opp_rating)
        weighted_scores.append((score, weight))
        total_weight += weight
    
    if len(opponent_ratings) < 5:
        return None, "insufficient"
    
    # Median opponent rating
    median_opponent = median(opponent_ratings)
    
    # Weighted score percentage
    weighted_score_sum = sum(s * w for s, w in weighted_scores)
    score_pct = weighted_score_sum / total_weight if total_weight > 0 else 0.5
    
    # Clamp score to avoid log(0) or log(inf)
    score_pct = max(0.1, min(0.9, score_pct))
    
    # Performance rating formula
    # perf = median_opponent + 400 * log10(score / (1 - score))
    try:
        perf_adjustment = 400 * math.log10(score_pct / (1 - score_pct))
        performance = median_opponent + perf_adjustment
    except:
        performance = median_opponent
    
    # Round to nearest 10
    performance = round(performance / 10) * 10
    
    # Confidence based on game count
    game_count = len(opponent_ratings)
    if game_count >= 20:
        confidence = "high"
    elif game_count >= 10:
        confidence = "medium"
    else:
        confidence = "low"
    
    return performance, confidence


def calculate_combined_rating(
    chesscom_games: List[Dict],
    lichess_games: List[Dict]
) -> Dict:
    """
    Calculate combined skill assessment from both platforms.
    
    Returns:
        {
            "assessed_rating": int,
            "confidence": str,
            "platforms": {"chess.com": {...}, "lichess": {...}},
            "skill_level": str
        }
    """
    result = {
        "assessed_rating": None,
        "confidence": "insufficient",
        "platforms": {},
        "skill_level": "unknown"
    }
    
    performances = []
    weights = []
    
    # Chess.com performance
    if chesscom_games:
        perf, conf = calculate_performance_rating(chesscom_games, "chess.com")
        if perf:
            result["platforms"]["chess.com"] = {
                "performance": perf,
                "confidence": conf,
                "games": len(chesscom_games[:25])
            }
            performances.append(perf)
            weights.append(len(chesscom_games[:25]))
    
    # Lichess performance
    if lichess_games:
        perf, conf = calculate_performance_rating(lichess_games, "lichess")
        if perf:
            result["platforms"]["lichess"] = {
                "performance": perf,
                "confidence": conf,
                "games": len(lichess_games[:25])
            }
            performances.append(perf)
            weights.append(len(lichess_games[:25]))
    
    # Combine performances (weighted by game count)
    if performances:
        total_weight = sum(weights)
        combined = sum(p * w for p, w in zip(performances, weights)) / total_weight
        result["assessed_rating"] = int(round(combined / 10) * 10)
        
        # Overall confidence
        total_games = sum(weights)
        if total_games >= 20:
            result["confidence"] = "high"
        elif total_games >= 10:
            result["confidence"] = "medium"
        else:
            result["confidence"] = "low"
        
        # Skill level classification
        rating = result["assessed_rating"]
        if rating >= 2000:
            result["skill_level"] = "expert"
        elif rating >= 1800:
            result["skill_level"] = "advanced"
        elif rating >= 1400:
            result["skill_level"] = "intermediate"
        elif rating >= 1000:
            result["skill_level"] = "developing"
        else:
            result["skill_level"] = "beginner"
    
    return result
