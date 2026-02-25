"""
SMART Pattern Context Service - Specific, Contextual Insights

Provides SPECIFIC insights mapped to:
- Player rating context (vs higher/lower rated, rating trends)
- Opening context (which openings trigger this mistake)
- Time control context (blitz vs rapid patterns)
- Win/loss correlation (when does this hurt most?)
- Phase context (opening/middlegame/endgame)

NO VAGUE LABELS like "positional" - everything is concrete and actionable.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import Counter, defaultdict
import re


# ============ SPECIFIC PATTERN DETECTION ============

def get_specific_mistake_type(move_eval: Dict) -> Dict:
    """
    Detect SPECIFIC mistake type from move evaluation.
    Returns a structured pattern with actionable details.
    """
    move = move_eval.get("move", "")
    best_move = move_eval.get("best_move", "")
    threat = move_eval.get("threat", "")
    cp_loss = abs(move_eval.get("cp_loss", 0))
    phase = move_eval.get("phase", "middlegame")
    eval_before = move_eval.get("eval_before", 0)
    eval_after = move_eval.get("eval_after", 0)
    
    # Check for specific tactical patterns
    pattern = {
        "type": "general_mistake",
        "specific_label": "Inaccurate move",
        "piece_involved": None,
        "tactical_theme": None,
        "severity": "medium" if cp_loss < 200 else "high" if cp_loss < 400 else "critical",
    }
    
    # Detect piece involved from move notation
    if move:
        move_upper = move.upper()
        if move_upper.startswith('K') and not move_upper.startswith('KN'):
            pattern["piece_involved"] = "king"
        elif move_upper.startswith('Q'):
            pattern["piece_involved"] = "queen"
        elif move_upper.startswith('R'):
            pattern["piece_involved"] = "rook"
        elif move_upper.startswith('B'):
            pattern["piece_involved"] = "bishop"
        elif move_upper.startswith('N'):
            pattern["piece_involved"] = "knight"
        elif move[0].islower() or 'x' in move.lower()[:2]:
            pattern["piece_involved"] = "pawn"
    
    # Detect tactical themes from threat
    threat_lower = (threat or "").lower()
    
    if "mate" in threat_lower or "checkmate" in threat_lower:
        pattern["type"] = "missed_checkmate_threat"
        pattern["specific_label"] = "Missed checkmate threat"
        pattern["tactical_theme"] = "checkmate"
    elif "fork" in threat_lower:
        pattern["type"] = "allowed_fork"
        pattern["specific_label"] = "Allowed a fork"
        pattern["tactical_theme"] = "fork"
    elif "pin" in threat_lower:
        pattern["type"] = "allowed_pin"
        pattern["specific_label"] = "Allowed a pin"
        pattern["tactical_theme"] = "pin"
    elif "skewer" in threat_lower:
        pattern["type"] = "allowed_skewer"
        pattern["specific_label"] = "Allowed a skewer"
        pattern["tactical_theme"] = "skewer"
    elif any(x in threat_lower for x in ["hanging", "undefended", "loose"]):
        pattern["type"] = "left_piece_hanging"
        pattern["specific_label"] = f"Left {pattern['piece_involved'] or 'piece'} hanging"
        pattern["tactical_theme"] = "hanging_piece"
    elif any(x in threat_lower for x in ["back rank", "backrank"]):
        pattern["type"] = "back_rank_weakness"
        pattern["specific_label"] = "Back rank weakness"
        pattern["tactical_theme"] = "back_rank"
    elif any(x in threat_lower for x in ["discovery", "discovered"]):
        pattern["type"] = "allowed_discovered_attack"
        pattern["specific_label"] = "Allowed discovered attack"
        pattern["tactical_theme"] = "discovered_attack"
    elif "x" in move.lower() and cp_loss > 150:
        # Bad capture
        pattern["type"] = "bad_exchange"
        pattern["specific_label"] = "Lost material in exchange"
        pattern["tactical_theme"] = "exchange"
    elif phase == "opening" and cp_loss > 100:
        pattern["type"] = "opening_mistake"
        pattern["specific_label"] = "Opening inaccuracy"
        pattern["tactical_theme"] = "opening"
    elif phase == "endgame":
        pattern["type"] = "endgame_mistake"
        pattern["specific_label"] = "Endgame technique error"
        pattern["tactical_theme"] = "endgame"
    
    # Position context: Was user winning, equal, or losing?
    if eval_before > 150:
        pattern["position_context"] = "winning"
    elif eval_before < -150:
        pattern["position_context"] = "losing"
    else:
        pattern["position_context"] = "equal"
    
    return pattern


def get_threat_category(threat: str) -> str:
    """Categorize threats into specific pattern types - LEGACY for compatibility."""
    if not threat:
        return "general"
    
    threat_lower = threat.lower()
    
    # More specific categorizations
    if "mate" in threat_lower:
        return "checkmate_threats"
    if "fork" in threat_lower:
        return "fork_vulnerability"
    if "pin" in threat_lower:
        return "pin_vulnerability"  
    if "hanging" in threat_lower or "undefended" in threat_lower:
        return "hanging_pieces"
    if "back rank" in threat_lower:
        return "back_rank_weakness"
    if any(x in threat_lower for x in ['knight', 'nxe', 'nxd', 'nxf']):
        return "knight_tactics"
    if any(x in threat_lower for x in ['bishop', 'bxe', 'diagonal']):
        return "bishop_tactics"
    if any(x in threat_lower for x in ['rook', 'file', 'rank']):
        return "rook_tactics"
    if any(x in threat_lower for x in ['queen']):
        return "queen_tactics"
    if any(x in threat_lower for x in ['pawn', 'push']):
        return "pawn_play"
    if any(x in threat_lower for x in ['check', 'king', 'castle']):
        return "king_safety"
    
    return "positional"


def extract_mistake_patterns(analysis: Dict, game_info: Optional[Dict] = None) -> List[Dict]:
    """
    Extract SPECIFIC mistake patterns from a game analysis.
    Includes game context (opening, time control, opponent rating).
    """
    patterns = []
    
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    
    # Get game context
    opening = None
    time_control = None
    opponent_rating = None
    user_rating = None
    
    if game_info:
        # Extract opening from various possible fields
        opening = game_info.get("opening_name") or game_info.get("opening") or game_info.get("eco")
        time_control = game_info.get("time_control") or ""
        
        # Get ratings
        user_color = game_info.get("user_color", "white")
        if user_color == "white":
            user_rating = game_info.get("white_rating")
            opponent_rating = game_info.get("black_rating")
        else:
            user_rating = game_info.get("black_rating")
            opponent_rating = game_info.get("white_rating")
    
    # Classify time control
    time_category = "classical"
    if time_control:
        tc_str = str(time_control).lower()
        if any(x in tc_str for x in ["bullet", "60", "120"]) or (tc_str.isdigit() and int(tc_str) <= 120):
            time_category = "bullet"
        elif any(x in tc_str for x in ["blitz", "180", "300", "3|", "5|"]):
            time_category = "blitz"
        elif any(x in tc_str for x in ["rapid", "600", "900", "10|", "15|"]):
            time_category = "rapid"
    
    for move_eval in evals:
        eval_type = move_eval.get("evaluation")
        if eval_type not in ["blunder", "mistake"]:
            continue
        
        # Get specific pattern details
        specific_pattern = get_specific_mistake_type(move_eval)
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
            # New specific fields
            "specific_type": specific_pattern["type"],
            "specific_label": specific_pattern["specific_label"],
            "piece_involved": specific_pattern.get("piece_involved"),
            "tactical_theme": specific_pattern.get("tactical_theme"),
            "position_context": specific_pattern.get("position_context"),
            # Game context
            "opening": opening,
            "time_category": time_category,
            "opponent_rating": opponent_rating,
            "user_rating": user_rating,
            "phase": move_eval.get("phase", "middlegame"),
        })
    
    return patterns


def build_pattern_history(user_id: str, all_analyses: List[Dict], all_games: List[Dict]) -> Dict:
    """
    Build a comprehensive pattern history with SPECIFIC contextual insights.
    
    Returns rich context mapped to:
    - Player rating (vs higher/lower rated opponents)
    - Openings (which openings trigger this mistake)
    - Time control (blitz vs rapid patterns)
    - Win/loss correlation
    - Position context (when winning/equal/losing)
    
    Returns:
        {
            "patterns": {
                "hanging_pieces": {
                    "total_occurrences": 15,
                    "games": [...],
                    "trend": "improving" | "stable" | "recurring",
                    "rating_context": {
                        "vs_higher_rated": {"count": 5, "pct": 33},
                        "vs_lower_rated": {"count": 8, "pct": 53},
                        "vs_equal_rated": {"count": 2, "pct": 14},
                    },
                    "opening_context": {
                        "top_openings": [{"name": "Italian Game", "count": 4}]
                    },
                    "time_context": {
                        "blitz": 8, "rapid": 5, "bullet": 2
                    },
                    "position_context": {
                        "when_winning": 6, "when_equal": 4, "when_losing": 5
                    },
                    "outcome_impact": {
                        "led_to_loss": 10, "still_won": 3, "drew": 2
                    }
                }
            },
            "most_recurring": "hanging_pieces",
            "rating_vulnerable": {
                "pattern": "You make more mistakes vs lower-rated opponents",
                "detail": "60% of your blunders happen against players rated below you"
            },
            "time_vulnerable": "blitz",
            "opening_triggers": ["Italian Game", "Sicilian Defense"]
        }
    """
    # Build games lookup with full data
    games_lookup = {}
    for g in all_games:
        game_id = g.get("game_id")
        if game_id:
            games_lookup[game_id] = g
    
    # Track patterns across all games with rich context
    pattern_data = defaultdict(lambda: {
        "total_occurrences": 0,
        "games": [],
        "timeline": [],
        "rating_deltas": [],  # (opponent_rating - user_rating) for each occurrence
        "openings": [],
        "time_controls": [],
        "position_contexts": [],  # winning/equal/losing
        "outcomes": [],  # win/loss/draw
        "specific_types": [],  # Detailed pattern types
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
        
        # Get opponent info
        user_color = game_info.get("user_color", "white")
        opponent = game_info.get("opponent_name")
        if not opponent:
            opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
        
        # Get ratings
        if user_color == "white":
            user_rating = game_info.get("white_rating")
            opponent_rating = game_info.get("black_rating")
        else:
            user_rating = game_info.get("black_rating")
            opponent_rating = game_info.get("white_rating")
        
        # Calculate rating delta
        rating_delta = None
        if user_rating and opponent_rating:
            try:
                rating_delta = int(opponent_rating) - int(user_rating)
            except:
                pass
        
        # Get result
        result = game_info.get("result", "")
        user_won = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
        user_lost = (result == "0-1" and user_color == "white") or (result == "1-0" and user_color == "black")
        outcome = "win" if user_won else "loss" if user_lost else "draw"
        
        created_at = analysis.get("created_at")
        
        # Extract patterns with game context
        patterns = extract_mistake_patterns(analysis, game_info)
        
        # Group by category
        game_patterns = defaultdict(list)
        for p in patterns:
            game_patterns[p["category"]].append(p)
        
        # Add to pattern history with full context
        for category, instances in game_patterns.items():
            pattern_data[category]["total_occurrences"] += len(instances)
            pattern_data[category]["games"].append({
                "game_id": game_id,
                "opponent": opponent or "Opponent",
                "opponent_rating": opponent_rating,
                "result": result,
                "outcome": outcome,
                "instances": instances,
                "date": created_at,
            })
            pattern_data[category]["timeline"].append({
                "date": created_at,
                "count": len(instances),
                "game_id": game_id,
            })
            
            # Track rating context
            if rating_delta is not None:
                pattern_data[category]["rating_deltas"].extend([rating_delta] * len(instances))
            
            # Track opening
            for inst in instances:
                if inst.get("opening"):
                    pattern_data[category]["openings"].append(inst["opening"])
                if inst.get("time_category"):
                    pattern_data[category]["time_controls"].append(inst["time_category"])
                if inst.get("position_context"):
                    pattern_data[category]["position_contexts"].append(inst["position_context"])
                if inst.get("specific_type"):
                    pattern_data[category]["specific_types"].append(inst["specific_type"])
            
            pattern_data[category]["outcomes"].extend([outcome] * len(instances))
    
    # Calculate derived insights for each pattern
    for category, data in pattern_data.items():
        timeline = data["timeline"]
        
        # Trend calculation
        if len(timeline) >= 5:
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
        
        # Rating context analysis
        deltas = data["rating_deltas"]
        if deltas:
            vs_higher = len([d for d in deltas if d > 50])
            vs_lower = len([d for d in deltas if d < -50])
            vs_equal = len(deltas) - vs_higher - vs_lower
            total = len(deltas)
            
            data["rating_context"] = {
                "vs_higher_rated": {"count": vs_higher, "pct": round(vs_higher * 100 / total) if total else 0},
                "vs_lower_rated": {"count": vs_lower, "pct": round(vs_lower * 100 / total) if total else 0},
                "vs_equal_rated": {"count": vs_equal, "pct": round(vs_equal * 100 / total) if total else 0},
                "avg_rating_delta": round(sum(deltas) / len(deltas)) if deltas else 0,
            }
        
        # Opening context
        opening_counts = Counter(data["openings"])
        if opening_counts:
            data["opening_context"] = {
                "top_openings": [{"name": name, "count": count} for name, count in opening_counts.most_common(3)]
            }
        
        # Time control context
        time_counts = Counter(data["time_controls"])
        if time_counts:
            data["time_context"] = dict(time_counts)
        
        # Position context
        pos_counts = Counter(data["position_contexts"])
        if pos_counts:
            data["position_context"] = dict(pos_counts)
        
        # Outcome impact
        outcome_counts = Counter(data["outcomes"])
        if outcome_counts:
            data["outcome_impact"] = {
                "led_to_loss": outcome_counts.get("loss", 0),
                "still_won": outcome_counts.get("win", 0),
                "drew": outcome_counts.get("draw", 0),
            }
        
        # Specific type breakdown
        type_counts = Counter(data["specific_types"])
        if type_counts:
            data["specific_breakdown"] = [
                {"type": t, "count": c, "label": t.replace("_", " ").title()}
                for t, c in type_counts.most_common(3)
            ]
        
        # Clean up temporary tracking fields
        del data["rating_deltas"]
        del data["openings"]
        del data["time_controls"]
        del data["position_contexts"]
        del data["outcomes"]
        del data["specific_types"]
    
    # Global insights
    most_recurring = max(pattern_data.items(), key=lambda x: x[1]["total_occurrences"])[0] if pattern_data else None
    improving = [cat for cat, data in pattern_data.items() if data.get("trend") == "improving"]
    fixed = [cat for cat, data in pattern_data.items() if data.get("trend") == "fixed"]
    
    # Find vulnerable rating zone
    all_rating_deltas = []
    for cat, data in pattern_data.items():
        rc = data.get("rating_context", {})
        if rc.get("vs_lower_rated", {}).get("pct", 0) > 50:
            all_rating_deltas.append(("lower", rc["vs_lower_rated"]["pct"]))
        elif rc.get("vs_higher_rated", {}).get("pct", 0) > 50:
            all_rating_deltas.append(("higher", rc["vs_higher_rated"]["pct"]))
    
    rating_vulnerable = None
    if all_rating_deltas:
        most_common = Counter([x[0] for x in all_rating_deltas]).most_common(1)
        if most_common:
            zone = most_common[0][0]
            if zone == "lower":
                rating_vulnerable = {
                    "pattern": "You make more mistakes vs lower-rated players",
                    "detail": "Over 50% of your mistakes happen against weaker opponents - likely overconfidence"
                }
            else:
                rating_vulnerable = {
                    "pattern": "You struggle more vs higher-rated players", 
                    "detail": "Most mistakes happen against stronger opponents - focus on defense"
                }
    
    # Find time control vulnerability
    all_time_contexts = []
    for cat, data in pattern_data.items():
        tc = data.get("time_context", {})
        if tc:
            all_time_contexts.extend(list(tc.keys()) * tc.get(list(tc.keys())[0] if tc else 0, 0))
    
    time_vulnerable = Counter(all_time_contexts).most_common(1)[0][0] if all_time_contexts else None
    
    # Find opening triggers
    all_openings = []
    for cat, data in pattern_data.items():
        oc = data.get("opening_context", {}).get("top_openings", [])
        all_openings.extend([o["name"] for o in oc])
    
    opening_triggers = [name for name, count in Counter(all_openings).most_common(3)]
    
    return {
        "patterns": dict(pattern_data),
        "most_recurring": most_recurring,
        "improving_patterns": improving,
        "fixed_patterns": fixed,
        "rating_vulnerable": rating_vulnerable,
        "time_vulnerable": time_vulnerable,
        "opening_triggers": opening_triggers,
    }


def get_pattern_context_for_mistake(
    mistake: Dict,
    current_game_id: str,
    pattern_history: Dict,
    all_games: List[Dict]
) -> Dict:
    """
    Get SPECIFIC contextual insights for a mistake.
    
    Returns rich, actionable insights:
    - Rating context: "This happens more against lower-rated opponents"
    - Opening context: "You've made this in the Italian Game 3 times"
    - Time control: "80% of these are in blitz games"
    - Historical games with specific opponents
    - Improvement tracking
    
    Returns:
        {
            "is_recurring": True,
            "recurrence_count": 5,
            "other_games": [{"game_id": ..., "opponent": ..., "opponent_rating": ..., "result": ...}],
            "trend": "improving" | "recurring" | "fixed",
            "coach_insight": "You've made this same mistake against 3 other opponents...",
            "specific_insights": {
                "rating_insight": "This mostly happens vs lower-rated players (60%)",
                "opening_insight": "Most common in Italian Game (3 times)",
                "time_insight": "Happens mostly in blitz (5 of 8 times)",
                "position_insight": "You do this when winning (70%)",
            },
            "improvement_example": {"game_id": ..., "opponent": ...} | None,
            "action_recommendation": "Focus on blitz time management in Italian Game positions"
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
            "specific_insights": {},
            "improvement_example": None,
            "action_recommendation": None,
        }
    
    # Build games lookup
    games_lookup = {g.get("game_id"): g for g in all_games}
    
    # Get other games with this pattern (excluding current)
    other_games = [
        {
            "game_id": g["game_id"],
            "opponent": g["opponent"],
            "opponent_rating": g.get("opponent_rating"),
            "result": g["result"],
            "outcome": g.get("outcome", "unknown"),
            "date": g.get("date"),
            "instance_count": len(g["instances"]),
        }
        for g in pattern_info.get("games", [])
        if g["game_id"] != current_game_id
    ]
    
    # Sort by date, most recent first
    def get_sort_date(game):
        d = game.get("date")
        if d is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(d, str):
            try:
                return datetime.fromisoformat(d.replace('Z', '+00:00'))
            except:
                return datetime.min.replace(tzinfo=timezone.utc)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    
    other_games.sort(key=get_sort_date, reverse=True)
    
    total_occurrences = pattern_info.get("total_occurrences", 0)
    trend = pattern_info.get("trend", "stable")
    
    # Build SPECIFIC insights
    specific_insights = {}
    
    # Rating insight
    rc = pattern_info.get("rating_context", {})
    if rc:
        vs_lower = rc.get("vs_lower_rated", {}).get("pct", 0)
        vs_higher = rc.get("vs_higher_rated", {}).get("pct", 0)
        
        if vs_lower > 50:
            specific_insights["rating_insight"] = f"This happens more against lower-rated opponents ({vs_lower}%) - possible overconfidence"
        elif vs_higher > 50:
            specific_insights["rating_insight"] = f"This happens more against higher-rated opponents ({vs_higher}%) - under pressure"
        elif rc.get("avg_rating_delta"):
            avg_delta = rc["avg_rating_delta"]
            if avg_delta > 0:
                specific_insights["rating_insight"] = f"Average opponent when this happens is {abs(avg_delta)} points above you"
            else:
                specific_insights["rating_insight"] = f"Average opponent when this happens is {abs(avg_delta)} points below you"
    
    # Opening insight
    oc = pattern_info.get("opening_context", {})
    if oc and oc.get("top_openings"):
        top = oc["top_openings"][0]
        if top["count"] >= 2:
            specific_insights["opening_insight"] = f"Most common in {top['name']} ({top['count']} times)"
    
    # Time control insight
    tc = pattern_info.get("time_context", {})
    if tc:
        total_tc = sum(tc.values())
        for time_type, count in sorted(tc.items(), key=lambda x: -x[1]):
            if count > total_tc * 0.5:  # Majority
                specific_insights["time_insight"] = f"Happens mostly in {time_type} games ({count} of {total_tc})"
                break
    
    # Position context insight
    pc = pattern_info.get("position_context", {})
    if pc:
        total_pc = sum(pc.values())
        when_winning = pc.get("winning", 0)
        when_losing = pc.get("losing", 0)
        
        if when_winning > total_pc * 0.5:
            specific_insights["position_insight"] = f"You make this mistake mostly when winning ({round(when_winning * 100 / total_pc)}%) - possible overconfidence"
        elif when_losing > total_pc * 0.5:
            specific_insights["position_insight"] = f"You make this mistake when already losing ({round(when_losing * 100 / total_pc)}%) - desperation moves"
    
    # Outcome impact insight
    oi = pattern_info.get("outcome_impact", {})
    if oi:
        total_outcomes = oi.get("led_to_loss", 0) + oi.get("still_won", 0) + oi.get("drew", 0)
        loss_pct = round(oi.get("led_to_loss", 0) * 100 / total_outcomes) if total_outcomes else 0
        
        if loss_pct > 60:
            specific_insights["outcome_insight"] = f"This mistake led to a loss {loss_pct}% of the time - high cost pattern"
        elif oi.get("still_won", 0) > total_outcomes * 0.5:
            specific_insights["outcome_insight"] = f"You often still win despite this mistake - lucky escape pattern"
    
    # Generate coach insight with specifics
    coach_insight = generate_specific_insight(
        category=category,
        total_occurrences=total_occurrences,
        other_games=other_games[:5],
        trend=trend,
        specific_insights=specific_insights,
        pattern_info=pattern_info,
    )
    
    # Generate action recommendation
    action_recommendation = generate_action_recommendation(
        category=category,
        specific_insights=specific_insights,
        trend=trend,
    )
    
    # Find improvement example if trend is improving
    improvement_example = None
    if trend == "improving" and len(other_games) >= 2:
        for game in other_games:
            if game.get("outcome") == "win":
                improvement_example = game
                break
    
    return {
        "is_recurring": total_occurrences > 1,
        "recurrence_count": total_occurrences,
        "other_games": other_games[:5],
        "trend": trend,
        "coach_insight": coach_insight,
        "specific_insights": specific_insights,
        "improvement_example": improvement_example,
        "action_recommendation": action_recommendation,
    }


def generate_specific_insight(category: str, total_occurrences: int, other_games: List[Dict], trend: str, specific_insights: Dict, pattern_info: Dict) -> str:
    """Generate a SPECIFIC coach insight - no vague labels."""
    
    category_labels = {
        "checkmate_threats": "checkmate threats",
        "fork_vulnerability": "forks",
        "pin_vulnerability": "pins",
        "hanging_pieces": "leaving pieces undefended",
        "back_rank_weakness": "back rank issues",
        "knight_tactics": "knight threats",
        "bishop_tactics": "bishop attacks",
        "rook_tactics": "rook play",
        "queen_tactics": "queen threats",
        "pawn_play": "pawn decisions",
        "king_safety": "king safety",
        "material_tactics": "material calculation",
        "positional": "positional judgment",
        "general": "this type of position",
    }
    
    label = category_labels.get(category, category.replace("_", " "))
    
    if total_occurrences <= 1:
        return None
    
    # Build specific context
    context_parts = []
    
    # Add rating context
    if specific_insights.get("rating_insight"):
        context_parts.append(specific_insights["rating_insight"])
    
    # Add opening context
    if specific_insights.get("opening_insight"):
        context_parts.append(specific_insights["opening_insight"])
    
    # Base message based on trend
    if trend == "fixed":
        base = f"Good news! You used to struggle with {label}, but you've fixed this pattern."
    elif trend == "improving":
        base = f"You're getting better at {label}. This appeared {total_occurrences} times but is decreasing."
    elif trend == "recurring":
        # Include specific opponents with ratings
        opponent_details = []
        for g in other_games[:3]:
            opp = g.get("opponent", "Unknown")
            rating = g.get("opponent_rating")
            if rating:
                opponent_details.append(f"{opp} ({rating})")
            else:
                opponent_details.append(opp)
        
        if opponent_details:
            base = f"Pattern alert: {label.capitalize()} issues against {', '.join(opponent_details[:2])} and {total_occurrences - 2} other games."
        else:
            base = f"This keeps appearing. You've made similar {label} mistakes in {total_occurrences} games."
    else:
        # Stable - include most recent specific opponent
        if other_games:
            recent = other_games[0]
            opp = recent.get("opponent", "Unknown")
            rating = recent.get("opponent_rating")
            if rating:
                base = f"You've seen this before - same {label} issue vs {opp} ({rating}). "
            else:
                base = f"You've seen this before - same {label} issue vs {opp}. "
        else:
            base = f"You've encountered {label} issues in {total_occurrences} games."
    
    # Add one specific insight
    if context_parts:
        base += " " + context_parts[0]
    
    return base


def generate_action_recommendation(category: str, specific_insights: Dict, trend: str) -> str:
    """Generate actionable recommendation based on specific insights."""
    
    if trend == "fixed":
        return None  # No action needed for fixed patterns
    
    recommendations = []
    
    # Opening-specific
    if specific_insights.get("opening_insight"):
        opening = specific_insights["opening_insight"].split(" in ")[-1].split(" (")[0]
        recommendations.append(f"Study {opening} positions more carefully")
    
    # Time-specific
    if specific_insights.get("time_insight"):
        if "blitz" in specific_insights["time_insight"].lower():
            recommendations.append("Slow down in blitz - take an extra second on critical moves")
        elif "bullet" in specific_insights["time_insight"].lower():
            recommendations.append("Consider playing more rapid games to train calculation")
    
    # Position-specific
    if specific_insights.get("position_insight"):
        if "winning" in specific_insights["position_insight"].lower():
            recommendations.append("When ahead, pause and ask: 'What can go wrong here?'")
        elif "losing" in specific_insights["position_insight"].lower():
            recommendations.append("When behind, avoid desperation moves - look for solid defense first")
    
    # Rating-specific
    if specific_insights.get("rating_insight"):
        if "lower-rated" in specific_insights["rating_insight"].lower():
            recommendations.append("Play more seriously against all opponents, regardless of rating")
        elif "higher-rated" in specific_insights["rating_insight"].lower():
            recommendations.append("Against stronger players, focus on solid moves over brilliancies")
    
    # Category-specific fallbacks
    category_recommendations = {
        "hanging_pieces": "Before each move, ask: 'Is anything undefended?'",
        "fork_vulnerability": "Check for knight and pawn fork squares before moving",
        "pin_vulnerability": "Keep pieces off the same line as your king/queen",
        "back_rank_weakness": "Create a luft (escape square) before it's urgent",
        "checkmate_threats": "Always check opponent's checks, captures, and threats",
        "king_safety": "Complete castling before opening the center",
    }
    
    if not recommendations and category in category_recommendations:
        recommendations.append(category_recommendations[category])
    
    return recommendations[0] if recommendations else "Review these positions in training mode"


def get_game_pattern_summary(
    analysis: Dict,
    pattern_history: Dict,
    all_games: List[Dict],
    game_info: Optional[Dict] = None
) -> Dict:
    """
    Get a SPECIFIC summary of patterns for an entire game.
    
    Returns:
        {
            "dominant_pattern": "hanging_pieces",
            "dominant_label": "Leaving pieces undefended",
            "patterns_in_game": [...],
            "recurring_patterns": [{"category": ..., "specific_insight": ..., "action": ...}],
            "new_patterns": [...],
            "coach_summary": "This game shows...",
            "global_insights": {
                "rating_vulnerable": {...},
                "time_vulnerable": "blitz",
                "opening_triggers": ["Italian Game"]
            }
        }
    """
    game_id = analysis.get("game_id")
    
    # Find game info if not provided
    if not game_info:
        for g in all_games:
            if g.get("game_id") == game_id:
                game_info = g
                break
    
    mistakes = extract_mistake_patterns(analysis, game_info)
    
    if not mistakes:
        return {
            "dominant_pattern": None,
            "dominant_label": None,
            "patterns_in_game": [],
            "recurring_patterns": [],
            "new_patterns": [],
            "coach_summary": "Clean game! No significant patterns to address.",
            "global_insights": {},
        }
    
    # Category labels for display
    category_labels = {
        "checkmate_threats": "Missing checkmate threats",
        "fork_vulnerability": "Allowing forks",
        "pin_vulnerability": "Allowing pins",
        "hanging_pieces": "Leaving pieces undefended",
        "back_rank_weakness": "Back rank issues",
        "knight_tactics": "Knight tactical errors",
        "bishop_tactics": "Bishop tactical errors",
        "rook_tactics": "Rook play errors",
        "queen_tactics": "Queen placement errors",
        "pawn_play": "Pawn structure decisions",
        "king_safety": "King safety lapses",
        "material_tactics": "Material calculation",
        "positional": "Positional judgment",
        "general": "General decision making",
    }
    
    # Group mistakes by category
    category_counts = Counter(m["category"] for m in mistakes)
    dominant = category_counts.most_common(1)[0][0] if category_counts else None
    dominant_label = category_labels.get(dominant, dominant.replace("_", " ").title()) if dominant else None
    
    # Get context for each pattern
    recurring = []
    new_patterns = []
    
    for category, count in category_counts.items():
        pattern_info = pattern_history.get("patterns", {}).get(category, {})
        total = pattern_info.get("total_occurrences", count)
        
        label = category_labels.get(category, category.replace("_", " ").title())
        
        if total > count:
            # This pattern existed before this game
            specific_insights = {}
            
            # Build specific insights from pattern info
            rc = pattern_info.get("rating_context", {})
            if rc.get("vs_lower_rated", {}).get("pct", 0) > 50:
                specific_insights["rating"] = f"Happens more vs weaker opponents ({rc['vs_lower_rated']['pct']}%)"
            elif rc.get("vs_higher_rated", {}).get("pct", 0) > 50:
                specific_insights["rating"] = f"Happens more vs stronger opponents ({rc['vs_higher_rated']['pct']}%)"
            
            oc = pattern_info.get("opening_context", {})
            if oc and oc.get("top_openings"):
                top = oc["top_openings"][0]
                if top["count"] >= 2:
                    specific_insights["opening"] = f"Common in {top['name']}"
            
            tc = pattern_info.get("time_context", {})
            if tc:
                top_time = max(tc.items(), key=lambda x: x[1])
                if top_time[1] > sum(tc.values()) * 0.5:
                    specific_insights["time"] = f"Mostly in {top_time[0]} games"
            
            # Action recommendation
            action = generate_action_recommendation(
                category=category,
                specific_insights={
                    "rating_insight": specific_insights.get("rating"),
                    "opening_insight": specific_insights.get("opening"),
                    "time_insight": specific_insights.get("time"),
                },
                trend=pattern_info.get("trend", "stable")
            )
            
            recurring.append({
                "category": category,
                "label": label,
                "count_this_game": count,
                "total_occurrences": total,
                "trend": pattern_info.get("trend", "stable"),
                "specific_insights": specific_insights,
                "action": action,
                "insight": generate_specific_insight(
                    category, total,
                    [g for g in pattern_info.get("games", []) if g["game_id"] != game_id][:3],
                    pattern_info.get("trend", "stable"),
                    specific_insights,
                    pattern_info
                ),
            })
        else:
            new_patterns.append({
                "category": category,
                "label": label,
                "count": count,
            })
    
    # Generate overall summary
    if recurring:
        main_recurring = max(recurring, key=lambda x: x["total_occurrences"])
        coach_summary = f"This game shows your recurring pattern: {main_recurring['label'].lower()}. "
        
        if main_recurring["trend"] == "improving":
            coach_summary += "Good news - you're getting better at this."
        elif main_recurring["trend"] == "recurring":
            coach_summary += "This keeps appearing. Consider focused training."
            # Add specific context
            if main_recurring.get("specific_insights"):
                si = main_recurring["specific_insights"]
                if si.get("rating"):
                    coach_summary += f" Note: {si['rating'].lower()}."
                elif si.get("opening"):
                    coach_summary += f" Note: {si['opening'].lower()}."
        elif main_recurring["trend"] == "fixed":
            coach_summary = f"You've been working on {main_recurring['label'].lower()} - it's improving!"
    else:
        coach_summary = "These are new patterns. Let's see if they repeat in future games."
    
    # Global insights from pattern history
    global_insights = {
        "rating_vulnerable": pattern_history.get("rating_vulnerable"),
        "time_vulnerable": pattern_history.get("time_vulnerable"),
        "opening_triggers": pattern_history.get("opening_triggers", []),
    }
    
    return {
        "dominant_pattern": dominant,
        "dominant_label": dominant_label,
        "patterns_in_game": list(category_counts.keys()),
        "recurring_patterns": recurring,
        "new_patterns": new_patterns,
        "coach_summary": coach_summary,
        "global_insights": global_insights,
    }
