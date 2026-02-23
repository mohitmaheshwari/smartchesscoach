"""
Journey Engine v3 - 3-Tab Journey Page

PATCH: Reuses existing pattern analysis logic from baseline_service.py

Tabs:
A) NOW (Snapshot): Current identity - 5 items + directive (shows Top 1 issue)
B) JOURNEY (Overall): First 15 vs Recent 15 - 4 rows + directive  
C) TREND (Momentum): Recent 5 vs Previous 5 - headline + Top 3 issues + evidence + directive

Rules:
- No raw severity numbers (use bands: Low/Moderate/High)
- No empty section spam (collapse to one line)
- One directive per tab (deterministic from driver)
- Plain Indian-English tone
- Reuse existing /progress logic - no new aggregation

"""

from typing import Dict, List, Optional, Tuple
from enum import Enum

# REUSE: Import existing pattern analysis from baseline_service
from baseline_service import (
    calculate_blunder_context_stats,
    detect_weakness_patterns,
    calculate_pattern_snapshot
)


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

# Map existing weakness IDs to cognitive-friendly labels
WEAKNESS_LABELS = {
    "relaxes_when_winning": "Relaxes when winning",
    "piece_safety": "Piece safety issues",
    "tactical_blindness": "Misses tactics",
    "time_trouble": "Time trouble blunders",
    # Also map cognitive categories
    "structural_misjudgment": "Structural mistakes",
    "critical_moment_drift": "Critical moment drift", 
    "missed_forcing_move": "Missing winning moves",
    "advantage_mismanagement": "Relaxes when winning",
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
    # Cognitive categories
    "structural_misjudgment": "Next 5 games: before pawn move, ask 'what becomes weak after this?'",
    "critical_moment_drift": "Next 5 games: when position changes, pause 10 seconds and scan threats.",
    "missed_forcing_move": "Next 5 games: every move do Checks → Captures → Threats.",
    "advantage_mismanagement": "When ahead: trade pieces, avoid risky pawn pushes, and check opponent threats every move.",
    "random_critical_move": "Next 5 games: in sharp positions, calculate 2 moves deeper before deciding.",
    "time_pressure_drop": "Play 3 slow games this week. In complex spots, spend extra time.",
    # Existing weakness IDs from baseline_service
    "relaxes_when_winning": "When ahead: trade pieces, avoid risky pawn pushes, and check opponent threats every move.",
    "piece_safety": "Before each move: scan the board for your undefended pieces.",
    "tactical_blindness": "Next 5 games: every move do Checks → Captures → Threats.",
    "time_trouble": "Play 3 slow games this week. In complex spots, spend extra time."
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


def get_risk_band(blunder_when_winning_pct: float) -> RiskBand:
    """Map blunders-when-winning percentage to risk band."""
    if blunder_when_winning_pct <= 30:
        return RiskBand.LOW
    elif blunder_when_winning_pct <= 55:
        return RiskBand.MEDIUM
    return RiskBand.HIGH


def severity_to_impact_band(severity: str) -> str:
    """Convert severity label to impact band."""
    if severity == "high":
        return "High"
    elif severity == "medium":
        return "Moderate"
    return "Low"


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


def get_directive(driver_id: Optional[str]) -> str:
    """Get directive for a driver."""
    if driver_id and driver_id in DRIVER_DIRECTIVES:
        return DRIVER_DIRECTIVES[driver_id]
    return DEFAULT_DIRECTIVE


def get_weakness_label(weakness_id: str) -> str:
    """Get human-readable label for a weakness ID."""
    return WEAKNESS_LABELS.get(weakness_id, weakness_id.replace("_", " ").title())


# ============================================
# TAB A: SNAPSHOT (NOW)
# Uses detect_weakness_patterns() from baseline_service
# ============================================

def compute_snapshot_now(recent_games: List[Dict], games_for_pattern: List[Dict] = None) -> Dict:
    """
    Tab A - Snapshot (Current)
    
    Shows exactly 5 items:
    1. Decision Stability (band + meaning)
    2. Primary Driver / Top Issue (one only - from existing weakness detection)
    3. Advantage Discipline (band from blunder context)
    4. Most Unstable Phase
    5. Do this next
    
    REUSES: detect_weakness_patterns() and calculate_blunder_context_stats() from baseline_service
    """
    if len(recent_games) < 5:
        return {
            "ready": False,
            "games_needed": 5 - len(recent_games),
            "message": f"Need {5 - len(recent_games)} more games for snapshot."
        }
    
    # Use recent 10 games for current snapshot
    window = recent_games[:min(10, len(recent_games))]
    
    # Calculate TSI-based stability
    tsi_scores = [calculate_game_tsi(g) for g in window]
    tsi_avg = sum(tsi_scores) / len(tsi_scores) if tsi_scores else 50
    stability_band = get_stability_band(tsi_avg)
    
    # REUSE: Get blunder context from baseline_service
    blunder_context = calculate_blunder_context_stats(window)
    winning_pct = blunder_context.get("when_winning", {}).get("percentage", 0)
    risk_band = get_risk_band(winning_pct)
    
    # REUSE: Detect weakness patterns from baseline_service
    # This returns: [{id, label, severity, occurrence_pct, examples, ...}]
    weaknesses = detect_weakness_patterns(window, games_for_pattern or [])
    
    # Get TOP 1 issue for Tab A (primary driver)
    top_issue = None
    top_issue_id = None
    if weaknesses:
        top = weaknesses[0]
        top_issue = {
            "name": get_weakness_label(top["id"]),
            "id": top["id"],
            "impact": severity_to_impact_band(top.get("severity", "medium")),
            "occurrence_pct": top.get("occurrence_pct", 0)
        }
        top_issue_id = top["id"]
    
    # Get most unstable phase
    unstable_phase = get_most_unstable_phase(window)
    
    # Get directive based on top issue
    directive = get_directive(top_issue_id)
    
    return {
        "ready": True,
        "decision_stability": {
            "band": STABILITY_LABELS[stability_band.value],
            "meaning": STABILITY_MEANING[stability_band.value]
        },
        "top_issue": top_issue if top_issue else {
            "name": "No clear pattern",
            "id": None,
            "impact": None,
            "occurrence_pct": 0
        },
        "advantage_discipline": {
            "band": RISK_LABELS[risk_band.value],
            "meaning": RISK_MEANING[risk_band.value],
            "blunder_when_winning_pct": winning_pct
        },
        "unstable_phase": unstable_phase,
        "directive": directive
    }


# ============================================
# TAB B: OVERALL JOURNEY (THEN VS NOW)
# Uses pattern comparison from baseline_service
# ============================================

def compute_overall_journey(all_games: List[Dict], games_for_pattern: List[Dict] = None) -> Dict:
    """
    Tab B - Overall Journey (Then vs Now)
    
    Shows 4 before/after rows:
    1. Decision Stability: Then → Now
    2. Primary Driver Evolution: Then → Now
    3. Advantage Discipline Evolution: Then → Now
    4. Phase Evolution: Then → Now
    + Do this next
    
    REUSES: detect_weakness_patterns(), calculate_blunder_context_stats()
    """
    total = len(all_games)
    
    if total < 15:
        return {
            "ready": False,
            "games_needed": 15 - total,
            "message": f"Need {15 - total} more games to see your journey."
        }
    
    # "Then" = first 15 games (oldest), "Now" = recent 15 games
    then_games = all_games[-15:]  # Oldest 15
    now_games = all_games[:15]    # Recent 15
    
    # Calculate stability for THEN
    then_tsi = [calculate_game_tsi(g) for g in then_games]
    then_tsi_avg = sum(then_tsi) / len(then_tsi) if then_tsi else 50
    then_stability = get_stability_band(then_tsi_avg)
    
    # Calculate stability for NOW
    now_tsi = [calculate_game_tsi(g) for g in now_games]
    now_tsi_avg = sum(now_tsi) / len(now_tsi) if now_tsi else 50
    now_stability = get_stability_band(now_tsi_avg)
    
    # REUSE: Blunder context comparison
    then_context = calculate_blunder_context_stats(then_games)
    now_context = calculate_blunder_context_stats(now_games)
    
    then_winning_pct = then_context.get("when_winning", {}).get("percentage", 0)
    now_winning_pct = now_context.get("when_winning", {}).get("percentage", 0)
    
    then_risk = get_risk_band(then_winning_pct)
    now_risk = get_risk_band(now_winning_pct)
    
    # REUSE: Weakness pattern comparison
    then_weaknesses = detect_weakness_patterns(then_games, [])
    now_weaknesses = detect_weakness_patterns(now_games, [])
    
    # Primary driver evolution
    then_top = then_weaknesses[0] if then_weaknesses else None
    now_top = now_weaknesses[0] if now_weaknesses else None
    
    driver_evolution = {
        "then_driver": get_weakness_label(then_top["id"]) if then_top else "No clear pattern",
        "now_driver": get_weakness_label(now_top["id"]) if now_top else "No clear pattern",
        "then_impact": severity_to_impact_band(then_top.get("severity", "medium")) if then_top else None,
        "now_impact": severity_to_impact_band(now_top.get("severity", "medium")) if now_top else None,
        "changed": (then_top["id"] if then_top else None) != (now_top["id"] if now_top else None)
    }
    
    # Phase evolution
    then_phase = get_most_unstable_phase(then_games)
    now_phase = get_most_unstable_phase(now_games)
    
    # Determine trend
    stability_delta = now_tsi_avg - then_tsi_avg
    if stability_delta >= 8:
        stability_trend = "Improving"
    elif stability_delta <= -8:
        stability_trend = "Declining"
    else:
        stability_trend = "No major shift"
    
    # Directive based on current worst
    directive = get_directive(now_top["id"] if now_top else None)
    
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
                "then_driver": driver_evolution["then_driver"],
                "now_driver": driver_evolution["now_driver"],
                "then_impact": driver_evolution["then_impact"],
                "now_impact": driver_evolution["now_impact"],
                "changed": driver_evolution["changed"]
            },
            {
                "label": "Advantage Discipline",
                "then": RISK_LABELS[then_risk.value],
                "now": RISK_LABELS[now_risk.value],
                "changed": then_risk != now_risk
            },
            {
                "label": "Weakest Phase",
                "then": then_phase,
                "now": now_phase,
                "changed": then_phase != now_phase
            }
        ],
        "directive": directive
    }


# ============================================
# TAB C: RECENT MOMENTUM (5 VS 5)
# Shows Top 3 issues + evidence links
# ============================================

def find_evidence_items(analyses: List[Dict], blunder_context: Dict) -> List[Dict]:
    """
    Find 2 strong evidence items for momentum tab.
    
    REUSES: blunder context examples from calculate_blunder_context_stats()
    """
    evidence = []
    
    # Evidence 1: Blunder when winning (from blunder_context)
    winning_examples = blunder_context.get("when_winning", {}).get("examples", [])
    if winning_examples:
        ex = winning_examples[0]
        evidence.append({
            "type": "blunder_when_winning",
            "label": "Blunder while winning",
            "game_id": ex.get("game_id"),
            "move_number": ex.get("move_number"),
            "description": f"Move {ex.get('move_number', '?')}"
        })
    
    # Evidence 2: Big mistake (from recent analyses)
    for analysis in analyses[:10]:
        sf = analysis.get("stockfish_analysis", {})
        game_id = analysis.get("game_id", "")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            
            if cp_loss >= 150:
                # Check not duplicate
                if not any(e["game_id"] == game_id and e["move_number"] == move.get("move_number") for e in evidence):
                    evidence.append({
                        "type": "big_mistake",
                        "label": "Significant mistake",
                        "game_id": game_id,
                        "move_number": move.get("move_number", 0),
                        "description": f"Move {move.get('move_number', '?')}"
                    })
                    break
        
        if len(evidence) >= 2:
            break
    
    return evidence[:2]


def compute_momentum_5v5(recent_games: List[Dict], games_for_pattern: List[Dict] = None) -> Dict:
    """
    Tab C - Recent Momentum (5 vs 5)
    
    Shows:
    - Headline (one line)
    - Top 3 issues (if meaningful/dominant)
    - Advantage discipline change with evidence
    - 2 Evidence items (with game links → /game/{id}?move={n}&src=journey)
    - Do this next
    
    REUSES: detect_weakness_patterns(), calculate_blunder_context_stats()
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
    
    # Calculate TSI stability
    recent_tsi = [calculate_game_tsi(g) for g in recent_5]
    previous_tsi = [calculate_game_tsi(g) for g in previous_5]
    
    recent_tsi_avg = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 50
    previous_tsi_avg = sum(previous_tsi) / len(previous_tsi) if previous_tsi else 50
    
    recent_stability = get_stability_band(recent_tsi_avg)
    previous_stability = get_stability_band(previous_tsi_avg)
    
    # REUSE: Blunder context for advantage discipline
    recent_context = calculate_blunder_context_stats(recent_5)
    previous_context = calculate_blunder_context_stats(previous_5)
    
    recent_winning_pct = recent_context.get("when_winning", {}).get("percentage", 0)
    previous_winning_pct = previous_context.get("when_winning", {}).get("percentage", 0)
    
    recent_risk = get_risk_band(recent_winning_pct)
    previous_risk = get_risk_band(previous_winning_pct)
    
    # REUSE: Weakness patterns for Top 3 issues
    recent_weaknesses = detect_weakness_patterns(recent_5, [])
    
    # Get Top 3 issues (only if meaningful)
    top_3_issues = []
    for w in recent_weaknesses[:3]:
        if w.get("occurrence_pct", 0) >= 25:  # Only include if meaningful (>25%)
            top_3_issues.append({
                "id": w["id"],
                "name": get_weakness_label(w["id"]),
                "impact": severity_to_impact_band(w.get("severity", "medium")),
                "occurrence_pct": w.get("occurrence_pct", 0),
                "examples": w.get("examples", [])[:1]  # Keep 1 example for linking
            })
    
    # Calculate deltas
    stability_delta = recent_tsi_avg - previous_tsi_avg
    context_delta = recent_winning_pct - previous_winning_pct
    
    # Generate headline (pick strongest signal)
    stability_changed = abs(stability_delta) >= 8
    risk_changed = previous_risk != recent_risk
    
    if not stability_changed and not risk_changed and not top_3_issues:
        headline = "No meaningful shift in last 10 games."
    elif stability_changed and risk_changed:
        if stability_delta > 0:
            if context_delta > 15:
                headline = "This week stability improved, but winning positions got riskier."
            else:
                headline = "This week stability improved and you're finishing games better."
        else:
            if top_3_issues:
                headline = f"This week stability dropped mainly due to {top_3_issues[0]['name'].lower()}."
            else:
                headline = "This week stability dropped. Need to slow down."
    elif stability_changed:
        if stability_delta > 0:
            headline = "This week your play became more stable."
        else:
            headline = "This week your play became less stable."
    elif risk_changed:
        if context_delta < -15:
            headline = "This week you're converting winning positions better."
        elif context_delta > 15:
            headline = "This week you're throwing more winning positions."
        else:
            headline = "No meaningful shift in last 10 games."
    elif top_3_issues:
        headline = f"Main issue right now: {top_3_issues[0]['name']}."
    else:
        headline = "No meaningful shift in last 10 games."
    
    # Advantage discipline change (5 vs 5)
    advantage_shift = None
    if abs(context_delta) > 15:
        advantage_shift = {
            "previous": RISK_LABELS[previous_risk.value],
            "recent": RISK_LABELS[recent_risk.value],
            "delta_pct": round(context_delta),
            "direction": "improving" if context_delta < 0 else "declining"
        }
    
    # Evidence items (from recent blunder context)
    evidence = find_evidence_items(recent_games, recent_context)
    
    # Directive based on top issue
    top_issue_id = top_3_issues[0]["id"] if top_3_issues else None
    directive = get_directive(top_issue_id)
    
    return {
        "ready": True,
        "headline": headline,
        "top_issues": top_3_issues,
        "advantage_shift": advantage_shift,
        "evidence": evidence,
        "evidence_ready": len(evidence) >= 2,
        "directive": directive
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
    accuracy_count = 0
    
    for game in window:
        sf = game.get("stockfish_analysis", {})
        
        # Accuracy
        accuracy = sf.get("accuracy", 0)
        if accuracy > 0:
            total_accuracy += accuracy
            accuracy_count += 1
        
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
        "accuracy": round(total_accuracy / accuracy_count, 1) if accuracy_count > 0 else 0,
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

def compute_journey(all_games: List[Dict], games_for_pattern: List[Dict] = None) -> Dict:
    """
    Main entry point for Journey page.
    
    Returns data for all 3 tabs + stats drawer:
    - snapshot: Tab A (Now) - shows Top 1 issue
    - journey: Tab B (Overall Journey)
    - momentum: Tab C (Recent Momentum) - shows Top 3 issues
    - stats: Collapsible stats drawer
    
    IMPORTANT: Reuses existing pattern detection from baseline_service.py
    """
    total_games = len(all_games)
    
    # Activation check
    if total_games < 10:
        return {
            "activated": False,
            "games_analyzed": total_games,
            "games_required": 10
        }
    
    # Use games_for_pattern if provided (from games collection), else empty
    pattern_games = games_for_pattern or []
    
    # Compute each tab
    snapshot = compute_snapshot_now(all_games, pattern_games)
    journey = compute_overall_journey(all_games, pattern_games)
    momentum = compute_momentum_5v5(all_games, pattern_games)
    stats = compute_stats_drawer(all_games)
    
    return {
        "activated": True,
        "games_analyzed": total_games,
        "snapshot": snapshot,
        "journey": journey,
        "momentum": momentum,
        "stats": stats
    }
