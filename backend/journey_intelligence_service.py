"""
Journey Intelligence Service

A deterministic, data-driven engine that powers the Journey page.
No LLM required - all insights are computed from game data.

Provides:
1. Identity Snapshot - Decision stability, primary pattern, weakest phase
2. Growth Delta - Then vs Now comparison
3. Rating Ceiling Model - Stable rating, peak rating, gap
4. Pattern Engine - Where blunders happen by game state
5. Phase Discipline - Opening/Middlegame/Endgame stability
6. Fundamentals Snapshot - Strongest and focus areas
7. Opening Snapshot - Top 3 openings performance
8. Momentum Trend - Recent change detection
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ============================================
# DETERMINISTIC TEXT TEMPLATES
# ============================================

DECISION_STABILITY_TEXT = {
    "stable": "Your decision-making is consistent across games.",
    "mixed": "Your decision quality varies game to game.",
    "volatile": "Your play swings significantly between games.",
}

RISK_PROFILE_TEXT = {
    "low": "You play solid, controlled chess.",
    "medium": "You take calculated risks with occasional lapses.",
    "high": "Your play tends toward aggressive but error-prone decisions.",
}

PHASE_WEAKNESS_TEXT = {
    "opening": "Most of your issues start in the opening phase.",
    "middlegame": "Complex middlegame positions cause most of your errors.",
    "endgame": "Endgame technique is where you lose the most ground.",
}

FOCUS_RECOMMENDATIONS = {
    "blunder_when_winning": "When ahead, simplify instead of attacking.",
    "blunder_when_equal": "In equal positions, check opponent forcing moves before each move.",
    "blunder_when_losing": "When behind, look for defensive resources before playing fast.",
    "time_trouble": "Manage your clock - spend less time in the opening.",
    "opening_instability": "Stick to 2-3 openings you know well.",
    "middlegame_collapse": "In complex positions, slow down and check threats.",
    "endgame_conversion": "When ahead in the endgame, calculate king activity first.",
    "accuracy_decline": "Before each move, ask: What does my opponent want?",
    "calculation_errors": "Calculate one move deeper before deciding.",
    "threat_blindness": "Every move, check: Is my opponent's last move a threat?",
    "hanging_pieces": "Before moving, verify all your pieces are defended.",
    "default": "Focus on checking opponent threats before each move.",
}

PATTERN_INTERPRETATION = {
    "winning": "You tend to relax when ahead - stay focused until checkmate.",
    "equal": "Equal positions require careful calculation - slow down.",
    "losing": "When behind, desperation leads to more errors - stay calm.",
}

GAP_DRIVERS = {
    "blunders": "too many blunders in critical moments",
    "time_pressure": "decisions made under time pressure",
    "winning_position_collapse": "losing focus when ahead",
    "calculation": "calculation errors in tactical positions",
    "opening_mistakes": "early game inaccuracies",
    "endgame_technique": "imprecise endgame play",
}


async def compute_journey_intelligence(db, user_id: str) -> Dict:
    """
    Compute all journey intelligence for a user.
    Returns structured data for all 8 sections.
    """
    
    # Fetch all games and analyses
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("analyzed_at", -1).limit(100).to_list(100)
    
    # Get cognitive gap data
    cognitive_gaps = await db.cognitive_gap_history.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    
    total_analyzed = len(analyses)
    
    # Minimum data check
    if total_analyzed < 5:
        return {
            "has_data": False,
            "games_analyzed": total_analyzed,
            "message": "Analyze more games to unlock deeper insights.",
            "minimum_required": 5,
        }
    
    # Build game-analysis map
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    # Enrich games with analysis data
    enriched_games = []
    for game in games:
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id)
        if analysis:
            enriched_games.append({
                **game,
                "analysis": analysis,
            })
    
    if len(enriched_games) < 5:
        return {
            "has_data": False,
            "games_analyzed": len(enriched_games),
            "message": "Analyze more games to unlock deeper insights.",
            "minimum_required": 5,
        }
    
    # Compute all sections
    result = {
        "has_data": True,
        "games_analyzed": len(enriched_games),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Section 1: Identity Snapshot
    result["identity"] = compute_identity_snapshot(enriched_games, cognitive_gaps)
    
    # Section 2: Growth Delta
    result["growth_delta"] = compute_growth_delta(enriched_games)
    
    # Section 3: Rating Ceiling Model
    result["rating_ceiling"] = compute_rating_ceiling(enriched_games)
    
    # Section 4: Pattern Engine
    result["pattern_engine"] = compute_pattern_engine(enriched_games)
    
    # Section 5: Phase Discipline
    result["phase_discipline"] = compute_phase_discipline(enriched_games)
    
    # Section 6: Fundamentals Snapshot
    result["fundamentals"] = compute_fundamentals_snapshot(enriched_games, cognitive_gaps)
    
    # Section 7: Opening Snapshot
    result["openings"] = compute_opening_snapshot(enriched_games)
    
    # Section 8: Momentum Trend
    result["momentum"] = compute_momentum_trend(enriched_games)
    
    return result


def compute_identity_snapshot(games: List[Dict], gaps: List[Dict]) -> Dict:
    """
    Compute player identity: stability, primary pattern, weakest phase, risk profile.
    """
    
    # Decision Stability - based on accuracy variance
    accuracies = []
    for g in games[:25]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        if moves:
            cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
            if cp_losses:
                avg_cp = sum(cp_losses) / len(cp_losses)
                accuracies.append(avg_cp)
    
    if len(accuracies) >= 5:
        accuracy_variance = sum((a - sum(accuracies)/len(accuracies))**2 for a in accuracies) / len(accuracies)
        if accuracy_variance < 200:
            decision_stability = "stable"
        elif accuracy_variance < 500:
            decision_stability = "mixed"
        else:
            decision_stability = "volatile"
    else:
        decision_stability = "mixed"
    
    # Primary Pattern - from cognitive gaps
    gap_counts = defaultdict(int)
    for gap in gaps[:50]:
        gap_type = gap.get("gap_type")
        if gap_type:
            gap_counts[gap_type] += 1
    
    if gap_counts:
        primary_pattern = max(gap_counts.items(), key=lambda x: x[1])[0]
        primary_pattern_name = primary_pattern.replace("_", " ").title()
        primary_pattern_count = gap_counts[primary_pattern]
    else:
        # Fallback to analysis data
        primary_pattern = detect_primary_pattern_from_games(games[:25])
        primary_pattern_name = primary_pattern.replace("_", " ").title()
        primary_pattern_count = 0
    
    # Weakest Phase - based on where most errors occur
    phase_errors = {"opening": 0, "middlegame": 0, "endgame": 0}
    for g in games[:25]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        total_moves = len(moves)
        
        for m in moves:
            if m.get("cp_loss", 0) >= 50:  # Significant error
                move_num = m.get("move_number", 0)
                if move_num <= 12:
                    phase_errors["opening"] += 1
                elif move_num <= total_moves * 0.7:
                    phase_errors["middlegame"] += 1
                else:
                    phase_errors["endgame"] += 1
    
    weakest_phase = max(phase_errors.items(), key=lambda x: x[1])[0] if sum(phase_errors.values()) > 0 else "middlegame"
    
    # Risk Profile - based on blunder frequency and playing style
    total_blunders = sum(g.get("analysis", {}).get("blunders", 0) for g in games[:25])
    games_count = min(len(games), 25)
    blunders_per_game = total_blunders / max(games_count, 1)
    
    if blunders_per_game < 0.3:
        risk_profile = "low"
    elif blunders_per_game < 0.8:
        risk_profile = "medium"
    else:
        risk_profile = "high"
    
    # Immediate Focus - single deterministic recommendation
    immediate_focus = determine_immediate_focus(games[:25], gaps[:30], phase_errors, primary_pattern)
    
    return {
        "decision_stability": decision_stability,
        "decision_stability_text": DECISION_STABILITY_TEXT[decision_stability],
        "primary_pattern": primary_pattern_name,
        "primary_pattern_count": primary_pattern_count,
        "weakest_phase": weakest_phase,
        "weakest_phase_text": PHASE_WEAKNESS_TEXT[weakest_phase],
        "risk_profile": risk_profile,
        "risk_profile_text": RISK_PROFILE_TEXT[risk_profile],
        "immediate_focus": immediate_focus,
    }


def detect_primary_pattern_from_games(games: List[Dict]) -> str:
    """Detect primary pattern from game analysis when no cognitive gap data."""
    
    pattern_signals = {
        "blunder_when_winning": 0,
        "tactical_oversight": 0,
        "time_trouble": 0,
        "opening_mistakes": 0,
        "endgame_errors": 0,
    }
    
    for g in games:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            if cp_loss >= 100:  # Blunder
                eval_before = m.get("eval_before", 0)
                move_num = m.get("move_number", 0)
                
                if eval_before > 100:  # Was winning
                    pattern_signals["blunder_when_winning"] += 1
                
                if move_num <= 12:
                    pattern_signals["opening_mistakes"] += 1
                elif move_num >= 35:
                    pattern_signals["endgame_errors"] += 1
                else:
                    pattern_signals["tactical_oversight"] += 1
    
    if sum(pattern_signals.values()) == 0:
        return "calculation_depth"
    
    return max(pattern_signals.items(), key=lambda x: x[1])[0]


def determine_immediate_focus(games: List[Dict], gaps: List[Dict], phase_errors: Dict, primary_pattern: str) -> Dict:
    """Determine the single most important focus recommendation."""
    
    # Priority 1: Blunders when winning (most costly)
    winning_blunders = 0
    equal_blunders = 0
    losing_blunders = 0
    
    for g in games:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            if m.get("cp_loss", 0) >= 100:
                eval_before = m.get("eval_before", 0)
                if eval_before > 100:
                    winning_blunders += 1
                elif eval_before < -100:
                    losing_blunders += 1
                else:
                    equal_blunders += 1
    
    total_blunders = winning_blunders + equal_blunders + losing_blunders
    
    if total_blunders > 0:
        if winning_blunders / total_blunders > 0.4:
            return {
                "key": "blunder_when_winning",
                "text": FOCUS_RECOMMENDATIONS["blunder_when_winning"],
                "reason": f"{int(winning_blunders/total_blunders*100)}% of blunders happen when you're ahead.",
            }
        elif equal_blunders / total_blunders > 0.4:
            return {
                "key": "blunder_when_equal",
                "text": FOCUS_RECOMMENDATIONS["blunder_when_equal"],
                "reason": f"{int(equal_blunders/total_blunders*100)}% of blunders happen in equal positions.",
            }
    
    # Priority 2: Phase-specific issue
    max_phase = max(phase_errors.items(), key=lambda x: x[1])
    if max_phase[1] > 5:
        if max_phase[0] == "opening":
            return {
                "key": "opening_instability",
                "text": FOCUS_RECOMMENDATIONS["opening_instability"],
                "reason": f"{max_phase[1]} errors in opening phase recently.",
            }
        elif max_phase[0] == "middlegame":
            return {
                "key": "middlegame_collapse",
                "text": FOCUS_RECOMMENDATIONS["middlegame_collapse"],
                "reason": f"{max_phase[1]} errors in middlegame recently.",
            }
        elif max_phase[0] == "endgame":
            return {
                "key": "endgame_conversion",
                "text": FOCUS_RECOMMENDATIONS["endgame_conversion"],
                "reason": f"{max_phase[1]} errors in endgame recently.",
            }
    
    # Priority 3: From cognitive gap pattern
    gap_focus_map = {
        "threat_blindness": "threat_blindness",
        "calculation_depth": "calculation_errors",
        "hanging_piece_blindness": "hanging_pieces",
        "tactical_oversight": "calculation_errors",
    }
    
    focus_key = gap_focus_map.get(primary_pattern, "default")
    
    return {
        "key": focus_key,
        "text": FOCUS_RECOMMENDATIONS.get(focus_key, FOCUS_RECOMMENDATIONS["default"]),
        "reason": f"Based on your most common error pattern.",
    }


def compute_growth_delta(games: List[Dict]) -> Dict:
    """Compare last 25 games vs previous 25 games."""
    
    if len(games) < 10:
        return {"has_delta": False, "message": "Need more games for comparison."}
    
    # Split games
    recent = games[:25]
    previous = games[25:50] if len(games) >= 50 else games[len(games)//2:]
    
    if len(previous) < 5:
        return {"has_delta": False, "message": "Need more historical games for comparison."}
    
    def compute_metrics(game_list):
        total_blunders = 0
        total_mistakes = 0
        total_games = len(game_list)
        wins = 0
        accuracy_sum = 0
        accuracy_count = 0
        
        for g in game_list:
            analysis = g.get("analysis", {})
            total_blunders += analysis.get("blunders", 0)
            total_mistakes += analysis.get("mistakes", 0)
            
            # Win rate
            result = g.get("result", "*")
            user_color = g.get("user_color", "white")
            if (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1"):
                wins += 1
            
            # Accuracy
            sf = analysis.get("stockfish_analysis", {})
            moves = sf.get("move_evaluations", [])
            if moves:
                cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
                if cp_losses:
                    accuracy_sum += sum(cp_losses) / len(cp_losses)
                    accuracy_count += 1
        
        return {
            "games": total_games,
            "blunders_per_game": round(total_blunders / max(total_games, 1), 2),
            "mistakes_per_game": round(total_mistakes / max(total_games, 1), 2),
            "win_rate": round(wins / max(total_games, 1) * 100, 1),
            "avg_cp_loss": round(accuracy_sum / max(accuracy_count, 1), 1),
        }
    
    recent_metrics = compute_metrics(recent)
    previous_metrics = compute_metrics(previous)
    
    # Calculate deltas
    metrics = []
    
    # Accuracy (lower is better)
    acc_delta = previous_metrics["avg_cp_loss"] - recent_metrics["avg_cp_loss"]
    metrics.append({
        "name": "Accuracy",
        "recent": f"{recent_metrics['avg_cp_loss']} cp",
        "previous": f"{previous_metrics['avg_cp_loss']} cp",
        "delta": round(acc_delta, 1),
        "improved": acc_delta > 0,
        "unit": "cp",
    })
    
    # Blunders per game (lower is better)
    blunder_delta = previous_metrics["blunders_per_game"] - recent_metrics["blunders_per_game"]
    metrics.append({
        "name": "Blunders/Game",
        "recent": recent_metrics["blunders_per_game"],
        "previous": previous_metrics["blunders_per_game"],
        "delta": round(blunder_delta, 2),
        "improved": blunder_delta > 0,
        "unit": "",
    })
    
    # Mistakes per game (lower is better)
    mistake_delta = previous_metrics["mistakes_per_game"] - recent_metrics["mistakes_per_game"]
    metrics.append({
        "name": "Mistakes/Game",
        "recent": recent_metrics["mistakes_per_game"],
        "previous": previous_metrics["mistakes_per_game"],
        "delta": round(mistake_delta, 2),
        "improved": mistake_delta > 0,
        "unit": "",
    })
    
    # Win rate (higher is better)
    wr_delta = recent_metrics["win_rate"] - previous_metrics["win_rate"]
    metrics.append({
        "name": "Win Rate",
        "recent": f"{recent_metrics['win_rate']}%",
        "previous": f"{previous_metrics['win_rate']}%",
        "delta": round(wr_delta, 1),
        "improved": wr_delta > 0,
        "unit": "%",
    })
    
    # Determine if there's meaningful change
    significant_changes = sum(1 for m in metrics if abs(m["delta"]) > 0.1)
    
    if significant_changes == 0:
        return {
            "has_delta": True,
            "is_stable": True,
            "message": "Your performance level is stable. No significant change detected.",
            "metrics": metrics,
            "recent_games": len(recent),
            "previous_games": len(previous),
        }
    
    return {
        "has_delta": True,
        "is_stable": False,
        "metrics": metrics,
        "recent_games": len(recent),
        "previous_games": len(previous),
    }


def compute_rating_ceiling(games: List[Dict]) -> Dict:
    """Compute stable rating, peak rating, and performance gap."""
    
    if len(games) < 10:
        return {"has_ceiling": False, "message": "Need more games for rating ceiling analysis."}
    
    # Collect performance data per game
    performances = []
    
    for g in games[:50]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        if not moves:
            continue
        
        # Calculate game quality metrics
        cp_losses = [m.get("cp_loss", 0) for m in moves if m.get("cp_loss") is not None]
        if not cp_losses:
            continue
        
        avg_cp = sum(cp_losses) / len(cp_losses)
        blunders = analysis.get("blunders", 0)
        
        # Check for collapse moments (big eval swings)
        has_collapse = any(m.get("cp_loss", 0) >= 200 for m in moves)
        
        # Rating performance estimate (simplified)
        # Better accuracy = higher performance rating
        # This is a rough estimate, not exact rating calculation
        base_rating = 1500
        accuracy_bonus = max(0, (50 - avg_cp) * 10)  # Lower cp loss = bonus
        blunder_penalty = blunders * 50
        
        estimated_performance = base_rating + accuracy_bonus - blunder_penalty
        
        performances.append({
            "avg_cp_loss": avg_cp,
            "blunders": blunders,
            "has_collapse": has_collapse,
            "estimated_performance": estimated_performance,
            "is_clean": blunders <= 1 and avg_cp < 35 and not has_collapse,
        })
    
    if len(performances) < 5:
        return {"has_ceiling": False, "message": "Need more analyzed games."}
    
    # Stable Rating: Average of clean games
    clean_games = [p for p in performances if p["is_clean"]]
    if len(clean_games) >= 3:
        stable_rating = sum(p["estimated_performance"] for p in clean_games) / len(clean_games)
    else:
        # Use top 50% of games
        sorted_perfs = sorted(performances, key=lambda x: x["estimated_performance"], reverse=True)
        top_half = sorted_perfs[:len(sorted_perfs)//2]
        stable_rating = sum(p["estimated_performance"] for p in top_half) / len(top_half)
    
    # Peak Rating: Top 10% performance
    sorted_by_perf = sorted(performances, key=lambda x: x["estimated_performance"], reverse=True)
    top_10_pct = sorted_by_perf[:max(1, len(sorted_by_perf)//10)]
    peak_rating = sum(p["estimated_performance"] for p in top_10_pct) / len(top_10_pct)
    
    # Performance Gap
    gap = peak_rating - stable_rating
    
    # Determine primary gap driver
    blunder_heavy = sum(1 for p in performances if p["blunders"] >= 2) / len(performances) > 0.3
    collapse_heavy = sum(1 for p in performances if p["has_collapse"]) / len(performances) > 0.25
    
    if blunder_heavy:
        gap_driver = "blunders"
    elif collapse_heavy:
        gap_driver = "winning_position_collapse"
    else:
        gap_driver = "calculation"
    
    return {
        "has_ceiling": True,
        "stable_rating": round(stable_rating),
        "peak_rating": round(peak_rating),
        "performance_gap": round(gap),
        "gap_driver": gap_driver,
        "gap_driver_text": GAP_DRIVERS[gap_driver],
        "explanation": f"Your peak play shows {round(peak_rating)} strength. Your average play holds you at {round(stable_rating)}. The gap comes from {GAP_DRIVERS[gap_driver]}.",
        "clean_games_count": len(clean_games),
        "total_games_analyzed": len(performances),
    }


def compute_pattern_engine(games: List[Dict]) -> Dict:
    """Analyze where blunders happen by game state (winning/equal/losing)."""
    
    states = {"winning": 0, "equal": 0, "losing": 0}
    total_blunders = 0
    
    for g in games[:30]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        user_color = g.get("user_color", "white")
        
        for m in moves:
            if m.get("cp_loss", 0) >= 100:  # Blunder threshold
                total_blunders += 1
                eval_before = m.get("eval_before", 0)
                
                # Adjust for color
                if user_color == "black":
                    eval_before = -eval_before
                
                if eval_before > 100:
                    states["winning"] += 1
                elif eval_before < -100:
                    states["losing"] += 1
                else:
                    states["equal"] += 1
    
    if total_blunders == 0:
        return {
            "has_pattern": False,
            "message": "No blunders detected in recent games. Great control!",
        }
    
    # Calculate percentages
    percentages = {
        k: round(v / total_blunders * 100, 1) for k, v in states.items()
    }
    
    # Find highest
    highest_state = max(states.items(), key=lambda x: x[1])[0]
    
    return {
        "has_pattern": True,
        "total_blunders": total_blunders,
        "states": [
            {"state": "winning", "label": "When Winning", "count": states["winning"], "percentage": percentages["winning"]},
            {"state": "equal", "label": "When Equal", "count": states["equal"], "percentage": percentages["equal"]},
            {"state": "losing", "label": "When Losing", "count": states["losing"], "percentage": percentages["losing"]},
        ],
        "highest_state": highest_state,
        "interpretation": PATTERN_INTERPRETATION[highest_state],
        "headline": f"{percentages[highest_state]}% of your blunders happen in {highest_state} positions.",
    }


def compute_phase_discipline(games: List[Dict]) -> Dict:
    """Analyze stability in each game phase."""
    
    phases = {
        "opening": {"errors": 0, "total_moves": 0},
        "middlegame": {"errors": 0, "total_moves": 0},
        "endgame": {"errors": 0, "total_moves": 0},
    }
    
    for g in games[:25]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        total_moves = len(moves)
        
        for m in moves:
            move_num = m.get("move_number", 0)
            cp_loss = m.get("cp_loss", 0)
            
            # Determine phase
            if move_num <= 12:
                phase = "opening"
            elif move_num <= total_moves * 0.7 or move_num <= 30:
                phase = "middlegame"
            else:
                phase = "endgame"
            
            phases[phase]["total_moves"] += 1
            if cp_loss >= 30:  # Inaccuracy or worse
                phases[phase]["errors"] += 1
    
    # Calculate stability
    result = []
    for phase_name, data in phases.items():
        if data["total_moves"] > 0:
            error_rate = data["errors"] / data["total_moves"]
            is_stable = error_rate < 0.15  # Less than 15% error rate
            
            result.append({
                "phase": phase_name,
                "label": phase_name.title(),
                "is_stable": is_stable,
                "status": "Stable" if is_stable else "Unstable",
                "error_rate": round(error_rate * 100, 1),
                "errors": data["errors"],
            })
    
    # Find most unstable
    unstable_phases = [p for p in result if not p["is_stable"]]
    most_errors_phase = max(result, key=lambda x: x["errors"]) if result else None
    
    return {
        "phases": result,
        "has_unstable": len(unstable_phases) > 0,
        "most_errors_phase": most_errors_phase["phase"] if most_errors_phase and most_errors_phase["errors"] > 3 else None,
    }


def compute_fundamentals_snapshot(games: List[Dict], gaps: List[Dict]) -> Dict:
    """Identify strongest and focus areas."""
    
    # Fundamental areas to track
    areas = {
        "tactical_awareness": {"score": 0, "max": 0},
        "defensive_play": {"score": 0, "max": 0},
        "advantage_discipline": {"score": 0, "max": 0},
        "endgame_technique": {"score": 0, "max": 0},
        "opening_knowledge": {"score": 0, "max": 0},
    }
    
    for g in games[:25]:
        analysis = g.get("analysis", {})
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        result = g.get("result", "*")
        user_color = g.get("user_color", "white")
        
        # Determine if won
        won = (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1")
        
        # Track metrics
        blunders = analysis.get("blunders", 0)
        total_moves = len(moves)
        
        # Tactical awareness: inverse of missed tactics
        areas["tactical_awareness"]["max"] += 1
        if blunders == 0:
            areas["tactical_awareness"]["score"] += 1
        
        # Opening knowledge: few errors in first 12 moves
        opening_errors = sum(1 for m in moves if m.get("move_number", 0) <= 12 and m.get("cp_loss", 0) >= 50)
        areas["opening_knowledge"]["max"] += 1
        if opening_errors <= 1:
            areas["opening_knowledge"]["score"] += 1
        
        # Endgame technique: performance in late game
        endgame_moves = [m for m in moves if m.get("move_number", 0) >= 35]
        if endgame_moves:
            areas["endgame_technique"]["max"] += 1
            endgame_errors = sum(1 for m in endgame_moves if m.get("cp_loss", 0) >= 50)
            if endgame_errors <= 1:
                areas["endgame_technique"]["score"] += 1
        
        # Advantage discipline: did we convert winning positions?
        was_winning = any(m.get("eval_before", 0) > 200 for m in moves)
        if was_winning:
            areas["advantage_discipline"]["max"] += 1
            if won:
                areas["advantage_discipline"]["score"] += 1
        
        # Defensive play: did we hold losing positions?
        was_losing = any(m.get("eval_before", 0) < -200 for m in moves)
        if was_losing:
            areas["defensive_play"]["max"] += 1
            if result == "1/2-1/2" or won:
                areas["defensive_play"]["score"] += 1
    
    # Calculate percentages and find strongest/weakest
    scored_areas = []
    for area_name, data in areas.items():
        if data["max"] > 0:
            pct = data["score"] / data["max"] * 100
            scored_areas.append({
                "area": area_name,
                "label": area_name.replace("_", " ").title(),
                "score": data["score"],
                "max": data["max"],
                "percentage": round(pct, 0),
            })
    
    if not scored_areas:
        return {"has_fundamentals": False}
    
    # Sort by percentage
    scored_areas.sort(key=lambda x: x["percentage"], reverse=True)
    
    strongest = scored_areas[0] if scored_areas[0]["percentage"] >= 50 else None
    focus = scored_areas[-1] if scored_areas[-1]["percentage"] < 70 else None
    
    # Focus recommendation
    focus_actions = {
        "tactical_awareness": "Practice daily tactics to sharpen pattern recognition.",
        "defensive_play": "When in trouble, look for the most resilient defense.",
        "advantage_discipline": "When ahead, simplify and avoid complications.",
        "endgame_technique": "Study basic endgame positions and king activity.",
        "opening_knowledge": "Stick to 2-3 openings and learn them deeply.",
    }
    
    return {
        "has_fundamentals": True,
        "strongest": strongest,
        "focus": focus,
        "focus_action": focus_actions.get(focus["area"], "") if focus else "",
        "all_areas": scored_areas,
    }


def compute_opening_snapshot(games: List[Dict]) -> Dict:
    """Get top 3 most played openings with performance."""
    
    openings = defaultdict(lambda: {"games": 0, "wins": 0})
    
    for g in games[:50]:
        opening = g.get("opening_name", "Unknown")
        if opening:
            # Simplify opening name
            opening_simple = opening.split(":")[0].strip()
            openings[opening_simple]["games"] += 1
            
            result = g.get("result", "*")
            user_color = g.get("user_color", "white")
            if (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1"):
                openings[opening_simple]["wins"] += 1
    
    if not openings:
        return {"has_openings": False}
    
    # Sort by games played
    sorted_openings = sorted(openings.items(), key=lambda x: x[1]["games"], reverse=True)[:3]
    
    result = []
    for name, data in sorted_openings:
        win_rate = data["wins"] / data["games"] * 100 if data["games"] > 0 else 0
        
        result.append({
            "name": name,
            "games": data["games"],
            "wins": data["wins"],
            "win_rate": round(win_rate, 0),
            "status": "Stable" if win_rate >= 50 else "Needs Work",
        })
    
    return {
        "has_openings": True,
        "openings": result,
    }


def compute_momentum_trend(games: List[Dict]) -> Dict:
    """Compare last 5 vs previous 5 games for recent momentum."""
    
    if len(games) < 10:
        return {"has_momentum": False, "message": "Need more recent games for momentum analysis."}
    
    recent = games[:5]
    previous = games[5:10]
    
    def avg_metrics(game_list):
        blunders = sum(g.get("analysis", {}).get("blunders", 0) for g in game_list) / len(game_list)
        mistakes = sum(g.get("analysis", {}).get("mistakes", 0) for g in game_list) / len(game_list)
        
        wins = sum(1 for g in game_list if 
            (g.get("user_color") == "white" and g.get("result") == "1-0") or
            (g.get("user_color") == "black" and g.get("result") == "0-1"))
        
        return {
            "blunders": round(blunders, 2),
            "mistakes": round(mistakes, 2),
            "win_rate": wins / len(game_list) * 100,
        }
    
    recent_avg = avg_metrics(recent)
    previous_avg = avg_metrics(previous)
    
    # Find biggest change
    changes = []
    
    blunder_change = previous_avg["blunders"] - recent_avg["blunders"]
    if abs(blunder_change) >= 0.3:
        changes.append({
            "metric": "Blunders",
            "direction": "improved" if blunder_change > 0 else "declined",
            "magnitude": abs(blunder_change),
        })
    
    wr_change = recent_avg["win_rate"] - previous_avg["win_rate"]
    if abs(wr_change) >= 20:
        changes.append({
            "metric": "Win Rate",
            "direction": "improved" if wr_change > 0 else "declined",
            "magnitude": abs(wr_change),
        })
    
    if not changes:
        return {
            "has_momentum": True,
            "is_stable": True,
            "message": "No meaningful change in last 10 games.",
            "recent": recent_avg,
            "previous": previous_avg,
        }
    
    # Get biggest change
    biggest = max(changes, key=lambda x: x["magnitude"])
    
    return {
        "has_momentum": True,
        "is_stable": False,
        "biggest_change": biggest,
        "message": f"{biggest['metric']} has {biggest['direction']}.",
        "recent": recent_avg,
        "previous": previous_avg,
    }
