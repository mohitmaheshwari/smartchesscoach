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
        # Check if there's basic analysis even without detailed move evals
        has_basic_analysis = sf_analysis.get("accuracy") is not None or analysis.get("blunders") is not None
        
        if has_basic_analysis:
            accuracy = sf_analysis.get("accuracy", 0)
            if accuracy >= 90:
                return {
                    "lesson": "Excellent accuracy! Consider re-analyzing for detailed move-by-move insights.",
                    "pattern": "clean_game",
                    "behavioral_fix": None,
                    "severity": "none"
                }
            return {
                "lesson": "Re-analyze this game for detailed move-by-move correction insights.",
                "pattern": "needs_detailed_analysis",
                "behavioral_fix": None,
                "severity": "unknown"
            }
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


def get_opening_guidance(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Opening Guidance - Direction, not labels.
    
    Design Rules:
    1. Don't base on win rate alone - use blunder frequency, eval drops, conversion
    2. "Pause For Now" instead of "Don't Play" - coach tone, not dictator
    3. Minimum 4-5 games per opening before showing guidance
    4. Update slowly - stable guidance builds trust
    
    Returns:
    {
        "as_white": {
            "working_well": [{"name": "Italian Game", "reason": "..."}],
            "pause_for_now": [{"name": "King's Gambit", "reason": "..."}]
        },
        "as_black": {
            "working_well": [...],
            "pause_for_now": [...]
        },
        "sample_size": 15,
        "ready": True/False
    }
    """
    
    MIN_GAMES_PER_OPENING = 4
    
    if not analyses or not games or len(analyses) < 10:
        return {
            "as_white": {"working_well": [], "pause_for_now": []},
            "as_black": {"working_well": [], "pause_for_now": []},
            "sample_size": len(analyses) if analyses else 0,
            "ready": False,
            "message": "Play more analyzed games to unlock opening guidance"
        }
    
    # ECO code to opening name mapping (common openings)
    ECO_TO_NAME = {
        "A00": "Uncommon Opening",
        "A04": "Reti Opening",
        "A06": "Reti Opening",
        "A10": "English Opening",
        "A20": "English Opening",
        "A40": "Queen's Pawn",
        "A45": "Indian Game",
        "A46": "Indian Game",
        "B00": "Uncommon Defense",
        "B01": "Scandinavian Defense",
        "B02": "Alekhine Defense",
        "B06": "Modern Defense",
        "B07": "Pirc Defense",
        "B10": "Caro-Kann Defense",
        "B12": "Caro-Kann Defense",
        "B20": "Sicilian Defense",
        "B21": "Sicilian Defense",
        "B22": "Sicilian Defense",
        "B23": "Sicilian Defense",
        "B27": "Sicilian Defense",
        "B30": "Sicilian Defense",
        "B40": "Sicilian Defense",
        "B50": "Sicilian Defense",
        "C00": "French Defense",
        "C01": "French Defense",
        "C02": "French Defense",
        "C10": "French Defense",
        "C20": "King's Pawn Game",
        "C21": "Center Game",
        "C23": "Bishop's Opening",
        "C24": "Bishop's Opening",
        "C25": "Vienna Game",
        "C30": "King's Gambit",
        "C40": "King's Knight Opening",
        "C42": "Petrov Defense",
        "C44": "Scotch Game",
        "C45": "Scotch Game",
        "C46": "Three Knights Game",
        "C47": "Four Knights Game",
        "C48": "Four Knights Game",
        "C50": "Italian Game",
        "C51": "Italian Game",
        "C52": "Italian Game",
        "C53": "Italian Game",
        "C54": "Italian Game",
        "C55": "Italian Game",
        "C57": "Italian Game",
        "C60": "Ruy Lopez",
        "C65": "Ruy Lopez",
        "C70": "Ruy Lopez",
        "C78": "Ruy Lopez",
        "C80": "Ruy Lopez",
        "D00": "Queen's Pawn Game",
        "D02": "London System",
        "D04": "Queen's Pawn Game",
        "D06": "Queen's Gambit",
        "D10": "Queen's Gambit",
        "D20": "Queen's Gambit Accepted",
        "D30": "Queen's Gambit Declined",
        "D35": "Queen's Gambit Declined",
        "E00": "Indian Defense",
        "E10": "Indian Defense",
        "E20": "Nimzo-Indian Defense",
        "E60": "King's Indian Defense",
        "E70": "King's Indian Defense",
        "E90": "King's Indian Defense"
    }
    
    def get_opening_name(eco_code: str, pgn: str = "") -> str:
        """Convert ECO code to readable name, or extract from PGN"""
        # First try to get from PGN Opening tag
        if pgn:
            import re
            match = re.search(r'\[Opening "([^"]+)"\]', pgn)
            if match:
                full_name = match.group(1)
                # Take base name (before variations)
                base = full_name.split(":")[0].split(",")[0].strip()
                if len(base) >= 4:
                    return base
        
        # Fall back to ECO mapping
        if eco_code:
            # Try exact match first
            if eco_code in ECO_TO_NAME:
                return ECO_TO_NAME[eco_code]
            # Try prefix match (B01 -> B0 -> B)
            for prefix_len in [2, 1]:
                prefix = eco_code[:prefix_len]
                for code, name in ECO_TO_NAME.items():
                    if code.startswith(prefix):
                        return name
        
        return eco_code if eco_code else "Unknown"
    
    # Build opening stats from games + analyses
    opening_stats = defaultdict(lambda: {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "blunders_first_15": 0,
        "mistakes_first_15": 0,
        "total_moves_first_15": 0,
        "eval_drops": 0,  # Significant eval drops (>1.5)
        "conversions_attempted": 0,
        "conversions_succeeded": 0,
        "avg_accuracy": 0,
        "accuracy_sum": 0,
        "color": None
    })
    
    # Map game_id to analysis for quick lookup
    analysis_map = {}
    for analysis in analyses:
        gid = analysis.get("game_id")
        if gid:
            analysis_map[gid] = analysis
    
    # Process each game
    for game in games:
        game_id = game.get("game_id")
        eco_code = game.get("opening", "").strip()
        user_color = game.get("user_color", "white")
        pgn = game.get("pgn", "")
        result = game.get("result", "")
        
        if not opening or opening in ["Unknown", "?", ""]:
            # Try to extract from PGN
            pgn = game.get("pgn", "")
            import re
            opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
            if opening_match:
                opening = opening_match.group(1)
            else:
                continue  # Skip games without opening info
        
        # Normalize opening name (take first part before variation)
        opening_base = opening.split(":")[0].split(",")[0].strip()
        if len(opening_base) < 3:
            continue
        
        key = f"{user_color}_{opening_base}"
        stats = opening_stats[key]
        stats["name"] = opening_base
        stats["color"] = user_color
        stats["games"] += 1
        
        # Win/loss/draw
        if result == "1-0":
            if user_color == "white":
                stats["wins"] += 1
            else:
                stats["losses"] += 1
        elif result == "0-1":
            if user_color == "black":
                stats["wins"] += 1
            else:
                stats["losses"] += 1
        else:
            stats["draws"] += 1
        
        # Get analysis data
        analysis = analysis_map.get(game_id)
        if analysis:
            sf_analysis = analysis.get("stockfish_analysis", {})
            accuracy = sf_analysis.get("accuracy", 0)
            if accuracy > 0:
                stats["accuracy_sum"] += accuracy
            
            # Analyze first 15 moves
            move_evals = sf_analysis.get("move_evaluations", [])
            first_15_user_moves = []
            prev_eval = 0
            
            for move in move_evals[:30]:  # First 30 half-moves = 15 full moves
                move_num = move.get("move_number", 0)
                is_user = move.get("is_user_move", False)
                
                if move_num <= 15 and is_user:
                    first_15_user_moves.append(move)
                    classification = move.get("classification", "")
                    
                    if classification == "blunder":
                        stats["blunders_first_15"] += 1
                    elif classification in ["mistake", "serious_mistake"]:
                        stats["mistakes_first_15"] += 1
                    
                    # Check for significant eval drops
                    eval_after = move.get("eval_after", 0)
                    cp_loss = abs(move.get("cp_loss", 0))
                    if cp_loss > 150:  # Significant drop
                        stats["eval_drops"] += 1
                    
                    stats["total_moves_first_15"] += 1
            
            # Conversion analysis
            # Did user have a winning position (+2 or more)?
            had_winning_pos = False
            converted = False
            
            for i, move in enumerate(move_evals):
                eval_after = move.get("eval_after", 0)
                is_user = move.get("is_user_move", False)
                
                # User had +2 or better (from their perspective)
                if user_color == "white" and eval_after >= 200:
                    had_winning_pos = True
                elif user_color == "black" and eval_after <= -200:
                    had_winning_pos = True
            
            if had_winning_pos:
                stats["conversions_attempted"] += 1
                if (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1"):
                    stats["conversions_succeeded"] += 1
    
    # Calculate scores for each opening
    def calculate_opening_score(stats: Dict) -> Tuple[float, str]:
        """
        Score opening performance. Higher = better.
        Returns (score, reason)
        
        Factors:
        - Blunder rate in first 15 moves (40% weight)
        - Eval drop rate (20% weight)  
        - Conversion rate (20% weight)
        - Accuracy (20% weight)
        """
        if stats["games"] < MIN_GAMES_PER_OPENING:
            return (0, "insufficient_data")
        
        n = stats["games"]
        
        # Blunder rate in opening (lower is better)
        moves_15 = stats["total_moves_first_15"] or 1
        blunder_rate = stats["blunders_first_15"] / moves_15
        blunder_score = max(0, 1 - (blunder_rate * 10))  # 10 blunders per 100 moves = 0 score
        
        # Mistake rate in opening
        mistake_rate = stats["mistakes_first_15"] / moves_15
        mistake_score = max(0, 1 - (mistake_rate * 5))
        
        # Eval drop rate (lower is better)
        eval_drop_rate = stats["eval_drops"] / n
        eval_drop_score = max(0, 1 - (eval_drop_rate * 0.5))
        
        # Conversion rate (higher is better)
        if stats["conversions_attempted"] > 0:
            conversion_rate = stats["conversions_succeeded"] / stats["conversions_attempted"]
        else:
            conversion_rate = 0.5  # Neutral if no conversion situations
        
        # Average accuracy
        if stats["games"] > 0 and stats["accuracy_sum"] > 0:
            avg_accuracy = stats["accuracy_sum"] / n
            accuracy_score = avg_accuracy / 100
        else:
            accuracy_score = 0.7  # Neutral
        
        # Weighted score
        score = (
            blunder_score * 0.35 +
            mistake_score * 0.15 +
            eval_drop_score * 0.20 +
            conversion_rate * 0.15 +
            accuracy_score * 0.15
        )
        
        # Generate reason
        if blunder_rate > 0.15:
            reason = "High tactical losses in first 15 moves"
        elif mistake_rate > 0.2:
            reason = "Frequent early mistakes"
        elif eval_drop_rate > 1.5:
            reason = "Unstable positions leading to drops"
        elif conversion_rate < 0.4 and stats["conversions_attempted"] >= 2:
            reason = "Difficulty converting advantages"
        elif blunder_rate < 0.05 and mistake_rate < 0.1:
            reason = "Stable positions. Low early mistakes."
        elif conversion_rate > 0.7 and stats["conversions_attempted"] >= 2:
            reason = "Strong conversion rate"
        elif accuracy_score > 0.75:
            reason = "Consistent development. Good accuracy."
        else:
            reason = "Solid middlegame performance"
        
        return (score, reason)
    
    # Categorize openings
    white_openings = []
    black_openings = []
    
    for key, stats in opening_stats.items():
        if stats["games"] < MIN_GAMES_PER_OPENING:
            continue
        
        score, reason = calculate_opening_score(stats)
        stats["score"] = score
        stats["reason"] = reason
        
        opening_data = {
            "name": stats["name"],
            "games": stats["games"],
            "score": round(score, 2),
            "reason": reason,
            "win_rate": round(stats["wins"] / stats["games"] * 100) if stats["games"] > 0 else 0,
            "blunders_per_game": round(stats["blunders_first_15"] / stats["games"], 1)
        }
        
        if stats["color"] == "white":
            white_openings.append(opening_data)
        else:
            black_openings.append(opening_data)
    
    # Sort and categorize
    def categorize(openings: List[Dict]) -> Dict:
        if not openings:
            return {"working_well": [], "pause_for_now": []}
        
        # Sort by score descending
        sorted_openings = sorted(openings, key=lambda x: x["score"], reverse=True)
        
        working_well = []
        pause_for_now = []
        
        for op in sorted_openings:
            if op["score"] >= 0.6:
                working_well.append({
                    "name": op["name"],
                    "reason": op["reason"],
                    "games": op["games"]
                })
            elif op["score"] < 0.45:
                pause_for_now.append({
                    "name": op["name"],
                    "reason": op["reason"],
                    "games": op["games"]
                })
        
        # Limit to top 2 each
        return {
            "working_well": working_well[:2],
            "pause_for_now": pause_for_now[:2]
        }
    
    white_guidance = categorize(white_openings)
    black_guidance = categorize(black_openings)
    
    has_guidance = (
        len(white_guidance["working_well"]) > 0 or 
        len(white_guidance["pause_for_now"]) > 0 or
        len(black_guidance["working_well"]) > 0 or
        len(black_guidance["pause_for_now"]) > 0
    )
    
    return {
        "as_white": white_guidance,
        "as_black": black_guidance,
        "sample_size": len(analyses),
        "ready": has_guidance,
        "message": None if has_guidance else "Play more games with varied openings to unlock guidance"
    }

def get_mission(analyses: List[Dict], current_missions: List[Dict] = None, user_rating: int = None) -> Dict:
    """
    MISSION ENGINE - 3 Layer Architecture
    
    Layer 1: Weakness Type → Determines THEME
    Layer 2: Rating Tier → Adjusts DIFFICULTY  
    Layer 3: Mission Difficulty → Actual challenge
    
    Key Principle: Weakness > Rating
    A 2000 player who relaxes when winning gets "Finish Strong" mission,
    but with harder criteria than a 1200 player.
    
    Rating Bands:
    - 600-1000: Basic blunder elimination (simple, direct)
    - 1000-1600: Pattern correction (slightly strategic)
    - 1600-2000: Efficiency & conversion (precision-based)
    - 2000+: Marginal gains (serious metrics)
    """
    
    # Calculate stats from recent games
    recent_analyses = analyses[-10:] if analyses else []
    
    if len(recent_analyses) < 3:
        return {
            "name": "First Steps",
            "goal": "Analyze 3 games to unlock your discipline focus",
            "instruction": "Import and analyze your recent games",
            "target": 3,
            "progress": len(recent_analyses),
            "rating_tier": "starter",
            "status": "active"
        }
    
    # Estimate rating if not provided (from game data or default)
    rating = user_rating or 1200  # Default to intermediate
    
    # Determine rating tier
    if rating < 1000:
        tier = "beginner"  # 600-1000
    elif rating < 1600:
        tier = "intermediate"  # 1000-1600
    elif rating < 2000:
        tier = "advanced"  # 1600-2000
    else:
        tier = "expert"  # 2000+
    
    # Calculate behavioral metrics
    total_blunders = 0
    total_mistakes = 0
    total_inaccuracies = 0
    total_cp_loss = 0
    games_with_hung_pieces = 0
    total_accuracy = 0
    accuracy_count = 0
    
    for analysis in recent_analyses:
        blunders = analysis.get("blunders", 0)
        mistakes = analysis.get("mistakes", 0)
        inaccuracies = analysis.get("inaccuracies", 0)
        total_blunders += blunders
        total_mistakes += mistakes
        total_inaccuracies += inaccuracies
        
        sf_analysis = analysis.get("stockfish_analysis", {})
        accuracy = sf_analysis.get("accuracy", 0)
        if accuracy > 0:
            total_accuracy += accuracy
            accuracy_count += 1
        
        avg_cp = sf_analysis.get("avg_cp_loss", 0)
        total_cp_loss += avg_cp
        
        # Check for hanging pieces
        moves = sf_analysis.get("move_evaluations", [])
        for move in moves:
            if move.get("classification") == "blunder" and abs(move.get("cp_loss", 0)) > 300:
                games_with_hung_pieces += 1
                break
    
    n = len(recent_analyses)
    avg_blunders = total_blunders / n
    avg_mistakes = total_mistakes / n
    avg_inaccuracies = total_inaccuracies / n
    avg_accuracy = total_accuracy / accuracy_count if accuracy_count > 0 else 70
    avg_cp_loss = total_cp_loss / n
    hung_piece_rate = games_with_hung_pieces / n
    
    # Get dominant weakness
    weakness = get_dominant_weakness_ranking(analyses)
    rk = weakness.get("rating_killer", {})
    pattern = rk.get("pattern", "")
    
    # ==================== MISSION TEMPLATES BY WEAKNESS × RATING ====================
    
    mission_templates = {
        # WEAKNESS: Hanging pieces / One-move blunders
        "hanging_pieces": {
            "beginner": {
                "name": "No Free Pieces",
                "goal": "Play 3 games without hanging a piece",
                "instruction": "Before every move, ask: Is this piece protected?",
                "check_rule": "No blunders with cp_loss > 300",
                "target": 3
            },
            "intermediate": {
                "name": "Piece Safety",
                "goal": "Play 5 games without giving away material",
                "instruction": "Before moving, check if your piece is defended",
                "check_rule": "No blunders with cp_loss > 200",
                "target": 5
            },
            "advanced": {
                "name": "Material Discipline",
                "goal": "Play 5 games with no material blunders",
                "instruction": "Visualize opponent responses before committing",
                "check_rule": "No blunders with cp_loss > 150",
                "target": 5
            },
            "expert": {
                "name": "Tactical Precision",
                "goal": "Play 5 games with no tactical oversights",
                "instruction": "Calculate all forcing lines before playing",
                "check_rule": "No blunders with cp_loss > 100",
                "target": 5
            }
        },
        
        # WEAKNESS: High blunder count (general)
        "high_blunders": {
            "beginner": {
                "name": "Scan Before Move",
                "goal": "Play 3 games with zero blunders",
                "instruction": "Every move, check: Checks, Captures, Threats",
                "check_rule": "0 blunders in game",
                "target": 3
            },
            "intermediate": {
                "name": "Clean Games",
                "goal": "Play 5 games with at most 1 blunder each",
                "instruction": "Take your time. No rushed moves.",
                "check_rule": "≤1 blunder per game",
                "target": 5
            },
            "advanced": {
                "name": "Blunder-Free Streak",
                "goal": "Play 3 consecutive games with 0 blunders",
                "instruction": "Double-check every move before playing",
                "check_rule": "0 blunders for 3 games in a row",
                "target": 3
            },
            "expert": {
                "name": "Zero Tolerance",
                "goal": "Play 5 games with 0 blunders total",
                "instruction": "Maintain focus throughout the game",
                "check_rule": "0 blunders across all 5 games",
                "target": 5
            }
        },
        
        # WEAKNESS: Loses focus when winning
        "loses_focus_when_winning": {
            "beginner": {
                "name": "Finish Strong",
                "goal": "Convert 3 winning positions without blundering",
                "instruction": "When ahead, don't rush. Keep checking threats.",
                "check_rule": "Win from +2 or better without blunder",
                "target": 3
            },
            "intermediate": {
                "name": "Close It Out",
                "goal": "Convert 5 winning positions cleanly",
                "instruction": "Trade pieces when ahead. Simplify to win.",
                "check_rule": "Win from +1.5 without eval drop >1.5",
                "target": 5
            },
            "advanced": {
                "name": "Winning Technique",
                "goal": "Convert 90% of winning positions in 5 games",
                "instruction": "Maintain pressure. Don't let opponent back in.",
                "check_rule": "Convert 90%+ of +1.5 positions",
                "target": 5
            },
            "expert": {
                "name": "Conversion Mastery",
                "goal": "Maintain eval above +1 for 10 moves when winning",
                "instruction": "Keep steady pressure. No eval drops.",
                "check_rule": "No eval drop >0.5 in winning positions",
                "target": 5
            }
        },
        
        # WEAKNESS: Misses opponent threats
        "attacks_before_checking_threats": {
            "beginner": {
                "name": "Threat Check",
                "goal": "Play 3 games without walking into a tactic",
                "instruction": "Every move, ask: What is opponent threatening?",
                "check_rule": "No losses to simple tactics",
                "target": 3
            },
            "intermediate": {
                "name": "Defensive Awareness",
                "goal": "Play 5 games with no tactical oversights",
                "instruction": "Check all opponent checks and captures first",
                "check_rule": "No blunders from missed threats",
                "target": 5
            },
            "advanced": {
                "name": "Threat Recognition",
                "goal": "Identify all threats for 5 games",
                "instruction": "Before your move, list opponent's best responses",
                "check_rule": "No eval drops >1.5 from missed tactics",
                "target": 5
            },
            "expert": {
                "name": "Prophylaxis Master",
                "goal": "Prevent all opponent threats in 5 games",
                "instruction": "Think prophylactically - what does opponent want?",
                "check_rule": "No tactical losses, maintain eval stability",
                "target": 5
            }
        },
        
        # WEAKNESS: Time pressure collapse
        "time_pressure_collapse": {
            "beginner": {
                "name": "Clock Discipline",
                "goal": "Play 3 games without time-pressure blunders",
                "instruction": "Use your time wisely. Don't rush.",
                "check_rule": "No blunders with <2 min on clock",
                "target": 3
            },
            "intermediate": {
                "name": "Time Management",
                "goal": "Play 5 games with at least 1 min remaining",
                "instruction": "Move faster in the opening. Save time for tactics.",
                "check_rule": "End game with >60 seconds",
                "target": 5
            },
            "advanced": {
                "name": "Clock Control",
                "goal": "Play 5 games with consistent move times",
                "instruction": "Avoid long thinks. Trust your preparation.",
                "check_rule": "No extreme time usage patterns",
                "target": 5
            },
            "expert": {
                "name": "Time Efficiency",
                "goal": "Improve move-time consistency in critical positions",
                "instruction": "Allocate time based on position complexity",
                "check_rule": "Efficient time use in complex positions",
                "target": 5
            }
        },
        
        # WEAKNESS: Misses tactical opportunities
        "misses_tactical_opportunities": {
            "beginner": {
                "name": "See More",
                "goal": "Play 3 games with 75%+ accuracy",
                "instruction": "Look for checks and captures before each move",
                "check_rule": "Accuracy ≥75%",
                "target": 3
            },
            "intermediate": {
                "name": "Tactics Finder",
                "goal": "Play 5 games with 80%+ accuracy",
                "instruction": "Every position, ask: Is there a tactic here?",
                "check_rule": "Accuracy ≥80%",
                "target": 5
            },
            "advanced": {
                "name": "Tactical Sharpness",
                "goal": "Play 5 games with 85%+ accuracy",
                "instruction": "Calculate all forcing sequences",
                "check_rule": "Accuracy ≥85%",
                "target": 5
            },
            "expert": {
                "name": "Tactical Precision",
                "goal": "Play 5 games with 90%+ accuracy",
                "instruction": "Find the best move in critical positions",
                "check_rule": "Accuracy ≥90%",
                "target": 5
            }
        },
        
        # WEAKNESS: Poor accuracy (general improvement)
        "low_accuracy": {
            "beginner": {
                "name": "Better Moves",
                "goal": "Play 3 games with fewer than 3 blunders each",
                "instruction": "Take 10 seconds before every move",
                "check_rule": "<3 blunders per game",
                "target": 3
            },
            "intermediate": {
                "name": "Quality Over Speed",
                "goal": "Play 5 games with 75%+ accuracy",
                "instruction": "Think first, move second",
                "check_rule": "Accuracy ≥75%",
                "target": 5
            },
            "advanced": {
                "name": "Precision Play",
                "goal": "Improve accuracy to 82%+ for 5 games",
                "instruction": "Focus on move quality over quick wins",
                "check_rule": "Accuracy ≥82%",
                "target": 5
            },
            "expert": {
                "name": "Elite Accuracy",
                "goal": "Maintain 88%+ accuracy for 5 games",
                "instruction": "Every move should be engine-approved quality",
                "check_rule": "Accuracy ≥88%",
                "target": 5
            }
        },
        
        # WEAKNESS: High centipawn loss
        "high_cp_loss": {
            "beginner": {
                "name": "Fewer Mistakes",
                "goal": "Play 3 games with avg cp loss under 80",
                "instruction": "Avoid obvious mistakes",
                "check_rule": "Avg cp loss <80",
                "target": 3
            },
            "intermediate": {
                "name": "Reduce Errors",
                "goal": "Play 5 games with avg cp loss under 50",
                "instruction": "Think longer on critical moves",
                "check_rule": "Avg cp loss <50",
                "target": 5
            },
            "advanced": {
                "name": "Tight Play",
                "goal": "Play 5 games with avg cp loss under 35",
                "instruction": "Every move counts. No slack.",
                "check_rule": "Avg cp loss <35",
                "target": 5
            },
            "expert": {
                "name": "Marginal Gains",
                "goal": "Play 5 games with avg cp loss under 25",
                "instruction": "Optimize every decision",
                "check_rule": "Avg cp loss <25",
                "target": 5
            }
        }
    }
    
    # ==================== MISSION SELECTION LOGIC ====================
    
    # Priority 1: Hanging pieces (most critical for beginners)
    if hung_piece_rate > 0.4 and tier in ["beginner", "intermediate"]:
        weakness_key = "hanging_pieces"
    
    # Priority 2: High blunder rate
    elif avg_blunders > 2 and tier == "beginner":
        weakness_key = "high_blunders"
    elif avg_blunders > 1.5 and tier == "intermediate":
        weakness_key = "high_blunders"
    elif avg_blunders > 0.5 and tier in ["advanced", "expert"]:
        weakness_key = "high_blunders"
    
    # Priority 3: Pattern-based weakness from analysis
    elif pattern == "loses_focus_when_winning":
        weakness_key = "loses_focus_when_winning"
    elif pattern == "attacks_before_checking_threats":
        weakness_key = "attacks_before_checking_threats"
    elif pattern == "time_pressure_collapse":
        weakness_key = "time_pressure_collapse"
    elif pattern == "misses_tactical_opportunities":
        weakness_key = "misses_tactical_opportunities"
    
    # Priority 4: Accuracy-based weakness
    elif avg_accuracy < 65 and tier == "beginner":
        weakness_key = "low_accuracy"
    elif avg_accuracy < 75 and tier == "intermediate":
        weakness_key = "low_accuracy"
    elif avg_accuracy < 82 and tier == "advanced":
        weakness_key = "low_accuracy"
    elif avg_accuracy < 88 and tier == "expert":
        weakness_key = "low_accuracy"
    
    # Priority 5: CP loss based
    elif avg_cp_loss > 60 and tier == "beginner":
        weakness_key = "high_cp_loss"
    elif avg_cp_loss > 40 and tier in ["intermediate", "advanced"]:
        weakness_key = "high_cp_loss"
    elif avg_cp_loss > 25 and tier == "expert":
        weakness_key = "high_cp_loss"
    
    # Default: General improvement
    else:
        weakness_key = "low_accuracy"
    
    # Get mission template
    template = mission_templates.get(weakness_key, mission_templates["low_accuracy"])
    mission = template.get(tier, template["intermediate"])
    
    return {
        **mission,
        "weakness_key": weakness_key,
        "rating_tier": tier,
        "user_rating": rating,
        "progress": 0,
        "status": "active",
        "metrics": {
            "avg_blunders": round(avg_blunders, 2),
            "avg_accuracy": round(avg_accuracy, 1),
            "avg_cp_loss": round(avg_cp_loss, 1),
            "hung_piece_rate": round(hung_piece_rate, 2)
        }
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


def get_focus_data(analyses: List[Dict], games: List[Dict] = None, user_rating: int = None) -> Dict:
    """
    Get all data needed for the Focus page (stripped down Coach page).
    
    Returns:
    - ONE dominant weakness with EVIDENCE
    - ONE mission (scaled by rating tier)
    - Opening Guidance (what's working, what to pause)
    - Rating impact estimate
    """
    weakness = get_dominant_weakness_ranking(analyses, games)
    mission = get_mission(analyses, user_rating=user_rating)
    opening_guidance = get_opening_guidance(analyses, games) if games else None
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
        "opening_guidance": opening_guidance,
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


def find_similar_pattern_games(current_analysis: Dict, all_analyses: List[Dict], all_games: List[Dict], limit: int = 3) -> List[Dict]:
    """
    Find other games where the user made similar mistakes.
    
    Returns: List of related games with the same dominant pattern.
    """
    if not current_analysis or not all_analyses:
        return []
    
    # Get dominant pattern from current game
    current_core_lesson = get_core_lesson(current_analysis)
    current_pattern = current_core_lesson.get("pattern") if current_core_lesson else None
    
    if not current_pattern or current_pattern == "clean_game":
        return []
    
    current_game_id = current_analysis.get("game_id")
    
    # Build games lookup
    games_lookup = {g.get("game_id"): g for g in all_games} if all_games else {}
    
    # Find other games with the same pattern
    similar_games = []
    
    for analysis in all_analyses:
        if analysis.get("game_id") == current_game_id:
            continue
            
        other_lesson = get_core_lesson(analysis)
        if other_lesson and other_lesson.get("pattern") == current_pattern:
            game_info = games_lookup.get(analysis.get("game_id"), {})
            user_color = game_info.get("user_color", "white")
            opponent = game_info.get("black_player") if user_color == "white" else game_info.get("white_player")
            result = game_info.get("result", "")
            
            # Determine win/loss
            if result:
                is_win = (result == "1-0" and user_color == "white") or (result == "0-1" and user_color == "black")
                result_text = "Won" if is_win else "Lost" if result != "1/2-1/2" else "Draw"
            else:
                result_text = ""
            
            similar_games.append({
                "game_id": analysis.get("game_id"),
                "opponent": opponent or "Opponent",
                "result": result_text,
                "pattern": current_pattern,
                "lesson": other_lesson.get("lesson", ""),
                "imported_at": game_info.get("imported_at")
            })
    
    # Sort by most recent and limit
    similar_games.sort(key=lambda x: x.get("imported_at") or "", reverse=True)
    return similar_games[:limit]
