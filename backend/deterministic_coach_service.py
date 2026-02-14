"""
Deterministic Adaptive Coach Service - The Core GM-Style Coaching Engine

This is the GOLD FEATURE of ChessGuru.ai - A true adaptive coaching system
that feels like having a GM personal coach.

Core Principles:
1. DETERMINISTIC: All plan generation is rule-based, no LLM for correctness
2. ADAPTIVE: Intensity adjusts based on consecutive failures/successes
3. PERSONALIZED: Plans computed from rating band, patterns, fundamentals, history
4. EVIDENCE-BACKED: Every audit item links to specific moves
5. GM TONE: Concise, direct, max 4 bullets per domain

Rating Bands (Granular):
- 600-1000: Absolute beginner, focus on not hanging pieces
- 1000-1400: Beginner, basic tactics and simple plans
- 1400-1800: Intermediate, positional understanding emerging
- 1800+: Advanced, nuanced strategic advice

Training Intensity (5 Levels):
- 1: Light - Outcome focus, gentle reminders
- 2: Normal - Behavior focus, clear rules
- 3: Focused - Simplified rules, higher stakes language
- 4: Intense - Micro-habits, single rule per domain
- 5: Critical - Emergency mode, ONE rule for entire game

The Adaptive Loop:
1. Generate Plan → User Plays → Audit Game
2. For each domain: executed/partial/missed
3. Adjust intensity: miss = +1, execute = -1 (with bounds)
4. Generate next plan with adjusted intensity
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import uuid
import re

logger = logging.getLogger(__name__)


# =============================================================================
# RATING BANDS - Granular System
# =============================================================================

RATING_BANDS = {
    "beginner_low": {"min": 0, "max": 999, "label": "600-1000", "strictness": 0.5},
    "beginner_high": {"min": 1000, "max": 1399, "label": "1000-1400", "strictness": 0.7},
    "intermediate": {"min": 1400, "max": 1799, "label": "1400-1800", "strictness": 0.85},
    "advanced": {"min": 1800, "max": 9999, "label": "1800+", "strictness": 1.0},
}


def get_rating_band(rating: int) -> Dict:
    """Get the rating band for a given rating."""
    for band_name, band_data in RATING_BANDS.items():
        if band_data["min"] <= rating <= band_data["max"]:
            return {"name": band_name, **band_data}
    return {"name": "beginner_low", **RATING_BANDS["beginner_low"]}


def get_band_specific_thresholds(band_name: str) -> Dict:
    """
    Get evaluation thresholds adjusted for rating band.
    
    Lower-rated players get more lenient thresholds since
    their games are more volatile.
    """
    thresholds = {
        "beginner_low": {
            "blunder_cp": 300,  # Only count as blunder if > 3 pawns lost
            "mistake_cp": 150,  # > 1.5 pawns
            "acceptable_early_drop": 100,  # Allow some opening sloppiness
            "winning_threshold": 200,  # +2 is "winning"
            "losing_threshold": -200,
            "advantage_collapse_threshold": 200,  # Dropping 2 pawns when winning
        },
        "beginner_high": {
            "blunder_cp": 200,
            "mistake_cp": 100,
            "acceptable_early_drop": 75,
            "winning_threshold": 150,
            "losing_threshold": -150,
            "advantage_collapse_threshold": 150,
        },
        "intermediate": {
            "blunder_cp": 150,
            "mistake_cp": 75,
            "acceptable_early_drop": 50,
            "winning_threshold": 100,
            "losing_threshold": -100,
            "advantage_collapse_threshold": 100,
        },
        "advanced": {
            "blunder_cp": 100,
            "mistake_cp": 50,
            "acceptable_early_drop": 30,
            "winning_threshold": 75,
            "losing_threshold": -75,
            "advantage_collapse_threshold": 75,
        },
    }
    return thresholds.get(band_name, thresholds["beginner_low"])


# =============================================================================
# TRAINING INTENSITY - 5 Level System
# =============================================================================

INTENSITY_LEVELS = {
    1: {
        "name": "Light",
        "description": "Gentle reminders, outcome focus",
        "rules_per_domain": 4,
        "tone": "encouraging",
    },
    2: {
        "name": "Normal", 
        "description": "Clear behavior rules",
        "rules_per_domain": 3,
        "tone": "direct",
    },
    3: {
        "name": "Focused",
        "description": "Simplified rules, higher urgency",
        "rules_per_domain": 2,
        "tone": "firm",
    },
    4: {
        "name": "Intense",
        "description": "Micro-habits, single focus",
        "rules_per_domain": 1,
        "tone": "strict",
    },
    5: {
        "name": "Critical",
        "description": "Emergency mode - ONE rule for game",
        "rules_per_domain": 1,
        "tone": "urgent",
    },
}


def calculate_intensity_from_history(domain_history: Dict) -> int:
    """
    Calculate intensity level based on consecutive misses/executions.
    
    Rules:
    - Start at level 2 (Normal)
    - Each consecutive miss: +1 intensity (max 5)
    - Each consecutive execution: -1 intensity (min 1)
    - 4+ consecutive misses: Force level 5
    """
    consecutive_misses = domain_history.get("consecutive_misses", 0)
    consecutive_executions = domain_history.get("consecutive_executions", 0)
    
    # Start at level 2
    base = 2
    
    if consecutive_misses >= 4:
        return 5  # Force critical mode
    elif consecutive_misses >= 3:
        return 4
    elif consecutive_misses >= 2:
        return 3
    elif consecutive_misses >= 1:
        return min(base + 1, 5)
    elif consecutive_executions >= 3:
        return 1  # Back to light
    elif consecutive_executions >= 2:
        return max(base - 1, 1)
    
    return base


def get_intensity_rules(domain: str, intensity: int, rating_band: str) -> Dict:
    """
    Get rules for a domain at a specific intensity level.
    
    Returns:
    - goal: One-line objective
    - rules: List of rules (count based on intensity)
    - micro_habit: Single rule for intensity 4-5
    """
    
    # Domain-specific rule sets organized by intensity
    domain_rules = {
        "opening": {
            "goal_levels": {
                1: "Develop pieces and castle safely",
                2: "Stick to your main openings",
                3: "No opening experiments - play what you know",
                4: "ONE opening per color. Zero deviation.",
                5: "OPENING RULE: Play your system. Nothing else matters.",
            },
            "rules": [
                "Complete development before attacking",
                "Castle by move 10",
                "Control the center with pawns",
                "Don't move the same piece twice early",
                "Connect your rooks",
                "No early queen adventures",
            ],
            "micro_habit": "Before move 1: pick your opening. No changing.",
        },
        "middlegame": {
            "goal_levels": {
                1: "Keep improving your position",
                2: "When winning, simplify the position",
                3: "Ahead? Trade pieces. That's it.",
                4: "ONE RULE: Trade a piece when you're winning",
                5: "MIDDLEGAME RULE: If ahead, trade. If equal, improve.",
            },
            "rules": [
                "Trade pieces when ahead material",
                "Improve your worst-placed piece",
                "Don't rush attacks from equal positions",
                "Verify your pieces are safe before attacking",
                "Control open files with rooks",
                "When +1.5, stop and simplify",
            ],
            "micro_habit": "Ask yourself: Am I winning? If yes, trade something.",
        },
        "tactics": {
            "goal_levels": {
                1: "Stay alert for tactics",
                2: "Check threats before every move",
                3: "CCT every move: Checks, Captures, Threats",
                4: "Before moving: 'What did they just threaten?'",
                5: "TACTICS RULE: No hanging pieces. Check everything.",
            },
            "rules": [
                "Look for opponent's threats first",
                "Check all your pieces are defended",
                "CCT protocol: Checks, Captures, Threats",
                "Spend extra time on tense positions",
                "Look for double attacks and pins",
                "Never assume a piece is safe",
            ],
            "micro_habit": "Before EVERY move: are all my pieces safe?",
        },
        "endgame": {
            "goal_levels": {
                1: "Activate your king in endgames",
                2: "King to center when queens come off",
                3: "King moves to center immediately",
                4: "KING TO CENTER. First priority in every endgame.",
                5: "ENDGAME RULE: King walks to center. Now.",
            },
            "rules": [
                "Centralize king immediately",
                "Rooks belong behind passed pawns",
                "Create passed pawns",
                "Calculate pawn races before playing",
                "Don't trade all pawns when ahead",
                "Push passed pawns with king support",
            ],
            "micro_habit": "Queens off? King to center. Do it first.",
        },
        "time": {
            "goal_levels": {
                1: "Manage your time well",
                2: "Keep time buffer for endgame",
                3: "Don't drop below 1 minute",
                4: "Max 30 seconds per move",
                5: "TIME RULE: Move within 20 seconds. Always.",
            },
            "rules": [
                "Use half your time by move 20",
                "Don't think more than 2 minutes on one move",
                "Keep 1+ minute buffer for endgame",
                "When low on time, play safe moves",
                "Pre-move obvious recaptures",
                "Check clock after every 5 moves",
            ],
            "micro_habit": "Check clock after EVERY move.",
        },
    }
    
    domain_data = domain_rules.get(domain, domain_rules["tactics"])
    intensity_config = INTENSITY_LEVELS.get(intensity, INTENSITY_LEVELS[2])
    
    # Get goal for this intensity
    goal = domain_data["goal_levels"].get(intensity, domain_data["goal_levels"][2])
    
    # Get appropriate number of rules
    num_rules = intensity_config["rules_per_domain"]
    rules = domain_data["rules"][:num_rules]
    
    # At intensity 4-5, use micro-habit as the only rule
    if intensity >= 4:
        rules = [domain_data["micro_habit"]]
    
    return {
        "goal": goal,
        "rules": rules,
        "micro_habit": domain_data["micro_habit"],
        "intensity": intensity,
        "intensity_name": intensity_config["name"],
        "tone": intensity_config["tone"],
    }


# =============================================================================
# FUNDAMENTALS PROFILE - Computed from last 25 games
# =============================================================================

def calculate_fundamentals_from_games(
    analyses: List[Dict], 
    games: List[Dict],
    rating_band: str
) -> Dict:
    """
    Calculate fundamentals profile from the last 25 analyzed games.
    
    Returns scores 0-100 for each domain:
    - opening: Early stability (moves 1-10)
    - middlegame: Advantage handling (maintaining eval)
    - tactics: Blunder/mistake rate
    - endgame: Conversion rate when entering with advantage
    - time: Late-game performance (proxy for time management)
    """
    if not analyses or len(analyses) < 5:
        return {
            "opening": 50,
            "middlegame": 50,
            "tactics": 50,
            "endgame": 50,
            "time": 50,
            "sample_size": len(analyses) if analyses else 0,
            "has_enough_data": False,
        }
    
    # Use last 25 games
    recent_analyses = analyses[-25:]
    recent_games = games[-25:] if games else []
    n = len(recent_analyses)
    
    thresholds = get_band_specific_thresholds(rating_band)
    
    # === OPENING SCORE ===
    opening_scores = []
    for a in recent_analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
        
        if early_moves:
            max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
            avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
            
            # Score based on rating-adjusted thresholds
            if max_drop < thresholds["acceptable_early_drop"] and avg_cp < 30:
                opening_scores.append(90)
            elif max_drop < thresholds["mistake_cp"] and avg_cp < 50:
                opening_scores.append(70)
            elif max_drop < thresholds["blunder_cp"]:
                opening_scores.append(50)
            else:
                opening_scores.append(30)
    
    opening_score = sum(opening_scores) / len(opening_scores) if opening_scores else 50
    
    # === MIDDLEGAME SCORE (Advantage Stability) ===
    middlegame_scores = []
    for a in recent_analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        had_advantage = False
        collapsed = False
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            cp_loss = m.get("cp_loss", 0)
            
            if eval_before >= thresholds["winning_threshold"]:
                had_advantage = True
                if cp_loss >= thresholds["advantage_collapse_threshold"]:
                    collapsed = True
        
        if had_advantage:
            middlegame_scores.append(30 if collapsed else 90)
    
    middlegame_score = sum(middlegame_scores) / len(middlegame_scores) if middlegame_scores else 50
    
    # === TACTICS SCORE ===
    total_blunders = sum(a.get("blunders", 0) for a in recent_analyses)
    avg_blunders = total_blunders / n
    
    # Adjust expectations based on rating band
    if rating_band == "beginner_low":
        if avg_blunders < 1.5:
            tactics_score = 80
        elif avg_blunders < 2.5:
            tactics_score = 60
        elif avg_blunders < 4:
            tactics_score = 40
        else:
            tactics_score = 20
    elif rating_band == "beginner_high":
        if avg_blunders < 1:
            tactics_score = 85
        elif avg_blunders < 2:
            tactics_score = 65
        elif avg_blunders < 3:
            tactics_score = 45
        else:
            tactics_score = 25
    elif rating_band == "intermediate":
        if avg_blunders < 0.5:
            tactics_score = 90
        elif avg_blunders < 1:
            tactics_score = 70
        elif avg_blunders < 2:
            tactics_score = 50
        else:
            tactics_score = 30
    else:  # advanced
        if avg_blunders < 0.3:
            tactics_score = 95
        elif avg_blunders < 0.7:
            tactics_score = 75
        elif avg_blunders < 1.5:
            tactics_score = 55
        else:
            tactics_score = 35
    
    # === ENDGAME SCORE ===
    endgame_results = []
    for i, a in enumerate(recent_analyses):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Endgame = after move 60 (30 per side)
        endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
        
        if len(endgame_moves) >= 5:
            first_eg = endgame_moves[0]
            entering_eval = first_eg.get("eval_before", 0)
            
            if entering_eval >= thresholds["winning_threshold"]:
                # Had winning endgame, check result
                if i < len(recent_games):
                    game = recent_games[i]
                    result = game.get("result", "")
                    user_color = game.get("user_color", "white")
                    won = (user_color == "white" and result == "1-0") or \
                          (user_color == "black" and result == "0-1")
                    endgame_results.append(100 if won else 20)
    
    endgame_score = sum(endgame_results) / len(endgame_results) if endgame_results else 50
    
    # === TIME SCORE (late-game blunder proxy) ===
    late_blunder_rates = []
    for a in recent_analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        total_blunders = a.get("blunders", 0)
        
        late_blunders = sum(1 for m in moves 
                          if m.get("move_number", 0) > 50 
                          and m.get("evaluation") == "blunder")
        
        if total_blunders > 0:
            late_ratio = late_blunders / total_blunders
            late_blunder_rates.append(late_ratio)
    
    avg_late_ratio = sum(late_blunder_rates) / len(late_blunder_rates) if late_blunder_rates else 0.5
    time_score = max(20, min(90, 90 - (avg_late_ratio * 60)))
    
    return {
        "opening": round(opening_score),
        "middlegame": round(middlegame_score),
        "tactics": round(tactics_score),
        "endgame": round(endgame_score),
        "time": round(time_score),
        "sample_size": n,
        "has_enough_data": n >= 10,
        "avg_blunders_per_game": round(avg_blunders, 2),
    }


# =============================================================================
# PATTERN DETECTION - Identify Player's Weaknesses
# =============================================================================

def detect_weakness_patterns(
    analyses: List[Dict],
    games: List[Dict],
    rating_band: str
) -> Dict:
    """
    Detect specific weakness patterns from game history.
    
    Returns:
    - patterns: List of detected patterns with severity
    - primary_weakness: The most impactful weakness
    - secondary_weakness: Second most impactful
    - clusters: Grouped patterns (e.g., "piece safety" cluster)
    """
    if not analyses or len(analyses) < 5:
        return {
            "patterns": [],
            "primary_weakness": None,
            "secondary_weakness": None,
            "clusters": [],
        }
    
    recent = analyses[-25:]
    n = len(recent)
    thresholds = get_band_specific_thresholds(rating_band)
    
    patterns = []
    
    # === ADVANTAGE COLLAPSE ===
    collapse_count = 0
    collapse_evidence = []
    
    for i, a in enumerate(recent):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            cp_loss = m.get("cp_loss", 0)
            
            if eval_before >= thresholds["winning_threshold"]:
                if cp_loss >= thresholds["advantage_collapse_threshold"]:
                    collapse_count += 1
                    collapse_evidence.append({
                        "game_index": i,
                        "game_id": a.get("game_id"),
                        "move_number": m.get("move_number"),
                        "cp_loss": cp_loss,
                    })
                    break
    
    collapse_rate = collapse_count / n
    if collapse_rate >= 0.3:
        patterns.append({
            "pattern": "advantage_collapse",
            "label": "Loses Focus When Winning",
            "severity": "critical" if collapse_rate >= 0.5 else "high",
            "frequency": f"{collapse_count}/{n} games ({round(collapse_rate*100)}%)",
            "rate": collapse_rate,
            "evidence": collapse_evidence[:5],  # Top 5 examples
            "impact": "rating_killer",  # This is a major rating drain
        })
    
    # === PIECE SAFETY (Hanging pieces) ===
    hung_piece_count = 0
    hung_evidence = []
    
    for i, a in enumerate(recent):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            if m.get("evaluation") == "blunder" and m.get("cp_loss", 0) >= 300:
                hung_piece_count += 1
                hung_evidence.append({
                    "game_index": i,
                    "game_id": a.get("game_id"),
                    "move_number": m.get("move_number"),
                    "cp_loss": m.get("cp_loss"),
                    "move": m.get("move"),
                })
                break
    
    hung_rate = hung_piece_count / n
    if hung_rate >= 0.25:
        patterns.append({
            "pattern": "piece_safety",
            "label": "Hangs Pieces",
            "severity": "critical" if hung_rate >= 0.4 else "high",
            "frequency": f"{hung_piece_count}/{n} games ({round(hung_rate*100)}%)",
            "rate": hung_rate,
            "evidence": hung_evidence[:5],
            "impact": "rating_killer",
        })
    
    # === TACTICAL BLINDNESS (High blunder rate) ===
    total_blunders = sum(a.get("blunders", 0) for a in recent)
    avg_blunders = total_blunders / n
    
    # Rating-adjusted thresholds
    blunder_threshold = {
        "beginner_low": 3,
        "beginner_high": 2,
        "intermediate": 1.5,
        "advanced": 1,
    }.get(rating_band, 2)
    
    if avg_blunders >= blunder_threshold:
        patterns.append({
            "pattern": "tactical_blindness",
            "label": "Misses Tactics",
            "severity": "high" if avg_blunders >= blunder_threshold * 1.5 else "medium",
            "frequency": f"{round(avg_blunders, 1)} blunders/game",
            "rate": avg_blunders / blunder_threshold,
            "evidence": [],
            "impact": "skill_gap",
        })
    
    # === TIME TROUBLE ===
    time_trouble_count = 0
    time_evidence = []
    
    for i, a in enumerate(recent):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        late_blunders = [m for m in moves 
                       if m.get("move_number", 0) > 50 
                       and m.get("evaluation") == "blunder"]
        
        if late_blunders:
            time_trouble_count += 1
            time_evidence.append({
                "game_index": i,
                "game_id": a.get("game_id"),
                "move_number": late_blunders[0].get("move_number"),
            })
    
    time_rate = time_trouble_count / n
    if time_rate >= 0.3:
        patterns.append({
            "pattern": "time_trouble",
            "label": "Time Pressure Blunders",
            "severity": "high" if time_rate >= 0.5 else "medium",
            "frequency": f"{time_trouble_count}/{n} games ({round(time_rate*100)}%)",
            "rate": time_rate,
            "evidence": time_evidence[:5],
            "impact": "controllable",
        })
    
    # Sort patterns by impact and rate
    def pattern_score(p):
        impact_scores = {"rating_killer": 3, "skill_gap": 2, "controllable": 1}
        return impact_scores.get(p["impact"], 1) * p["rate"]
    
    patterns.sort(key=pattern_score, reverse=True)
    
    # Determine primary and secondary
    primary = patterns[0]["pattern"] if patterns else None
    secondary = patterns[1]["pattern"] if len(patterns) > 1 else None
    
    # Create clusters
    clusters = []
    if any(p["pattern"] in ["piece_safety", "tactical_blindness"] for p in patterns):
        clusters.append({
            "name": "piece_safety",
            "label": "Piece Safety Issues",
            "patterns": ["piece_safety", "tactical_blindness"],
        })
    if any(p["pattern"] == "advantage_collapse" for p in patterns):
        clusters.append({
            "name": "advantage_handling",
            "label": "Converting Advantages",
            "patterns": ["advantage_collapse"],
        })
    
    return {
        "patterns": patterns,
        "primary_weakness": primary,
        "secondary_weakness": secondary,
        "clusters": clusters,
    }


# =============================================================================
# DOMAIN HISTORY TRACKER - Tracks audit results per domain
# =============================================================================

def build_domain_history(plan_history: List[Dict], max_lookback: int = 10) -> Dict:
    """
    Build history of domain execution from past audits.
    
    Returns dict per domain with:
    - consecutive_misses
    - consecutive_executions
    - last_status
    - total_misses (in lookback window)
    - total_executions
    """
    history = {
        "opening": {"consecutive_misses": 0, "consecutive_executions": 0, 
                   "last_status": None, "total_misses": 0, "total_executions": 0},
        "middlegame": {"consecutive_misses": 0, "consecutive_executions": 0,
                      "last_status": None, "total_misses": 0, "total_executions": 0},
        "tactics": {"consecutive_misses": 0, "consecutive_executions": 0,
                   "last_status": None, "total_misses": 0, "total_executions": 0},
        "endgame": {"consecutive_misses": 0, "consecutive_executions": 0,
                   "last_status": None, "total_misses": 0, "total_executions": 0},
        "time": {"consecutive_misses": 0, "consecutive_executions": 0,
                "last_status": None, "total_misses": 0, "total_executions": 0},
    }
    
    if not plan_history:
        return history
    
    # Process only audited plans
    audited_plans = [p for p in plan_history if p.get("is_audited")][-max_lookback:]
    
    # Process from oldest to newest
    for plan in audited_plans:
        for card in plan.get("cards", []):
            domain = card.get("domain")
            if domain not in history:
                continue
            
            status = card.get("audit", {}).get("status")
            if not status or status == "n/a":
                continue
            
            if status == "missed":
                history[domain]["consecutive_misses"] += 1
                history[domain]["consecutive_executions"] = 0
                history[domain]["total_misses"] += 1
            elif status == "executed":
                history[domain]["consecutive_executions"] += 1
                history[domain]["consecutive_misses"] = 0
                history[domain]["total_executions"] += 1
            else:  # partial
                # Partial doesn't break execution streak but doesn't add
                history[domain]["consecutive_misses"] = 0
            
            history[domain]["last_status"] = status
    
    return history


# =============================================================================
# OPENING RECOMMENDATION ENGINE
# =============================================================================

def calculate_opening_recommendations(
    analyses: List[Dict],
    games: List[Dict],
    rating_band: str
) -> Dict:
    """
    Calculate opening recommendations based on stability scores.
    
    Stability = Inverse of early position volatility
    NOT win rate (correlation is weak at lower levels)
    """
    if not games or len(games) < 8:
        return {
            "as_white": {"recommended": None, "avoid": None, "all": []},
            "as_black": {"recommended": None, "avoid": None, "all": []},
            "sample_size": len(games) if games else 0,
        }
    
    # Build analysis lookup by game_id
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    openings_white = {}
    openings_black = {}
    
    thresholds = get_band_specific_thresholds(rating_band)
    
    for game in games[-30:]:
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
        
        # Calculate stability score
        max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
        avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
        early_blunders = sum(1 for m in early_moves if m.get("evaluation") == "blunder")
        
        stability = 100
        stability -= min(30, max_drop / 10)
        stability -= min(20, avg_cp)
        stability -= early_blunders * 20
        stability = max(0, stability)
        
        # Store
        target = openings_white if user_color == "white" else openings_black
        if opening not in target:
            target[opening] = {"scores": [], "wins": 0, "total": 0}
        
        target[opening]["scores"].append(stability)
        target[opening]["total"] += 1
        
        result = game.get("result", "")
        won = (user_color == "white" and result == "1-0") or \
              (user_color == "black" and result == "0-1")
        if won:
            target[opening]["wins"] += 1
    
    def process_color(openings_dict) -> Dict:
        processed = []
        for name, data in openings_dict.items():
            if data["total"] >= 2:
                avg_stability = sum(data["scores"]) / len(data["scores"])
                win_rate = (data["wins"] / data["total"]) * 100
                processed.append({
                    "name": name,
                    "games": data["total"],
                    "stability": round(avg_stability),
                    "win_rate": round(win_rate),
                })
        
        processed.sort(key=lambda x: x["stability"], reverse=True)
        
        recommended = processed[0] if processed else None
        avoid = None
        if len(processed) >= 2:
            worst = processed[-1]
            if worst["games"] >= 3 and worst["stability"] < 55:
                avoid = worst
        
        return {
            "recommended": recommended,
            "avoid": avoid,
            "all": processed[:5],
        }
    
    return {
        "as_white": process_color(openings_white),
        "as_black": process_color(openings_black),
        "sample_size": len(games),
    }


def _extract_opening_family(game: Dict) -> str:
    """Extract opening family name from game."""
    pgn = game.get("pgn", "")
    
    # Try ECOUrl first
    eco_url_match = re.search(r'\[ECOUrl "[^"]+/([^/"]+)"\]', pgn)
    if eco_url_match:
        raw = eco_url_match.group(1)
        parts = raw.split("-")
        main_parts = []
        for part in parts[:3]:
            if part.lower() in ["variation", "attack", "defense", "defence", "game", "opening", "gambit"]:
                main_parts.append(part.title())
                break
            main_parts.append(part.title())
        if main_parts:
            return " ".join(main_parts)
    
    # Try Opening field
    opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
    if opening_match:
        return " ".join(opening_match.group(1).split()[:2])
    
    # Try ECO code
    eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
    if eco_match:
        eco = eco_match.group(1)
        eco_families = {
            "A": "Flank Opening", "B": "Sicilian/Semi-Open",
            "C": "Open Game", "D": "Queen's Pawn",
            "E": "Indian Defense",
        }
        return eco_families.get(eco[0], "Opening")
    
    return "Unknown Opening"


# =============================================================================
# PLAN GENERATOR - THE CORE DETERMINISTIC ENGINE
# =============================================================================

def generate_deterministic_plan(
    user_id: str,
    rating: int,
    fundamentals: Dict,
    weakness_patterns: Dict,
    opening_recommendations: Dict,
    domain_history: Dict,
    last_audit: Optional[Dict] = None,
    critical_insights: Optional[List[Dict]] = None
) -> Dict:
    """
    Generate a personalized coaching plan using deterministic logic.
    
    This is the heart of the Deterministic Adaptive Coach.
    
    Inputs:
    - rating: User's rating (determines thresholds and language)
    - fundamentals: Scores per domain from last 25 games
    - weakness_patterns: Detected patterns with evidence
    - opening_recommendations: What to play/avoid
    - domain_history: Consecutive misses/executions per domain
    - last_audit: Most recent plan audit (for persistence)
    - critical_insights: Tactical patterns from last game
    
    Output:
    - PlanCard with domain-specific goals, rules, criteria
    - Intensity per domain based on history
    - Focus items from last game
    """
    
    rating_band = get_rating_band(rating)
    band_name = rating_band["name"]
    
    # Create plan structure
    plan = {
        "plan_id": str(uuid.uuid4()),
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rating": rating,
        "rating_band": band_name,
        "rating_label": rating_band["label"],
        "is_active": True,
        "is_audited": False,
        "cards": [],
        "focus_items": [],
        "situational_rules": [],
    }
    
    # Determine primary and secondary domains to focus on
    primary_weakness = weakness_patterns.get("primary_weakness")
    secondary_weakness = weakness_patterns.get("secondary_weakness")
    
    weakness_to_domain = {
        "advantage_collapse": "middlegame",
        "piece_safety": "tactics",
        "tactical_blindness": "tactics",
        "time_trouble": "time",
    }
    
    # Map weaknesses to domains
    primary_domain = weakness_to_domain.get(primary_weakness, None)
    secondary_domain = weakness_to_domain.get(secondary_weakness, None)
    
    # If no clear weakness, use lowest fundamental
    if not primary_domain:
        fund_scores = [(k, v) for k, v in fundamentals.items() 
                      if k not in ["sample_size", "has_enough_data", "avg_blunders_per_game"]]
        fund_scores.sort(key=lambda x: x[1])
        if fund_scores:
            primary_domain = fund_scores[0][0]
    
    # Set domain priorities
    domain_priorities = {
        "opening": "baseline",
        "middlegame": "baseline",
        "tactics": "baseline",
        "endgame": "baseline",
        "time": "baseline",
    }
    
    if primary_domain:
        domain_priorities[primary_domain] = "primary"
    if secondary_domain and secondary_domain != primary_domain:
        domain_priorities[secondary_domain] = "secondary"
    
    # Calculate global training intensity
    # Based on primary weakness consecutive misses
    primary_history = domain_history.get(primary_domain or "tactics", {})
    global_intensity = calculate_intensity_from_history(primary_history)
    
    # Create training block
    training_block = _create_training_block(
        primary_weakness, 
        fundamentals, 
        global_intensity
    )
    plan["training_block"] = training_block
    
    # Generate cards for each domain
    for domain in ["opening", "middlegame", "tactics", "endgame", "time"]:
        priority = domain_priorities[domain]
        domain_hist = domain_history.get(domain, {})
        
        # Calculate domain-specific intensity
        domain_intensity = calculate_intensity_from_history(domain_hist)
        
        # If this is primary domain, use higher of global or domain intensity
        if domain == primary_domain:
            domain_intensity = max(global_intensity, domain_intensity)
        
        # Generate the card
        card = _generate_domain_card(
            domain=domain,
            priority=priority,
            intensity=domain_intensity,
            rating_band=band_name,
            fundamentals=fundamentals,
            weakness_patterns=weakness_patterns,
            opening_recs=opening_recommendations if domain == "opening" else None,
            domain_history=domain_hist,
        )
        
        plan["cards"].append(card)
    
    # Add focus items from critical insights
    if critical_insights:
        plan["focus_items"] = _create_focus_items(critical_insights)
    
    # Add situational rules based on rating
    plan["situational_rules"] = _get_situational_rules(rating)
    
    return plan


def _create_training_block(
    primary_weakness: Optional[str],
    fundamentals: Dict,
    intensity: int
) -> Dict:
    """Create training block metadata."""
    
    blocks = {
        "advantage_collapse": {
            "name": "Finish Strong",
            "focus": "Converting winning positions into wins",
        },
        "piece_safety": {
            "name": "Piece Safety",
            "focus": "No more hanging pieces",
        },
        "tactical_blindness": {
            "name": "Tactical Vision",
            "focus": "Seeing the board clearly",
        },
        "time_trouble": {
            "name": "Clock Master",
            "focus": "Managing time under pressure",
        },
    }
    
    if primary_weakness and primary_weakness in blocks:
        block = blocks[primary_weakness]
    else:
        # Default to Foundation
        block = {"name": "Foundation", "focus": "Building solid fundamentals"}
    
    intensity_info = INTENSITY_LEVELS.get(intensity, INTENSITY_LEVELS[2])
    
    return {
        "name": block["name"],
        "focus": block["focus"],
        "intensity": intensity,
        "intensity_name": intensity_info["name"],
        "intensity_description": intensity_info["description"],
    }


def _generate_domain_card(
    domain: str,
    priority: str,
    intensity: int,
    rating_band: str,
    fundamentals: Dict,
    weakness_patterns: Dict,
    opening_recs: Optional[Dict],
    domain_history: Dict,
) -> Dict:
    """Generate a single domain card."""
    
    # Get intensity-appropriate rules
    rules_data = get_intensity_rules(domain, intensity, rating_band)
    
    # Customize goal based on specific weakness
    goal = rules_data["goal"]
    rules = rules_data["rules"]
    
    # For opening, add specific recommendations
    if domain == "opening" and opening_recs:
        white_rec = opening_recs.get("as_white", {}).get("recommended")
        black_rec = opening_recs.get("as_black", {}).get("recommended")
        
        if white_rec and intensity <= 3:
            rules.insert(0, f"As White: {white_rec['name']} (your most stable)")
        if black_rec and intensity <= 3:
            rules.insert(1 if white_rec else 0, f"As Black: {black_rec['name']} (your most stable)")
    
    # Success criteria based on domain and rating band
    criteria = _get_success_criteria(domain, rating_band, priority)
    
    # Build escalation info
    is_escalated = domain_history.get("consecutive_misses", 0) >= 2
    
    card = {
        "domain": domain,
        "priority": priority,
        "goal": goal,
        "rules": rules[:INTENSITY_LEVELS[intensity]["rules_per_domain"]],
        "success_criteria": criteria,
        "intensity": intensity,
        "intensity_name": INTENSITY_LEVELS[intensity]["name"],
        "escalation": {
            "is_escalated": is_escalated,
            "consecutive_misses": domain_history.get("consecutive_misses", 0),
            "consecutive_executions": domain_history.get("consecutive_executions", 0),
        },
        "audit": {
            "status": None,  # filled after audit
            "data_points": [],
            "evidence": [],
            "coach_note": None,
        },
    }
    
    return card


def _get_success_criteria(domain: str, rating_band: str, priority: str) -> List[Dict]:
    """Get success criteria for a domain."""
    
    thresholds = get_band_specific_thresholds(rating_band)
    
    criteria_map = {
        "opening": [
            {
                "metric": "max_early_cp_loss",
                "op": "<=",
                "value": thresholds["acceptable_early_drop"],
                "window": "moves 1-10",
                "label": "No big early drops",
            },
        ],
        "middlegame": [
            {
                "metric": "advantage_maintained",
                "op": "==",
                "value": True,
                "window": "when eval >= +1.5",
                "label": "Hold advantages",
            },
        ],
        "tactics": [
            {
                "metric": "blunders",
                "op": "<=",
                "value": 1 if rating_band in ["beginner_low", "beginner_high"] else 0,
                "window": "full game",
                "label": "Minimal blunders",
            },
        ],
        "endgame": [
            {
                "metric": "endgame_converted",
                "op": "==",
                "value": True,
                "window": "if entered winning",
                "label": "Convert advantages",
            },
        ],
        "time": [
            {
                "metric": "time_trouble_blunders",
                "op": "==",
                "value": 0,
                "window": "moves 40+",
                "label": "No late blunders",
            },
        ],
    }
    
    return criteria_map.get(domain, [])


def _create_focus_items(insights: List[Dict]) -> List[Dict]:
    """Create focus items from critical insights."""
    
    focus_items = []
    seen = set()
    
    pattern_icons = {
        "piece_trap": "🪤",
        "fork": "⚔️",
        "mobility_restriction": "🔒",
        "multi_threat": "💥",
        "attack_valuable": "🎯",
        "pin": "📌",
    }
    
    for insight in insights[:3]:
        pattern = insight.get("type", "")
        if pattern in seen:
            continue
        seen.add(pattern)
        
        focus_items.append({
            "id": f"focus_{pattern}_{insight.get('move_number', 0)}",
            "pattern": pattern,
            "pattern_name": insight.get("pattern_name", pattern),
            "move_number": insight.get("move_number"),
            "cp_lost": insight.get("cp_loss", 0),
            "goal": insight.get("actionable_goal", ""),
            "key_insight": insight.get("key_insight", ""),
            "icon": pattern_icons.get(pattern, "💡"),
        })
    
    return focus_items


def _get_situational_rules(rating: int) -> List[Dict]:
    """Get situational rules appropriate for rating."""
    
    rules = [
        {
            "id": "when_winning",
            "condition": "When ahead material",
            "rules": ["Trade pieces", "Don't get fancy", "Simplify"],
            "applies_to_rating": [0, 9999],
        },
        {
            "id": "when_losing",
            "condition": "When down material",
            "rules": ["Create complications", "Avoid trades", "Fight for activity"],
            "applies_to_rating": [0, 9999],
        },
        {
            "id": "time_pressure",
            "condition": "Under 2 minutes",
            "rules": ["Play safe", "No long thinks", "Trust instincts"],
            "applies_to_rating": [0, 9999],
        },
    ]
    
    return [r for r in rules 
            if r["applies_to_rating"][0] <= rating <= r["applies_to_rating"][1]]


# =============================================================================
# AUDIT ENGINE - Evaluate Game Against Plan
# =============================================================================

def audit_game_against_plan(
    plan: Dict,
    game: Dict,
    analysis: Dict,
) -> Dict:
    """
    Audit a game against the given plan.
    
    For each domain:
    1. Evaluate success criteria
    2. Determine status: executed | partial | missed | n/a
    3. Collect evidence (specific moves with eval changes)
    4. Generate deterministic coach note
    
    Returns the plan with audit fields filled in.
    """
    
    rating_band = plan.get("rating_band", "beginner_low")
    thresholds = get_band_specific_thresholds(rating_band)
    
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white")
    
    # Determine game result
    result = game.get("result", "*")
    if user_color == "white":
        game_result = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
    else:
        game_result = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
    
    # Get opponent name
    pgn = game.get("pgn", "")
    if user_color == "white":
        match = re.search(r'\[Black "([^"]+)"\]', pgn)
        opponent = match.group(1) if match else game.get("black_player", "Opponent")
    else:
        match = re.search(r'\[White "([^"]+)"\]', pgn)
        opponent = match.group(1) if match else game.get("white_player", "Opponent")
    
    # Get opening played
    opening_played = _extract_opening_family(game)
    
    # Audit each domain
    audited_plan = plan.copy()
    audited_plan["is_audited"] = True
    audited_plan["audited_against_game_id"] = game.get("game_id")
    
    for card in audited_plan.get("cards", []):
        domain = card.get("domain")
        
        if domain == "opening":
            _audit_opening_domain(card, moves, thresholds, opening_played)
        elif domain == "middlegame":
            _audit_middlegame_domain(card, moves, thresholds, game_result)
        elif domain == "tactics":
            _audit_tactics_domain(card, moves, thresholds, analysis)
        elif domain == "endgame":
            _audit_endgame_domain(card, moves, thresholds, game_result)
        elif domain == "time":
            _audit_time_domain(card, moves, thresholds)
    
    # Calculate summary
    executed = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "executed")
    partial = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "partial")
    missed = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "missed")
    applicable = executed + partial + missed
    
    audited_plan["audit_summary"] = {
        "executed": executed,
        "partial": partial,
        "missed": missed,
        "applicable": applicable,
        "score": f"{executed}/{applicable}" if applicable > 0 else "0/0",
        "game_result": game_result,
        "opponent_name": opponent,
        "user_color": user_color,
        "opening_played": opening_played,
    }
    
    return audited_plan


def _audit_opening_domain(card: Dict, moves: List[Dict], thresholds: Dict, opening: str):
    """Audit the opening domain."""
    
    early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
    
    if not early_moves:
        card["audit"]["status"] = "n/a"
        card["audit"]["coach_note"] = "Game too short to evaluate opening."
        return
    
    max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
    avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
    early_blunders = sum(1 for m in early_moves if m.get("evaluation") == "blunder")
    
    data_points = [
        f"Played: {opening}",
        f"Avg CP loss (moves 1-10): {round(avg_cp)}",
    ]
    
    evidence = []
    if early_blunders > 0:
        # Find the blunder moves
        for m in early_moves:
            if m.get("evaluation") == "blunder":
                evidence.append({
                    "move": m.get("move_number"),
                    "eval": m.get("eval_after", 0),
                    "delta": -m.get("cp_loss", 0),
                    "note": f"Blunder: {m.get('move')}",
                })
    
    # Determine status
    if early_blunders == 0 and max_drop <= thresholds["acceptable_early_drop"]:
        status = "executed"
        coach_note = "Solid opening. Development on track."
    elif early_blunders == 0 and max_drop <= thresholds["mistake_cp"]:
        status = "partial"
        coach_note = "Opening okay, but had some inaccuracies."
    else:
        status = "missed"
        coach_note = f"Opening went wrong. {early_blunders} early blunder(s)."
    
    card["audit"]["status"] = status
    card["audit"]["data_points"] = data_points
    card["audit"]["evidence"] = evidence
    card["audit"]["coach_note"] = coach_note


def _audit_middlegame_domain(card: Dict, moves: List[Dict], thresholds: Dict, game_result: str):
    """Audit the middlegame domain."""
    
    middlegame_moves = [m for m in moves if 20 < m.get("move_number", 0) <= 60]
    
    if not middlegame_moves:
        card["audit"]["status"] = "n/a"
        card["audit"]["coach_note"] = "No middlegame to evaluate."
        return
    
    # Check for advantage collapses
    collapses = []
    for m in middlegame_moves:
        eval_before = m.get("eval_before", 0)
        cp_loss = m.get("cp_loss", 0)
        
        if eval_before >= thresholds["winning_threshold"]:
            if cp_loss >= thresholds["advantage_collapse_threshold"]:
                collapses.append({
                    "move": m.get("move_number"),
                    "eval": m.get("eval_after", 0),
                    "delta": -cp_loss,
                    "note": f"Advantage dropped: {m.get('move')}",
                })
    
    had_advantage = any(m.get("eval_before", 0) >= thresholds["winning_threshold"] 
                       for m in middlegame_moves)
    
    data_points = []
    if had_advantage:
        data_points.append(f"Had winning position: Yes")
        data_points.append(f"Collapses: {len(collapses)}")
    
    evidence = collapses[:3]  # Top 3
    
    # Determine status
    if not had_advantage:
        status = "n/a"
        coach_note = "Never had a winning position to convert."
    elif len(collapses) == 0:
        status = "executed"
        coach_note = "Held advantages well. Good discipline."
    elif len(collapses) == 1:
        status = "partial"
        coach_note = "One slip when winning. Be more careful."
    else:
        status = "missed"
        coach_note = f"Collapsed {len(collapses)} times when winning. Major issue."
    
    card["audit"]["status"] = status
    card["audit"]["data_points"] = data_points
    card["audit"]["evidence"] = evidence
    card["audit"]["coach_note"] = coach_note


def _audit_tactics_domain(card: Dict, moves: List[Dict], thresholds: Dict, analysis: Dict):
    """Audit the tactics domain."""
    
    blunders = analysis.get("blunders", 0)
    mistakes = analysis.get("mistakes", 0)
    
    # Find blunder moves for evidence
    blunder_moves = [m for m in moves if m.get("evaluation") == "blunder"]
    evidence = []
    for m in blunder_moves[:3]:
        evidence.append({
            "move": m.get("move_number"),
            "eval": m.get("eval_after", 0),
            "delta": -m.get("cp_loss", 0),
            "note": f"Blunder: {m.get('move')} ({m.get('cp_loss', 0)}cp lost)",
        })
    
    data_points = [
        f"Blunders: {blunders}",
        f"Mistakes: {mistakes}",
    ]
    
    # Success criteria from card
    allowed_blunders = 1 if "beginner" in (card.get("intensity_name", "") or "").lower() else 0
    
    if blunders == 0:
        status = "executed"
        coach_note = "No blunders! Excellent tactical discipline."
    elif blunders <= allowed_blunders:
        status = "partial"
        coach_note = "One blunder - stay sharp, you can do better."
    else:
        status = "missed"
        coach_note = f"{blunders} blunders. Need to slow down and check threats."
    
    card["audit"]["status"] = status
    card["audit"]["data_points"] = data_points
    card["audit"]["evidence"] = evidence
    card["audit"]["coach_note"] = coach_note


def _audit_endgame_domain(card: Dict, moves: List[Dict], thresholds: Dict, game_result: str):
    """Audit the endgame domain."""
    
    endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
    
    if len(endgame_moves) < 5:
        card["audit"]["status"] = "n/a"
        card["audit"]["coach_note"] = "No significant endgame reached."
        return
    
    # Check if entered with advantage
    first_eg = endgame_moves[0]
    entering_eval = first_eg.get("eval_before", 0)
    
    had_winning_endgame = entering_eval >= thresholds["winning_threshold"]
    
    data_points = []
    evidence = []
    
    if had_winning_endgame:
        data_points.append(f"Entered endgame winning: +{entering_eval/100:.1f}")
        
        if game_result == "win":
            status = "executed"
            coach_note = "Converted winning endgame. Well done."
        else:
            status = "missed"
            coach_note = "Had winning endgame but didn't convert. Work on technique."
            
            # Find where it went wrong
            for m in endgame_moves:
                if m.get("cp_loss", 0) >= thresholds["mistake_cp"]:
                    evidence.append({
                        "move": m.get("move_number"),
                        "eval": m.get("eval_after", 0),
                        "delta": -m.get("cp_loss", 0),
                        "note": f"Endgame error: {m.get('move')}",
                    })
                    break
    else:
        status = "n/a"
        coach_note = "Did not enter endgame with winning position."
    
    card["audit"]["status"] = status
    card["audit"]["data_points"] = data_points
    card["audit"]["evidence"] = evidence[:3]
    card["audit"]["coach_note"] = coach_note


def _audit_time_domain(card: Dict, moves: List[Dict], thresholds: Dict):
    """Audit the time domain."""
    
    late_moves = [m for m in moves if m.get("move_number", 0) > 50]
    
    if not late_moves:
        card["audit"]["status"] = "n/a"
        card["audit"]["coach_note"] = "Game ended before late-game time pressure."
        return
    
    late_blunders = [m for m in late_moves if m.get("evaluation") == "blunder"]
    
    data_points = [f"Late-game blunders: {len(late_blunders)}"]
    evidence = []
    for m in late_blunders[:2]:
        evidence.append({
            "move": m.get("move_number"),
            "eval": m.get("eval_after", 0),
            "delta": -m.get("cp_loss", 0),
            "note": f"Time pressure blunder: {m.get('move')}",
        })
    
    if len(late_blunders) == 0:
        status = "executed"
        coach_note = "No time pressure issues. Good clock management."
    elif len(late_blunders) == 1:
        status = "partial"
        coach_note = "One late blunder - watch the clock."
    else:
        status = "missed"
        coach_note = f"{len(late_blunders)} late blunders. Time management needs work."
    
    card["audit"]["status"] = status
    card["audit"]["data_points"] = data_points
    card["audit"]["evidence"] = evidence
    card["audit"]["coach_note"] = coach_note


# =============================================================================
# PUBLIC API - Main entry points for the coaching loop
# =============================================================================

async def get_coaching_profile(db, user_id: str) -> Dict:
    """
    Get all inputs needed for plan generation.
    
    Fetches:
    - User's rating
    - Last 25 games and analyses
    - Plan history (for domain miss tracking)
    - Calculates fundamentals, patterns, opening recs
    """
    
    # Get user
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"error": "User not found"}
    
    rating = user.get("rating", 1200)
    rating_band = get_rating_band(rating)
    
    # Get games and analyses
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(30)
    
    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0}
    ).to_list(30)
    
    # Get plan history
    plan_history = await db.user_plans.find(
        {"user_id": user_id, "is_audited": True},
        {"_id": 0}
    ).sort("generated_at", -1).to_list(10)
    
    # Calculate all profile components
    fundamentals = calculate_fundamentals_from_games(analyses, games, rating_band["name"])
    patterns = detect_weakness_patterns(analyses, games, rating_band["name"])
    opening_recs = calculate_opening_recommendations(analyses, games, rating_band["name"])
    domain_history = build_domain_history(plan_history)
    
    return {
        "user_id": user_id,
        "rating": rating,
        "rating_band": rating_band,
        "fundamentals": fundamentals,
        "weakness_patterns": patterns,
        "opening_recommendations": opening_recs,
        "domain_history": domain_history,
        "games_analyzed": len(analyses),
        "has_enough_data": len(analyses) >= 10,
    }


async def generate_round_preparation(db, user_id: str) -> Dict:
    """
    Generate the next game plan (Round Preparation).
    
    This is called when user opens the Coach page.
    Returns a plan customized to their profile.
    """
    
    # Get coaching profile
    profile = await get_coaching_profile(db, user_id)
    if profile.get("error"):
        return profile
    
    # Get last audited game for critical insights
    critical_insights = []
    last_audit = None
    
    plan_history = await db.user_plans.find(
        {"user_id": user_id, "is_audited": True},
        {"_id": 0}
    ).sort("generated_at", -1).to_list(1)
    
    if plan_history:
        last_audit = plan_history[0]
        game_id = last_audit.get("audited_against_game_id")
        
        if game_id:
            # Get analysis for critical insights
            analysis = await db.game_analyses.find_one(
                {"game_id": game_id},
                {"_id": 0}
            )
            game = await db.games.find_one(
                {"game_id": game_id},
                {"_id": 0}
            )
            
            if analysis and game:
                try:
                    from coaching_loop_service import extract_critical_insights_from_analysis
                    critical_insights = extract_critical_insights_from_analysis(analysis, game)
                except Exception as e:
                    logger.warning(f"Failed to extract critical insights: {e}")
    
    # Generate the plan
    plan = generate_deterministic_plan(
        user_id=user_id,
        rating=profile["rating"],
        fundamentals=profile["fundamentals"],
        weakness_patterns=profile["weakness_patterns"],
        opening_recommendations=profile["opening_recommendations"],
        domain_history=profile["domain_history"],
        last_audit=last_audit,
        critical_insights=critical_insights,
    )
    
    # Save plan
    await db.user_plans.update_one(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False}},
    )
    await db.user_plans.insert_one(plan)
    
    return plan


async def generate_plan_audit(db, user_id: str) -> Dict:
    """
    Audit the last game against the current plan.
    
    Returns the plan with audit results filled in.
    """
    
    # Get active plan
    plan = await db.user_plans.find_one(
        {"user_id": user_id, "is_active": True, "is_audited": False},
        {"_id": 0}
    )
    
    if not plan:
        return {"has_data": False, "message": "No active plan to audit against"}
    
    # Get the latest analyzed game
    game = await db.games.find_one(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0},
        sort=[("imported_at", -1)]
    )
    
    if not game:
        return {"has_data": False, "message": "No analyzed games found"}
    
    # Get analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game["game_id"]},
        {"_id": 0}
    )
    
    if not analysis:
        return {"has_data": False, "message": "Game analysis not found"}
    
    # Audit the game
    audited_plan = audit_game_against_plan(plan, game, analysis)
    
    # Save audited plan
    await db.user_plans.update_one(
        {"plan_id": plan["plan_id"]},
        {"$set": audited_plan}
    )
    
    return {
        "has_data": True,
        **audited_plan
    }
