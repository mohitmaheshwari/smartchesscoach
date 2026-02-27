"""
Narrative Engine Module

Generates deterministic, data-backed coaching narratives.

Rules:
- ALWAYS produce: 1 Progress Signal, 1 Core Problem, 1 Root Cause, 1 Historical Anchor
- NEVER use vague words like "often", "frequently", "consistent pattern"
- MUST include real numbers: "4 of your last 6 games", "3 of last 5 mistakes"

This replaces generic AI-speak with precise coaching language.
"""

from typing import Dict, List, Optional, Tuple
from .context_enricher import get_root_cause_description


def build_behavioral_narrative(
    features,
    scorecard: Dict,
    history_games: List[Dict],
    stagnation: bool = False
) -> Tuple[str, str]:
    """
    Build headline and rich insight with precise, data-backed language.
    
    Returns:
        (headline, rich_insight)
    """
    # 1. Detect progress signal
    progress_signal = _detect_progress_signal(features, scorecard)
    
    # 2. Detect core problem
    core_problem = _detect_core_problem(features, scorecard)
    
    # 3. Get root cause
    root_cause = features.root_cause or "CALCULATION_GAP"
    
    # 4. Compute historical anchor (real numbers)
    historical_anchor = _compute_historical_anchor(features, history_games, core_problem)
    
    # 5. Build headline
    headline = _build_headline(progress_signal, core_problem, root_cause, stagnation)
    
    # 6. Build rich insight
    rich_insight = _build_rich_insight(
        progress_signal, core_problem, root_cause, 
        historical_anchor, features, scorecard
    )
    
    return headline, rich_insight


def _detect_progress_signal(features, scorecard: Dict) -> Optional[str]:
    """
    Detect the strongest progress signal to highlight.
    
    Returns None if all scores < 50.
    """
    # Find strongest dimension
    best_score = 0
    best_key = None
    
    for key, item in scorecard.items():
        score = item.score if hasattr(item, 'score') else item.get('score', 0)
        if score >= 75 and score > best_score:
            best_score = score
            best_key = key
    
    if best_key is None:
        return None
    
    # Generate progress signal text
    progress_signals = {
        "plan_discipline": "Your opening discipline is now stable.",
        "decision_stability": "You stayed calm and stable this game.",
        "pattern_persistence": "Your recurring patterns are reducing.",
        "coach_compliance": "You applied previous advice correctly this game.",
        "learning_velocity": "Your improvement rate is accelerating.",
    }
    
    return progress_signals.get(best_key)


def _detect_core_problem(features, scorecard: Dict) -> str:
    """
    Detect the core problem to address (priority order).
    
    Returns one of:
    - DECISION_STABILITY
    - PLAN_DISCIPLINE
    - COACH_COMPLIANCE
    - REPEATING_LEAK
    - LEARNING_STAGNATION
    - NONE
    """
    # Priority order
    priority_checks = [
        ("decision_stability", "DECISION_STABILITY"),
        ("plan_discipline", "PLAN_DISCIPLINE"),
        ("coach_compliance", "COACH_COMPLIANCE"),
        ("pattern_persistence", "REPEATING_LEAK"),
        ("learning_velocity", "LEARNING_STAGNATION"),
    ]
    
    for key, problem in priority_checks:
        item = scorecard.get(key, {})
        label = item.label if hasattr(item, 'label') else item.get('label', '')
        if label == "Concern":
            return problem
    
    # Check for tactical errors
    if features.blunder_count >= 2:
        return "TACTICAL_ERRORS"
    
    return "NONE"


def _compute_historical_anchor(
    features,
    history_games: List[Dict],
    core_problem: str
) -> Dict:
    """
    Compute REAL NUMBERS for historical anchoring.
    
    Returns:
        {
            "games_checked": 6,
            "games_with_problem": 4,
            "time_triggered_games": 3,
            "pattern_sentence": "This happened in 4 of your last 6 games."
        }
    """
    if not history_games:
        return {
            "games_checked": 0,
            "games_with_problem": 0,
            "time_triggered_games": 0,
            "pattern_sentence": None,
        }
    
    games_to_check = min(len(history_games), 6)
    recent_games = history_games[:games_to_check]
    
    # Count games with similar problems
    games_with_problem = 0
    time_triggered_games = 0
    
    for game in recent_games:
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        # Check for similar problem
        if core_problem == "DECISION_STABILITY":
            # Check for tilt pattern (multiple blunders in sequence)
            blunders = [m for m in move_evals if m.get("evaluation") == "blunder"]
            if len(blunders) >= 2:
                games_with_problem += 1
        
        elif core_problem == "PLAN_DISCIPLINE":
            # Check for opening issues
            opening_errors = sum(1 for m in move_evals if m.get("move_number", 0) <= 10 and m.get("cp_loss", 0) >= 100)
            if opening_errors >= 2:
                games_with_problem += 1
        
        elif core_problem in ["REPEATING_LEAK", "TACTICAL_ERRORS"]:
            # Check for tactical blindness
            big_blunders = sum(1 for m in move_evals if m.get("cp_loss", 0) >= 300)
            if big_blunders >= 1:
                games_with_problem += 1
        
        # Check for time-triggered errors
        time_errors = sum(1 for m in move_evals 
                        if m.get("cp_loss", 0) >= 150 
                        and m.get("clock_before_ms") 
                        and m.get("clock_before_ms") <= 30000)
        if time_errors >= 1:
            time_triggered_games += 1
    
    # Build pattern sentence with REAL NUMBERS
    pattern_sentence = None
    if games_with_problem >= 2:
        pattern_sentence = f"This happened in {games_with_problem} of your last {games_to_check} games."
    
    if features.root_cause == "TIME_TRIGGERED" and time_triggered_games >= 2:
        pattern_sentence = f"Time-triggered errors appeared in {time_triggered_games} of your last {games_to_check} games."
    
    return {
        "games_checked": games_to_check,
        "games_with_problem": games_with_problem,
        "time_triggered_games": time_triggered_games,
        "pattern_sentence": pattern_sentence,
    }


def _build_headline(
    progress_signal: Optional[str],
    core_problem: str,
    root_cause: str,
    stagnation: bool
) -> str:
    """
    Build the main headline.
    
    Rules:
    - If stagnation, use firm tone
    - If progress + problem, acknowledge both
    - Be specific about root cause
    """
    
    # Stagnation override
    if stagnation:
        return "We are stuck in the same loop — this won't fix itself."
    
    # Progress + problem
    if progress_signal and core_problem != "NONE":
        # Combine progress with problem
        problem_phrases = {
            "DECISION_STABILITY": "time pressure is still breaking your decisions",
            "PLAN_DISCIPLINE": "opening discipline needs attention",
            "REPEATING_LEAK": "the same pattern keeps appearing",
            "TACTICAL_ERRORS": "tactical errors are still the main leak",
            "COACH_COMPLIANCE": "the advice isn't being applied yet",
            "LEARNING_STAGNATION": "progress has stalled",
        }
        problem_phrase = problem_phrases.get(core_problem, "one issue needs attention")
        
        # Extract the positive part
        if "opening discipline" in progress_signal.lower():
            return f"Your opening discipline is improving — but {problem_phrase}."
        elif "calm" in progress_signal.lower():
            return f"You stayed calmer this game — but {problem_phrase}."
        else:
            return f"Good progress — but {problem_phrase}."
    
    # Progress only
    if progress_signal and core_problem == "NONE":
        return "Clear progress — your play was more disciplined than recent games."
    
    # Problem only (no progress)
    problem_headlines = {
        "DECISION_STABILITY": "Your ideas are fine — but decision stability is breaking your game.",
        "PLAN_DISCIPLINE": "You're drifting early — the opening plan breaks too soon.",
        "REPEATING_LEAK": "Same pattern again — we need to isolate it and fix it.",
        "TACTICAL_ERRORS": "The tactical errors are the main leak today.",
        "COACH_COMPLIANCE": "You're collecting advice but not applying it yet.",
        "LEARNING_STAGNATION": "Progress has stalled — we need a different approach.",
    }
    
    return problem_headlines.get(core_problem, "A mixed game — let's look at what happened.")


def _build_rich_insight(
    progress_signal: Optional[str],
    core_problem: str,
    root_cause: str,
    historical_anchor: Dict,
    features,
    scorecard: Dict
) -> str:
    """
    Build the 2-3 sentence rich insight with real numbers.
    
    NEVER use: "consistent pattern", "recent games", "often", "frequently"
    ALWAYS use: "4 of your last 6 games", "3 of last 5 mistakes"
    """
    parts = []
    
    # Add progress if exists
    if progress_signal:
        # Make it more specific
        if "opening" in progress_signal.lower():
            parts.append("You followed your development plan cleanly this game.")
        elif "calm" in progress_signal.lower():
            parts.append("You maintained composure longer than usual.")
        else:
            parts.append(progress_signal)
    
    # Add problem-specific insight with NUMBERS
    if core_problem == "DECISION_STABILITY":
        if features.collapse_move:
            parts.append(f"However, tactical errors occurred after move {features.collapse_move}.")
        
        # Add root cause context
        root_cause_text = get_root_cause_description(root_cause)
        parts.append(root_cause_text)
    
    elif core_problem == "PLAN_DISCIPLINE":
        if features.plan_break_move:
            parts.append(f"Your opening plan breaks around move {features.plan_break_move}.")
        if features.repeat_piece_moves > 0:
            parts.append(f"You moved the same piece {features.repeat_piece_moves} times in the opening.")
    
    elif core_problem in ["REPEATING_LEAK", "TACTICAL_ERRORS"]:
        # Root cause
        root_cause_text = get_root_cause_description(root_cause)
        parts.append(root_cause_text)
    
    elif core_problem == "NONE" and features.game_quality_bucket == "GOOD":
        parts.append("You maintained good discipline throughout.")
    
    # Add historical anchor with REAL NUMBERS
    pattern_sentence = historical_anchor.get("pattern_sentence")
    if pattern_sentence:
        parts.append(pattern_sentence)
    
    return " ".join(parts)
