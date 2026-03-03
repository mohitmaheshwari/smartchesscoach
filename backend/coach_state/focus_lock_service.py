"""
Focus Lock Service - Step 9: Behavioral Enforcement

Converts pattern detection into measurable discipline enforcement.
Locks ONE rule at a time and tracks compliance per game.

Key Difference:
- Without Focus Lock: "You should improve this."
- With Focus Lock: "We are locking this for 5 games."

Compliance Heuristics:
- FORCING_BLIND: Check forcing moves before deciding
- STOPPED_CALCULATION_EARLY: Calculate one move deeper at critical moments
- THREAT_VERIFICATION: Verify opponent threats before executing

NO LLM. NO RAG. Fully deterministic.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Literal, Optional
from datetime import datetime, timezone
from enum import Enum


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

LockState = Literal["ACTIVE", "EXTENDED", "STRICT", "COMPLETED", "FAILED", "NONE"]
LessonKey = Literal["FORCING_BLIND", "STOPPED_CALCULATION_EARLY", "THREAT_VERIFICATION"]


class ComplianceLevel(Enum):
    """Compliance interpretation thresholds."""
    STRONG = "strong"      # >= 0.80
    PARTIAL = "partial"    # 0.60 - 0.79
    FAILED = "failed"      # < 0.60


# =============================================================================
# THRESHOLDS
# =============================================================================

# Compliance thresholds
STRONG_COMPLIANCE = 0.80
PARTIAL_COMPLIANCE = 0.60

# Minimum signal thresholds (ignore games with too few opportunities)
MIN_FORCING_OPPORTUNITIES = 3
MIN_CRITICAL_MOMENTS = 2
MIN_THREAT_OPPORTUNITIES = 3

# CP loss thresholds
CP_LOSS_FORCING_MISSED = 80
CP_LOSS_EARLY_STOP = 100
CP_LOSS_THREAT_IGNORED = 80

# Lock configuration
DEFAULT_LOCK_GAMES = 5
EXTENSION_GAMES = 3
COMPLETION_COMPLIANCE_THRESHOLD = 0.75

# Strict mode triggers
MAX_LOCK_FAILURES = 2


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ComplianceResult:
    """Result of compliance calculation for a single game."""
    lesson_key: str
    total_opportunities: int
    missed_count: int
    compliance_score: float
    interpretation: ComplianceLevel
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def passed(self) -> bool:
        return self.compliance_score >= COMPLETION_COMPLIANCE_THRESHOLD


@dataclass
class FocusLock:
    """Represents an active focus lock for a user."""
    lesson_key: str
    state: LockState
    games_required: int
    games_completed: int
    compliance_scores: List[float]
    strict_mode: bool
    failure_count: int
    failed_cycles: int  # NEW: Track how many times lock has failed and re-extended
    created_at: datetime
    updated_at: datetime
    headline: str
    message: str
    
    @property
    def average_compliance(self) -> float:
        if not self.compliance_scores:
            return 0.0
        return sum(self.compliance_scores) / len(self.compliance_scores)
    
    @property
    def progress_text(self) -> str:
        return f"{self.games_completed} of {self.games_required} games completed"
    
    @property
    def compliance_color(self) -> str:
        avg = self.average_compliance
        if avg >= STRONG_COMPLIANCE:
            return "green"
        elif avg >= PARTIAL_COMPLIANCE:
            return "yellow"
        else:
            return "red"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "lesson_key": self.lesson_key,
            "state": self.state,
            "games_required": self.games_required,
            "games_completed": self.games_completed,
            "compliance_scores": self.compliance_scores,
            "average_compliance": round(self.average_compliance, 2),
            "strict_mode": self.strict_mode,
            "failure_count": self.failure_count,
            "failed_cycles": self.failed_cycles,
            "headline": self.headline,
            "message": self.message,
            "progress_text": self.progress_text,
            "compliance_color": self.compliance_color,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# =============================================================================
# COMPLIANCE CALCULATION - FORCING_BLIND
# =============================================================================

def calculate_forcing_compliance(move_evaluations: List[Dict]) -> ComplianceResult:
    """
    FORCING_BLIND: Check forcing moves before deciding.
    
    Forcing Opportunity: Engine best_move is check, capture, or creates mate threat.
    Missed: Player didn't play forcing move AND cp_loss >= 80.
    
    Compliance = 1 - (missed_forcing / total_forcing_opportunities)
    """
    total_opportunities = 0
    missed_count = 0
    details = {"opportunities": [], "missed": []}
    
    for move in move_evaluations:
        if not move.get("is_user_move"):
            continue
        
        # Check if this was a forcing opportunity
        best_move_data = move.get("engine_best_move_data", {})
        
        is_check = best_move_data.get("gives_check", False)
        is_capture = best_move_data.get("is_capture", False)
        mate_in = best_move_data.get("mate_in")
        
        # Also check from other fields if available
        if not is_check:
            is_check = move.get("best_gives_check", False)
        if not is_capture:
            is_capture = move.get("best_is_capture", False)
        
        forcing_opportunity = is_check or is_capture or (mate_in is not None)
        
        if forcing_opportunity:
            total_opportunities += 1
            details["opportunities"].append(move.get("move_number", 0))
            
            # Check if player missed it
            player_move = move.get("move_uci", "")
            best_move = move.get("engine_best_move", "")
            cp_loss = move.get("cp_loss", 0)
            
            if player_move != best_move and cp_loss >= CP_LOSS_FORCING_MISSED:
                missed_count += 1
                details["missed"].append({
                    "move_number": move.get("move_number", 0),
                    "played": player_move,
                    "best": best_move,
                    "cp_loss": cp_loss,
                })
    
    # Calculate compliance
    if total_opportunities < MIN_FORCING_OPPORTUNITIES:
        # Not enough data - return neutral
        return ComplianceResult(
            lesson_key="FORCING_BLIND",
            total_opportunities=total_opportunities,
            missed_count=missed_count,
            compliance_score=1.0,  # Give benefit of doubt
            interpretation=ComplianceLevel.STRONG,
            details={"insufficient_data": True, **details}
        )
    
    compliance = 1 - (missed_count / total_opportunities)
    
    if compliance >= STRONG_COMPLIANCE:
        interpretation = ComplianceLevel.STRONG
    elif compliance >= PARTIAL_COMPLIANCE:
        interpretation = ComplianceLevel.PARTIAL
    else:
        interpretation = ComplianceLevel.FAILED
    
    return ComplianceResult(
        lesson_key="FORCING_BLIND",
        total_opportunities=total_opportunities,
        missed_count=missed_count,
        compliance_score=round(compliance, 2),
        interpretation=interpretation,
        details=details
    )


# =============================================================================
# COMPLIANCE CALCULATION - STOPPED_CALCULATION_EARLY
# =============================================================================

def calculate_calculation_compliance(move_evaluations: List[Dict]) -> ComplianceResult:
    """
    STOPPED_CALCULATION_EARLY: Calculate one move deeper at critical moments.
    
    Critical Moment: abs(eval_before - eval_after_best) >= 150 OR mate available.
    Early Stop: Player move not in top 2 AND cp_loss >= 100.
    
    Compliance = 1 - (early_stop / total_critical_moments)
    """
    total_critical = 0
    early_stops = 0
    details = {"critical_moments": [], "early_stops": []}
    
    for move in move_evaluations:
        if not move.get("is_user_move"):
            continue
        
        eval_before = move.get("score_before", 0)
        eval_after_best = move.get("eval_after_best", move.get("score_after", 0))
        mate_available = move.get("mate_in_best") is not None
        
        # Check if critical moment
        eval_swing = abs(eval_before - eval_after_best) if eval_after_best else 0
        is_critical = eval_swing >= 150 or mate_available
        
        if is_critical:
            total_critical += 1
            details["critical_moments"].append(move.get("move_number", 0))
            
            # Check for early stop
            player_move = move.get("move_uci", "")
            top_moves = move.get("engine_top_moves", [])
            
            # Get top 2 moves
            top_2 = []
            if isinstance(top_moves, list) and len(top_moves) >= 1:
                top_2 = [m.get("move", m) if isinstance(m, dict) else m for m in top_moves[:2]]
            else:
                top_2 = [move.get("engine_best_move", "")]
            
            cp_loss = move.get("cp_loss", 0)
            
            if player_move not in top_2 and cp_loss >= CP_LOSS_EARLY_STOP:
                early_stops += 1
                details["early_stops"].append({
                    "move_number": move.get("move_number", 0),
                    "played": player_move,
                    "top_moves": top_2,
                    "cp_loss": cp_loss,
                })
    
    # Calculate compliance
    if total_critical < MIN_CRITICAL_MOMENTS:
        return ComplianceResult(
            lesson_key="STOPPED_CALCULATION_EARLY",
            total_opportunities=total_critical,
            missed_count=early_stops,
            compliance_score=1.0,
            interpretation=ComplianceLevel.STRONG,
            details={"insufficient_data": True, **details}
        )
    
    compliance = 1 - (early_stops / total_critical)
    
    if compliance >= STRONG_COMPLIANCE:
        interpretation = ComplianceLevel.STRONG
    elif compliance >= PARTIAL_COMPLIANCE:
        interpretation = ComplianceLevel.PARTIAL
    else:
        interpretation = ComplianceLevel.FAILED
    
    return ComplianceResult(
        lesson_key="STOPPED_CALCULATION_EARLY",
        total_opportunities=total_critical,
        missed_count=early_stops,
        compliance_score=round(compliance, 2),
        interpretation=interpretation,
        details=details
    )


# =============================================================================
# COMPLIANCE CALCULATION - THREAT_VERIFICATION
# =============================================================================

def calculate_threat_compliance(move_evaluations: List[Dict]) -> ComplianceResult:
    """
    THREAT_VERIFICATION: Verify opponent threats before executing.
    
    Threat Exists: Opponent's best reply gives check, wins material >= 100cp, or creates mate.
    Threat Ignored: Player move doesn't address threat AND cp_loss >= 80.
    
    Compliance = 1 - (missed_threat / total_threat_opportunities)
    """
    total_threats = 0
    missed_threats = 0
    details = {"threat_opportunities": [], "missed_threats": []}
    
    for i, move in enumerate(move_evaluations):
        if not move.get("is_user_move"):
            continue
        
        # Get opponent's best reply data (from PV or previous move analysis)
        opponent_reply = move.get("opponent_best_reply", {})
        
        # Check if threat exists
        reply_is_check = opponent_reply.get("gives_check", False)
        reply_material_gain = opponent_reply.get("material_gain", 0)
        reply_mate_threat = opponent_reply.get("mate_in") is not None
        
        # Alternative: check if opponent has forcing response in PV
        pv = move.get("engine_pv", [])
        if len(pv) >= 2:
            # Second move in PV is opponent's reply
            # Check if it was forcing based on eval change
            reply_is_check = reply_is_check or move.get("pv_reply_is_check", False)
        
        threat_exists = reply_is_check or reply_material_gain >= 100 or reply_mate_threat
        
        if threat_exists:
            total_threats += 1
            details["threat_opportunities"].append(move.get("move_number", 0))
            
            # Check if player addressed the threat
            cp_loss = move.get("cp_loss", 0)
            addresses_threat = move.get("addresses_threat", False)
            
            # If significant cp_loss and threat wasn't addressed
            if cp_loss >= CP_LOSS_THREAT_IGNORED and not addresses_threat:
                missed_threats += 1
                details["missed_threats"].append({
                    "move_number": move.get("move_number", 0),
                    "cp_loss": cp_loss,
                    "threat_type": "check" if reply_is_check else ("material" if reply_material_gain >= 100 else "mate"),
                })
    
    # Calculate compliance
    if total_threats < MIN_THREAT_OPPORTUNITIES:
        return ComplianceResult(
            lesson_key="THREAT_VERIFICATION",
            total_opportunities=total_threats,
            missed_count=missed_threats,
            compliance_score=1.0,
            interpretation=ComplianceLevel.STRONG,
            details={"insufficient_data": True, **details}
        )
    
    compliance = 1 - (missed_threats / total_threats)
    
    if compliance >= STRONG_COMPLIANCE:
        interpretation = ComplianceLevel.STRONG
    elif compliance >= PARTIAL_COMPLIANCE:
        interpretation = ComplianceLevel.PARTIAL
    else:
        interpretation = ComplianceLevel.FAILED
    
    return ComplianceResult(
        lesson_key="THREAT_VERIFICATION",
        total_opportunities=total_threats,
        missed_count=missed_threats,
        compliance_score=round(compliance, 2),
        interpretation=interpretation,
        details=details
    )


# =============================================================================
# COMPLIANCE DISPATCHER
# =============================================================================

def calculate_compliance(lesson_key: str, move_evaluations: List[Dict]) -> ComplianceResult:
    """
    Calculate compliance for a given lesson key.
    
    Dispatches to the appropriate compliance calculator.
    """
    calculators = {
        "FORCING_BLIND": calculate_forcing_compliance,
        "STOPPED_CALCULATION_EARLY": calculate_calculation_compliance,
        "THREAT_VERIFICATION": calculate_threat_compliance,
    }
    
    calculator = calculators.get(lesson_key, calculate_forcing_compliance)
    return calculator(move_evaluations)


# =============================================================================
# LOCK UI COPY
# =============================================================================

# Rule descriptions for each lesson key
RULE_DESCRIPTIONS = {
    "FORCING_BLIND": "Forcing moves before every decision.",
    "STOPPED_CALCULATION_EARLY": "Calculate one move deeper at critical moments.",
    "THREAT_VERIFICATION": "Verify opponent threats before executing.",
}

# Headlines per lock state
LOCK_HEADLINES = {
    "ACTIVE": "Rule locked for {games} games.",
    "EXTENDED": "Rule extended.",
    "STRICT": "Discipline slipping.",
    "COMPLETED": "Rule mastered.",
    "FAILED": "Loop not broken.",
}

# Messages per lock state
LOCK_MESSAGES = {
    "ACTIVE": "{rule_description}",
    "EXTENDED": "Compliance below required level. {extension} more games.",
    "STRICT": "Same mistake repeated. Lock remains active.",
    "COMPLETED": "{lesson} awareness improved. Lock lifted.",
    "FAILED": "Deep review required.",
}

# Strict mode tone replacements
STRICT_TONE = {
    "Keep building this pattern.": None,  # Remove
    "You're improving.": None,  # Remove
    "This will stick.": None,  # Remove
    "encouragement": [
        "This must improve.",
        "No shortcuts here.",
        "Discipline first.",
    ],
}


def get_lock_copy(
    state: LockState,
    lesson_key: str,
    games_required: int = DEFAULT_LOCK_GAMES,
    extension_games: int = EXTENSION_GAMES,
) -> tuple[str, str]:
    """
    Get headline and message for lock state.
    
    Returns (headline, message) tuple.
    """
    rule_desc = RULE_DESCRIPTIONS.get(lesson_key, "Focus on this pattern.")
    lesson_name = lesson_key.replace("_", " ").title()
    
    headline = LOCK_HEADLINES.get(state, "Focus Lock Active").format(
        games=games_required,
        extension=extension_games,
    )
    
    message = LOCK_MESSAGES.get(state, rule_desc).format(
        rule_description=rule_desc,
        extension=extension_games,
        lesson=lesson_name,
    )
    
    return headline, message


# =============================================================================
# FOCUS LOCK LIFECYCLE
# =============================================================================

def create_focus_lock(lesson_key: str, games: int = DEFAULT_LOCK_GAMES) -> FocusLock:
    """Create a new focus lock for a lesson."""
    headline, message = get_lock_copy("ACTIVE", lesson_key, games)
    
    now = datetime.now(timezone.utc)
    return FocusLock(
        lesson_key=lesson_key,
        state="ACTIVE",
        games_required=games,
        games_completed=0,
        compliance_scores=[],
        strict_mode=False,
        failure_count=0,
        failed_cycles=0,  # NEW: Initialize failed_cycles
        created_at=now,
        updated_at=now,
        headline=headline,
        message=message,
    )


def update_lock_after_game(
    lock: FocusLock,
    compliance: ComplianceResult,
    trend: str = "stable",
) -> FocusLock:
    """
    Update focus lock after a game is analyzed.
    
    Handles:
    - Progress tracking
    - Compliance scoring
    - Extension logic
    - Strict mode activation
    - Exit conditions
    
    Strict mode rule (updated):
    - if failed_cycles >= 1 and declining_trend: strict_mode = True
    
    Deep review rule:
    - if failed_cycles >= 2: trigger deep session
    """
    # Add compliance score
    new_scores = lock.compliance_scores + [compliance.compliance_score]
    games_completed = lock.games_completed + 1
    now = datetime.now(timezone.utc)
    
    # Calculate average compliance
    avg_compliance = sum(new_scores) / len(new_scores)
    
    # Determine new state
    new_state = lock.state
    new_failure_count = lock.failure_count
    new_failed_cycles = lock.failed_cycles
    strict_mode = lock.strict_mode
    games_required = lock.games_required
    
    # Check if lock cycle is complete
    if games_completed >= lock.games_required:
        if avg_compliance >= COMPLETION_COMPLIANCE_THRESHOLD:
            # SUCCESS - Lock completed
            new_state = "COMPLETED"
            headline, message = get_lock_copy("COMPLETED", lock.lesson_key)
        else:
            # FAILED - Need to extend or escalate
            new_failure_count += 1
            new_failed_cycles += 1  # Track failed cycle
            
            if new_failed_cycles >= MAX_LOCK_FAILURES:
                # Failed twice - trigger deep review
                new_state = "FAILED"
                headline, message = get_lock_copy("FAILED", lock.lesson_key)
            else:
                # Extend lock - keep current game count, add more required
                new_state = "EXTENDED"
                games_required = lock.games_required + EXTENSION_GAMES
                # games_completed stays at current value (already incremented)
                headline, message = get_lock_copy("EXTENDED", lock.lesson_key)
    else:
        # Lock still in progress
        new_state = lock.state
        headline = lock.headline
        message = lock.message
    
    # Check for strict mode activation (updated rule)
    # if failed_cycles >= 1 and declining_trend: strict_mode = True
    if lock.failed_cycles >= 1 and trend == "declining" and new_state not in ("COMPLETED", "FAILED"):
        strict_mode = True
        new_state = "STRICT"
        headline, message = get_lock_copy("STRICT", lock.lesson_key)
    
    # Also activate strict mode on declining trend during active lock
    if trend == "declining" and new_state == "ACTIVE" and not strict_mode:
        strict_mode = True
        new_state = "STRICT"
        headline, message = get_lock_copy("STRICT", lock.lesson_key)
    
    return FocusLock(
        lesson_key=lock.lesson_key,
        state=new_state,
        games_required=games_required,
        games_completed=games_completed,
        compliance_scores=new_scores,
        strict_mode=strict_mode,
        failure_count=new_failure_count,
        failed_cycles=new_failed_cycles,
        created_at=lock.created_at,
        updated_at=now,
        headline=headline,
        message=message,
    )


def check_lock_exit(lock: FocusLock) -> Dict[str, Any]:
    """
    Check exit conditions and return appropriate messaging.
    
    Returns dict with:
    - should_exit: bool
    - exit_type: "success" | "extended" | "failed" | None
    - headline: str
    - message: str
    - next_action: str
    """
    if lock.state == "COMPLETED":
        return {
            "should_exit": True,
            "exit_type": "success",
            "headline": "Rule mastered.",
            "message": f"{lock.lesson_key.replace('_', ' ').title()} awareness improved. Lock lifted.",
            "next_action": "CONTINUE_TRAINING",
            "reward": "+1 Discipline Level",
        }
    
    elif lock.state == "FAILED":
        return {
            "should_exit": True,
            "exit_type": "failed",
            "headline": "Loop not broken.",
            "message": "Deep review required.",
            "next_action": "DEEP_SESSION",
            "auto_cta": "Start Deep Session",
        }
    
    elif lock.state == "EXTENDED":
        return {
            "should_exit": False,
            "exit_type": "extended",
            "headline": "Almost there.",
            "message": f"Awareness improving, but not stable yet. {EXTENSION_GAMES} more games.",
            "next_action": "CONTINUE_LOCK",
        }
    
    return {
        "should_exit": False,
        "exit_type": None,
        "headline": lock.headline,
        "message": lock.message,
        "next_action": "CONTINUE_LOCK",
    }


# =============================================================================
# STRICT MODE TONE ADJUSTMENTS
# =============================================================================

# Sentence budgets per tier in strict mode
STRICT_SENTENCE_BUDGET = {
    "Novice": 3,
    "Developing": 3,
    "Disciplined": 2,
    "Advanced": 1,
}

# Tone rules per tier in strict mode
STRICT_TONE_RULES = {
    "Novice": "no_encouragement",
    "Developing": "no_soft_phrases",
    "Disciplined": "direct_instruction",
    "Advanced": "command_tone",
}


def apply_strict_mode_tone(
    text: str,
    tier: str,
    strict_mode: bool,
) -> str:
    """
    Apply strict mode tone adjustments to coaching text.
    
    In strict mode:
    - Remove encouragement
    - Remove soft phrases
    - Enforce sentence budget
    """
    if not strict_mode:
        return text
    
    # Remove encouragement phrases
    phrases_to_remove = [
        "Keep building this pattern.",
        "You're improving.",
        "This will stick.",
        "This habit will pay off.",
        "Trust the process.",
        "Stay patient.",
    ]
    
    for phrase in phrases_to_remove:
        text = text.replace(phrase, "").strip()
    
    # Clean up double spaces
    while "  " in text:
        text = text.replace("  ", " ")
    
    # Enforce sentence budget
    budget = STRICT_SENTENCE_BUDGET.get(tier, 3)
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    
    if len(sentences) > budget:
        sentences = sentences[:budget]
    
    return ". ".join(sentences) + "." if sentences else text


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def should_activate_lock(
    breakthrough_state: str,
    dominant_lesson_key: str,
) -> bool:
    """
    Check if focus lock should be activated based on breakthrough state.
    
    Lock activates for:
    - CONFIDENCE_ILLUSION
    - PLATEAU
    """
    should_lock = breakthrough_state in ("CONFIDENCE_ILLUSION", "PLATEAU")
    valid_lesson = dominant_lesson_key in (
        "FORCING_BLIND",
        "STOPPED_CALCULATION_EARLY",
        "THREAT_VERIFICATION",
    )
    
    return should_lock and valid_lesson


def get_lock_ui_state(lock: Optional[FocusLock]) -> Dict[str, Any]:
    """
    Get UI-ready state for focus lock display.
    
    Returns None if no active lock.
    """
    if not lock or lock.state in ("COMPLETED", "FAILED", "NONE"):
        return None
    
    return {
        "active": True,
        "lesson_key": lock.lesson_key,
        "rule_description": RULE_DESCRIPTIONS.get(lock.lesson_key, ""),
        "state": lock.state,
        "headline": lock.headline,
        "message": lock.message,
        "progress": {
            "completed": lock.games_completed,
            "required": lock.games_required,
            "text": lock.progress_text,
        },
        "compliance": {
            "average": round(lock.average_compliance * 100),
            "color": lock.compliance_color,
            "text": f"Current discipline: {round(lock.average_compliance * 100)}%",
        },
        "strict_mode": lock.strict_mode,
        "cta": "Start Next Game",
    }



# =============================================================================
# COMPLIANCE TREND CALCULATION
# =============================================================================

def calculate_compliance_trend(compliance_scores: List[float]) -> str:
    """
    Calculate compliance trend from recent scores.
    
    Returns: "improving" | "stable" | "declining"
    """
    if len(compliance_scores) < 2:
        return "stable"
    
    # Compare last 2 scores vs previous 2 (or whatever we have)
    recent = compliance_scores[-2:]
    previous = compliance_scores[:-2] if len(compliance_scores) > 2 else compliance_scores[:1]
    
    avg_recent = sum(recent) / len(recent)
    avg_previous = sum(previous) / len(previous) if previous else avg_recent
    
    diff = avg_recent - avg_previous
    
    if diff > 0.10:  # 10% improvement
        return "improving"
    elif diff < -0.10:  # 10% decline
        return "declining"
    else:
        return "stable"


# =============================================================================
# DB SERIALIZATION HELPERS
# =============================================================================

def focus_lock_to_db(lock: FocusLock) -> Dict[str, Any]:
    """Convert FocusLock to DB-storable dict."""
    return {
        "lesson_key": lock.lesson_key,
        "state": lock.state,
        "games_required": lock.games_required,
        "games_completed": lock.games_completed,
        "compliance_scores": lock.compliance_scores,
        "strict_mode": lock.strict_mode,
        "failure_count": lock.failure_count,
        "failed_cycles": lock.failed_cycles,
        "created_at": lock.created_at.isoformat(),
        "updated_at": lock.updated_at.isoformat(),
        "headline": lock.headline,
        "message": lock.message,
    }


def focus_lock_from_db(doc: Dict[str, Any]) -> Optional[FocusLock]:
    """Rebuild FocusLock from DB document."""
    if not doc:
        return None
    
    # Parse dates
    created_at = doc.get("created_at")
    updated_at = doc.get("updated_at")
    
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
    
    return FocusLock(
        lesson_key=doc.get("lesson_key", "FORCING_BLIND"),
        state=doc.get("state", "ACTIVE"),
        games_required=doc.get("games_required", DEFAULT_LOCK_GAMES),
        games_completed=doc.get("games_completed", 0),
        compliance_scores=doc.get("compliance_scores", []),
        strict_mode=doc.get("strict_mode", False),
        failure_count=doc.get("failure_count", 0),
        failed_cycles=doc.get("failed_cycles", 0),
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=updated_at or datetime.now(timezone.utc),
        headline=doc.get("headline", "Focus Lock Active"),
        message=doc.get("message", ""),
    )


def should_trigger_deep_session(lock: FocusLock) -> bool:
    """Check if lock failure should trigger a deep session."""
    return lock.failed_cycles >= 2 or lock.state == "FAILED"
