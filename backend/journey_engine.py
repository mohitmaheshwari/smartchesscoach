"""
Journey Engine v3 - 3-Tab Journey Page

Tabs:
A) NOW (Snapshot): Current identity - 5 items + directive
B) JOURNEY (Overall): First 15 vs Recent 15 - 4 rows + directive  
C) TREND (Momentum): Recent 5 vs Previous 5 - headline + shifts + evidence + directive

Rules:
- No raw severity numbers (use bands: Low/Moderate/High)
- No empty section spam (collapse to one line)
- One directive per tab (deterministic from driver)
- Plain Indian-English tone

"""

from typing import Dict, List, Optional, Tuple
from enum import Enum


# ============================================
# LABELS - Plain Indian-English
# ============================================

STABILITY_LABELS = {
    "STABLE": "Stable",
    "MIXED": "Mixed",
    "VOLATILE": "Volatile",
    "CHAOTIC": "Chaotic"
}

STABILITY_MEANING = {
    "STABLE": "Most games are clean and consistent.",
    "MIXED": "Some games are clean, some games collapse.",
    "VOLATILE": "Too many ups and downs in your play.",
    "CHAOTIC": "Very inconsistent—needs urgent work."
}

RISK_LABELS = {
    "LOW": "Low risk",
    "MEDIUM": "Medium risk", 
    "HIGH": "High risk"
}

RISK_MEANING = {
    "LOW": "You finish winning games well.",
    "MEDIUM": "Sometimes you relax and make mistakes when ahead.",
    "HIGH": "You often throw away winning positions."
}

# Pattern names - plain language
PATTERN_LABELS = {
    "structural_misjudgment": "Structural mistakes",
    "critical_moment_drift": "Critical moment drift", 
    "missed_forcing_move": "Missing winning moves",
    "advantage_mismanagement": "Relaxing when ahead",
    "random_critical_move": "Random moves in key spots",
    "time_pressure_drop": "Time pressure mistakes"
}

# Impact bands (not raw numbers)
IMPACT_BANDS = {
    "LOW": "Low",
    "MODERATE": "Moderate",
    "HIGH": "High"
}

# Directive mapping - deterministic, one per driver
DRIVER_DIRECTIVES = {
    "structural_misjudgment": "Next 5 games: before pawn move, ask 'what becomes weak after this?'",
    "critical_moment_drift": "Next 5 games: when position changes, pause 10 seconds and scan threats.",
    "missed_forcing_move": "Next 5 games: every move do Checks → Captures → Threats.",
    "advantage_mismanagement": "When ahead: trade pieces, avoid risky pawn pushes, and check opponent threats every move.",
    "random_critical_move": "Next 5 games: in sharp positions, calculate 2 moves deeper before deciding.",
    "time_pressure_drop": "Play 3 slow games this week. In complex spots, spend extra time."
}

DEFAULT_DIRECTIVE = "Next 5 games: every move do Checks → Captures → Threats."


class StabilityBand(Enum):
    STABLE = "STABLE"
    MIXED = "MIXED"
    VOLATILE = "VOLATILE"
    CHAOTIC = "CHAOTIC"


class RiskBand(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactBand(Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_stability_band(tsi_avg: float) -> StabilityBand:
    """Map TSI average to stability band."""
    if tsi_avg >= 75:
        return StabilityBand.STABLE
    elif tsi_avg >= 55:
        return StabilityBand.MIXED
    elif tsi_avg >= 35:
        return StabilityBand.VOLATILE
    return StabilityBand.CHAOTIC


def get_risk_band(blunder_rate: float) -> RiskBand:
    """Map blunders-when-ahead rate to risk band."""
    if blunder_rate <= 30:
        return RiskBand.LOW
    elif blunder_rate <= 55:
        return RiskBand.MEDIUM
    return RiskBand.HIGH


def get_impact_band(score: float) -> ImpactBand:
    """Map pattern score to impact band."""
    if score <= 0.25:
        return ImpactBand.LOW
    elif score <= 0.50:
        return ImpactBand.MODERATE
    return ImpactBand.HIGH


def calculate_game_tsi(analysis: Dict) -> int:
    """Calculate TSI for a single game (0-100 scale)."""
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    if not moves:
        return 80
    
    total_mistakes = 0
    total_severity = 0
    
    for move in moves:
        cp_loss = abs(move.get("cp_loss", 0))
        if cp_loss >= 50:
            total_mistakes += 1
            total_severity += min(1.0, cp_loss / 300)
    
    if total_mistakes == 0:
        return 85
    
    avg_severity = total_severity / total_mistakes
    mistakes_per_move = total_mistakes / max(len(moves), 1)
    instability = (mistakes_per_move * avg_severity) * 10
    instability = min(1.0, instability)
    
    return max(20, min(90, int(100 - instability * 80)))


def calculate_blunder_context(analyses: List[Dict]) -> Dict:
    """Calculate blunder context distribution."""
    winning = 0
    equal = 0
    losing = 0
    total = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        user_color = analysis.get("user_color", "white")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 100:
                continue
            
            total += 1
            eval_before = move.get("eval_before", 0)
            if user_color == "black":
                eval_before = -eval_before
            
            if eval_before >= 150:
                winning += 1
            elif eval_before <= -150:
                losing += 1
            else:
                equal += 1
    
    if total == 0:
        return {"winning_rate": 0, "equal_rate": 0, "losing_rate": 0, "total": 0}
    
    return {
        "winning_rate": round((winning / total) * 100),
        "equal_rate": round((equal / total) * 100),
        "losing_rate": round((losing / total) * 100),
        "total": total
    }


def calculate_pattern_scores(analyses: List[Dict], classify_func, severity_func) -> Dict[str, float]:
    """Calculate pattern scores for a window."""
    scores = {
        "structural_misjudgment": 0,
        "critical_moment_drift": 0,
        "missed_forcing_move": 0,
        "advantage_mismanagement": 0
    }
    total_weight = 0
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 50:
                continue
            
            total_weight += severity_func(cp_loss)
            
            mistake_type = move.get("mistake_type", "")
            best_move = move.get("best_move", "")
            best_move_forcing = "+" in best_move or "x" in best_move or "#" in best_move
            
            category = classify_func(
                mistake_type=mistake_type,
                cp_loss=cp_loss,
                best_move_was_forcing=best_move_forcing
            )
            
            if category:
                cat_key = category.value
                if cat_key in scores:
                    scores[cat_key] += severity_func(cp_loss)
                elif cat_key == "random_move_critical":
                    scores["critical_moment_drift"] += severity_func(cp_loss)
            elif cp_loss >= 150:
                scores["critical_moment_drift"] += severity_func(cp_loss)
            else:
                scores["structural_misjudgment"] += severity_func(cp_loss)
    
    # Normalize to shares
    if total_weight > 0:
        for key in scores:
            scores[key] = scores[key] / total_weight
    
    return scores


def get_primary_driver(scores: Dict[str, float]) -> Tuple[Optional[str], float]:
    """Get primary driver if it explains >= 30% of instability."""
    if not scores:
        return None, 0
    
    top_driver = max(scores, key=scores.get)
    top_share = scores[top_driver]
    
    if top_share >= 0.30:
        return top_driver, top_share
    return None, 0


def get_most_unstable_phase(analyses: List[Dict]) -> str:
    """Get the most unstable phase."""
    phase_scores = {"opening": 0, "middlegame": 0, "endgame": 0}
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss >= 50:
                phase = move.get("phase", "middlegame")
                if phase in phase_scores:
                    phase_scores[phase] += min(1.0, cp_loss / 300)
    
    if sum(phase_scores.values()) == 0:
        return "Middlegame"
    
    return max(phase_scores, key=phase_scores.get).capitalize()


def get_directive(driver: Optional[str]) -> str:
    """Get directive for a driver."""
    if driver and driver in DRIVER_DIRECTIVES:
        return DRIVER_DIRECTIVES[driver]
    return DEFAULT_DIRECTIVE


# ============================================
# TAB A: SNAPSHOT (NOW)
# ============================================

def compute_snapshot_now(recent_games: List[Dict], classify_func, severity_func) -> Dict:
    """
    Tab A - Snapshot (Current)
    
    Shows exactly 5 items:
    1. Decision Stability (band + meaning)
    2. Primary Driver (one only)
    3. Advantage Discipline (band)
    4. Most Unstable Phase
    5. Do this next
    """
    if len(recent_games) < 5:
        return {
            "ready": False,
            "games_needed": 5 - len(recent_games),
            "message": f"Need {5 - len(recent_games)} more games for snapshot."
        }
    
    # Use recent 10 games for current snapshot
    window = recent_games[:min(10, len(recent_games))]
    
    # Calculate metrics
    tsi_scores = [calculate_game_tsi(g) for g in window]
    tsi_avg = sum(tsi_scores) / len(tsi_scores) if tsi_scores else 50
    
    stability_band = get_stability_band(tsi_avg)
    
    blunder_context = calculate_blunder_context(window)
    risk_band = get_risk_band(blunder_context["winning_rate"])
    
    pattern_scores = calculate_pattern_scores(window, classify_func, severity_func)
    primary_driver, driver_share = get_primary_driver(pattern_scores)
    
    unstable_phase = get_most_unstable_phase(window)
    
    directive = get_directive(primary_driver)
    
    return {
        "ready": True,
        "decision_stability": {
            "band": STABILITY_LABELS[stability_band.value],
            "meaning": STABILITY_MEANING[stability_band.value]
        },
        "primary_driver": {
            "name": PATTERN_LABELS.get(primary_driver, "No clear pattern") if primary_driver else "No clear pattern",
            "key": primary_driver,
            "impact": IMPACT_BANDS[get_impact_band(driver_share).value] if primary_driver else None
        },
        "advantage_discipline": {
            "band": RISK_LABELS[risk_band.value],
            "meaning": RISK_MEANING[risk_band.value]
        },
        "unstable_phase": unstable_phase,
        "directive": directive
    }


# ============================================
# TAB B: OVERALL JOURNEY (THEN VS NOW)
# ============================================

def compute_overall_journey(all_games: List[Dict], classify_func, severity_func) -> Dict:
    """
    Tab B - Overall Journey (Then vs Now)
    
    Shows 4 before/after rows:
    1. Decision Stability: Then → Now
    2. Primary Driver Evolution: Then → Now
    3. Advantage Discipline Evolution: Then → Now
    4. Phase Evolution: Then → Now
    + Do this next
    """
    total = len(all_games)
    
    # Need at least 15 games for meaningful comparison
    if total < 15:
        return {
            "ready": False,
            "games_needed": 15 - total,
            "message": f"Need {15 - total} more games to see your journey."
        }
    
    # "Then" = first 15 games (oldest), "Now" = recent 15 games
    then_games = all_games[-15:]  # Oldest 15
    now_games = all_games[:15]    # Recent 15
    
    # Calculate for THEN
    then_tsi = [calculate_game_tsi(g) for g in then_games]
    then_tsi_avg = sum(then_tsi) / len(then_tsi) if then_tsi else 50
    then_stability = get_stability_band(then_tsi_avg)
    
    then_context = calculate_blunder_context(then_games)
    then_risk = get_risk_band(then_context["winning_rate"])
    
    then_patterns = calculate_pattern_scores(then_games, classify_func, severity_func)
    then_driver, then_share = get_primary_driver(then_patterns)
    then_phase = get_most_unstable_phase(then_games)
    
    # Calculate for NOW
    now_tsi = [calculate_game_tsi(g) for g in now_games]
    now_tsi_avg = sum(now_tsi) / len(now_tsi) if now_tsi else 50
    now_stability = get_stability_band(now_tsi_avg)
    
    now_context = calculate_blunder_context(now_games)
    now_risk = get_risk_band(now_context["winning_rate"])
    
    now_patterns = calculate_pattern_scores(now_games, classify_func, severity_func)
    now_driver, now_share = get_primary_driver(now_patterns)
    now_phase = get_most_unstable_phase(now_games)
    
    # Determine trend descriptions
    stability_delta = now_tsi_avg - then_tsi_avg
    if stability_delta >= 8:
        stability_trend = "Improving"
    elif stability_delta <= -8:
        stability_trend = "Declining"
    else:
        stability_trend = "No major shift"
    
    # Primary driver evolution
    if then_driver:
        then_driver_band = get_impact_band(then_patterns.get(then_driver, 0))
        now_driver_band = get_impact_band(now_patterns.get(then_driver, 0))
        driver_evolution = {
            "driver": PATTERN_LABELS.get(then_driver, then_driver),
            "then_band": IMPACT_BANDS[then_driver_band.value],
            "now_band": IMPACT_BANDS[now_driver_band.value],
            "changed": then_driver_band != now_driver_band
        }
    else:
        driver_evolution = {
            "driver": "No clear pattern",
            "then_band": None,
            "now_band": None,
            "changed": False
        }
    
    # Risk evolution
    risk_changed = then_risk != now_risk
    
    # Phase evolution
    phase_changed = then_phase != now_phase
    
    # Directive based on current worst
    directive = get_directive(now_driver)
    
    return {
        "ready": True,
        "rows": [
            {
                "label": "Decision Stability",
                "then": STABILITY_LABELS[then_stability.value],
                "now": STABILITY_LABELS[now_stability.value],
                "trend": stability_trend,
                "changed": then_stability != now_stability
            },
            {
                "label": "Primary Driver",
                "driver": driver_evolution["driver"],
                "then_band": driver_evolution["then_band"],
                "now_band": driver_evolution["now_band"],
                "changed": driver_evolution["changed"]
            },
            {
                "label": "Advantage Discipline",
                "then": RISK_LABELS[then_risk.value],
                "now": RISK_LABELS[now_risk.value],
                "changed": risk_changed
            },
            {
                "label": "Weakest Phase",
                "then": then_phase,
                "now": now_phase,
                "changed": phase_changed
            }
        ],
        "directive": directive
    }


# ============================================
# TAB C: RECENT MOMENTUM (5 VS 5)
# ============================================

def find_evidence_items(analyses: List[Dict]) -> List[Dict]:
    """
    Find 2 strong evidence items for momentum tab.
    Returns empty list if confidence is low.
    """
    evidence = []
    
    # Evidence 1: Blunder when winning
    for i, analysis in enumerate(analyses[:10]):
        sf = analysis.get("stockfish_analysis", {})
        user_color = analysis.get("user_color", "white")
        game_id = analysis.get("game_id", "")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 150:
                continue
            
            eval_before = move.get("eval_before", 0)
            if user_color == "black":
                eval_before = -eval_before
            
            if eval_before >= 150:  # Was winning
                evidence.append({
                    "type": "blunder_when_winning",
                    "label": "Blunder while winning",
                    "game_id": game_id,
                    "move_number": move.get("move_number", 0),
                    "description": f"Move {move.get('move_number', '?')}"
                })
                break
        
        if len(evidence) >= 1:
            break
    
    # Evidence 2: Critical moment drift
    for i, analysis in enumerate(analyses[:10]):
        sf = analysis.get("stockfish_analysis", {})
        game_id = analysis.get("game_id", "")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            mistake_type = move.get("mistake_type", "")
            
            if cp_loss >= 100 and mistake_type:
                # Avoid duplicate game
                if not any(e["game_id"] == game_id and e["move_number"] == move.get("move_number") for e in evidence):
                    evidence.append({
                        "type": "critical_moment",
                        "label": "Critical moment drift",
                        "game_id": game_id,
                        "move_number": move.get("move_number", 0),
                        "description": f"Move {move.get('move_number', '?')}"
                    })
                    break
        
        if len(evidence) >= 2:
            break
    
    # Only return if we have 2 strong items
    if len(evidence) < 2:
        return []
    
    return evidence[:2]


def compute_momentum_5v5(recent_games: List[Dict], classify_func, severity_func) -> Dict:
    """
    Tab C - Recent Momentum (5 vs 5)
    
    Rolling continuous tracker:
    - Headline (one line)
    - Top 2 meaningful shifts (if any)
    - 2 Evidence items (with game links)
    - Do this next
    """
    if len(recent_games) < 10:
        return {
            "ready": False,
            "games_needed": 10 - len(recent_games),
            "message": f"Need {10 - len(recent_games)} more games for momentum tracking."
        }
    
    # Recent 5 vs Previous 5
    recent_5 = recent_games[:5]
    previous_5 = recent_games[5:10]
    
    # Calculate for both windows
    recent_tsi = [calculate_game_tsi(g) for g in recent_5]
    previous_tsi = [calculate_game_tsi(g) for g in previous_5]
    
    recent_tsi_avg = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 50
    previous_tsi_avg = sum(previous_tsi) / len(previous_tsi) if previous_tsi else 50
    
    recent_stability = get_stability_band(recent_tsi_avg)
    previous_stability = get_stability_band(previous_tsi_avg)
    
    recent_context = calculate_blunder_context(recent_5)
    previous_context = calculate_blunder_context(previous_5)
    
    recent_risk = get_risk_band(recent_context["winning_rate"])
    previous_risk = get_risk_band(previous_context["winning_rate"])
    
    recent_patterns = calculate_pattern_scores(recent_5, classify_func, severity_func)
    previous_patterns = calculate_pattern_scores(previous_5, classify_func, severity_func)
    
    recent_driver, recent_share = get_primary_driver(recent_patterns)
    
    # Calculate deltas
    stability_delta = recent_tsi_avg - previous_tsi_avg
    context_delta = recent_context["winning_rate"] - previous_context["winning_rate"]
    
    # Find pattern shifts (band changes)
    pattern_shifts = []
    for cat in recent_patterns:
        recent_band = get_impact_band(recent_patterns.get(cat, 0))
        previous_band = get_impact_band(previous_patterns.get(cat, 0))
        if recent_band != previous_band:
            direction = "improved" if recent_band.value < previous_band.value else "worsened"
            pattern_shifts.append({
                "pattern": PATTERN_LABELS.get(cat, cat),
                "previous_band": IMPACT_BANDS[previous_band.value],
                "recent_band": IMPACT_BANDS[recent_band.value],
                "direction": direction
            })
    
    # Generate headline (pick strongest signal)
    stability_changed = abs(stability_delta) >= 8
    risk_changed = previous_risk != recent_risk
    has_pattern_shifts = len(pattern_shifts) > 0
    
    if not stability_changed and not risk_changed and not has_pattern_shifts:
        headline = "No meaningful shift in last 10 games."
    elif stability_changed and risk_changed:
        if stability_delta > 0:
            if context_delta > 10:
                headline = "This week stability improved, but winning positions got riskier."
            else:
                headline = "This week stability improved and you're finishing games better."
        else:
            if recent_driver:
                headline = f"This week stability dropped mainly due to {PATTERN_LABELS.get(recent_driver, 'mistakes').lower()}."
            else:
                headline = "This week stability dropped. Need to slow down."
    elif stability_changed:
        if stability_delta > 0:
            headline = "This week your play became more stable."
        else:
            headline = "This week your play became less stable."
    elif risk_changed:
        if context_delta < 0:
            headline = "This week you're converting winning positions better."
        else:
            headline = "This week you're throwing more winning positions."
    elif has_pattern_shifts:
        shift = pattern_shifts[0]
        if shift["direction"] == "improved":
            headline = f"{shift['pattern']} is improving this week."
        else:
            headline = f"{shift['pattern']} got worse this week."
    else:
        headline = "No meaningful shift in last 10 games."
    
    # Top 2 meaningful shifts
    meaningful_shifts = []
    
    # Add stability shift if significant
    if stability_changed:
        direction = "improving" if stability_delta > 0 else "declining"
        meaningful_shifts.append({
            "type": "stability",
            "label": "Decision Stability",
            "previous": STABILITY_LABELS[previous_stability.value],
            "recent": STABILITY_LABELS[recent_stability.value],
            "direction": direction
        })
    
    # Add risk shift if significant
    if risk_changed and abs(context_delta) > 15:
        direction = "improving" if context_delta < 0 else "declining"
        meaningful_shifts.append({
            "type": "risk",
            "label": "Advantage Discipline",
            "previous": RISK_LABELS[previous_risk.value],
            "recent": RISK_LABELS[recent_risk.value],
            "direction": direction
        })
    
    # Add pattern shifts
    for shift in pattern_shifts[:2]:
        if len(meaningful_shifts) >= 2:
            break
        meaningful_shifts.append({
            "type": "pattern",
            "label": shift["pattern"],
            "previous": shift["previous_band"],
            "recent": shift["recent_band"],
            "direction": "improving" if shift["direction"] == "improved" else "declining"
        })
    
    # Evidence items
    evidence = find_evidence_items(recent_games)
    
    # Directive
    directive = get_directive(recent_driver)
    
    return {
        "ready": True,
        "headline": headline,
        "shifts": meaningful_shifts[:2],
        "evidence": evidence,
        "evidence_ready": len(evidence) == 2,
        "directive": directive,
        "stats": {
            "stability_delta": round(stability_delta),
            "context_delta": round(context_delta)
        }
    }


# ============================================
# STATS DRAWER DATA
# ============================================

def compute_stats_drawer(recent_games: List[Dict]) -> Dict:
    """
    Collapsible stats drawer - for users who want numbers.
    
    Shows: Accuracy, Win Rate, Blunders/game, Mistakes/game
    """
    if len(recent_games) < 5:
        return {"ready": False}
    
    window = recent_games[:20]  # Last 20 games
    
    total_accuracy = 0
    total_blunders = 0
    total_mistakes = 0
    wins = 0
    losses = 0
    draws = 0
    
    for game in window:
        sf = game.get("stockfish_analysis", {})
        
        # Accuracy
        accuracy = sf.get("accuracy", 0)
        if accuracy > 0:
            total_accuracy += accuracy
        
        # Blunders and mistakes
        blunders = sf.get("blunders", 0)
        mistakes = sf.get("mistakes", 0)
        total_blunders += blunders
        total_mistakes += mistakes
        
        # Result
        result = game.get("user_result", "")
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        else:
            draws += 1
    
    game_count = len(window)
    
    return {
        "ready": True,
        "games_count": game_count,
        "accuracy": round(total_accuracy / game_count, 1) if game_count > 0 else 0,
        "win_rate": round((wins / game_count) * 100) if game_count > 0 else 0,
        "blunders_per_game": round(total_blunders / game_count, 1) if game_count > 0 else 0,
        "mistakes_per_game": round(total_mistakes / game_count, 1) if game_count > 0 else 0,
        "record": {
            "wins": wins,
            "losses": losses,
            "draws": draws
        }
    }


# ============================================
# MAIN ENTRY POINT
# ============================================

def compute_journey(all_games: List[Dict], classify_func, severity_func) -> Dict:
    """
    Main entry point for Journey page.
    
    Returns data for all 3 tabs + stats drawer:
    - snapshot: Tab A (Now)
    - journey: Tab B (Overall Journey)
    - momentum: Tab C (Recent Momentum)
    - stats: Collapsible stats drawer
    """
    total_games = len(all_games)
    
    # Activation check
    if total_games < 10:
        return {
            "activated": False,
            "games_analyzed": total_games,
            "games_required": 10
        }
    
    # Compute each tab
    snapshot = compute_snapshot_now(all_games, classify_func, severity_func)
    journey = compute_overall_journey(all_games, classify_func, severity_func)
    momentum = compute_momentum_5v5(all_games, classify_func, severity_func)
    stats = compute_stats_drawer(all_games)
    
    return {
        "activated": True,
        "games_analyzed": total_games,
        "snapshot": snapshot,
        "journey": journey,
        "momentum": momentum,
        "stats": stats
    }
