"""
Behavioral Analyzer Service - Orchestrator

This is the thin orchestrator that ties together all behavioral modules.

Modules orchestrated:
- feature_extractor: Extract raw behavioral features
- context_enricher: Add contextual intelligence  
- narrative_engine: Generate headline + rich insight
- mission_picker: Select root-cause matched mission
- stagnation_detector: Detect stuck-in-loop patterns
- scoring_engine: Convert features to scores
- advice_engine: Evaluate coach advice compliance (P1.5)
- learning_velocity: Calculate improvement speed (P1.5)
- difficulty_policy: Adaptive mission difficulty (P1.6)
- mission_templates: Difficulty-scaled mission params (P1.6)
"""

import logging
import uuid
from typing import Dict, Optional, List
from datetime import datetime, timezone

from engine_config import ENGINE_VERSION

logger = logging.getLogger(__name__)


async def generate_behavioral_report(
    db,
    user_id: str,
    game_id: str,
    historical_mode: bool = False
) -> Dict:
    """
    Main entry point: Generate a complete behavioral report for a game.
    
    Args:
        db: Database connection
        user_id: User ID
        game_id: Game ID
        historical_mode: If True, does NOT mutate advice lifecycle (no auto-create, no auto-resolve)
                        Used for historical re-analysis jobs.
    
    Returns:
        BehavioralReport dict with:
        - headline: One-sentence coach insight
        - rich_insight: 2-3 sentences with numbers
        - scorecard: 5 behavioral dimensions
        - next_mission: Root-cause matched action (or advice enforcement)
        - root_cause: TIME_TRIGGERED | OVERCONFIDENCE | CALCULATION_GAP | DEFENSIVE_STRESS
        - main_problem: Core problem type
        - stagnation: True if stuck in same loop
        - confidence: 0-1 reliability score
        - learning_velocity: 0-1 improvement speed (P1.5)
        - learner_type: FAST_ADAPTER | STEADY | TRYING_BUT_STUCK | NOT_APPLYING (P1.5)
        - coach_compliance_score: 0-100 (P1.5)
        - active_advice_count: Number of active advice (P1.5)
        - difficulty: Mission difficulty level (P1.6)
        - engine_version: Engine version used for analysis (P1.6)
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
        AdviceEngine,
        LEAK_TO_RULE,
        compute_learning_velocity,
        compute_compliance_score,
        check_advice_resolution,
        resolve_advice,
        get_active_advice_count,
    )
    from behavioral.difficulty_policy import choose_difficulty
    from behavioral.mission_templates import get_mission_params
    
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
    
    # ==================== P1.5: ADVICE EVALUATION PIPELINE ====================
    # CRITICAL: historical_mode=True prevents advice lifecycle mutations
    
    # 8. Load active advice
    active_advice = await db.coach_advice.find(
        {"user_id": user_id, "status": "ACTIVE"}
    ).to_list(10)
    
    # 9. Evaluate all advice against this game
    advice_results = AdviceEngine.evaluate_all(active_advice, features, history)
    
    # 10. Persist advice applications (upsert to avoid duplicates)
    # Note: This is safe in historical_mode - it only records evaluations
    await _persist_advice_applications(db, user_id, game_id, advice_results)
    
    # 11-12: ONLY if NOT historical_mode - advice lifecycle mutations
    if not historical_mode:
        # 11. Check for advice resolution (followed 4 consecutive times)
        for advice in active_advice:
            if await check_advice_resolution(db, advice["advice_id"]):
                await resolve_advice(db, advice["advice_id"])
                logger.info(f"Resolved advice {advice['advice_id']} for user {user_id}")
        
        # 12. Auto-create advice for persistent leak patterns
        await _auto_create_advice(db, user_id, features, active_advice)
    else:
        logger.debug(f"Historical mode: skipping advice lifecycle mutations for game {game_id}")
    
    # 13. Load advice applications for learning velocity (last 10 games)
    applications = await db.advice_applications.find(
        {"user_id": user_id}
    ).sort("evaluated_at", -1).limit(50).to_list(50)
    
    # 14. Compute learning velocity
    velocity_result = compute_learning_velocity(applications, features.leak_trends)
    
    # 15. Update coach_compliance score in scorecard
    scorecard["coach_compliance"].score = compute_compliance_score(applications)
    scorecard["coach_compliance"].label = _get_compliance_label(scorecard["coach_compliance"].score)
    scorecard["coach_compliance"].why = _get_compliance_why(velocity_result)
    
    # 16. Update learning_velocity score in scorecard
    scorecard["learning_velocity"].score = int(velocity_result.velocity * 100)
    scorecard["learning_velocity"].label = _get_velocity_label(velocity_result.learner_type)
    scorecard["learning_velocity"].why = f"{velocity_result.learner_type.replace('_', ' ').title()}"
    
    # ==================== END P1.5 ====================
    
    # 17. Check for stagnation
    stagnation_info = await detect_stagnation(db, user_id, main_problem)
    is_stagnated = stagnation_info.get("is_stagnated", False)
    
    # ==================== P1.7: MISSION FEEDBACK LOOP ====================
    
    # 18. Get last mission result for narrative reference
    from behavioral.mission_lifecycle import get_last_mission_result, get_recent_mission_validations
    
    last_mission = await get_last_mission_result(db, user_id) if not historical_mode else None
    recent_mission_validations = await get_recent_mission_validations(db, user_id, limit=3) if not historical_mode else None
    
    # 19. Re-compute velocity with mission validation adjustment (smoothed)
    previous_velocity = user_profile.get("last_learning_velocity") if user_profile else None
    velocity_result = compute_learning_velocity(
        applications, 
        features.leak_trends,
        previous_velocity=previous_velocity,
        mission_validations=recent_mission_validations
    )
    
    # 20. Generate narrative (headline + rich insight) - now with mission reference
    headline, rich_insight = build_behavioral_narrative(
        features, scorecard, history, 
        stagnation=is_stagnated,
        learner_type=velocity_result.learner_type,
        advice_stats=velocity_result.advice_stats,
        last_mission_result=last_mission  # P1.7
    )
    
    # 21. Compute confidence
    confidence = _compute_confidence(
        history_count=len(history),
        has_clock=features.has_clock_data,
        has_reflection=reflection is not None,
        has_advice_data=len(applications) > 0
    )
    
    # ==================== P1.6: ADAPTIVE DIFFICULTY ====================
    
    # 20. Load recent behavioral reports for collapse detection
    recent_reports = await db.behavioral_reports.find(
        {"user_id": user_id}
    ).sort("computed_at", -1).limit(3).to_list(3)
    
    # 21. Get user's difficulty profile
    user_profile = await db.users.find_one({"user_id": user_id}) or {}
    consecutive_hard_failures = user_profile.get("consecutive_hard_failures", 0)
    
    # 22. Choose difficulty based on learner_type, stagnation, confidence, recent collapses
    difficulty_result = choose_difficulty(
        learner_type=velocity_result.learner_type,
        stagnation=is_stagnated,
        confidence=confidence,
        recent_games=recent_reports,
        consecutive_hard_failures=consecutive_hard_failures
    )
    
    # 23. Choose mission - priority: violated high-severity advice > root cause > generic
    root_cause = features.root_cause or "CALCULATION_GAP"
    violated_advice = [r for r in advice_results if r.get("outcome") == "VIOLATED"]
    
    if violated_advice:
        # Sort by severity (highest first)
        violated_advice.sort(key=lambda x: x.get("severity_weight", 0), reverse=True)
        mission = _build_advice_enforcement_mission(
            violated_advice[0], game_id, difficulty_result.difficulty
        )
    else:
        mission = choose_mission(
            features, scorecard, game_id, root_cause, 
            difficulty=difficulty_result.difficulty
        )
    
    # Apply difficulty-specific parameters to mission
    mission_params = get_mission_params(
        mission.type if hasattr(mission, 'type') else mission.get("type", ""),
        difficulty_result.difficulty
    )
    
    # ==================== END P1.6 ====================
    
    # 24. Store report for stagnation tracking
    await store_behavioral_report(
        db, user_id, game_id, main_problem, root_cause, headline
    )
    
    # 25. Get current active advice count
    active_count = await get_active_advice_count(db, user_id)
    
    # 26. Build final report
    return {
        "game_id": game_id,
        "headline": headline,
        "rich_insight": rich_insight,
        "scorecard": {k: v.to_dict() for k, v in scorecard.items()},
        "next_mission": _enrich_mission_with_difficulty(mission, mission_params, difficulty_result),
        "root_cause": root_cause,
        "root_cause_label": get_root_cause_label(root_cause),
        "main_problem": main_problem,
        "stagnation": is_stagnated,
        "stagnation_info": stagnation_info,
        "confidence": round(confidence, 2),
        "confidence_label": _get_confidence_label(confidence),
        # P1.5 additions
        "learning_velocity": velocity_result.velocity,
        "learner_type": velocity_result.learner_type,
        "coach_compliance_score": scorecard["coach_compliance"].score,
        "active_advice_count": active_count,
        "advice_results": advice_results,
        "advice_stats": velocity_result.advice_stats,
        # P1.6 additions
        "difficulty": difficulty_result.difficulty,
        "difficulty_reason": difficulty_result.reason,
        "difficulty_guardrail": difficulty_result.guardrail_triggered,
        "engine_version": ENGINE_VERSION,
        "historical_mode": historical_mode,
        # Debug info
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


async def _persist_advice_applications(
    db,
    user_id: str,
    game_id: str,
    advice_results: List[Dict]
) -> None:
    """Persist advice evaluation results to DB"""
    for result in advice_results:
        application = {
            "application_id": str(uuid.uuid4()),
            "advice_id": result.get("advice_id"),
            "user_id": user_id,
            "game_id": game_id,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "outcome": result.get("outcome"),
            "applicable": result.get("applicable", False),
            "evidence": result.get("evidence", {}),
            "severity_weight": result.get("severity_weight", 3),
        }
        
        # Upsert to avoid duplicates
        await db.advice_applications.update_one(
            {"advice_id": result.get("advice_id"), "game_id": game_id},
            {"$set": application},
            upsert=True
        )


async def _auto_create_advice(
    db,
    user_id: str,
    features,
    active_advice: List[Dict]
) -> None:
    """Auto-create advice for persistent leak patterns"""
    from behavioral import AdviceEngine, LEAK_TO_RULE
    
    # Check each leak tag
    for leak_tag, rule_code in LEAK_TO_RULE.items():
        if AdviceEngine.should_create_advice(rule_code, features.leak_trends, active_advice):
            advice = AdviceEngine.create_advice_for_leak(user_id, rule_code)
            await db.coach_advice.insert_one(advice)
            logger.info(f"Auto-created advice {rule_code} for user {user_id}")


def _build_advice_enforcement_mission(
    violated_advice: Dict, 
    game_id: str,
    difficulty: str = "STANDARD"
) -> Dict:
    """Build a mission specifically to enforce violated advice"""
    from behavioral import Mission
    from behavioral.mission_templates import get_mission_params
    
    rule_code = violated_advice.get("rule_code", "")
    text = violated_advice.get("text", "")
    
    # Get difficulty-specific parameters
    params = get_mission_params("ADVICE_ENFORCEMENT", difficulty)
    
    # Custom mission text based on rule and difficulty
    instruction_map = {
        "OPENING_REPEAT_PIECE": "Your only goal next game: avoid moving the same piece twice in the opening.",
        "TIME_PANIC": "Your only goal next game: under 30 seconds, pause and pick the safest move.",
        "HANGING_PIECE": "Your only goal next game: before every move, scan for hanging pieces.",
        "EARLY_QUEEN": "Your only goal next game: develop knights and bishops before the queen.",
        "OPENING_WANDER": "Your only goal next game: stick to your opening plan for 10 moves.",
        "CONVERSION_ISSUE": "Your only goal next game: when ahead, simplify and don't overpress.",
    }
    
    base_instruction = instruction_map.get(rule_code, f"Focus on: {text}")
    suffix = params.get("instruction_suffix", "")
    
    return Mission(
        type="ADVICE_ENFORCEMENT",
        title="Fix This First",
        instruction=f"{base_instruction} {suffix}".strip(),
        payload={
            "game_id": game_id,
            "advice_id": violated_advice.get("advice_id"),
            "rule_code": rule_code,
            "focus": "advice_enforcement",
            "difficulty": difficulty,
            "checkpoint_reminder": params.get("checkpoint_reminder", False),
            "checkpoint_move": params.get("checkpoint_move"),
            "require_annotation": params.get("require_annotation", False),
        }
    )


def _enrich_mission_with_difficulty(mission, mission_params: Dict, difficulty_result) -> Dict:
    """Enrich mission with difficulty-specific parameters"""
    base = mission.to_dict() if hasattr(mission, 'to_dict') else dict(mission)
    
    # Add difficulty info
    base["difficulty"] = difficulty_result.difficulty
    base["difficulty_reason"] = difficulty_result.reason
    
    # Add mission-specific params
    if mission_params:
        base["timebox_seconds"] = mission_params.get("timebox_seconds")
        base["required_reps"] = mission_params.get("required_reps")
        base["positions"] = mission_params.get("positions")
        base["params"] = mission_params
    
    return base


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


def _compute_confidence(
    history_count: int, 
    has_clock: bool, 
    has_reflection: bool,
    has_advice_data: bool = False
) -> float:
    """Compute confidence score"""
    confidence = 0.25
    confidence += min(history_count / 20, 0.35)
    if has_clock:
        confidence += 0.2
    if has_reflection:
        confidence += 0.1
    if has_advice_data:
        confidence += 0.1
    return min(1.0, confidence)


def _get_confidence_label(confidence: float) -> str:
    """Get confidence label"""
    if confidence >= 0.7:
        return "High"
    elif confidence >= 0.45:
        return "Medium"
    return "Low"


def _get_compliance_label(score: int) -> str:
    """Get compliance label from score"""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 45:
        return "Mixed"
    return "Concern"


def _get_velocity_label(learner_type: str) -> str:
    """Get label for velocity based on learner type"""
    labels = {
        "FAST_ADAPTER": "Excellent",
        "STEADY": "Good",
        "TRYING_BUT_STUCK": "Mixed",
        "NOT_APPLYING": "Concern"
    }
    return labels.get(learner_type, "Mixed")


def _get_compliance_why(velocity_result) -> str:
    """Get explanation for compliance score"""
    stats = velocity_result.advice_stats
    if stats.get("applicable", 0) == 0:
        return "No advice to evaluate yet"
    
    followed = stats.get("followed", 0)
    applicable = stats.get("applicable", 0)
    
    if followed == applicable:
        return f"Applied {followed}/{applicable} advice"
    elif followed > applicable / 2:
        return f"Applied {followed}/{applicable} advice"
    else:
        return f"Only {followed}/{applicable} advice applied"
