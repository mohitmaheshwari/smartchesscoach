"""
Mission Validation Module

Validates mission effectiveness by measuring actual behavioral change
across a window of applicable games.

Key Concepts:
- VALIDATION_WINDOW_GAMES = 3 (not just next game)
- Only validates when scenario is APPLICABLE
- Returns validation_score (0-1) and applicability flag

Mission Types and Validation:
- TIME_DECISION_DRILL → tilt_index, collapse_move timing
- OPENING_REPEAT_PIECE → repeat_piece_moves
- DEFENSIVE_RESILIENCE_DRILL → defensive errors
- CANDIDATE_MOVE_DRILL → calculation errors
- ADVICE_ENFORCEMENT → was advice followed?
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone


# Validation window size (not just next game)
VALIDATION_WINDOW_GAMES = 3


@dataclass
class ValidationResult:
    """Result of mission validation"""
    applicable: bool  # Was the scenario relevant in the validation window?
    score: float  # 0.0 - 1.0 improvement score (only meaningful if applicable)
    confidence: float  # How confident are we in this score
    validation_games_used: List[str]  # Game IDs used for validation
    metrics: Dict  # Raw metrics for debugging
    reason: str  # Human-readable explanation
    
    def to_dict(self):
        return {
            "applicable": self.applicable,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 2),
            "validation_games_used": self.validation_games_used,
            "metrics": self.metrics,
            "reason": self.reason
        }


async def validate_mission_effect(
    db,
    user_id: str,
    mission: Dict,
    pre_mission_games: List[Dict] = None
) -> ValidationResult:
    """
    Validate if a mission had measurable effect on user's behavior.
    
    Uses VALIDATION_WINDOW_GAMES (3) applicable games, not just next game.
    
    Args:
        db: Database connection
        user_id: User ID
        mission: Mission document from mission_history
        pre_mission_games: Optional pre-computed games before mission
        
    Returns:
        ValidationResult with applicable, score, and metadata
    """
    mission_type = mission.get("mission_type")
    mission_created = mission.get("created_at")
    
    # Load games AFTER mission was started
    post_games = await _load_post_mission_games(
        db, user_id, mission_created, limit=VALIDATION_WINDOW_GAMES * 2
    )
    
    if not post_games:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[],
            metrics={"reason": "No games played after mission"},
            reason="No games played yet"
        )
    
    # Load pre-mission baseline (last 3 games before mission)
    if pre_mission_games is None:
        pre_mission_games = await _load_pre_mission_games(
            db, user_id, mission_created, limit=3
        )
    
    # Route to mission-specific validator
    validator = _get_validator(mission_type)
    return await validator(db, user_id, mission, pre_mission_games, post_games)


def _get_validator(mission_type: str):
    """Get the appropriate validator function for a mission type"""
    validators = {
        "TIME_DECISION_DRILL": _validate_time_decision,
        "CANDIDATE_MOVE_DRILL": _validate_candidate_move,
        "DEFENSIVE_RESILIENCE_DRILL": _validate_defensive_resilience,
        "CONVERSION_DISCIPLINE_DRILL": _validate_conversion,
        "ADVICE_ENFORCEMENT": _validate_advice_enforcement,
        "OPENING_DISCIPLINE": _validate_opening_discipline,
        "STABILITY_DRILL": _validate_stability,
        "TACTICAL_FUEL": _validate_tactical,
    }
    return validators.get(mission_type, _validate_generic)


# ==================== TIME DECISION DRILL VALIDATOR ====================

async def _validate_time_decision(
    db, user_id: str, mission: Dict, 
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """
    Validate TIME_DECISION_DRILL effectiveness.
    
    Applicable: When user had time pressure (clock < 30s) in post games.
    Metrics: tilt_index, collapse_move timing
    """
    # Filter for applicable games (had time pressure)
    applicable_post = [g for g in post_games if _had_time_pressure(g)]
    
    if not applicable_post:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[g.get("game_id") for g in post_games[:3]],
            metrics={"reason": "No time pressure in recent games"},
            reason="No time pressure situations to validate"
        )
    
    # Get applicable games (up to window size)
    validation_games = applicable_post[:VALIDATION_WINDOW_GAMES]
    game_ids = [g.get("game_id") for g in validation_games]
    
    # Compute pre-mission baseline
    pre_tilt_avg = _avg_metric(pre_games, "tilt_index", default=0.5)
    pre_time_pressure_avg = _avg_metric(pre_games, "time_pressure_index", default=0.5)
    
    # Compute post-mission metrics
    post_tilt_avg = _avg_metric(validation_games, "tilt_index", default=0.5)
    post_time_pressure_avg = _avg_metric(validation_games, "time_pressure_index", default=0.5)
    
    # Calculate improvement (lower tilt = better)
    tilt_improvement = max(0, pre_tilt_avg - post_tilt_avg)
    time_improvement = max(0, pre_time_pressure_avg - post_time_pressure_avg)
    
    # Normalize to 0-1 score
    score = min(1.0, (tilt_improvement * 2) + (time_improvement * 1))
    
    # Confidence based on sample size
    confidence = min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES)
    
    return ValidationResult(
        applicable=True,
        score=score,
        confidence=confidence,
        validation_games_used=game_ids,
        metrics={
            "pre_tilt_avg": round(pre_tilt_avg, 2),
            "post_tilt_avg": round(post_tilt_avg, 2),
            "tilt_improvement": round(tilt_improvement, 2),
            "time_improvement": round(time_improvement, 2),
            "games_evaluated": len(validation_games)
        },
        reason=_get_time_decision_reason(score, tilt_improvement)
    )


# ==================== ADVICE ENFORCEMENT VALIDATOR ====================

async def _validate_advice_enforcement(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """
    Validate ADVICE_ENFORCEMENT mission.
    
    Applicable: When the specific advice rule is applicable in post games.
    Metrics: Was the advice followed in applicable games?
    """
    advice_id = mission.get("payload", {}).get("advice_id")
    rule_code = mission.get("payload", {}).get("rule_code")
    
    if not advice_id:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[],
            metrics={"reason": "No advice_id in mission"},
            reason="Missing advice reference"
        )
    
    # Load advice applications for post-mission games
    game_ids = [g.get("game_id") for g in post_games[:VALIDATION_WINDOW_GAMES]]
    
    applications = await db.advice_applications.find({
        "advice_id": advice_id,
        "game_id": {"$in": game_ids}
    }).to_list(VALIDATION_WINDOW_GAMES)
    
    # Filter for applicable applications
    applicable_apps = [a for a in applications if a.get("applicable", False)]
    
    if not applicable_apps:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=game_ids,
            metrics={"reason": f"Rule {rule_code} not applicable in recent games"},
            reason="Advice rule not triggered in recent games"
        )
    
    # Count followed vs violated
    followed = sum(1 for a in applicable_apps if a.get("outcome") == "FOLLOWED")
    total = len(applicable_apps)
    
    score = followed / total if total > 0 else 0.0
    confidence = min(1.0, total / VALIDATION_WINDOW_GAMES)
    
    return ValidationResult(
        applicable=True,
        score=score,
        confidence=confidence,
        validation_games_used=[a.get("game_id") for a in applicable_apps],
        metrics={
            "rule_code": rule_code,
            "followed": followed,
            "violated": total - followed,
            "total_applicable": total
        },
        reason=_get_advice_reason(score, followed, total)
    )


# ==================== CANDIDATE MOVE VALIDATOR ====================

async def _validate_candidate_move(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """
    Validate CANDIDATE_MOVE_DRILL effectiveness.
    
    Applicable: Always (unless game too short).
    Metrics: Calculation errors, blunder count in equal positions.
    """
    # Filter valid games
    valid_post = [g for g in post_games if g.get("total_moves", 0) >= 15]
    
    if not valid_post:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[],
            metrics={"reason": "No full-length games to evaluate"},
            reason="No full games played yet"
        )
    
    validation_games = valid_post[:VALIDATION_WINDOW_GAMES]
    game_ids = [g.get("game_id") for g in validation_games]
    
    # Compare blunder counts
    pre_blunders_avg = _avg_metric(pre_games, "blunder_count", default=2)
    post_blunders_avg = _avg_metric(validation_games, "blunder_count", default=2)
    
    # Calculate improvement (fewer blunders = better)
    improvement = max(0, pre_blunders_avg - post_blunders_avg)
    score = min(1.0, improvement / 2)  # 2 fewer blunders = perfect score
    
    confidence = min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES)
    
    return ValidationResult(
        applicable=True,
        score=score,
        confidence=confidence,
        validation_games_used=game_ids,
        metrics={
            "pre_blunders_avg": round(pre_blunders_avg, 1),
            "post_blunders_avg": round(post_blunders_avg, 1),
            "improvement": round(improvement, 1)
        },
        reason=_get_calculation_reason(score, improvement)
    )


# ==================== DEFENSIVE RESILIENCE VALIDATOR ====================

async def _validate_defensive_resilience(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """
    Validate DEFENSIVE_RESILIENCE_DRILL.
    
    Applicable: When user was in worse position.
    Metrics: Collapse behavior when defending.
    """
    # Filter for games where user was defending
    applicable_post = [g for g in post_games if _had_defensive_position(g)]
    
    if not applicable_post:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[g.get("game_id") for g in post_games[:3]],
            metrics={"reason": "No defensive situations in recent games"},
            reason="No defensive positions to validate"
        )
    
    validation_games = applicable_post[:VALIDATION_WINDOW_GAMES]
    game_ids = [g.get("game_id") for g in validation_games]
    
    # Compare defensive collapse rates
    pre_collapse = _avg_metric(pre_games, "tilt_index", default=0.5)
    post_collapse = _avg_metric(validation_games, "tilt_index", default=0.5)
    
    improvement = max(0, pre_collapse - post_collapse)
    score = min(1.0, improvement * 2)
    confidence = min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES)
    
    return ValidationResult(
        applicable=True,
        score=score,
        confidence=confidence,
        validation_games_used=game_ids,
        metrics={
            "pre_collapse_rate": round(pre_collapse, 2),
            "post_collapse_rate": round(post_collapse, 2),
            "improvement": round(improvement, 2)
        },
        reason=_get_defensive_reason(score, improvement)
    )


# ==================== CONVERSION VALIDATOR ====================

async def _validate_conversion(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """
    Validate CONVERSION_DISCIPLINE_DRILL.
    
    Applicable: When user had winning advantage.
    Metrics: Did they convert or throw?
    """
    # Filter for games where user had winning position
    applicable_post = [g for g in post_games if _had_winning_position(g)]
    
    if not applicable_post:
        return ValidationResult(
            applicable=False,
            score=0.0,
            confidence=0.0,
            validation_games_used=[g.get("game_id") for g in post_games[:3]],
            metrics={"reason": "No winning positions in recent games"},
            reason="No conversion situations to validate"
        )
    
    validation_games = applicable_post[:VALIDATION_WINDOW_GAMES]
    game_ids = [g.get("game_id") for g in validation_games]
    
    # Check for conversion issues
    conversion_issues = sum(
        1 for g in validation_games 
        if g.get("leak_tags", {}).get("CONVERSION_ISSUE", 0) > 0
    )
    
    score = 1.0 - (conversion_issues / len(validation_games))
    confidence = min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES)
    
    return ValidationResult(
        applicable=True,
        score=score,
        confidence=confidence,
        validation_games_used=game_ids,
        metrics={
            "games_with_winning": len(validation_games),
            "conversion_issues": conversion_issues
        },
        reason=_get_conversion_reason(score, conversion_issues, len(validation_games))
    )


# ==================== GENERIC VALIDATORS ====================

async def _validate_opening_discipline(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """Validate opening discipline improvement"""
    valid_post = [g for g in post_games if g.get("total_moves", 0) >= 10]
    
    if not valid_post:
        return ValidationResult(
            applicable=False, score=0.0, confidence=0.0,
            validation_games_used=[], metrics={},
            reason="No full games to evaluate"
        )
    
    validation_games = valid_post[:VALIDATION_WINDOW_GAMES]
    game_ids = [g.get("game_id") for g in validation_games]
    
    pre_plan_score = _avg_metric(pre_games, "opening_plan_score", default=0.5)
    post_plan_score = _avg_metric(validation_games, "opening_plan_score", default=0.5)
    
    improvement = max(0, post_plan_score - pre_plan_score)
    score = min(1.0, improvement * 2)
    
    return ValidationResult(
        applicable=True, score=score,
        confidence=min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES),
        validation_games_used=game_ids,
        metrics={"pre_plan_score": pre_plan_score, "post_plan_score": post_plan_score},
        reason=f"Opening discipline {'improved' if score >= 0.5 else 'unchanged'}"
    )


async def _validate_stability(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """Validate stability drill"""
    return await _validate_time_decision(db, user_id, mission, pre_games, post_games)


async def _validate_tactical(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """Validate tactical drill"""
    return await _validate_candidate_move(db, user_id, mission, pre_games, post_games)


async def _validate_generic(
    db, user_id: str, mission: Dict,
    pre_games: List[Dict], post_games: List[Dict]
) -> ValidationResult:
    """Generic validation for unknown mission types"""
    if not post_games:
        return ValidationResult(
            applicable=False, score=0.0, confidence=0.0,
            validation_games_used=[], metrics={},
            reason="No games to evaluate"
        )
    
    validation_games = post_games[:VALIDATION_WINDOW_GAMES]
    
    # Compare general performance
    pre_blunders = _avg_metric(pre_games, "blunder_count", default=2)
    post_blunders = _avg_metric(validation_games, "blunder_count", default=2)
    
    improvement = max(0, pre_blunders - post_blunders)
    score = min(1.0, improvement / 2)
    
    return ValidationResult(
        applicable=True, score=score,
        confidence=min(1.0, len(validation_games) / VALIDATION_WINDOW_GAMES),
        validation_games_used=[g.get("game_id") for g in validation_games],
        metrics={"improvement": improvement},
        reason="General performance evaluated"
    )


# ==================== HELPER FUNCTIONS ====================

async def _load_post_mission_games(db, user_id: str, mission_created: str, limit: int) -> List[Dict]:
    """Load games played AFTER mission was created"""
    from behavioral import extract_behavior_features
    
    games = await db.game_analyses.find(
        {"user_id": user_id, "analyzed_at": {"$gt": mission_created}}
    ).sort("analyzed_at", 1).limit(limit).to_list(limit)
    
    # Enrich with behavioral metrics
    enriched = []
    for game in games:
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        enriched.append({
            "game_id": game.get("game_id"),
            "analyzed_at": game.get("analyzed_at"),
            "total_moves": len(move_evals),
            "blunder_count": sf.get("blunder_count", 0),
            "mistake_count": sf.get("mistake_count", 0),
            "tilt_index": _compute_tilt_from_evals(move_evals),
            "time_pressure_index": _compute_time_pressure_from_evals(move_evals),
            "opening_plan_score": _compute_opening_score(move_evals),
            "leak_tags": sf.get("leak_tags", {}),
        })
    
    return enriched


async def _load_pre_mission_games(db, user_id: str, mission_created: str, limit: int) -> List[Dict]:
    """Load games played BEFORE mission was created"""
    games = await db.game_analyses.find(
        {"user_id": user_id, "analyzed_at": {"$lt": mission_created}}
    ).sort("analyzed_at", -1).limit(limit).to_list(limit)
    
    enriched = []
    for game in games:
        sf = game.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        enriched.append({
            "game_id": game.get("game_id"),
            "analyzed_at": game.get("analyzed_at"),
            "total_moves": len(move_evals),
            "blunder_count": sf.get("blunder_count", 0),
            "mistake_count": sf.get("mistake_count", 0),
            "tilt_index": _compute_tilt_from_evals(move_evals),
            "time_pressure_index": _compute_time_pressure_from_evals(move_evals),
            "opening_plan_score": _compute_opening_score(move_evals),
            "leak_tags": sf.get("leak_tags", {}),
        })
    
    return enriched


def _had_time_pressure(game: Dict) -> bool:
    """Check if game had time pressure"""
    return game.get("time_pressure_index", 0) >= 0.3


def _had_defensive_position(game: Dict) -> bool:
    """Check if game had defensive situations"""
    return game.get("tilt_index", 0) >= 0.2 or game.get("blunder_count", 0) >= 1


def _had_winning_position(game: Dict) -> bool:
    """Check if user had winning position"""
    leak_tags = game.get("leak_tags", {})
    return leak_tags.get("CONVERSION_ISSUE", 0) > 0 or game.get("mistake_count", 0) >= 1


def _avg_metric(games: List[Dict], key: str, default: float = 0.0) -> float:
    """Compute average of a metric across games"""
    if not games:
        return default
    
    values = [g.get(key, default) for g in games]
    return sum(values) / len(values) if values else default


def _compute_tilt_from_evals(move_evals: List[Dict]) -> float:
    """Compute tilt index from move evaluations"""
    if not move_evals:
        return 0.0
    
    # Count errors in second half of game
    second_half = move_evals[len(move_evals)//2:]
    errors = sum(1 for m in second_half if m.get("is_blunder") or m.get("is_mistake"))
    
    return min(1.0, errors / max(len(second_half), 1))


def _compute_time_pressure_from_evals(move_evals: List[Dict]) -> float:
    """Compute time pressure index"""
    if not move_evals:
        return 0.0
    
    # Check for clock data
    low_time_moves = sum(1 for m in move_evals if m.get("clock_ms", 60000) < 30000)
    return min(1.0, low_time_moves / max(len(move_evals), 1))


def _compute_opening_score(move_evals: List[Dict]) -> float:
    """Compute opening plan score"""
    if not move_evals:
        return 0.5
    
    opening = move_evals[:10]
    errors = sum(1 for m in opening if m.get("is_mistake") or m.get("is_blunder"))
    return max(0, 1.0 - (errors * 0.2))


# ==================== REASON GENERATORS ====================

def _get_time_decision_reason(score: float, improvement: float) -> str:
    if score >= 0.6:
        return f"Time pressure handling improved by {improvement:.0%}"
    elif score >= 0.3:
        return "Some improvement in time pressure situations"
    else:
        return "Time pressure still causing issues"


def _get_advice_reason(score: float, followed: int, total: int) -> str:
    if score >= 0.8:
        return f"Advice followed in {followed}/{total} games"
    elif score >= 0.5:
        return f"Advice partially applied ({followed}/{total})"
    else:
        return f"Advice violated in most games ({total-followed}/{total})"


def _get_calculation_reason(score: float, improvement: float) -> str:
    if score >= 0.6:
        return f"Calculation errors reduced by {improvement:.1f} per game"
    elif score >= 0.3:
        return "Some improvement in calculation"
    else:
        return "Calculation errors still present"


def _get_defensive_reason(score: float, improvement: float) -> str:
    if score >= 0.6:
        return f"Defensive resilience improved by {improvement:.0%}"
    elif score >= 0.3:
        return "Slight improvement in defensive positions"
    else:
        return "Defensive collapse still occurring"


def _get_conversion_reason(score: float, issues: int, total: int) -> str:
    if score >= 0.8:
        return f"Converting winning positions cleanly ({total-issues}/{total})"
    elif score >= 0.5:
        return f"Some conversion issues remain ({issues}/{total})"
    else:
        return f"Conversion still a major leak ({issues}/{total} thrown)"
