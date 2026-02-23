"""
Journey Engine - Cognitive Evolution System

Architecture:
1. SHORT-TERM MOMENTUM (5 vs 5)
2. LONG-TERM GROWTH ARC (Early vs Recent)
3. Rating-Aware Commentary
4. Playing Style Adaptation

Core Principle: Never "invent insight" - all commentary derived from measured deltas.
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum


class CognitiveBand(Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


# Rating cohort baselines (pre-computed expectations)
RATING_COHORTS = {
    "under_1000": {"avg_tsi": 45, "avg_blunder_rate": 0.12, "label": "<1000"},
    "1000_1399": {"avg_tsi": 55, "avg_blunder_rate": 0.08, "label": "1000-1399"},
    "1400_1799": {"avg_tsi": 65, "avg_blunder_rate": 0.05, "label": "1400-1799"},
    "1800_plus": {"avg_tsi": 75, "avg_blunder_rate": 0.03, "label": "1800+"}
}


def get_rating_cohort(rating: int) -> Dict:
    """Get cohort baseline for a rating."""
    if rating < 1000:
        return RATING_COHORTS["under_1000"]
    elif rating < 1400:
        return RATING_COHORTS["1000_1399"]
    elif rating < 1800:
        return RATING_COHORTS["1400_1799"]
    else:
        return RATING_COHORTS["1800_plus"]


def get_band(score: float) -> CognitiveBand:
    """Map score to impact band."""
    if score <= 0.20:
        return CognitiveBand.LOW
    elif score <= 0.50:
        return CognitiveBand.MODERATE
    return CognitiveBand.HIGH


def calculate_game_tsi(analysis: Dict) -> int:
    """Calculate TSI for a single game (0-100 scale)."""
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    if not moves:
        return 90  # No data = assume stable
    
    total_mistakes = 0
    total_severity = 0
    
    for move in moves:
        cp_loss = abs(move.get("cp_loss", 0))
        if cp_loss >= 50:
            total_mistakes += 1
            total_severity += min(1.0, cp_loss / 300)
    
    if total_mistakes == 0:
        return 90  # No mistakes = high stability (not perfect)
    
    avg_severity = total_severity / total_mistakes
    mistakes_per_move = total_mistakes / max(len(moves), 1)
    
    # TSI formula: penalize mistakes weighted by severity
    instability = (mistakes_per_move * avg_severity) * 10
    instability = min(1.0, instability)
    
    return max(20, min(95, int(100 - instability * 80)))


def calculate_game_cognitive_scores(analysis: Dict, classify_func, severity_func) -> Dict[str, float]:
    """Calculate cognitive category scores for a single game."""
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    scores = {
        "structural_misjudgment": 0,
        "critical_moment_drift": 0,
        "missed_forcing_move": 0,
        "random_critical_move": 0,
        "advantage_mismanagement": 0
    }
    
    for move in moves:
        cp_loss = abs(move.get("cp_loss", 0))
        if cp_loss < 50:
            continue
        
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
        elif cp_loss >= 150:
            scores["random_critical_move"] += severity_func(cp_loss)
        else:
            scores["structural_misjudgment"] += severity_func(cp_loss)
    
    # Normalize by game length
    move_count = max(len(moves), 1)
    for key in scores:
        scores[key] = scores[key] / move_count
    
    return scores


def calculate_blunder_context(analysis: Dict) -> Dict[str, int]:
    """Calculate blunder context distribution for a single game."""
    sf = analysis.get("stockfish_analysis", {})
    user_color = analysis.get("user_color", "white")
    
    context = {"winning": 0, "equal": 0, "losing": 0, "total": 0}
    
    for move in sf.get("move_evaluations", []):
        cp_loss = abs(move.get("cp_loss", 0))
        if cp_loss < 100:
            continue
        
        context["total"] += 1
        eval_before = move.get("eval_before", 0)
        if user_color == "black":
            eval_before = -eval_before
        
        if eval_before >= 150:
            context["winning"] += 1
        elif eval_before <= -150:
            context["losing"] += 1
        else:
            context["equal"] += 1
    
    return context


def calculate_phase_instability(analysis: Dict) -> Dict[str, float]:
    """Calculate phase instability scores for a single game."""
    sf = analysis.get("stockfish_analysis", {})
    
    phase_scores = {"opening": 0, "middlegame": 0, "endgame": 0}
    phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
    
    for move in sf.get("move_evaluations", []):
        cp_loss = abs(move.get("cp_loss", 0))
        phase = move.get("phase", "middlegame")
        
        if phase in phase_scores:
            phase_counts[phase] += 1
            if cp_loss >= 50:
                phase_scores[phase] += min(1.0, cp_loss / 300)
    
    # Normalize
    for phase in phase_scores:
        if phase_counts[phase] > 0:
            phase_scores[phase] /= phase_counts[phase]
    
    return phase_scores


def compute_momentum(recent_games: List[Dict], previous_games: List[Dict], 
                     classify_func, severity_func, user_rating: int = 1200) -> Dict:
    """
    Compute Short-Term Momentum (5 vs 5).
    
    All deltas are threshold-filtered. Weak signals return "no change".
    """
    BASELINE_FLOOR = 0.05
    TSI_THRESHOLD = 5
    PATTERN_CHANGE_THRESHOLD = 0.20  # 20%
    CONTEXT_THRESHOLD = 15  # percentage points
    
    # Calculate per-game metrics
    recent_tsi = [calculate_game_tsi(g) for g in recent_games]
    previous_tsi = [calculate_game_tsi(g) for g in previous_games]
    
    recent_patterns = [calculate_game_cognitive_scores(g, classify_func, severity_func) for g in recent_games]
    previous_patterns = [calculate_game_cognitive_scores(g, classify_func, severity_func) for g in previous_games]
    
    recent_context = [calculate_blunder_context(g) for g in recent_games]
    previous_context = [calculate_blunder_context(g) for g in previous_games]
    
    recent_phase = [calculate_phase_instability(g) for g in recent_games]
    previous_phase = [calculate_phase_instability(g) for g in previous_games]
    
    # A. Stability Delta
    recent_avg_tsi = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 0
    previous_avg_tsi = sum(previous_tsi) / len(previous_tsi) if previous_tsi else 0
    tsi_delta = recent_avg_tsi - previous_avg_tsi
    
    if abs(tsi_delta) < TSI_THRESHOLD:
        stability_status = "stable"
        stability_text = "No meaningful stability shift detected."
    elif tsi_delta >= TSI_THRESHOLD:
        stability_status = "improving"
        stability_text = "Decision stability is trending upward."
    else:
        stability_status = "declining"
        stability_text = "Decision stability has weakened in recent games."
    
    # B. Pattern Shifts (only show if band changed AND relative change >= 20%)
    pattern_shifts = []
    categories = ["structural_misjudgment", "critical_moment_drift", "missed_forcing_move", 
                  "random_critical_move", "advantage_mismanagement"]
    
    for cat in categories:
        recent_avg = sum(p.get(cat, 0) for p in recent_patterns) / len(recent_patterns) if recent_patterns else 0
        previous_avg = sum(p.get(cat, 0) for p in previous_patterns) / len(previous_patterns) if previous_patterns else 0
        
        relative_change = (recent_avg - previous_avg) / max(previous_avg, BASELINE_FLOOR)
        
        recent_band = get_band(recent_avg)
        previous_band = get_band(previous_avg)
        
        # Only show if significant change AND band shift
        if abs(relative_change) >= PATTERN_CHANGE_THRESHOLD and recent_band != previous_band:
            if recent_band.value < previous_band.value:  # Band reduced = improvement
                status = "improving"
            else:
                status = "worsening"
            
            pattern_shifts.append({
                "category": cat,
                "previous_band": previous_band.value,
                "recent_band": recent_band.value,
                "status": status
            })
    
    # C. Blunder Context Shift
    total_recent_blunders = sum(c["total"] for c in recent_context)
    total_previous_blunders = sum(c["total"] for c in previous_context)
    
    context_shift = None
    
    # Safety: need minimum blunders
    if total_recent_blunders >= 3 and total_previous_blunders >= 3:
        recent_winning_rate = sum(c["winning"] for c in recent_context) / total_recent_blunders * 100
        previous_winning_rate = sum(c["winning"] for c in previous_context) / total_previous_blunders * 100
        
        context_delta = recent_winning_rate - previous_winning_rate
        
        if abs(context_delta) >= CONTEXT_THRESHOLD:
            context_shift = {
                "previous_rate": round(previous_winning_rate),
                "recent_rate": round(recent_winning_rate),
                "delta": round(context_delta),
                "status": "worsening" if context_delta > 0 else "improving"
            }
    
    # D. Phase Instability Shift
    def get_primary_phase(phase_list):
        avg = {"opening": 0, "middlegame": 0, "endgame": 0}
        for p in phase_list:
            for phase in avg:
                avg[phase] += p.get(phase, 0)
        for phase in avg:
            avg[phase] /= len(phase_list) if phase_list else 1
        return max(avg, key=avg.get).capitalize() if sum(avg.values()) > 0 else "Middlegame"
    
    recent_primary_phase = get_primary_phase(recent_phase)
    previous_primary_phase = get_primary_phase(previous_phase)
    
    phase_changed = recent_primary_phase != previous_primary_phase
    
    return {
        "valid": True,
        "stability": {
            "recent_avg": round(recent_avg_tsi),
            "previous_avg": round(previous_avg_tsi),
            "delta": round(tsi_delta),
            "status": stability_status,
            "text": stability_text
        },
        "pattern_shifts": pattern_shifts,
        "no_pattern_shifts": len(pattern_shifts) == 0,
        "context_shift": context_shift,
        "context_unchanged": context_shift is None,
        "phase": {
            "changed": phase_changed,
            "previous": previous_primary_phase,
            "recent": recent_primary_phase
        }
    }


def compute_growth_arc(all_games: List[Dict], classify_func, severity_func, 
                       user_rating: int = 1200) -> Optional[Dict]:
    """
    Compute Long-Term Growth Arc (Early vs Recent).
    
    Window sizing:
    - If total <= 40: early = first 10, recent = last 10
    - If total > 40: early = first 20%, recent = last 20% (cap at 20)
    """
    total_games = len(all_games)
    
    if total_games < 20:
        return None  # Not enough for growth arc
    
    # Window definition
    if total_games <= 40:
        early_size = min(10, total_games // 2)
        recent_size = min(10, total_games // 2)
    else:
        early_size = min(20, int(total_games * 0.2))
        recent_size = min(20, int(total_games * 0.2))
    
    # Games are sorted newest-first, so:
    recent_window = all_games[:recent_size]
    early_window = all_games[-early_size:]
    
    GROWTH_THRESHOLD = 7  # Higher bar for long-term
    
    # A. Stability Growth
    recent_tsi = [calculate_game_tsi(g) for g in recent_window]
    early_tsi = [calculate_game_tsi(g) for g in early_window]
    
    recent_avg = sum(recent_tsi) / len(recent_tsi) if recent_tsi else 0
    early_avg = sum(early_tsi) / len(early_tsi) if early_tsi else 0
    growth_delta = recent_avg - early_avg
    
    if abs(growth_delta) < GROWTH_THRESHOLD:
        stability_growth = {"status": "stable", "text": "Long-term stability has remained consistent."}
    elif growth_delta >= GROWTH_THRESHOLD:
        stability_growth = {"status": "growth", "text": "Sustained improvement in decision stability over time."}
    else:
        stability_growth = {"status": "regression", "text": "Decision stability has declined compared to earlier games."}
    
    # B. Driver Evolution (dominant pattern in early vs recent)
    early_patterns = [calculate_game_cognitive_scores(g, classify_func, severity_func) for g in early_window]
    recent_patterns = [calculate_game_cognitive_scores(g, classify_func, severity_func) for g in recent_window]
    
    categories = ["structural_misjudgment", "critical_moment_drift", "missed_forcing_move", 
                  "random_critical_move", "advantage_mismanagement"]
    
    # Find dominant driver in early window
    early_avgs = {}
    for cat in categories:
        early_avgs[cat] = sum(p.get(cat, 0) for p in early_patterns) / len(early_patterns) if early_patterns else 0
    
    dominant_driver = max(early_avgs, key=early_avgs.get) if early_avgs else None
    
    driver_evolution = None
    if dominant_driver and early_avgs[dominant_driver] > 0.05:
        recent_avg_driver = sum(p.get(dominant_driver, 0) for p in recent_patterns) / len(recent_patterns) if recent_patterns else 0
        
        early_band = get_band(early_avgs[dominant_driver])
        recent_band = get_band(recent_avg_driver)
        
        if recent_band.value < early_band.value:
            status = "growth"
            text = f"Your primary weakness has reduced over time."
        elif recent_band.value > early_band.value:
            status = "regression"
            text = f"Your primary weakness has intensified."
        else:
            status = "persistent"
            text = f"Your primary weakness remains consistent."
        
        driver_evolution = {
            "driver": dominant_driver,
            "early_band": early_band.value,
            "recent_band": recent_band.value,
            "status": status,
            "text": text
        }
    
    # C. Peer Comparison
    cohort = get_rating_cohort(user_rating)
    cohort_avg = cohort["avg_tsi"]
    peer_delta = recent_avg - cohort_avg
    
    if peer_delta >= 10:
        peer_status = "above"
        peer_text = f"Above peer stability for {cohort['label']} rating."
    elif peer_delta <= -10:
        peer_status = "below"
        peer_text = f"Below peer stability for {cohort['label']} rating."
    else:
        peer_status = "average"
        peer_text = f"Stability is typical for {cohort['label']} rating."
    
    peer_comparison = {
        "status": peer_status,
        "text": peer_text,
        "cohort_label": cohort["label"]
    }
    
    # D. Phase Evolution
    early_phase_list = [calculate_phase_instability(g) for g in early_window]
    recent_phase_list = [calculate_phase_instability(g) for g in recent_window]
    
    def get_primary_phase(phase_list):
        avg = {"opening": 0, "middlegame": 0, "endgame": 0}
        for p in phase_list:
            for phase in avg:
                avg[phase] += p.get(phase, 0)
        for phase in avg:
            avg[phase] /= len(phase_list) if phase_list else 1
        return max(avg, key=avg.get).capitalize() if sum(avg.values()) > 0 else "Middlegame"
    
    early_phase = get_primary_phase(early_phase_list)
    recent_phase = get_primary_phase(recent_phase_list)
    
    phase_evolution = {
        "changed": early_phase != recent_phase,
        "early": early_phase,
        "recent": recent_phase
    }
    
    return {
        "valid": True,
        "window_size": {"early": early_size, "recent": recent_size},
        "stability_growth": stability_growth,
        "driver_evolution": driver_evolution,
        "peer_comparison": peer_comparison,
        "phase_evolution": phase_evolution
    }


def generate_cognitive_summary(momentum: Dict, growth_arc: Optional[Dict]) -> str:
    """
    Generate integrative summary that reconciles all signals.
    
    Hard rule: Every line must map to a measured delta.
    """
    signals = []
    
    # Momentum stability
    if momentum["stability"]["status"] == "improving":
        signals.append("improving_stability")
    elif momentum["stability"]["status"] == "declining":
        signals.append("declining_stability")
    
    # Context shift
    if momentum.get("context_shift"):
        if momentum["context_shift"]["status"] == "worsening":
            signals.append("weakening_discipline")
        else:
            signals.append("strengthening_discipline")
    
    # Pattern shifts
    for shift in momentum.get("pattern_shifts", []):
        if shift["status"] == "improving":
            signals.append("pattern_improving")
        elif shift["status"] == "worsening":
            signals.append("pattern_worsening")
    
    # Build summary
    if "improving_stability" in signals and "weakening_discipline" in signals:
        return "Decision stability is improving, but discipline when ahead has weakened."
    elif "improving_stability" in signals:
        return "Decision stability is trending upward."
    elif "declining_stability" in signals and "strengthening_discipline" in signals:
        return "Overall stability has declined, though advantage discipline shows improvement."
    elif "declining_stability" in signals:
        return "Decision stability has weakened in recent games."
    elif "weakening_discipline" in signals:
        return "Stability is steady, but errors increase when ahead."
    elif "pattern_worsening" in signals:
        return "No major shift, but some patterns are emerging."
    elif "pattern_improving" in signals:
        return "Cognitive patterns are becoming more controlled."
    else:
        return "No significant cognitive shift detected."
