"""
Journey Engine v2 - Before/After Report

Architecture:
A) MICRO: Now vs Then (Recent 5 vs Previous 5)
B) MACRO: Becoming vs Started (Recent 15 vs First 15)
C) EVIDENCE: 2 clickable game links

Tone: Plain Indian-English, simple, direct.
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum


# Plain Indian-English labels for stability (simpler)
STABILITY_LABELS = {
    "STABLE": "Playing steady",
    "MIXED": "Hit and miss",
    "VOLATILE": "Too many slips",
    "CHAOTIC": "All over the place"
}

# Plain Indian-English labels for risk (simpler)
RISK_LABELS = {
    "LOW": "Finishing games well",
    "MEDIUM": "Sometimes losing grip when winning",
    "HIGH": "Throwing away winning positions"
}

# Pattern names in plain language (what it means, not technical term)
PATTERN_LABELS = {
    "structural_misjudgment": "Weak pawns or squares",
    "critical_moment_drift": "Losing focus at key moments", 
    "missed_forcing_move": "Missing winning moves",
    "advantage_mismanagement": "Relaxing when ahead",
    "random_critical_move": "Random moves when it matters"
}

# Action directives based on main driver (plain, direct)
DRIVER_DIRECTIVES = {
    "structural_misjudgment": "Next 5 games: before pawn moves, ask 'what becomes weak after this?'",
    "critical_moment_drift": "Next 5 games: when position changes, pause 10 seconds and scan threats.",
    "missed_forcing_move": "Next 5 games: every move do Checks → Captures → Threats.",
    "advantage_mismanagement": "Next 5 games: when ahead, play safe improving moves—no rushing.",
    "random_critical_move": "Next 5 games: in sharp positions, calculate 2 moves deeper before deciding."
}

# Weekly focus directives for macro level
MACRO_DIRECTIVES = {
    "improving": "Keep doing what you're doing. Your discipline is showing results.",
    "declining": "This week: slow down. Take 5 extra seconds before each move.",
    "same": "Time to push. Pick one weakness and drill it this week."
}


class StabilityBand(Enum):
    STABLE = "STABLE"
    MIXED = "MIXED"
    VOLATILE = "VOLATILE"
    CHAOTIC = "CHAOTIC"


class RiskBand(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SeverityBand(Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


# Rating cohort baselines
RATING_COHORTS = {
    "under_1200": {"avg_tsi": 50, "label": "<1200"},
    "1200_1599": {"avg_tsi": 58, "label": "1200-1599"},
    "1600_1999": {"avg_tsi": 68, "label": "1600-1999"},
    "2000_plus": {"avg_tsi": 78, "label": "2000+"}
}


def get_rating_cohort(rating: int) -> Dict:
    if rating < 1200:
        return RATING_COHORTS["under_1200"]
    elif rating < 1600:
        return RATING_COHORTS["1200_1599"]
    elif rating < 2000:
        return RATING_COHORTS["1600_1999"]
    return RATING_COHORTS["2000_plus"]


def get_stability_band(tsi_avg: float) -> StabilityBand:
    """Map TSI average to stability band."""
    if tsi_avg >= 75:
        return StabilityBand.STABLE
    elif tsi_avg >= 55:
        return StabilityBand.MIXED
    elif tsi_avg >= 35:
        return StabilityBand.VOLATILE
    return StabilityBand.CHAOTIC


def get_stability_label(band: StabilityBand) -> str:
    return STABILITY_LABELS.get(band.value, "Unknown")


def get_risk_band(blunder_rate: float) -> RiskBand:
    """Map blunders-when-ahead rate to risk band."""
    if blunder_rate <= 30:
        return RiskBand.LOW
    elif blunder_rate <= 55:
        return RiskBand.MEDIUM
    return RiskBand.HIGH


def get_risk_label(band: RiskBand) -> str:
    return RISK_LABELS.get(band.value, "Unknown")


def get_pattern_label(key: str) -> str:
    return PATTERN_LABELS.get(key, key.replace("_", " ").title())


def get_severity_band(score: float) -> SeverityBand:
    """Map pattern severity to band."""
    if score <= 0.20:
        return SeverityBand.LOW
    elif score <= 0.50:
        return SeverityBand.MODERATE
    return SeverityBand.HIGH


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
    """Calculate blunder context for a window."""
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
        return {"winning_rate": 0, "total": 0}
    
    return {
        "winning_rate": round((winning / total) * 100),
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
    """Get primary driver if it explains >= 35% of instability."""
    if not scores:
        return None, 0
    
    top_driver = max(scores, key=scores.get)
    top_share = scores[top_driver]
    
    if top_share >= 0.35:
        return top_driver, top_share
    return None, 0


def calculate_phase_instability(analyses: List[Dict]) -> str:
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


def find_evidence_games(analyses: List[Dict]) -> List[Dict]:
    """Find 2 evidence examples: one negative (blunder when ahead), one positive if available."""
    evidence = []
    
    # Find a blunder when ahead (negative)
    for i, analysis in enumerate(analyses):
        sf = analysis.get("stockfish_analysis", {})
        user_color = analysis.get("user_color", "white")
        game_id = analysis.get("game_id", f"game_{i}")
        
        for move in sf.get("move_evaluations", []):
            cp_loss = abs(move.get("cp_loss", 0))
            if cp_loss < 150:
                continue
            
            eval_before = move.get("eval_before", 0)
            if user_color == "black":
                eval_before = -eval_before
            
            if eval_before >= 150:  # Was winning
                evidence.append({
                    "type": "negative",
                    "label": "Blunder in winning position",
                    "game_index": i,
                    "move_number": move.get("move_number", 0),
                    "description": f"Game {i+1}, Move {move.get('move_number', '?')}"
                })
                break
        
        if len(evidence) >= 1:
            break
    
    # Find a good decision (positive) - look for moves where user didn't blunder in critical moment
    for i, analysis in enumerate(analyses):
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Look for a complex position handled well
        for move in moves:
            cp_loss = abs(move.get("cp_loss", 0))
            complexity = move.get("position_complexity", 0)
            
            if complexity > 0.5 and cp_loss < 30:
                evidence.append({
                    "type": "positive",
                    "label": "Critical moment handled well",
                    "game_index": i,
                    "move_number": move.get("move_number", 0),
                    "description": f"Game {i+1}, Move {move.get('move_number', '?')}"
                })
                break
        
        if len(evidence) >= 2:
            break
    
    # If we don't have 2, fill with more negative examples
    while len(evidence) < 2:
        for i, analysis in enumerate(analyses[len(evidence):]):
            sf = analysis.get("stockfish_analysis", {})
            for move in sf.get("move_evaluations", []):
                cp_loss = abs(move.get("cp_loss", 0))
                if cp_loss >= 100:
                    evidence.append({
                        "type": "negative",
                        "label": "Significant mistake",
                        "game_index": i + len(evidence),
                        "move_number": move.get("move_number", 0),
                        "description": f"Game {i+1+len(evidence)}, Move {move.get('move_number', '?')}"
                    })
                    break
            if len(evidence) >= 2:
                break
        break
    
    return evidence[:2]


def compute_micro(recent_5: List[Dict], previous_5: List[Dict], 
                  classify_func, severity_func) -> Dict:
    """
    Compute MICRO: Now vs Then (5 vs 5)
    
    Returns exactly 3 rows + headline + what_changed
    """
    # Calculate metrics for both windows
    recent_tsi = [calculate_game_tsi(g) for g in recent_5]
    previous_tsi = [calculate_game_tsi(g) for g in previous_5]
    
    recent_tsi_avg = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 50
    previous_tsi_avg = sum(previous_tsi) / len(previous_tsi) if previous_tsi else 50
    
    recent_context = calculate_blunder_context(recent_5)
    previous_context = calculate_blunder_context(previous_5)
    
    recent_patterns = calculate_pattern_scores(recent_5, classify_func, severity_func)
    previous_patterns = calculate_pattern_scores(previous_5, classify_func, severity_func)
    
    # Row 1: Decision Stability
    recent_stability_band = get_stability_band(recent_tsi_avg)
    previous_stability_band = get_stability_band(previous_tsi_avg)
    stability_delta = recent_tsi_avg - previous_tsi_avg
    
    # Row 2: Advantage Discipline
    recent_risk_band = get_risk_band(recent_context["winning_rate"])
    previous_risk_band = get_risk_band(previous_context["winning_rate"])
    context_delta = recent_context["winning_rate"] - previous_context["winning_rate"]
    
    # Row 3: Primary Driver
    recent_driver, recent_share = get_primary_driver(recent_patterns)
    
    # Impact scoring for headline
    stability_impact = abs(stability_delta)
    context_impact = abs(context_delta)
    
    # Pattern band changes
    pattern_changes = []
    for cat in recent_patterns:
        recent_band = get_severity_band(recent_patterns.get(cat, 0))
        previous_band = get_severity_band(previous_patterns.get(cat, 0))
        if recent_band != previous_band:
            direction = "improved" if recent_band.value < previous_band.value else "worsened"
            pattern_changes.append({
                "category": cat,
                "previous": previous_band.value,
                "recent": recent_band.value,
                "direction": direction
            })
    
    pattern_impact = len(pattern_changes) * 5
    
    # Generate headline in plain Indian-English
    impacts = {
        "stability": stability_impact,
        "context": context_impact,
        "pattern": pattern_impact
    }
    strongest = max(impacts, key=impacts.get)
    
    if impacts[strongest] < 3:
        headline = "Same pattern: no big change in your recent games."
    elif strongest == "stability":
        if stability_delta > 0:
            if context_delta > 10:
                headline = "Good: you are more stable, but still slipping when ahead."
            else:
                headline = "Good: your decision-making is more steady now."
        else:
            if recent_driver:
                driver_name = get_pattern_label(recent_driver)
                headline = f"Issue: stability dropped, mainly because of {driver_name.lower()}."
            else:
                headline = "Issue: your decisions are less steady in recent games."
    elif strongest == "context":
        if context_delta > 0:
            headline = "Issue: you are still slipping after getting advantage."
        else:
            headline = "Good: you are handling winning positions better."
    else:
        if pattern_changes:
            change = pattern_changes[0]
            name = get_pattern_label(change["category"])
            if change["direction"] == "improved":
                headline = f"Good: {name.lower()} is happening less often."
            else:
                headline = f"Issue: {name.lower()} is happening more often."
        else:
            headline = "Same pattern: no big change in your recent games."
    
    # What changed with meaning
    what_changed = []
    for change in pattern_changes[:2]:
        name = get_pattern_label(change["category"])
        if change["direction"] == "improved":
            what_changed.append(f"{name}: {change['previous']} → {change['recent']} (this is improving)")
        else:
            what_changed.append(f"{name}: {change['previous']} → {change['recent']} (this is slipping)")
    
    # Action directive based on main driver
    directive = DRIVER_DIRECTIVES.get(
        recent_driver, 
        "Next 5 games: before every move, do Checks → Captures → Threats."
    )
    
    return {
        "headline": headline,
        "rows": [
            {
                "label": "Decision Stability",
                "previous": get_stability_label(previous_stability_band),
                "recent": get_stability_label(recent_stability_band),
                "changed": previous_stability_band != recent_stability_band
            },
            {
                "label": "Advantage Discipline", 
                "previous": get_risk_label(previous_risk_band),
                "recent": get_risk_label(recent_risk_band),
                "changed": previous_risk_band != recent_risk_band
            },
            {
                "label": "Main reason",
                "value": get_pattern_label(recent_driver) if recent_driver else "No single cause",
                "note": "(most of your slips come from this)" if recent_driver else "(mistakes are spread across different areas)"
            }
        ],
        "what_changed": what_changed,
        "directive": directive,
        "metrics": {
            "tsi_previous": round(previous_tsi_avg),
            "tsi_recent": round(recent_tsi_avg),
            "tsi_delta": round(stability_delta),
            "context_previous": previous_context["winning_rate"],
            "context_recent": recent_context["winning_rate"],
            "context_delta": round(context_delta)
        }
    }


def compute_macro(recent_15: List[Dict], first_15: List[Dict],
                  classify_func, severity_func, user_rating: int) -> Dict:
    """
    Compute MACRO: Becoming vs Started (15 vs 15)
    
    Plain Indian-English, with directive.
    """
    # Calculate metrics
    recent_tsi = [calculate_game_tsi(g) for g in recent_15]
    first_tsi = [calculate_game_tsi(g) for g in first_15]
    
    recent_tsi_avg = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 50
    first_tsi_avg = sum(first_tsi) / len(first_tsi) if first_tsi else 50
    
    recent_patterns = calculate_pattern_scores(recent_15, classify_func, severity_func)
    first_patterns = calculate_pattern_scores(first_15, classify_func, severity_func)
    
    recent_phase = calculate_phase_instability(recent_15)
    first_phase = calculate_phase_instability(first_15)
    
    # Row 1: Long-term Stability - plain language
    recent_band = get_stability_band(recent_tsi_avg)
    first_band = get_stability_band(first_tsi_avg)
    stability_delta = recent_tsi_avg - first_tsi_avg
    
    if stability_delta >= 8:
        stability_clause = "Overall you're improving, but still work to do."
    elif stability_delta <= -8:
        stability_clause = "Your stability has dropped compared to earlier."
    else:
        stability_clause = "No big change over time yet."
    
    # Row 2: Weakness Evolution
    first_driver, first_share = get_primary_driver(first_patterns)
    if first_driver:
        first_driver_band = get_severity_band(first_patterns.get(first_driver, 0))
        recent_driver_band = get_severity_band(recent_patterns.get(first_driver, 0))
        driver_evolution = {
            "driver": first_driver.replace("_", " ").title(),
            "first_band": first_driver_band.value,
            "recent_band": recent_driver_band.value,
            "changed": first_driver_band != recent_driver_band
        }
    else:
        driver_evolution = {
            "driver": None,
            "text": "Primary weakness unchanged"
        }
    
    # Row 3: Phase Evolution
    phase_changed = first_phase != recent_phase
    
    # Row 4: Peer Context
    cohort = get_rating_cohort(user_rating)
    peer_delta = recent_tsi_avg - cohort["avg_tsi"]
    
    if len(recent_15) < 10:
        peer_text = "Peer comparison unavailable (insufficient games)"
        peer_status = "unavailable"
    elif peer_delta >= 8:
        peer_text = "Compared to similar-rated players: Above average"
        peer_status = "above"
    elif peer_delta <= -8:
        peer_text = "Compared to similar-rated players: Below average"
        peer_status = "below"
    else:
        peer_text = "Compared to similar-rated players: In line"
        peer_status = "inline"
    
    # Determine macro directive
    if stability_delta >= 8:
        macro_directive = MACRO_DIRECTIVES["improving"]
    elif stability_delta <= -8:
        macro_directive = MACRO_DIRECTIVES["declining"]
    else:
        macro_directive = MACRO_DIRECTIVES["same"]
    
    return {
        "rows": [
            {
                "label": "Long-term Stability",
                "first": first_band.value,
                "recent": recent_band.value,
                "clause": stability_clause
            },
            {
                "label": "Weakness Evolution",
                "driver": driver_evolution.get("driver"),
                "first_band": driver_evolution.get("first_band"),
                "recent_band": driver_evolution.get("recent_band"),
                "changed": driver_evolution.get("changed", False),
                "text": driver_evolution.get("text")
            },
            {
                "label": "Phase Evolution",
                "first": first_phase,
                "recent": recent_phase,
                "changed": phase_changed
            },
            {
                "label": "Peer Context",
                "text": peer_text,
                "status": peer_status
            }
        ],
        "directive": macro_directive,
        "metrics": {
            "tsi_first": round(first_tsi_avg),
            "tsi_recent": round(recent_tsi_avg),
            "cohort_label": cohort["label"]
        }
    }


def compute_journey(all_games: List[Dict], classify_func, severity_func, 
                    user_rating: int = 1200) -> Dict:
    """
    Main entry point for Journey computation.
    
    Returns the full journey report with:
    - micro: Now vs Then (5 vs 5)
    - macro: Becoming vs Started (15 vs 15)
    - evidence: 2 game links
    """
    total_games = len(all_games)
    
    # Activation check
    if total_games < 10:
        return {
            "activated": False,
            "games_analyzed": total_games,
            "games_required": 10
        }
    
    # MICRO: Recent 5 vs Previous 5
    recent_5 = all_games[:5]
    previous_5 = all_games[5:10]
    
    micro = compute_micro(recent_5, previous_5, classify_func, severity_func)
    
    # MACRO: Recent 15 vs First 15 (if enough games)
    macro = None
    if total_games >= 30:
        recent_15 = all_games[:15]
        first_15 = all_games[-15:]  # First 15 (oldest)
        macro = compute_macro(recent_15, first_15, classify_func, severity_func, user_rating)
    
    # EVIDENCE: 2 game links
    evidence = find_evidence_games(all_games[:20])
    
    return {
        "activated": True,
        "games_analyzed": total_games,
        "micro": micro,
        "macro": macro,
        "evidence": evidence
    }
