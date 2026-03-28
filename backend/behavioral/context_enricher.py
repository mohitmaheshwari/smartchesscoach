"""
Context Enricher Module

Enriches raw behavioral features with contextual intelligence:
- Phase distribution for each pattern
- Time pressure context
- Evaluation context (ahead/equal/behind)
- Root cause classification

This transforms category-level patterns into actionable coaching insights.
"""

from typing import Dict, List, Optional
from collections import Counter


def enrich_pattern_context(features, move_facts: List[Dict], history_games: List[Dict]) -> None:
    """
    Enrich features with contextual pattern intelligence.
    
    For each negative leak tag, attach:
    - phase distribution (opening/mid/end)
    - time pressure distribution
    - evaluation context (ahead/equal/behind)
    - trigger classification
    
    Mutates features.contextual_patterns and features.root_cause
    """
    
    # Initialize contextual patterns
    features.contextual_patterns = {}
    
    # Process error moves for context
    error_contexts = _analyze_error_contexts(features.error_moves)
    
    # Enrich each leak tag
    for tag in features.leak_tags_last_game.keys():
        context = _build_tag_context(tag, features, error_contexts)
        features.contextual_patterns[tag] = context
    
    # Determine primary root cause
    features.root_cause = _classify_root_cause(features, error_contexts)


def _analyze_error_contexts(error_moves: List[Dict]) -> Dict:
    """
    Analyze the context distribution of all errors.
    
    Returns:
        {
            "phase_distribution": {"OPENING": 2, "MIDDLEGAME": 5, "ENDGAME": 1},
            "eval_distribution": {"WINNING": 3, "EQUAL": 4, "LOSING": 1},
            "time_triggered_count": 2,
            "total_errors": 8,
            "time_trigger_ratio": 0.25,
            "dominant_phase": "MIDDLEGAME",
            "dominant_eval_context": "EQUAL"
        }
    """
    if not error_moves:
        return {
            "phase_distribution": {},
            "eval_distribution": {},
            "time_triggered_count": 0,
            "total_errors": 0,
            "time_trigger_ratio": 0.0,
            "dominant_phase": None,
            "dominant_eval_context": None,
        }
    
    phase_counts = Counter()
    eval_counts = Counter()
    time_triggered = 0
    
    for error in error_moves:
        # Phase distribution
        phase = error.get("phase", "MIDDLEGAME")
        phase_counts[phase] += 1
        
        # Evaluation context
        eval_before = error.get("eval_before", 0)
        eval_context = _classify_eval_context(eval_before)
        eval_counts[eval_context] += 1
        
        # Time trigger
        clock_ms = error.get("clock_before_ms")
        if clock_ms is not None and clock_ms <= 30000:  # Under 30 seconds
            time_triggered += 1
    
    total = len(error_moves)
    
    # Find dominant contexts
    dominant_phase = phase_counts.most_common(1)[0][0] if phase_counts else None
    dominant_eval = eval_counts.most_common(1)[0][0] if eval_counts else None
    
    return {
        "phase_distribution": dict(phase_counts),
        "eval_distribution": dict(eval_counts),
        "time_triggered_count": time_triggered,
        "total_errors": total,
        "time_trigger_ratio": time_triggered / total if total > 0 else 0.0,
        "dominant_phase": dominant_phase,
        "dominant_eval_context": dominant_eval,
    }


def _classify_eval_context(eval_before: float) -> str:
    """Classify evaluation context into WINNING/EQUAL/LOSING"""
    if eval_before > 1.5:  # +150cp
        return "WINNING"
    elif eval_before < -1.5:  # -150cp
        return "LOSING"
    return "EQUAL"


def _build_tag_context(tag: str, features, error_contexts: Dict) -> Dict:
    """
    Build contextual information for a specific leak tag.
    """
    # Base context from error analysis
    context = {
        "phase_distribution": error_contexts.get("phase_distribution", {}),
        "eval_distribution": error_contexts.get("eval_distribution", {}),
        "time_trigger_ratio": error_contexts.get("time_trigger_ratio", 0.0),
        "dominant_phase": error_contexts.get("dominant_phase"),
        "dominant_eval_context": error_contexts.get("dominant_eval_context"),
        "trigger_type": None,
    }
    
    # Classify trigger type for this tag
    context["trigger_type"] = _classify_trigger_type(
        time_trigger_ratio=context["time_trigger_ratio"],
        dominant_eval=context["dominant_eval_context"],
        tag=tag
    )
    
    return context


def _classify_trigger_type(
    time_trigger_ratio: float,
    dominant_eval: Optional[str],
    tag: str
) -> str:
    """
    Classify the root trigger for a pattern.
    
    Returns one of:
    - TIME_TRIGGERED: Errors mostly happen under time pressure
    - OVERCONFIDENCE: Errors mostly happen when winning
    - CALCULATION_GAP: Errors mostly happen in equal positions
    - DEFENSIVE_STRESS: Errors mostly happen when defending
    """
    # Time pressure is strongest signal
    if time_trigger_ratio > 0.6:
        return "TIME_TRIGGERED"
    
    # Evaluation context
    if dominant_eval == "WINNING":
        return "OVERCONFIDENCE"
    elif dominant_eval == "EQUAL":
        return "CALCULATION_GAP"
    elif dominant_eval == "LOSING":
        return "DEFENSIVE_STRESS"
    
    # Tag-specific defaults
    if tag == "TIME_PANIC":
        return "TIME_TRIGGERED"
    elif tag == "CONVERSION_ISSUE":
        return "OVERCONFIDENCE"
    elif tag == "TACTICAL_BLINDNESS":
        return "CALCULATION_GAP"
    elif tag == "OPENING_WANDER":
        return "CALCULATION_GAP"
    
    return "CALCULATION_GAP"  # Default


def _classify_root_cause(features, error_contexts: Dict) -> str:
    """
    Determine the PRIMARY root cause for this game's errors.
    
    Priority order:
    1. TIME_TRIGGERED if time_trigger_ratio > 0.6
    2. OVERCONFIDENCE if majority errors when winning
    3. CALCULATION_GAP if majority errors in equal positions
    4. DEFENSIVE_STRESS if majority errors when losing
    """
    time_ratio = error_contexts.get("time_trigger_ratio", 0.0)
    dominant_eval = error_contexts.get("dominant_eval_context")
    
    # Check time pressure first (strongest signal)
    if time_ratio > 0.6:
        return "TIME_TRIGGERED"
    
    # Check if time pressure is still significant
    if time_ratio > 0.4 and features.time_pressure_index >= 0.5:
        return "TIME_TRIGGERED"
    
    # Evaluation context
    if dominant_eval == "WINNING":
        return "OVERCONFIDENCE"
    elif dominant_eval == "EQUAL":
        return "CALCULATION_GAP"
    elif dominant_eval == "LOSING":
        return "DEFENSIVE_STRESS"
    
    # Fallback based on features
    if features.tilt_index >= 0.5:
        return "DEFENSIVE_STRESS"
    
    return "CALCULATION_GAP"


def get_root_cause_description(root_cause: str) -> str:
    """Get human-readable description of root cause"""
    descriptions = {
        "TIME_TRIGGERED": "These errors appear mostly when your clock drops below 30 seconds.",
        "OVERCONFIDENCE": "Most of these errors happen when you're already ahead.",
        "CALCULATION_GAP": "These mistakes appear in equal positions where deeper calculation was required.",
        "DEFENSIVE_STRESS": "The errors happen while defending slightly worse positions.",
    }
    return descriptions.get(root_cause, "The pattern needs further analysis.")


def get_root_cause_label(root_cause: str) -> str:
    """Get short label for root cause"""
    labels = {
        "TIME_TRIGGERED": "Time Pressure",
        "OVERCONFIDENCE": "Overconfidence",
        "CALCULATION_GAP": "Calculation Gap",
        "DEFENSIVE_STRESS": "Defensive Stress",
    }
    return labels.get(root_cause, root_cause)
