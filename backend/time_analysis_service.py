"""
Time Analysis Service - Extract and analyze time data from PGN

Parses clock times from PGN comments like {[%clk 0:15:07.6]} and provides:
- Time spent on each move
- Time pressure detection
- Time management patterns
- Correlation between time and mistakes
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MoveTime:
    """Time data for a single move."""
    move_number: int
    color: str  # 'white' or 'black'
    san: str  # Move in SAN notation
    clock_after: float  # Seconds remaining after move
    time_spent: float  # Seconds spent on this move
    is_time_pressure: bool  # True if <30s remaining
    is_rushed: bool  # True if <5s spent on move
    is_slow: bool  # True if >60s spent on move


def parse_clock_time(clock_str: str) -> float:
    """
    Parse clock time string like '0:15:07.6' to seconds.
    
    Args:
        clock_str: Time string in format H:MM:SS.d or MM:SS.d
    
    Returns:
        Total seconds as float
    """
    try:
        parts = clock_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        else:
            return float(clock_str)
    except (ValueError, TypeError):
        return 0.0


def extract_time_data_from_pgn(pgn: str) -> Dict:
    """
    Extract comprehensive time data from PGN.
    
    Args:
        pgn: Full PGN string with clock annotations
        
    Returns:
        {
            "has_time_data": bool,
            "initial_time": float,  # Starting time in seconds
            "increment": float,  # Increment per move
            "moves": [MoveTime, ...],
            "white_time_profile": {...},
            "black_time_profile": {...},
            "time_pressure_moves": [...],  # Moves made under time pressure
            "rushed_moves": [...],  # Moves made very quickly
        }
    """
    # Extract TimeControl header
    time_control_match = re.search(r'\[TimeControl "([^"]+)"\]', pgn)
    initial_time = 0
    increment = 0
    
    if time_control_match:
        tc = time_control_match.group(1)
        if '+' in tc:
            parts = tc.split('+')
            initial_time = int(parts[0])
            increment = int(parts[1]) if len(parts) > 1 else 0
        elif '|' in tc:
            parts = tc.split('|')
            initial_time = int(parts[0]) * 60  # Minutes to seconds
            increment = int(parts[1]) if len(parts) > 1 else 0
        else:
            try:
                initial_time = int(tc)
            except ValueError:
                pass
    
    if not moves:
        return {"has_time_data": False, "moves": []}
    
    # Build time profiles
    white_moves = [m for m in moves if m.color == 'white']
    black_moves = [m for m in moves if m.color == 'black']
    
    def build_profile(color_moves: List[MoveTime]) -> Dict:
        if not color_moves:
            return {}
        
        times = [m.time_spent for m in color_moves]
        return {
            "total_time_used": sum(times),
            "avg_time_per_move": sum(times) / len(times),
            "fastest_move": min(times),
            "slowest_move": max(times),
            "time_pressure_moves": len([m for m in color_moves if m.is_time_pressure]),
            "rushed_moves": len([m for m in color_moves if m.is_rushed]),
            "final_clock": color_moves[-1].clock_after if color_moves else 0,
        }
    
    # Find critical time decisions
    time_pressure_moves = [
        {"move_number": m.move_number, "san": m.san, "clock": m.clock_after, "time_spent": m.time_spent}
        for m in moves if m.is_time_pressure
    ]
    
    rushed_moves = [
        {"move_number": m.move_number, "san": m.san, "clock": m.clock_after, "time_spent": m.time_spent}
        for m in moves if m.is_rushed
    ]
    
    return {
        "has_time_data": True,
        "initial_time": initial_time,
        "increment": increment,
        "total_moves": len(moves),
        "moves": [
            {
                "move_number": m.move_number,
                "color": m.color,
                "san": m.san,
                "clock_after": round(m.clock_after, 1),
                "time_spent": round(m.time_spent, 1),
                "is_time_pressure": m.is_time_pressure,
                "is_rushed": m.is_rushed,
                "is_slow": m.is_slow,
            }
            for m in moves
        ],
        "white_profile": build_profile(white_moves),
        "black_profile": build_profile(black_moves),
        "time_pressure_moves": time_pressure_moves,
        "rushed_moves": rushed_moves,
    }


def get_time_context_for_move(
    time_data: Dict,
    move_number: int,
    color: str
) -> Dict:
    """
    Get time context for a specific move.
    
    Returns:
        {
            "time_spent": 3.5,
            "clock_after": 245.0,
            "is_time_pressure": False,
            "is_rushed": True,
            "time_category": "rushed" | "normal" | "long_think" | "time_pressure",
            "insight": "You spent only 3 seconds on this move - too fast for a critical decision"
        }
    """
    if not time_data.get("has_time_data"):
        return {"has_data": False}
    
    # Find the specific move
    target_move = None
    for m in time_data.get("moves", []):
        if m["move_number"] == move_number and m["color"] == color:
            target_move = m
            break
    
    if not target_move:
        return {"has_data": False}
    
    time_spent = target_move["time_spent"]
    clock_after = target_move["clock_after"]
    is_time_pressure = target_move["is_time_pressure"]
    is_rushed = target_move["is_rushed"]
    is_slow = target_move["is_slow"]
    
    # Categorize
    if is_time_pressure:
        category = "time_pressure"
        insight = f"You had only {clock_after:.0f}s left - time pressure affected this decision"
    elif is_rushed:
        category = "rushed"
        insight = f"You spent only {time_spent:.1f}s on this move - too fast for a critical position"
    elif is_slow:
        category = "long_think"
        insight = f"You thought for {time_spent:.0f}s - you sensed something important here"
    else:
        category = "normal"
        insight = None
    
    return {
        "has_data": True,
        "time_spent": time_spent,
        "clock_after": clock_after,
        "is_time_pressure": is_time_pressure,
        "is_rushed": is_rushed,
        "is_slow": is_slow,
        "time_category": category,
        "insight": insight,
    }


def analyze_time_management(time_data: Dict, user_color: str) -> Dict:
    """
    Analyze overall time management patterns.
    
    Returns insights like:
    - "You used 60% of your time in the first 15 moves"
    - "Your average think time dropped from 25s to 8s in the last 10 moves"
    - "You made 5 rushed moves (<5s) in winning positions"
    """
    if not time_data.get("has_time_data"):
        return {"has_analysis": False}
    
    profile_key = f"{user_color}_profile"
    profile = time_data.get(profile_key, {})
    
    if not profile:
        return {"has_analysis": False}
    
    moves = [m for m in time_data.get("moves", []) if m["color"] == user_color]
    
    if not moves:
        return {"has_analysis": False}
    
    insights = []
    
    # Check opening vs endgame time distribution
    opening_moves = moves[:10]
    endgame_moves = moves[-10:] if len(moves) > 10 else []
    
    if opening_moves and endgame_moves:
        opening_time = sum(m["time_spent"] for m in opening_moves)
        endgame_time = sum(m["time_spent"] for m in endgame_moves)
        total_time = profile.get("total_time_used", 1)
        
        opening_pct = (opening_time / total_time * 100) if total_time > 0 else 0
        
        if opening_pct > 50:
            insights.append({
                "type": "time_front_loaded",
                "message": f"You used {opening_pct:.0f}% of your time in the first 10 moves - consider saving time for critical positions",
                "severity": "warning",
            })
        
        if endgame_moves:
            avg_opening = opening_time / len(opening_moves)
            avg_endgame = endgame_time / len(endgame_moves)
            
            if avg_endgame < avg_opening * 0.3:
                insights.append({
                    "type": "rushed_endgame",
                    "message": f"Your average think time dropped from {avg_opening:.0f}s to {avg_endgame:.0f}s - endgame decisions were rushed",
                    "severity": "warning",
                })
    
    # Check for rushed critical moves
    rushed_count = profile.get("rushed_moves", 0)
    if rushed_count > 3:
        insights.append({
            "type": "too_many_rushed",
            "message": f"You made {rushed_count} moves in under 5 seconds - slow down on critical positions",
            "severity": "info",
        })
    
    # Time pressure summary
    tp_moves = profile.get("time_pressure_moves", 0)
    if tp_moves > 5:
        insights.append({
            "type": "time_trouble",
            "message": f"You played {tp_moves} moves under time pressure (<30s) - work on time management",
            "severity": "warning",
        })
    
    return {
        "has_analysis": True,
        "total_time_used": profile.get("total_time_used", 0),
        "avg_time_per_move": profile.get("avg_time_per_move", 0),
        "final_clock": profile.get("final_clock", 0),
        "rushed_moves": rushed_count,
        "time_pressure_moves": tp_moves,
        "insights": insights,
    }
