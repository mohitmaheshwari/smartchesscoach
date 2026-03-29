"""
MODULE TRIGGER SERVICE - Step 10: Pattern Injection Engine

Detects which theory module applies to a game.
Handles:
- Module selection (max 1 per game)
- Trigger priority
- Auto-lock conditions (3+ triggers with guardrails)
- Injection history tracking
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from coach_state.theory_modules import (
    TheoryModule,
    ALL_MODULES,
    LESSON_TO_MODULE,
    get_module,
    get_module_for_lesson,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Auto-lock guardrails
AUTO_LOCK_TRIGGER_THRESHOLD = 3  # Need 3+ triggers in window
AUTO_LOCK_WINDOW_GAMES = 10  # Look at last 10 games
HIGH_CONFIDENCE_CP_SWING = 300  # Minimum cp swing for high-confidence trigger

# Injection cooldown
INJECTION_COOLDOWN_GAMES = 10  # Don't re-inject same module within 10 games


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ModuleTrigger:
    """Result of module detection for a single game."""
    triggered: bool
    module_key: Optional[str] = None
    module_name: Optional[str] = None
    category: Optional[str] = None
    rule: Optional[str] = None
    explanation: Optional[str] = None
    evidence_move: Optional[int] = None
    evidence_cp_loss: Optional[int] = None
    confidence: str = "low"  # "low" | "medium" | "high"
    should_auto_lock: bool = False
    trigger_count_in_window: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered": self.triggered,
            "module_key": self.module_key,
            "module_name": self.module_name,
            "category": self.category,
            "rule": self.rule,
            "explanation": self.explanation,
            "evidence_move": self.evidence_move,
            "evidence_cp_loss": self.evidence_cp_loss,
            "confidence": self.confidence,
            "should_auto_lock": self.should_auto_lock,
            "trigger_count_in_window": self.trigger_count_in_window,
        }


@dataclass
class InjectionRecord:
    """Record of a module injection."""
    user_id: str
    game_id: str
    module_key: str
    confidence: str
    cp_loss: int
    injected_at: str
    auto_locked: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "game_id": self.game_id,
            "module_key": self.module_key,
            "confidence": self.confidence,
            "cp_loss": self.cp_loss,
            "injected_at": self.injected_at,
            "auto_locked": self.auto_locked,
        }


# =============================================================================
# CORE DETECTION LOGIC
# =============================================================================

def detect_module_for_game(
    game_analysis: Dict[str, Any],
    user_rating: int,
    recent_injections: List[Dict[str, Any]] = None,
) -> ModuleTrigger:
    """
    Detect which theory module (if any) applies to this game.
    
    Trigger priority:
    1. High-intensity failure (≥300cp swing)
    2. Repeated lesson_key in last 5 games
    3. Endgame collapse
    4. Structural misplay
    
    Only inject if:
    - Rating appropriate
    - Not already injected in last 10 games
    """
    recent_injections = recent_injections or []
    
    # Get recently injected modules (cooldown check)
    recent_module_keys = {inj.get("module_key") for inj in recent_injections[-INJECTION_COOLDOWN_GAMES:]}
    
    # Extract analysis data
    lesson_key = game_analysis.get("lesson_key") or game_analysis.get("dominant_lesson_key")
    core_lesson = game_analysis.get("core_lesson", {})
    stockfish_analysis = game_analysis.get("stockfish_analysis", {})
    
    # Find biggest cp swing
    biggest_swing = _find_biggest_swing(stockfish_analysis)
    
    # Try to match a module
    matched_module = None
    evidence_move = None
    evidence_cp = 0
    
    # Priority 1: Check lesson_key mapping
    if lesson_key:
        matched_module = get_module_for_lesson(lesson_key)
    
    # Priority 2: Check core_lesson pattern
    if not matched_module and core_lesson:
        pattern = core_lesson.get("pattern", "")
        matched_module = get_module_for_lesson(pattern)
    
    # Priority 3: High-intensity failure detection
    if biggest_swing and biggest_swing.get("cp_loss", 0) >= HIGH_CONFIDENCE_CP_SWING:
        evidence_move = biggest_swing.get("move_number")
        evidence_cp = biggest_swing.get("cp_loss", 0)
        
        # Try to infer module from context if not already matched
        if not matched_module:
            matched_module = _infer_module_from_position(biggest_swing, game_analysis)
    
    # No module detected
    if not matched_module:
        return ModuleTrigger(triggered=False)
    
    # Check rating appropriateness
    if not (matched_module.min_rating <= user_rating <= matched_module.max_rating):
        logger.debug(f"Module {matched_module.key} not appropriate for rating {user_rating}")
        return ModuleTrigger(triggered=False)
    
    # Check cooldown
    if matched_module.key in recent_module_keys:
        logger.debug(f"Module {matched_module.key} on cooldown")
        return ModuleTrigger(triggered=False)
    
    # Determine confidence
    confidence = "low"
    if evidence_cp >= HIGH_CONFIDENCE_CP_SWING:
        confidence = "high"
    elif evidence_cp >= 150:
        confidence = "medium"
    
    return ModuleTrigger(
        triggered=True,
        module_key=matched_module.key,
        module_name=matched_module.name,
        category=matched_module.category,
        rule=matched_module.rule,
        explanation=matched_module.explanation,
        evidence_move=evidence_move,
        evidence_cp_loss=evidence_cp,
        confidence=confidence,
    )


def _find_biggest_swing(stockfish_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the biggest eval swing in the game."""
    move_evals = stockfish_analysis.get("move_evaluations", [])
    if not move_evals:
        return None
    
    biggest = None
    biggest_loss = 0
    
    for move_eval in move_evals:
        cp_loss = move_eval.get("cp_loss", 0)
        if cp_loss > biggest_loss:
            biggest_loss = cp_loss
            biggest = move_eval
    
    return biggest


def _infer_module_from_position(swing: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[TheoryModule]:
    """
    Infer the most likely module from position context.
    
    This is a fallback when no direct lesson_key mapping exists.
    """
    # Check for conversion failures (advantage lost)
    eval_before = swing.get("eval_before", 0)
    if eval_before >= 200:  # Was winning
        return get_module("SIMPLIFY_WHEN_AHEAD")
    
    # Check for endgame issues
    phase = analysis.get("game_phase") or analysis.get("final_phase", "")
    if "endgame" in phase.lower():
        return get_module("ACTIVATE_KING_ENDGAME")
    
    # Default to forcing moves if high tactical loss
    if swing.get("cp_loss", 0) >= 300:
        return get_module("FORCING_MOVES_FIRST")
    
    return None


# =============================================================================
# AUTO-LOCK DETECTION
# =============================================================================

def check_auto_lock_condition(
    module_key: str,
    trigger_confidence: str,
    recent_triggers: List[Dict[str, Any]],
    has_active_lock: bool,
) -> tuple[bool, int]:
    """
    Check if auto-lock should be activated.
    
    Guardrails:
    - Only after 3+ triggers in last 10 games
    - Only if user has no active lock
    - Only for high-confidence triggers (≥300cp swing)
    
    Returns: (should_auto_lock, trigger_count)
    """
    # Guardrail 1: No auto-lock if already locked
    if has_active_lock:
        return False, 0
    
    # Guardrail 2: Only high-confidence triggers
    if trigger_confidence != "high":
        return False, 0
    
    # Count triggers for this module in window
    trigger_count = sum(
        1 for t in recent_triggers[-AUTO_LOCK_WINDOW_GAMES:]
        if t.get("module_key") == module_key
    )
    
    # Include current trigger
    trigger_count += 1
    
    # Guardrail 3: Need 3+ triggers
    if trigger_count >= AUTO_LOCK_TRIGGER_THRESHOLD:
        return True, trigger_count
    
    return False, trigger_count


# =============================================================================
# INJECTION TRACKING
# =============================================================================

def create_injection_record(
    user_id: str,
    game_id: str,
    trigger: ModuleTrigger,
    auto_locked: bool = False,
) -> InjectionRecord:
    """Create a record of module injection for tracking."""
    return InjectionRecord(
        user_id=user_id,
        game_id=game_id,
        module_key=trigger.module_key,
        confidence=trigger.confidence,
        cp_loss=trigger.evidence_cp_loss or 0,
        injected_at=datetime.now(timezone.utc).isoformat(),
        auto_locked=auto_locked,
    )


def get_module_injection_stats(injections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate injection statistics for a user.
    
    Returns counts and patterns for analytics.
    """
    if not injections:
        return {"total_injections": 0, "modules": {}}
    
    module_counts = {}
    auto_lock_count = 0
    high_confidence_count = 0
    
    for inj in injections:
        key = inj.get("module_key", "unknown")
        module_counts[key] = module_counts.get(key, 0) + 1
        
        if inj.get("auto_locked"):
            auto_lock_count += 1
        if inj.get("confidence") == "high":
            high_confidence_count += 1
    
    # Find most common module
    most_common = max(module_counts.items(), key=lambda x: x[1]) if module_counts else (None, 0)
    
    return {
        "total_injections": len(injections),
        "modules": module_counts,
        "most_common_module": most_common[0],
        "most_common_count": most_common[1],
        "auto_lock_count": auto_lock_count,
        "high_confidence_count": high_confidence_count,
    }


# =============================================================================
# FOCUS LOCK INTEGRATION
# =============================================================================

def get_focus_lock_lesson_for_module(module_key: str) -> Optional[str]:
    """
    Map a theory module to a Focus Lock lesson_key.
    
    Focus Lock only supports 3 lessons currently:
    - FORCING_BLIND
    - STOPPED_CALCULATION_EARLY
    - THREAT_VERIFICATION
    
    This maps theory modules to the closest Focus Lock lesson.
    """
    module = get_module(module_key)
    if not module:
        return None
    
    # Direct mappings
    if module_key == "FORCING_MOVES_FIRST":
        return "FORCING_BLIND"
    
    if module_key in ("ZWISCHENZUG", "DISCOVERED_ATTACK"):
        return "STOPPED_CALCULATION_EARLY"
    
    if module_key in ("BACK_RANK_WEAKNESS", "OVERLOADED_DEFENDER", "REMOVE_THE_DEFENDER"):
        return "THREAT_VERIFICATION"
    
    # Category-based fallbacks
    if module.category == "tactical":
        return "FORCING_BLIND"
    
    if module.category == "conversion":
        return "STOPPED_CALCULATION_EARLY"
    
    # Default
    return "FORCING_BLIND"
