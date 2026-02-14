"""
Adaptive Performance Coach Service
==================================

This is the GM-style performance briefing system for the Focus page.

Core Philosophy:
- Stage-aware: Coaching adapts to rating band (600-1000, 1000-1600, 1600-2000, 2000+)
- Behavioral: Focus on thinking patterns, not just move mistakes  
- Deterministic: All computations are rule-based, no LLM required
- Plan-centric: Each game is audited against the previous plan
- Adaptive: Plan intensity adjusts based on compliance

The 4 Sections:
1. Coach Diagnosis - Your Current Growth Priority (ONE primary leak)
2. Round Preparation - Next Game Plan (5 domains)
3. Plan Audit - Last Game Execution Review (audit vs plan)
4. Skill Signals - Live Performance Monitoring (trends)

Rating Bands:
- 600-1000: Focus on Hanging Pieces
- 1000-1600: Focus on Tactical Awareness
- 1600-2000: Focus on Advantage Discipline
- 2000+: Focus on Conversion Precision
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

# Starting FEN position
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# =============================================================================
# RATING BAND DEFINITIONS
# =============================================================================

RATING_BANDS = {
    "beginner": {
        "min": 0, "max": 999, 
        "label": "600-1000",
        "primary_focus": "hanging_pieces",
        "secondary_focus": "early_development",
        "tactical_protocol": "Check if any piece is hanging.",
        "middlegame_rule": "Don't move a piece unless it's safe on the new square.",
    },
    "club": {
        "min": 1000, "max": 1599,
        "label": "1000-1600", 
        "primary_focus": "tactical_awareness",
        "secondary_focus": "advantage_discipline",
        "tactical_protocol": "Checks, captures, threats every move.",
        "middlegame_rule": "When ahead, simplify. When equal, improve worst piece.",
    },
    "intermediate": {
        "min": 1600, "max": 1999,
        "label": "1600-2000",
        "primary_focus": "advantage_discipline",
        "secondary_focus": "positional_decisions",
        "tactical_protocol": "Calculate 2 moves deeper in sharp positions.",
        "middlegame_rule": "Before creating threats, ensure all pieces are coordinated.",
    },
    "advanced": {
        "min": 2000, "max": 9999,
        "label": "2000+",
        "primary_focus": "conversion_precision",
        "secondary_focus": "strategic_imbalances",
        "tactical_protocol": "Evaluate structural trade consequences before exchanging.",
        "middlegame_rule": "In winning positions, calculate concrete variations to conversion.",
    },
}


def get_rating_band(rating: int) -> Dict:
    """Get the rating band for a given rating."""
    for band_name, band_data in RATING_BANDS.items():
        if band_data["min"] <= rating <= band_data["max"]:
            return {"name": band_name, **band_data}
    return {"name": "beginner", **RATING_BANDS["beginner"]}


# =============================================================================
# LEAK DEFINITIONS BY RATING BAND
# =============================================================================

LEAKS_BY_BAND = {
    "beginner": {
        "primary": {
            "id": "hanging_pieces",
            "label": "Hanging Pieces",
            "explanation": "You are losing rating due to pieces being captured for free.",
            "board_example_pattern": "piece_left_undefended",
        },
        "secondary": {
            "id": "early_development",
            "label": "Early Development Delay",
            "explanation": "You often delay piece development, leaving pieces on starting squares too long.",
            "board_example_pattern": "slow_development",
        },
    },
    "club": {
        "primary": {
            "id": "tactical_awareness",
            "label": "Tactical Awareness",
            "explanation": "You are missing tactical patterns that lose material or advantages.",
            "board_example_pattern": "missed_tactic",
        },
        "secondary": {
            "id": "advantage_discipline", 
            "label": "Advantage Discipline",
            "explanation": "When ahead, you're giving back the advantage instead of converting.",
            "board_example_pattern": "advantage_collapse",
        },
    },
    "intermediate": {
        "primary": {
            "id": "advantage_discipline",
            "label": "Advantage Stability",
            "explanation": "You are losing rating due to advantage instability, not opening knowledge.",
            "board_example_pattern": "advantage_collapse",
        },
        "secondary": {
            "id": "positional_decisions",
            "label": "Positional Decision-Making",
            "explanation": "Piece placement choices are costing you long-term advantages.",
            "board_example_pattern": "poor_piece_placement",
        },
    },
    "advanced": {
        "primary": {
            "id": "conversion_precision",
            "label": "Conversion Precision",
            "explanation": "Converting winning positions requires more concrete calculation.",
            "board_example_pattern": "conversion_failure",
        },
        "secondary": {
            "id": "strategic_imbalances",
            "label": "Strategic Imbalances",
            "explanation": "Understanding when to create vs. resolve strategic tension.",
            "board_example_pattern": "strategic_error",
        },
    },
}


# =============================================================================
# DETERMINISTIC ENGINES
# =============================================================================

def compute_hanging_piece_frequency(analyses: List[Dict], rating_band: str) -> Dict:
    """
    Compute how often the user hangs pieces (cp_loss >= 300).
    
    Returns:
    - rate: Float (0-1) representing frequency
    - count: Number of games with hanging pieces
    - total: Total games analyzed
    - example_positions: List of FENs where pieces were hung
    """
    if not analyses:
        return {"rate": 0, "count": 0, "total": 0, "example_positions": [], "trend": "unknown"}
    
    count = 0
    example_positions = []
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            if cp_loss >= 300:
                count += 1
                if m.get("fen_before") and len(example_positions) < 5:
                    example_positions.append({
                        "fen": m.get("fen_before"),
                        "move": m.get("move"),
                        "cp_loss": cp_loss,
                        "game_id": a.get("game_id"),
                        "move_number": m.get("move_number"),
                    })
                break  # Count once per game
    
    total = len(analyses)
    rate = count / total if total > 0 else 0
    
    return {
        "rate": round(rate, 3),
        "count": count,
        "total": total,
        "example_positions": example_positions,
        "trend": "stable",  # Will be computed by trend engine
    }


def compute_tactical_miss_rate(analyses: List[Dict], rating_band: str) -> Dict:
    """
    Compute blunder/mistake rate per game.
    
    Returns:
    - blunders_per_game: Average blunders
    - mistakes_per_game: Average mistakes
    - example_positions: Positions where tactics were missed
    """
    if not analyses:
        return {"blunders_per_game": 0, "mistakes_per_game": 0, "example_positions": [], "trend": "unknown"}
    
    total_blunders = 0
    total_mistakes = 0
    example_positions = []
    
    for a in analyses:
        total_blunders += a.get("blunders", 0)
        total_mistakes += a.get("mistakes", 0)
        
        # Get example positions
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            eval_type = m.get("evaluation", "")
            if hasattr(eval_type, "value"):
                eval_type = eval_type.value
            
            if eval_type == "blunder" and len(example_positions) < 5:
                example_positions.append({
                    "fen": m.get("fen_before", START_FEN),
                    "move": m.get("move"),
                    "best_move": m.get("best_move"),
                    "cp_loss": m.get("cp_loss", 0),
                    "game_id": a.get("game_id"),
                    "move_number": m.get("move_number"),
                })
    
    n = len(analyses)
    
    return {
        "blunders_per_game": round(total_blunders / n, 2) if n > 0 else 0,
        "mistakes_per_game": round(total_mistakes / n, 2) if n > 0 else 0,
        "example_positions": example_positions,
        "trend": "stable",
    }


def compute_advantage_collapse_rate(analyses: List[Dict], rating_band: str) -> Dict:
    """
    Compute how often user collapses from winning positions.
    
    Winning = eval >= +150 cp (1.5 pawns)
    Collapse = cp_loss >= 150 while winning
    """
    if not analyses:
        return {"rate": 0, "count": 0, "total_winning_games": 0, "example_positions": [], "trend": "unknown"}
    
    collapse_count = 0
    winning_games = 0
    example_positions = []
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        had_winning_position = False
        collapsed = False
        collapse_position = None
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            cp_loss = m.get("cp_loss", 0)
            
            if eval_before >= 150:  # We're winning
                had_winning_position = True
                if cp_loss >= 150:  # Big mistake while winning
                    collapsed = True
                    collapse_position = {
                        "fen": m.get("fen_before", START_FEN),
                        "move": m.get("move"),
                        "eval_before": eval_before,
                        "cp_loss": cp_loss,
                        "game_id": a.get("game_id"),
                        "move_number": m.get("move_number"),
                    }
                    break
        
        if had_winning_position:
            winning_games += 1
            if collapsed:
                collapse_count += 1
                if collapse_position and len(example_positions) < 5:
                    example_positions.append(collapse_position)
    
    rate = collapse_count / winning_games if winning_games > 0 else 0
    
    return {
        "rate": round(rate, 3),
        "count": collapse_count,
        "total_winning_games": winning_games,
        "example_positions": example_positions,
        "trend": "stable",
    }


def compute_opening_stability(analyses: List[Dict], games: List[Dict], rating_band: str) -> Dict:
    """
    Compute opening stability score (0-100).
    
    Stability = Low eval volatility in moves 1-10
    High stability = Stick to familiar systems
    """
    if not analyses:
        return {"score": 50, "best_opening_white": None, "best_opening_black": None, "recommendation": None}
    
    # Build analysis map
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    opening_stats_white = {}
    opening_stats_black = {}
    
    for game in games:
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id)
        if not analysis:
            continue
        
        user_color = game.get("user_color", "white")
        opening = _extract_opening_family(game)
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
        
        if not early_moves:
            continue
        
        # Calculate stability for this game
        max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
        avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
        
        stability = 100
        stability -= min(30, max_drop / 10)
        stability -= min(20, avg_cp)
        stability = max(0, stability)
        
        target = opening_stats_white if user_color == "white" else opening_stats_black
        if opening not in target:
            target[opening] = {"scores": [], "games": 0, "name": opening}
        target[opening]["scores"].append(stability)
        target[opening]["games"] += 1
    
    # Find best openings
    best_white = None
    best_white_score = 0
    for name, data in opening_stats_white.items():
        if data["games"] >= 3:
            avg = sum(data["scores"]) / len(data["scores"])
            if avg > best_white_score:
                best_white_score = avg
                best_white = {"name": name, "stability": round(avg), "games": data["games"]}
    
    best_black = None
    best_black_score = 0
    for name, data in opening_stats_black.items():
        if data["games"] >= 3:
            avg = sum(data["scores"]) / len(data["scores"])
            if avg > best_black_score:
                best_black_score = avg
                best_black = {"name": name, "stability": round(avg), "games": data["games"]}
    
    # Overall stability score
    all_scores = []
    for data in list(opening_stats_white.values()) + list(opening_stats_black.values()):
        all_scores.extend(data["scores"])
    
    overall_score = sum(all_scores) / len(all_scores) if all_scores else 50
    
    return {
        "score": round(overall_score),
        "best_opening_white": best_white,
        "best_opening_black": best_black,
        "recommendation": best_white.get("name") if best_white else None,
    }


def compute_endgame_conversion_rate(analyses: List[Dict], games: List[Dict], rating_band: str) -> Dict:
    """
    Compute endgame conversion rate.
    
    If user enters endgame with advantage (eval >= 150), did they win?
    """
    if not analyses or not games:
        return {"rate": 0, "converted": 0, "total_advantaged_endgames": 0, "trend": "unknown"}
    
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    converted = 0
    total_advantaged_endgames = 0
    
    for game in games:
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id)
        if not analysis:
            continue
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Endgame = after move 60 (30 per side)
        endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
        
        if len(endgame_moves) >= 3:
            first_eg_eval = endgame_moves[0].get("eval_before", 0)
            
            if first_eg_eval >= 150:  # Had winning endgame
                total_advantaged_endgames += 1
                
                # Check result
                result = game.get("result", "")
                user_color = game.get("user_color", "white")
                won = (user_color == "white" and result == "1-0") or \
                      (user_color == "black" and result == "0-1")
                
                if won:
                    converted += 1
    
    rate = converted / total_advantaged_endgames if total_advantaged_endgames > 0 else 0
    
    return {
        "rate": round(rate, 3),
        "converted": converted,
        "total_advantaged_endgames": total_advantaged_endgames,
        "trend": "stable",
    }


def compute_time_trouble_pattern(analyses: List[Dict], rating_band: str) -> Dict:
    """
    Detect if user has time trouble pattern (blunders in moves 40+).
    """
    if not analyses:
        return {"has_pattern": False, "rate": 0, "late_blunder_count": 0, "total_blunders": 0, "trend": "unknown"}
    
    late_blunder_count = 0
    total_blunders = 0
    games_with_late_blunders = 0
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        game_total_blunders = a.get("blunders", 0)
        total_blunders += game_total_blunders
        
        late_blunders = [m for m in moves 
                        if m.get("move_number", 0) > 40 
                        and m.get("evaluation") == "blunder"]
        
        if late_blunders:
            late_blunder_count += len(late_blunders)
            games_with_late_blunders += 1
    
    rate = games_with_late_blunders / len(analyses) if analyses else 0
    has_pattern = rate >= 0.25  # 25%+ games have late blunders
    
    return {
        "has_pattern": has_pattern,
        "rate": round(rate, 3),
        "late_blunder_count": late_blunder_count,
        "total_blunders": total_blunders,
        "trend": "stable",
    }


def compute_primary_leak(
    analyses: List[Dict], 
    games: List[Dict],
    rating: int
) -> Dict:
    """
    Compute the PRIMARY leak limiting the user's rating.
    
    This is rating-band aware:
    - 600-1000: Check hanging pieces first
    - 1000-1600: Check tactical awareness
    - 1600-2000: Check advantage discipline
    - 2000+: Check conversion precision
    """
    band = get_rating_band(rating)
    band_name = band["name"]
    
    # Get all metrics
    hanging = compute_hanging_piece_frequency(analyses, band_name)
    tactical = compute_tactical_miss_rate(analyses, band_name)
    collapse = compute_advantage_collapse_rate(analyses, band_name)
    endgame = compute_endgame_conversion_rate(analyses, games, band_name)
    time = compute_time_trouble_pattern(analyses, band_name)
    
    # Rating-band specific leak detection
    leak_info = LEAKS_BY_BAND.get(band_name, LEAKS_BY_BAND["beginner"])
    primary_leak = leak_info["primary"].copy()
    
    # Always try to get an example position based on the leak type
    # This makes the "See Typical Pattern" button useful
    if band_name == "beginner":
        # For beginners, look for hanging pieces
        primary_leak["evidence_rate"] = hanging["rate"]
        primary_leak["example_position"] = hanging["example_positions"][0] if hanging["example_positions"] else None
    elif band_name == "club":
        # For club players, look for tactical misses
        primary_leak["evidence_rate"] = tactical["blunders_per_game"]
        primary_leak["example_position"] = tactical["example_positions"][0] if tactical["example_positions"] else None
    elif band_name in ["intermediate", "advanced"]:
        # For higher rated players, look for advantage collapses
        primary_leak["evidence_rate"] = collapse["rate"]
        primary_leak["example_position"] = collapse["example_positions"][0] if collapse["example_positions"] else None
        
        # Fallback to tactical if no collapse evidence
        if not primary_leak["example_position"] and tactical["example_positions"]:
            primary_leak["example_position"] = tactical["example_positions"][0]
    
    return {
        "leak": primary_leak,
        "raw_metrics": {
            "hanging_piece_rate": hanging["rate"],
            "blunders_per_game": tactical["blunders_per_game"],
            "advantage_collapse_rate": collapse["rate"],
            "endgame_conversion_rate": endgame["rate"],
            "time_trouble_rate": time["rate"],
        }
    }


def compute_secondary_leak(
    analyses: List[Dict],
    games: List[Dict], 
    rating: int,
    primary_leak_id: str
) -> Optional[Dict]:
    """
    Compute secondary leak (if any).
    """
    band = get_rating_band(rating)
    band_name = band["name"]
    leak_info = LEAKS_BY_BAND.get(band_name, LEAKS_BY_BAND["beginner"])
    
    secondary = leak_info.get("secondary")
    if secondary and secondary["id"] != primary_leak_id:
        return secondary.copy()
    
    return None


def compute_skill_trends(
    recent_analyses: List[Dict],  # Last 10 games
    older_analyses: List[Dict],   # Games 11-20
    games: List[Dict],
    rating: int
) -> Dict:
    """
    Compute skill development signals with trends.
    
    Returns 5 skill dimensions with:
    - trend: "improving" (↑), "declining" (↓), "stable" (→)
    - reason: Short explanation
    - example_position: FEN for click-to-view
    """
    band = get_rating_band(rating)
    band_name = band["name"]
    
    # Need both sets for comparison
    if len(recent_analyses) < 5 or len(older_analyses) < 5:
        return {
            "has_enough_data": False,
            "signals": []
        }
    
    signals = []
    
    # 1. Opening Stability
    recent_opening = compute_opening_stability(recent_analyses, games[-10:], band_name)
    older_opening = compute_opening_stability(older_analyses, games[-20:-10] if len(games) >= 20 else [], band_name)
    
    opening_diff = recent_opening["score"] - older_opening["score"]
    signals.append({
        "id": "opening_stability",
        "label": "Opening Stability",
        "trend": "improving" if opening_diff > 5 else ("declining" if opening_diff < -5 else "stable"),
        "trend_arrow": "↑" if opening_diff > 5 else ("↓" if opening_diff < -5 else "→"),
        "reason": f"{'More' if opening_diff > 0 else 'Less'} consistent opening play" if abs(opening_diff) > 5 else "Steady opening performance",
        "current_score": recent_opening["score"],
        "example_position": None,
    })
    
    # 2. Tactical Awareness
    recent_tactical = compute_tactical_miss_rate(recent_analyses, band_name)
    older_tactical = compute_tactical_miss_rate(older_analyses, band_name)
    
    tactical_diff = older_tactical["blunders_per_game"] - recent_tactical["blunders_per_game"]
    signals.append({
        "id": "tactical_awareness",
        "label": "Tactical Awareness",
        "trend": "improving" if tactical_diff > 0.3 else ("declining" if tactical_diff < -0.3 else "stable"),
        "trend_arrow": "↑" if tactical_diff > 0.3 else ("↓" if tactical_diff < -0.3 else "→"),
        "reason": f"{'Fewer' if tactical_diff > 0 else 'More'} tactical errors" if abs(tactical_diff) > 0.3 else "Consistent tactical play",
        "current_score": round(100 - (recent_tactical["blunders_per_game"] * 20)),
        "example_position": recent_tactical["example_positions"][0] if recent_tactical["example_positions"] else None,
    })
    
    # 3. Advantage Discipline
    recent_collapse = compute_advantage_collapse_rate(recent_analyses, band_name)
    older_collapse = compute_advantage_collapse_rate(older_analyses, band_name)
    
    collapse_diff = older_collapse["rate"] - recent_collapse["rate"]
    signals.append({
        "id": "advantage_discipline",
        "label": "Advantage Discipline",
        "trend": "improving" if collapse_diff > 0.1 else ("declining" if collapse_diff < -0.1 else "stable"),
        "trend_arrow": "↑" if collapse_diff > 0.1 else ("↓" if collapse_diff < -0.1 else "→"),
        "reason": f"{'Better' if collapse_diff > 0 else 'Worse'} at holding advantages" if abs(collapse_diff) > 0.1 else "Steady advantage handling",
        "current_score": round(100 - (recent_collapse["rate"] * 100)),
        "example_position": recent_collapse["example_positions"][0] if recent_collapse["example_positions"] else None,
    })
    
    # 4. Endgame Technique
    recent_games = games[-10:] if len(games) >= 10 else games
    older_games = games[-20:-10] if len(games) >= 20 else []
    recent_endgame = compute_endgame_conversion_rate(recent_analyses, recent_games, band_name)
    older_endgame = compute_endgame_conversion_rate(older_analyses, older_games, band_name)
    
    endgame_diff = recent_endgame["rate"] - older_endgame["rate"]
    signals.append({
        "id": "endgame_technique",
        "label": "Endgame Technique",
        "trend": "improving" if endgame_diff > 0.1 else ("declining" if endgame_diff < -0.1 else "stable"),
        "trend_arrow": "↑" if endgame_diff > 0.1 else ("↓" if endgame_diff < -0.1 else "→"),
        "reason": f"{'Better' if endgame_diff > 0 else 'Worse'} endgame conversion" if abs(endgame_diff) > 0.1 else "Consistent endgame play",
        "current_score": round(recent_endgame["rate"] * 100) if recent_endgame["total_advantaged_endgames"] > 0 else None,
        "example_position": None,
    })
    
    # 5. Time Control
    recent_time = compute_time_trouble_pattern(recent_analyses, band_name)
    older_time = compute_time_trouble_pattern(older_analyses, band_name)
    
    time_diff = older_time["rate"] - recent_time["rate"]
    signals.append({
        "id": "time_control",
        "label": "Time Control",
        "trend": "improving" if time_diff > 0.1 else ("declining" if time_diff < -0.1 else "stable"),
        "trend_arrow": "↑" if time_diff > 0.1 else ("↓" if time_diff < -0.1 else "→"),
        "reason": f"{'Fewer' if time_diff > 0 else 'More'} time pressure mistakes" if abs(time_diff) > 0.1 else "Steady time management",
        "current_score": round(100 - (recent_time["rate"] * 100)),
        "example_position": None,
    })
    
    return {
        "has_enough_data": True,
        "signals": signals,
    }


def generate_next_game_plan(
    rating: int,
    primary_leak: Dict,
    opening_stability: Dict,
    time_trouble: Dict,
    endgame_conversion: Dict,
    domain_intensity: Dict,  # Per-domain intensity levels
) -> Dict:
    """
    Generate the 5-domain Next Game Plan.
    
    Domains:
    1. Opening Strategy
    2. Middlegame Objective
    3. Tactical Protocol
    4. Endgame Reminder (if applicable)
    5. Time Discipline (if applicable)
    """
    band = get_rating_band(rating)
    
    plan = {
        "plan_id": f"plan_{uuid.uuid4().hex[:12]}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rating_band": band["label"],
        "domains": []
    }
    
    # 1. Opening Strategy
    opening_rec = opening_stability.get("best_opening_white")
    opening_moves = []  # Would come from opening book in real implementation
    
    plan["domains"].append({
        "id": "opening",
        "label": "Opening Strategy",
        "goal": f"Play {opening_rec['name']}" if opening_rec else "Develop pieces, control center, castle early",
        "moves": opening_moves[:8] if opening_moves else None,
        "intensity": domain_intensity.get("opening", 2),
        "has_board_drill": bool(opening_moves),
    })
    
    # 2. Middlegame Objective (based on primary leak)
    middlegame_goal = band["middlegame_rule"]
    if primary_leak.get("id") == "advantage_collapse":
        middlegame_goal = "When ahead, trade pieces. Don't complicate."
    elif primary_leak.get("id") == "hanging_pieces":
        middlegame_goal = "Before moving, check: Will my piece be safe?"
    
    plan["domains"].append({
        "id": "middlegame",
        "label": "Middlegame Objective",
        "goal": middlegame_goal,
        "intensity": domain_intensity.get("middlegame", 2),
        "has_board_drill": False,
    })
    
    # 3. Tactical Protocol (rating-specific)
    plan["domains"].append({
        "id": "tactical",
        "label": "Tactical Protocol",
        "goal": band["tactical_protocol"],
        "intensity": domain_intensity.get("tactical", 2),
        "has_board_drill": False,
    })
    
    # 4. Endgame Reminder (only if needed)
    if endgame_conversion.get("total_advantaged_endgames", 0) > 2 and endgame_conversion.get("rate", 1) < 0.7:
        plan["domains"].append({
            "id": "endgame",
            "label": "Endgame Reminder",
            "goal": "King to center immediately. Activate king before pushing pawns.",
            "intensity": domain_intensity.get("endgame", 2),
            "has_board_drill": False,
        })
    
    # 5. Time Discipline (only if pattern detected)
    if time_trouble.get("has_pattern"):
        plan["domains"].append({
            "id": "time",
            "label": "Time Discipline",
            "goal": "Move within 30 seconds. No long thinks.",
            "intensity": domain_intensity.get("time", 3),
            "has_board_drill": False,
        })
    
    return plan


def audit_last_game_against_plan(
    analysis: Dict,
    game: Dict,
    previous_plan: Dict
) -> Dict:
    """
    Audit the last game against the previous plan.
    
    Returns audit cards for each domain:
    - status: "executed" / "partial" / "missed"
    - data_line: Single data point
    - move_reference: Move number if applicable
    - board_link_fen: FEN for click-to-view
    """
    if not previous_plan or not previous_plan.get("domains"):
        return {"has_plan": False, "audit_cards": []}
    
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    audit_cards = []
    domains_audited = 0
    domains_executed = 0
    
    for domain in previous_plan.get("domains", []):
        domain_id = domain.get("id")
        card = {
            "domain_id": domain_id,
            "label": domain.get("label"),
            "goal": domain.get("goal"),
            "status": "n/a",
            "data_line": None,
            "move_reference": None,
            "board_link_fen": None,
        }
        
        if domain_id == "opening":
            # Check opening stability
            early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
            if early_moves:
                max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
                avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
                
                if max_drop < 100 and avg_cp < 30:
                    card["status"] = "executed"
                    card["data_line"] = f"Opening phase: stable ({round(avg_cp)}cp avg loss)"
                elif max_drop < 200:
                    card["status"] = "partial"
                    card["data_line"] = f"Opening phase: some inaccuracies"
                else:
                    card["status"] = "missed"
                    card["data_line"] = f"Opening mistake on move {early_moves[0].get('move_number')}"
                    card["board_link_fen"] = early_moves[0].get("fen_before")
                    card["move_reference"] = early_moves[0].get("move_number")
        
        elif domain_id == "middlegame":
            # Check advantage handling
            had_advantage = False
            collapsed = False
            collapse_move = None
            
            for m in moves:
                if m.get("eval_before", 0) >= 150:
                    had_advantage = True
                    if m.get("cp_loss", 0) >= 150:
                        collapsed = True
                        collapse_move = m
                        break
            
            if not had_advantage:
                card["status"] = "n/a"
                card["data_line"] = "No clear advantage reached"
            elif collapsed:
                card["status"] = "missed"
                card["data_line"] = f"Advantage lost on move {collapse_move.get('move_number')}"
                card["board_link_fen"] = collapse_move.get("fen_before")
                card["move_reference"] = collapse_move.get("move_number")
            else:
                card["status"] = "executed"
                card["data_line"] = "Maintained advantage when ahead"
        
        elif domain_id == "tactical":
            # Check blunder count
            blunders = analysis.get("blunders", 0)
            mistakes = analysis.get("mistakes", 0)
            
            if blunders == 0 and mistakes <= 1:
                card["status"] = "executed"
                card["data_line"] = "Clean tactical play"
            elif blunders <= 1:
                card["status"] = "partial"
                card["data_line"] = f"{blunders} blunder, {mistakes} mistakes"
            else:
                card["status"] = "missed"
                # Find first blunder
                for m in moves:
                    if m.get("evaluation") == "blunder":
                        card["data_line"] = f"Blunder on move {m.get('move_number')}"
                        card["board_link_fen"] = m.get("fen_before")
                        card["move_reference"] = m.get("move_number")
                        break
        
        elif domain_id == "endgame":
            # Check endgame performance
            endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
            if not endgame_moves:
                card["status"] = "n/a"
                card["data_line"] = "Game ended before endgame"
            else:
                eg_blunders = [m for m in endgame_moves if m.get("evaluation") == "blunder"]
                if eg_blunders:
                    card["status"] = "missed"
                    card["data_line"] = f"Endgame error on move {eg_blunders[0].get('move_number')}"
                    card["board_link_fen"] = eg_blunders[0].get("fen_before")
                else:
                    card["status"] = "executed"
                    card["data_line"] = "Solid endgame play"
        
        elif domain_id == "time":
            # Check late-game blunders (proxy for time trouble)
            late_blunders = [m for m in moves if m.get("move_number", 0) > 40 and m.get("evaluation") == "blunder"]
            if late_blunders:
                card["status"] = "missed"
                card["data_line"] = f"Late blunder on move {late_blunders[0].get('move_number')}"
                card["board_link_fen"] = late_blunders[0].get("fen_before")
            else:
                card["status"] = "executed"
                card["data_line"] = "Good time management"
        
        if card["status"] != "n/a":
            domains_audited += 1
            if card["status"] == "executed":
                domains_executed += 1
        
        audit_cards.append(card)
    
    return {
        "has_plan": True,
        "plan_id": previous_plan.get("plan_id"),
        "audit_cards": audit_cards,
        "score": f"{domains_executed}/{domains_audited}" if domains_audited > 0 else "0/0",
        "execution_rate": domains_executed / domains_audited if domains_audited > 0 else 0,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_opening_family(game: Dict) -> str:
    """Extract opening family name from game data."""
    opening = game.get("opening", "")
    
    if not opening:
        # Try to extract from PGN
        pgn = game.get("pgn", "")
        import re
        match = re.search(r'\[Opening "([^"]+)"\]', pgn)
        if match:
            opening = match.group(1)
        else:
            eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
            if eco_match:
                opening = eco_match.group(1)
    
    if not opening:
        return "Unknown Opening"
    
    # Extract family (first part before colon or comma)
    family = opening.split(":")[0].split(",")[0].strip()
    
    # Common families
    families = [
        "Sicilian Defense", "French Defense", "Caro-Kann Defense",
        "Italian Game", "Ruy Lopez", "Queen's Gambit", "King's Indian",
        "English Opening", "Scandinavian Defense", "Pirc Defense",
        "London System", "Queen's Pawn Opening", "King's Pawn Opening"
    ]
    
    for f in families:
        if f.lower() in opening.lower():
            return f
    
    return family if len(family) < 40 else family[:40]


# =============================================================================
# MAIN API FUNCTIONS
# =============================================================================

async def get_adaptive_coach_data(db, user_id: str) -> Dict:
    """
    Get complete Adaptive Performance Coach data for the Focus page.
    
    Returns all 4 sections:
    1. Coach Diagnosis (primary/secondary leak)
    2. Next Game Plan (5 domains)
    3. Plan Audit (last game vs plan)
    4. Skill Signals (trends)
    """
    
    # Get user
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"error": "User not found"}
    
    rating = user.get("rating", 1200)
    band = get_rating_band(rating)
    
    # Get last 20 analyzed games
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(30)
    
    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0}
    ).to_list(30)
    
    # Sort analyses to match games order
    analysis_map = {a.get("game_id"): a for a in analyses}
    sorted_analyses = [analysis_map.get(g["game_id"]) for g in games if analysis_map.get(g["game_id"])]
    
    games_analyzed = len(sorted_analyses)
    needs_more_games = games_analyzed < 5
    
    if needs_more_games:
        return {
            "needs_more_games": True,
            "games_analyzed": games_analyzed,
            "games_required": 5,
            "rating": rating,
            "rating_band": band["label"],
        }
    
    # Split for trend analysis
    recent_analyses = sorted_analyses[:10]
    older_analyses = sorted_analyses[10:20] if len(sorted_analyses) >= 20 else []
    
    # === SECTION 1: COACH DIAGNOSIS ===
    primary_leak_data = compute_primary_leak(sorted_analyses[:20], games[:20], rating)
    primary_leak = primary_leak_data["leak"]
    secondary_leak = compute_secondary_leak(sorted_analyses[:20], games[:20], rating, primary_leak["id"])
    
    diagnosis = {
        "title": "Your Current Growth Priority",
        "primary_leak": primary_leak,
        "secondary_leak": secondary_leak,
        "raw_metrics": primary_leak_data["raw_metrics"],
    }
    
    # === SECTION 2: NEXT GAME PLAN ===
    opening_stability = compute_opening_stability(sorted_analyses[:20], games[:20], band["name"])
    time_trouble = compute_time_trouble_pattern(sorted_analyses[:20], band["name"])
    endgame_conversion = compute_endgame_conversion_rate(sorted_analyses[:20], games[:20], band["name"])
    
    # Get or create domain intensity from user's active plan
    active_plan = await db.user_adaptive_plans.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0}
    )
    
    domain_intensity = {}
    if active_plan:
        for d in active_plan.get("domains", []):
            domain_intensity[d.get("id")] = d.get("intensity", 2)
    
    next_game_plan = generate_next_game_plan(
        rating, primary_leak, opening_stability, time_trouble, endgame_conversion, domain_intensity
    )
    
    # === SECTION 3: PLAN AUDIT ===
    last_game = games[0] if games else None
    last_analysis = sorted_analyses[0] if sorted_analyses else None
    
    # Get the previous plan (before last game)
    previous_plan = await db.user_adaptive_plans.find_one(
        {"user_id": user_id, "is_active": False},
        {"_id": 0},
        sort=[("generated_at", -1)]
    )
    
    plan_audit = {"has_plan": False, "audit_cards": []}
    
    # If no previous plan exists, use the current plan to audit the last game
    # This gives users immediate value on first visit
    plan_to_audit = previous_plan if previous_plan else next_game_plan
    
    if last_analysis and plan_to_audit:
        plan_audit = audit_last_game_against_plan(last_analysis, last_game, plan_to_audit)
    
    # Add last game info to audit
    if last_game:
        user_color = last_game.get("user_color", "white")
        result = last_game.get("result", "")
        
        if user_color == "white":
            user_won = result == "1-0"
            opponent = last_game.get("black_player", "Opponent")
        else:
            user_won = result == "0-1"
            opponent = last_game.get("white_player", "Opponent")
        
        plan_audit["last_game"] = {
            "result": "win" if user_won else ("loss" if result in ["1-0", "0-1"] else "draw"),
            "opponent": opponent,
            "game_id": last_game.get("game_id"),
        }
    
    # === SECTION 4: SKILL SIGNALS ===
    skill_signals = compute_skill_trends(recent_analyses, older_analyses, games, rating)
    
    # Store the new plan
    next_game_plan["user_id"] = user_id
    next_game_plan["is_active"] = True
    
    # Deactivate old plans
    await db.user_adaptive_plans.update_many(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Insert new plan
    await db.user_adaptive_plans.insert_one({**next_game_plan})
    
    # Remove _id from plan before returning
    next_game_plan.pop("_id", None)
    
    return {
        "needs_more_games": False,
        "games_analyzed": games_analyzed,
        "rating": rating,
        "rating_band": band["label"],
        
        # The 4 Sections
        "diagnosis": diagnosis,
        "next_game_plan": next_game_plan,
        "plan_audit": plan_audit,
        "skill_signals": skill_signals,
        
        # Supporting data
        "opening_recommendation": opening_stability,
    }


async def update_intensity_after_audit(db, user_id: str, audit_result: Dict) -> Dict:
    """
    Update domain intensity levels after audit.
    
    Adaptive loop:
    - Missed: +1 intensity (max 5)
    - Executed: -1 intensity (min 1)
    """
    active_plan = await db.user_adaptive_plans.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0}
    )
    
    if not active_plan:
        return {"updated": False}
    
    audit_cards = audit_result.get("audit_cards", [])
    updates = {}
    
    for card in audit_cards:
        domain_id = card.get("domain_id")
        status = card.get("status")
        
        if status == "n/a":
            continue
        
        # Find current intensity
        current_intensity = 2
        for d in active_plan.get("domains", []):
            if d.get("id") == domain_id:
                current_intensity = d.get("intensity", 2)
                break
        
        # Adjust
        if status == "missed":
            new_intensity = min(5, current_intensity + 1)
        elif status == "executed":
            new_intensity = max(1, current_intensity - 1)
        else:
            new_intensity = current_intensity
        
        if new_intensity != current_intensity:
            updates[domain_id] = new_intensity
    
    # Update plan in database
    if updates:
        for domain in active_plan.get("domains", []):
            if domain.get("id") in updates:
                domain["intensity"] = updates[domain.get("id")]
        
        await db.user_adaptive_plans.update_one(
            {"plan_id": active_plan["plan_id"]},
            {"$set": {"domains": active_plan["domains"]}}
        )
    
    return {"updated": True, "intensity_changes": updates}
