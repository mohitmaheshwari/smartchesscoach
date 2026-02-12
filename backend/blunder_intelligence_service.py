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


def calculate_pattern_trends(analyses: List[Dict]) -> Dict:
    """
    Calculate improvement trends by comparing recent games vs older games.
    
    Compares:
    - Last 7 games (recent) vs Previous 7 games (older)
    - Returns trend direction and percentage change for each pattern
    
    Example output:
    {
        "loses_focus_when_winning": {
            "recent": 3,
            "previous": 7,
            "change": -57,
            "trend": "improving"
        }
    }
    """
    if len(analyses) < 10:
        return {"has_enough_data": False, "patterns": {}}
    
    # Split into recent and previous
    recent_analyses = analyses[-7:]  # Last 7 games
    previous_analyses = analyses[-14:-7]  # Previous 7 games
    
    def count_patterns(game_list):
        """Count pattern occurrences in a list of games."""
        pattern_counts = defaultdict(int)
        
        for analysis in game_list:
            sf_analysis = analysis.get("stockfish_analysis", {})
            move_evals = sf_analysis.get("move_evaluations", [])
            
            for move in move_evals:
                mistake_type = move.get("mistake_type", "")
                if not mistake_type:
                    mistake_type = infer_mistake_type_from_eval(move)
                
                if not mistake_type or mistake_type in ["good_move", "excellent_move"]:
                    continue
                
                for pattern_key, pattern_data in BEHAVIORAL_PATTERNS.items():
                    if mistake_type in pattern_data["triggers"]:
                        pattern_counts[pattern_key] += 1
                        break
        
        return pattern_counts
    
    recent_counts = count_patterns(recent_analyses)
    previous_counts = count_patterns(previous_analyses)
    
    # Calculate trends for each pattern
    all_patterns = set(recent_counts.keys()) | set(previous_counts.keys())
    pattern_trends = {}
    
    for pattern in all_patterns:
        recent = recent_counts.get(pattern, 0)
        previous = previous_counts.get(pattern, 0)
        
        if previous == 0:
            if recent == 0:
                change = 0
                trend = "stable"
            else:
                change = 100  # New pattern appeared
                trend = "worsening"
        else:
            change = round(((recent - previous) / previous) * 100)
            if change < -20:
                trend = "improving"
            elif change > 20:
                trend = "worsening"
            else:
                trend = "stable"
        
        pattern_trends[pattern] = {
            "recent": recent,
            "previous": previous,
            "change": change,
            "trend": trend,
            "label": BEHAVIORAL_PATTERNS.get(pattern, {}).get("short", pattern)
        }
    
    return {
        "has_enough_data": True,
        "recent_games": len(recent_analyses),
        "previous_games": len(previous_analyses),
        "patterns": pattern_trends
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


def get_mistake_heatmap(analyses: List[Dict], games: List[Dict] = None) -> Dict:
    """
    Generate heatmap data showing where mistakes occur on the board.
    
    Tracks:
    - Squares where material was lost
    - Squares where pieces were hanging
    - Pattern by board region (kingside/queenside/center)
    - EVIDENCE per square (clickable drill-down)
    """
    if not analyses:
        return {
            "squares": {},
            "regions": {"kingside": 0, "queenside": 0, "center": 0},
            "hot_squares": [],
            "square_evidence": {},
            "insight": "Not enough data yet."
        }
    
    # Build games lookup for opponent names
    games_lookup = {}
    if games:
        for g in games:
            games_lookup[g.get("game_id")] = g
    
    square_counts = defaultdict(int)
    square_evidence = defaultdict(list)  # Evidence per square
    region_counts = {"kingside": 0, "queenside": 0, "center": 0}
    
    # Define regions
    kingside_files = ['f', 'g', 'h']
    queenside_files = ['a', 'b', 'c']
    center_files = ['d', 'e']
    
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
            if cp_loss < 50:  # Only count meaningful mistakes
                continue
            
            # Get the move played
            move_san = move.get("move", "")
            if not move_san:
                continue
            
            # Handle castling
            if move_san in ["O-O", "O-O-O"]:
                continue
            
            # Extract square - last 2 chars before any check/mate symbol
            clean_move = move_san.rstrip("+#")
            if len(clean_move) >= 2:
                dest_square = clean_move[-2:]
                if len(dest_square) == 2 and dest_square[0] in 'abcdefgh' and dest_square[1] in '12345678':
                    square_counts[dest_square] += 1
                    
                    # Store evidence (limit 5 per square)
                    if len(square_evidence[dest_square]) < 5:
                        square_evidence[dest_square].append({
                            "game_id": game_id,
                            "move_number": move.get("move_number", 0),
                            "move_played": move_san,
                            "best_move": move.get("best_move", ""),
                            "fen_before": move.get("fen_before", ""),
                            "cp_loss": round(cp_loss),
                            "eval_before": round(move.get("eval_before", 0), 1),
                            "opponent": opponent,
                            "square": dest_square
                        })
                    
                    # Categorize by region
                    file_char = dest_square[0]
                    if file_char in kingside_files:
                        region_counts["kingside"] += 1
                    elif file_char in queenside_files:
                        region_counts["queenside"] += 1
                    else:
                        region_counts["center"] += 1
    
    # Sort evidence by cp_loss for each square
    for sq in square_evidence:
        square_evidence[sq] = sorted(square_evidence[sq], key=lambda x: x["cp_loss"], reverse=True)
    
    # Get hot squares (top 5) with evidence
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
        "hot_squares": [{"square": sq, "count": ct, "evidence": square_evidence.get(sq, [])} for sq, ct in hot_squares],
        "square_evidence": dict(square_evidence),
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
    - ONE dominant weakness with EVIDENCE
    - ONE mission
    - ONE behavioral rule
    - ONE pattern reminder
    """
    weakness = get_dominant_weakness_ranking(analyses, games)
    mission = get_mission(analyses)
    identity = get_identity_profile(analyses)
    rating_impact = estimate_rating_impact(analyses)
    
    # Get the ONE thing to focus on with evidence
    if weakness.get("rating_killer"):
        rk = weakness["rating_killer"]
        focus = {
            "main_message": rk["message"],
            "fix": rk["fix"],
            "label": rk["label"],
            "pattern": rk["pattern"],
            "impact": f"~{rk['total_cp_loss']} centipawns lost",
            "occurrences": rk["occurrences"],
            "evidence": rk.get("evidence", [])[:5]  # Top 5 examples
        }
    else:
        focus = {
            "main_message": "Keep playing and analyzing games.",
            "fix": "Focus on not hanging pieces.",
            "label": "Building data",
            "pattern": None,
            "impact": None,
            "occurrences": 0,
            "evidence": []
        }
    
    return {
        "focus": focus,
        "mission": mission,
        "identity": identity,
        "rating_impact": rating_impact,
        "games_analyzed": len(analyses) if analyses else 0
    }


def get_drill_positions(analyses: List[Dict], games: List[Dict] = None, 
                       pattern: str = None, state: str = None, limit: int = 5) -> List[Dict]:
    """
    Get positions for drill mode based on pattern or game state.
    
    Used for:
    - Pattern Drill Mode: Train specific weakness patterns
    - State Drill Mode: Practice positions when winning/equal/losing
    
    Args:
        analyses: List of game analyses
        games: List of games for opponent info
        pattern: Behavioral pattern to filter by (e.g., "attacks_before_checking_threats")
        state: Game state to filter by ("winning", "equal", "losing")
        limit: Max positions to return
    
    Returns positions where user was ahead (for practice) and made mistakes.
    
    NOTE: FEN positions may show post-move state (opponent's turn) due to how
    game analysis stores data. The drill mode handles this by showing choices
    rather than requiring piece dragging.
    """
    positions = []
    
    # Build games lookup
    games_lookup = {}
    if games:
        for g in games:
            games_lookup[g.get("game_id")] = g
    
    for analysis in analyses[-20:]:  # Look at last 20 games
        sf_analysis = analysis.get("stockfish_analysis", {})
        move_evals = sf_analysis.get("move_evaluations", [])
        game_id = analysis.get("game_id", "")
        
        if not move_evals:
            continue
        
        # Get opponent name and user color
        game_info = games_lookup.get(game_id, {})
        user_color = game_info.get("user_color", "white")
        opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
        opponent = opponent or "Opponent"
        
        for move in move_evals:
            cp_loss = abs(move.get("cp_loss", 0))
            eval_before = move.get("eval_before", 0)
            mistake_type = move.get("mistake_type", "")
            fen_before = move.get("fen_before", "")
            
            if not mistake_type:
                mistake_type = infer_mistake_type_from_eval(move)
            
            # Skip non-mistakes
            if cp_loss < 50 or mistake_type in ["good_move", "excellent_move"]:
                continue
            
            # Filter by state if specified
            if state:
                if state == "winning" and eval_before <= 1.5:
                    continue
                elif state == "equal" and (eval_before > 1.5 or eval_before < -1.5):
                    continue
                elif state == "losing" and eval_before >= -1.5:
                    continue
            
            # Filter by pattern if specified
            if pattern:
                matched = False
                pattern_data = BEHAVIORAL_PATTERNS.get(pattern, {})
                if mistake_type in pattern_data.get("triggers", []):
                    matched = True
                if not matched:
                    continue
            
            # For drill mode, prefer positions where user was winning (+2 or more)
            # These are the most instructive - "you had it, don't throw it away"
            if eval_before >= 2.0 or (state and state != "winning"):
                positions.append({
                    "game_id": game_id,
                    "move_number": move.get("move_number", 0),
                    "fen_before": fen_before,
                    "move_played": move.get("move", ""),
                    "best_move": move.get("best_move", ""),
                    "cp_loss": round(cp_loss),
                    "eval_before": round(eval_before, 1),
                    "opponent": opponent,
                    "mistake_type": mistake_type,
                    "user_color": user_color,
                    "pattern": pattern,
                    "state": "winning" if eval_before > 1.5 else "equal" if eval_before > -1.5 else "losing"
                })
            
            if len(positions) >= limit:
                break
        
        if len(positions) >= limit:
            break
    
    # Sort by eval_before descending (most winning positions first)
    positions = sorted(positions, key=lambda x: x["eval_before"], reverse=True)
    
    return positions[:limit]


def get_journey_data(analyses: List[Dict], games: List[Dict] = None, badge_data: Dict = None) -> Dict:
    """
    Get all data needed for the Journey page (Progress page with hierarchy).
    
    Returns:
    - Weakness ranking (not equal badges) with EVIDENCE
    - Win-state analysis with EVIDENCE
    - Mistake heatmap with EVIDENCE per square
    - Identity profile
    - Pattern trends (improvement tracking)
    - Milestones
    """
    weakness_ranking = get_dominant_weakness_ranking(analyses, games)
    pattern_trends = calculate_pattern_trends(analyses)
    
    # Merge trend data into weakness ranking
    if pattern_trends.get("has_enough_data") and weakness_ranking.get("ranking"):
        for item in weakness_ranking["ranking"]:
            pattern = item.get("pattern")
            if pattern and pattern in pattern_trends.get("patterns", {}):
                trend_info = pattern_trends["patterns"][pattern]
                item["trend"] = {
                    "recent": trend_info["recent"],
                    "previous": trend_info["previous"],
                    "change": trend_info["change"],
                    "direction": trend_info["trend"]
                }
    
    return {
        "weakness_ranking": weakness_ranking,
        "win_state": get_win_state_analysis(analyses, games),
        "heatmap": get_mistake_heatmap(analyses, games),  # Now includes evidence per square
        "identity": get_identity_profile(analyses),
        "pattern_trends": pattern_trends,  # NEW: Improvement tracking
        "milestones": check_milestones(analyses),
        "badges": badge_data,
        "games_analyzed": len(analyses) if analyses else 0
    }


def get_game_strategic_analysis(analysis: Dict, game: Dict = None) -> Dict:
    """
    Generate TRUE STRATEGIC ANALYSIS for a specific game.
    
    This is NOT about listing mistakes. It's about:
    1. What opening was played and what the correct PLAN should have been
    2. What pawn structure arose and what it dictates
    3. Key strategic themes (piece activity, weak squares, etc.)
    4. What to remember for future games with similar positions
    
    Uses evidence from the game to back up recommendations.
    """
    import chess
    
    if not analysis:
        return {"has_strategy": False}
    
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    # Get game metadata
    game_id = analysis.get("game_id", "")
    user_color = game.get("user_color", "white") if game else "white"
    opening_name = game.get("opening", "") if game else ""
    pgn = game.get("pgn", "") if game else ""
    
    result = {
        "has_strategy": True,
        "opening": {},
        "pawn_structure": {},
        "strategic_themes": [],
        "key_moments": [],
        "future_advice": []
    }
    
    # 1. OPENING ANALYSIS - What was the plan?
    result["opening"] = _analyze_opening_strategy(opening_name, user_color, pgn, move_evals)
    
    # 2. PAWN STRUCTURE ANALYSIS - What does it dictate?
    result["pawn_structure"] = _analyze_pawn_structure(move_evals, user_color)
    
    # 3. STRATEGIC THEMES - What patterns emerged?
    result["strategic_themes"] = _identify_strategic_themes(move_evals, user_color)
    
    # 4. KEY STRATEGIC MOMENTS - Important decision points (not mistakes)
    result["key_moments"] = _find_key_strategic_moments(move_evals, user_color)
    
    # 5. FUTURE ADVICE - What to remember
    result["future_advice"] = _generate_future_advice(result, game)
    
    return result


def _analyze_opening_strategy(opening_name: str, user_color: str, pgn: str, move_evals: List) -> Dict:
    """Analyze the opening: Plan + How you executed it + Where you deviated."""
    import chess
    
    # Import opening coaching data
    from opening_service import OPENING_COACHING
    
    opening_info = {
        "name": opening_name or "Unknown Opening",
        "your_color": user_color,
        "plan": "",
        "key_ideas": [],
        "theory_tip": "",
        "execution": {
            "verdict": "",
            "details": [],
            "critical_deviation": None
        }
    }
    
    # Find matching opening coaching
    matched_opening = None
    for name, coaching in OPENING_COACHING.items():
        if opening_name and name.lower() in opening_name.lower():
            matched_opening = coaching
            opening_info["name"] = name
            break
    
    if matched_opening:
        opening_info["plan"] = matched_opening.get("simple_plan", "")
        opening_info["key_ideas"] = matched_opening.get("must_know", [])[:3]
        opening_info["main_idea"] = matched_opening.get("main_idea", "")
        opening_info["theory_tip"] = matched_opening.get("practice_tip", "")
    else:
        # Generic opening advice based on color
        if user_color == "white":
            opening_info["plan"] = "Control center (e4/d4) → Develop knights → Develop bishops → Castle → Connect rooks"
            opening_info["key_ideas"] = [
                "As White, you have the first-move advantage - use it to control the center",
                "Develop pieces toward the center before starting attacks",
                "Complete development before move 10-12"
            ]
        else:
            opening_info["plan"] = "Counter center control → Develop pieces → Neutralize White's initiative → Castle → Look for counterplay"
            opening_info["key_ideas"] = [
                "As Black, focus on equalizing first, then look for chances",
                "Challenge White's center with ...d5 or ...c5 when ready",
                "Don't be passive - create your own threats"
            ]
    
    # ===== EXECUTION ANALYSIS =====
    opening_moves = [m for m in move_evals if m.get("move_number", 99) <= 12 and m.get("is_user_move", True)]
    
    if not opening_moves:
        return opening_info
    
    execution_details = []
    critical_deviation = None
    
    # Track key opening metrics
    castling_move = None
    development_count = 0  # How many unique pieces developed
    pawn_moves_count = 0
    center_pawn_played = False
    worst_opening_mistake = None
    
    developed_pieces = set()
    
    for move in opening_moves:
        move_san = move.get("move", "")
        move_num = move.get("move_number", 0)
        cp_loss = abs(move.get("cp_loss", 0))
        fen = move.get("fen_before", "")
        
        # Track worst mistake
        if worst_opening_mistake is None or cp_loss > worst_opening_mistake.get("cp_loss", 0):
            if cp_loss >= 50:
                worst_opening_mistake = {
                    "move_number": move_num,
                    "move": move_san,
                    "cp_loss": cp_loss,
                    "best_move": move.get("best_move", ""),
                    "fen": fen
                }
        
        # Detect castling
        if "O-O" in move_san or "0-0" in move_san:
            castling_move = move_num
        
        # Detect piece development vs pawn moves
        if move_san and len(move_san) >= 2:
            first_char = move_san[0]
            if first_char in "NBRQK":
                developed_pieces.add(first_char)
                development_count += 1
            elif first_char.islower():  # Pawn move
                pawn_moves_count += 1
                if 'd' in move_san or 'e' in move_san:
                    center_pawn_played = True
    
    # === Generate execution feedback ===
    
    # 1. Castling analysis
    if castling_move:
        if castling_move <= 8:
            execution_details.append(f"✓ Castled early (move {castling_move}) - good king safety")
        elif castling_move <= 12:
            execution_details.append(f"⚠ Castled on move {castling_move} - slightly late but acceptable")
    else:
        execution_details.append("✗ Did not castle in the opening - king safety was neglected")
    
    # 2. Development analysis
    unique_pieces_developed = len(developed_pieces)
    if unique_pieces_developed >= 3:
        execution_details.append(f"✓ Good development - {unique_pieces_developed} piece types developed")
    elif unique_pieces_developed >= 2:
        execution_details.append(f"⚠ Limited development - only {unique_pieces_developed} piece types moved")
    else:
        execution_details.append(f"✗ Poor development - only {unique_pieces_developed} piece type developed")
    
    # 3. Pawn moves vs piece moves
    if pawn_moves_count > development_count and pawn_moves_count > 3:
        execution_details.append(f"✗ Too many pawn moves ({pawn_moves_count}) instead of developing pieces")
    
    # 4. Critical deviation
    if worst_opening_mistake and worst_opening_mistake["cp_loss"] >= 100:
        critical_deviation = {
            "move_number": worst_opening_mistake["move_number"],
            "your_move": worst_opening_mistake["move"],
            "better_move": worst_opening_mistake["best_move"],
            "cp_loss": worst_opening_mistake["cp_loss"],
            "fen": worst_opening_mistake["fen"],
            "explanation": f"Move {worst_opening_mistake['move_number']}: You played {worst_opening_mistake['move']} instead of {worst_opening_mistake['best_move']}"
        }
    
    # 5. Overall verdict
    total_cp_lost = sum(abs(m.get("cp_loss", 0)) for m in opening_moves)
    if total_cp_lost < 50 and castling_move and castling_move <= 10:
        verdict = "Excellent opening execution - you followed the plan well"
    elif total_cp_lost < 100:
        verdict = "Solid opening - minor inaccuracies"
    elif total_cp_lost < 200:
        verdict = "Opening had issues - see where you deviated below"
    else:
        verdict = "Opening went poorly - significant deviations from the plan"
    
    opening_info["execution"] = {
        "verdict": verdict,
        "details": execution_details,
        "critical_deviation": critical_deviation
    }
    
    return opening_info


def _analyze_pawn_structure(move_evals: List, user_color: str) -> Dict:
    """Analyze the pawn structure: Plan + How you executed it."""
    import chess
    
    structure_info = {
        "type": "Standard",
        "your_plan": "",
        "opponent_plan": "",
        "key_squares": [],
        "pawn_breaks": [],
        "execution": {
            "verdict": "",
            "details": [],
            "critical_moment": None
        }
    }
    
    # Get a middlegame position (around move 15-20)
    mid_position = None
    mid_move_num = None
    for move in move_evals:
        if 15 <= move.get("move_number", 0) <= 25:
            fen = move.get("fen_before", move.get("fen", ""))
            if fen:
                try:
                    mid_position = chess.Board(fen)
                    mid_move_num = move.get("move_number", 0)
                    break
                except:
                    pass
    
    if not mid_position:
        for move in move_evals:
            fen = move.get("fen_before", move.get("fen", ""))
            if fen:
                try:
                    mid_position = chess.Board(fen)
                    mid_move_num = move.get("move_number", 0)
                    break
                except:
                    pass
    
    if not mid_position:
        return structure_info
    
    # Analyze pawn structure
    white_pawns = []
    black_pawns = []
    
    for square in chess.SQUARES:
        piece = mid_position.piece_at(square)
        if piece and piece.piece_type == chess.PAWN:
            file = chess.square_file(square)
            rank = chess.square_rank(square)
            if piece.color == chess.WHITE:
                white_pawns.append((file, rank))
            else:
                black_pawns.append((file, rank))
    
    # Detect common structures
    w_files = set(p[0] for p in white_pawns)
    b_files = set(p[0] for p in black_pawns)
    
    # Check for isolated pawns
    isolated_white = [f for f in w_files if f-1 not in w_files and f+1 not in w_files]
    isolated_black = [f for f in b_files if f-1 not in b_files and f+1 not in b_files]
    
    # Check for doubled pawns
    w_file_counts = {}
    b_file_counts = {}
    for f, r in white_pawns:
        w_file_counts[f] = w_file_counts.get(f, 0) + 1
    for f, r in black_pawns:
        b_file_counts[f] = b_file_counts.get(f, 0) + 1
    
    doubled_white = [f for f, c in w_file_counts.items() if c > 1]
    doubled_black = [f for f, c in b_file_counts.items() if c > 1]
    
    # ===== STRUCTURE TYPE + PLAN =====
    structure_plan = ""
    opponent_has_iqp = False
    user_has_iqp = False
    
    if 3 in isolated_white or 3 in isolated_black:  # d-file isolated pawn
        structure_info["type"] = "Isolated Queen's Pawn (IQP)"
        if (user_color == "white" and 3 in isolated_white) or (user_color == "black" and 3 in isolated_black):
            user_has_iqp = True
            structure_info["your_plan"] = "Attack! Use piece activity. Push the d-pawn when ready. Avoid endgames."
            structure_plan = "attack_with_iqp"
            structure_info["pawn_breaks"] = ["d4-d5 (or d5-d4) breakthrough at the right moment"]
            structure_info["key_squares"] = ["e5/c5 outpost squares for knights", "Open c and e files for rooks"]
        else:
            opponent_has_iqp = True
            structure_info["your_plan"] = "Blockade the isolated pawn. Trade pieces. Head for endgame."
            structure_plan = "blockade_iqp"
            structure_info["key_squares"] = ["d4/d5 blockade square for knight"]
    
    elif doubled_white or doubled_black:
        structure_info["type"] = "Doubled Pawns Structure"
        has_doubled = (user_color == "white" and doubled_white) or (user_color == "black" and doubled_black)
        if has_doubled:
            structure_info["your_plan"] = "Use the open file created. Your pieces have more activity to compensate."
            structure_plan = "compensate_doubled"
        else:
            structure_info["your_plan"] = "Target the doubled pawns in endgame. They're weak."
            structure_plan = "target_doubled"
    
    else:
        # Check for pawn majority
        kingside_w = len([p for p in white_pawns if p[0] >= 4])
        queenside_w = len([p for p in white_pawns if p[0] <= 3])
        kingside_b = len([p for p in black_pawns if p[0] >= 4])
        queenside_b = len([p for p in black_pawns if p[0] <= 3])
        
        if user_color == "white":
            if kingside_w > kingside_b:
                structure_info["type"] = "Kingside Pawn Majority"
                structure_info["your_plan"] = "Advance kingside pawns to create a passed pawn"
                structure_plan = "kingside_majority"
                structure_info["pawn_breaks"] = ["f4-f5 or g4-g5 to open lines"]
            elif queenside_w > queenside_b:
                structure_info["type"] = "Queenside Pawn Majority"
                structure_info["your_plan"] = "Push queenside pawns (a4-b4-c4 or similar)"
                structure_plan = "queenside_majority"
        else:
            if kingside_b > kingside_w:
                structure_info["type"] = "Kingside Pawn Majority"
                structure_info["your_plan"] = "Advance kingside pawns to create a passed pawn"
                structure_plan = "kingside_majority"
            elif queenside_b > queenside_w:
                structure_info["type"] = "Queenside Pawn Majority"
                structure_info["your_plan"] = "Push queenside pawns to create a passed pawn"
                structure_plan = "queenside_majority"
    
    if not structure_info["your_plan"]:
        structure_info["type"] = "Balanced Structure"
        structure_info["your_plan"] = "Focus on piece activity and look for tactical opportunities"
        structure_plan = "balanced"
    
    # ===== EXECUTION ANALYSIS =====
    execution_details = []
    critical_moment = None
    
    # Analyze middlegame moves (11-35) for structure execution
    middlegame_moves = [m for m in move_evals if 11 <= m.get("move_number", 0) <= 40 and m.get("is_user_move", True)]
    
    # Track execution metrics
    pieces_traded = 0
    major_pieces_remaining = True  # Assume true initially
    knight_on_blockade = False
    advantage_moments = []
    blunder_in_advantage = None
    
    for move in middlegame_moves:
        move_san = move.get("move", "")
        move_num = move.get("move_number", 0)
        eval_before = move.get("eval_before", 0)
        eval_after = move.get("eval_after", 0)
        cp_loss = abs(move.get("cp_loss", 0))
        
        # Adjust eval for black
        if user_color == "black":
            eval_before = -eval_before
            eval_after = -eval_after
        
        # Track when user had advantage
        if eval_before >= 1.5:
            advantage_moments.append({
                "move_number": move_num,
                "eval": round(eval_before, 1),
                "move": move_san,
                "cp_loss": cp_loss,
                "fen": move.get("fen_before", "")
            })
            
            # Check if they blundered while winning
            if cp_loss >= 150 and blunder_in_advantage is None:
                blunder_in_advantage = {
                    "move_number": move_num,
                    "eval_before": round(eval_before, 1),
                    "move": move_san,
                    "cp_loss": cp_loss,
                    "fen": move.get("fen_before", "")
                }
        
        # Track trades (captures that exchange)
        if 'x' in move_san:
            pieces_traded += 1
        
        # Check for knight on d4/d5 (blockade squares)
        if move_san and move_san[0] == 'N' and ('d4' in move_san or 'd5' in move_san):
            knight_on_blockade = True
    
    # ===== Generate Execution Feedback Based on Structure =====
    
    if structure_plan == "blockade_iqp":
        # They should have: traded pieces, put knight on blockade, headed to endgame
        if knight_on_blockade:
            execution_details.append("✓ Good! You placed a knight on the blockade square")
        else:
            execution_details.append("✗ Missed opportunity: No knight on d4/d5 to blockade the IQP")
        
        if pieces_traded >= 3:
            execution_details.append(f"✓ Good trading: {pieces_traded} exchanges toward endgame")
        else:
            execution_details.append(f"⚠ Limited trading ({pieces_traded} exchanges) - should trade more vs IQP")
    
    elif structure_plan == "attack_with_iqp":
        # They should have: kept pieces, attacked, avoided trades
        if pieces_traded <= 2:
            execution_details.append("✓ Good! Kept pieces on to maintain attacking chances")
        else:
            execution_details.append(f"⚠ Too many trades ({pieces_traded}) - IQP positions need pieces for attack")
    
    # Check for advantage conversion
    if advantage_moments:
        if blunder_in_advantage:
            execution_details.append(f"✗ Critical: You were +{blunder_in_advantage['eval_before']} on move {blunder_in_advantage['move_number']} but blundered")
            critical_moment = {
                "move_number": blunder_in_advantage["move_number"],
                "description": f"You had +{blunder_in_advantage['eval_before']} advantage",
                "your_move": blunder_in_advantage["move"],
                "what_went_wrong": f"Move {blunder_in_advantage['move_number']}: {blunder_in_advantage['move']} lost {blunder_in_advantage['cp_loss']}cp",
                "fen": blunder_in_advantage["fen"]
            }
        else:
            if len(advantage_moments) > 3:
                execution_details.append(f"⚠ You had advantage {len(advantage_moments)} times - did you simplify enough?")
    
    # Overall verdict
    if blunder_in_advantage:
        verdict = "Followed the structure plan but failed to convert advantage"
    elif len(execution_details) > 0 and all("✓" in d for d in execution_details):
        verdict = "Good structural understanding and execution"
    elif len(execution_details) > 0:
        verdict = "Partial execution - see details below"
    else:
        verdict = "No major structural violations"
    
    structure_info["execution"] = {
        "verdict": verdict,
        "details": execution_details,
        "critical_moment": critical_moment
    }
    
    return structure_info


def _identify_strategic_themes(move_evals: List, user_color: str) -> List[Dict]:
    """Identify strategic themes with SPECIFIC MOVE EVIDENCE."""
    themes = []
    
    # Collect evidence for each theme
    advantage_positions = []  # Moves where user had +1.5 or more
    disadvantage_positions = []  # Moves where user was -1.5 or worse
    endgame_moves = []  # Moves after move 35
    conversion_failures = []  # Moves where user blundered while winning
    
    for move in move_evals:
        if not move.get("is_user_move", True):
            continue
            
        eval_before = move.get("eval_before", 0)
        eval_after = move.get("eval_after", 0)
        move_num = move.get("move_number", 0)
        move_san = move.get("move", "")
        cp_loss = abs(move.get("cp_loss", 0))
        
        # Adjust eval for black
        if user_color == "black":
            eval_before = -eval_before
            eval_after = -eval_after
        
        # Track advantage positions
        if eval_before >= 1.5:
            advantage_positions.append({
                "move_number": move_num,
                "eval": round(eval_before, 1),
                "move": move_san,
                "cp_loss": cp_loss,
                "fen": move.get("fen_before", "")
            })
            
            # Check for conversion failure (blunder while winning)
            if cp_loss >= 100:
                conversion_failures.append({
                    "move_number": move_num,
                    "eval_before": round(eval_before, 1),
                    "eval_after": round(eval_after, 1),
                    "move": move_san,
                    "cp_loss": cp_loss,
                    "fen": move.get("fen_before", "")
                })
        
        # Track disadvantage positions
        if eval_before <= -0.5:
            disadvantage_positions.append({
                "move_number": move_num,
                "eval": round(eval_before, 1),
                "move": move_san,
                "fen": move.get("fen_before", "")
            })
        
        # Track endgame
        if move_num > 35:
            endgame_moves.append({
                "move_number": move_num,
                "eval": round(eval_before, 1),
                "move": move_san,
                "cp_loss": cp_loss
            })
    
    # ===== BUILD THEMES WITH EVIDENCE =====
    
    # 1. CONVERTING ADVANTAGE
    if advantage_positions:
        theme = {
            "theme": "Converting Advantage",
            "icon": "trending-up",
            "description": f"You had a winning position {len(advantage_positions)} times",
            "principle": "When ahead in material or position, simplify! Trade pieces (not pawns), reduce opponent's counterplay.",
            "remember": "The most important skill at higher levels is converting won positions."
        }
        
        # Add critical evidence
        if conversion_failures:
            worst_failure = max(conversion_failures, key=lambda x: x["cp_loss"])
            theme["critical_moment"] = {
                "move_number": worst_failure["move_number"],
                "description": f"You were +{worst_failure['eval_before']} but played {worst_failure['move']}",
                "eval_before": worst_failure["eval_before"],
                "your_move": worst_failure["move"],
                "impact": f"Lost {worst_failure['cp_loss']}cp - position went from winning to uncertain",
                "fen": worst_failure["fen"]
            }
            theme["verdict"] = f"❌ Failed to convert: Move {worst_failure['move_number']} threw away a +{worst_failure['eval_before']} position"
        else:
            # Find the best moment
            best_advantage = max(advantage_positions, key=lambda x: x["eval"])
            theme["critical_moment"] = {
                "move_number": best_advantage["move_number"],
                "description": f"Peak advantage: +{best_advantage['eval']}",
                "eval_before": best_advantage["eval"],
                "your_move": best_advantage["move"],
                "fen": best_advantage["fen"]
            }
            theme["verdict"] = "✓ Handled the advantage reasonably well"
        
        themes.append(theme)
    
    # 2. DEFENSIVE PLAY
    if disadvantage_positions:
        theme = {
            "theme": "Defensive Play",
            "icon": "shield",
            "description": f"You were under pressure for {len(disadvantage_positions)} moves",
            "principle": "When worse, create complications! Avoid trades, keep pieces active, look for counterplay.",
            "remember": "Defense is about making your opponent prove they can win."
        }
        
        # Find worst moment
        worst_moment = min(disadvantage_positions, key=lambda x: x["eval"])
        theme["critical_moment"] = {
            "move_number": worst_moment["move_number"],
            "description": f"Worst position: {worst_moment['eval']}",
            "eval_before": worst_moment["eval"],
            "your_move": worst_moment["move"],
            "fen": worst_moment["fen"]
        }
        
        themes.append(theme)
    
    # 3. ENDGAME TECHNIQUE
    if endgame_moves:
        endgame_cp_lost = sum(m["cp_loss"] for m in endgame_moves)
        theme = {
            "theme": "Endgame Technique",
            "icon": "target",
            "description": f"The game reached an endgame ({len(endgame_moves)} moves)",
            "principle": "In endgames: activate your king, create passed pawns, and calculate precisely.",
            "remember": "Endgame knowledge is the most efficient way to gain rating points."
        }
        
        if endgame_cp_lost > 200:
            worst_endgame = max(endgame_moves, key=lambda x: x["cp_loss"])
            theme["verdict"] = f"⚠ Endgame struggles: Lost ~{endgame_cp_lost}cp. Worst move: {worst_endgame['move_number']}"
        else:
            theme["verdict"] = "✓ Reasonable endgame play"
        
        themes.append(theme)
    
    # 4. PIECE ACTIVITY (always include)
    themes.append({
        "theme": "Piece Activity",
        "icon": "zap",
        "description": "The battle for piece coordination",
        "principle": "An active piece is worth more than a passive one. Before each move, ask: 'Which piece is my worst?'",
        "remember": "Improve your worst piece, then reassess."
    })
    
    return themes


def _find_key_strategic_moments(move_evals: List, user_color: str) -> List[Dict]:
    """Find key strategic decision points (not necessarily mistakes)."""
    import chess
    
    moments = []
    
    # Look for significant evaluation swings (>1.0)
    for i, move in enumerate(move_evals):
        if not move.get("is_user_move", True):
            continue
        
        eval_before = move.get("eval_before", 0)
        eval_after = move.get("eval_after", 0)
        move_num = move.get("move_number", 0)
        
        # Adjust for color
        if user_color == "black":
            eval_before = -eval_before
            eval_after = -eval_after
        
        # Significant positive swing - you gained advantage
        if eval_after - eval_before > 0.8:
            moments.append({
                "move_number": move_num,
                "type": "opportunity_seized",
                "description": f"Good decision! You improved your position significantly with {move.get('move', '')}",
                "fen": move.get("fen_before", ""),
                "icon": "check-circle"
            })
        
        # Critical moment - where game changed
        if move_num in [15, 20, 25, 30] and abs(eval_before) < 1.5:  # Roughly equal positions
            moments.append({
                "move_number": move_num,
                "type": "critical_moment",
                "description": f"Move {move_num} was a key moment - the position was balanced and required careful play",
                "fen": move.get("fen_before", ""),
                "icon": "alert-circle"
            })
    
    # Limit to 3 most important moments
    return moments[:3]


def _generate_future_advice(analysis_result: Dict, game: Dict) -> List[Dict]:
    """Generate actionable advice for future games."""
    advice = []
    
    opening_info = analysis_result.get("opening", {})
    structure_info = analysis_result.get("pawn_structure", {})
    themes = analysis_result.get("strategic_themes", [])
    
    # Opening-based advice
    if opening_info.get("how_you_did") and "issues" in opening_info.get("how_you_did", ""):
        advice.append({
            "category": "Opening Preparation",
            "icon": "book-open",
            "advice": f"Study the main ideas of the {opening_info.get('name', 'opening')}",
            "action": opening_info.get("plan", "Focus on development and center control")
        })
    
    # Structure-based advice
    if structure_info.get("type") and structure_info.get("type") != "Standard":
        advice.append({
            "category": "Pawn Structure",
            "icon": "grid",
            "advice": f"You played a {structure_info.get('type')} position",
            "action": structure_info.get("your_plan", "")
        })
    
    # Theme-based advice
    for theme in themes[:2]:
        advice.append({
            "category": theme.get("theme", "Strategy"),
            "icon": theme.get("icon", "lightbulb"),
            "advice": theme.get("remember", ""),
            "action": theme.get("principle", "")
        })
    
    return advice[:4]  # Limit to 4 pieces of advice


def get_lab_data(analysis: Dict, game: Dict = None) -> Dict:
    """
    Get data needed for the Lab page (detailed game analysis).
    
    Adds:
    - Core lesson of the game
    - Strategic analysis (opening, structure, themes)
    """
    core_lesson = get_core_lesson(analysis)
    strategic_analysis = get_game_strategic_analysis(analysis, game)
    
    return {
        "core_lesson": core_lesson,
        "strategic_analysis": strategic_analysis,
        "analysis": analysis
    }
