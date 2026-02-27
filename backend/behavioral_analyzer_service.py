"""
Behavioral Analyzer Service - P0 Implementation

This is the core engine that produces BEHAVIORAL insights, not just chess analysis.

Output: BehavioralReport with:
- 5 scorecard dimensions (Plan Discipline, Decision Stability, Pattern Persistence, Coach Compliance, Learning Velocity)
- One headline + one rich insight
- One mission (next action)
- Evidence references
- Confidence score

P0 focuses on: Plan Discipline, Decision Stability, Pattern Persistence
P1 will add: Coach Compliance, Learning Velocity (advice engine)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from collections import Counter
import re

logger = logging.getLogger(__name__)


# ==================== DATA STRUCTURES ====================

class ScoreItem:
    """A single behavioral dimension score"""
    def __init__(self, score: int, label: str, why: str, evidence_refs: List[Dict] = None):
        self.score = score
        self.label = label
        self.why = why
        self.evidence_refs = evidence_refs or []
    
    def to_dict(self):
        return {
            "score": self.score,
            "label": self.label,
            "why": self.why,
            "evidence_refs": self.evidence_refs
        }


class Mission:
    """A single next action for the user"""
    def __init__(self, type: str, title: str, instruction: str, payload: Dict = None):
        self.type = type
        self.title = title
        self.instruction = instruction
        self.payload = payload or {}
    
    def to_dict(self):
        return {
            "type": self.type,
            "title": self.title,
            "instruction": self.instruction,
            "payload": self.payload
        }


class BehaviorFeatures:
    """Extracted behavioral features from a game"""
    def __init__(self):
        # Plan discipline
        self.opening_plan_score: float = 0.0
        self.plan_break_move: Optional[int] = None
        self.plan_signal: str = "NO_CLEAR_PLAN"
        self.repeat_piece_moves: int = 0
        self.early_queen_moves: int = 0
        self.undeveloped_after_10: int = 0
        
        # Decision stability
        self.time_pressure_index: float = 0.0
        self.tilt_index: float = 0.0
        self.collapse_move: Optional[int] = None
        self.has_clock_data: bool = False
        
        # Pattern persistence
        self.leak_tags_last_game: Dict[str, int] = {}
        self.leak_trends: Dict[str, Dict] = {}
        
        # Context
        self.game_quality_bucket: str = "MIXED"
        self.total_moves: int = 0
        self.user_color: str = "white"
        self.blunder_count: int = 0
        self.mistake_count: int = 0
        self.first_blunder_move: Optional[int] = None
        
        # Evidence
        self.evidence: List[Dict] = []


# ==================== CONSTANTS ====================

# Leak tags for pattern persistence
NEGATIVE_LEAK_TAGS = [
    "OPENING_WANDER",      # Repeat pieces, undeveloped minors
    "TACTICAL_BLINDNESS",  # Blunder with cp_loss > 300
    "TIME_PANIC",          # Low time + error spike
    "CONVERSION_ISSUE",    # Was winning, then threw
]

POSITIVE_LEAK_TAGS = [
    "COMEBACK_RESILIENCE", # Was losing, then recovered
]

# CP loss thresholds
CP_INACCURACY = 50
CP_MISTAKE = 100
CP_BLUNDER = 200

# Phase detection (simple)
OPENING_END = 10
MIDDLEGAME_END = 30


# ==================== FEATURE EXTRACTION ====================

def detect_phase(move_no: int) -> str:
    """Simple phase detection based on move number"""
    if move_no <= OPENING_END:
        return "OPENING"
    elif move_no <= MIDDLEGAME_END:
        return "MIDDLEGAME"
    return "ENDGAME"


def extract_behavior_features(
    game_data: Dict,
    move_facts: List[Dict],
    history_games: List[Dict],
    reflection: Optional[Dict] = None
) -> BehaviorFeatures:
    """
    Extract all behavioral features from a game.
    
    Args:
        game_data: The game document
        move_facts: List of move evaluations from Stockfish
        history_games: Recent games for trend analysis
        reflection: Optional reflection data
    
    Returns:
        BehaviorFeatures object
    """
    features = BehaviorFeatures()
    
    # Determine user color
    user_color = game_data.get("user_color", "white")
    features.user_color = user_color
    
    # Filter to user's moves
    user_moves = [m for m in move_facts if is_user_move(m, user_color)]
    features.total_moves = len(user_moves)
    
    if not user_moves:
        return features
    
    # Count errors
    features.blunder_count = sum(1 for m in user_moves if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= CP_BLUNDER)
    features.mistake_count = sum(1 for m in user_moves if m.get("evaluation") == "mistake" or (CP_MISTAKE <= m.get("cp_loss", 0) < CP_BLUNDER))
    
    # Find first blunder
    for m in user_moves:
        if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= CP_BLUNDER:
            features.first_blunder_move = m.get("move_number")
            break
    
    # 1. Plan Discipline
    plan_score, plan_break, plan_signal, evidence = compute_plan_discipline(user_moves, reflection)
    features.opening_plan_score = plan_score
    features.plan_break_move = plan_break
    features.plan_signal = plan_signal
    features.evidence.extend(evidence)
    
    # Extract opening stats for evidence
    opening_moves = [m for m in user_moves if m.get("move_number", 0) <= OPENING_END]
    features.repeat_piece_moves = count_repeat_piece_moves(opening_moves)
    features.early_queen_moves = count_piece_moves(opening_moves, "Q")
    
    # 2. Decision Stability
    time_pressure, tilt, collapse, has_clock, stability_evidence = compute_decision_stability(user_moves, move_facts)
    features.time_pressure_index = time_pressure
    features.tilt_index = tilt
    features.collapse_move = collapse
    features.has_clock_data = has_clock
    features.evidence.extend(stability_evidence)
    
    # 3. Pattern Persistence
    leak_tags = tag_leaks_for_game(features, user_moves)
    features.leak_tags_last_game = leak_tags
    
    # Compute trends from history
    features.leak_trends = compute_leak_trends(history_games, user_color)
    
    # 4. Game quality bucket
    features.game_quality_bucket = determine_game_quality(features)
    
    return features


def is_user_move(move: Dict, user_color: str) -> bool:
    """Determine if a move belongs to the user based on move number and color"""
    move_no = move.get("move_number", 0)
    # In chess, white moves on odd half-moves, black on even
    # If move_number is the full move count, we need FEN to check
    # Simpler: check the FEN's turn indicator
    fen = move.get("fen_before", "")
    if " w " in fen:
        return user_color == "white"
    elif " b " in fen:
        return user_color == "black"
    # Fallback: assume alternating
    return (move_no % 2 == 1) == (user_color == "white")


def compute_plan_discipline(
    user_moves: List[Dict],
    reflection: Optional[Dict]
) -> Tuple[float, Optional[int], str, List[Dict]]:
    """
    Compute plan discipline score for opening play.
    
    Signals:
    - Repeat piece moves in first 10
    - Early queen moves
    - Leaving pieces undeveloped
    - Reflection alignment (if available)
    """
    opening_moves = [m for m in user_moves if m.get("move_number", 0) <= OPENING_END]
    
    if not opening_moves:
        return 0.5, None, "NO_CLEAR_PLAN", []
    
    evidence = []
    
    # Count violations
    repeat_moves = count_repeat_piece_moves(opening_moves)
    queen_moves = count_piece_moves(opening_moves, "Q")
    
    # Base score starts at 1.0
    score = 1.0
    
    # Penalty for repeat piece moves (up to 0.36)
    repeat_penalty = min(repeat_moves * 0.12, 0.36)
    score -= repeat_penalty
    if repeat_moves > 0:
        evidence.append({
            "move_no": None,
            "note": f"Moved same piece {repeat_moves} times in opening",
            "type": "repeat_piece"
        })
    
    # Penalty for early queen moves (up to 0.20)
    queen_penalty = min(queen_moves * 0.10, 0.20)
    score -= queen_penalty
    if queen_moves > 0:
        evidence.append({
            "move_no": None,
            "note": f"Early queen moves: {queen_moves}",
            "type": "early_queen"
        })
    
    # Check for big cp_loss in opening (plan break)
    plan_break_move = None
    for m in opening_moves:
        cp_loss = m.get("cp_loss", 0)
        if cp_loss >= 150:
            plan_break_move = m.get("move_number")
            score -= 0.15
            evidence.append({
                "move_no": plan_break_move,
                "note": f"Significant error (lost {cp_loss}cp)",
                "type": "plan_break"
            })
            break
    
    # Clamp score
    score = max(0, min(1, score))
    
    # Determine signal
    if score >= 0.75:
        plan_signal = "STUCK_TO_PLAN"
    elif score >= 0.45:
        plan_signal = "NO_CLEAR_PLAN"
    else:
        plan_signal = "ABANDONED"
    
    return score, plan_break_move, plan_signal, evidence


def count_repeat_piece_moves(moves: List[Dict]) -> int:
    """
    Count how many times the same piece was moved in the opening.
    Uses UCI notation to track piece origin squares.
    """
    piece_moves = {}  # from_square -> count
    repeats = 0
    
    for m in moves:
        uci = m.get("move_uci") or m.get("uci") or ""
        if len(uci) >= 4:
            from_sq = uci[:2]
            piece_moves[from_sq] = piece_moves.get(from_sq, 0) + 1
            if piece_moves[from_sq] >= 2:
                repeats += 1
    
    return repeats


def count_piece_moves(moves: List[Dict], piece: str) -> int:
    """Count moves of a specific piece type (e.g., 'Q' for queen)"""
    count = 0
    for m in moves:
        san = m.get("move") or m.get("san") or ""
        if san.startswith(piece):
            count += 1
    return count


def compute_decision_stability(
    user_moves: List[Dict],
    all_moves: List[Dict]
) -> Tuple[float, float, Optional[int], bool, List[Dict]]:
    """
    Compute decision stability (time pressure + tilt detection).
    
    Returns:
        (time_pressure_index, tilt_index, collapse_move, has_clock, evidence)
    """
    evidence = []
    
    # Check for clock data
    has_clock = any(m.get("clock_before_ms") or m.get("clock") for m in user_moves)
    
    # Time pressure index
    if has_clock:
        low_time_moves = sum(1 for m in user_moves if (m.get("clock_before_ms") or 999999) <= 30000)
        very_fast_moves = sum(1 for m in user_moves if (m.get("think_time_ms") or 999999) <= 2000)
        time_pressure_index = min(1, (0.6 * low_time_moves + 0.4 * very_fast_moves) / max(1, len(user_moves)))
    else:
        # Unknown - use neutral default
        time_pressure_index = 0.35
    
    # Tilt detection: after first blunder, do next moves show elevated cp_loss?
    tilt_index = 0.0
    collapse_move = None
    
    # Find first blunder
    first_blunder_idx = None
    for i, m in enumerate(user_moves):
        if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= CP_BLUNDER:
            first_blunder_idx = i
            break
    
    if first_blunder_idx is not None:
        # Get cp_loss before and after
        before_moves = user_moves[max(0, first_blunder_idx - 6):first_blunder_idx]
        after_moves = user_moves[first_blunder_idx + 1:first_blunder_idx + 7]
        
        avg_before = sum(m.get("cp_loss", 0) for m in before_moves) / max(1, len(before_moves))
        avg_after = sum(m.get("cp_loss", 0) for m in after_moves) / max(1, len(after_moves))
        
        # Tilt = elevated cp_loss after blunder
        tilt_raw = (avg_after - avg_before) / 200.0
        tilt_index = max(0, min(1, tilt_raw))
        
        # Find collapse move (first big error after blunder)
        for m in after_moves:
            if m.get("cp_loss", 0) >= 250:
                collapse_move = m.get("move_number")
                evidence.append({
                    "move_no": collapse_move,
                    "note": f"Collapse after blunder (lost {m.get('cp_loss', 0)}cp)",
                    "type": "collapse"
                })
                break
    
    # Add evidence for time pressure
    if time_pressure_index >= 0.6:
        evidence.append({
            "move_no": None,
            "note": "High time pressure detected",
            "type": "time_pressure"
        })
    
    if tilt_index >= 0.4:
        evidence.append({
            "move_no": user_moves[first_blunder_idx].get("move_number") if first_blunder_idx else None,
            "note": "Tilt pattern: errors escalated after first blunder",
            "type": "tilt"
        })
    
    return time_pressure_index, tilt_index, collapse_move, has_clock, evidence


def tag_leaks_for_game(features: BehaviorFeatures, user_moves: List[Dict]) -> Dict[str, int]:
    """
    Tag behavioral leaks for a single game.
    """
    tags = {}
    
    # OPENING_WANDER: poor plan discipline
    if features.opening_plan_score < 0.45:
        tags["OPENING_WANDER"] = 1
    
    # TACTICAL_BLINDNESS: blunder with high cp_loss
    big_blunders = sum(1 for m in user_moves if m.get("cp_loss", 0) >= 300)
    if big_blunders >= 1:
        tags["TACTICAL_BLINDNESS"] = big_blunders
    
    # TIME_PANIC: high time pressure + tilt
    if features.time_pressure_index >= 0.6 and features.tilt_index >= 0.3:
        tags["TIME_PANIC"] = 1
    
    # CONVERSION_ISSUE: was winning then threw
    if had_winning_then_threw(user_moves):
        tags["CONVERSION_ISSUE"] = 1
    
    # COMEBACK_RESILIENCE: was losing then recovered (positive)
    if had_losing_then_recovered(user_moves):
        tags["COMEBACK_RESILIENCE"] = 1
    
    return tags


def had_winning_then_threw(user_moves: List[Dict]) -> bool:
    """Check if user was winning (>+200cp) then dropped below 0"""
    was_winning = False
    threw = False
    
    for m in user_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        
        if eval_before >= 2.0:  # +200cp
            was_winning = True
        
        if was_winning and eval_after <= 0:
            threw = True
            break
    
    return was_winning and threw


def had_losing_then_recovered(user_moves: List[Dict]) -> bool:
    """Check if user was losing (<-200cp) then recovered to near equal"""
    was_losing = False
    recovered = False
    
    for m in user_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        
        if eval_before <= -2.0:  # -200cp
            was_losing = True
        
        if was_losing and eval_after >= -0.5:
            recovered = True
            break
    
    return was_losing and recovered


def compute_leak_trends(history_games: List[Dict], user_color: str) -> Dict[str, Dict]:
    """
    Compute leak tag trends across recent games.
    Returns avg occurrence and trend slope for each tag.
    """
    trends = {}
    
    # Initialize all tags
    for tag in NEGATIVE_LEAK_TAGS + POSITIVE_LEAK_TAGS:
        trends[tag] = {"avg": 0.0, "slope": 0.0, "series": []}
    
    if not history_games:
        return trends
    
    # Extract tags from each historical game
    for game in history_games[-10:]:  # Last 10 games
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Simple tag extraction from history
        game_tags = {}
        
        # Check for blunders
        blunder_count = sum(1 for m in move_evals if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= 300)
        if blunder_count >= 1:
            game_tags["TACTICAL_BLINDNESS"] = blunder_count
        
        # Check for opening issues (repeat moves, high cp_loss early)
        opening_errors = sum(1 for m in move_evals if m.get("move_number", 0) <= 10 and m.get("cp_loss", 0) >= 100)
        if opening_errors >= 2:
            game_tags["OPENING_WANDER"] = 1
        
        # Store in series
        for tag in NEGATIVE_LEAK_TAGS + POSITIVE_LEAK_TAGS:
            trends[tag]["series"].append(game_tags.get(tag, 0))
    
    # Compute avg and slope
    for tag, data in trends.items():
        series = data["series"]
        if series:
            data["avg"] = sum(series) / len(series)
            # Simple slope: compare first half to second half
            if len(series) >= 4:
                first_half = sum(series[:len(series)//2]) / (len(series)//2)
                second_half = sum(series[len(series)//2:]) / (len(series) - len(series)//2)
                data["slope"] = second_half - first_half  # Positive = worsening
            else:
                data["slope"] = 0.0
    
    return trends


def determine_game_quality(features: BehaviorFeatures) -> str:
    """Determine overall game quality bucket"""
    if features.blunder_count == 0 and features.mistake_count <= 2:
        return "GOOD"
    elif features.blunder_count >= 3 or features.mistake_count >= 5:
        return "BAD"
    return "MIXED"


# ==================== SCORING ====================

def score_behavior(features: BehaviorFeatures) -> Dict[str, ScoreItem]:
    """
    Convert features into 0-100 scores with labels.
    """
    scorecard = {}
    
    # Plan Discipline
    plan_score = round(features.opening_plan_score * 100)
    plan_why = "Development stayed clean" if features.plan_signal == "STUCK_TO_PLAN" else \
               "Opening plan broke early" if features.plan_signal == "ABANDONED" else \
               "Opening could be more focused"
    scorecard["plan_discipline"] = ScoreItem(
        score=plan_score,
        label=labelize(plan_score),
        why=plan_why,
        evidence_refs=[e for e in features.evidence if e.get("type") in ["repeat_piece", "early_queen", "plan_break"]]
    )
    
    # Decision Stability
    stability_raw = 1 - (0.55 * features.time_pressure_index + 0.45 * features.tilt_index)
    stability_score = round(max(0, min(1, stability_raw)) * 100)
    stability_why = "Stable decision-making throughout" if stability_score >= 70 else \
                    "Some instability after errors" if features.tilt_index >= 0.3 else \
                    "Time pressure affected decisions" if features.time_pressure_index >= 0.5 else \
                    "Decision stability needs attention"
    scorecard["decision_stability"] = ScoreItem(
        score=stability_score,
        label=labelize(stability_score),
        why=stability_why,
        evidence_refs=[e for e in features.evidence if e.get("type") in ["time_pressure", "tilt", "collapse"]]
    )
    
    # Pattern Persistence
    persistence_score = score_persistence(features.leak_tags_last_game, features.leak_trends)
    persistence_why = "No recurring negative patterns" if persistence_score >= 70 else \
                      "Some patterns repeating from recent games" if persistence_score >= 50 else \
                      "Same issues keep appearing"
    scorecard["pattern_persistence"] = ScoreItem(
        score=persistence_score,
        label=labelize(persistence_score),
        why=persistence_why,
        evidence_refs=[]
    )
    
    # Coach Compliance (P1 - placeholder for now)
    scorecard["coach_compliance"] = ScoreItem(
        score=60,
        label="Mixed",
        why="Advice tracking coming soon",
        evidence_refs=[]
    )
    
    # Learning Velocity (P1 - placeholder)
    scorecard["learning_velocity"] = ScoreItem(
        score=60,
        label="Mixed",
        why="Learning velocity tracking coming soon",
        evidence_refs=[]
    )
    
    return scorecard


def score_persistence(leak_tags: Dict[str, int], leak_trends: Dict[str, Dict]) -> int:
    """Score pattern persistence (lower = more persistent issues)"""
    penalty = 0
    
    for tag in NEGATIVE_LEAK_TAGS:
        # Penalty for occurrence in this game
        penalty += min(25, leak_tags.get(tag, 0) * 15)
        
        # Penalty for recurring in history
        if leak_trends.get(tag, {}).get("avg", 0) >= 0.6:
            penalty += 10
    
    return max(0, 80 - penalty)


def labelize(score: int) -> str:
    """Convert score to label"""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 45:
        return "Mixed"
    return "Concern"


# ==================== INSIGHT GENERATION ====================

def generate_coach_insight(
    features: BehaviorFeatures,
    scorecard: Dict[str, ScoreItem],
    history_games: List[Dict]
) -> Tuple[str, str]:
    """
    Generate headline and rich insight based on features and scorecard.
    
    Returns:
        (headline, rich_insight)
    """
    # Detect notable improvement
    improvement = detect_notable_improvement(features, scorecard, history_games)
    
    # Detect main problem
    main_problem = detect_main_problem(features, scorecard)
    
    # Build headline
    headline = build_headline(improvement, main_problem, features)
    
    # Build rich insight
    rich_insight = build_rich_insight(improvement, main_problem, features, scorecard, history_games)
    
    return headline, rich_insight


def detect_notable_improvement(
    features: BehaviorFeatures,
    scorecard: Dict[str, ScoreItem],
    history_games: List[Dict]
) -> Optional[str]:
    """Detect if there's a notable improvement to highlight"""
    
    # Check if opening is improving
    if features.leak_trends.get("OPENING_WANDER", {}).get("slope", 0) < -0.25:
        return "Your openings are getting more disciplined."
    
    # Check if time pressure is improving
    if features.leak_trends.get("TIME_PANIC", {}).get("slope", 0) < -0.25:
        return "Your time management is improving."
    
    # Check if this was a clean game after bad ones
    if features.game_quality_bucket == "GOOD" and history_games:
        recent_bad = sum(1 for g in history_games[-5:] 
                       if g.get("stockfish_analysis", {}).get("blunders", 0) >= 2)
        if recent_bad >= 3:
            return "This was a cleaner game than your recent ones."
    
    return None


def detect_main_problem(
    features: BehaviorFeatures,
    scorecard: Dict[str, ScoreItem]
) -> str:
    """Detect the main problem to address (priority order)"""
    
    if scorecard["decision_stability"].label == "Concern":
        return "DECISION_STABILITY"
    
    if scorecard["plan_discipline"].label == "Concern":
        return "PLAN_DISCIPLINE"
    
    if scorecard["pattern_persistence"].label == "Concern":
        return "REPEATING_LEAK"
    
    if features.blunder_count >= 2:
        return "TACTICAL_ERRORS"
    
    return "NONE"


def build_headline(
    improvement: Optional[str],
    main_problem: str,
    features: BehaviorFeatures
) -> str:
    """Build the main headline"""
    
    if improvement and main_problem == "NONE":
        return "Clear progress — your play was more disciplined than recent games."
    
    if improvement and main_problem != "NONE":
        return "You improved one key habit — but one issue still needs attention."
    
    if main_problem == "DECISION_STABILITY":
        return "Your ideas are fine — but decision stability is breaking your game."
    
    if main_problem == "PLAN_DISCIPLINE":
        return "You're drifting early — the opening plan breaks too soon."
    
    if main_problem == "REPEATING_LEAK":
        return "Same pattern again — we need to isolate it and fix it."
    
    if main_problem == "TACTICAL_ERRORS":
        return "The tactical errors are the main leak today."
    
    if features.game_quality_bucket == "GOOD":
        return "A solid game — one small fix will lift your results."
    
    return "A mixed game — let's look at what happened."


def build_rich_insight(
    improvement: Optional[str],
    main_problem: str,
    features: BehaviorFeatures,
    scorecard: Dict[str, ScoreItem],
    history_games: List[Dict]
) -> str:
    """Build the 2-3 sentence rich insight"""
    
    parts = []
    
    # Add improvement if exists
    if improvement:
        parts.append(improvement)
    
    # Add problem-specific insight
    if main_problem == "DECISION_STABILITY":
        if features.collapse_move:
            parts.append(f"After move {features.collapse_move}, your errors escalated and stayed high.")
        if features.tilt_index >= 0.4:
            parts.append("This matches a tilt pattern: one mistake leads to more.")
        # Add history context
        panic_count = count_recent_games_with_tag(history_games, "TIME_PANIC", 8)
        if panic_count >= 2:
            parts.append(f"This has happened in {panic_count} of your last 8 games.")
    
    elif main_problem == "PLAN_DISCIPLINE":
        if features.plan_break_move:
            parts.append(f"Your opening plan breaks around move {features.plan_break_move}.")
        if features.repeat_piece_moves > 0:
            parts.append(f"You moved the same piece multiple times in the opening ({features.repeat_piece_moves}x).")
        parts.append("When development stays clean, your middlegame errors drop.")
    
    elif main_problem == "REPEATING_LEAK":
        top_leak = get_top_negative_leak(features.leak_tags_last_game)
        if top_leak:
            leak_label = format_leak_label(top_leak)
            parts.append(f"The repeating issue is: {leak_label}.")
            trend = features.leak_trends.get(top_leak, {})
            if trend.get("avg", 0) >= 0.5:
                parts.append("This has been a consistent pattern across recent games.")
    
    elif main_problem == "TACTICAL_ERRORS":
        parts.append(f"You had {features.blunder_count} blunders and {features.mistake_count} mistakes.")
        if features.first_blunder_move:
            parts.append(f"The first major error came on move {features.first_blunder_move}.")
    
    else:
        # No major problem
        if features.game_quality_bucket == "GOOD":
            parts.append("You maintained good discipline throughout.")
        else:
            parts.append("A few small adjustments will make a difference.")
    
    return " ".join(parts)


def count_recent_games_with_tag(history_games: List[Dict], tag: str, limit: int) -> int:
    """Count how many recent games have a specific leak tag"""
    count = 0
    for game in history_games[-limit:]:
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        if tag == "TIME_PANIC":
            # Check for tilt pattern
            blunders = [m for m in move_evals if m.get("evaluation") == "blunder"]
            if len(blunders) >= 2:
                count += 1
        elif tag == "OPENING_WANDER":
            opening_errors = sum(1 for m in move_evals if m.get("move_number", 0) <= 10 and m.get("cp_loss", 0) >= 100)
            if opening_errors >= 2:
                count += 1
    
    return count


def get_top_negative_leak(leak_tags: Dict[str, int]) -> Optional[str]:
    """Get the most prominent negative leak"""
    for tag in NEGATIVE_LEAK_TAGS:
        if leak_tags.get(tag, 0) > 0:
            return tag
    return None


def format_leak_label(leak: str) -> str:
    """Format leak tag into human-readable label"""
    labels = {
        "OPENING_WANDER": "unfocused opening play",
        "TACTICAL_BLINDNESS": "missing tactical threats",
        "TIME_PANIC": "time pressure errors",
        "CONVERSION_ISSUE": "failing to convert winning positions",
        "COMEBACK_RESILIENCE": "fighting back from losing positions",
    }
    return labels.get(leak, leak.lower().replace("_", " "))


# ==================== MISSION SELECTION ====================

def choose_next_mission(
    features: BehaviorFeatures,
    scorecard: Dict[str, ScoreItem],
    game_id: str
) -> Mission:
    """
    Choose ONE mission (next action) based on features and scorecard.
    """
    
    # Priority 1: Decision stability issues
    if scorecard["decision_stability"].label in ["Concern", "Mixed"] and features.collapse_move:
        return Mission(
            type="STABILITY_DRILL",
            title="Decision Stability Drill (5 min)",
            instruction=f"Replay the position at move {features.collapse_move}. Take 30 seconds. Find 3 candidate moves. Pick the safest one.",
            payload={
                "game_id": game_id,
                "move_no": features.collapse_move,
                "focus": "stability"
            }
        )
    
    # Priority 2: Opening discipline issues
    if scorecard["plan_discipline"].label in ["Concern", "Mixed"]:
        return Mission(
            type="OPENING_DISCIPLINE",
            title="Opening Review (3 min)",
            instruction="Look at your first 10 moves. Find ONE move where you broke development rules. What should you have played?",
            payload={
                "game_id": game_id,
                "moves_range": [1, 10],
                "focus": "opening"
            }
        )
    
    # Priority 3: Recurring pattern
    top_leak = get_top_negative_leak(features.leak_tags_last_game)
    if top_leak:
        return Mission(
            type="PATTERN_FIX",
            title=f"Fix {format_leak_label(top_leak).title()} (5 min)",
            instruction=f"Your pattern: {format_leak_label(top_leak)}. Solve 3 positions that train the opposite habit.",
            payload={
                "game_id": game_id,
                "pattern": top_leak,
                "focus": "pattern"
            }
        )
    
    # Default: Tactical drill from errors
    return Mission(
        type="TACTICAL_FUEL",
        title="Fix Your Mistakes (5 min)",
        instruction="Solve 3 positions from your biggest errors in this game.",
        payload={
            "game_id": game_id,
            "focus": "tactics"
        }
    )


# ==================== CONFIDENCE ====================

def compute_confidence(
    history_count: int,
    has_clock: bool,
    has_reflection: bool
) -> float:
    """
    Compute confidence score for the behavioral report.
    
    Higher confidence = more reliable insights.
    """
    confidence = 0.3  # Base
    
    # More history = more confidence (up to 0.4)
    confidence += min(history_count / 20, 0.4)
    
    # Clock data helps (0.2)
    if has_clock:
        confidence += 0.2
    
    # Reflection helps (0.1)
    if has_reflection:
        confidence += 0.1
    
    return min(1.0, confidence)


def get_confidence_label(confidence: float) -> str:
    """Get confidence label for UI"""
    if confidence >= 0.7:
        return "High"
    elif confidence >= 0.45:
        return "Medium"
    return "Low"


# ==================== MAIN ENTRY POINT ====================

async def generate_behavioral_report(
    db,
    user_id: str,
    game_id: str
) -> Dict:
    """
    Main entry point: Generate a complete behavioral report for a game.
    
    Returns:
        BehavioralReport dict
    """
    # Load game data
    game = await db.games.find_one({"game_id": game_id, "user_id": user_id})
    if not game:
        return {"error": "Game not found"}
    
    # Load analysis
    analysis = await db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        return {"error": "Game not analyzed yet"}
    
    # Get move facts from Stockfish analysis
    sf = analysis.get("stockfish_analysis", {})
    move_facts = sf.get("move_evaluations", [])
    
    # Load history (last 30 games before this one)
    history = await db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$ne": game_id}},
        {"stockfish_analysis": 1, "game_id": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(30).to_list(30)
    
    # Load reflection (if exists)
    reflection = await db.reflection_sessions.find_one({"game_id": game_id, "user_id": user_id})
    
    # Extract features
    game_data = {
        "user_color": game.get("user_color", "white"),
        "result": game.get("result"),
        "opponent_name": game.get("opponent_name"),
    }
    features = extract_behavior_features(game_data, move_facts, history, reflection)
    
    # Score behavior
    scorecard = score_behavior(features)
    
    # Generate insight
    headline, rich_insight = generate_coach_insight(features, scorecard, history)
    
    # Choose mission
    mission = choose_next_mission(features, scorecard, game_id)
    
    # Compute confidence
    confidence = compute_confidence(
        history_count=len(history),
        has_clock=features.has_clock_data,
        has_reflection=reflection is not None
    )
    
    # Build report
    report = {
        "game_id": game_id,
        "headline": headline,
        "rich_insight": rich_insight,
        "scorecard": {k: v.to_dict() for k, v in scorecard.items()},
        "next_mission": mission.to_dict(),
        "confidence": round(confidence, 2),
        "confidence_label": get_confidence_label(confidence),
        "evidence": features.evidence,
        "debug": {
            "game_quality": features.game_quality_bucket,
            "blunders": features.blunder_count,
            "mistakes": features.mistake_count,
            "plan_signal": features.plan_signal,
            "tilt_index": round(features.tilt_index, 2),
            "time_pressure_index": round(features.time_pressure_index, 2),
            "leak_tags": features.leak_tags_last_game,
        }
    }
    
    return report
