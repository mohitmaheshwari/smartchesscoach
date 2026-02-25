"""
Pattern Context Service - Longitudinal Pattern Tracking

Provides insights like:
- "You made this same mistake in 3 other games"
- "You did this against opponent X too"
- "You FIXED this! Compare to your game vs Y"
- "This pattern is recurring - let's drill it"

The golden information that makes coaching real.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import Counter, defaultdict


def get_threat_category(threat: str) -> str:
    """Categorize threats into broader pattern types."""
    if not threat:
        return "general"
    
    threat_lower = threat.lower()
    
    # Knight threats
    if any(x in threat_lower for x in ['knight', 'nxe', 'nxd', 'nxf', 'nxc', 'nxg', 'nxb']):
        return "knight_tactics"
    
    # Bishop threats
    if any(x in threat_lower for x in ['bishop', 'bxe', 'bxd', 'bxf', 'bxc', 'bxg', 'bxb', 'diagonal']):
        return "bishop_tactics"
    
    # Rook threats
    if any(x in threat_lower for x in ['rook', 'rxe', 'rxd', 'rxf', 'rxc', 'rxg', 'rxb', 'file', 'rank']):
        return "rook_tactics"
    
    # Queen threats
    if any(x in threat_lower for x in ['queen', 'qxe', 'qxd', 'qxf', 'qxc', 'qxg', 'qxb']):
        return "queen_tactics"
    
    # Pawn threats
    if any(x in threat_lower for x in ['pawn', 'push', 'advance', 'passed']):
        return "pawn_play"
    
    # King safety
    if any(x in threat_lower for x in ['check', 'king', 'castle', 'mate', 'attack']):
        return "king_safety"
    
    # Material
    if any(x in threat_lower for x in ['win', 'capture', 'take', 'fork', 'pin', 'skewer']):
        return "material_tactics"
    
    return "positional"


def extract_mistake_patterns(analysis: Dict) -> List[Dict]:
    """Extract all mistake patterns from a game analysis."""
    patterns = []
    
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    for move_eval in evals:
        eval_type = move_eval.get("evaluation")
        if eval_type not in ["blunder", "mistake"]:
            continue
        
        threat = move_eval.get("threat", "")
        category = get_threat_category(threat)
        
        patterns.append({
            "move_number": move_eval.get("move_number"),
            "move": move_eval.get("move"),
            "best_move": move_eval.get("best_move"),
            "threat": threat,
            "category": category,
            "eval_type": eval_type,
            "cp_loss": move_eval.get("cp_loss", 0),
            "fen": move_eval.get("fen_before"),
        })
    
    return patterns


def build_pattern_history(user_id: str, all_analyses: List[Dict], all_games: List[Dict]) -> Dict:
    """
    Build a comprehensive pattern history for a user.
    
    Returns:
        {
            "patterns": {
                "knight_tactics": {
                    "total_occurrences": 15,
                    "games": [{"game_id": ..., "opponent": ..., "instances": [...]}],
                    "trend": "improving" | "stable" | "recurring",
                    "last_5_games": 2,  # How many in last 5 games
                }
            },
            "most_recurring": "knight_tactics",
            "improving_patterns": ["bishop_tactics"],
            "fixed_patterns": ["pawn_play"],
        }
    """
    # Build games lookup
    games_lookup = {g.get("game_id"): g for g in all_games}
    
    # Track patterns across all games
    pattern_data = defaultdict(lambda: {
        "total_occurrences": 0,
        "games": [],
        "timeline": [],  # (date, count) for trend
    })
    
    # Helper to parse date
    def get_sortable_date(analysis):
        created = analysis.get("created_at")
        if created is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(created, str):
            try:
                return datetime.fromisoformat(created.replace('Z', '+00:00'))
            except:
                return datetime.min.replace(tzinfo=timezone.utc)
        return created if created.tzinfo else created.replace(tzinfo=timezone.utc)
    
    # Process all analyses chronologically
    sorted_analyses = sorted(all_analyses, key=get_sortable_date)
    
    for analysis in sorted_analyses:
        game_id = analysis.get("game_id")
        game_info = games_lookup.get(game_id, {})
        
        user_color = game_info.get("user_color", "white")
        opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
        result = game_info.get("result", "")
        created_at = analysis.get("created_at")
        
        # Extract patterns from this game
        patterns = extract_mistake_patterns(analysis)
        
        # Group by category
        game_patterns = defaultdict(list)
        for p in patterns:
            game_patterns[p["category"]].append(p)
        
        # Add to pattern history
        for category, instances in game_patterns.items():
            pattern_data[category]["total_occurrences"] += len(instances)
            pattern_data[category]["games"].append({
                "game_id": game_id,
                "opponent": opponent or "Opponent",
                "result": result,
                "instances": instances,
                "date": created_at,
            })
            pattern_data[category]["timeline"].append({
                "date": created_at,
                "count": len(instances),
                "game_id": game_id,
            })
    
    # Calculate trends for each pattern
    for category, data in pattern_data.items():
        timeline = data["timeline"]
        if len(timeline) >= 5:
            # Compare last 5 games to previous 5
            recent = sum(t["count"] for t in timeline[-5:])
            previous = sum(t["count"] for t in timeline[-10:-5]) if len(timeline) >= 10 else sum(t["count"] for t in timeline[:-5])
            
            if recent == 0 and previous > 0:
                data["trend"] = "fixed"
            elif recent < previous * 0.5:
                data["trend"] = "improving"
            elif recent > previous * 1.5:
                data["trend"] = "recurring"
            else:
                data["trend"] = "stable"
            
            data["last_5_games"] = recent
        else:
            data["trend"] = "not_enough_data"
            data["last_5_games"] = sum(t["count"] for t in timeline)
    
    # Find most recurring and improving patterns
    most_recurring = max(pattern_data.items(), key=lambda x: x[1]["total_occurrences"])[0] if pattern_data else None
    improving = [cat for cat, data in pattern_data.items() if data.get("trend") == "improving"]
    fixed = [cat for cat, data in pattern_data.items() if data.get("trend") == "fixed"]
    
    return {
        "patterns": dict(pattern_data),
        "most_recurring": most_recurring,
        "improving_patterns": improving,
        "fixed_patterns": fixed,
    }


def get_pattern_context_for_mistake(
    mistake: Dict,
    current_game_id: str,
    pattern_history: Dict,
    all_games: List[Dict]
) -> Dict:
    """
    Get contextual insights for a specific mistake.
    
    Returns:
        {
            "is_recurring": True,
            "recurrence_count": 5,
            "other_games": [{"game_id": ..., "opponent": ..., "result": ...}],
            "trend": "improving" | "recurring" | "fixed",
            "coach_insight": "You've made this same mistake against 3 other opponents...",
            "improvement_example": {"game_id": ..., "opponent": ...} | None,
        }
    """
    category = mistake.get("category") or get_threat_category(mistake.get("threat", ""))
    
    pattern_info = pattern_history.get("patterns", {}).get(category, {})
    
    if not pattern_info:
        return {
            "is_recurring": False,
            "recurrence_count": 0,
            "other_games": [],
            "trend": "new",
            "coach_insight": None,
            "improvement_example": None,
        }
    
    # Build games lookup
    games_lookup = {g.get("game_id"): g for g in all_games}
    
    # Get other games with this pattern (excluding current)
    other_games = [
        {
            "game_id": g["game_id"],
            "opponent": g["opponent"],
            "result": g["result"],
            "date": g.get("date"),
            "instance_count": len(g["instances"]),
        }
        for g in pattern_info.get("games", [])
        if g["game_id"] != current_game_id
    ]
    
    # Sort by date, most recent first
    other_games.sort(key=lambda x: x.get("date") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    total_occurrences = pattern_info.get("total_occurrences", 0)
    trend = pattern_info.get("trend", "stable")
    
    # Generate coach insight
    coach_insight = generate_pattern_insight(
        category=category,
        total_occurrences=total_occurrences,
        other_games=other_games[:5],
        trend=trend,
    )
    
    # Find improvement example if trend is improving
    improvement_example = None
    if trend == "improving" and len(other_games) >= 2:
        # Find a game where the pattern appeared but user did better overall
        for game in other_games:
            game_info = games_lookup.get(game["game_id"], {})
            result = game_info.get("result", "")
            user_color = game_info.get("user_color", "white")
            is_win = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
            if is_win:
                improvement_example = game
                break
    
    return {
        "is_recurring": total_occurrences > 1,
        "recurrence_count": total_occurrences,
        "other_games": other_games[:5],
        "trend": trend,
        "coach_insight": coach_insight,
        "improvement_example": improvement_example,
    }


def generate_pattern_insight(category: str, total_occurrences: int, other_games: List[Dict], trend: str) -> str:
    """Generate a coach insight message for a pattern."""
    
    category_labels = {
        "knight_tactics": "knight threats",
        "bishop_tactics": "bishop attacks",
        "rook_tactics": "rook play",
        "queen_tactics": "queen threats",
        "pawn_play": "pawn moves",
        "king_safety": "king safety",
        "material_tactics": "material calculation",
        "positional": "positional play",
        "general": "this type of position",
    }
    
    label = category_labels.get(category, category)
    
    if total_occurrences <= 1:
        return None
    
    if trend == "fixed":
        return f"Good news! You used to struggle with {label}, but you've fixed this pattern."
    
    if trend == "improving":
        return f"You're getting better at {label}. This appeared in {total_occurrences} games but less frequently now."
    
    if trend == "recurring":
        opponents = [g["opponent"] for g in other_games[:3]]
        if len(opponents) >= 2:
            return f"Pattern alert: You've missed {label} against {', '.join(opponents[:2])} and {total_occurrences - 2} other games. This needs work."
        return f"This pattern keeps appearing. You've made similar mistakes with {label} in {total_occurrences} games."
    
    # Stable
    if len(other_games) >= 1:
        recent_opponent = other_games[0]["opponent"]
        return f"You've seen this before - same issue vs {recent_opponent}. {label.capitalize()} continues to be a weak spot."
    
    return f"You've encountered {label} issues in {total_occurrences} games."


def get_game_pattern_summary(
    analysis: Dict,
    pattern_history: Dict,
    all_games: List[Dict]
) -> Dict:
    """
    Get a summary of patterns for an entire game with context.
    
    Returns:
        {
            "dominant_pattern": "knight_tactics",
            "patterns_in_game": ["knight_tactics", "king_safety"],
            "recurring_patterns": [{"category": ..., "count": ..., "insight": ...}],
            "new_patterns": [...],
            "coach_summary": "This game shows your recurring struggle with knight threats..."
        }
    """
    game_id = analysis.get("game_id")
    mistakes = extract_mistake_patterns(analysis)
    
    if not mistakes:
        return {
            "dominant_pattern": None,
            "patterns_in_game": [],
            "recurring_patterns": [],
            "new_patterns": [],
            "coach_summary": "Clean game! No significant patterns to address.",
        }
    
    # Group mistakes by category
    category_counts = Counter(m["category"] for m in mistakes)
    dominant = category_counts.most_common(1)[0][0] if category_counts else None
    
    # Get context for each pattern
    recurring = []
    new_patterns = []
    
    for category, count in category_counts.items():
        pattern_info = pattern_history.get("patterns", {}).get(category, {})
        total = pattern_info.get("total_occurrences", count)
        
        if total > count:
            # This pattern existed before this game
            recurring.append({
                "category": category,
                "count_this_game": count,
                "total_occurrences": total,
                "trend": pattern_info.get("trend", "stable"),
                "insight": generate_pattern_insight(
                    category, total,
                    [g for g in pattern_info.get("games", []) if g["game_id"] != game_id][:3],
                    pattern_info.get("trend", "stable")
                ),
            })
        else:
            new_patterns.append({
                "category": category,
                "count": count,
            })
    
    # Generate overall summary
    if recurring:
        main_recurring = max(recurring, key=lambda x: x["total_occurrences"])
        coach_summary = f"This game shows your recurring pattern: {main_recurring['category'].replace('_', ' ')}. "
        if main_recurring["trend"] == "improving":
            coach_summary += "Good news - you're getting better at this."
        elif main_recurring["trend"] == "recurring":
            coach_summary += "This keeps appearing. Consider focused training on this."
    else:
        coach_summary = "These are new patterns. Let's see if they repeat in future games."
    
    return {
        "dominant_pattern": dominant,
        "patterns_in_game": list(category_counts.keys()),
        "recurring_patterns": recurring,
        "new_patterns": new_patterns,
        "coach_summary": coach_summary,
    }
