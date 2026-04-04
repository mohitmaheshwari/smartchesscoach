"""
Coach Voice — Personality Wrapper
=================================

Takes accurate coaching content and rewrites it in a human voice.
NOT an LLM call. Pure deterministic string transforms. Fast, free, consistent.

The wrapper doesn't change WHAT the coach says. It changes HOW.

Inputs:
- message: the coaching content (already accurate from diagnosis engine)
- intensity: calm / firm / sharp_light / sharp_heavy / recovery / brilliant
- context: {games_together, pattern_count, is_recovery, streak_type, streak_count}

The coach's personality:
- Direct. Never vague.
- Warm when you earn it. Firm when you need it.
- Remembers how long you've been together.
- Gets more blunt the longer you've trained together.
- Genuinely celebrates progress. Genuinely confronts patterns.
"""

import random
from typing import Dict, Optional


# ── RELATIONSHIP TIERS ──
# How the coach talks changes based on how many games you've played together.
# Early: polite, encouraging. Later: direct, blunt, real.

def _get_familiarity(games_together: int) -> str:
    if games_together >= 20:
        return "blunt"       # "We both know this is your problem."
    if games_together >= 10:
        return "familiar"    # "You know better than this."
    if games_together >= 5:
        return "warm"        # "You're getting better. Let's keep going."
    return "formal"          # "This is something to work on."


# ── VOICE TRANSFORMS ──

# Openers — injected at the start of messages based on intensity
_OPENERS = {
    "calm": {
        "formal": ["", ""],
        "warm": ["Nice. ", ""],
        "familiar": ["That's the stuff. ", ""],
        "blunt": ["", ""],
    },
    "firm": {
        "formal": ["", ""],
        "warm": ["Hmm. ", ""],
        "familiar": ["Look — ", "Okay, "],
        "blunt": ["Right. ", ""],
    },
    "sharp_light": {
        "formal": ["", ""],
        "warm": ["", ""],
        "familiar": ["Come on. ", ""],
        "blunt": ["Again? ", "Seriously. "],
    },
    "sharp_heavy": {
        "formal": ["", ""],
        "warm": ["", ""],
        "familiar": ["", ""],
        "blunt": ["Listen. ", "Stop. "],
    },
    "recovery": {
        "formal": ["", ""],
        "warm": ["Hey — ", ""],
        "familiar": ["", ""],
        "blunt": ["", ""],
    },
    "brilliant": {
        "formal": ["", ""],
        "warm": ["Wow. ", ""],
        "familiar": ["Hold on — ", "Wait. "],
        "blunt": ["", ""],
    },
}

# Closers — appended at the end based on intensity + familiarity
_CLOSERS = {
    "calm": {
        "formal": ["", ""],
        "warm": [" Keep it up.", ""],
        "familiar": [" This is you at your best.", ""],
        "blunt": ["", ""],
    },
    "firm": {
        "formal": ["", ""],
        "warm": [" You can do better.", ""],
        "familiar": [" But you know that.", " One moment — that's all it was."],
        "blunt": [" Don't let it happen again.", " You're better than that move."],
    },
    "sharp_light": {
        "formal": ["", ""],
        "warm": ["", ""],
        "familiar": [" We keep coming back to this.", ""],
        "blunt": [" How many more games?", " Fix it."],
    },
    "sharp_heavy": {
        "formal": ["", ""],
        "warm": ["", ""],
        "familiar": [" You're better than this.", ""],
        "blunt": [" This is the one thing between you and the next level.", " Your rating will jump the day you stop doing this."],
    },
    "recovery": {
        "formal": [" Good progress.", ""],
        "warm": [" I noticed.", " That's real growth."],
        "familiar": [" Don't stop.", " You're building something here."],
        "blunt": [" About time.", " Now keep it going."],
    },
    "brilliant": {
        "formal": ["", ""],
        "warm": [" Remember this feeling.", ""],
        "familiar": [" This is your ceiling. Now make it your floor.", ""],
        "blunt": [" That's the player you're supposed to be.", " Do this every game."],
    },
}

# Pattern-count-specific injections (mid-sentence)
_PATTERN_INJECTIONS = {
    3: "We've seen this before. ",
    4: "Third time now. ",
    5: "This is becoming your thing. ",
    6: "You know what this is. ",
    7: "This is THE thing. ",
    8: "Eight games with this now. ",
    9: "I'm not going to stop bringing this up. ",
    10: "Ten games. This is who you are until you fix it. ",
}

# Streak-aware injections
_STREAK_INJECTIONS = {
    ("W", 3): "Three in a row — you're in the zone. ",
    ("W", 5): "Five wins. Something clicked. ",
    ("L", 3): "Three losses. Let's slow down. ",
    ("L", 5): "Five losses. Stop playing and start reviewing. ",
}

# Games-together milestone injections (used once per milestone)
_MILESTONE_INJECTIONS = {
    5: "Five games together now. I'm starting to know your chess. ",
    10: "Ten games. I know your patterns. ",
    20: "Twenty games. We've been through a lot. ",
    50: "Fifty games. I know you better than you know your own chess. ",
}


def apply_coach_voice(
    message: str,
    intensity: str = "calm",
    context: Optional[Dict] = None,
) -> str:
    """
    Apply coach personality to a coaching message.

    Args:
        message: The raw coaching content (already accurate)
        intensity: calm / firm / sharp_light / sharp_heavy / recovery / brilliant
        context: {
            games_together: int,
            pattern_count: int,
            is_recovery: bool,
            streak_type: "W" | "L" | None,
            streak_count: int,
            move_quality: str,
        }

    Returns:
        The same message rewritten in the coach's voice.
    """
    if not message or not message.strip():
        return message

    ctx = context or {}
    games = ctx.get("games_together", 0)
    pattern_count = ctx.get("pattern_count", 0)
    streak_type = ctx.get("streak_type")
    streak_count = ctx.get("streak_count", 0)
    is_recovery = ctx.get("is_recovery", False)

    # Override intensity for recovery
    if is_recovery:
        intensity = "recovery"

    familiarity = _get_familiarity(games)

    # ── BUILD THE VOICED MESSAGE ──

    # 1. Pick opener
    openers = _OPENERS.get(intensity, _OPENERS["calm"]).get(familiarity, [""])
    opener = random.choice(openers)

    # 2. Pick closer
    closers = _CLOSERS.get(intensity, _CLOSERS["calm"]).get(familiarity, [""])
    closer = random.choice(closers)

    # 3. Pattern injection (only for sharp intensities)
    pattern_inject = ""
    if pattern_count >= 3 and intensity in ("sharp_light", "sharp_heavy", "firm"):
        pattern_inject = _PATTERN_INJECTIONS.get(pattern_count, "")

    # 4. Streak injection (only at notable streaks)
    streak_inject = ""
    if streak_type and streak_count >= 3:
        streak_inject = _STREAK_INJECTIONS.get((streak_type, min(streak_count, 5)), "")

    # 5. Milestone injection (very rare)
    milestone = ""
    if games in _MILESTONE_INJECTIONS:
        milestone = _MILESTONE_INJECTIONS[games]

    # ── ASSEMBLE ──
    # Structure: [opener] [milestone] [streak] [pattern] [message] [closer]
    parts = []
    if opener:
        parts.append(opener)
    if milestone:
        parts.append(milestone)
    if streak_inject:
        parts.append(streak_inject)
    if pattern_inject:
        parts.append(pattern_inject)

    parts.append(message.strip())

    result = "".join(parts)

    if closer:
        result = result.rstrip(".!") + "." + closer

    return result.strip()
