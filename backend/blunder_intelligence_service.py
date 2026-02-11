"""
Blunder Intelligence Service - Core Analytics for the Blunder Reduction System

This service provides:
1. Core Lesson Engine - One dominant behavioral cause per game
2. Dominant Weakness Ranking - #1 Rating Killer identification
3. Win-State Analysis - When do blunders happen (ahead/equal/behind)
4. Mistake Heatmap Data - Where on the board do mistakes occur
5. Rating Impact Estimator - "Fixing X saves ~Y rating points"
6. Identity Profile - "Aggressive but careless" labels
7. Mission System - Gamified improvement tracking
8. Milestone Detection - Achievement triggers

100% DETERMINISTIC - No LLM decisions here.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import chess

logger = logging.getLogger(__name__)

# ============================================
# BEHAVIORAL PATTERNS - Maps mistake types to human behaviors
# ============================================

def infer_mistake_type_from_eval(move: Dict) -> str:
    """
    Infer a basic mistake type from move evaluation data.
    This is a fallback when mistake_type isn't explicitly stored.
    
    Uses cp_loss, eval_before, eval_after, is_best to categorize.
    """
    cp_loss = abs(move.get("cp_loss", 0))
    eval_before = move.get("eval_before", 0)
    eval_after = move.get("eval_after", 0)
    is_best = move.get("is_best", False)
    move_number = move.get("move_number", 20)
    
    if is_best or cp_loss < 20:
        return "good_move"
    
    # Determine game phase by move number (simplified)
    if move_number <= 10:
        phase = "opening"
    elif move_number <= 30:
        phase = "middlegame"
    else:
        phase = "endgame"
    
    # Was ahead before the move?
    was_ahead = eval_before > 1.0
    was_behind = eval_before < -1.0
    
    # Categorize by severity and context
    if cp_loss >= 300:  # Major blunder (3+ pawns)
        if was_ahead:
            return "blunder_when_ahead"
        else:
            return "material_blunder"
    elif cp_loss >= 150:  # Significant mistake
        if was_ahead:
            return "failed_conversion"
        elif phase == "opening":
            return "positional_drift"
        else:
            return "tactical_miss"
    elif cp_loss >= 50:  # Minor mistake
        if phase == "opening":
            return "opening_inaccuracy"
        else:
            return "positional_drift"
    
    return "inaccuracy"


# Extended behavioral patterns for inferred types
BEHAVIORAL_PATTERNS = {
    # Attack-related behaviors
    "attacks_before_checking_threats": {
        "triggers": ["hanging_piece", "ignored_threat", "walked_into_fork", "walked_into_pin", "walked_into_skewer", "walked_into_discovered_attack", "tactical_miss"],
        "message": "You attack before checking opponent threats.",
        "short": "Impulsive attacker",
        "fix": "Before each move, ask: What can my opponent do to me?"
    },
    "loses_focus_when_winning": {
        "triggers": ["blunder_when_ahead", "failed_conversion"],
        "message": "You lose focus immediately after gaining advantage.",
        "short": "Relaxes when winning",
        "fix": "When ahead, play like you're still equal. Stay alert."
    },
    "misses_tactical_opportunities": {
        "triggers": ["missed_fork", "missed_pin", "missed_skewer", "missed_discovered_attack", "missed_overloaded_defender", "missed_winning_tactic"],
        "message": "You miss winning tactics that were available.",
        "short": "Tactical blind spots",
        "fix": "Look for checks, captures, and threats before each move."
    },
    "poor_piece_safety": {
        "triggers": ["hanging_piece", "material_blunder"],
        "message": "You leave pieces undefended or in danger.",
        "short": "Piece safety issues",
        "fix": "After choosing a move, verify each piece is safe."
    },
    "time_pressure_collapse": {
        "triggers": ["time_pressure_blunder"],
        "message": "You make critical errors under time pressure.",
        "short": "Time trouble weakness",
        "fix": "Use more time in complex positions. Simplify when low on clock."
    },
    "positional_drift": {
        "triggers": ["positional_drift", "king_safety_error", "opening_inaccuracy", "inaccuracy"],
        "message": "You lose the thread of the position.",
        "short": "Positional wanderer",
        "fix": "Every 5 moves, reassess: What's the plan?"
    }
}

# Identity profiles based on mistake ratios
IDENTITY_PROFILES = {
    "aggressive_careless": {
        "condition": lambda stats: stats.get("attacks_before_checking_threats", 0) > stats.get("total", 1) * 0.3,
        "label": "Aggressive but careless",
        "description": "You play actively but often miss opponent threats."
    },
    "solid_passive": {
        "condition": lambda stats: stats.get("misses_tactical_opportunities", 0) > stats.get("total", 1) * 0.3,
        "label": "Solid but passive",
        "description": "You defend well but miss winning chances."
    },
    "tactical_impatient": {
        "condition": lambda stats: stats.get("attacks_before_checking_threats", 0) > 2 and stats.get("misses_tactical_opportunities", 0) > 2,
        "label": "Tactical but impatient",
        "description": "You see tactics but rush into them without checking safety."
    },
    "conversion_struggler": {
        "condition": lambda stats: stats.get("loses_focus_when_winning", 0) > stats.get("total", 1) * 0.25,
        "label": "Conversion struggler",
        "description": "You get good positions but struggle to finish games."
    },
    "time_trouble_player": {
        "condition": lambda stats: stats.get("time_pressure_collapse", 0) > stats.get("total", 1) * 0.2,
        "label": "Time trouble player",
        "description": "Clock management is your biggest enemy."
    },
    "balanced_improver": {
        "condition": lambda stats: True,  # Default fallback
        "label": "Balanced improver",
        "description": "No single glaring weakness - focus on consistency."
    }
}


def get_core_lesson(analysis: Dict) -> Dict:
    """
    Extract ONE dominant behavioral cause from a single game analysis.
    
    Returns the most impactful mistake pattern based on:
    1. Total centipawn loss
    2. Frequency in the game
    3. Critical phase occurrence
    
    NO ENGINE LINES. NO INVENTED VARIATIONS.
    """
    if not analysis:
        return {
            "lesson": "No analysis available for this game.",
            "pattern": None,
            "behavioral_fix": None,
            "severity": "unknown"
        }
    
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    if not move_evals:
        return {
            "lesson": "Game not yet analyzed with engine.",
            "pattern": None,
            "behavioral_fix": None,
            "severity": "unknown"
        }
    
    # Count mistake types and their total centipawn impact
    pattern_impact = defaultdict(lambda: {"count": 0, "total_cp_loss": 0, "critical_phase": False})
    
    for move in move_evals:
        # Use stored mistake_type OR infer from eval data
        mistake_type = move.get("mistake_type", "")
        if not mistake_type:
            mistake_type = infer_mistake_type_from_eval(move)
        
        cp_loss = abs(move.get("cp_loss", 0))  # Already in centipawns
        phase = move.get("phase", "middlegame")
        move_number = move.get("move_number", 20)
        
        # Infer phase from move number if not stored
        if not phase or phase == "middlegame":
            if move_number <= 10:
                phase = "opening"
            elif move_number <= 30:
                phase = "middlegame"
            else:
                phase = "endgame"
        
        if not mistake_type or mistake_type in ["good_move", "excellent_move"]:
            continue
        
        # Map to behavioral pattern
        for pattern_key, pattern_data in BEHAVIORAL_PATTERNS.items():
            if mistake_type in pattern_data["triggers"]:
                pattern_impact[pattern_key]["count"] += 1
                pattern_impact[pattern_key]["total_cp_loss"] += cp_loss
                if phase == "middlegame" and cp_loss > 100:
                    pattern_impact[pattern_key]["critical_phase"] = True
                break
    
    if not pattern_impact:
        return {
            "lesson": "No significant mistakes detected. Well played!",
            "pattern": "clean_game",
            "behavioral_fix": "Keep this focus in your next games.",
            "severity": "none"
        }
    
    # Find dominant pattern: prioritize critical phase, then CP loss, then count
    dominant = max(
        pattern_impact.items(),
        key=lambda x: (
            x[1]["critical_phase"],
            x[1]["total_cp_loss"],
            x[1]["count"]
        )
    )
    
    pattern_key = dominant[0]
    pattern_data = BEHAVIORAL_PATTERNS[pattern_key]
    impact = dominant[1]
    
    # Determine severity
    if impact["total_cp_loss"] > 300:
        severity = "critical"
    elif impact["total_cp_loss"] > 150:
        severity = "significant"
    else:
        severity = "minor"
    
    return {
        "lesson": pattern_data["message"],
        "pattern": pattern_key,
        "behavioral_fix": pattern_data["fix"],
        "severity": severity,
        "occurrences": impact["count"],
        "total_cp_loss": round(impact["total_cp_loss"]),
        "short_label": pattern_data["short"]
    }


def get_dominant_weakness_ranking(analyses: List[Dict], games: List[Dict] = None) -> Dict:
    """
    Rank weaknesses by rating impact. Returns:
    - #1 Rating Killer (highest CP loss contribution)
    - Secondary Weakness
    - Stable Strength
    - EVIDENCE: List of specific positions for each pattern
    
    Based on last 15 games.
    """
    if not analyses:
        return {
            "rating_killer": None,
            "secondary_weakness": None,
            "stable_strength": None,
            "ranking": [],
            "insight": "Play more games to identify your weaknesses."
        }
    
    # Build games lookup for opponent names
    games_lookup = {}
    if games:
        for g in games:
            games_lookup[g.get("game_id")] = g
    
    # Aggregate all patterns across games WITH EVIDENCE
    pattern_totals = defaultdict(lambda: {
        "total_cp_loss": 0,
        "count": 0,
        "games_affected": 0,
        "evidence": []  # NEW: Store specific positions
    })
    
    games_analyzed = 0
    
    for analysis in analyses[-15:]:  # Last 15 games
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        game_id = analysis.get("game_id", "")
        
        if not move_evals:
            continue
        
        games_analyzed += 1
        patterns_in_game = set()
        
        # Get opponent name from games lookup
        game_info = games_lookup.get(game_id, {})
        user_color = game_info.get("user_color", "white")
        opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
        opponent = opponent or "Opponent"
        
        for move in move_evals:
            # Use stored mistake_type OR infer from eval data
            mistake_type = move.get("mistake_type", "")
            if not mistake_type:
                mistake_type = infer_mistake_type_from_eval(move)
            
            cp_loss = abs(move.get("cp_loss", 0))  # Already in centipawns
            eval_before = move.get("eval_before", 0)
            
            if not mistake_type or mistake_type in ["good_move", "excellent_move"]:
                continue
            
            for pattern_key, pattern_data in BEHAVIORAL_PATTERNS.items():
                if mistake_type in pattern_data["triggers"]:
                    pattern_totals[pattern_key]["total_cp_loss"] += cp_loss
                    pattern_totals[pattern_key]["count"] += 1
                    patterns_in_game.add(pattern_key)
                    
                    # Store evidence (limit to 10 examples per pattern)
                    if len(pattern_totals[pattern_key]["evidence"]) < 10:
                        pattern_totals[pattern_key]["evidence"].append({
                            "game_id": game_id,
                            "move_number": move.get("move_number", 0),
                            "move_played": move.get("move", ""),
                            "best_move": move.get("best_move", ""),
                            "fen_before": move.get("fen_before", ""),
                            "cp_loss": round(cp_loss),
                            "eval_before": round(eval_before, 1) if eval_before else 0,
                            "opponent": opponent,
                            "mistake_type": mistake_type
                        })
                    break
        
        for pattern in patterns_in_game:
            pattern_totals[pattern]["games_affected"] += 1
    
    if not pattern_totals:
        return {
            "rating_killer": None,
            "secondary_weakness": None,
            "stable_strength": None,
            "ranking": [],
            "insight": "No significant patterns detected yet."
        }
    
    # Rank by: CP loss * recurrence factor
    ranking = sorted(
        pattern_totals.items(),
        key=lambda x: x[1]["total_cp_loss"] * (1 + x[1]["games_affected"] / max(games_analyzed, 1)),
        reverse=True
    )
    
    # Build result
    result = {
        "games_analyzed": games_analyzed,
        "ranking": []
    }
    
    for i, (pattern_key, stats) in enumerate(ranking):
        pattern_info = BEHAVIORAL_PATTERNS.get(pattern_key, {})
        
        # Sort evidence by cp_loss (most costly first)
        sorted_evidence = sorted(stats["evidence"], key=lambda x: x["cp_loss"], reverse=True)
        
        entry = {
            "pattern": pattern_key,
            "label": pattern_info.get("short", pattern_key),
            "message": pattern_info.get("message", ""),
            "fix": pattern_info.get("fix", ""),
            "total_cp_loss": round(stats["total_cp_loss"]),
            "occurrences": stats["count"],
            "games_affected": stats["games_affected"],
            "frequency_pct": round(stats["games_affected"] / max(games_analyzed, 1) * 100),
            "evidence": sorted_evidence  # NEW: Include evidence positions
        }
        result["ranking"].append(entry)
        
        if i == 0:
            result["rating_killer"] = entry
        elif i == 1:
            result["secondary_weakness"] = entry
    
    # Find stable strength (least problematic area)
    if len(ranking) >= 1:
        stable = ranking[-1]
        pattern_info = BEHAVIORAL_PATTERNS.get(stable[0], {})
        result["stable_strength"] = {
            "pattern": stable[0],
            "label": pattern_info.get("short", stable[0]),
            "message": f"You rarely make {pattern_info.get('short', 'these')} mistakes."
        }
    
    # Generate insight
    if result.get("rating_killer"):
        rk = result["rating_killer"]
        result["insight"] = f"Your #1 rating killer: {rk['label']}. This cost you ~{rk['total_cp_loss']} centipawns across {rk['games_affected']} games."
    
    return result


def get_win_state_analysis(analyses: List[Dict], games: List[Dict] = None) -> Dict:
    """
    Analyze when blunders happen:
    - Blunders when winning (was_ahead)
    - Blunders when equal
    - Blunders when losing (was_behind)
    - EVIDENCE: Specific positions for each state
    
    Returns percentages, insight, and evidence.
    """
    if not analyses:
        return {
            "when_winning": {"count": 0, "percentage": 0, "evidence": []},
            "when_equal": {"count": 0, "percentage": 0, "evidence": []},
            "when_losing": {"count": 0, "percentage": 0, "evidence": []},
            "total_blunders": 0,
            "insight": "Not enough data yet."
        }
    
    # Build games lookup for opponent names
    games_lookup = {}
    if games:
        for g in games:
            games_lookup[g.get("game_id")] = g
    
    counts = {"winning": 0, "equal": 0, "losing": 0}
    evidence = {"winning": [], "equal": [], "losing": []}
    
    for analysis in analyses[-15:]:
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        game_id = analysis.get("game_id", "")
        
        # Get opponent name
        game_info = games_lookup.get(game_id, {})
        user_color = game_info.get("user_color", "white")
        opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
        opponent = opponent or "Opponent"
        
        for move in move_evals:
            cp_loss = abs(move.get("cp_loss", 0))  # Already in centipawns
            if cp_loss < 100:  # Only count significant mistakes
                continue
            
            # Determine position state before the blunder
            eval_before = move.get("eval_before", 0)
            if eval_before > 1.5:
                state = "winning"
            elif eval_before < -1.5:
                state = "losing"
            else:
                state = "equal"
            
            counts[state] += 1
            
            # Store evidence (limit to 7 per state)
            if len(evidence[state]) < 7:
                evidence[state].append({
                    "game_id": game_id,
                    "move_number": move.get("move_number", 0),
                    "move_played": move.get("move", ""),
                    "best_move": move.get("best_move", ""),
                    "fen_before": move.get("fen_before", ""),
                    "cp_loss": round(cp_loss),
                    "eval_before": round(eval_before, 1) if eval_before else 0,
                    "opponent": opponent
                })
    
    total = sum(counts.values())
    
    if total == 0:
        return {
            "when_winning": {"count": 0, "percentage": 0, "evidence": []},
            "when_equal": {"count": 0, "percentage": 0, "evidence": []},
            "when_losing": {"count": 0, "percentage": 0, "evidence": []},
            "total_blunders": 0,
            "insight": "No significant blunders detected. Great play!"
        }
    
    # Sort evidence by cp_loss (most costly first)
    for state in evidence:
        evidence[state] = sorted(evidence[state], key=lambda x: x["cp_loss"], reverse=True)
    
    result = {
        "when_winning": {
            "count": counts["winning"],
            "percentage": round(counts["winning"] / total * 100),
            "evidence": evidence["winning"]
        },
        "when_equal": {
            "count": counts["equal"],
            "percentage": round(counts["equal"] / total * 100),
            "evidence": evidence["equal"]
        },
        "when_losing": {
            "count": counts["losing"],
            "percentage": round(counts["losing"] / total * 100),
            "evidence": evidence["losing"]
        },
        "total_blunders": total
    }
    
    # Generate insight
    max_state = max(counts.items(), key=lambda x: x[1])
    if max_state[0] == "winning" and result["when_winning"]["percentage"] > 50:
        result["insight"] = f"You relax when winning. {result['when_winning']['percentage']}% of blunders happen in + positions."
        result["danger_zone"] = "winning"
    elif max_state[0] == "equal" and result["when_equal"]["percentage"] > 50:
        result["insight"] = f"Equal positions are tricky for you. {result['when_equal']['percentage']}% of blunders happen when even."
        result["danger_zone"] = "equal"
    elif max_state[0] == "losing" and result["when_losing"]["percentage"] > 50:
        result["insight"] = f"You struggle under pressure. {result['when_losing']['percentage']}% of blunders happen when behind."
        result["danger_zone"] = "losing"
    else:
        result["insight"] = "Your blunders are evenly distributed across game states."
        result["danger_zone"] = None
    
    return result


def get_mistake_heatmap(analyses: List[Dict]) -> Dict:
    """
    Generate heatmap data showing where mistakes occur on the board.
    
    Tracks:
    - Squares where material was lost
    - Squares where pieces were hanging
    - Pattern by board region (kingside/queenside/center)
    """
    if not analyses:
        return {
            "squares": {},
            "regions": {"kingside": 0, "queenside": 0, "center": 0},
            "hot_squares": [],
            "insight": "Not enough data yet."
        }
    
    square_counts = defaultdict(int)
    region_counts = {"kingside": 0, "queenside": 0, "center": 0}
    
    # Define regions
    kingside_files = ['f', 'g', 'h']
    queenside_files = ['a', 'b', 'c']
    center_files = ['d', 'e']
    
    for analysis in analyses[-15:]:
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        for move in move_evals:
            cp_loss = abs(move.get("cp_loss", 0))  # Already in centipawns
            if cp_loss < 50:  # Only count meaningful mistakes
                continue
            
            # Get the move played
            move_san = move.get("move", "")
            if not move_san:
                continue
            
            # Extract destination square from move (simplified)
            # Handle castling
            if move_san in ["O-O", "O-O-O"]:
                continue
            
            # Extract square - last 2 chars before any check/mate symbol
            clean_move = move_san.rstrip("+#")
            if len(clean_move) >= 2:
                dest_square = clean_move[-2:]
                if len(dest_square) == 2 and dest_square[0] in 'abcdefgh' and dest_square[1] in '12345678':
                    square_counts[dest_square] += 1
                    
                    # Categorize by region
                    file_char = dest_square[0]
                    if file_char in kingside_files:
                        region_counts["kingside"] += 1
                    elif file_char in queenside_files:
                        region_counts["queenside"] += 1
                    else:
                        region_counts["center"] += 1
    
    # Get hot squares (top 5)
    hot_squares = sorted(square_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Generate insight
    total = sum(region_counts.values())
    if total == 0:
        insight = "No significant mistakes to map."
    else:
        max_region = max(region_counts.items(), key=lambda x: x[1])
        pct = round(max_region[1] / total * 100) if total > 0 else 0
        insight = f"Most mistakes occur on the {max_region[0]} ({pct}% of errors)."
    
    return {
        "squares": dict(square_counts),
        "regions": region_counts,
        "hot_squares": [{"square": sq, "count": ct} for sq, ct in hot_squares],
        "insight": insight,
        "total_mapped": total
    }


def estimate_rating_impact(analyses: List[Dict], current_rating: int = 1000) -> Dict:
    """
    Estimate rating impact if dominant mistake type was fixed.
    
    Formula (simplified): 
    - Each 100cp average loss ≈ 50 rating points
    - Fixing dominant pattern could save 30-50% of that loss
    
    Returns motivational estimate: "Fixing X would save ~Y rating points"
    """
    if not analyses or len(analyses) < 5:
        return {
            "potential_gain": 0,
            "dominant_fix": None,
            "message": "Play more games for accurate rating impact estimate.",
            "confidence": "low"
        }
    
    weakness = get_dominant_weakness_ranking(analyses)
    
    if not weakness.get("rating_killer"):
        return {
            "potential_gain": 0,
            "dominant_fix": None,
            "message": "No dominant weakness detected.",
            "confidence": "low"
        }
    
    rk = weakness["rating_killer"]
    
    # Estimate: Each 100cp = ~15 rating points (conservative)
    # Assume fixing the pattern reduces it by 60%
    total_cp = rk["total_cp_loss"]
    games = weakness["games_analyzed"]
    
    avg_cp_per_game = total_cp / max(games, 1)
    potential_rating_save = round(avg_cp_per_game * 0.15 * 0.6)  # 60% improvement
    
    # Cap at reasonable bounds
    potential_rating_save = min(potential_rating_save, 150)
    potential_rating_save = max(potential_rating_save, 10) if total_cp > 100 else 0
    
    confidence = "high" if games >= 10 else "medium" if games >= 5 else "low"
    
    return {
        "potential_gain": potential_rating_save,
        "dominant_fix": rk["pattern"],
        "dominant_label": rk["label"],
        "message": f"Fixing '{rk['label']}' could save ~{potential_rating_save} rating points.",
        "confidence": confidence,
        "based_on_games": games
    }


def get_identity_profile(analyses: List[Dict]) -> Dict:
    """
    Generate identity-based label from mistake distribution.
    
    Examples:
    - "Aggressive but careless"
    - "Solid but passive"
    - "Tactical but impatient"
    - "Conversion struggler"
    """
    if not analyses:
        return {
            "profile": "unknown",
            "label": "Developing player",
            "description": "Play more games to reveal your chess identity."
        }
    
    # Aggregate pattern counts
    pattern_counts = defaultdict(int)
    total_mistakes = 0
    
    for analysis in analyses[-15:]:
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        
        for move in move_evals:
            mistake_type = move.get("mistake_type", "")
            if not mistake_type or mistake_type in ["good_move", "excellent_move"]:
                continue
            
            total_mistakes += 1
            for pattern_key, pattern_data in BEHAVIORAL_PATTERNS.items():
                if mistake_type in pattern_data["triggers"]:
                    pattern_counts[pattern_key] += 1
                    break
    
    pattern_counts["total"] = total_mistakes
    
    # Find matching identity profile
    for profile_key, profile_data in IDENTITY_PROFILES.items():
        if profile_data["condition"](pattern_counts):
            return {
                "profile": profile_key,
                "label": profile_data["label"],
                "description": profile_data["description"],
                "stats": dict(pattern_counts)
            }
    
    # Fallback
    return {
        "profile": "balanced",
        "label": "Balanced improver",
        "description": "No single glaring weakness - focus on consistency."
    }


def get_mission(analyses: List[Dict], current_missions: List[Dict] = None) -> Dict:
    """
    Generate a 10-game mission based on dominant weakness.
    
    Example:
    Mission: Discipline Builder
    Goal: Reduce hanging pieces below 1 per game in next 10 games.
    """
    weakness = get_dominant_weakness_ranking(analyses)
    
    if not weakness.get("rating_killer"):
        return {
            "name": "Foundation Builder",
            "goal": "Play 10 games with engine analysis",
            "target_metric": "games_analyzed",
            "target_value": 10,
            "progress": len(analyses) if analyses else 0,
            "reward": "Unlock your Chess DNA profile"
        }
    
    rk = weakness["rating_killer"]
    
    # Mission based on dominant weakness
    missions = {
        "attacks_before_checking_threats": {
            "name": "Threat Scanner",
            "goal": "Check opponent threats before each move",
            "target_metric": "hanging_pieces_per_game",
            "target_value": 1,
            "description": f"Reduce '{rk['label']}' mistakes to less than 1 per game"
        },
        "loses_focus_when_winning": {
            "name": "Closer",
            "goal": "Convert winning positions",
            "target_metric": "conversion_rate",
            "target_value": 80,
            "description": "Win 80% of games where you had +2 advantage"
        },
        "misses_tactical_opportunities": {
            "name": "Tactics Hunter",
            "goal": "Find more tactics in your games",
            "target_metric": "tactics_found_per_game",
            "target_value": 2,
            "description": "Execute at least 2 tactics per game"
        },
        "time_pressure_collapse": {
            "name": "Time Lord",
            "goal": "Manage your clock better",
            "target_metric": "time_blunders",
            "target_value": 0,
            "description": "No time pressure blunders in 10 games"
        }
    }
    
    mission_data = missions.get(rk["pattern"], {
        "name": "Skill Builder",
        "goal": f"Improve {rk['label']}",
        "target_metric": "cp_loss_reduction",
        "target_value": 50,
        "description": f"Reduce average centipawn loss from {rk['label']} by 50%"
    })
    
    return {
        **mission_data,
        "weakness_target": rk["pattern"],
        "games_required": 10,
        "games_completed": 0,
        "status": "active",
        "reward": "+50 rating potential"
    }


def check_milestones(analyses: List[Dict], user_stats: Dict = None) -> List[Dict]:
    """
    Check for achievement milestones.
    
    Returns list of newly achieved milestones.
    """
    milestones = []
    
    if not analyses:
        return milestones
    
    # Count stats
    total_games = len(analyses)
    clean_games = 0  # Games with no significant blunders
    consecutive_clean = 0
    max_consecutive_clean = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        has_blunder = False
        for move in move_evals:
            if abs(move.get("eval_drop", 0)) * 100 > 200:  # Major blunder
                has_blunder = True
                break
        
        if not has_blunder:
            clean_games += 1
            consecutive_clean += 1
            max_consecutive_clean = max(max_consecutive_clean, consecutive_clean)
        else:
            consecutive_clean = 0
    
    # Check milestones
    if clean_games >= 1 and (not user_stats or not user_stats.get("first_clean_game")):
        milestones.append({
            "id": "first_clean_game",
            "name": "Clean Sheet",
            "description": "First game with no major blunders!",
            "icon": "trophy",
            "rarity": "common"
        })
    
    if max_consecutive_clean >= 3 and (not user_stats or not user_stats.get("three_game_streak")):
        milestones.append({
            "id": "three_game_streak",
            "name": "On Fire",
            "description": "3 games in a row without major blunders!",
            "icon": "fire",
            "rarity": "rare"
        })
    
    if max_consecutive_clean >= 5 and (not user_stats or not user_stats.get("five_game_streak")):
        milestones.append({
            "id": "five_game_streak",
            "name": "Unstoppable",
            "description": "5 games in a row without major blunders!",
            "icon": "star",
            "rarity": "epic"
        })
    
    if total_games >= 10 and (not user_stats or not user_stats.get("ten_games_analyzed")):
        milestones.append({
            "id": "ten_games_analyzed",
            "name": "Data Driven",
            "description": "Analyzed 10 games - your Chess DNA is forming!",
            "icon": "chart",
            "rarity": "common"
        })
    
    return milestones


def get_focus_data(analyses: List[Dict], games: List[Dict] = None) -> Dict:
    """
    Get all data needed for the Focus page (stripped down Coach page).
    
    Returns:
    - ONE dominant weakness
    - ONE mission
    - ONE behavioral rule
    - ONE pattern reminder
    """
    weakness = get_dominant_weakness_ranking(analyses)
    mission = get_mission(analyses)
    identity = get_identity_profile(analyses)
    rating_impact = estimate_rating_impact(analyses)
    
    # Get the ONE thing to focus on
    if weakness.get("rating_killer"):
        rk = weakness["rating_killer"]
        focus = {
            "main_message": rk["message"],
            "fix": rk["fix"],
            "label": rk["label"],
            "pattern": rk["pattern"],
            "impact": f"~{rk['total_cp_loss']} centipawns lost"
        }
    else:
        focus = {
            "main_message": "Keep playing and analyzing games.",
            "fix": "Focus on not hanging pieces.",
            "label": "Building data",
            "pattern": None,
            "impact": None
        }
    
    return {
        "focus": focus,
        "mission": mission,
        "identity": identity,
        "rating_impact": rating_impact,
        "games_analyzed": len(analyses) if analyses else 0
    }


def get_journey_data(analyses: List[Dict], games: List[Dict] = None, badge_data: Dict = None) -> Dict:
    """
    Get all data needed for the Journey page (Progress page with hierarchy).
    
    Returns:
    - Weakness ranking (not equal badges)
    - Win-state analysis
    - Mistake heatmap
    - Identity profile
    - Trend data
    """
    return {
        "weakness_ranking": get_dominant_weakness_ranking(analyses, games),
        "win_state": get_win_state_analysis(analyses),
        "heatmap": get_mistake_heatmap(analyses),
        "identity": get_identity_profile(analyses),
        "milestones": check_milestones(analyses),
        "badges": badge_data,  # Pass through existing badge data
        "games_analyzed": len(analyses) if analyses else 0
    }


def get_lab_data(analysis: Dict) -> Dict:
    """
    Get data needed for the Lab page (detailed game analysis).
    
    Adds:
    - Core lesson of the game
    """
    core_lesson = get_core_lesson(analysis)
    
    return {
        "core_lesson": core_lesson,
        "analysis": analysis
    }
