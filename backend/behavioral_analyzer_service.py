"""
Behavioral Analyzer Service - Orchestrator

This is the thin orchestrator that ties together all behavioral modules.
Maximum 150 lines.

Modules orchestrated:
- feature_extractor: Extract raw behavioral features
- context_enricher: Add contextual intelligence  
- narrative_engine: Generate headline + rich insight
- mission_picker: Select root-cause matched mission
- stagnation_detector: Detect stuck-in-loop patterns
- scoring_engine: Convert features to scores
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def generate_behavioral_report(
    db,
    user_id: str,
    game_id: str
) -> Dict:
    """
    Main entry point: Generate a complete behavioral report for a game.
    
    Returns:
        BehavioralReport dict with:
        - headline: One-sentence coach insight
        - rich_insight: 2-3 sentences with numbers
        - scorecard: 5 behavioral dimensions
        - next_mission: Root-cause matched action
        - root_cause: TIME_TRIGGERED | OVERCONFIDENCE | CALCULATION_GAP | DEFENSIVE_STRESS
        - main_problem: Core problem type
        - stagnation: True if stuck in same loop
        - confidence: 0-1 reliability score
    """
    from behavioral import (
        extract_behavior_features,
        enrich_pattern_context,
        score_behavior,
        build_behavioral_narrative,
        choose_mission,
        detect_stagnation,
        store_behavioral_report,
        get_root_cause_label,
    )
    
    # 1. Load game data
    game = await db.games.find_one({"game_id": game_id, "user_id": user_id})
    if not game:
        return {"error": "Game not found"}
    
    analysis = await db.game_analyses.find_one({"game_id": game_id})
    if not analysis:
        return {"error": "Game not analyzed yet"}
    
    sf = analysis.get("stockfish_analysis", {})
    move_facts = sf.get("move_evaluations", [])
    
    # 2. Load history (last 30 games)
    history = await db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$ne": game_id}},
        {"stockfish_analysis": 1, "game_id": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(30).to_list(30)
    
    # 3. Load reflection
    reflection = await db.reflection_sessions.find_one({"game_id": game_id, "user_id": user_id})
    
    # 4. Extract features
    game_data = {
        "user_color": game.get("user_color", "white"),
        "result": game.get("result"),
        "opponent_name": game.get("opponent_name"),
    }
    features = extract_behavior_features(game_data, move_facts, history, reflection)
    
    # 5. Enrich with context (phase distribution, eval context, root cause)
    enrich_pattern_context(features, move_facts, history)
    
    # 6. Score behavior
    scorecard = score_behavior(features)
    
    # 7. Detect main problem
    main_problem = _detect_main_problem(features, scorecard)
    
    # 8. Check for stagnation
    stagnation_info = await detect_stagnation(db, user_id, main_problem)
    is_stagnated = stagnation_info.get("is_stagnated", False)
    
    # 9. Generate narrative (headline + rich insight)
    headline, rich_insight = build_behavioral_narrative(
        features, scorecard, history, stagnation=is_stagnated
    )
    
    # 10. Choose mission
    root_cause = features.root_cause or "CALCULATION_GAP"
    mission = choose_mission(features, scorecard, game_id, root_cause)
    
    # 11. Compute confidence
    confidence = _compute_confidence(
        history_count=len(history),
        has_clock=features.has_clock_data,
        has_reflection=reflection is not None
    )
    
    # 12. Store report for stagnation tracking
    await store_behavioral_report(
        db, user_id, game_id, main_problem, root_cause, headline
    )
    
    # 13. Build final report
    return {
        "game_id": game_id,
        "headline": headline,
        "rich_insight": rich_insight,
        "scorecard": {k: v.to_dict() for k, v in scorecard.items()},
        "next_mission": mission.to_dict(),
        "root_cause": root_cause,
        "root_cause_label": get_root_cause_label(root_cause),
        "main_problem": main_problem,
        "stagnation": is_stagnated,
        "stagnation_info": stagnation_info,
        "confidence": round(confidence, 2),
        "confidence_label": _get_confidence_label(confidence),
        "evidence": features.evidence,
        "contextual_patterns": features.contextual_patterns,
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


def _detect_main_problem(features, scorecard: Dict) -> str:
    """Detect core problem from scorecard"""
    priority = [
        ("decision_stability", "DECISION_STABILITY"),
        ("plan_discipline", "PLAN_DISCIPLINE"),
        ("pattern_persistence", "REPEATING_LEAK"),
    ]
    
    for key, problem in priority:
        item = scorecard.get(key)
        if item and item.label == "Concern":
            return problem
    
    if features.blunder_count >= 2:
        return "TACTICAL_ERRORS"
    
    return "NONE"


def _compute_confidence(history_count: int, has_clock: bool, has_reflection: bool) -> float:
    """Compute confidence score"""
    confidence = 0.3
    confidence += min(history_count / 20, 0.4)
    if has_clock:
        confidence += 0.2
    if has_reflection:
        confidence += 0.1
    return min(1.0, confidence)


def _get_confidence_label(confidence: float) -> str:
    """Get confidence label"""
    if confidence >= 0.7:
        return "High"
    elif confidence >= 0.45:
        return "Medium"
    return "Low"
