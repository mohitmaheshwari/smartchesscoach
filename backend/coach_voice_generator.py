"""
Coach Voice Generator - Deterministic Indian English

Purpose: Convert signals into 3 lines: headline, explanation, one instruction.
NO LLM usage. Pure deterministic mapping.

Output structure:
{ headline, explanation, focus_instruction, tone_level }

Language rules:
- Simple Indian English
- No corporate terms
- Short lines (headline ≤10 words, explanation ≤18 words, instruction ≤16 words)
- Exactly ONE instruction per tab
"""

from typing import Dict, Optional


# ============================================
# HEADLINE MAPPING (signal → headline text)
# ============================================

HEADLINE_MAP = {
    # Improvement signals
    "major_improvement": "Your decision quality has improved significantly.",
    "improving": "Your decision stability is improving.",
    "slight_improvement": "Small improvement in your recent games.",
    
    # Stable signals
    "stable": "Your performance level is stable.",
    "stable_hidden": "Your level is currently stable.",
    
    # Decline signals  
    "declining": "Decision stability has dropped recently.",
    "major_decline": "Your game quality has dropped significantly.",
    
    # Context-specific
    "stability_improving": "Your decision stability is improving.",
    "stability_declining": "Decision stability has dropped recently.",
    "advantage_risk_increasing": "You are slipping when ahead.",
    "advantage_risk_decreasing": "You are finishing winning games better."
}

# Anti-repetition alternate headlines
ALTERNATE_HEADLINES = {
    "stable": "Your recent games show gradual change.",
    "stable_hidden": "Stable week. Next jump needs one clean habit."
}


# ============================================
# EXPLANATION TEMPLATES
# ============================================

def get_stability_explanation(stability_band: str) -> str:
    """Get explanation for stability band."""
    if stability_band == "volatile":
        return "Your games swing a lot. Clean games, then sudden slips."
    elif stability_band == "moderate":
        return "Mostly okay, but some lapses still happen."
    elif stability_band == "stable":
        return "Your decision quality is becoming consistent."
    return "Your performance is being tracked."


def get_context_clause(phase_instability: Optional[str], advantage_risk: Optional[str]) -> str:
    """Get one context clause based on phase or advantage risk."""
    if phase_instability:
        phase_map = {
            "opening": "Most slips happen in the opening.",
            "middlegame": "Most slips happen in middlegame.",
            "endgame": "Most slips happen in endgame."
        }
        return phase_map.get(phase_instability.lower(), "")
    
    if advantage_risk and advantage_risk.lower() in ["high", "high risk"]:
        return "When ahead, you relax and make mistakes."
    
    return ""


def build_explanation(stability_band: str, phase_instability: Optional[str] = None,
                     advantage_risk: Optional[str] = None, confidence: float = 1.0) -> str:
    """Build explanation with optional context clause."""
    base = get_stability_explanation(stability_band)
    context = get_context_clause(phase_instability, advantage_risk)
    
    # Add confidence modifier
    if confidence < 0.6:
        base = f"Early trend suggests: {base}"
    
    # Add context clause if available
    if context:
        return f"{base} {context}"
    
    return base


# ============================================
# INSTRUCTION MAPPING (primary_driver → instruction)
# ============================================

INSTRUCTION_MAP = {
    # Cognitive drivers
    "structural_misjudgment": "Before pawn moves, ask what becomes weak.",
    "missed_forcing_move": "Every move: checks, captures, threats.",
    "critical_moment_drift": "When position changes, pause and scan threats.",
    "advantage_mismanagement": "When ahead, simplify and avoid risky attacks.",
    "random_critical_move": "In sharp positions, calculate 2 moves deeper.",
    "time_pressure_drop": "Spend extra time in complex positions.",
    "time_pressure": "Spend extra time in complex positions.",
    
    # Existing weakness IDs from baseline_service
    "relaxes_when_winning": "When ahead, simplify and avoid risky attacks.",
    "piece_safety": "Before each move, scan for undefended pieces.",
    "tactical_blindness": "Every move: checks, captures, threats.",
    "time_trouble": "Spend extra time in complex positions.",
    
    # Default
    "default": "Every move: checks, captures, threats."
}


def get_instruction(primary_driver: Optional[str]) -> str:
    """Get instruction for primary driver."""
    if primary_driver and primary_driver in INSTRUCTION_MAP:
        return INSTRUCTION_MAP[primary_driver]
    return INSTRUCTION_MAP["default"]


# ============================================
# TONE LEVEL
# ============================================

def get_tone_level(headline_signal: str) -> str:
    """Determine tone level for UI styling."""
    if headline_signal in ["major_improvement", "improving"]:
        return "positive"
    elif headline_signal in ["major_decline", "declining"]:
        return "concern"
    else:
        return "neutral"


# ============================================
# MAIN GENERATOR FUNCTION
# ============================================

def generate_coach_voice(
    headline_signal: str,
    stability_band: str,
    primary_driver: Optional[str] = None,
    phase_instability: Optional[str] = None,
    advantage_risk: Optional[str] = None,
    confidence: float = 1.0,
    consecutive_stable_count: int = 0
) -> Dict:
    """
    Generate coach voice output.
    
    Returns:
    {
        headline: str (≤10 words),
        explanation: str (≤18 words),
        focus_instruction: str (≤16 words),
        tone_level: str (positive/concern/neutral)
    }
    """
    # Get headline
    headline = HEADLINE_MAP.get(headline_signal, HEADLINE_MAP["stable"])
    
    # Anti-repetition: if stable for 2+ consecutive times, use alternate
    if consecutive_stable_count >= 2 and headline_signal in ["stable", "stable_hidden"]:
        headline = ALTERNATE_HEADLINES.get(headline_signal, headline)
    
    # Build explanation
    explanation = build_explanation(
        stability_band=stability_band,
        phase_instability=phase_instability,
        advantage_risk=advantage_risk,
        confidence=confidence
    )
    
    # Get instruction
    focus_instruction = get_instruction(primary_driver)
    
    # Get tone level
    tone_level = get_tone_level(headline_signal)
    
    return {
        "headline": headline,
        "explanation": explanation,
        "focus_instruction": focus_instruction,
        "tone_level": tone_level
    }


# ============================================
# DOPAMINE LOOP: BADGE LOGIC
# ============================================

def should_show_improvement_badge(headline_signal: str) -> bool:
    """Check if we should show 'Big improvement this week' badge."""
    return headline_signal == "major_improvement"


def get_badge_text(headline_signal: str) -> Optional[str]:
    """Get badge text if applicable."""
    if headline_signal == "major_improvement":
        return "Big improvement this week."
    return None


# ============================================
# HELPER: Generate full voice for a tab
# ============================================

def generate_tab_voice(
    stat_interpretation: Dict,
    primary_driver: Optional[str] = None,
    phase_instability: Optional[str] = None,
    advantage_risk: Optional[str] = None,
    consecutive_stable_count: int = 0
) -> Dict:
    """
    Generate complete voice output for a tab.
    
    Takes stat_interpretation output and generates voice.
    """
    if not stat_interpretation.get("evaluation_ready", False):
        return {
            "headline": "Play more games to see your progress.",
            "explanation": stat_interpretation.get("message", "More games needed for analysis."),
            "focus_instruction": get_instruction(None),
            "tone_level": "neutral",
            "badge": None
        }
    
    signals = stat_interpretation.get("signals", {})
    headline_signal = signals.get("headline", "stable")
    stability_band = stat_interpretation.get("stability_band", "moderate")
    confidence = stat_interpretation.get("confidence", 1.0)
    
    voice = generate_coach_voice(
        headline_signal=headline_signal,
        stability_band=stability_band,
        primary_driver=primary_driver,
        phase_instability=phase_instability,
        advantage_risk=advantage_risk,
        confidence=confidence,
        consecutive_stable_count=consecutive_stable_count
    )
    
    # Add badge if applicable
    voice["badge"] = get_badge_text(headline_signal)
    
    return voice
