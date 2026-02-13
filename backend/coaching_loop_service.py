"""
Coaching Loop Service - GM Coach Style Plan → Play → Audit → Adjust

This is the GOLD FEATURE of ChessGuru.ai

The coaching loop:
1. PLAN: Generate personalized plan for next game
2. PLAY: User plays their game
3. AUDIT: Evaluate game against the exact plan we gave
4. ADJUST: Update intensity, persist failed domains

Key Principles:
- Deterministic logic for all decisions (no LLM for correctness)
- Personalized using: rating band, behavior patterns, fundamentals profile, opening stats, last audit
- Same PlanCard schema for both preparation and audit
- Evidence-backed with move numbers, eval swings, time markers
- Short coach bullets, not essays
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# PLAN CARD SCHEMA
# =============================================================================

def create_empty_plan_card(user_id: str, rating_band: str) -> Dict:
    """Create an empty PlanCard structure."""
    return {
        "plan_id": str(uuid.uuid4()),
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applies_to_game_id": None,  # Will be set when user plays next game
        "rating_band": rating_band,
        "training_block": {
            "name": "Foundation",
            "intensity": 1  # 1-3
        },
        "cards": [],  # Will be populated with domain cards
        "is_active": True,
        "is_audited": False,
        "audited_against_game_id": None
    }


def create_domain_card(
    domain: str,
    priority: str,
    goal: str,
    rules: List[str],
    success_criteria: List[Dict]
) -> Dict:
    """Create a single domain card."""
    return {
        "domain": domain,  # opening | middlegame | tactics | endgame | time
        "priority": priority,  # primary | secondary | baseline
        "goal": goal,  # 1-line coach objective
        "rules": rules[:4] if priority == "primary" else rules[:2] if priority == "secondary" else rules[:1],
        "success_criteria": success_criteria,
        "audit": {
            "status": None,  # executed | partial | missed | n/a
            "data_points": [],  # computed facts
            "evidence": [],  # move references
            "coach_note": None  # 1-2 lines, deterministic
        }
    }


# =============================================================================
# FUNDAMENTALS PROFILE CALCULATOR
# =============================================================================

def calculate_fundamentals_profile(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate user's fundamentals profile across 5 domains.
    
    Returns scores 0-100 for each domain:
    - opening_discipline: early eval stability, development timing
    - tactical_awareness: blunder rate, missed tactic rate
    - middlegame_quality: advantage stability, decision quality when ahead
    - endgame_conversion: conversion rate when entering endgame with advantage
    - time_discipline: late-game blunder correlation, time trouble frequency
    """
    if not analyses or len(analyses) < 3:
        return {
            "opening_discipline": 50,
            "tactical_awareness": 50,
            "middlegame_quality": 50,
            "endgame_conversion": 50,
            "time_discipline": 50,
            "sample_size": len(analyses) if analyses else 0
        }
    
    recent = analyses[-20:]  # Last 20 games
    n = len(recent)
    
    # === OPENING DISCIPLINE ===
    opening_scores = []
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Check first 10 moves for stability
        early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
        if early_moves:
            max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
            avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
            
            # Score: lower drops = better
            if max_drop < 50 and avg_cp < 20:
                opening_scores.append(90)
            elif max_drop < 100 and avg_cp < 40:
                opening_scores.append(70)
            elif max_drop < 200:
                opening_scores.append(50)
            else:
                opening_scores.append(30)
    
    opening_discipline = sum(opening_scores) / len(opening_scores) if opening_scores else 50
    
    # === TACTICAL AWARENESS ===
    total_blunders = sum(a.get("blunders", 0) for a in recent)
    avg_blunders = total_blunders / n
    
    if avg_blunders < 0.5:
        tactical_awareness = 90
    elif avg_blunders < 1:
        tactical_awareness = 75
    elif avg_blunders < 2:
        tactical_awareness = 55
    elif avg_blunders < 3:
        tactical_awareness = 35
    else:
        tactical_awareness = 20
    
    # === MIDDLEGAME QUALITY (Advantage Stability) ===
    advantage_scores = []
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Find moves where user had +1.5 or better
        had_advantage = False
        collapsed = False
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            eval_after = m.get("eval_after", 0)
            
            if eval_before >= 150:
                had_advantage = True
                if eval_before - eval_after > 150:
                    collapsed = True
        
        if had_advantage:
            advantage_scores.append(30 if collapsed else 90)
    
    middlegame_quality = sum(advantage_scores) / len(advantage_scores) if advantage_scores else 50
    
    # === ENDGAME CONVERSION ===
    endgame_conversions = []
    for i, a in enumerate(recent):
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Check if endgame reached (move > 30 per side = 60 total)
        endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
        
        if len(endgame_moves) >= 5:
            # Had advantage entering endgame?
            first_endgame = endgame_moves[0] if endgame_moves else None
            if first_endgame and first_endgame.get("eval_before", 0) >= 100:
                # Check game result
                game = games[i] if i < len(games) else None
                if game:
                    result = game.get("result", "")
                    user_color = game.get("user_color", "white")
                    won = (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1")
                    endgame_conversions.append(100 if won else 30)
    
    endgame_conversion = sum(endgame_conversions) / len(endgame_conversions) if endgame_conversions else 50
    
    # === TIME DISCIPLINE ===
    # Check for late-game blunders (proxy for time trouble)
    late_blunder_rate = []
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        blunders = a.get("blunders", 0)
        
        late_blunders = sum(1 for m in moves if m.get("move_number", 0) > 50 and m.get("classification") == "blunder")
        
        if blunders > 0:
            late_ratio = late_blunders / blunders if blunders > 0 else 0
            late_blunder_rate.append(late_ratio)
    
    avg_late_ratio = sum(late_blunder_rate) / len(late_blunder_rate) if late_blunder_rate else 0.5
    time_discipline = max(20, min(90, 90 - (avg_late_ratio * 60)))
    
    return {
        "opening_discipline": round(opening_discipline),
        "tactical_awareness": round(tactical_awareness),
        "middlegame_quality": round(middlegame_quality),
        "endgame_conversion": round(endgame_conversion),
        "time_discipline": round(time_discipline),
        "sample_size": n
    }


# =============================================================================
# BEHAVIOR PATTERN DETECTOR
# =============================================================================

def detect_behavior_patterns(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Detect user's behavior patterns (weaknesses and strengths).
    
    Patterns detected:
    - advantage_collapse: Loses eval when ahead
    - piece_safety: Hangs pieces frequently
    - tactical_blindness: Misses forcing moves
    - passivity: Doesn't improve position when equal
    - time_trouble: Blunders under time pressure
    - opening_drift: Deviates from known openings
    """
    if not analyses:
        return {"patterns": [], "primary_weakness": None, "strengths": []}
    
    recent = analyses[-15:]
    n = len(recent)
    
    patterns = []
    
    # === ADVANTAGE COLLAPSE ===
    collapse_count = 0
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            eval_after = m.get("eval_after", 0)
            
            if eval_before >= 150 and eval_before - eval_after > 150:
                collapse_count += 1
                break
    
    if collapse_count / n >= 0.4:
        patterns.append({
            "pattern": "advantage_collapse",
            "label": "Loses Focus When Winning",
            "severity": "high" if collapse_count / n >= 0.6 else "medium",
            "frequency": f"{collapse_count}/{n} games"
        })
    
    # === PIECE SAFETY ===
    hung_piece_games = 0
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        for m in moves:
            if m.get("classification") == "blunder" and m.get("cp_loss", 0) >= 300:
                hung_piece_games += 1
                break
    
    if hung_piece_games / n >= 0.3:
        patterns.append({
            "pattern": "piece_safety",
            "label": "Hangs Pieces",
            "severity": "high" if hung_piece_games / n >= 0.5 else "medium",
            "frequency": f"{hung_piece_games}/{n} games"
        })
    
    # === TACTICAL BLINDNESS ===
    total_blunders = sum(a.get("blunders", 0) for a in recent)
    avg_blunders = total_blunders / n
    
    if avg_blunders >= 2:
        patterns.append({
            "pattern": "tactical_blindness",
            "label": "Misses Tactics",
            "severity": "high" if avg_blunders >= 3 else "medium",
            "frequency": f"{round(avg_blunders, 1)} blunders/game"
        })
    
    # === TIME TROUBLE ===
    late_blunder_games = 0
    for a in recent:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        late_blunders = sum(1 for m in moves if m.get("move_number", 0) > 50 and m.get("classification") == "blunder")
        if late_blunders >= 1:
            late_blunder_games += 1
    
    if late_blunder_games / n >= 0.3:
        patterns.append({
            "pattern": "time_trouble",
            "label": "Time Pressure Blunders",
            "severity": "high" if late_blunder_games / n >= 0.5 else "medium",
            "frequency": f"{late_blunder_games}/{n} games"
        })
    
    # Determine primary weakness (highest severity, highest frequency)
    primary_weakness = None
    if patterns:
        high_severity = [p for p in patterns if p["severity"] == "high"]
        if high_severity:
            primary_weakness = high_severity[0]["pattern"]
        else:
            primary_weakness = patterns[0]["pattern"]
    
    # Determine strengths (areas without issues)
    strengths = []
    pattern_names = [p["pattern"] for p in patterns]
    
    if "advantage_collapse" not in pattern_names and any(
        sf.get("move_evaluations", []) 
        for a in recent 
        for sf in [a.get("stockfish_analysis", {})]
    ):
        strengths.append("advantage_stability")
    
    if "tactical_blindness" not in pattern_names and avg_blunders < 1:
        strengths.append("tactical_awareness")
    
    if "piece_safety" not in pattern_names and hung_piece_games / n < 0.2:
        strengths.append("piece_safety")
    
    return {
        "patterns": patterns,
        "primary_weakness": primary_weakness,
        "strengths": strengths
    }


# =============================================================================
# OPENING NAME EXTRACTION
# =============================================================================

def _extract_opening_name(game: Dict) -> str:
    """
    Extract the actual opening name from a game.
    
    Priority:
    1. ECOUrl (e.g., "https://www.chess.com/openings/Sicilian-Defense-Alapin-Variation")
       → "Sicilian Defense"
    2. Opening field in game
    3. ECO code lookup
    4. Fallback to "Unknown"
    """
    pgn = game.get("pgn", "")
    
    # Try ECOUrl first (most reliable for chess.com games)
    eco_url_match = re.search(r'\[ECOUrl "[^"]+/([^/"]+)"\]', pgn)
    if eco_url_match:
        # Convert "Sicilian-Defense-Alapin-Variation" to "Sicilian Defense"
        raw_name = eco_url_match.group(1)
        # Split by hyphen and take first 2-3 meaningful parts
        parts = raw_name.split("-")
        # Filter out common suffixes like "Variation", "Attack", etc for grouping
        main_parts = []
        for part in parts:
            if part.lower() in ["variation", "attack", "defense", "defence", "game", "opening", "gambit"]:
                main_parts.append(part.title())
                break
            main_parts.append(part.title())
            if len(main_parts) >= 2:
                break
        if main_parts:
            return " ".join(main_parts)
    
    # Try Opening field in PGN
    opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
    if opening_match:
        opening = opening_match.group(1)
        # Take first 2-3 words for grouping
        parts = opening.split()[:3]
        return " ".join(parts)
    
    # Try opening field in game object
    if game.get("opening"):
        parts = game["opening"].split()[:3]
        return " ".join(parts)
    
    # Try ECO code and map to opening name
    eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
    if eco_match:
        eco = eco_match.group(1)
        return _eco_to_opening_name(eco)
    
    return "Unknown Opening"


def _eco_to_opening_name(eco: str) -> str:
    """
    Map ECO code to opening family name.
    """
    eco_map = {
        # A - Flank openings
        "A00": "Irregular Opening",
        "A01": "Nimzowitsch-Larsen",
        "A02": "Bird Opening",
        "A04": "Reti Opening",
        "A10": "English Opening",
        "A20": "English Opening",
        "A30": "English Opening",
        "A40": "Queen's Pawn",
        "A45": "Indian Defense",
        "A50": "Indian Defense",
        # B - Semi-open games
        "B00": "King's Pawn",
        "B01": "Scandinavian Defense",
        "B02": "Alekhine Defense",
        "B06": "Modern Defense",
        "B07": "Pirc Defense",
        "B10": "Caro-Kann",
        "B20": "Sicilian Defense",
        "B30": "Sicilian Defense",
        "B40": "Sicilian Defense",
        "B50": "Sicilian Defense",
        "B60": "Sicilian Defense",
        "B70": "Sicilian Defense",
        "B80": "Sicilian Defense",
        "B90": "Sicilian Defense",
        # C - Open games
        "C00": "French Defense",
        "C10": "French Defense",
        "C20": "King's Pawn",
        "C30": "King's Gambit",
        "C40": "King's Knight",
        "C41": "Philidor Defense",
        "C42": "Petrov Defense",
        "C44": "Scotch Game",
        "C45": "Scotch Game",
        "C50": "Italian Game",
        "C54": "Italian Game",
        "C55": "Two Knights",
        "C60": "Ruy Lopez",
        "C70": "Ruy Lopez",
        "C80": "Ruy Lopez",
        "C90": "Ruy Lopez",
        # D - Closed/Semi-closed games
        "D00": "Queen's Pawn",
        "D02": "London System",
        "D06": "Queen's Gambit",
        "D10": "Slav Defense",
        "D20": "Queen's Gambit",
        "D30": "Queen's Gambit",
        "D40": "Queen's Gambit",
        "D50": "Queen's Gambit",
        "D70": "Grunfeld Defense",
        "D80": "Grunfeld Defense",
        "D90": "Grunfeld Defense",
        # E - Indian defenses
        "E00": "Indian Defense",
        "E10": "Indian Defense",
        "E20": "Nimzo-Indian",
        "E30": "Nimzo-Indian",
        "E40": "Nimzo-Indian",
        "E60": "King's Indian",
        "E70": "King's Indian",
        "E80": "King's Indian",
        "E90": "King's Indian",
    }
    
    # Try exact match first
    if eco in eco_map:
        return eco_map[eco]
    
    # Try prefix match (e.g., B32 matches B30)
    eco_prefix = eco[:2] + "0"
    if eco_prefix in eco_map:
        return eco_map[eco_prefix]
    
    # Try first letter match
    eco_letter = eco[0]
    letter_defaults = {
        "A": "Flank Opening",
        "B": "Semi-Open Game",
        "C": "Open Game",
        "D": "Closed Game",
        "E": "Indian Defense"
    }
    return letter_defaults.get(eco_letter, f"Opening {eco}")


# =============================================================================
# OPENING STABILITY CALCULATOR
# =============================================================================

def calculate_opening_stability(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate opening stability scores (NOT just win rate).
    
    Stability Score = weighted combination of:
    - Early eval stability (moves 1-10)
    - Early blunder/mistake rate
    - Development markers
    - Volatility (max eval drop)
    
    Returns recommendations per color:
    - play_this: Most stable opening
    - avoid_for_now: Least stable opening (only if sample >= 3)
    """
    if not games or len(games) < 5:
        return {
            "as_white": {"play_this": None, "avoid_for_now": None, "openings": []},
            "as_black": {"play_this": None, "avoid_for_now": None, "openings": []},
            "sample_size": len(games) if games else 0
        }
    
    # Create a lookup map for analyses by game_id
    analysis_map = {}
    for analysis in analyses:
        game_id = analysis.get("game_id")
        if game_id:
            analysis_map[game_id] = analysis
    
    # Group games by color and opening
    openings_white = {}
    openings_black = {}
    
    for game in games[-30:]:  # Last 30 games
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id)
        if not analysis:
            continue
        
        user_color = game.get("user_color", "white")
        
        # Extract opening name properly from PGN
        opening = _extract_opening_name(game)
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Calculate early stability metrics
        early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
        
        if not early_moves:
            continue
        
        max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
        avg_cp_loss = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves)
        early_blunders = sum(1 for m in early_moves if m.get("classification") == "blunder")
        
        # Stability score (0-100)
        stability = 100
        stability -= min(30, max_drop / 10)  # Penalize big drops
        stability -= min(20, avg_cp_loss)  # Penalize avg cp loss
        stability -= early_blunders * 15  # Heavy penalty for early blunders
        stability = max(0, stability)
        
        # Store by color
        target = openings_white if user_color == "white" else openings_black
        
        if opening not in target:
            target[opening] = {
                "name": opening,
                "games": 0,
                "stability_scores": [],
                "wins": 0
            }
        
        target[opening]["games"] += 1
        target[opening]["stability_scores"].append(stability)
        
        result = game.get("result", "")
        won = (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1")
        if won:
            target[opening]["wins"] += 1
    
    def process_openings(openings_dict):
        result = []
        for name, data in openings_dict.items():
            if data["games"] >= 2:  # Minimum sample
                avg_stability = sum(data["stability_scores"]) / len(data["stability_scores"])
                win_rate = (data["wins"] / data["games"]) * 100
                
                result.append({
                    "name": name,
                    "games": data["games"],
                    "stability_score": round(avg_stability),
                    "win_rate": round(win_rate)
                })
        
        return sorted(result, key=lambda x: x["stability_score"], reverse=True)
    
    white_openings = process_openings(openings_white)
    black_openings = process_openings(openings_black)
    
    def get_recommendations(openings):
        if not openings:
            return {"play_this": None, "avoid_for_now": None, "openings": []}
        
        play_this = openings[0] if openings else None
        avoid_for_now = openings[-1] if len(openings) >= 2 and openings[-1]["games"] >= 3 and openings[-1]["stability_score"] < 60 else None
        
        return {
            "play_this": play_this,
            "avoid_for_now": avoid_for_now,
            "openings": openings[:5]  # Top 5
        }
    
    return {
        "as_white": get_recommendations(white_openings),
        "as_black": get_recommendations(black_openings),
        "sample_size": len(games)
    }


# =============================================================================
# ADAPTIVE INTENSITY ESCALATION SYSTEM
# =============================================================================

def get_domain_miss_history(last_audits: List[Dict]) -> Dict[str, Dict]:
    """
    Analyze recent audits to track consecutive misses per domain.
    
    Returns:
    {
        "opening": {"consecutive_misses": 2, "last_status": "missed", "needs_escalation": True},
        "middlegame": {"consecutive_misses": 0, "last_status": "executed", "needs_escalation": False},
        ...
    }
    
    Escalation rules:
    - 2 consecutive misses → Increase intensity, simplify rules
    - 4 consecutive misses → Force micro-habit level (intensity 3)
    - 3 consecutive executions → Mark as stable, reduce detail
    """
    history = {
        "opening": {"consecutive_misses": 0, "consecutive_executions": 0, "last_status": None, "needs_escalation": False, "is_stable": False},
        "middlegame": {"consecutive_misses": 0, "consecutive_executions": 0, "last_status": None, "needs_escalation": False, "is_stable": False},
        "tactics": {"consecutive_misses": 0, "consecutive_executions": 0, "last_status": None, "needs_escalation": False, "is_stable": False},
        "endgame": {"consecutive_misses": 0, "consecutive_executions": 0, "last_status": None, "needs_escalation": False, "is_stable": False},
        "time": {"consecutive_misses": 0, "consecutive_executions": 0, "last_status": None, "needs_escalation": False, "is_stable": False}
    }
    
    if not last_audits:
        return history
    
    # Process audits from oldest to newest
    for audit in last_audits:
        for card in audit.get("cards", []):
            domain = card.get("domain")
            if domain not in history:
                continue
            
            status = card.get("audit", {}).get("status")
            if not status or status == "n/a":
                continue
            
            if status == "missed":
                history[domain]["consecutive_misses"] += 1
                history[domain]["consecutive_executions"] = 0
            elif status == "executed":
                history[domain]["consecutive_executions"] += 1
                history[domain]["consecutive_misses"] = 0
            else:  # partial
                # Partial doesn't break execution streak but doesn't add to it
                history[domain]["consecutive_misses"] = 0
            
            history[domain]["last_status"] = status
    
    # Determine escalation and stability
    for domain, data in history.items():
        data["needs_escalation"] = data["consecutive_misses"] >= 2
        data["is_stable"] = data["consecutive_executions"] >= 3
    
    return history


def calculate_domain_intensity(
    domain: str,
    base_intensity: int,
    miss_history: Dict[str, Dict]
) -> int:
    """
    Calculate intensity for a specific domain based on miss history.
    
    Intensity levels:
    - 1: Outcome focus (e.g., "convert winning positions")
    - 2: Behavior focus (e.g., "pause when +1.5")
    - 3: Micro-habit (e.g., "check piece safety before EVERY move")
    """
    domain_data = miss_history.get(domain, {})
    consecutive_misses = domain_data.get("consecutive_misses", 0)
    
    if consecutive_misses >= 4:
        return 3  # Force micro-habit
    elif consecutive_misses >= 2:
        return min(3, base_intensity + 1)  # Escalate
    else:
        return base_intensity


def get_escalated_rules(domain: str, base_rules: List[str], intensity: int, is_escalated: bool) -> List[str]:
    """
    Get rules adjusted for intensity level.
    
    At higher intensity:
    - Simplify rules
    - Focus on micro-habits
    - More prescriptive language
    """
    if not is_escalated or intensity < 2:
        return base_rules
    
    # Intensity 2: Behavior focus
    intensity_2_rules = {
        "opening": [
            "Before move 1: Decide on your opening. No improvisation.",
            "If unfamiliar position: Castle first, ask questions later.",
        ],
        "middlegame": [
            "When eval shows +1.5: STOP. Count to 5. Then simplify.",
            "Ask: 'Am I winning? If yes, trade a piece.'",
        ],
        "tactics": [
            "CCT protocol EVERY move: Checks, Captures, Threats.",
            "Before moving: 'What does opponent want to do next?'",
        ],
        "endgame": [
            "Queens off? King to center immediately.",
            "One plan only: Push passed pawn or create one.",
        ],
        "time": [
            "Check clock after every 5 moves.",
            "Under 2 minutes: Play safe, not brilliant.",
        ]
    }
    
    # Intensity 3: Micro-habit (very specific, one action)
    intensity_3_rules = {
        "opening": [
            "ONE rule: Play your prepared opening. Zero exceptions.",
        ],
        "middlegame": [
            "ONE rule: When ahead, trade ONE piece before doing anything else.",
        ],
        "tactics": [
            "ONE rule: Before EVERY move, say 'checks, captures, threats' out loud.",
        ],
        "endgame": [
            "ONE rule: King moves toward center. Every. Single. Endgame.",
        ],
        "time": [
            "ONE rule: Never think more than 30 seconds on one move.",
        ]
    }
    
    if intensity >= 3:
        return intensity_3_rules.get(domain, base_rules[:1])
    elif intensity >= 2:
        return intensity_2_rules.get(domain, base_rules[:2])
    
    return base_rules


# =============================================================================
# TRAINING BLOCK MANAGER
# =============================================================================

def get_training_block(primary_weakness: str, fundamentals: Dict, last_audit: Dict = None, miss_history: Dict = None) -> Dict:
    """
    Determine training block based on weakness and fundamentals.
    
    Training blocks:
    - Finish Strong: For advantage collapse
    - Piece Safety: For hanging pieces
    - Tactical Vision: For tactical blindness
    - Clock Master: For time trouble
    - Foundation: Default balanced
    
    Intensity (1-3):
    - 1: Outcome focus (e.g., convert 4/5 winning positions)
    - 2: Behavior focus (e.g., pause 10 seconds when +1.5)
    - 3: Micro-habit (e.g., check piece safety before every move)
    
    Adaptive Escalation:
    - 2 consecutive misses on primary domain → intensity +1
    - 4 consecutive misses → force intensity 3
    - 3 consecutive executions → mark stable, reduce verbosity
    """
    
    # Calculate consecutive misses from history
    consecutive_misses = 0
    primary_domain = None
    
    # Map weakness to domain
    weakness_to_domain = {
        "advantage_collapse": "middlegame",
        "piece_safety": "tactics",
        "tactical_blindness": "tactics",
        "time_trouble": "time",
        "opening_drift": "opening"
    }
    
    if primary_weakness:
        primary_domain = weakness_to_domain.get(primary_weakness, "tactics")
    
    # Get consecutive misses from history if available
    if miss_history and primary_domain:
        consecutive_misses = miss_history.get(primary_domain, {}).get("consecutive_misses", 0)
    elif last_audit:
        # Fallback: count from last audit
        for card in last_audit.get("cards", []):
            if card.get("priority") == "primary":
                status = card.get("audit", {}).get("status")
                if status == "missed":
                    consecutive_misses = last_audit.get("consecutive_misses", 0) + 1
    
    # Intensity adjustment based on consecutive misses
    if consecutive_misses >= 4:
        base_intensity = 3
    elif consecutive_misses >= 2:
        base_intensity = 2
    else:
        base_intensity = 1
    
    # Determine training block
    blocks = {
        "advantage_collapse": {
            "name": "Finish Strong",
            "focus": "Converting winning positions"
        },
        "piece_safety": {
            "name": "Piece Safety",
            "focus": "No hanging pieces"
        },
        "tactical_blindness": {
            "name": "Tactical Vision",
            "focus": "Checks, captures, threats"
        },
        "time_trouble": {
            "name": "Clock Master",
            "focus": "Time management"
        }
    }
    
    if primary_weakness and primary_weakness in blocks:
        block = blocks[primary_weakness]
    else:
        # Default based on lowest fundamental
        lowest = min(fundamentals.items(), key=lambda x: x[1] if x[0] != "sample_size" else 100)
        
        fundamental_to_block = {
            "opening_discipline": {"name": "Opening Prep", "focus": "Stable openings"},
            "tactical_awareness": {"name": "Tactical Vision", "focus": "Checks, captures, threats"},
            "middlegame_quality": {"name": "Finish Strong", "focus": "Converting advantages"},
            "endgame_conversion": {"name": "Endgame Technique", "focus": "Converting endgames"},
            "time_discipline": {"name": "Clock Master", "focus": "Time management"}
        }
        
        block = fundamental_to_block.get(lowest[0], {"name": "Foundation", "focus": "Balanced improvement"})
    
    return {
        "name": block["name"],
        "focus": block["focus"],
        "intensity": base_intensity,
        "consecutive_misses": consecutive_misses,
        "escalated": consecutive_misses >= 2
    }


# =============================================================================
# PLAN GENERATOR (DETERMINISTIC)
# =============================================================================

def generate_next_plan(
    user_id: str,
    rating_band: str,
    fundamentals: Dict,
    behavior_patterns: Dict,
    opening_stability: Dict,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """
    Generate the next game plan (DETERMINISTIC).
    
    This is the core of the coaching loop.
    
    Inputs used:
    - rating_band: Adjusts difficulty and language
    - fundamentals: Determines baseline expectations
    - behavior_patterns: Determines primary/secondary focus
    - opening_stability: Determines opening recommendations
    - last_audit: Determines persistence and intensity adjustment
    - miss_history: Tracks consecutive misses per domain for adaptive escalation
    
    Adaptive Escalation:
    - If domain missed 2x in a row → increase intensity, simplify rules
    - If domain missed 4x in a row → force micro-habit level
    - If domain executed 3x in a row → mark stable, reduce verbosity
    """
    
    primary_weakness = behavior_patterns.get("primary_weakness")
    
    # Get training block with miss history for adaptive intensity
    training_block = get_training_block(primary_weakness, fundamentals, last_audit, miss_history)
    
    # Create plan card
    plan = create_empty_plan_card(user_id, rating_band)
    plan["training_block"] = training_block
    plan["miss_history"] = miss_history or {}  # Store for reference
    
    # === DETERMINE DOMAIN PRIORITIES ===
    # Primary: Main weakness (or tactical if none)
    # Secondary: Second weakness or area needing work
    # Baseline: Everything else
    
    domain_priorities = {
        "opening": "baseline",
        "middlegame": "baseline",
        "tactics": "baseline",
        "endgame": "baseline",
        "time": "baseline"
    }
    
    # Map weakness to domain
    weakness_to_domain = {
        "advantage_collapse": "middlegame",
        "piece_safety": "tactics",
        "tactical_blindness": "tactics",
        "time_trouble": "time",
        "opening_drift": "opening"
    }
    
    if primary_weakness:
        primary_domain = weakness_to_domain.get(primary_weakness, "tactics")
        domain_priorities[primary_domain] = "primary"
    else:
        # Default to tactics if no clear weakness
        domain_priorities["tactics"] = "primary"
    
    # Set secondary based on second pattern or low fundamental
    patterns = behavior_patterns.get("patterns", [])
    if len(patterns) >= 2:
        secondary_weakness = patterns[1]["pattern"]
        secondary_domain = weakness_to_domain.get(secondary_weakness)
        if secondary_domain and domain_priorities[secondary_domain] != "primary":
            domain_priorities[secondary_domain] = "secondary"
    
    # If no secondary from patterns, use lowest fundamental
    if "secondary" not in domain_priorities.values():
        fundamental_to_domain = {
            "opening_discipline": "opening",
            "middlegame_quality": "middlegame",
            "tactical_awareness": "tactics",
            "endgame_conversion": "endgame",
            "time_discipline": "time"
        }
        
        lowest = None
        lowest_score = 100
        for key, score in fundamentals.items():
            if key != "sample_size" and score < lowest_score:
                domain = fundamental_to_domain.get(key)
                if domain and domain_priorities.get(domain) != "primary":
                    lowest = domain
                    lowest_score = score
        
        if lowest:
            domain_priorities[lowest] = "secondary"
    
    # === GENERATE DOMAIN CARDS ===
    
    # 1. OPENING CARD
    opening_card = _generate_opening_card(
        domain_priorities["opening"],
        rating_band,
        opening_stability,
        training_block["intensity"],
        last_audit,
        miss_history
    )
    plan["cards"].append(opening_card)
    
    # 2. MIDDLEGAME CARD
    middlegame_card = _generate_middlegame_card(
        domain_priorities["middlegame"],
        rating_band,
        primary_weakness,
        training_block["intensity"],
        last_audit,
        miss_history
    )
    plan["cards"].append(middlegame_card)
    
    # 3. TACTICS CARD
    tactics_card = _generate_tactics_card(
        domain_priorities["tactics"],
        rating_band,
        behavior_patterns,
        training_block["intensity"],
        last_audit,
        miss_history
    )
    plan["cards"].append(tactics_card)
    
    # 4. ENDGAME CARD
    endgame_card = _generate_endgame_card(
        domain_priorities["endgame"],
        rating_band,
        fundamentals.get("endgame_conversion", 50),
        training_block["intensity"],
        last_audit,
        miss_history
    )
    plan["cards"].append(endgame_card)
    
    # 5. TIME CARD
    time_card = _generate_time_card(
        domain_priorities["time"],
        rating_band,
        fundamentals.get("time_discipline", 50),
        training_block["intensity"],
        last_audit,
        miss_history
    )
    plan["cards"].append(time_card)
    
    return plan


def _generate_opening_card(
    priority: str,
    rating_band: str,
    opening_stability: Dict,
    intensity: int,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """Generate opening domain card with adaptive escalation."""
    
    # Check for escalation
    domain_history = (miss_history or {}).get("opening", {})
    is_escalated = domain_history.get("needs_escalation", False)
    domain_intensity = calculate_domain_intensity("opening", intensity, miss_history or {})
    
    # Get opening recommendations
    white_rec = opening_stability.get("as_white", {})
    black_rec = opening_stability.get("as_black", {})
    
    play_white = white_rec.get("play_this", {})
    play_black = black_rec.get("play_this", {})
    avoid_white = white_rec.get("avoid_for_now")
    avoid_black = black_rec.get("avoid_for_now")
    
    # Build goal - escalate if needed
    if is_escalated and domain_intensity >= 3:
        goal = "ONE opening per color. No switching. No experiments."
    elif play_white or play_black:
        goal = "Stick to stable openings. No experiments."
    else:
        goal = "Play solid, develop pieces, castle early."
    
    # Build rules based on priority and intensity
    rules = []
    
    if priority == "primary":
        if play_white:
            rules.append(f"As White: Play {play_white.get('name', 'your main opening')}")
        if play_black:
            rules.append(f"As Black: Play {play_black.get('name', 'your main defense')}")
        if avoid_white:
            rules.append(f"Avoid {avoid_white.get('name')} as White")
        if avoid_black:
            rules.append(f"Avoid {avoid_black.get('name')} as Black")
        rules.append("Complete development by move 10")
        rules.append("No early queen adventures")
    elif priority == "secondary":
        if play_white or play_black:
            rec = play_white or play_black
            rules.append(f"Prefer {rec.get('name', 'stable openings')}")
        rules.append("Castle by move 10")
    else:  # baseline
        rules.append("Develop pieces, castle, connect rooks")
    
    # Success criteria
    criteria = [
        {
            "metric": "eval_drop_moves_1_10",
            "op": "<=",
            "value": 50 if rating_band in ["600-1000", "1000-1600"] else 30,
            "window": "moves 1-10"
        }
    ]
    
    if priority in ["primary", "secondary"]:
        criteria.append({
            "metric": "early_blunders",
            "op": "==",
            "value": 0,
            "window": "moves 1-10"
        })
    
    # Apply escalated rules if needed
    if is_escalated:
        rules = get_escalated_rules("opening", rules, domain_intensity, is_escalated)
    
    card = create_domain_card("opening", priority, goal, rules, criteria)
    card["escalation"] = {
        "is_escalated": is_escalated,
        "intensity": domain_intensity,
        "consecutive_misses": domain_history.get("consecutive_misses", 0)
    }
    return card


def _generate_middlegame_card(
    priority: str,
    rating_band: str,
    primary_weakness: str,
    intensity: int,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """Generate middlegame domain card with adaptive escalation."""
    
    # Check for escalation
    domain_history = (miss_history or {}).get("middlegame", {})
    is_escalated = domain_history.get("needs_escalation", False)
    domain_intensity = calculate_domain_intensity("middlegame", intensity, miss_history or {})
    
    # Determine goal based on weakness
    if primary_weakness == "advantage_collapse":
        if is_escalated and domain_intensity >= 3:
            goal = "ONE RULE: When ahead, trade a piece. That's it."
        else:
            goal = "When ahead, simplify. Don't give back the advantage."
        
        if domain_intensity == 1:
            rules = [
                "After +1.5, look for piece trades",
                "Avoid pawn pushes that open the position",
                "Keep queens on only if you see mate",
                "Verify your move doesn't hang anything"
            ]
        elif domain_intensity == 2:
            rules = [
                "Pause 5 seconds when eval shows +1.5 or better",
                "Ask: 'Am I simplifying or complicating?'",
                "Trade one pair of pieces when clearly winning",
                "No speculative sacrifices when ahead"
            ]
        else:  # intensity 3
            rules = [
                "Before EVERY move when winning: check if pieces are safe",
                "If +2 or better: must trade at least one piece",
                "No attacking moves unless forced win is seen"
            ]
    else:
        goal = "Improve your position before attacking."
        
        if priority == "primary":
            rules = [
                "Find your worst-placed piece and improve it",
                "Control the center before attacking flanks",
                "Don't start an attack without full development",
                "When equal, don't rush - consolidate first"
            ]
        elif priority == "secondary":
            rules = [
                "Look for piece improvements before pawn moves",
                "Don't overextend when position is equal"
            ]
        else:
            rules = [
                "Keep pieces active and coordinated"
            ]
    
    # Success criteria
    criteria = []
    
    if primary_weakness == "advantage_collapse" or priority == "primary":
        criteria.append({
            "metric": "eval_drop_after_advantage",
            "op": "<=",
            "value": 100,  # Max 1 pawn drop when winning
            "window": "after +1.5"
        })
    
    criteria.append({
        "metric": "middlegame_blunders",
        "op": "<=",
        "value": 1 if rating_band in ["600-1000", "1000-1600"] else 0,
        "window": "moves 15-40"
    })
    
    # Apply escalated rules if needed
    if is_escalated:
        rules = get_escalated_rules("middlegame", rules, domain_intensity, is_escalated)
    
    card = create_domain_card("middlegame", priority, goal, rules, criteria)
    card["escalation"] = {
        "is_escalated": is_escalated,
        "intensity": domain_intensity,
        "consecutive_misses": domain_history.get("consecutive_misses", 0)
    }
    return card


def _generate_tactics_card(
    priority: str,
    rating_band: str,
    behavior_patterns: Dict,
    intensity: int,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """Generate tactics domain card with adaptive escalation."""
    
    # Check for escalation
    domain_history = (miss_history or {}).get("tactics", {})
    is_escalated = domain_history.get("needs_escalation", False)
    domain_intensity = calculate_domain_intensity("tactics", intensity, miss_history or {})
    
    primary_weakness = behavior_patterns.get("primary_weakness")
    
    if primary_weakness == "piece_safety":
        if is_escalated and domain_intensity >= 3:
            goal = "ONE RULE: Before moving, count your hanging pieces."
        else:
            goal = "No hanging pieces. Check every piece before you move."
        
        if domain_intensity >= 2:
            rules = [
                "Before EVERY move: 'Is anything undefended?'",
                "After opponent's move: 'What is attacked now?'",
                "No piece should be defended only once",
                "CCT check: Checks, Captures, Threats"
            ]
        else:
            rules = [
                "Check all pieces are defended before moving",
                "Look for opponent's threats first",
                "Don't leave pieces on the same diagonal as enemy bishop",
                "Watch for knight forks"
            ]
    elif primary_weakness == "tactical_blindness":
        if is_escalated and domain_intensity >= 3:
            goal = "ONE RULE: Say 'checks, captures, threats' before EVERY move."
        else:
            goal = "See the tactics. CCT before every move."
        
        rules = [
            "CCT protocol: Checks, Captures, Threats",
            "Before your move: What can opponent do?",
            "Look for double attacks and pins",
            "Spend 5 extra seconds on tense positions"
        ]
    else:
        goal = "Stay alert tactically. No free pieces."
        
        if priority == "primary":
            rules = [
                "Check opponent's last move for threats",
                "Verify your move doesn't hang anything",
                "Look for forcing moves each turn",
                "CCT: Checks, Captures, Threats"
            ]
        elif priority == "secondary":
            rules = [
                "Scan for threats before moving",
                "No undefended pieces"
            ]
        else:
            rules = [
                "Basic threat awareness each move"
            ]
    
    # Success criteria
    criteria = [
        {
            "metric": "blunders",
            "op": "<=",
            "value": 1 if rating_band in ["600-1000"] else 0,
            "window": "full game"
        }
    ]
    
    if priority in ["primary", "secondary"]:
        criteria.append({
            "metric": "hung_pieces",
            "op": "==",
            "value": 0,
            "window": "full game"
        })
    
    # Apply escalated rules if needed
    if is_escalated:
        rules = get_escalated_rules("tactics", rules, domain_intensity, is_escalated)
    
    card = create_domain_card("tactics", priority, goal, rules, criteria)
    card["escalation"] = {
        "is_escalated": is_escalated,
        "intensity": domain_intensity,
        "consecutive_misses": domain_history.get("consecutive_misses", 0)
    }
    return card


def _generate_endgame_card(
    priority: str,
    rating_band: str,
    endgame_conversion_score: int,
    intensity: int,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """Generate endgame domain card with adaptive escalation."""
    
    # Check for escalation
    domain_history = (miss_history or {}).get("endgame", {})
    is_escalated = domain_history.get("needs_escalation", False)
    domain_intensity = calculate_domain_intensity("endgame", intensity, miss_history or {})
    
    if is_escalated and domain_intensity >= 3:
        goal = "ONE RULE: King to center. Immediately. Every endgame."
        rules = ["King moves toward the center as soon as queens come off"]
    elif priority == "primary" or endgame_conversion_score < 50:
        goal = "Activate king immediately. Push passed pawns."
        
        rules = [
            "King to center as soon as queens are off",
            "Rooks belong behind passed pawns",
            "Don't trade all pawns when ahead",
            "Calculate pawn races before playing"
        ]
    elif priority == "secondary":
        goal = "Convert endgame advantages cleanly."
        
        rules = [
            "Centralize king in endgames",
            "Support passed pawns with pieces"
        ]
    else:
        goal = "Basic endgame technique."
        
        rules = [
            "Activate king when queens are traded"
        ]
    
    # Success criteria
    criteria = [
        {
            "metric": "endgame_conversion",
            "op": "==",
            "value": 1,  # Boolean: converted or not
            "window": "if winning endgame entered"
        }
    ]
    
    # Apply escalated rules if needed (unless already micro-habit)
    if is_escalated and domain_intensity < 3:
        rules = get_escalated_rules("endgame", rules, domain_intensity, is_escalated)
    
    card = create_domain_card("endgame", priority, goal, rules, criteria)
    card["escalation"] = {
        "is_escalated": is_escalated,
        "intensity": domain_intensity,
        "consecutive_misses": domain_history.get("consecutive_misses", 0)
    }
    return card


def _generate_time_card(
    priority: str,
    rating_band: str,
    time_discipline_score: int,
    intensity: int,
    last_audit: Dict = None,
    miss_history: Dict = None
) -> Dict:
    """Generate time domain card with adaptive escalation."""
    
    # Check for escalation
    domain_history = (miss_history or {}).get("time", {})
    is_escalated = domain_history.get("needs_escalation", False)
    domain_intensity = calculate_domain_intensity("time", intensity, miss_history or {})
    
    if is_escalated and domain_intensity >= 3:
        goal = "ONE RULE: Never think more than 30 seconds on one move."
        rules = ["30 seconds max per move. Move, don't think."]
    elif priority == "primary" or time_discipline_score < 50:
        goal = "Manage your clock. No time-trouble blunders."
        
        rules = [
            "Use 50% of time by move 20",
            "Never drop below 30 seconds with moves left",
            "When low on time: play safe, not brilliant",
            "Pre-move obvious recaptures"
        ]
    elif priority == "secondary":
        goal = "Keep comfortable time throughout."
        
        rules = [
            "Don't spend more than 2 minutes on one move",
            "Keep 1+ minute buffer for endgame"
        ]
    else:
        goal = "Reasonable time distribution."
        
        rules = [
            "Don't flag - watch the clock"
        ]
    
    # Success criteria
    criteria = [
        {
            "metric": "time_trouble_blunders",
            "op": "==",
            "value": 0,
            "window": "last 10 moves"
        }
    ]
    
    # Apply escalated rules if needed (unless already micro-habit)
    if is_escalated and domain_intensity < 3:
        rules = get_escalated_rules("time", rules, domain_intensity, is_escalated)
    
    card = create_domain_card("time", priority, goal, rules, criteria)
    card["escalation"] = {
        "is_escalated": is_escalated,
        "intensity": domain_intensity,
        "consecutive_misses": domain_history.get("consecutive_misses", 0)
    }
    return card


# =============================================================================
# AUDIT ENGINE (DETERMINISTIC)
# =============================================================================

def audit_game_against_plan(
    plan: Dict,
    game: Dict,
    analysis: Dict,
    opening_played: str = None
) -> Dict:
    """
    Audit a game against the given plan (DETERMINISTIC).
    
    For each domain card in the plan:
    1. Evaluate success criteria
    2. Determine status: executed | partial | missed | n/a
    3. Collect evidence (move numbers, eval swings)
    4. Generate deterministic coach note
    
    Returns the plan with audit fields filled.
    """
    
    audited_plan = plan.copy()
    audited_plan["is_audited"] = True
    audited_plan["audited_against_game_id"] = game.get("game_id")
    
    sf = analysis.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white")
    
    # Determine game result
    result = game.get("result", "*")
    if user_color == "white":
        game_result = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
    else:
        game_result = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
    
    # Audit each domain
    for card in audited_plan.get("cards", []):
        domain = card.get("domain")
        
        if domain == "opening":
            _audit_opening(card, game, analysis, moves, user_color, opening_played)
        elif domain == "middlegame":
            _audit_middlegame(card, game, analysis, moves, user_color)
        elif domain == "tactics":
            _audit_tactics(card, game, analysis, moves, user_color)
        elif domain == "endgame":
            _audit_endgame(card, game, analysis, moves, user_color, game_result)
        elif domain == "time":
            _audit_time(card, game, analysis, moves, user_color)
    
    # Calculate overall execution score
    executed = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "executed")
    partial = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "partial")
    missed = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] == "missed")
    applicable = sum(1 for c in audited_plan["cards"] if c["audit"]["status"] != "n/a")
    
    audited_plan["audit_summary"] = {
        "executed": executed,
        "partial": partial,
        "missed": missed,
        "applicable": applicable,
        "score": f"{executed}/{applicable}",
        "game_result": game_result
    }
    
    return audited_plan


def _audit_opening(card, game, analysis, moves, user_color, opening_played):
    """Audit opening domain."""
    
    audit = card["audit"]
    audit["data_points"] = []
    audit["evidence"] = []
    
    # Get early moves (first 10 per side = 20 total)
    early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
    
    if not early_moves:
        audit["status"] = "n/a"
        audit["coach_note"] = "Game ended too early to evaluate opening."
        return
    
    # Calculate metrics
    user_early_moves = []
    for m in early_moves:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        if is_user_move:
            user_early_moves.append(m)
    
    max_drop = max((m.get("cp_loss", 0) for m in user_early_moves), default=0)
    early_blunders = sum(1 for m in user_early_moves if m.get("classification") == "blunder")
    avg_cp_loss = sum(m.get("cp_loss", 0) for m in user_early_moves) / len(user_early_moves) if user_early_moves else 0
    
    # Extract opening name properly
    opening_name = opening_played or _extract_opening_name(game)
    audit["data_points"].append(f"Played: {opening_name}")
    
    # Evaluate against criteria
    criteria_met = 0
    criteria_total = len(card.get("success_criteria", []))
    
    for criterion in card.get("success_criteria", []):
        metric = criterion.get("metric")
        op = criterion.get("op")
        value = criterion.get("value")
        
        if metric == "eval_drop_moves_1_10":
            actual = max_drop
            if _check_criterion(actual, op, value):
                criteria_met += 1
            else:
                # Find the worst move
                worst_move = max(user_early_moves, key=lambda m: m.get("cp_loss", 0), default=None)
                if worst_move:
                    audit["evidence"].append({
                        "move": worst_move.get("move_number"),
                        "delta": -round(worst_move.get("cp_loss", 0) / 100, 1),
                        "note": f"Dropped {round(max_drop/100, 1)} pawns"
                    })
        
        elif metric == "early_blunders":
            actual = early_blunders
            if _check_criterion(actual, op, value):
                criteria_met += 1
            else:
                blunder_moves = [m for m in user_early_moves if m.get("classification") == "blunder"]
                if blunder_moves:
                    audit["evidence"].append({
                        "move": blunder_moves[0].get("move_number"),
                        "note": "Early blunder"
                    })
    
    # Add stability data point
    if max_drop < 50:
        audit["data_points"].append("Opening stable (no big drops)")
    elif max_drop < 100:
        audit["data_points"].append(f"Minor wobble (-{round(max_drop/100, 1)})")
    else:
        audit["data_points"].append(f"Opening unstable (-{round(max_drop/100, 1)} drop)")
    
    # Determine status
    if criteria_total == 0:
        audit["status"] = "executed" if max_drop < 50 else "partial"
    elif criteria_met == criteria_total:
        audit["status"] = "executed"
    elif criteria_met > 0:
        audit["status"] = "partial"
    else:
        audit["status"] = "missed"
    
    # Coach note
    if audit["status"] == "executed":
        audit["coach_note"] = "Opening plan followed. Clean development."
    elif audit["status"] == "partial":
        audit["coach_note"] = f"Opening okay, but had a wobble ({round(max_drop/100, 1)} drop)."
    else:
        audit["coach_note"] = "Opening plan not executed. Review the early moves."


def _audit_middlegame(card, game, analysis, moves, user_color):
    """Audit middlegame domain."""
    
    audit = card["audit"]
    audit["data_points"] = []
    audit["evidence"] = []
    
    # Get middlegame moves (moves 15-40 per side = 30-80 total)
    middlegame_moves = [m for m in moves if 30 <= m.get("move_number", 0) <= 80]
    
    if len(middlegame_moves) < 5:
        audit["status"] = "n/a"
        audit["coach_note"] = "Game ended before middlegame developed."
        return
    
    user_mg_moves = []
    for m in middlegame_moves:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        if is_user_move:
            user_mg_moves.append(m)
    
    # Check for advantage positions
    advantage_positions = []
    collapses = []
    max_advantage = 0
    max_advantage_move = None
    
    for m in user_mg_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        
        if user_color == "black":
            eval_before, eval_after = -eval_before, -eval_after
        
        if eval_before > max_advantage:
            max_advantage = eval_before
            max_advantage_move = m.get("move_number")
        
        if eval_before >= 150:
            advantage_positions.append(m)
            drop = eval_before - eval_after
            if drop > 100:
                collapses.append({
                    "move": m.get("move_number"),
                    "drop": drop,
                    "from_eval": eval_before,
                    "to_eval": eval_after
                })
    
    # Middlegame blunders
    mg_blunders = sum(1 for m in user_mg_moves if m.get("classification") == "blunder")
    
    # Data points
    if max_advantage >= 150:
        audit["data_points"].append(f"Peak advantage: +{round(max_advantage/100, 1)} at move {max_advantage_move}")
    else:
        audit["data_points"].append("No significant advantage reached")
    
    if collapses:
        total_dropped = sum(c["drop"] for c in collapses)
        audit["data_points"].append(f"Gave back {round(total_dropped/100, 1)} pawns in {len(collapses)} collapse(s)")
        
        worst = max(collapses, key=lambda c: c["drop"])
        audit["evidence"].append({
            "move": worst["move"],
            "delta": -round(worst["drop"] / 100, 1),
            "note": f"+{round(worst['from_eval']/100, 1)} → +{round(worst['to_eval']/100, 1)}"
        })
    
    # Evaluate criteria
    criteria_met = 0
    criteria_total = len(card.get("success_criteria", []))
    
    for criterion in card.get("success_criteria", []):
        metric = criterion.get("metric")
        op = criterion.get("op")
        value = criterion.get("value")
        
        if metric == "eval_drop_after_advantage":
            if not collapses:
                criteria_met += 1
            else:
                max_collapse = max(c["drop"] for c in collapses)
                if _check_criterion(max_collapse, op, value):
                    criteria_met += 1
        
        elif metric == "middlegame_blunders":
            if _check_criterion(mg_blunders, op, value):
                criteria_met += 1
            else:
                blunder_move = next((m for m in user_mg_moves if m.get("classification") == "blunder"), None)
                if blunder_move:
                    audit["evidence"].append({
                        "move": blunder_move.get("move_number"),
                        "delta": -round(blunder_move.get("cp_loss", 0) / 100, 1),
                        "note": "Middlegame blunder"
                    })
    
    # Determine status
    if not advantage_positions:
        # No advantage to collapse, check blunders only
        if mg_blunders == 0:
            audit["status"] = "executed"
            audit["coach_note"] = "Middlegame clean. No clear winning chances, but no errors."
        else:
            audit["status"] = "partial"
            audit["coach_note"] = f"Had {mg_blunders} middlegame error(s). Work on tactical vigilance."
    elif criteria_total == 0:
        audit["status"] = "executed" if not collapses else "partial"
    elif criteria_met == criteria_total:
        audit["status"] = "executed"
        audit["coach_note"] = "Middlegame discipline maintained. Advantage held."
    elif criteria_met > 0:
        audit["status"] = "partial"
        audit["coach_note"] = "Had control, but let some advantage slip. Review the key moments."
    else:
        audit["status"] = "missed"
        audit["coach_note"] = "Middlegame plan not followed. You had it and gave it back."


def _audit_tactics(card, game, analysis, moves, user_color):
    """Audit tactics domain."""
    
    audit = card["audit"]
    audit["data_points"] = []
    audit["evidence"] = []
    
    sf = analysis.get("stockfish_analysis", {})
    total_blunders = sf.get("blunders", 0)
    total_mistakes = sf.get("mistakes", 0)
    
    # Find hung pieces (blunders with cp_loss >= 300)
    hung_pieces = 0
    worst_blunder = None
    worst_blunder_loss = 0
    
    for m in moves:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move:
            if m.get("classification") == "blunder":
                cp_loss = m.get("cp_loss", 0)
                if cp_loss >= 300:
                    hung_pieces += 1
                if cp_loss > worst_blunder_loss:
                    worst_blunder = m
                    worst_blunder_loss = cp_loss
    
    # Data points
    audit["data_points"].append(f"Blunders: {total_blunders}")
    if hung_pieces > 0:
        audit["data_points"].append(f"Hung pieces: {hung_pieces}")
    
    # Evidence
    if worst_blunder:
        audit["evidence"].append({
            "move": worst_blunder.get("move_number"),
            "delta": -round(worst_blunder_loss / 100, 1),
            "note": "Worst blunder"
        })
    
    # Evaluate criteria
    criteria_met = 0
    criteria_total = len(card.get("success_criteria", []))
    
    for criterion in card.get("success_criteria", []):
        metric = criterion.get("metric")
        op = criterion.get("op")
        value = criterion.get("value")
        
        if metric == "blunders":
            if _check_criterion(total_blunders, op, value):
                criteria_met += 1
        
        elif metric == "hung_pieces":
            if _check_criterion(hung_pieces, op, value):
                criteria_met += 1
    
    # Determine status
    if criteria_total == 0:
        audit["status"] = "executed" if total_blunders == 0 else "partial"
    elif criteria_met == criteria_total:
        audit["status"] = "executed"
        audit["coach_note"] = "Tactical protocol followed. Clean game."
    elif criteria_met > 0:
        audit["status"] = "partial"
        audit["coach_note"] = f"Some tactical awareness shown, but {total_blunders} blunder(s) slipped through."
    else:
        audit["status"] = "missed"
        audit["coach_note"] = "Tactical protocol not followed. Review the blunders carefully."


def _audit_endgame(card, game, analysis, moves, user_color, game_result):
    """Audit endgame domain."""
    
    audit = card["audit"]
    audit["data_points"] = []
    audit["evidence"] = []
    
    # Check if endgame reached (moves > 60)
    endgame_moves = [m for m in moves if m.get("move_number", 0) > 60]
    
    if len(endgame_moves) < 5:
        audit["status"] = "n/a"
        audit["coach_note"] = "No endgame reached. Plan not applicable."
        return
    
    # Check if user had winning endgame
    had_winning_endgame = False
    endgame_eval = 0
    
    for m in endgame_moves[:5]:
        eval_before = m.get("eval_before", 0)
        if user_color == "black":
            eval_before = -eval_before
        if eval_before >= 100:
            had_winning_endgame = True
            endgame_eval = eval_before
            break
    
    # Conversion
    converted = game_result == "win"
    
    # Data points
    if had_winning_endgame:
        audit["data_points"].append(f"Entered endgame with +{round(endgame_eval/100, 1)}")
        audit["data_points"].append(f"Conversion: {'Yes' if converted else 'No'}")
    else:
        audit["data_points"].append("No winning endgame position")
    
    # Check for endgame blunders
    endgame_blunders = []
    for m in endgame_moves:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move and m.get("classification") == "blunder":
            endgame_blunders.append(m)
    
    if endgame_blunders:
        worst = max(endgame_blunders, key=lambda m: m.get("cp_loss", 0))
        audit["evidence"].append({
            "move": worst.get("move_number"),
            "delta": -round(worst.get("cp_loss", 0) / 100, 1),
            "note": "Endgame blunder"
        })
    
    # Determine status
    if not had_winning_endgame:
        if len(endgame_blunders) == 0:
            audit["status"] = "executed"
            audit["coach_note"] = "Endgame played solidly. No errors."
        else:
            audit["status"] = "partial"
            audit["coach_note"] = f"Made {len(endgame_blunders)} error(s) in endgame."
    else:
        if converted:
            audit["status"] = "executed"
            audit["coach_note"] = "Winning endgame converted. Well done."
        else:
            audit["status"] = "missed"
            audit["coach_note"] = f"Had +{round(endgame_eval/100, 1)} in endgame but didn't convert. Review technique."


def _audit_time(card, game, analysis, moves, user_color):
    """Audit time domain."""
    
    audit = card["audit"]
    audit["data_points"] = []
    audit["evidence"] = []
    
    # Check for late-game blunders (proxy for time trouble)
    late_moves = [m for m in moves if m.get("move_number", 0) > 50]
    
    if not late_moves:
        audit["status"] = "n/a"
        audit["coach_note"] = "Game ended early. Time plan not applicable."
        return
    
    late_blunders = []
    for m in late_moves:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move and m.get("classification") == "blunder":
            late_blunders.append(m)
    
    # Data points
    audit["data_points"].append(f"Late-game blunders: {len(late_blunders)}")
    
    # Evidence
    if late_blunders:
        worst = max(late_blunders, key=lambda m: m.get("cp_loss", 0))
        audit["evidence"].append({
            "move": worst.get("move_number"),
            "delta": -round(worst.get("cp_loss", 0) / 100, 1),
            "note": "Possible time pressure error"
        })
    
    # Evaluate criteria
    criteria_met = 0
    criteria_total = len(card.get("success_criteria", []))
    
    for criterion in card.get("success_criteria", []):
        metric = criterion.get("metric")
        op = criterion.get("op")
        value = criterion.get("value")
        
        if metric == "time_trouble_blunders":
            if _check_criterion(len(late_blunders), op, value):
                criteria_met += 1
    
    # Determine status
    if criteria_total == 0:
        audit["status"] = "executed" if len(late_blunders) == 0 else "partial"
    elif criteria_met == criteria_total:
        audit["status"] = "executed"
        audit["coach_note"] = "Time managed well. No late-game disasters."
    elif len(late_blunders) <= 1:
        audit["status"] = "partial"
        audit["coach_note"] = "Minor time issue. One late error."
    else:
        audit["status"] = "missed"
        audit["coach_note"] = f"{len(late_blunders)} errors in late game. Likely time pressure."


def _check_criterion(actual: float, op: str, expected: float) -> bool:
    """Check if actual value meets criterion."""
    if op == "<=":
        return actual <= expected
    elif op == ">=":
        return actual >= expected
    elif op == "==":
        return actual == expected
    elif op == "<":
        return actual < expected
    elif op == ">":
        return actual > expected
    return False


# =============================================================================
# MAIN API FUNCTIONS
# =============================================================================

async def get_or_generate_plan(db, user_id: str, force_new: bool = False) -> Dict:
    """
    Get current active plan or generate a new one.
    
    This is called when user visits Focus page.
    
    Adaptive Escalation:
    - Fetches recent audits to calculate miss history
    - Passes miss history to plan generator for adaptive intensity
    """
    
    # Check for existing active plan
    if not force_new:
        existing_plan = await db.user_plans.find_one(
            {"user_id": user_id, "is_active": True, "is_audited": False},
            {"_id": 0},
            sort=[("generated_at", -1)]
        )
        
        if existing_plan:
            return existing_plan
    
    # Need to generate new plan
    # 1. Get user data
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    # 2. Get all games and analyses
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(50)
    
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # 3. Calculate all inputs
    rating_band = _get_rating_band(user.get("rating", 1200) if user else 1200)
    fundamentals = calculate_fundamentals_profile(analyses, games)
    behavior_patterns = detect_behavior_patterns(analyses, games)
    opening_stability = calculate_opening_stability(analyses, games)
    
    # 4. Get recent audits for miss history (adaptive escalation)
    recent_audits = await db.user_plans.find(
        {"user_id": user_id, "is_audited": True},
        {"_id": 0}
    ).sort("generated_at", -1).limit(10).to_list(10)
    
    # Calculate miss history from recent audits
    miss_history = get_domain_miss_history(recent_audits)
    
    # 5. Get last audit if exists
    last_audit = recent_audits[0] if recent_audits else None
    
    # 6. Generate new plan with adaptive escalation
    new_plan = generate_next_plan(
        user_id=user_id,
        rating_band=rating_band,
        fundamentals=fundamentals,
        behavior_patterns=behavior_patterns,
        opening_stability=opening_stability,
        last_audit=last_audit,
        miss_history=miss_history
    )
    
    # 7. Store the plan (insert modifies dict by adding _id)
    await db.user_plans.insert_one(new_plan)
    
    # 8. Mark previous active plans as inactive
    await db.user_plans.update_many(
        {"user_id": user_id, "is_active": True, "plan_id": {"$ne": new_plan["plan_id"]}},
        {"$set": {"is_active": False}}
    )
    
    # 9. Re-fetch to get clean document without _id
    clean_plan = await db.user_plans.find_one(
        {"plan_id": new_plan["plan_id"]},
        {"_id": 0}
    )
    
    return clean_plan


async def get_latest_audit(db, user_id: str) -> Optional[Dict]:
    """Get the most recent audited plan."""
    
    audit = await db.user_plans.find_one(
        {"user_id": user_id, "is_audited": True},
        {"_id": 0},
        sort=[("generated_at", -1)]
    )
    
    return audit


async def audit_game_and_update_plan(db, user_id: str, game_id: str) -> Dict:
    """
    Audit a specific game against the user's active plan.
    
    This should be called after a game is analyzed.
    """
    
    # 1. Get the active plan
    active_plan = await db.user_plans.find_one(
        {"user_id": user_id, "is_active": True, "is_audited": False},
        {"_id": 0}
    )
    
    if not active_plan:
        # No plan to audit against, generate one first
        active_plan = await get_or_generate_plan(db, user_id, force_new=True)
    
    # 2. Get the game and analysis
    game = await db.games.find_one({"game_id": game_id, "user_id": user_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user_id}, {"_id": 0})
    
    if not game or not analysis:
        return {"error": "Game or analysis not found"}
    
    # 3. Audit the game
    opening_played = game.get("opening")
    audited_plan = audit_game_against_plan(active_plan, game, analysis, opening_played)
    
    # 4. Update the plan in database
    await db.user_plans.update_one(
        {"plan_id": active_plan["plan_id"]},
        {"$set": audited_plan}
    )
    
    # 5. Generate new plan for next game
    new_plan = await get_or_generate_plan(db, user_id, force_new=True)
    
    return {
        "audited_plan": audited_plan,
        "new_plan": new_plan
    }


def _get_rating_band(rating: int) -> str:
    """Get rating band from numeric rating."""
    if rating < 1000:
        return "600-1000"
    elif rating < 1600:
        return "1000-1600"
    elif rating < 2000:
        return "1600-2000"
    else:
        return "2000+"
