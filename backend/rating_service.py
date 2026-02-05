"""
Rating Prediction & Training Service for Chess Coach AI

This module provides:
1. Rating trajectory prediction based on performance metrics
2. Time management analysis from game clock data
3. Fast thinking/calculation training with personalized puzzles
"""

import logging
import re
import random
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import math

logger = logging.getLogger(__name__)

# ==================== RATING PREDICTION ====================

class RatingMilestone(int, Enum):
    """Standard rating milestones"""
    BEGINNER = 800
    NOVICE = 1000
    INTERMEDIATE = 1200
    CLUB = 1400
    STRONG_CLUB = 1600
    EXPERT = 1800
    CANDIDATE_MASTER = 2000
    MASTER = 2200

MILESTONE_NAMES = {
    800: "Beginner",
    1000: "Novice",
    1200: "Intermediate",
    1400: "Club Player",
    1600: "Strong Club",
    1800: "Expert",
    2000: "Candidate Master",
    2200: "Master"
}

def get_next_milestone(current_rating: int) -> Tuple[int, str]:
    """Get the next rating milestone above current rating"""
    milestones = sorted(MILESTONE_NAMES.keys())
    for m in milestones:
        if m > current_rating:
            return m, MILESTONE_NAMES[m]
    return 2400, "Senior Master"

def calculate_performance_rating(games: List[Dict], user_id: str) -> Optional[int]:
    """
    Calculate performance rating from recent games.
    Uses a simplified version of FIDE performance rating calculation.
    """
    if not games:
        return None
    
    # Get games with opponent ratings (if available from analysis)
    scored_games = []
    for game in games[-30:]:  # Last 30 games
        result = game.get('result', '*')
        user_color = game.get('user_color', 'white')
        
        # Determine score
        if result == '1-0':
            score = 1.0 if user_color == 'white' else 0.0
        elif result == '0-1':
            score = 0.0 if user_color == 'white' else 1.0
        elif result == '1/2-1/2':
            score = 0.5
        else:
            continue
        
        scored_games.append({'score': score, 'game': game})
    
    if not scored_games:
        return None
    
    # Calculate win rate
    total_score = sum(g['score'] for g in scored_games)
    win_rate = total_score / len(scored_games)
    
    # Estimate performance based on win rate
    # This is a simplified model - higher win rate = higher performance
    base_rating = 1200  # Assume average opponent
    if win_rate > 0.75:
        return base_rating + 300
    elif win_rate > 0.60:
        return base_rating + 150
    elif win_rate > 0.50:
        return base_rating + 50
    elif win_rate > 0.40:
        return base_rating - 50
    else:
        return base_rating - 150

def calculate_improvement_velocity(analyses: List[Dict]) -> Dict[str, Any]:
    """
    Calculate how fast the player is improving based on analysis metrics.
    Returns improvement velocity and trend.
    """
    if len(analyses) < 5:
        return {
            "velocity": 0,
            "trend": "insufficient_data",
            "blunder_trend": "unknown",
            "accuracy_trend": "unknown"
        }
    
    # Sort by date
    sorted_analyses = sorted(analyses, key=lambda x: x.get('analyzed_at', ''))
    
    # Split into two halves
    mid = len(sorted_analyses) // 2
    first_half = sorted_analyses[:mid]
    second_half = sorted_analyses[mid:]
    
    # Calculate average metrics for each half
    def avg_metric(items, key, default=0):
        values = [item.get(key, default) for item in items if key in item]
        return sum(values) / len(values) if values else default
    
    # Blunders trend (lower is better)
    first_blunders = avg_metric(first_half, 'blunders', 2)
    second_blunders = avg_metric(second_half, 'blunders', 2)
    blunder_improvement = first_blunders - second_blunders
    
    # Best moves trend (higher is better)
    first_best = avg_metric(first_half, 'best_moves', 5)
    second_best = avg_metric(second_half, 'best_moves', 5)
    best_move_improvement = second_best - first_best
    
    # Calculate velocity (rating points per month estimate)
    # Each blunder reduced = ~10 rating points
    # Each best move increase = ~5 rating points
    velocity = (blunder_improvement * 10) + (best_move_improvement * 5)
    
    # Determine trend
    if velocity > 15:
        trend = "rapid_improvement"
    elif velocity > 5:
        trend = "steady_improvement"
    elif velocity > -5:
        trend = "stable"
    elif velocity > -15:
        trend = "slight_decline"
    else:
        trend = "needs_attention"
    
    return {
        "velocity": round(velocity, 1),
        "trend": trend,
        "blunder_trend": "improving" if blunder_improvement > 0.3 else "stable" if blunder_improvement > -0.3 else "worsening",
        "accuracy_trend": "improving" if best_move_improvement > 1 else "stable" if best_move_improvement > -1 else "worsening",
        "games_analyzed": len(sorted_analyses),
        "blunders_per_game": {
            "before": round(first_blunders, 1),
            "after": round(second_blunders, 1)
        },
        "best_moves_per_game": {
            "before": round(first_best, 1),
            "after": round(second_best, 1)
        }
    }

def predict_rating_trajectory(
    current_rating: int,
    improvement_velocity: Dict[str, Any],
    weaknesses: List[Dict]
) -> Dict[str, Any]:
    """
    Predict future rating based on current metrics and improvement velocity.
    """
    velocity = improvement_velocity.get("velocity", 0)
    trend = improvement_velocity.get("trend", "stable")
    
    # Base monthly gain from velocity
    monthly_gain = velocity
    
    # Adjust based on weakness count (more weaknesses = more room to grow)
    weakness_count = len(weaknesses)
    if weakness_count > 5:
        monthly_gain += 5  # Lots of low-hanging fruit
    elif weakness_count > 3:
        monthly_gain += 2
    
    # Cap the monthly gain to realistic values
    monthly_gain = max(-20, min(40, monthly_gain))
    
    # Calculate projections
    projection_1m = current_rating + monthly_gain
    projection_3m = current_rating + (monthly_gain * 2.5)  # Diminishing returns
    projection_6m = current_rating + (monthly_gain * 4)
    
    # Get next milestone
    next_milestone, milestone_name = get_next_milestone(current_rating)
    
    # Calculate time to milestone
    points_needed = next_milestone - current_rating
    if monthly_gain > 0:
        months_to_milestone = math.ceil(points_needed / monthly_gain)
    else:
        months_to_milestone = None  # Not on track
    
    # Rating gain potential from fixing weaknesses
    weakness_rating_impact = []
    for w in weaknesses[:5]:  # Top 5 weaknesses
        category = w.get('category', 'tactical')
        occurrences = w.get('occurrences', 1)
        
        # Estimate rating impact
        if category == 'tactical':
            impact = min(50, occurrences * 15)
        elif category == 'strategic':
            impact = min(40, occurrences * 10)
        elif category == 'opening_principles':
            impact = min(30, occurrences * 8)
        else:
            impact = min(25, occurrences * 5)
        
        weakness_rating_impact.append({
            "weakness": w.get('subcategory', w.get('name', 'unknown')),
            "category": category,
            "potential_rating_gain": impact,
            "occurrences": occurrences
        })
    
    total_potential = sum(w['potential_rating_gain'] for w in weakness_rating_impact)
    
    return {
        "current_rating": current_rating,
        "projected_rating": {
            "1_month": round(projection_1m),
            "3_months": round(projection_3m),
            "6_months": round(projection_6m),
            "range_3m": [round(projection_3m - 30), round(projection_3m + 30)]
        },
        "monthly_velocity": round(monthly_gain, 1),
        "trend": trend,
        "next_milestone": {
            "rating": next_milestone,
            "name": milestone_name,
            "points_needed": points_needed,
            "estimated_months": months_to_milestone
        },
        "weakness_impact": weakness_rating_impact,
        "total_potential_gain": total_potential,
        "improvement_tips": generate_improvement_tips(trend, weaknesses)
    }

def generate_improvement_tips(trend: str, weaknesses: List[Dict]) -> List[str]:
    """Generate personalized tips based on trend and weaknesses"""
    tips = []
    
    if trend == "rapid_improvement":
        tips.append("🔥 You're on fire! Keep up the focused practice.")
    elif trend == "steady_improvement":
        tips.append("📈 Steady progress! Consistency is key.")
    elif trend == "stable":
        tips.append("💡 Try focusing on one weakness at a time to break through.")
    elif trend in ["slight_decline", "needs_attention"]:
        tips.append("⚠️ Consider taking a short break, then focusing on fundamentals.")
    
    # Add weakness-specific tips
    if weaknesses:
        top_weakness = weaknesses[0]
        category = top_weakness.get('category', '')
        subcat = top_weakness.get('subcategory', '')
        
        if category == 'tactical':
            tips.append(f"🎯 Practice {subcat.replace('_', ' ')} puzzles daily - this is your biggest rating opportunity.")
        elif category == 'opening_principles':
            tips.append("📚 Review your opening moves - small improvements here compound over many games.")
        elif category == 'endgame_fundamentals':
            tips.append("♟️ Study basic endgame patterns - this separates intermediate from advanced players.")
    
    return tips[:3]

# ==================== TIME MANAGEMENT ANALYSIS ====================

def parse_clock_times_from_pgn(pgn: str) -> List[Dict[str, Any]]:
    """
    Extract clock times from PGN comments.
    Chess.com format: {[%clk 0:09:45]}
    Lichess format: { [%clk 0:09:45] } or %clk inline
    """
    moves_with_time = []
    
    # Find all clock annotations - multiple patterns
    # Pattern 1: Standard [%clk H:MM:SS]
    clock_pattern = r'\[%clk\s*(\d+):(\d+):(\d+)\]'
    # Pattern 2: Also try without brackets for some formats
    clock_pattern_alt = r'%clk\s*(\d+):(\d+):(\d+)'
    
    # Try standard pattern first
    matches = re.findall(clock_pattern, pgn)
    
    # If no matches, try alternative pattern
    if not matches:
        matches = re.findall(clock_pattern_alt, pgn)
    
    move_num = 0
    for match in matches:
        hours, minutes, seconds = int(match[0]), int(match[1]), int(match[2])
        total_seconds = hours * 3600 + minutes * 60 + seconds
        move_num += 1
        moves_with_time.append({
            "move_number": (move_num + 1) // 2,
            "is_white": move_num % 2 == 1,
            "clock_remaining": total_seconds
        })
    
    return moves_with_time


def extract_time_control_seconds(time_control: str) -> int:
    """
    Parse time control string to get initial time in seconds.
    Examples: "600" (10 min), "180+2" (3 min + 2 sec increment), "600+5"
    """
    if not time_control:
        return 0
    
    try:
        # Handle increment format: "600+5"
        if '+' in time_control:
            base_time = int(time_control.split('+')[0])
        elif '/' in time_control:
            # Daily format: "1/86400"
            parts = time_control.split('/')
            base_time = int(parts[1]) if len(parts) > 1 else 0
        else:
            base_time = int(time_control)
        return base_time
    except (ValueError, IndexError):
        return 0


def analyze_time_usage(games: List[Dict], user_id: str) -> Dict[str, Any]:
    """
    Analyze time usage patterns across recent games.
    Uses actual clock data from PGN annotations.
    
    Note: Clock data is only available in games where the platform 
    records move times (typically rapid/classical with clock enabled).
    """
    all_time_data = []
    games_with_time = 0
    games_checked = 0
    time_control_info = []
    
    for game in games[-30:]:  # Check last 30 games
        games_checked += 1
        pgn = game.get('pgn', '')
        user_color = game.get('user_color', 'white')
        time_control = game.get('time_control', '')
        
        clock_times = parse_clock_times_from_pgn(pgn)
        if not clock_times:
            continue
        
        games_with_time += 1
        
        # Track time control for context
        if time_control:
            initial_time = extract_time_control_seconds(time_control)
            if initial_time > 0:
                time_control_info.append(initial_time)
        
        # Filter to user's moves only
        user_moves = [t for t in clock_times if (t['is_white'] and user_color == 'white') or 
                                                  (not t['is_white'] and user_color == 'black')]
        
        if len(user_moves) < 2:
            continue
        
        # Calculate time spent per move
        for i in range(1, len(user_moves)):
            time_spent = user_moves[i-1]['clock_remaining'] - user_moves[i]['clock_remaining']
            if time_spent > 0:
                all_time_data.append({
                    "move_number": user_moves[i]['move_number'],
                    "time_spent": time_spent,
                    "clock_remaining": user_moves[i]['clock_remaining'],
                    "game_phase": get_game_phase(user_moves[i]['move_number'])
                })
    
    if not all_time_data:
        return {
            "has_data": False,
            "games_checked": games_checked,
            "games_with_clock": games_with_time,
            "message": f"Checked {games_checked} recent games but found no clock data. Clock annotations are only available in timed games (rapid/classical) where the platform records move times. Try playing more rapid games on Chess.com or Lichess with the clock visible."
        }
    
    # Analyze by game phase
    phases = {"opening": [], "middlegame": [], "endgame": []}
    for td in all_time_data:
        phases[td['game_phase']].append(td['time_spent'])
    
    phase_averages = {}
    for phase, times in phases.items():
        if times:
            phase_averages[phase] = {
                "avg_time": round(sum(times) / len(times), 1),
                "max_time": max(times),
                "move_count": len(times)
            }
    
    # Detect time trouble patterns
    time_trouble_moves = [td for td in all_time_data if td['clock_remaining'] < 60]
    
    # Calculate overall stats
    total_time = sum(td['time_spent'] for td in all_time_data)
    opening_time = sum(phases.get('opening', []))
    
    opening_percentage = (opening_time / total_time * 100) if total_time > 0 else 0
    
    # Generate insights
    insights = []
    
    if opening_percentage > 35:
        insights.append({
            "type": "warning",
            "message": f"You spend {round(opening_percentage)}% of your time in the opening. Try to play the first 10 moves faster.",
            "category": "opening_time"
        })
    
    if len(time_trouble_moves) > 5:
        insights.append({
            "type": "critical",
            "message": f"You reached time trouble (<1 min) in {len(time_trouble_moves)} positions. Practice faster decision-making.",
            "category": "time_trouble"
        })
    
    if phase_averages.get('endgame', {}).get('avg_time', 0) > phase_averages.get('middlegame', {}).get('avg_time', 0):
        insights.append({
            "type": "info",
            "message": "You're slower in endgames. Study basic endgame patterns to play them more confidently.",
            "category": "endgame_speed"
        })
    
    return {
        "has_data": True,
        "games_analyzed": games_with_time,
        "total_moves_analyzed": len(all_time_data),
        "phase_breakdown": phase_averages,
        "time_trouble_count": len(time_trouble_moves),
        "opening_time_percentage": round(opening_percentage, 1),
        "insights": insights,
        "recommendations": generate_time_recommendations(phase_averages, opening_percentage, len(time_trouble_moves))
    }

def get_game_phase(move_number: int) -> str:
    """Determine game phase based on move number"""
    if move_number <= 10:
        return "opening"
    elif move_number <= 30:
        return "middlegame"
    else:
        return "endgame"

def generate_time_recommendations(phase_averages: Dict, opening_pct: float, trouble_count: int) -> List[str]:
    """Generate time management recommendations"""
    recs = []
    
    if opening_pct > 30:
        recs.append("📖 Pre-move your first 5-6 opening moves - you should know them by heart")
    
    if trouble_count > 3:
        recs.append("⏰ Set mental checkpoints: By move 20, have at least half your time remaining")
    
    opening_avg = phase_averages.get('opening', {}).get('avg_time', 0)
    if opening_avg > 30:
        recs.append("🚀 Practice blitz games to improve opening speed and pattern recognition")
    
    if len(recs) == 0:
        recs.append("✅ Your time management looks solid! Keep maintaining this discipline.")
    
    return recs

# ==================== FAST THINKING / PUZZLE TRAINER ====================

# Predefined puzzle templates based on weakness categories
PUZZLE_TEMPLATES = {
    "pin_blindness": [
        {"fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4", "solution": "Qxf7#", "theme": "pin", "difficulty": "easy"},
        {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "solution": "Nxe4", "theme": "pin", "difficulty": "medium"},
    ],
    "fork_misses": [
        {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", "solution": "Bb5", "theme": "fork_setup", "difficulty": "easy"},
        {"fen": "r2qkb1r/ppp2ppp/2n1bn2/3pp3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 0 5", "solution": "Nxe5", "theme": "fork", "difficulty": "medium"},
    ],
    "back_rank_weakness": [
        {"fen": "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", "solution": "Re8#", "theme": "back_rank", "difficulty": "easy"},
        {"fen": "3r2k1/5ppp/8/8/8/8/5PPP/3RR1K1 w - - 0 1", "solution": "Rd8+", "theme": "back_rank", "difficulty": "medium"},
    ],
    "one_move_blunders": [
        {"fen": "r1bqkbnr/pppppppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2", "solution": "d4", "theme": "center_control", "difficulty": "easy"},
    ],
    "center_control_neglect": [
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "solution": "e4", "theme": "opening", "difficulty": "easy"},
    ],
    "delayed_castling": [
        {"fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", "solution": "O-O", "theme": "castle", "difficulty": "easy"},
    ]
}

# Thinking speed tips based on patterns
THINKING_TIPS = {
    "pin_blindness": [
        "Before each move, scan for pieces that are aligned with higher-value pieces behind them",
        "Ask yourself: 'If I move this piece, what does it uncover?'",
        "Practice the 'X-ray' vision: look through pieces to see what's behind"
    ],
    "fork_misses": [
        "After each opponent move, check if any of their pieces can be attacked together",
        "Knights are fork machines - always check knight jumps first",
        "Look for undefended pieces - they're fork targets"
    ],
    "one_move_blunders": [
        "Before clicking, ask: 'What can my opponent do after this move?'",
        "Use the 'Blunder Check': Is this piece hanging? Is my king safe?",
        "Take 5 extra seconds on every move - it's worth it"
    ],
    "time_trouble_blunders": [
        "Set a mental alarm at 2 minutes - switch to 'survival mode'",
        "In time trouble, prefer solid moves over brilliant ones",
        "Practice bullet chess to improve quick decision-making"
    ],
    "back_rank_weakness": [
        "Before attacking, always check: 'Is my back rank safe?'",
        "Create a luft (h3/h6) early when queens are still on the board",
        "In endings, keep your king active - back rank only matters with heavy pieces"
    ]
}

def generate_training_session(weaknesses: List[Dict], session_length: int = 5) -> Dict[str, Any]:
    """
    Generate a personalized training session with puzzles based on weaknesses.
    """
    if not weaknesses:
        # Default training
        return {
            "session_type": "general",
            "puzzles": get_random_puzzles(session_length),
            "focus_area": "general tactics",
            "tips": ["Practice regularly to build pattern recognition"]
        }
    
    # Get top weakness
    top_weakness = weaknesses[0]
    weakness_key = top_weakness.get('subcategory', top_weakness.get('name', '')).lower().replace(' ', '_')
    
    # Find matching puzzles
    puzzles = PUZZLE_TEMPLATES.get(weakness_key, [])
    
    if not puzzles:
        # Try category-level puzzles
        category = top_weakness.get('category', 'tactical')
        for key, puzzle_list in PUZZLE_TEMPLATES.items():
            if key in weakness_key or weakness_key in key:
                puzzles.extend(puzzle_list)
    
    # If still no puzzles, use general tactical puzzles
    if not puzzles:
        puzzles = get_random_puzzles(session_length)
    
    # Get tips
    tips = THINKING_TIPS.get(weakness_key, [])
    if not tips:
        tips = ["Focus on this pattern in your games", "Practice makes permanent - drill daily"]
    
    return {
        "session_type": "targeted",
        "target_weakness": weakness_key.replace('_', ' ').title(),
        "puzzles": puzzles[:session_length],
        "focus_area": top_weakness.get('category', 'tactics'),
        "tips": tips,
        "estimated_time_minutes": session_length * 2,
        "next_weakness": weaknesses[1].get('subcategory', '') if len(weaknesses) > 1 else None
    }

def get_random_puzzles(count: int) -> List[Dict]:
    """Get random puzzles from all categories"""
    all_puzzles = []
    for puzzles in PUZZLE_TEMPLATES.values():
        all_puzzles.extend(puzzles)
    
    if not all_puzzles:
        return []
    
    return random.sample(all_puzzles, min(count, len(all_puzzles)))

def generate_calculation_analysis(analyses: List[Dict]) -> Dict[str, Any]:
    """
    Analyze where the player is slow to spot tactics.
    """
    if not analyses:
        return {"has_data": False}
    
    # Analyze move-by-move data for patterns
    pattern_misses = {}
    
    for analysis in analyses[-20:]:
        move_by_move = analysis.get('move_by_move', [])
        for move in move_by_move:
            evaluation = move.get('evaluation', '')
            thinking_pattern = move.get('thinking_pattern', '')
            
            if evaluation in ['blunder', 'mistake']:
                if thinking_pattern and thinking_pattern != 'solid_thinking':
                    pattern_misses[thinking_pattern] = pattern_misses.get(thinking_pattern, 0) + 1
    
    # Sort by frequency
    sorted_patterns = sorted(pattern_misses.items(), key=lambda x: x[1], reverse=True)
    
    # Generate analysis
    speed_issues = []
    for pattern, count in sorted_patterns[:3]:
        speed_issues.append({
            "pattern": pattern.replace('_', ' ').title(),
            "occurrences": count,
            "tip": THINKING_TIPS.get(pattern, ["Practice this pattern"])[0]
        })
    
    return {
        "has_data": True,
        "games_analyzed": len(analyses),
        "speed_issues": speed_issues,
        "overall_tip": "Pattern recognition improves with repetition. Do 10-15 puzzles daily focusing on your weak patterns.",
        "recommended_drill_time": "15 minutes daily"
    }

# ==================== PLATFORM RATING FETCHER ====================

async def fetch_platform_ratings(chess_com_username: str = None, lichess_username: str = None) -> Dict[str, Any]:
    """
    Fetch current ratings from Chess.com and Lichess.
    To be called with httpx from the server.
    """
    import httpx
    
    ratings = {}
    
    if chess_com_username:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.chess.com/pub/player/{chess_com_username}/stats")
                if resp.status_code == 200:
                    data = resp.json()
                    ratings['chess_com'] = {
                        'rapid': data.get('chess_rapid', {}).get('last', {}).get('rating'),
                        'blitz': data.get('chess_blitz', {}).get('last', {}).get('rating'),
                        'bullet': data.get('chess_bullet', {}).get('last', {}).get('rating'),
                    }
        except Exception as e:
            logger.error(f"Failed to fetch Chess.com ratings: {e}")
    
    if lichess_username:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://lichess.org/api/user/{lichess_username}")
                if resp.status_code == 200:
                    data = resp.json()
                    perfs = data.get('perfs', {})
                    ratings['lichess'] = {
                        'rapid': perfs.get('rapid', {}).get('rating'),
                        'blitz': perfs.get('blitz', {}).get('rating'),
                        'bullet': perfs.get('bullet', {}).get('rating'),
                        'classical': perfs.get('classical', {}).get('rating'),
                    }
        except Exception as e:
            logger.error(f"Failed to fetch Lichess ratings: {e}")
    
    return ratings
