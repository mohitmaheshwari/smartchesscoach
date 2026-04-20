"""
CoachingPolicy — decides WHETHER the coach speaks and in what VOICE.

Layer 3 of the coaching pipeline (extract → critique → policy → render).
Reads a MoveCritique plus student context, outputs a PolicyDecision.

Core rule set (locked with user on 2026-04-20):
    < 1000       → CHATTY   (speaks on every move)
    1000–1399    → MEDIUM   (silent on nudges/directionless)
    1400+        → FOCUSED  (speaks only on teaching-worthy deviations)

Teaching-worthy deviations (speak regardless of band):
    WALKED_INTO, TACTICAL_MISS, PRINCIPLE_MISS

User override: if `verbosity_override` is set on the student context it wins over
the rating-derived band — power-users can dial their own volume.

This module never renders text. It only decides speak/silent + tone. Text comes
from coaching_library / smart_coaching, consuming the critique + this decision.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

from services.move_critique import MoveCritique, DeviationType, Principle
from deterministic_coach_service import get_rating_band


class Voice(str, Enum):
    """Coach voice for the rendering layer."""
    CHATTY = "chatty"      # encouraging, speaks often, simple language
    MEDIUM = "medium"      # balanced — teaches when it matters
    FOCUSED = "focused"    # peer-level, interrupts only for real teaching moments


@dataclass
class StudentContext:
    """Minimum context the policy needs about the student."""
    rating: int = 1200
    verbosity_override: Optional[str] = None   # "chatty" | "medium" | "focused"
    active_patterns: List[str] = field(default_factory=list)  # Engine 1 active weakness keys


@dataclass
class PolicyDecision:
    should_speak: bool
    voice: Voice
    reason: str = ""                           # why we decided this way (logging / debug)
    connect_to_weakness: Optional[str] = None  # Engine 1 pattern this critique reinforces
    is_milestone: bool = False                 # e.g. student avoided a usually-failed pattern


# ─────────────────────────────────────────────────────────────────────────────
# Band → voice mapping (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

_BAND_TO_VOICE = {
    "beginner_low": Voice.CHATTY,      # <1000
    "beginner_high": Voice.MEDIUM,     # 1000-1399
    "intermediate": Voice.FOCUSED,     # 1400-1799
    "advanced": Voice.FOCUSED,         # 1800+
}


def _voice_for(student: StudentContext) -> Voice:
    """Resolve voice from override first, then rating band."""
    if student.verbosity_override:
        try:
            return Voice(student.verbosity_override)
        except ValueError:
            pass
    band = get_rating_band(student.rating)
    return _BAND_TO_VOICE.get(band["name"], Voice.MEDIUM)


# ─────────────────────────────────────────────────────────────────────────────
# Decision rules
# ─────────────────────────────────────────────────────────────────────────────

_ALWAYS_TEACH = {
    DeviationType.WALKED_INTO,
    DeviationType.TACTICAL_MISS,
    DeviationType.PRINCIPLE_MISS,
}

_SILENT_IF_FOCUSED = {
    DeviationType.ON_PLAN_NUDGE,
    DeviationType.DIRECTIONLESS,
    DeviationType.RIGHT_IDEA_WRONG_SQUARE,
}


def _critique_matches_active_pattern(critique: MoveCritique,
                                      active_patterns: List[str]) -> Optional[str]:
    """If this critique reinforces an Engine 1 active weakness, return the pattern name."""
    if not active_patterns:
        return None
    # Map teaching_focus (Principle) to pattern keys. Loose match by substring so
    # we don't need to hardcode every weakness spelling.
    focus_str = critique.teaching_focus.value if critique.teaching_focus else ""
    for pat in active_patterns:
        if not pat:
            continue
        pat_lower = pat.lower()
        if focus_str and focus_str in pat_lower:
            return pat
        if critique.walked_into_pattern and any(
            kw in pat_lower for kw in critique.walked_into_pattern.lower().split()
        ):
            return pat
    return None


def decide(critique: MoveCritique, student: StudentContext) -> PolicyDecision:
    """Decide whether to speak + what voice, given critique + student context."""
    voice = _voice_for(student)
    connect = _critique_matches_active_pattern(critique, student.active_patterns)
    dev = critique.deviation_type

    # Teaching-worthy deviations: always speak, any band.
    if dev in _ALWAYS_TEACH:
        return PolicyDecision(
            should_speak=True,
            voice=voice,
            reason=f"teaching moment: {dev.value}",
            connect_to_weakness=connect,
        )

    # BEST_MOVE: chatty affirms every time; medium affirms briefly; focused usually silent
    if dev == DeviationType.BEST_MOVE:
        if voice == Voice.CHATTY:
            milestone = connect is not None  # student avoided a known weakness
            return PolicyDecision(
                should_speak=True, voice=voice,
                reason="chatty affirms on best move",
                is_milestone=milestone,
                connect_to_weakness=connect,
            )
        if voice == Voice.MEDIUM:
            # speak briefly only if it avoids a known weakness, else silent
            if connect:
                return PolicyDecision(
                    should_speak=True, voice=voice,
                    reason="best move avoided known weakness",
                    is_milestone=True,
                    connect_to_weakness=connect,
                )
            return PolicyDecision(
                should_speak=False, voice=voice,
                reason="medium: silent on routine best move",
            )
        # focused: silent on best move unless milestone
        if connect:
            return PolicyDecision(
                should_speak=True, voice=voice,
                reason="focused: milestone (avoided weakness)",
                is_milestone=True,
                connect_to_weakness=connect,
            )
        return PolicyDecision(
            should_speak=False, voice=voice,
            reason="focused: silent on routine best move",
        )

    # ON_PLAN_NUDGE / DIRECTIONLESS / RIGHT_IDEA_WRONG_SQUARE
    if dev in _SILENT_IF_FOCUSED:
        if voice == Voice.CHATTY:
            return PolicyDecision(
                should_speak=True, voice=voice,
                reason=f"chatty: warm acknowledgment on {dev.value}",
                connect_to_weakness=connect,
            )
        if voice == Voice.MEDIUM:
            # Medium speaks on RIGHT_IDEA_WRONG_SQUARE (brief teaching),
            # silent on nudge/directionless.
            if dev == DeviationType.RIGHT_IDEA_WRONG_SQUARE:
                return PolicyDecision(
                    should_speak=True, voice=voice,
                    reason="medium: brief nudge on square choice",
                    connect_to_weakness=connect,
                )
            return PolicyDecision(
                should_speak=False, voice=voice,
                reason=f"medium: silent on {dev.value}",
            )
        # focused
        return PolicyDecision(
            should_speak=False, voice=voice,
            reason=f"focused: silent on {dev.value}",
        )

    # Fallback — shouldn't happen if DeviationType is exhaustive.
    return PolicyDecision(
        should_speak=False, voice=voice,
        reason=f"unknown deviation: {dev}",
    )
