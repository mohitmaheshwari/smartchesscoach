"""
Journey Engine v4 - Master Spec Implementation

INTEGRATES:
- Stat Interpretation Engine (threshold-based signals)
- Coach Voice Generator (deterministic Indian English)
- Reuses baseline_service.py patterns

Tabs:
A) NOW (Snapshot): 5 items + directive
B) JOURNEY (Overall): 4 stat rows + 4 cognitive rows + directive
C) TREND (Momentum): headline + top issues + advantage shift + evidence + directive

Rules from Master Spec:
- No raw numbers on surface (bands only)
- Hide deltas when stable_hidden
- One instruction per tab
- Plain Indian-English tone
"""

from typing import Dict, List, Optional

# Import engines
from stat_interpretation_engine import (
    interpret_stats,
    extract_metrics_from_analyses,
    calculate_stability_band,
    StabilityBand
)
from coach_voice_generator import (
    generate_tab_voice,
    get_instruction,
    should_show_improvement_badge,
    get_badge_text
)

# Reuse existing pattern analysis
from baseline_service import (
    calculate_blunder_context_stats,
    detect_weakness_patterns
)


# ============================================
# LABELS - Plain Indian-English (Master Spec Section 12)
# ============================================

STABILITY_BAND_LABELS = {
    "stable": "Stable",
    "moderate": "Moderate",
    "volatile": "Volatile"
}

STABILITY_BAND_MEANING = {
    "stable": "Your decision quality is becoming consistent.",
    "moderate": "Mostly okay, but some lapses still happen.",
    "volatile": "Your games swing a lot. Clean games, then sudden slips."
}

RISK_BAND_LABELS = {
    "low": "Low risk",
    "medium": "Medium risk",
    "high": "High risk"
}

RISK_BAND_MEANING = {
    "low": "You finish winning games well.",
    "medium": "Sometimes you relax when ahead.",
    "high": "When ahead, you relax and make mistakes."
}

# Weakness labels (plain language)
WEAKNESS_LABELS = {
    "relaxes_when_winning": "Relaxes when winning",
    "piece_safety": "Piece safety issues",
    "tactical_blindness": "Misses tactics",
    "time_trouble": "Time trouble blunders",
    "structural_misjudgment": "Structural mistakes",
    "critical_moment_drift": "Critical moment drift",
    "missed_forcing_move": "Missing winning moves",
    "advantage_mismanagement": "Relaxes when winning",
    "random_critical_move": "Random moves in key spots",
    "time_pressure_drop": "Time pressure mistakes"
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_weakness_label(weakness_id: str) -> str:
    """Get human-readable label for weakness ID."""
    return WEAKNESS_LABELS.get(weakness_id, weakness_id.replace("_", " ").title())


def get_risk_band_from_blunder_context(blunder_context: Dict) -> str:
    """Get risk band from blunder context stats."""
    winning_pct = blunder_context.get("when_winning", {}).get("percentage", 0)
    if winning_pct <= 30:
        return "low"
    elif winning_pct <= 55:
        return "medium"
    return "high"


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
        return "middlegame"
    
    return max(phase_scores, key=phase_scores.get)


def severity_to_band(severity: str) -> str:
    """Convert severity label to band."""
    if severity == "high":
        return "High"
    elif severity == "medium":
        return "Moderate"
    return "Low"


# ============================================
# TAB A: SNAPSHOT (NOW) - Section 8
# ============================================

def compute_snapshot_now(recent_games: List[Dict]) -> Dict:
    """
    Tab A - Snapshot (Current)
    
    Shows EXACTLY 5 items:
    1) Decision Stability (band + one plain meaning line)
    2) Top Issue Right Now (TOP 1) - "Main issue: {primary_driver}"
    3) Advantage Discipline (band only)
    4) Weakest Phase
    5) Do this next (one instruction)
    
    No deltas. No stats blocks on main surface.
    """
    if len(recent_games) < 5:
        return {
            "ready": False,
            "games_needed": 5 - len(recent_games),
            "message": f"Need {5 - len(recent_games)} more games for snapshot."
        }
    
    # Use 10-15 games for snapshot (prefer 15)
    window_size = min(15, max(10, len(recent_games)))
    window = recent_games[:window_size]
    
    # Extract metrics for stability band
    metrics = extract_metrics_from_analyses(window)
    stability_band = calculate_stability_band(metrics["blunders_per_game"])
    
    # Get blunder context for advantage discipline
    blunder_context = calculate_blunder_context_stats(window)
    risk_band = get_risk_band_from_blunder_context(blunder_context)
    
    # Detect weakness patterns - get TOP 1
    weaknesses = detect_weakness_patterns(window, [])
    top_issue = None
    top_issue_id = None
    if weaknesses:
        top = weaknesses[0]
        top_issue = {
            "name": get_weakness_label(top["id"]),
            "id": top["id"]
        }
        top_issue_id = top["id"]
    
    # Get weakest phase
    unstable_phase = get_most_unstable_phase(window)
    
    # Generate voice (for instruction)
    voice = generate_tab_voice(
        stat_interpretation={"evaluation_ready": True, "stability_band": stability_band.value, 
                            "signals": {"headline": "stable"}, "confidence": 1.0},
        primary_driver=top_issue_id,
        phase_instability=unstable_phase,
        advantage_risk=risk_band
    )
    
    return {
        "ready": True,
        "decision_stability": {
            "band": STABILITY_BAND_LABELS.get(stability_band.value, stability_band.value),
            "meaning": STABILITY_BAND_MEANING.get(stability_band.value, "")
        },
        "top_issue": top_issue if top_issue else {
            "name": "No clear pattern",
            "id": None
        },
        "advantage_discipline": {
            "band": RISK_BAND_LABELS.get(risk_band, risk_band),
            "meaning": RISK_BAND_MEANING.get(risk_band, "")
        },
        "unstable_phase": unstable_phase.capitalize(),
        "directive": voice["focus_instruction"]
    }


# ============================================
# TAB B: JOURNEY (OVERALL THEN VS NOW) - Section 8
# ============================================

def compute_overall_journey(all_games: List[Dict]) -> Dict:
    """
    Tab B - Overall Journey (Then vs Now)
    
    Shows:
    A) 4 stat comparison rows (Accuracy, Blunders/Game, Mistakes/Game, Win Rate)
       - Show deltas only if overall_change = visible
       - If stable_hidden, show "Overall stable" and hide deltas
    
    B) 4 cognitive growth rows (band-based):
       1) Decision Stability band: Then → Now
       2) Primary Driver Evolution: Then → Now
       3) Advantage risk band: Then → Now
       4) Phase evolution: Then → Now
    
    C) One "Do this next" line (based on NOW driver)
    """
    total = len(all_games)
    
    if total < 15:
        return {
            "ready": False,
            "games_needed": 15 - total,
            "message": f"Need {15 - total} more games to see your journey."
        }
    
    # THEN = first 15 games (oldest), NOW = latest 15 games
    then_games = all_games[-15:]  # Oldest 15
    now_games = all_games[:15]    # Recent 15
    
    # Extract metrics
    then_metrics = extract_metrics_from_analyses(then_games)
    now_metrics = extract_metrics_from_analyses(now_games)
    
    # Run Stat Interpretation Engine
    stat_interpretation = interpret_stats(then_metrics, now_metrics)
    
    # Calculate cognitive bands for THEN
    then_stability = calculate_stability_band(then_metrics["blunders_per_game"])
    then_context = calculate_blunder_context_stats(then_games)
    then_risk = get_risk_band_from_blunder_context(then_context)
    then_weaknesses = detect_weakness_patterns(then_games, [])
    then_driver = then_weaknesses[0]["id"] if then_weaknesses else None
    then_phase = get_most_unstable_phase(then_games)
    
    # Calculate cognitive bands for NOW
    now_stability = calculate_stability_band(now_metrics["blunders_per_game"])
    now_context = calculate_blunder_context_stats(now_games)
    now_risk = get_risk_band_from_blunder_context(now_context)
    now_weaknesses = detect_weakness_patterns(now_games, [])
    now_driver = now_weaknesses[0]["id"] if now_weaknesses else None
    now_phase = get_most_unstable_phase(now_games)
    
    # Generate voice
    voice = generate_tab_voice(
        stat_interpretation=stat_interpretation,
        primary_driver=now_driver,
        phase_instability=now_phase,
        advantage_risk=now_risk
    )
    
    # Build stat comparison rows (show deltas only if visible)
    show_deltas = stat_interpretation.get("show_deltas", False)
    deltas = stat_interpretation.get("deltas", {})
    
    stat_rows = [
        {
            "label": "Accuracy",
            "then": f"{then_metrics['accuracy']}%",
            "now": f"{now_metrics['accuracy']}%",
            "delta": f"+{deltas['accuracy']}%" if deltas.get('accuracy', 0) > 0 else f"{deltas.get('accuracy', 0)}%",
            "show_delta": show_deltas and abs(deltas.get('accuracy', 0)) >= 2
        },
        {
            "label": "Blunders/Game",
            "then": str(then_metrics['blunders_per_game']),
            "now": str(now_metrics['blunders_per_game']),
            "delta": f"{-deltas['blunders']}" if deltas.get('blunders', 0) != 0 else "0",  # Negative = worse
            "show_delta": show_deltas and abs(deltas.get('blunders', 0)) >= 0.3,
            "lower_is_better": True
        },
        {
            "label": "Mistakes/Game",
            "then": str(then_metrics['mistakes_per_game']),
            "now": str(now_metrics['mistakes_per_game']),
            "delta": f"{-deltas['mistakes']}" if deltas.get('mistakes', 0) != 0 else "0",
            "show_delta": show_deltas and abs(deltas.get('mistakes', 0)) >= 0.4,
            "lower_is_better": True
        },
        {
            "label": "Win Rate",
            "then": f"{then_metrics['winrate']}%",
            "now": f"{now_metrics['winrate']}%",
            "delta": f"+{deltas['winrate']}%" if deltas.get('winrate', 0) > 0 else f"{deltas.get('winrate', 0)}%",
            "show_delta": show_deltas and abs(deltas.get('winrate', 0)) >= 5
        }
    ]
    
    # Build cognitive growth rows
    cognitive_rows = [
        {
            "label": "Decision Stability",
            "then": STABILITY_BAND_LABELS.get(then_stability.value, then_stability.value),
            "now": STABILITY_BAND_LABELS.get(now_stability.value, now_stability.value),
            "changed": then_stability != now_stability
        },
        {
            "label": "Primary Driver",
            "then": get_weakness_label(then_driver) if then_driver else "No clear pattern",
            "now": get_weakness_label(now_driver) if now_driver else "No clear pattern",
            "changed": then_driver != now_driver
        },
        {
            "label": "Advantage Risk",
            "then": RISK_BAND_LABELS.get(then_risk, then_risk),
            "now": RISK_BAND_LABELS.get(now_risk, now_risk),
            "changed": then_risk != now_risk
        },
        {
            "label": "Weakest Phase",
            "then": then_phase.capitalize(),
            "now": now_phase.capitalize(),
            "changed": then_phase != now_phase
        }
    ]
    
    return {
        "ready": True,
        "voice": voice,
        "overall_change": stat_interpretation.get("overall_change", "visible"),
        "show_deltas": show_deltas,
        "stat_rows": stat_rows,
        "cognitive_rows": cognitive_rows,
        "directive": voice["focus_instruction"],
        "badge": voice.get("badge")
    }


# ============================================
# TAB C: TREND (MOMENTUM 5 VS 5) - Section 8
# ============================================

def find_evidence_items(analyses: List[Dict], blunder_context: Dict) -> List[Dict]:
    """Find 2 evidence items for momentum tab."""
    evidence = []
    
    # Evidence 1: Blunder when winning
    winning_examples = blunder_context.get("when_winning", {}).get("examples", [])
    if winning_examples:
        ex = winning_examples[0]
        evidence.append({
            "type": "blunder_when_winning",
            "label": "Blunder while winning",
            "game_id": ex.get("game_id"),
            "move_number": ex.get("move_number"),
            "description": f"Game, Move {ex.get('move_number', '?')}"
        })
    
    # Evidence 2: Critical moment / big mistake
    for analysis in analyses[:10]:
        sf = analysis.get("stockfish_analysis", {})
        game_id = analysis.get("game_id", "")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss >= 150:
                if not any(e["game_id"] == game_id and e["move_number"] == move.get("move_number") for e in evidence):
                    evidence.append({
                        "type": "critical_moment",
                        "label": "Critical moment slip",
                        "game_id": game_id,
                        "move_number": move.get("move_number", 0),
                        "description": f"Game, Move {move.get('move_number', '?')}"
                    })
                    break
        
        if len(evidence) >= 2:
            break
    
    return evidence[:2]


def compute_momentum_5v5(recent_games: List[Dict]) -> Dict:
    """
    Tab C - Recent Momentum (5 vs 5)
    
    Shows:
    A) One headline (from Stat Engine priority)
    B) Max 2 meaningful shifts (pattern band OR advantage >15%)
       - If nothing meaningful, show ONE line: "No meaningful change in last 10 games."
    C) Evidence: 2 links OR fallback line
    D) One "Do this next" line
    """
    if len(recent_games) < 10:
        return {
            "ready": False,
            "games_needed": 10 - len(recent_games),
            "message": f"Need {10 - len(recent_games)} more games for momentum tracking."
        }
    
    # PREVIOUS = games 6-10, RECENT = last 5
    recent_5 = recent_games[:5]
    previous_5 = recent_games[5:10]
    
    # Extract metrics
    recent_metrics = extract_metrics_from_analyses(recent_5)
    previous_metrics = extract_metrics_from_analyses(previous_5)
    
    # Run Stat Interpretation Engine
    stat_interpretation = interpret_stats(previous_metrics, recent_metrics)
    
    # Get blunder context for advantage discipline change
    recent_context = calculate_blunder_context_stats(recent_5)
    previous_context = calculate_blunder_context_stats(previous_5)
    
    recent_winning_pct = recent_context.get("when_winning", {}).get("percentage", 0)
    previous_winning_pct = previous_context.get("when_winning", {}).get("percentage", 0)
    winning_shift = recent_winning_pct - previous_winning_pct
    
    recent_risk = get_risk_band_from_blunder_context(recent_context)
    previous_risk = get_risk_band_from_blunder_context(previous_context)
    
    # Detect weaknesses for TOP 3 issues
    recent_weaknesses = detect_weakness_patterns(recent_5, [])
    
    # Get top 3 issues (only if >= 25% occurrence)
    top_issues = []
    for w in recent_weaknesses[:3]:
        if w.get("occurrence_pct", 0) >= 25:
            top_issues.append({
                "id": w["id"],
                "name": get_weakness_label(w["id"]),
                "impact": severity_to_band(w.get("severity", "medium"))
            })
    
    now_driver = recent_weaknesses[0]["id"] if recent_weaknesses else None
    now_phase = get_most_unstable_phase(recent_5)
    
    # Generate voice
    voice = generate_tab_voice(
        stat_interpretation=stat_interpretation,
        primary_driver=now_driver,
        phase_instability=now_phase,
        advantage_risk=recent_risk
    )
    
    # Build meaningful shifts (max 2)
    meaningful_shifts = []
    
    # Check stability band shift
    recent_stability = calculate_stability_band(recent_metrics["blunders_per_game"])
    previous_stability = calculate_stability_band(previous_metrics["blunders_per_game"])
    
    if recent_stability != previous_stability:
        direction = "improving" if recent_stability.value == "stable" or (recent_stability.value == "moderate" and previous_stability.value == "volatile") else "declining"
        meaningful_shifts.append({
            "type": "stability",
            "label": "Decision Stability",
            "previous": STABILITY_BAND_LABELS.get(previous_stability.value, previous_stability.value),
            "recent": STABILITY_BAND_LABELS.get(recent_stability.value, recent_stability.value),
            "direction": direction
        })
    
    # Check advantage discipline shift (>15% change)
    if abs(winning_shift) >= 15:
        direction = "improving" if winning_shift < 0 else "declining"
        meaningful_shifts.append({
            "type": "advantage",
            "label": "Advantage Discipline",
            "previous": RISK_BAND_LABELS.get(previous_risk, previous_risk),
            "recent": RISK_BAND_LABELS.get(recent_risk, recent_risk),
            "direction": direction,
            "delta_pct": round(winning_shift)
        })
    
    # Evidence items
    evidence = find_evidence_items(recent_games, recent_context)
    
    # Determine if we have meaningful change or show "no change" line
    has_meaningful_change = len(meaningful_shifts) > 0 or stat_interpretation.get("overall_change") == "visible"
    
    return {
        "ready": True,
        "voice": voice,
        "headline": voice["headline"],
        "has_meaningful_change": has_meaningful_change,
        "meaningful_shifts": meaningful_shifts[:2],
        "top_issues": top_issues,
        "evidence": evidence,
        "evidence_ready": len(evidence) >= 2,
        "directive": voice["focus_instruction"],
        "badge": voice.get("badge")
    }


# ============================================
# STATS DRAWER (Section 10)
# ============================================

def compute_stats_drawer(recent_games: List[Dict], then_games: List[Dict] = None) -> Dict:
    """
    Collapsible stats drawer - for Indian users who like numbers.
    
    Shows only 4 metrics: Accuracy, Blunders/Game, Mistakes/Game, Win Rate
    """
    if len(recent_games) < 5:
        return {"ready": False}
    
    now_metrics = extract_metrics_from_analyses(recent_games[:20])
    
    result = {
        "ready": True,
        "now": {
            "accuracy": now_metrics["accuracy"],
            "blunders_per_game": now_metrics["blunders_per_game"],
            "mistakes_per_game": now_metrics["mistakes_per_game"],
            "winrate": now_metrics["winrate"]
        },
        "games_count": now_metrics["games"]
    }
    
    # Add THEN metrics for Journey tab comparison
    if then_games and len(then_games) >= 5:
        then_metrics = extract_metrics_from_analyses(then_games)
        result["then"] = {
            "accuracy": then_metrics["accuracy"],
            "blunders_per_game": then_metrics["blunders_per_game"],
            "mistakes_per_game": then_metrics["mistakes_per_game"],
            "winrate": then_metrics["winrate"]
        }
    
    return result


# ============================================
# MAIN ENTRY POINT
# ============================================

def compute_journey(all_games: List[Dict]) -> Dict:
    """
    Main entry point for Journey page.
    
    Returns data for all 3 tabs + stats drawer:
    - snapshot: Tab A (Now)
    - journey: Tab B (Overall Journey)
    - momentum: Tab C (Trend)
    - stats: Collapsible stats drawer
    """
    total_games = len(all_games)
    
    # Activation check (Section 2)
    if total_games < 10:
        return {
            "activated": False,
            "games_analyzed": total_games,
            "games_required": 10
        }
    
    # Compute each tab
    snapshot = compute_snapshot_now(all_games)
    journey = compute_overall_journey(all_games)
    momentum = compute_momentum_5v5(all_games)
    
    # Stats drawer with THEN/NOW comparison
    then_games = all_games[-15:] if len(all_games) >= 15 else []
    stats = compute_stats_drawer(all_games, then_games)
    
    return {
        "activated": True,
        "games_analyzed": total_games,
        "snapshot": snapshot,
        "journey": journey,
        "momentum": momentum,
        "stats": stats
    }
