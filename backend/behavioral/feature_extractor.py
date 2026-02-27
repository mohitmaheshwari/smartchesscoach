"""
Feature Extractor Module

Extracts behavioral features from game data.
This is the foundation layer - raw feature extraction before enrichment.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import Counter

# Constants
CP_INACCURACY = 50
CP_MISTAKE = 100
CP_BLUNDER = 200
OPENING_END = 10
MIDDLEGAME_END = 30

# Leak tags
NEGATIVE_LEAK_TAGS = [
    "OPENING_WANDER",
    "TACTICAL_BLINDNESS", 
    "TIME_PANIC",
    "CONVERSION_ISSUE",
]

POSITIVE_LEAK_TAGS = [
    "COMEBACK_RESILIENCE",
]


class BehaviorFeatures:
    """Container for extracted behavioral features"""
    def __init__(self):
        # Plan discipline
        self.opening_plan_score: float = 0.0
        self.plan_break_move: Optional[int] = None
        self.plan_signal: str = "NO_CLEAR_PLAN"
        self.repeat_piece_moves: int = 0
        self.early_queen_moves: int = 0
        
        # Decision stability
        self.time_pressure_index: float = 0.0
        self.tilt_index: float = 0.0
        self.collapse_move: Optional[int] = None
        self.has_clock_data: bool = False
        
        # Pattern persistence
        self.leak_tags_last_game: Dict[str, int] = {}
        self.leak_trends: Dict[str, Dict] = {}
        
        # Contextual patterns (enriched in context_enricher)
        self.contextual_patterns: Dict[str, Dict] = {}
        
        # Root cause (set by context_enricher)
        self.root_cause: Optional[str] = None
        
        # Context
        self.game_quality_bucket: str = "MIXED"
        self.total_moves: int = 0
        self.user_color: str = "white"
        self.blunder_count: int = 0
        self.mistake_count: int = 0
        self.first_blunder_move: Optional[int] = None
        
        # Evidence
        self.evidence: List[Dict] = []
        
        # Move-level details for context enrichment
        self.error_moves: List[Dict] = []  # All error moves with context


def detect_phase(move_no: int) -> str:
    """Simple phase detection based on move number"""
    if move_no <= OPENING_END:
        return "OPENING"
    elif move_no <= MIDDLEGAME_END:
        return "MIDDLEGAME"
    return "ENDGAME"


def is_user_move(move: Dict, user_color: str) -> bool:
    """Determine if a move belongs to the user"""
    fen = move.get("fen_before", "")
    if " w " in fen:
        return user_color == "white"
    elif " b " in fen:
        return user_color == "black"
    move_no = move.get("move_number", 0)
    return (move_no % 2 == 1) == (user_color == "white")


def extract_behavior_features(
    game_data: Dict,
    move_facts: List[Dict],
    history_games: List[Dict],
    reflection: Optional[Dict] = None
) -> BehaviorFeatures:
    """
    Extract all behavioral features from a game.
    """
    features = BehaviorFeatures()
    
    user_color = game_data.get("user_color", "white")
    features.user_color = user_color
    
    user_moves = [m for m in move_facts if is_user_move(m, user_color)]
    features.total_moves = len(user_moves)
    
    if not user_moves:
        return features
    
    # Count errors and collect error moves with context
    for m in user_moves:
        cp_loss = m.get("cp_loss", 0)
        eval_type = m.get("evaluation", "")
        
        is_blunder = eval_type == "blunder" or cp_loss >= CP_BLUNDER
        is_mistake = eval_type == "mistake" or (CP_MISTAKE <= cp_loss < CP_BLUNDER)
        
        if is_blunder:
            features.blunder_count += 1
            if features.first_blunder_move is None:
                features.first_blunder_move = m.get("move_number")
        
        if is_mistake:
            features.mistake_count += 1
        
        # Collect error moves with full context for enrichment
        if is_blunder or is_mistake:
            features.error_moves.append({
                "move_number": m.get("move_number"),
                "phase": detect_phase(m.get("move_number", 0)),
                "cp_loss": cp_loss,
                "eval_before": m.get("eval_before", 0),
                "clock_before_ms": m.get("clock_before_ms"),
                "is_blunder": is_blunder,
                "is_mistake": is_mistake,
            })
    
    # Plan Discipline
    plan_score, plan_break, plan_signal, evidence = _compute_plan_discipline(user_moves)
    features.opening_plan_score = plan_score
    features.plan_break_move = plan_break
    features.plan_signal = plan_signal
    features.evidence.extend(evidence)
    
    opening_moves = [m for m in user_moves if m.get("move_number", 0) <= OPENING_END]
    features.repeat_piece_moves = _count_repeat_piece_moves(opening_moves)
    features.early_queen_moves = _count_piece_moves(opening_moves, "Q")
    
    # Decision Stability
    time_pressure, tilt, collapse, has_clock, stability_evidence = _compute_decision_stability(user_moves)
    features.time_pressure_index = time_pressure
    features.tilt_index = tilt
    features.collapse_move = collapse
    features.has_clock_data = has_clock
    features.evidence.extend(stability_evidence)
    
    # Pattern Persistence
    features.leak_tags_last_game = _tag_leaks_for_game(features, user_moves)
    features.leak_trends = _compute_leak_trends(history_games, user_color)
    
    # Game quality
    features.game_quality_bucket = _determine_game_quality(features)
    
    return features


def _compute_plan_discipline(user_moves: List[Dict]) -> Tuple[float, Optional[int], str, List[Dict]]:
    """Compute plan discipline score"""
    opening_moves = [m for m in user_moves if m.get("move_number", 0) <= OPENING_END]
    
    if not opening_moves:
        return 0.5, None, "NO_CLEAR_PLAN", []
    
    evidence = []
    repeat_moves = _count_repeat_piece_moves(opening_moves)
    queen_moves = _count_piece_moves(opening_moves, "Q")
    
    score = 1.0
    score -= min(repeat_moves * 0.12, 0.36)
    score -= min(queen_moves * 0.10, 0.20)
    
    if repeat_moves > 0:
        evidence.append({
            "move_no": None,
            "note": f"Moved same piece {repeat_moves} times in opening",
            "type": "repeat_piece"
        })
    
    if queen_moves > 0:
        evidence.append({
            "move_no": None,
            "note": f"Early queen moves: {queen_moves}",
            "type": "early_queen"
        })
    
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
    
    score = max(0, min(1, score))
    
    if score >= 0.75:
        plan_signal = "STUCK_TO_PLAN"
    elif score >= 0.45:
        plan_signal = "NO_CLEAR_PLAN"
    else:
        plan_signal = "ABANDONED"
    
    return score, plan_break_move, plan_signal, evidence


def _count_repeat_piece_moves(moves: List[Dict]) -> int:
    """Count repeat piece moves in opening"""
    piece_moves = {}
    repeats = 0
    
    for m in moves:
        uci = m.get("move_uci") or m.get("uci") or ""
        if len(uci) >= 4:
            from_sq = uci[:2]
            piece_moves[from_sq] = piece_moves.get(from_sq, 0) + 1
            if piece_moves[from_sq] >= 2:
                repeats += 1
    
    return repeats


def _count_piece_moves(moves: List[Dict], piece: str) -> int:
    """Count moves of a specific piece type"""
    count = 0
    for m in moves:
        san = m.get("move") or m.get("san") or ""
        if san.startswith(piece):
            count += 1
    return count


def _compute_decision_stability(user_moves: List[Dict]) -> Tuple[float, float, Optional[int], bool, List[Dict]]:
    """Compute decision stability metrics"""
    evidence = []
    has_clock = any(m.get("clock_before_ms") or m.get("clock") for m in user_moves)
    
    if has_clock:
        low_time_moves = sum(1 for m in user_moves if (m.get("clock_before_ms") or 999999) <= 30000)
        very_fast_moves = sum(1 for m in user_moves if (m.get("think_time_ms") or 999999) <= 2000)
        time_pressure_index = min(1, (0.6 * low_time_moves + 0.4 * very_fast_moves) / max(1, len(user_moves)))
    else:
        time_pressure_index = 0.35
    
    tilt_index = 0.0
    collapse_move = None
    
    first_blunder_idx = None
    for i, m in enumerate(user_moves):
        if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= CP_BLUNDER:
            first_blunder_idx = i
            break
    
    if first_blunder_idx is not None:
        before_moves = user_moves[max(0, first_blunder_idx - 6):first_blunder_idx]
        after_moves = user_moves[first_blunder_idx + 1:first_blunder_idx + 7]
        
        avg_before = sum(m.get("cp_loss", 0) for m in before_moves) / max(1, len(before_moves))
        avg_after = sum(m.get("cp_loss", 0) for m in after_moves) / max(1, len(after_moves))
        
        tilt_raw = (avg_after - avg_before) / 200.0
        tilt_index = max(0, min(1, tilt_raw))
        
        for m in after_moves:
            if m.get("cp_loss", 0) >= 250:
                collapse_move = m.get("move_number")
                evidence.append({
                    "move_no": collapse_move,
                    "note": f"Collapse after blunder (lost {m.get('cp_loss', 0)}cp)",
                    "type": "collapse"
                })
                break
    
    if time_pressure_index >= 0.6:
        evidence.append({"move_no": None, "note": "High time pressure detected", "type": "time_pressure"})
    
    if tilt_index >= 0.4:
        evidence.append({
            "move_no": user_moves[first_blunder_idx].get("move_number") if first_blunder_idx else None,
            "note": "Tilt pattern: errors escalated after first blunder",
            "type": "tilt"
        })
    
    return time_pressure_index, tilt_index, collapse_move, has_clock, evidence


def _tag_leaks_for_game(features: BehaviorFeatures, user_moves: List[Dict]) -> Dict[str, int]:
    """Tag behavioral leaks for a single game"""
    tags = {}
    
    if features.opening_plan_score < 0.45:
        tags["OPENING_WANDER"] = 1
    
    big_blunders = sum(1 for m in user_moves if m.get("cp_loss", 0) >= 300)
    if big_blunders >= 1:
        tags["TACTICAL_BLINDNESS"] = big_blunders
    
    if features.time_pressure_index >= 0.6 and features.tilt_index >= 0.3:
        tags["TIME_PANIC"] = 1
    
    if _had_winning_then_threw(user_moves):
        tags["CONVERSION_ISSUE"] = 1
    
    if _had_losing_then_recovered(user_moves):
        tags["COMEBACK_RESILIENCE"] = 1
    
    return tags


def _had_winning_then_threw(user_moves: List[Dict]) -> bool:
    """Check if user was winning then threw"""
    was_winning = False
    for m in user_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        if eval_before >= 2.0:
            was_winning = True
        if was_winning and eval_after <= 0:
            return True
    return False


def _had_losing_then_recovered(user_moves: List[Dict]) -> bool:
    """Check if user was losing then recovered"""
    was_losing = False
    for m in user_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        if eval_before <= -2.0:
            was_losing = True
        if was_losing and eval_after >= -0.5:
            return True
    return False


def _compute_leak_trends(history_games: List[Dict], user_color: str) -> Dict[str, Dict]:
    """Compute leak tag trends across recent games"""
    trends = {}
    
    for tag in NEGATIVE_LEAK_TAGS + POSITIVE_LEAK_TAGS:
        trends[tag] = {"avg": 0.0, "slope": 0.0, "series": [], "games_with_tag": 0}
    
    if not history_games:
        return trends
    
    for game in history_games[-10:]:
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        game_tags = {}
        
        blunder_count = sum(1 for m in move_evals if m.get("evaluation") == "blunder" or m.get("cp_loss", 0) >= 300)
        if blunder_count >= 1:
            game_tags["TACTICAL_BLINDNESS"] = blunder_count
        
        opening_errors = sum(1 for m in move_evals if m.get("move_number", 0) <= 10 and m.get("cp_loss", 0) >= 100)
        if opening_errors >= 2:
            game_tags["OPENING_WANDER"] = 1
        
        for tag in NEGATIVE_LEAK_TAGS + POSITIVE_LEAK_TAGS:
            count = game_tags.get(tag, 0)
            trends[tag]["series"].append(count)
            if count > 0:
                trends[tag]["games_with_tag"] += 1
    
    for tag, data in trends.items():
        series = data["series"]
        if series:
            data["avg"] = sum(series) / len(series)
            if len(series) >= 4:
                first_half = sum(series[:len(series)//2]) / (len(series)//2)
                second_half = sum(series[len(series)//2:]) / (len(series) - len(series)//2)
                data["slope"] = second_half - first_half
    
    return trends


def _determine_game_quality(features: BehaviorFeatures) -> str:
    """Determine overall game quality bucket"""
    if features.blunder_count == 0 and features.mistake_count <= 2:
        return "GOOD"
    elif features.blunder_count >= 3 or features.mistake_count >= 5:
        return "BAD"
    return "MIXED"
