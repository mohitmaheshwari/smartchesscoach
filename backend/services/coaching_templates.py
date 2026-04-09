"""
Coaching Templates — Production-ready messages for the 4-layer system.

Rules:
  - Never suggest moves
  - One idea per message
  - Short > clever
  - Position-specific > generic
  - Opponent > self
  - Each template has variants to avoid repetition

Usage:
  text = pick_template("ambient", "center_pressure", signals)
"""

import random
from typing import Optional, Dict, List

# ─── AMBIENT TEMPLATES ────────────────────────────────────────────
# Purpose: describe what's happening. No judgment, no correction.

AMBIENT = {
    # Opponent idea (PRIORITY — most important ambient signal)
    "opponent_threat": {
        "texts": [
            "Their {attacker} now targets your {target} on {square}.",
            "Watch out — their {attacker} is aiming at your {target}.",
            "Their {attacker} creates pressure on {square}.",
        ],
        "needs": ["attacker", "target", "square"],
    },
    "opponent_activity": {
        "texts": [
            "Your opponent just improved a key piece.",
            "Their pieces are becoming more active.",
            "That move strengthened their position.",
        ],
    },
    "opponent_center_pressure": {
        "texts": [
            "Black is challenging your center now.",
            "The center tension is starting to matter.",
            "Black is trying to undermine your center.",
            "Your opponent has more influence in the center.",
        ],
    },
    "opponent_kingside": {
        "texts": [
            "That move points toward your king side.",
            "Black is preparing something on the king side.",
        ],
    },

    # King safety context
    "king_uncommitted": {
        "texts": [
            "Your king is still in the center.",
            "King safety is not settled yet.",
            "Your king is still uncommitted.",
            "This position is about king safety first.",
        ],
    },

    # Development context
    "development_phase": {
        "texts": [
            "This is still a development position.",
            "Your pieces are not fully coordinated yet.",
            "Development is not complete yet.",
        ],
    },

    # Structure awareness
    "structure_solid": {
        "texts": [
            "Your pawn structure is still solid.",
        ],
    },
    "structure_loosening": {
        "texts": [
            "Your structure is starting to loosen.",
            "Black now has targets in your position.",
        ],
    },

    # Reinforcement (only non-obvious strong moves)
    "strong_move": {
        "texts": [
            "Good. You improved your worst piece.",
            "Good. You kept control instead of rushing.",
            "Nice. You strengthened your position without risk.",
            "Good. You addressed the right priority.",
        ],
    },

    # Center context
    "center_stable": {
        "texts": [
            "Your center is stable for now.",
        ],
    },
}

# ─── ADVISORY TEMPLATES ──────────────────────────────────────────
# Purpose: suggest adjustment. Still non-blocking.

ADVISORY = {
    # Premature attack
    "premature_attack": {
        "texts": [
            "Your pieces are active, but your setup isn't finished.",
            "You are starting to attack before finishing coordination.",
            "You are creating threats without full coordination.",
            "Your pieces are not ready to support this attack yet.",
        ],
    },

    # King safety warning
    "king_safety": {
        "texts": [
            "Your king safety is still the bigger issue here.",
            "Before pushing further, your king needs attention.",
            "Your position is active, but your king is exposed.",
            "King safety matters more than attack right now.",
        ],
    },

    # Loose pieces
    "loose_pieces": {
        "texts": [
            "You have loose pieces that need attention.",
            "Some of your pieces are not properly protected.",
            "Your position has targets your opponent can hit.",
            "Secure your pieces before expanding.",
        ],
    },

    # Opponent pressure (advisory level)
    "opponent_pressure": {
        "texts": [
            "Black is building pressure — you need to respond soon.",
            "Your opponent is improving faster than you right now.",
            "Black's pieces are becoming more active than yours.",
        ],
    },

    # Drift detection
    "drift_warning": {
        "texts": [
            "Your position is drifting from stability.",
            "You are losing coordination between your pieces.",
            "Your moves are no longer connected to a clear plan.",
        ],
    },

    # Development
    "development": {
        "texts": [
            "This is still a development position, not an attack yet.",
            "You need to finish development before creating threats.",
            "Complete your setup before starting action.",
        ],
    },

    # Center mismanagement
    "center_warning": {
        "texts": [
            "The center is unstable — be careful opening it.",
            "You are giving up control of the center.",
            "Your center needs support before expansion.",
        ],
    },

    # Plan correction
    "plan_guidance": {
        "texts": [
            "Improve your worst piece before doing more.",
            "Stability matters more than activity here.",
            "This position rewards patience, not forcing moves.",
            "There was something more accurate. Think about what the position needs.",
        ],
    },

    # Inaccuracy (generic fallback — position-specific preferred)
    "inaccuracy": {
        "texts": [
            "There was something more accurate here.",
            "Think about what the position needs most.",
            "This is close, but not quite right.",
        ],
    },

    # Opponent threat (advisory level, non-critical)
    "opponent_threat_advisory": {
        "texts": [
            "Your opponent is threatening something you must address.",
            "Check what changed in their position.",
            "That move created a new problem you must deal with.",
        ],
    },
}

# ─── CRITICAL TEMPLATES ──────────────────────────────────────────
# Purpose: force awareness. Sharp, direct.

CRITICAL = {
    # Hanging piece
    "hung_piece": {
        "texts": [
            "Stop. Your {piece} on {square} is undefended.",
            "Stop. Your {piece} is hanging.",
            "Stop. You are losing your {piece}.",
        ],
        "questions": [
            "What is your opponent attacking?",
            "Did you check if all your pieces are protected?",
            "Which of your pieces is undefended?",
        ],
        "needs": ["piece", "square"],
    },

    # Ignored threat
    "ignored_threat": {
        "texts": [
            "You ignored a direct threat on your {piece}.",
            "You moved without responding to danger.",
            "Your opponent's last move had a threat you missed.",
        ],
        "questions": [
            "What changed after their last move?",
            "What was your opponent threatening?",
        ],
        "needs": ["piece"],
    },

    # Ignored capture
    "ignored_capture": {
        "texts": [
            "Your opponent's {piece} on {square} was free to take.",
            "You missed a free capture.",
            "There was material to win that you overlooked.",
        ],
        "questions": [
            "Did you check for captures first?",
            "Did you scan for free pieces?",
        ],
        "needs": ["piece", "square"],
    },

    # Generic blunder/mistake
    "blunder": {
        "texts": [
            "This move drops material.",
            "This turns a good position into a bad one.",
            "This move loses your advantage.",
        ],
        "questions": [
            "Did you check your opponent's reply?",
            "What can your opponent do after this?",
        ],
    },
    "mistake": {
        "texts": [
            "This move loses ground.",
            "This makes your position harder to play.",
            "You gave your opponent an opportunity here.",
        ],
        "questions": [
            "Did you calculate your opponent's reply?",
            "What does your opponent want to do now?",
        ],
    },

    # Conversion failure
    "conversion_failure": {
        "texts": [
            "You were winning. This move lets the advantage slip.",
            "You had a winning position and gave it back.",
            "In winning positions, keep it simple.",
        ],
        "questions": [
            "When you're ahead, what should your priority be?",
        ],
    },

    # Game shift
    "game_shift": {
        "texts": [
            "This is where the game shifted.",
            "Until now the position was manageable.",
            "This is the turning point.",
        ],
    },

    # King exposure
    "king_exposure": {
        "texts": [
            "Your king is now exposed.",
            "You opened your king side too early.",
            "Your king is not safe here.",
        ],
        "questions": [
            "Is your king safer than your opponent's?",
        ],
    },

    # Pattern repeat
    "pattern_repeat": {
        "texts": [
            "This is happening again: you are not checking threats.",
            "Same mistake again: you are moving too quickly.",
            "You are repeating the same pattern.",
        ],
        "questions": [
            "What should you check before every move?",
        ],
    },
}


# ─── TEMPLATE PICKER ─────────────────────────────────────────────

# Track used templates per session to avoid repetition
_session_used = {}


def pick_template(
    layer: str,
    concept_key: str,
    signals: Dict = None,
    session_id: str = None,
) -> Dict[str, Optional[str]]:
    """
    Pick a template for the given layer and concept.

    Returns:
        {"text": "...", "question": "..." or None}
    """
    signals = signals or {}

    if layer == "ambient":
        templates = AMBIENT.get(concept_key, {})
    elif layer == "advisory":
        templates = ADVISORY.get(concept_key, {})
    elif layer == "critical_interrupt":
        templates = CRITICAL.get(concept_key, {})
    else:
        return {"text": None, "question": None}

    texts = templates.get("texts", [])
    questions = templates.get("questions", [])
    needs = templates.get("needs", [])

    if not texts:
        return {"text": None, "question": None}

    # Track used templates to avoid repetition
    cache_key = f"{session_id}_{concept_key}" if session_id else concept_key
    used = _session_used.get(cache_key, set())

    # Pick unused template first, fallback to random
    available = [t for i, t in enumerate(texts) if i not in used]
    if not available:
        # Reset and pick any
        used = set()
        available = texts

    text = random.choice(available)
    used.add(texts.index(text))
    _session_used[cache_key] = used

    # Format with signal data
    if needs:
        format_vars = {}
        for key in needs:
            format_vars[key] = signals.get(key, "piece")
        try:
            text = text.format(**format_vars)
        except (KeyError, IndexError):
            pass

    question = random.choice(questions) if questions else None

    return {"text": text, "question": question}


def reset_session_templates(session_id: str = None):
    """Reset template tracking for a new game."""
    if session_id:
        keys_to_remove = [k for k in _session_used if k.startswith(f"{session_id}_")]
        for k in keys_to_remove:
            del _session_used[k]
    else:
        _session_used.clear()
