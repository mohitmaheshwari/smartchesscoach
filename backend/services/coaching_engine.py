"""
Coaching Engine Service
=======================

Comprehensive coaching decision engine that:
1. Detects issues from move analysis (cognitive_gap + motif + rushing detection)
2. Aggregates issues with frequency + severity + trend analysis
3. Generates prescriptions (select top issue, find best plan, check prerequisites)
4. Calculates metrics for each issue type (rushing, piece_safety, missed_tactic, king_safety, conversion)
5. Tracks improvement percentage across games
6. Detects competence levels in specific areas
7. Integrates with analysis_worker.py after game analysis

The engine provides unified coaching decisions for:
- What to focus on next
- Why that specific issue matters
- How to measure improvement
- When the player has mastered a skill
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
import math

logger = logging.getLogger(__name__)


class IssueType(str, Enum):
    """Types of chess-related issues the engine tracks"""
    RUSHING = "rushing"
    PIECE_SAFETY = "piece_safety"
    MISSED_TACTIC = "missed_tactic"
    KING_SAFETY = "king_safety"
    CALCULATION_DEPTH = "calculation_depth"
    POSITIONAL_ERROR = "positional_error"
    OPENING_KNOWLEDGE = "opening_knowledge"
    ENDGAME_TECHNIQUE = "endgame_technique"
    TIME_MANAGEMENT = "time_management"
    PAWN_STRUCTURE = "pawn_structure"


class IssueSeverity(str, Enum):
    """Severity levels for issues"""
    CRITICAL = "critical"      # >400cp loss
    HIGH = "high"              # 200-400cp loss
    MEDIUM = "medium"          # 100-200cp loss
    LOW = "low"                # 30-100cp loss
    MINIMAL = "minimal"        # <30cp loss


class CompetenceLevel(str, Enum):
    """Competence assessment levels"""
    NOVICE = "novice"              # <20% correct
    DEVELOPING = "developing"      # 20-50% correct
    INTERMEDIATE = "intermediate"  # 50-70% correct
    PROFICIENT = "proficient"      # 70-85% correct
    MASTERED = "mastered"          # >85% correct


@dataclass
class DetectedIssue:
    """A single issue detected from a move"""
    issue_type: IssueType
    move_number: int
    move_san: str
    severity: IssueSeverity
    cp_loss: int
    fen_before: str
    cognitive_gap: Optional[str] = None
    motif_type: Optional[str] = None  # "fork", "pin", "skewer", etc.
    is_rushing: bool = False
    time_remaining_seconds: Optional[int] = None
    explanation: str = ""
    best_move: Optional[str] = None
    phase: str = "middlegame"  # "opening", "middlegame", "endgame"


@dataclass
class AggregatedIssue:
    """Aggregated view of an issue across games"""
    issue_type: IssueType
    occurrence_count: int
    total_severity_score: float  # Sum of severity weights
    avg_cp_loss: float
    recent_games: List[str] = field(default_factory=list)  # game_ids
    trend: str = "stable"  # "improving", "regressing", "stable"
    last_occurrence_ago: int = 0  # Number of games ago
    clean_streak: int = 0  # Consecutive games without this issue
    severity_distribution: Dict[str, int] = field(default_factory=dict)  # count per severity


@dataclass
class IssueMetrics:
    """Metrics calculated for an issue type"""
    issue_type: IssueType
    frequency_per_game: float
    avg_severity: str
    avg_cp_loss: float
    trend: str
    competence_level: CompetenceLevel
    recommended_focus: bool
    priority_score: float  # 0-100 ranking


@dataclass
class PrescriptionPlan:
    """Personalized training prescription"""
    primary_issue: IssueType
    reasoning: str
    training_focus: str  # Name of the training content
    prerequisites: List[str] = field(default_factory=list)
    training_phase: str = "beginner"  # "beginner", "intermediate", "advanced"
    estimated_focus_duration_days: int = 7
    success_metrics: List[str] = field(default_factory=list)
    coaching_message: str = ""


# Constants for severity classification
SEVERITY_THRESHOLDS = {
    IssueSeverity.CRITICAL: 400,
    IssueSeverity.HIGH: 200,
    IssueSeverity.MEDIUM: 100,
    IssueSeverity.LOW: 30,
}

# Rushing detection thresholds (seconds remaining)
RUSHING_TIME_THRESHOLDS = {
    "bullet": 2,      # < 2 seconds in bullet
    "blitz": 15,      # < 15 seconds in blitz
    "rapid": 60,      # < 60 seconds in rapid
    "classical": 300, # < 5 minutes in classical
}

# Issue priority weights for ranking
ISSUE_PRIORITY_WEIGHTS = {
    IssueType.PIECE_SAFETY: 1.0,         # Highest priority - fundamental
    IssueType.MISSED_TACTIC: 0.95,
    IssueType.KING_SAFETY: 0.9,
    IssueType.RUSHING: 0.85,              # Behavioral issue
    IssueType.CALCULATION_DEPTH: 0.8,
    IssueType.POSITIONAL_ERROR: 0.7,
    IssueType.TIME_MANAGEMENT: 0.75,
    IssueType.ENDGAME_TECHNIQUE: 0.65,
    IssueType.PAWN_STRUCTURE: 0.6,
    IssueType.OPENING_KNOWLEDGE: 0.55,
}


def detect_issues_from_move(
    move_eval: Dict[str, Any],
    move_number: int,
    user_color: str,
    time_control: Optional[str] = "rapid",
    time_remaining_seconds: Optional[int] = None,
) -> Optional[DetectedIssue]:
    """
    Detect coaching-relevant issues from a single move evaluation.

    This function analyzes a move and identifies:
    1. Cognitive gaps (piece_safety, missed_tactic, etc.)
    2. Motif-related errors (unrecognized tactics)
    3. Rushing behavior (fast moves with high cp_loss)

    Args:
        move_eval: Move evaluation dict from Stockfish analysis
        move_number: Move number in game
        user_color: "white" or "black"
        time_control: time control type for rushing detection
        time_remaining_seconds: Time remaining at this move

    Returns:
        DetectedIssue if an issue is found, None otherwise

    Raises:
        ValueError: If move_eval is missing critical fields
    """
    try:
        # Skip opponent moves
        if not move_eval.get("is_user_move", False):
            return None

        # Skip moves without meaningful loss
        cp_loss = move_eval.get("cp_loss", 0)
        if cp_loss < 30:
            return None

        # Get core move data
        move_san = move_eval.get("move_san", move_eval.get("move", ""))
        evaluation = move_eval.get("evaluation", "").lower()

        if not move_san or evaluation not in ("blunder", "mistake", "inaccuracy"):
            return None

        # Determine severity
        severity = IssueSeverity.MINIMAL
        for sev, threshold in SEVERITY_THRESHOLDS.items():
            if cp_loss >= threshold:
                severity = sev
                break

        # Get cognitive gap (primary classification)
        cognitive_gap = move_eval.get("cognitive_gap")

        # Detect motif-related issues
        motif_type = None
        threat = move_eval.get("threat", "").lower()
        if threat:
            if "fork" in threat:
                motif_type = "fork"
            elif "pin" in threat:
                motif_type = "pin"
            elif "skewer" in threat:
                motif_type = "skewer"
            elif "battery" in threat:
                motif_type = "battery"

        # Map cognitive gap to issue type
        issue_type = _map_cognitive_gap_to_issue(cognitive_gap, threat, cp_loss)

        # Detect rushing behavior
        is_rushing = False
        if time_remaining_seconds is not None and time_control:
            is_rushing = _is_rushing_move(
                time_remaining_seconds,
                time_control,
                cp_loss,
                evaluation
            )

        # Determine game phase
        phase = _get_game_phase(move_number)

        return DetectedIssue(
            issue_type=issue_type,
            move_number=move_number,
            move_san=move_san,
            severity=severity,
            cp_loss=cp_loss,
            fen_before=move_eval.get("fen_before", ""),
            cognitive_gap=cognitive_gap,
            motif_type=motif_type,
            is_rushing=is_rushing,
            time_remaining_seconds=time_remaining_seconds,
            explanation=move_eval.get("explanation", ""),
            best_move=move_eval.get("best_move_san", move_eval.get("best_move")),
            phase=phase,
        )

    except Exception as e:
        logger.error(f"Failed to detect issue from move {move_number}: {e}", exc_info=True)
        return None


def issue_aggregation(
    detected_issues: List[DetectedIssue],
    recent_games: List[Dict[str, Any]],
) -> Dict[IssueType, AggregatedIssue]:
    """
    Aggregate detected issues with frequency, severity, and trend analysis.

    Takes individual move-level issues and creates game-level summaries.
    Computes:
    - Occurrence count
    - Severity distribution
    - Trend (improving/regressing/stable)
    - Clean streak (consecutive games without the issue)

    Args:
        detected_issues: Issues detected in the current game
        recent_games: List of recent game analyses (newest first)

    Returns:
        Dict mapping IssueType to AggregatedIssue

    Example:
        aggregated = issue_aggregation(
            [issue1, issue2],
            [game1, game2, game3]
        )
        # aggregated[IssueType.PIECE_SAFETY].trend → "regressing"
    """
    try:
        aggregated = {}

        # Count issues in current game
        issue_counts = {}
        for issue in detected_issues:
            if issue.issue_type not in issue_counts:
                issue_counts[issue.issue_type] = {
                    "count": 0,
                    "severity_scores": [],
                    "cp_losses": [],
                    "severities": {},
                }
            issue_counts[issue.issue_type]["count"] += 1
            issue_counts[issue.issue_type]["severity_scores"].append(
                _severity_to_weight(issue.severity)
            )
            issue_counts[issue.issue_type]["cp_losses"].append(issue.cp_loss)

            sev_name = issue.severity.value
            issue_counts[issue.issue_type]["severities"][sev_name] = (
                issue_counts[issue.issue_type]["severities"].get(sev_name, 0) + 1
            )

        # Build aggregated issues
        for issue_type, data in issue_counts.items():
            avg_cp_loss = sum(data["cp_losses"]) / len(data["cp_losses"])
            total_severity = sum(data["severity_scores"])

            # Calculate trend from recent games
            trend = _calculate_issue_trend(
                issue_type, recent_games, detected_issues
            )

            # Calculate clean streak
            clean_streak = _calculate_clean_streak(issue_type, recent_games)

            current_game_id = recent_games[0].get("game_id", "") if recent_games else ""

            aggregated[issue_type] = AggregatedIssue(
                issue_type=issue_type,
                occurrence_count=data["count"],
                total_severity_score=total_severity,
                avg_cp_loss=avg_cp_loss,
                recent_games=[current_game_id] if current_game_id else [],
                trend=trend,
                last_occurrence_ago=0,  # In current game
                clean_streak=clean_streak,
                severity_distribution=data["severities"],
            )

        logger.info(f"Aggregated {len(aggregated)} issue types from {len(detected_issues)} detected issues")
        return aggregated

    except Exception as e:
        logger.error(f"Failed to aggregate issues: {e}", exc_info=True)
        return {}


def prescription_generation(
    aggregated_issues: Dict[IssueType, AggregatedIssue],
    user_rating: int,
    user_id: str,
) -> Optional[PrescriptionPlan]:
    """
    Generate a personalized training prescription based on aggregated issues.

    Algorithm:
    1. Select top issue by priority + severity
    2. Determine training phase (beginner/intermediate/advanced)
    3. Check prerequisites are met
    4. Build coaching message
    5. Set success metrics

    Args:
        aggregated_issues: Issues aggregated from recent games
        user_rating: Player's estimated rating
        user_id: User identifier for logging

    Returns:
        PrescriptionPlan or None if no issues

    Example:
        prescription = prescription_generation(
            {IssueType.PIECE_SAFETY: issue},
            1500,
            "user_123"
        )
        print(prescription.training_focus)  # "Piece Protection Fundamentals"
    """
    try:
        if not aggregated_issues:
            logger.info(f"No issues to prescribe for {user_id}")
            return None

        # Calculate priority scores for each issue
        scored_issues = []
        for issue_type, issue in aggregated_issues.items():
            priority_score = _calculate_priority_score(
                issue_type, issue, user_rating
            )
            scored_issues.append((issue_type, issue, priority_score))

        # Sort by priority score (descending)
        scored_issues.sort(key=lambda x: x[2], reverse=True)

        primary_issue_type, primary_issue, priority_score = scored_issues[0]

        # Determine training phase based on rating
        training_phase = _determine_training_phase(primary_issue_type, user_rating)

        # Check prerequisites
        prerequisites = _check_prerequisites(primary_issue_type, aggregated_issues)

        # Build training focus name
        training_focus = _get_training_focus_name(primary_issue_type)

        # Build success metrics
        success_metrics = _build_success_metrics(primary_issue_type)

        # Build coaching message
        coaching_message = _build_coaching_message(
            primary_issue_type, primary_issue, user_rating
        )

        # Estimate focus duration
        estimated_duration = _estimate_focus_duration(primary_issue_type, primary_issue)

        prescription = PrescriptionPlan(
            primary_issue=primary_issue_type,
            reasoning=f"Detected {primary_issue.occurrence_count}x in recent games with {primary_issue.avg_cp_loss:.0f} avg cp loss",
            training_focus=training_focus,
            prerequisites=prerequisites,
            training_phase=training_phase,
            estimated_focus_duration_days=estimated_duration,
            success_metrics=success_metrics,
            coaching_message=coaching_message,
        )

        logger.info(
            f"Generated prescription for {user_id}: {primary_issue_type.value} "
            f"(priority_score={priority_score:.2f})"
        )
        return prescription

    except Exception as e:
        logger.error(f"Failed to generate prescription for {user_id}: {e}", exc_info=True)
        return None


def metric_calculation(
    issue_type: IssueType,
    detected_issues: List[DetectedIssue],
    recent_games: List[Dict[str, Any]],
) -> IssueMetrics:
    """
    Calculate detailed metrics for a specific issue type.

    Computes:
    - Frequency per game
    - Average severity
    - Trend direction
    - Competence level
    - Recommendation priority
    - Overall priority score (0-100)

    Args:
        issue_type: The issue type to analyze
        detected_issues: Issues detected in current game
        recent_games: Recent game history

    Returns:
        IssueMetrics with comprehensive statistics
    """
    try:
        # Filter to this issue type
        this_issue = [i for i in detected_issues if i.issue_type == issue_type]

        if not this_issue and not recent_games:
            return IssueMetrics(
                issue_type=issue_type,
                frequency_per_game=0.0,
                avg_severity="none",
                avg_cp_loss=0.0,
                trend="unknown",
                competence_level=CompetenceLevel.MASTERED,
                recommended_focus=False,
                priority_score=0.0,
            )

        # Calculate frequency
        total_games = max(len(recent_games), 1)
        issue_games = len([g for g in recent_games if _game_has_issue(g, issue_type)])
        frequency_per_game = len(this_issue) / total_games if total_games else 0

        # Calculate average severity
        if this_issue:
            severities = [i.severity for i in this_issue]
            avg_severity = max(severities, key=lambda s: _severity_to_weight(s))
            avg_cp_loss = sum(i.cp_loss for i in this_issue) / len(this_issue)
        else:
            avg_severity = IssueSeverity.MINIMAL
            avg_cp_loss = 0.0

        # Calculate trend
        trend = _calculate_issue_trend(issue_type, recent_games, detected_issues)

        # Calculate competence level
        competence = _assess_competence(issue_type, issue_games, total_games, avg_cp_loss)

        # Determine if should be recommended focus
        recommended_focus = (
            frequency_per_game > 0.3 and
            competence != CompetenceLevel.MASTERED
        )

        # Calculate priority score
        priority_score = _calculate_priority_score_from_metrics(
            frequency_per_game, avg_severity, trend, competence
        )

        return IssueMetrics(
            issue_type=issue_type,
            frequency_per_game=round(frequency_per_game, 2),
            avg_severity=avg_severity.value,
            avg_cp_loss=round(avg_cp_loss, 1),
            trend=trend,
            competence_level=competence,
            recommended_focus=recommended_focus,
            priority_score=round(priority_score, 1),
        )

    except Exception as e:
        logger.error(f"Failed to calculate metrics for {issue_type}: {e}", exc_info=True)
        return IssueMetrics(
            issue_type=issue_type,
            frequency_per_game=0.0,
            avg_severity="unknown",
            avg_cp_loss=0.0,
            trend="unknown",
            competence_level=CompetenceLevel.DEVELOPING,
            recommended_focus=False,
            priority_score=0.0,
        )


def improvement_pct(
    issue_type: IssueType,
    recent_games: List[Dict[str, Any]],
    improvement_window: int = 10,
) -> float:
    """
    Calculate improvement percentage for an issue type.

    Compares recent half vs. earlier half of games to determine
    if the player is improving on this specific issue.

    Returns:
        float: -100 to +100 where:
        - >0 = improving (fewer mistakes)
        - 0 = stable
        - <0 = regressing (more mistakes)

    Example:
        improvement = improvement_pct(IssueType.PIECE_SAFETY, games)
        if improvement > 20:
            print("Great progress on piece safety!")
    """
    try:
        if len(recent_games) < 4:
            return 0.0

        games = recent_games[:improvement_window]
        mid = len(games) // 2

        if mid == 0:
            return 0.0

        # Earlier half
        earlier = games[mid:]
        earlier_count = sum(
            1 for g in earlier if _game_has_issue(g, issue_type)
        )
        earlier_rate = earlier_count / len(earlier) if earlier else 0

        # Recent half
        recent = games[:mid]
        recent_count = sum(
            1 for g in recent if _game_has_issue(g, issue_type)
        )
        recent_rate = recent_count / len(recent) if recent else 0

        # Calculate percentage improvement
        if earlier_rate == 0:
            return 100.0 if recent_rate == 0 else 0.0

        improvement = (earlier_rate - recent_rate) / earlier_rate * 100
        return round(max(-100, min(100, improvement)), 1)

    except Exception as e:
        logger.error(f"Failed to calculate improvement for {issue_type}: {e}", exc_info=True)
        return 0.0


def competence_detection(
    issue_type: IssueType,
    recent_games: List[Dict[str, Any]],
    detected_issues: List[DetectedIssue],
    minimum_sample_size: int = 5,
) -> CompetenceLevel:
    """
    Assess player's competence level for a specific issue type.

    Based on:
    - Frequency of issue occurrence
    - Severity when it does occur
    - Trend (improving/regressing)
    - Recent performance

    Args:
        issue_type: Issue to assess
        recent_games: Recent game history
        detected_issues: Issues in current game
        minimum_sample_size: Min games needed for reliable assessment

    Returns:
        CompetenceLevel from NOVICE to MASTERED

    Example:
        level = competence_detection(
            IssueType.TACTICAL_OVERSIGHT,
            games,
            issues
        )
        if level == CompetenceLevel.MASTERED:
            print("Player has mastered this!")
    """
    try:
        if len(recent_games) < minimum_sample_size:
            return CompetenceLevel.DEVELOPING

        # Count games with this issue
        games_with_issue = sum(
            1 for g in recent_games if _game_has_issue(g, issue_type)
        )
        total_games = len(recent_games)
        issue_rate = games_with_issue / total_games

        # Get average cp_loss for this issue
        this_issue = [i for i in detected_issues if i.issue_type == issue_type]
        avg_cp_loss = sum(i.cp_loss for i in this_issue) / len(this_issue) if this_issue else 0

        # Calculate competence based on frequency and severity
        if issue_rate == 0:
            return CompetenceLevel.MASTERED
        elif issue_rate < 0.1 and avg_cp_loss < 100:
            return CompetenceLevel.PROFICIENT
        elif issue_rate < 0.3 and avg_cp_loss < 200:
            return CompetenceLevel.INTERMEDIATE
        elif issue_rate < 0.6:
            return CompetenceLevel.DEVELOPING
        else:
            return CompetenceLevel.NOVICE

    except Exception as e:
        logger.error(f"Failed to assess competence for {issue_type}: {e}", exc_info=True)
        return CompetenceLevel.DEVELOPING


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _map_cognitive_gap_to_issue(
    cognitive_gap: Optional[str],
    threat: str,
    cp_loss: int,
) -> IssueType:
    """Map cognitive_gap field to IssueType"""
    if cognitive_gap == "piece_safety":
        return IssueType.PIECE_SAFETY
    elif cognitive_gap == "missed_tactic":
        return IssueType.MISSED_TACTIC
    elif cognitive_gap == "tactical_oversight":
        return IssueType.MISSED_TACTIC
    elif cognitive_gap == "calculation_depth":
        return IssueType.CALCULATION_DEPTH
    elif cognitive_gap == "king_safety":
        return IssueType.KING_SAFETY
    elif cognitive_gap == "pawn_structure":
        return IssueType.PAWN_STRUCTURE
    elif cognitive_gap == "piece_activity":
        return IssueType.POSITIONAL_ERROR
    elif cognitive_gap == "opening_knowledge":
        return IssueType.OPENING_KNOWLEDGE
    elif cognitive_gap == "endgame_technique":
        return IssueType.ENDGAME_TECHNIQUE

    # Fallback to threat analysis
    if "fork" in threat or "pin" in threat or "skewer" in threat:
        return IssueType.MISSED_TACTIC
    elif "mate" in threat or "check" in threat:
        return IssueType.KING_SAFETY
    elif "hanging" in threat:
        return IssueType.PIECE_SAFETY

    # Default based on severity
    if cp_loss > 300:
        return IssueType.MISSED_TACTIC
    return IssueType.POSITIONAL_ERROR


def _is_rushing_move(
    time_remaining: int,
    time_control: str,
    cp_loss: int,
    evaluation: str,
) -> bool:
    """Detect if a move looks like it was made in time trouble"""
    threshold = RUSHING_TIME_THRESHOLDS.get(time_control, 60)

    if time_remaining > threshold:
        return False

    # Low time + significant error = likely rushing
    if evaluation in ("blunder", "mistake") and cp_loss > 100:
        return True

    return False


def _get_game_phase(move_number: int) -> str:
    """Classify game phase based on move number"""
    if move_number <= 12:
        return "opening"
    elif move_number <= 30:
        return "middlegame"
    else:
        return "endgame"


def _severity_to_weight(severity: IssueSeverity) -> float:
    """Convert severity to numeric weight"""
    weights = {
        IssueSeverity.CRITICAL: 1.0,
        IssueSeverity.HIGH: 0.75,
        IssueSeverity.MEDIUM: 0.5,
        IssueSeverity.LOW: 0.25,
        IssueSeverity.MINIMAL: 0.1,
    }
    return weights.get(severity, 0.0)


def _calculate_issue_trend(
    issue_type: IssueType,
    recent_games: List[Dict[str, Any]],
    detected_issues: List[DetectedIssue],
) -> str:
    """Calculate trend for an issue type (improving/regressing/stable)"""
    if len(recent_games) < 4:
        return "unknown"

    mid = len(recent_games) // 2
    if mid == 0:
        return "unknown"

    # Earlier vs. recent
    earlier = recent_games[mid:]
    recent = recent_games[:mid]

    earlier_count = sum(1 for g in earlier if _game_has_issue(g, issue_type))
    recent_count = sum(1 for g in recent if _game_has_issue(g, issue_type))

    earlier_rate = earlier_count / len(earlier) if earlier else 0
    recent_rate = recent_count / len(recent) if recent else 0

    if recent_rate < earlier_rate * 0.8:
        return "improving"
    elif recent_rate > earlier_rate * 1.2:
        return "regressing"
    else:
        return "stable"


def _calculate_clean_streak(
    issue_type: IssueType,
    recent_games: List[Dict[str, Any]],
) -> int:
    """Calculate consecutive games without an issue"""
    streak = 0
    for game in recent_games:
        if _game_has_issue(game, issue_type):
            break
        streak += 1
    return streak


def _game_has_issue(game: Dict[str, Any], issue_type: IssueType) -> bool:
    """Check if a game record contains a specific issue"""
    try:
        gaps = game.get("cognitive_gaps", [])
        moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

        # Check cognitive gaps
        gap_map = {
            IssueType.PIECE_SAFETY: "piece_safety",
            IssueType.MISSED_TACTIC: ["missed_tactic", "tactical_oversight"],
            IssueType.KING_SAFETY: "king_safety",
            IssueType.CALCULATION_DEPTH: "calculation_depth",
            IssueType.POSITIONAL_ERROR: "piece_activity",
            IssueType.PAWN_STRUCTURE: "pawn_structure",
            IssueType.OPENING_KNOWLEDGE: "opening_knowledge",
            IssueType.ENDGAME_TECHNIQUE: "endgame_technique",
        }

        target_gaps = gap_map.get(issue_type, [])
        if isinstance(target_gaps, str):
            target_gaps = [target_gaps]

        for gap in gaps:
            if gap in target_gaps:
                return True

        # Check for rushing in evaluation
        if issue_type == IssueType.RUSHING:
            for move in moves:
                if move.get("is_rushing"):
                    return True

        return False
    except Exception:
        return False


def _calculate_priority_score(
    issue_type: IssueType,
    issue: AggregatedIssue,
    user_rating: int,
) -> float:
    """Calculate priority score for an issue (0-100)"""
    base_weight = ISSUE_PRIORITY_WEIGHTS.get(issue_type, 0.5)

    # Frequency factor (0-1)
    frequency_factor = min(issue.occurrence_count / 5, 1.0)

    # Severity factor (0-1)
    severity_factor = issue.total_severity_score / issue.occurrence_count if issue.occurrence_count else 0

    # Trend factor (improving issues lower priority)
    trend_factor = {
        "improving": 0.3,
        "regressing": 1.0,
        "stable": 0.6,
        "unknown": 0.5,
    }.get(issue.trend, 0.5)

    # Rating factor (some issues matter more at certain ratings)
    if user_rating < 1000:
        if issue_type == IssueType.PIECE_SAFETY:
            rating_factor = 1.2  # Critical at low rating
        elif issue_type in (IssueType.OPENING_KNOWLEDGE, IssueType.PAWN_STRUCTURE):
            rating_factor = 0.5  # Less relevant
        else:
            rating_factor = 1.0
    elif user_rating > 1800:
        if issue_type == IssueType.POSITIONAL_ERROR:
            rating_factor = 1.2  # More relevant for advanced
        elif issue_type in (IssueType.PIECE_SAFETY,):
            rating_factor = 0.7  # Less of an issue
        else:
            rating_factor = 1.0
    else:
        rating_factor = 1.0

    score = (
        base_weight *
        (1 + frequency_factor) *
        (1 + severity_factor) *
        trend_factor *
        rating_factor *
        100
    )

    return min(100, max(0, score))


def _determine_training_phase(issue_type: IssueType, user_rating: int) -> str:
    """Determine training phase based on rating"""
    if user_rating < 1000:
        return "beginner"
    elif user_rating < 1600:
        return "intermediate"
    else:
        return "advanced"


def _check_prerequisites(
    issue_type: IssueType,
    aggregated_issues: Dict[IssueType, AggregatedIssue],
) -> List[str]:
    """Check if prerequisites are met for training an issue"""
    prerequisites = []

    # Some issues require foundations
    prereq_map = {
        IssueType.PAWN_STRUCTURE: [IssueType.PIECE_SAFETY],
        IssueType.POSITIONAL_ERROR: [IssueType.PIECE_SAFETY],
        IssueType.ENDGAME_TECHNIQUE: [IssueType.PIECE_SAFETY, IssueType.KING_SAFETY],
    }

    required = prereq_map.get(issue_type, [])
    for prereq in required:
        if prereq in aggregated_issues:
            prereq_issue = aggregated_issues[prereq]
            if prereq_issue.occurrence_count > 2:
                prerequisites.append(f"Master {prereq.value} first")

    return prerequisites


def _get_training_focus_name(issue_type: IssueType) -> str:
    """Get human-readable training focus name"""
    names = {
        IssueType.PIECE_SAFETY: "Piece Protection Fundamentals",
        IssueType.MISSED_TACTIC: "Tactical Pattern Recognition",
        IssueType.KING_SAFETY: "King Safety Essentials",
        IssueType.CALCULATION_DEPTH: "Deep Calculation Training",
        IssueType.RUSHING: "Time Management & Patience",
        IssueType.POSITIONAL_ERROR: "Positional Understanding",
        IssueType.PAWN_STRUCTURE: "Pawn Structure Mastery",
        IssueType.OPENING_KNOWLEDGE: "Opening Repertoire Development",
        IssueType.ENDGAME_TECHNIQUE: "Endgame Technique Drills",
        IssueType.TIME_MANAGEMENT: "Time Allocation Strategy",
    }
    return names.get(issue_type, "Chess Fundamentals")


def _build_success_metrics(issue_type: IssueType) -> List[str]:
    """Build measurable success metrics for an issue"""
    metrics_map = {
        IssueType.PIECE_SAFETY: [
            "0 hanging pieces per game",
            "100% piece protection check",
        ],
        IssueType.MISSED_TACTIC: [
            "Spot tactical patterns within 3 seconds",
            "85% accuracy on pattern drills",
        ],
        IssueType.KING_SAFETY: [
            "0 mate threats missed",
            "Safe king position maintained",
        ],
        IssueType.CALCULATION_DEPTH: [
            "Calculate 5+ moves deep",
            "75% accuracy on deep variations",
        ],
        IssueType.RUSHING: [
            "Average move time > 10 seconds",
            "0 blunders in first 60 moves",
        ],
    }
    return metrics_map.get(issue_type, ["Improve accuracy by 10%", "Reduce cp loss by 20%"])


def _build_coaching_message(
    issue_type: IssueType,
    issue: AggregatedIssue,
    user_rating: int,
) -> str:
    """Build personalized coaching message"""
    messages = {
        IssueType.PIECE_SAFETY: (
            f"I notice you left {issue.occurrence_count} pieces undefended in recent games. "
            "Before each move, do a 3-second check: are all my pieces safe? "
            "This single habit alone could gain 100+ rating points."
        ),
        IssueType.MISSED_TACTIC: (
            f"You missed {issue.occurrence_count} tactical opportunities recently. "
            "Let's sharpen your pattern recognition with focused drills. "
            "Most of these are repeatable patterns you'll start seeing immediately."
        ),
        IssueType.KING_SAFETY: (
            f"Your king came under serious attack {issue.occurrence_count} times. "
            "Proactive defense before threats emerge is the key. "
            "Let's build your threat-detection instincts."
        ),
        IssueType.RUSHING: (
            f"I see you're playing fast moves that lose positions. "
            f"With {issue.occurrence_count} blunders in time trouble, "
            "taking 3-5 extra seconds would likely win you the game."
        ),
    }

    return messages.get(
        issue_type,
        f"Let's focus on {_get_training_focus_name(issue_type).lower()}. "
        f"You've had {issue.occurrence_count} recent instances. With targeted training, "
        "you can eliminate this pattern quickly."
    )


def _estimate_focus_duration(
    issue_type: IssueType,
    issue: AggregatedIssue,
) -> int:
    """Estimate how many days to focus on an issue"""
    # More severe/frequent issues = longer focus
    base = 5

    frequency_multiplier = min(issue.occurrence_count / 3, 2.0)
    severity_multiplier = issue.total_severity_score / issue.occurrence_count if issue.occurrence_count else 1.0

    duration = int(base * frequency_multiplier * severity_multiplier)
    return max(3, min(21, duration))  # Clamp 3-21 days


def _assess_competence(
    issue_type: IssueType,
    games_with_issue: int,
    total_games: int,
    avg_cp_loss: float,
) -> CompetenceLevel:
    """Assess competence level based on statistics"""
    if total_games == 0:
        return CompetenceLevel.DEVELOPING

    issue_rate = games_with_issue / total_games

    if issue_rate == 0:
        return CompetenceLevel.MASTERED
    elif issue_rate < 0.15:
        if avg_cp_loss < 75:
            return CompetenceLevel.PROFICIENT
        else:
            return CompetenceLevel.INTERMEDIATE
    elif issue_rate < 0.35:
        if avg_cp_loss < 150:
            return CompetenceLevel.INTERMEDIATE
        else:
            return CompetenceLevel.DEVELOPING
    elif issue_rate < 0.65:
        return CompetenceLevel.DEVELOPING
    else:
        return CompetenceLevel.NOVICE


def _calculate_priority_score_from_metrics(
    frequency: float,
    severity: IssueSeverity,
    trend: str,
    competence: CompetenceLevel,
) -> float:
    """Calculate priority score from individual metrics"""
    frequency_score = min(frequency * 100, 30)

    severity_weights = {
        IssueSeverity.CRITICAL: 30,
        IssueSeverity.HIGH: 25,
        IssueSeverity.MEDIUM: 15,
        IssueSeverity.LOW: 5,
        IssueSeverity.MINIMAL: 1,
    }
    severity_score = severity_weights.get(severity, 0)

    trend_weights = {
        "regressing": 20,
        "stable": 10,
        "improving": 5,
        "unknown": 7,
    }
    trend_score = trend_weights.get(trend, 0)

    competence_weights = {
        CompetenceLevel.NOVICE: 15,
        CompetenceLevel.DEVELOPING: 10,
        CompetenceLevel.INTERMEDIATE: 5,
        CompetenceLevel.PROFICIENT: 2,
        CompetenceLevel.MASTERED: 0,
    }
    competence_score = competence_weights.get(competence, 0)

    return frequency_score + severity_score + trend_score + competence_score


# ============================================================================
# INTEGRATION WITH ANALYSIS WORKER
# ============================================================================

def process_game_for_coaching(
    db,
    game_id: str,
    user_id: str,
    move_evaluations: List[Dict[str, Any]],
    user_rating: int,
    user_color: str,
    time_control: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main integration point with analysis_worker.py

    After Stockfish analysis completes, this function:
    1. Detects all issues from the game
    2. Aggregates them with historical data
    3. Generates a training prescription
    4. Stores results in coach_memory
    5. Returns coaching summary

    Args:
        db: MongoDB database connection
        game_id: ID of the analyzed game
        user_id: Player's user ID
        move_evaluations: Stockfish move evaluations
        user_rating: Player's rating
        user_color: "white" or "black"
        time_control: Time control type

    Returns:
        Dict with coaching_summary, prescription, metrics

    Example:
        # In analysis_worker.py after game analysis:
        coaching_result = process_game_for_coaching(
            db, game_id, user_id, move_evaluations, 1400, "white", "rapid"
        )
        logger.info(coaching_result['coaching_summary'])
    """
    try:
        logger.info(f"[COACHING_ENGINE] Processing game {game_id} for {user_id}")

        # Step 1: Detect issues
        detected_issues = []
        for i, move_eval in enumerate(move_evaluations):
            if move_eval.get("is_user_move"):
                issue = detect_issues_from_move(
                    move_eval,
                    i + 1,
                    user_color,
                    time_control,
                    None,  # time_remaining not available in analysis
                )
                if issue:
                    detected_issues.append(issue)

        logger.info(f"[COACHING_ENGINE] Detected {len(detected_issues)} issues in game {game_id}")

        # Step 2: Get recent games for context
        recent_games = list(db.game_analyses.find(
            {"user_id": user_id},
            {"stockfish_analysis.move_evaluations": 1, "cognitive_gaps": 1}
        ).sort("analyzed_at", -1).limit(10))

        # Step 3: Aggregate issues
        aggregated = issue_aggregation(detected_issues, recent_games)

        # Step 4: Generate prescription
        prescription = prescription_generation(aggregated, user_rating, user_id)

        # Step 5: Calculate metrics for all issue types
        metrics = {}
        for issue_type in IssueType:
            m = metric_calculation(issue_type, detected_issues, recent_games)
            metrics[issue_type.value] = asdict(m)

        # Step 6: Calculate overall improvement
        improvements = {}
        for issue_type in IssueType:
            imp = improvement_pct(issue_type, recent_games)
            improvements[issue_type.value] = imp

        # Step 7: Store results in coach_memory (for next session)
        try:
            coaching_summary = {
                "game_id": game_id,
                "user_id": user_id,
                "detected_issues": len(detected_issues),
                "aggregated_issues": {k.value: asdict(v) for k, v in aggregated.items()},
                "prescription": asdict(prescription) if prescription else None,
                "metrics": metrics,
                "improvements": improvements,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Upsert coaching summary to database
            db.coaching_summaries.update_one(
                {"game_id": game_id, "user_id": user_id},
                {"$set": coaching_summary},
                upsert=True
            )

            logger.info(
                f"[COACHING_ENGINE] Completed for {game_id}: "
                f"{len(aggregated)} issue types, prescription={prescription.primary_issue.value if prescription else 'none'}"
            )

            return coaching_summary

        except Exception as e:
            logger.warning(f"[COACHING_ENGINE] Failed to store coaching summary: {e}")
            return {
                "game_id": game_id,
                "user_id": user_id,
                "detected_issues": len(detected_issues),
                "error": str(e)
            }

    except Exception as e:
        logger.error(f"[COACHING_ENGINE] Failed to process game {game_id}: {e}", exc_info=True)
        return {
            "game_id": game_id,
            "user_id": user_id,
            "error": str(e)
        }
