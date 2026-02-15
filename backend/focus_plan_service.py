"""
Focus Plan Service - Deterministic Personalized Coaching System
================================================================

This service implements a GM-style coaching system that:
1. Computes Cost Scores per coaching bucket from last N games
2. Selects Primary/Secondary focus deterministically
3. Generates personalized opening recommendations
4. Creates daily missions with positions from user's own games
5. Tracks active training time (15 min goal)

Core Philosophy:
- Same user + same inputs = same plan (deterministic)
- Different users + different inputs = different plan (personalized)
- Rating band gates (different advice by rating)
- All computed from user's actual game data

Coaching Buckets:
1. PIECE_SAFETY - Hanging pieces (cp_loss >= 300)
2. THREAT_AWARENESS - Missed opponent threats
3. TACTICAL_EXECUTION - Missed tactics for self
4. ADVANTAGE_DISCIPLINE - Fails to convert when ahead
5. OPENING_STABILITY - Bad first 10-12 moves
6. TIME_DISCIPLINE - Blunders in late game (proxy for time trouble)
7. ENDGAME_FUNDAMENTALS - Conversion failures in simplified positions

Cost Score Formula:
CostScore(bucket) = Σ(EvalDrop × ContextWeight × SeverityWeight) 
                  + FrequencyWeight × count(events)
                  + InstabilityBoost (if events happen in winning positions)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Analysis window
DEFAULT_GAME_WINDOW = 25
MIN_GAMES_REQUIRED = 5

# Phase definitions (by half-move number)
OPENING_END = 20      # First 10 moves per side
MIDDLEGAME_END = 60   # Moves 11-30 per side
# After 60 = Endgame

# Thresholds
WINNING_THRESHOLD = 150      # +1.5 pawns = winning
BLUNDER_THRESHOLD = 200      # 2 pawns = blunder
SIGNIFICANT_DROP = 100       # 1 pawn = significant
HANGING_PIECE_THRESHOLD = 300  # 3 pawns = hanging piece

# Context weights for cost scoring
CONTEXT_WEIGHTS = {
    "winning": 1.4,    # Mistakes when ahead hurt more
    "equal": 1.0,
    "losing": 0.8,     # Mistakes when losing are more understandable
}

# =============================================================================
# RATING BAND DEFINITIONS
# =============================================================================

RATING_BANDS = {
    "beginner": {
        "min": 0, "max": 899,
        "label": "<900",
        "allowed_buckets": ["PIECE_SAFETY", "OPENING_STABILITY"],
        "primary_advice": "Piece safety + opening principles",
        "rules": {
            "PIECE_SAFETY": ["Before moving, ask: Is my piece safe on the new square?", "Count attackers vs defenders"],
            "OPENING_STABILITY": ["Develop knights and bishops first", "Castle before move 10"],
        }
    },
    "developing": {
        "min": 900, "max": 1399,
        "label": "900-1400",
        "allowed_buckets": ["PIECE_SAFETY", "THREAT_AWARENESS", "TACTICAL_EXECUTION", "ADVANTAGE_DISCIPLINE", "OPENING_STABILITY"],
        "primary_advice": "Threat awareness + tactics + advantage conversion",
        "rules": {
            "PIECE_SAFETY": ["Check all pieces after opponent's move", "Don't leave pieces undefended"],
            "THREAT_AWARENESS": ["After opponent moves, ask: What is the threat?", "CCT: Checks, Captures, Threats"],
            "TACTICAL_EXECUTION": ["Look for forcing moves: checks, captures, threats", "Calculate 2 moves ahead minimum"],
            "ADVANTAGE_DISCIPLINE": ["When ahead, trade pieces", "Don't give counterplay when winning"],
            "OPENING_STABILITY": ["Stick to one opening as White", "Have a plan vs 1.e4 and 1.d4"],
        }
    },
    "intermediate": {
        "min": 1400, "max": 1799,
        "label": "1400-1800",
        "allowed_buckets": ["THREAT_AWARENESS", "TACTICAL_EXECUTION", "ADVANTAGE_DISCIPLINE", "OPENING_STABILITY", "ENDGAME_FUNDAMENTALS"],
        "primary_advice": "Calculation depth + positional decisions + endgames",
        "rules": {
            "THREAT_AWARENESS": ["Calculate opponent's best response", "Consider prophylaxis"],
            "TACTICAL_EXECUTION": ["Calculate 3-4 moves deep in tactical positions", "Verify your calculation before playing"],
            "ADVANTAGE_DISCIPLINE": ["Simplify when ahead", "Improve worst piece when equal"],
            "OPENING_STABILITY": ["Know 8-10 moves of your main lines", "Understand the plans, not just moves"],
            "ENDGAME_FUNDAMENTALS": ["Activate king immediately in endgame", "Create passed pawns"],
        }
    },
    "advanced": {
        "min": 1800, "max": 9999,
        "label": "1800+",
        "allowed_buckets": ["TACTICAL_EXECUTION", "ADVANTAGE_DISCIPLINE", "OPENING_STABILITY", "ENDGAME_FUNDAMENTALS", "TIME_DISCIPLINE"],
        "primary_advice": "Opening refinement + targeted endgame/tactical themes",
        "rules": {
            "TACTICAL_EXECUTION": ["Look for hidden resources in complex positions", "Evaluate structural consequences"],
            "ADVANTAGE_DISCIPLINE": ["Convert with precision - calculate to mate/win", "Avoid time pressure in winning positions"],
            "OPENING_STABILITY": ["Deepen main repertoire lines", "Prepare specific anti-systems"],
            "ENDGAME_FUNDAMENTALS": ["Know theoretical endgames cold", "Technique in R+P endgames"],
            "TIME_DISCIPLINE": ["Allocate time budget by phase", "Move faster in known positions"],
        }
    },
}


def get_rating_band(rating: int) -> Dict:
    """Get the rating band configuration for a given rating."""
    for band_name, band_data in RATING_BANDS.items():
        if band_data["min"] <= rating <= band_data["max"]:
            return {"name": band_name, **band_data}
    return {"name": "developing", **RATING_BANDS["developing"]}


# =============================================================================
# PHASE DETECTION
# =============================================================================

def get_move_phase(move_number: int) -> str:
    """Determine game phase from move number (half-moves)."""
    if move_number <= OPENING_END:
        return "opening"
    elif move_number <= MIDDLEGAME_END:
        return "middlegame"
    else:
        return "endgame"


def tag_moves_with_phase(moves: List[Dict]) -> List[Dict]:
    """Add phase tag to each move."""
    for m in moves:
        m["phase"] = get_move_phase(m.get("move_number", 0))
    return moves


# =============================================================================
# COST SCORE COMPUTATION
# =============================================================================

def get_position_context(eval_before: int) -> str:
    """Determine context (winning/equal/losing) from evaluation."""
    if eval_before >= WINNING_THRESHOLD:
        return "winning"
    elif eval_before <= -WINNING_THRESHOLD:
        return "losing"
    return "equal"


def compute_bucket_costs(analyses: List[Dict], games: List[Dict], rating: int) -> Dict[str, Dict]:
    """
    Compute Cost Score for each coaching bucket.
    
    Formula:
    CostScore(bucket) = Σ(EvalDrop × ContextWeight × SeverityWeight)
                      + FrequencyWeight × count(events)
                      + InstabilityBoost (if events in winning positions)
    
    Returns dict with bucket_id -> {score, events, example_positions}
    """
    band = get_rating_band(rating)
    allowed_buckets = band["allowed_buckets"]
    
    # Initialize buckets
    buckets = {
        "PIECE_SAFETY": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "THREAT_AWARENESS": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "TACTICAL_EXECUTION": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "ADVANTAGE_DISCIPLINE": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "OPENING_STABILITY": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "TIME_DISCIPLINE": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
        "ENDGAME_FUNDAMENTALS": {"score": 0, "events": [], "example_positions": [], "games_affected": set()},
    }
    
    # Build game map for result lookup
    game_map = {g.get("game_id"): g for g in games}
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        game = game_map.get(game_id, {})
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        moves = tag_moves_with_phase(moves)
        
        for m in moves:
            cp_loss = m.get("cp_loss", 0)
            eval_before = m.get("eval_before", 0)
            evaluation = m.get("evaluation", "")
            phase = m.get("phase", "middlegame")
            move_number = m.get("move_number", 0)
            
            # Skip minor inaccuracies
            if cp_loss < 50:
                continue
            
            context = get_position_context(eval_before)
            context_weight = CONTEXT_WEIGHTS.get(context, 1.0)
            
            # Instability boost: mistakes when winning are extra costly
            instability_boost = 1.3 if context == "winning" and cp_loss >= SIGNIFICANT_DROP else 1.0
            
            # Base score for this event
            event_score = cp_loss * context_weight * instability_boost
            
            event_data = {
                "game_id": game_id,
                "move_number": move_number,
                "phase": phase,
                "cp_loss": cp_loss,
                "eval_before": eval_before,
                "context": context,
                "fen": m.get("fen_before"),
                "fen_after": m.get("fen_after"),
                "move": m.get("move"),
                "best_move": m.get("best_move"),
                "threat": m.get("threat"),
            }
            
            # === CLASSIFY INTO BUCKETS ===
            
            # 1. PIECE_SAFETY: Large material loss (hanging piece)
            if cp_loss >= HANGING_PIECE_THRESHOLD:
                buckets["PIECE_SAFETY"]["score"] += event_score * 1.2
                buckets["PIECE_SAFETY"]["events"].append(event_data)
                buckets["PIECE_SAFETY"]["games_affected"].add(game_id)
            
            # 2. OPENING_STABILITY: Mistakes in opening phase
            if phase == "opening" and cp_loss >= SIGNIFICANT_DROP:
                buckets["OPENING_STABILITY"]["score"] += event_score
                buckets["OPENING_STABILITY"]["events"].append(event_data)
                buckets["OPENING_STABILITY"]["games_affected"].add(game_id)
            
            # 3. ADVANTAGE_DISCIPLINE: Mistakes when winning
            if context == "winning" and cp_loss >= SIGNIFICANT_DROP:
                buckets["ADVANTAGE_DISCIPLINE"]["score"] += event_score * 1.4
                buckets["ADVANTAGE_DISCIPLINE"]["events"].append(event_data)
                buckets["ADVANTAGE_DISCIPLINE"]["games_affected"].add(game_id)
            
            # 4. TACTICAL_EXECUTION: Blunders (missed winning tactics or hung pieces)
            if evaluation in ["blunder", "mistake"] and cp_loss >= BLUNDER_THRESHOLD:
                buckets["TACTICAL_EXECUTION"]["score"] += event_score
                buckets["TACTICAL_EXECUTION"]["events"].append(event_data)
                buckets["TACTICAL_EXECUTION"]["games_affected"].add(game_id)
            
            # 5. THREAT_AWARENESS: Opponent had a threat that was missed
            if m.get("threat") and cp_loss >= SIGNIFICANT_DROP:
                buckets["THREAT_AWARENESS"]["score"] += event_score * 0.9
                buckets["THREAT_AWARENESS"]["events"].append(event_data)
                buckets["THREAT_AWARENESS"]["games_affected"].add(game_id)
            
            # 6. TIME_DISCIPLINE: Late-game blunders (proxy for time trouble)
            if move_number > 40 and evaluation in ["blunder", "mistake"]:
                buckets["TIME_DISCIPLINE"]["score"] += event_score * 0.8
                buckets["TIME_DISCIPLINE"]["events"].append(event_data)
                buckets["TIME_DISCIPLINE"]["games_affected"].add(game_id)
            
            # 7. ENDGAME_FUNDAMENTALS: Mistakes in endgame
            if phase == "endgame" and cp_loss >= SIGNIFICANT_DROP:
                buckets["ENDGAME_FUNDAMENTALS"]["score"] += event_score
                buckets["ENDGAME_FUNDAMENTALS"]["events"].append(event_data)
                buckets["ENDGAME_FUNDAMENTALS"]["games_affected"].add(game_id)
    
    # Compute final scores with frequency weighting
    total_games = len(analyses) if analyses else 1
    
    for bucket_id, bucket in buckets.items():
        # Frequency weight: more affected games = higher priority
        frequency_rate = len(bucket["games_affected"]) / total_games
        bucket["frequency_rate"] = round(frequency_rate, 3)
        bucket["games_affected_count"] = len(bucket["games_affected"])
        
        # Add frequency bonus to score
        bucket["score"] += frequency_rate * 1000  # Frequency bonus
        bucket["score"] = round(bucket["score"], 2)
        
        # Get top example positions (sorted by cp_loss)
        sorted_events = sorted(bucket["events"], key=lambda x: x["cp_loss"], reverse=True)
        bucket["example_positions"] = sorted_events[:5]
        
        # Convert set to count for JSON serialization
        bucket["games_affected"] = len(bucket["games_affected"])
        
        # Filter by rating band
        bucket["allowed_for_rating"] = bucket_id in allowed_buckets
    
    return buckets


def select_primary_and_secondary_focus(bucket_costs: Dict[str, Dict], rating: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Select Primary and Secondary focus from bucket costs.
    
    Rules:
    - Primary = highest cost score among allowed buckets
    - Secondary = second highest IF score >= 70% of primary AND rating allows training both
    """
    band = get_rating_band(rating)
    allowed_buckets = band["allowed_buckets"]
    
    # Filter to allowed buckets and sort by score
    eligible = [
        {"id": bucket_id, **data}
        for bucket_id, data in bucket_costs.items()
        if bucket_id in allowed_buckets and data["score"] > 0
    ]
    
    if not eligible:
        # Fallback to default for rating band
        default_bucket = allowed_buckets[0] if allowed_buckets else "PIECE_SAFETY"
        return {
            "id": default_bucket,
            "score": 0,
            "reason": f"Default focus for {band['label']} players",
            "example_positions": [],
        }, None
    
    # Sort by score descending
    eligible.sort(key=lambda x: x["score"], reverse=True)
    
    primary = eligible[0]
    primary["reason"] = f"Highest cost area ({primary['games_affected']} games affected)"
    
    # Check for secondary
    secondary = None
    if len(eligible) >= 2:
        candidate = eligible[1]
        if candidate["score"] >= primary["score"] * 0.7:
            secondary = candidate
            secondary["reason"] = f"Secondary priority ({candidate['games_affected']} games affected)"
    
    return primary, secondary


# =============================================================================
# OPENING SELECTION
# =============================================================================

def compute_opening_stats(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Compute opening statistics for personalized selection.
    
    For each opening:
    - Usage% (how often played)
    - Stability score (accuracy in first 10-12 moves)
    - Result score (win rate)
    """
    # Build analysis map
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    white_openings = {}
    black_openings = {}
    black_vs_e4 = {}
    black_vs_d4 = {}
    
    for game in games:
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id)
        if not analysis:
            continue
        
        user_color = game.get("user_color", "white")
        opening_name = _extract_opening_name(game)
        first_move = _extract_first_move(game)
        
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        early_moves = [m for m in moves if m.get("move_number", 0) <= 20]
        
        if not early_moves:
            continue
        
        # Calculate stability for this game
        max_drop = max((m.get("cp_loss", 0) for m in early_moves), default=0)
        avg_cp = sum(m.get("cp_loss", 0) for m in early_moves) / len(early_moves) if early_moves else 0
        
        stability = 100
        stability -= min(30, max_drop / 10)
        stability -= min(20, avg_cp)
        stability = max(0, stability)
        
        # Result score
        result = game.get("result", "")
        user_won = (user_color == "white" and result == "1-0") or (user_color == "black" and result == "0-1")
        user_drew = result == "1/2-1/2"
        result_score = 1.0 if user_won else (0.5 if user_drew else 0.0)
        
        # Store by color
        target = white_openings if user_color == "white" else black_openings
        if opening_name not in target:
            target[opening_name] = {"games": 0, "stability_scores": [], "result_scores": []}
        target[opening_name]["games"] += 1
        target[opening_name]["stability_scores"].append(stability)
        target[opening_name]["result_scores"].append(result_score)
        
        # Track black responses to specific first moves
        if user_color == "black":
            if first_move in ["e4", "e2e4"]:
                if opening_name not in black_vs_e4:
                    black_vs_e4[opening_name] = {"games": 0, "stability_scores": [], "result_scores": []}
                black_vs_e4[opening_name]["games"] += 1
                black_vs_e4[opening_name]["stability_scores"].append(stability)
                black_vs_e4[opening_name]["result_scores"].append(result_score)
            elif first_move in ["d4", "d2d4"]:
                if opening_name not in black_vs_d4:
                    black_vs_d4[opening_name] = {"games": 0, "stability_scores": [], "result_scores": []}
                black_vs_d4[opening_name]["games"] += 1
                black_vs_d4[opening_name]["stability_scores"].append(stability)
                black_vs_d4[opening_name]["result_scores"].append(result_score)
    
    return {
        "white": _select_best_opening(white_openings),
        "black": _select_best_opening(black_openings),
        "black_vs_e4": _select_best_opening(black_vs_e4),
        "black_vs_d4": _select_best_opening(black_vs_d4),
    }


def _select_best_opening(opening_stats: Dict) -> Optional[Dict]:
    """Select best opening based on usage and stability."""
    if not opening_stats:
        return None
    
    # Need at least 2 games with an opening
    eligible = {name: data for name, data in opening_stats.items() if data["games"] >= 2}
    
    if not eligible:
        # Fall back to most played
        most_played = max(opening_stats.items(), key=lambda x: x[1]["games"])
        return {
            "name": most_played[0],
            "games": most_played[1]["games"],
            "avg_stability": round(sum(most_played[1]["stability_scores"]) / len(most_played[1]["stability_scores"]), 1) if most_played[1]["stability_scores"] else 50,
            "win_rate": round(sum(most_played[1]["result_scores"]) / len(most_played[1]["result_scores"]) * 100, 1) if most_played[1]["result_scores"] else 50,
            "recommendation": "Keep playing to build experience",
        }
    
    # Score each opening: usage * 0.3 + stability * 0.5 + result * 0.2
    total_games = sum(d["games"] for d in eligible.values())
    
    best = None
    best_score = -1
    
    for name, data in eligible.items():
        usage_pct = data["games"] / total_games if total_games > 0 else 0
        avg_stability = sum(data["stability_scores"]) / len(data["stability_scores"]) if data["stability_scores"] else 50
        avg_result = sum(data["result_scores"]) / len(data["result_scores"]) if data["result_scores"] else 0.5
        
        composite_score = (usage_pct * 30) + (avg_stability * 0.5) + (avg_result * 20)
        
        if composite_score > best_score:
            best_score = composite_score
            best = {
                "name": name,
                "games": data["games"],
                "usage_pct": round(usage_pct * 100, 1),
                "avg_stability": round(avg_stability, 1),
                "win_rate": round(avg_result * 100, 1),
            }
    
    if best:
        # Add recommendation
        if best["avg_stability"] >= 70:
            best["recommendation"] = "Working well - keep it"
        elif best["usage_pct"] >= 40:
            best["recommendation"] = "High usage but unstable - focus here"
        else:
            best["recommendation"] = "Consider exploring more"
    
    return best


def _extract_opening_name(game: Dict) -> str:
    """Extract opening family name from game."""
    import re
    
    opening = game.get("opening", "")
    pgn = game.get("pgn", "")
    
    # Try multiple sources in order of preference
    if not opening and pgn:
        # 1. Try [Opening "..."] tag
        match = re.search(r'\[Opening "([^"]+)"\]', pgn)
        if match:
            opening = match.group(1)
        
        # 2. Try ECOUrl (Chess.com format) - more detailed
        if not opening:
            eco_url_match = re.search(r'\[ECOUrl "[^"]*openings/([^"]+)"\]', pgn)
            if eco_url_match:
                # Parse URL path like "Scandinavian-Defense-Mieses-Kotrc-Main-Line-4.Nf3-Nf6-5.Bc4"
                url_path = eco_url_match.group(1)
                # Take first part before move numbers (4.Nf3 etc)
                parts = url_path.split("-")
                name_parts = []
                for p in parts:
                    if re.match(r'^\d+\.', p):  # Stop at move numbers like "4.Nf3"
                        break
                    name_parts.append(p)
                if name_parts:
                    opening = " ".join(name_parts)
        
        # 3. Try ECO code and map to opening name
        if not opening:
            eco_match = re.search(r'\[ECO "([A-E]\d{2})"\]', pgn)
            if eco_match:
                eco = eco_match.group(1)
                opening = _eco_to_opening_name(eco)
    
    if not opening:
        return "Unknown"
    
    # Extract family name (clean up variations)
    family = opening.split(":")[0].split(",")[0].strip()
    
    # Standardize common openings
    families = {
        "sicilian": "Sicilian Defense",
        "french": "French Defense",
        "caro": "Caro-Kann Defense",
        "caro-kann": "Caro-Kann Defense",
        "italian": "Italian Game",
        "ruy": "Ruy Lopez",
        "spanish": "Ruy Lopez",
        "queen's gambit": "Queen's Gambit",
        "queens gambit": "Queen's Gambit",
        "king's indian": "King's Indian Defense",
        "kings indian": "King's Indian Defense",
        "english": "English Opening",
        "scandinavian": "Scandinavian Defense",
        "pirc": "Pirc Defense",
        "london": "London System",
        "slav": "Slav Defense",
        "dutch": "Dutch Defense",
        "nimzo": "Nimzo-Indian Defense",
        "grunfeld": "Grünfeld Defense",
        "benoni": "Benoni Defense",
        "alekhine": "Alekhine Defense",
        "petrov": "Petrov Defense",
        "petroff": "Petrov Defense",
        "philidor": "Philidor Defense",
        "scotch": "Scotch Game",
        "vienna": "Vienna Game",
        "bishop": "Bishop's Opening",
        "kings pawn": "King's Pawn Opening",
        "queens pawn": "Queen's Pawn Opening",
        "center game": "Center Game",
        "danish gambit": "Danish Gambit",
        "smith morra": "Smith-Morra Gambit",
        "evan": "Evans Gambit",
    }
    
    lower_opening = opening.lower()
    for key, standard_name in families.items():
        if key in lower_opening:
            return standard_name
    
    return family[:40] if len(family) > 40 else family


def _extract_first_move(game: Dict) -> str:
    """Extract opponent's first move (for black responses)."""
    pgn = game.get("pgn", "")
    # Simple extraction: find first move after 1.
    import re
    match = re.search(r'1\.\s*([a-h1-8KQRBNP]+)', pgn)
    if match:
        return match.group(1).lower()
    return ""


# =============================================================================
# POSITION SELECTION FOR MISSIONS
# =============================================================================

def select_mission_positions(bucket_costs: Dict[str, Dict], primary_focus: Dict, analyses: List[Dict]) -> Dict:
    """
    Select positions for daily mission based on primary focus.
    
    Returns:
    - opening_positions: 3 positions from opening phase
    - threat_positions: 5 positions where threat awareness was needed
    - turning_points: Top 3 biggest eval swings for guided replay
    """
    primary_id = primary_focus.get("id", "TACTICAL_EXECUTION")
    
    # Get events from the primary bucket
    primary_bucket = bucket_costs.get(primary_id, {})
    primary_events = primary_bucket.get("events", [])[:10]
    
    # Opening positions (from opening stability bucket)
    opening_bucket = bucket_costs.get("OPENING_STABILITY", {})
    opening_events = opening_bucket.get("events", [])
    opening_positions = [
        {
            "position_id": f"op_{i}",
            "fen": e["fen"],
            "fen_after": e.get("fen_after"),
            "game_id": e["game_id"],
            "move_number": e["move_number"],
            "cp_loss": e["cp_loss"],
            "your_move": e["move"],
            "best_move": e["best_move"],
        }
        for i, e in enumerate(opening_events[:5])
        if e.get("fen")
    ]
    
    # Threat positions (from threat awareness bucket)
    threat_bucket = bucket_costs.get("THREAT_AWARENESS", {})
    threat_events = threat_bucket.get("events", [])
    threat_positions = [
        {
            "position_id": f"th_{i}",
            "fen": e["fen"],
            "fen_after": e.get("fen_after"),
            "game_id": e["game_id"],
            "move_number": e["move_number"],
            "threat": e.get("threat"),
            "cp_loss": e["cp_loss"],
            "your_move": e["move"],
            "best_move": e["best_move"],
        }
        for i, e in enumerate(threat_events[:7])
        if e.get("fen")
    ]
    
    # Turning points: biggest eval swings across all games
    all_events = []
    for bucket in bucket_costs.values():
        all_events.extend(bucket.get("events", []))
    
    # Sort by cp_loss and get top turning points
    sorted_events = sorted(all_events, key=lambda x: x["cp_loss"], reverse=True)
    seen_games = set()
    turning_points = []
    
    for e in sorted_events:
        if e["game_id"] not in seen_games and e.get("fen"):
            turning_points.append({
                "turning_point_id": f"tp_{len(turning_points)}",
                "fen": e["fen"],
                "fen_after": e.get("fen_after"),
                "game_id": e["game_id"],
                "move_number": e["move_number"],
                "cp_loss": e["cp_loss"],
                "phase": e["phase"],
                "context": e["context"],
                "your_move": e["move"],
                "best_move": e["best_move"],
            })
            seen_games.add(e["game_id"])
            if len(turning_points) >= 5:
                break
    
    # Primary focus specific positions
    focus_positions = [
        {
            "position_id": f"focus_{i}",
            "fen": e["fen"],
            "fen_after": e.get("fen_after"),
            "game_id": e["game_id"],
            "move_number": e["move_number"],
            "cp_loss": e["cp_loss"],
            "your_move": e["move"],
            "best_move": e["best_move"],
            "bucket": primary_id,
        }
        for i, e in enumerate(primary_events[:5])
        if e.get("fen")
    ]
    
    return {
        "opening_positions": opening_positions[:3],
        "threat_positions": threat_positions[:5],
        "turning_points": turning_points[:3],
        "focus_positions": focus_positions[:5],
    }


# =============================================================================
# COMPUTE RATINGS DATA
# =============================================================================

def compute_rating_stats(user: Dict, games: List[Dict]) -> Dict:
    """Compute stable rating, peak rating, and gap."""
    current_rating = user.get("rating", 1200)
    
    # Get rating history from games if available
    ratings = [current_rating]
    for game in games[:50]:  # Last 50 games
        if game.get("user_rating"):
            ratings.append(game["user_rating"])
    
    if len(ratings) < 3:
        return {
            "current": current_rating,
            "stable": current_rating,
            "peak": current_rating,
            "gap": 0,
        }
    
    # Stable = median of recent ratings
    sorted_ratings = sorted(ratings)
    stable = sorted_ratings[len(sorted_ratings) // 2]
    
    # Peak = max rating
    peak = max(ratings)
    
    # Gap = peak - stable
    gap = peak - stable
    
    return {
        "current": current_rating,
        "stable": stable,
        "peak": peak,
        "gap": gap,
    }


# =============================================================================
# GENERATE FOCUS PLAN JSON
# =============================================================================

def generate_deterministic_plan_id(user_id: str, week_start: str, inputs_hash: str) -> str:
    """Generate a deterministic plan ID based on user and inputs."""
    combined = f"{user_id}_{week_start}_{inputs_hash}"
    return f"focus_{hashlib.md5(combined.encode()).hexdigest()[:16]}"


async def generate_focus_plan(db, user_id: str, force_regenerate: bool = False) -> Dict:
    """
    Generate a complete Focus Plan for a user.
    
    This is the main entry point that:
    1. Computes bucket costs from last N games
    2. Selects primary/secondary focus
    3. Selects openings
    4. Generates mission positions
    5. Returns complete plan JSON
    """
    
    # Get user
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"error": "User not found"}
    
    rating = user.get("rating", 1200)
    band = get_rating_band(rating)
    
    # Get last N analyzed games
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0}
    ).sort("imported_at", -1).to_list(DEFAULT_GAME_WINDOW + 10)
    
    game_ids = [g["game_id"] for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0}
    ).to_list(DEFAULT_GAME_WINDOW + 10)
    
    # Filter to properly analyzed games
    valid_analyses = [
        a for a in analyses
        if a.get("stockfish_analysis", {}).get("move_evaluations") 
        and len(a.get("stockfish_analysis", {}).get("move_evaluations", [])) >= 3
    ]
    
    games_analyzed = len(valid_analyses)
    needs_more_games = games_analyzed < MIN_GAMES_REQUIRED
    
    if needs_more_games:
        return {
            "needs_more_games": True,
            "games_analyzed": games_analyzed,
            "games_required": MIN_GAMES_REQUIRED,
            "rating": rating,
            "rating_band": band["label"],
        }
    
    # Sort analyses to match games order
    analysis_map = {a.get("game_id"): a for a in valid_analyses}
    sorted_analyses = [analysis_map.get(g["game_id"]) for g in games if analysis_map.get(g["game_id"])]
    sorted_analyses = sorted_analyses[:DEFAULT_GAME_WINDOW]
    
    # === COMPUTE BUCKET COSTS ===
    bucket_costs = compute_bucket_costs(sorted_analyses, games[:DEFAULT_GAME_WINDOW], rating)
    
    # === SELECT FOCUS ===
    primary_focus, secondary_focus = select_primary_and_secondary_focus(bucket_costs, rating)
    
    # === COMPUTE OPENING STATS ===
    opening_stats = compute_opening_stats(sorted_analyses, games[:DEFAULT_GAME_WINDOW])
    
    # === SELECT MISSION POSITIONS ===
    mission_positions = select_mission_positions(bucket_costs, primary_focus, sorted_analyses)
    
    # === COMPUTE RATING STATS ===
    rating_stats = compute_rating_stats(user, games)
    
    # === GET RULES FOR PRIMARY FOCUS ===
    focus_rules = band["rules"].get(primary_focus["id"], ["Focus on your primary weakness"])
    
    # === GENERATE PLAN ID ===
    week_start = datetime.now(timezone.utc).strftime("%Y-W%W")
    inputs_hash = hashlib.md5(json.dumps({
        "games_analyzed": games_analyzed,
        "rating": rating,
        "primary_focus_id": primary_focus["id"],
    }, sort_keys=True).encode()).hexdigest()[:8]
    
    plan_id = generate_deterministic_plan_id(user_id, week_start, inputs_hash)
    
    # === BUILD PLAN JSON ===
    plan = {
        "plan_id": plan_id,
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "week_start": week_start,
        "is_active": True,
        
        # Inputs
        "inputs": {
            "window_games": DEFAULT_GAME_WINDOW,
            "games_analyzed": games_analyzed,
            "rating": rating,
            "rating_band": band["label"],
        },
        
        # Rating stats
        "ratings": rating_stats,
        
        # Primary and secondary focus
        "primary_focus": {
            "code": primary_focus["id"],
            "label": _bucket_id_to_label(primary_focus["id"]),
            "score": primary_focus["score"],
            "games_affected": primary_focus.get("games_affected", 0),
            "frequency_rate": primary_focus.get("frequency_rate", 0),
            "example_position": primary_focus["example_positions"][0] if primary_focus.get("example_positions") else None,
            "reason": primary_focus.get("reason", ""),
        },
        "secondary_focus": {
            "code": secondary_focus["id"],
            "label": _bucket_id_to_label(secondary_focus["id"]),
            "score": secondary_focus["score"],
            "reason": secondary_focus.get("reason", ""),
        } if secondary_focus else None,
        
        # Focus rules (2 rules for user to follow)
        "rules": focus_rules[:2],
        
        # Opening recommendations
        "openings": {
            "white": opening_stats.get("white"),
            "black_vs_e4": opening_stats.get("black_vs_e4"),
            "black_vs_d4": opening_stats.get("black_vs_d4"),
        },
        
        # Today's mission
        "mission": {
            "active_seconds_target": 900,  # 15 minutes
            "idle_pause_seconds": 12,
            "steps": [
                {
                    "type": "OPENING_DRILL",
                    "label": "Opening Positions",
                    "required": min(3, len(mission_positions.get("opening_positions", []))),
                    "positions": mission_positions.get("opening_positions", [])[:3],
                },
                {
                    "type": "THREAT_DRILL",
                    "label": "Threat Awareness",
                    "required": min(5, len(mission_positions.get("threat_positions", []))),
                    "positions": mission_positions.get("threat_positions", [])[:5],
                },
                {
                    "type": "GUIDED_REPLAY",
                    "label": "Guided Replay",
                    "turning_point": mission_positions.get("turning_points", [{}])[0] if mission_positions.get("turning_points") else None,
                    "required_plies": 6,
                },
            ],
        },
        
        # Full bucket costs for debugging/display
        "bucket_costs": {
            bucket_id: {
                "score": data["score"],
                "games_affected": data["games_affected"],
                "frequency_rate": data["frequency_rate"],
                "allowed_for_rating": data["allowed_for_rating"],
            }
            for bucket_id, data in bucket_costs.items()
        },
        
        # All turning points for guided replay selection
        "turning_points": mission_positions.get("turning_points", []),
        
        # Weekly requirements
        "weekly_requirements": {
            "games_with_openings": {"target": 10, "current": 0},
            "missions_completed": {"target": 7, "current": 0},
            "guided_replays": {"target": 2, "current": 0},
        },
    }
    
    # === STORE PLAN ===
    # Deactivate old plans
    await db.focus_plans.update_many(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Check if plan already exists
    existing = await db.focus_plans.find_one({"plan_id": plan_id})
    if existing and not force_regenerate:
        # Return existing plan
        existing.pop("_id", None)
        return existing
    
    # Insert new plan
    await db.focus_plans.insert_one({**plan})
    
    return plan


def _bucket_id_to_label(bucket_id: str) -> str:
    """Convert bucket ID to human-readable label."""
    labels = {
        "PIECE_SAFETY": "Piece Safety",
        "THREAT_AWARENESS": "Threat Awareness",
        "TACTICAL_EXECUTION": "Tactical Execution",
        "ADVANTAGE_DISCIPLINE": "Advantage Discipline",
        "OPENING_STABILITY": "Opening Stability",
        "TIME_DISCIPLINE": "Time Discipline",
        "ENDGAME_FUNDAMENTALS": "Endgame Fundamentals",
    }
    return labels.get(bucket_id, bucket_id)


# =============================================================================
# COACH NOTE GENERATION
# =============================================================================

def generate_coach_note(plan: Dict) -> str:
    """
    Generate personalized coach note from plan data.
    
    Template:
    You're stable at {stable} and you've shown {peak}.
    The gap ({gap}) is mainly from {top_bucket}.
    This week we fix one habit: {habit_rule}.
    """
    ratings = plan.get("ratings", {})
    primary = plan.get("primary_focus", {})
    rules = plan.get("rules", [])
    
    stable = ratings.get("stable", 1200)
    peak = ratings.get("peak", stable)
    gap = ratings.get("gap", 0)
    
    focus_label = primary.get("label", "your weakest area")
    first_rule = rules[0] if rules else "Focus on your primary weakness"
    
    if gap <= 50:
        gap_note = f"You're playing consistently around {stable}."
    else:
        gap_note = f"You're stable at {stable} but you've shown {peak}. The {gap}-point gap"
    
    note = f"{gap_note} is mainly from {focus_label}. This week: {first_rule}"
    
    return note


# =============================================================================
# ACTIVE TIME TRACKING
# =============================================================================

async def start_mission_session(db, user_id: str, plan_id: str) -> Dict:
    """Start a new mission session for active time tracking."""
    session_id = f"session_{hashlib.md5(f'{user_id}_{datetime.now().isoformat()}'.encode()).hexdigest()[:12]}"
    
    session = {
        "session_id": session_id,
        "user_id": user_id,
        "plan_id": plan_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "active_seconds": 0,
        "last_interaction_at": datetime.now(timezone.utc).isoformat(),
        "is_paused": False,
        "events": [],
        "completed": False,
    }
    
    await db.mission_sessions.insert_one(session)
    session.pop("_id", None)
    
    return session


async def update_mission_interaction(db, session_id: str, event_type: str, event_data: Dict = None) -> Dict:
    """
    Update mission session with interaction.
    
    Tracks active time (pauses if idle > threshold).
    """
    session = await db.mission_sessions.find_one({"session_id": session_id})
    if not session:
        return {"error": "Session not found"}
    
    now = datetime.now(timezone.utc)
    last_interaction = datetime.fromisoformat(session["last_interaction_at"].replace("Z", "+00:00"))
    
    # Calculate time since last interaction
    elapsed = (now - last_interaction).total_seconds()
    
    # Get idle threshold from plan
    plan = await db.focus_plans.find_one({"plan_id": session["plan_id"]})
    idle_threshold = plan.get("mission", {}).get("idle_pause_seconds", 12) if plan else 12
    
    # If not too long since last interaction, count as active time
    if elapsed <= idle_threshold and not session.get("is_paused"):
        new_active = session["active_seconds"] + elapsed
    else:
        new_active = session["active_seconds"]
    
    # Record event
    event = {
        "type": event_type,
        "timestamp": now.isoformat(),
        "data": event_data or {},
    }
    
    # Update session
    update_data = {
        "active_seconds": new_active,
        "last_interaction_at": now.isoformat(),
        "is_paused": False,
    }
    
    await db.mission_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": update_data,
            "$push": {"events": event}
        }
    )
    
    return {
        "session_id": session_id,
        "active_seconds": new_active,
        "target_seconds": plan.get("mission", {}).get("active_seconds_target", 900) if plan else 900,
    }


async def complete_mission(db, session_id: str) -> Dict:
    """Mark mission as complete and update weekly progress."""
    session = await db.mission_sessions.find_one({"session_id": session_id})
    if not session:
        return {"error": "Session not found"}
    
    # Mark session complete
    await db.mission_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    # Update weekly progress on plan
    plan_id = session.get("plan_id")
    if plan_id:
        await db.focus_plans.update_one(
            {"plan_id": plan_id},
            {"$inc": {"weekly_requirements.missions_completed.current": 1}}
        )
    
    return {
        "completed": True,
        "active_seconds": session["active_seconds"],
        "session_id": session_id,
    }


# =============================================================================
# API FUNCTIONS
# =============================================================================

async def get_focus_page_data(db, user_id: str) -> Dict:
    """
    Get complete Focus Page data for the frontend.
    
    Returns:
    - plan: The current focus plan
    - coach_note: Personalized coach message
    - proof_metrics: 3 trend indicators
    """
    # Get or generate plan
    plan = await generate_focus_plan(db, user_id)
    
    if plan.get("needs_more_games"):
        return plan
    
    # Generate coach note
    coach_note = generate_coach_note(plan)
    
    # Get recent mission sessions for streak
    recent_sessions = await db.mission_sessions.find(
        {"user_id": user_id, "completed": True},
        {"_id": 0}
    ).sort("completed_at", -1).to_list(30)
    
    # Calculate streak
    streak = 0
    if recent_sessions:
        today = datetime.now(timezone.utc).date()
        for i, session in enumerate(recent_sessions):
            completed_at = datetime.fromisoformat(session["completed_at"].replace("Z", "+00:00")).date()
            expected_date = today - timedelta(days=i)
            if completed_at == expected_date:
                streak += 1
            else:
                break
    
    # Remove large data from plan for frontend
    frontend_plan = {k: v for k, v in plan.items() if k not in ["bucket_costs"]}
    
    return {
        "plan": frontend_plan,
        "coach_note": coach_note,
        "streak": streak,
        "last_mission_date": recent_sessions[0]["completed_at"] if recent_sessions else None,
    }
