"""
Focus Mastery Service - Tracks user's progress on cognitive patterns.

Each user has focus areas (like "Check all captures", "Scan for pins") and this 
service tracks how well they're mastering these patterns over time.

Mastery levels:
- novice: Just started working on this
- developing: Showing progress, but inconsistent  
- competent: Consistent improvement, occasional lapses
- proficient: Strong pattern recognition
- master: Rarely makes this type of mistake
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict


# Focus pattern definitions with training protocols
FOCUS_PATTERNS = {
    # Tactical patterns
    "check_captures_threats": {
        "name": "Check all captures",
        "category": "tactical",
        "description": "Before moving, scan all captures on the board",
        "protocol": ["List opponent's captures", "List your captures", "Compare threats"],
        "mistake_triggers": ["hanging_pieces", "missed_capture", "blunder"],
    },
    "scan_for_pins": {
        "name": "Scan for pins",
        "category": "tactical", 
        "description": "Check if pieces are aligned with king/queen on same file/diagonal",
        "protocol": ["Find pieces on same line as king", "Check for enemy attackers"],
        "mistake_triggers": ["pin_blindness", "missed_pin"],
    },
    "calculate_forcing_moves": {
        "name": "Calculate forcing moves",
        "category": "tactical",
        "description": "Always check checks, captures, threats before committing",
        "protocol": ["List all checks", "List all captures", "List direct threats"],
        "mistake_triggers": ["missed_tactic", "tunnel_vision"],
    },
    "look_for_forks": {
        "name": "Look for forks",
        "category": "tactical",
        "description": "Check if a piece can attack two targets simultaneously",
        "protocol": ["Find undefended pieces", "Check knight squares", "Check pawn squares"],
        "mistake_triggers": ["missed_fork", "fork_vulnerability"],
    },
    
    # Positional patterns
    "piece_activity_check": {
        "name": "Piece activity check",
        "category": "positional",
        "description": "Ensure all pieces are active and have purpose",
        "protocol": ["Count active pieces", "Find worst piece", "Plan to activate it"],
        "mistake_triggers": ["passive_piece", "poor_coordination"],
    },
    "king_safety_awareness": {
        "name": "King safety awareness",
        "category": "positional",
        "description": "Regularly assess king safety for both sides",
        "protocol": ["Count defenders", "Check open files near king", "Assess pawn shelter"],
        "mistake_triggers": ["king_safety", "weakened_castling"],
    },
    "pawn_structure_thinking": {
        "name": "Pawn structure thinking",
        "category": "positional",
        "description": "Consider pawn moves carefully - they can't go back",
        "protocol": ["Check for weaknesses created", "Assess outpost squares", "Consider pawn breaks"],
        "mistake_triggers": ["weak_pawns", "structural_damage"],
    },
    
    # Decision quality patterns
    "avoid_hope_chess": {
        "name": "Avoid hope chess",
        "category": "decision",
        "description": "Don't just hope opponent misses your threat - verify it works",
        "protocol": ["Ask: What's opponent's best reply?", "If they find it, is my move still good?"],
        "mistake_triggers": ["hope_chess", "wishful_thinking"],
    },
    "slow_down_critical": {
        "name": "Slow down on critical moves",
        "category": "decision",
        "description": "Take extra time when position is sharp or material is at stake",
        "protocol": ["Recognize critical moment", "Use full time", "Double-check calculation"],
        "mistake_triggers": ["rushing", "time_trouble_blunder"],
    },
    "prophylaxis_thinking": {
        "name": "Prophylaxis thinking",
        "category": "decision",
        "description": "Ask what opponent wants to do and prevent it",
        "protocol": ["What's opponent's threat?", "What's their plan?", "Can I stop it profitably?"],
        "mistake_triggers": ["missed_threat", "ignored_opponent_plan"],
    },
}


def get_mastery_level(score: float) -> str:
    """Convert mastery score (0-100) to level name."""
    if score >= 90:
        return "master"
    elif score >= 75:
        return "proficient"
    elif score >= 55:
        return "competent"
    elif score >= 30:
        return "developing"
    return "novice"


def get_mastery_color(level: str) -> str:
    """Get color class for mastery level."""
    colors = {
        "master": "text-yellow-500",
        "proficient": "text-emerald-500",
        "competent": "text-blue-500",
        "developing": "text-amber-500",
        "novice": "text-gray-500",
    }
    return colors.get(level, "text-gray-500")


def calculate_pattern_mastery(
    pattern_key: str,
    game_analyses: List[Dict],
    recent_days: int = 30
) -> Dict:
    """
    Calculate mastery score for a specific pattern based on game history.
    
    Returns:
        {
            "pattern_key": "check_captures_threats",
            "name": "Check all captures",
            "mastery_score": 65.0,
            "mastery_level": "competent",
            "trend": "improving" | "stable" | "declining",
            "occurrences_recent": 3,
            "occurrences_total": 12,
            "last_occurrence": "2026-02-20",
            "improvement_rate": 15.0,  # % improvement over baseline
        }
    """
    pattern_def = FOCUS_PATTERNS.get(pattern_key)
    if not pattern_def:
        return None
    
    triggers = set(pattern_def.get("mistake_triggers", []))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=recent_days)
    
    # Track occurrences over time
    total_games = len(game_analyses)
    total_occurrences = 0
    recent_occurrences = 0
    old_occurrences = 0
    last_occurrence = None
    
    for analysis in game_analyses:
        created = analysis.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            except ValueError:
                continue
        
        is_recent = created and created >= cutoff
        
        # Check stockfish analysis for mistake types
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        
        game_has_pattern = False
        for move_eval in evals:
            if move_eval.get("evaluation") not in ["blunder", "mistake"]:
                continue
            
            # Check if the mistake matches our pattern triggers
            threat = (move_eval.get("threat") or "").lower()
            thinking = (move_eval.get("thinking_pattern") or "").lower()
            
            for trigger in triggers:
                if trigger in threat or trigger in thinking:
                    game_has_pattern = True
                    break
        
        if game_has_pattern:
            total_occurrences += 1
            if is_recent:
                recent_occurrences += 1
            else:
                old_occurrences += 1
            
            if last_occurrence is None or (created and created > last_occurrence):
                last_occurrence = created
    
    # Calculate mastery score
    # Higher score = fewer mistakes, improving trend
    if total_games == 0:
        mastery_score = 50.0  # Neutral starting point
    else:
        # Base score: games without this mistake / total games
        games_without = total_games - total_occurrences
        base_score = (games_without / total_games) * 100
        
        # Trend adjustment
        trend_adjustment = 0
        if recent_occurrences < old_occurrences:
            trend_adjustment = 10  # Improving
        elif recent_occurrences > old_occurrences:
            trend_adjustment = -10  # Getting worse
        
        mastery_score = min(100, max(0, base_score + trend_adjustment))
    
    # Determine trend
    if old_occurrences > 0 and recent_occurrences == 0:
        trend = "improving"
    elif recent_occurrences > old_occurrences * 1.5:
        trend = "declining"
    else:
        trend = "stable"
    
    # Calculate improvement rate
    improvement_rate = 0
    if old_occurrences > 0:
        improvement_rate = ((old_occurrences - recent_occurrences) / old_occurrences) * 100
    
    return {
        "pattern_key": pattern_key,
        "name": pattern_def["name"],
        "category": pattern_def["category"],
        "description": pattern_def["description"],
        "protocol": pattern_def["protocol"],
        "mastery_score": round(mastery_score, 1),
        "mastery_level": get_mastery_level(mastery_score),
        "trend": trend,
        "occurrences_recent": recent_occurrences,
        "occurrences_total": total_occurrences,
        "last_occurrence": last_occurrence.isoformat() if last_occurrence else None,
        "improvement_rate": round(improvement_rate, 1),
        "total_games_analyzed": total_games,
    }


def get_user_focus_mastery(
    user_id: str,
    game_analyses: List[Dict],
    active_focus_patterns: Optional[List[str]] = None
) -> Dict:
    """
    Get complete focus mastery data for a user.
    
    Args:
        user_id: User ID
        game_analyses: List of game analysis documents
        active_focus_patterns: Optional list of patterns user is actively working on
        
    Returns:
        {
            "user_id": "user_xxx",
            "total_patterns_tracked": 10,
            "active_patterns": [...],
            "patterns": {
                "check_captures_threats": {...mastery data...},
                ...
            },
            "overall_mastery": 62.5,
            "overall_level": "competent",
            "top_strength": {"pattern": "...", "score": 85},
            "biggest_gap": {"pattern": "...", "score": 35},
            "recommended_focus": "scan_for_pins",
        }
    """
    if active_focus_patterns is None:
        # Default to most common patterns
        active_focus_patterns = [
            "check_captures_threats",
            "scan_for_pins",
            "avoid_hope_chess",
            "king_safety_awareness",
        ]
    
    patterns_data = {}
    scores = []
    
    for pattern_key in FOCUS_PATTERNS.keys():
        mastery = calculate_pattern_mastery(pattern_key, game_analyses)
        if mastery:
            patterns_data[pattern_key] = mastery
            scores.append(mastery["mastery_score"])
    
    # Calculate overall mastery
    overall_mastery = sum(scores) / len(scores) if scores else 50.0
    
    # Find top strength and biggest gap
    sorted_patterns = sorted(patterns_data.values(), key=lambda x: x["mastery_score"], reverse=True)
    top_strength = sorted_patterns[0] if sorted_patterns else None
    biggest_gap = sorted_patterns[-1] if sorted_patterns else None
    
    # Recommend focus: lowest scoring pattern that user isn't already working on
    recommended = None
    for p in reversed(sorted_patterns):
        if p["pattern_key"] not in active_focus_patterns:
            recommended = p["pattern_key"]
            break
    
    # If all are already active, recommend the lowest scoring one
    if not recommended and biggest_gap:
        recommended = biggest_gap["pattern_key"]
    
    return {
        "user_id": user_id,
        "total_patterns_tracked": len(patterns_data),
        "active_patterns": active_focus_patterns,
        "patterns": patterns_data,
        "overall_mastery": round(overall_mastery, 1),
        "overall_level": get_mastery_level(overall_mastery),
        "top_strength": {
            "pattern": top_strength["pattern_key"],
            "name": top_strength["name"],
            "score": top_strength["mastery_score"],
        } if top_strength else None,
        "biggest_gap": {
            "pattern": biggest_gap["pattern_key"],
            "name": biggest_gap["name"],
            "score": biggest_gap["mastery_score"],
        } if biggest_gap else None,
        "recommended_focus": recommended,
    }


def get_pattern_drill_positions(
    pattern_key: str,
    game_analyses: List[Dict],
    limit: int = 5
) -> List[Dict]:
    """
    Get drill positions for a specific pattern from user's game history.
    These are positions where the user made the relevant mistake.
    
    Returns list of positions to practice.
    """
    pattern_def = FOCUS_PATTERNS.get(pattern_key)
    if not pattern_def:
        return []
    
    triggers = set(pattern_def.get("mistake_triggers", []))
    positions = []
    
    for analysis in game_analyses:
        game_id = analysis.get("game_id")
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        
        for move_eval in evals:
            if move_eval.get("evaluation") not in ["blunder", "mistake"]:
                continue
            
            threat = (move_eval.get("threat") or "").lower()
            thinking = (move_eval.get("thinking_pattern") or "").lower()
            
            for trigger in triggers:
                if trigger in threat or trigger in thinking:
                    fen = move_eval.get("fen_before")
                    if fen:
                        positions.append({
                            "game_id": game_id,
                            "fen": fen,
                            "best_move": move_eval.get("best_move"),
                            "your_move": move_eval.get("move"),
                            "explanation": move_eval.get("threat") or pattern_def["description"],
                            "pattern_key": pattern_key,
                        })
                    break
        
        if len(positions) >= limit:
            break
    
    return positions[:limit]
