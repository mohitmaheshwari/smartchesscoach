"""
CoachingVoice — renders a MoveCritique into text in the correct voice.

Layer 4 of the coaching pipeline. Consumes a MoveCritique (from move_critique)
and a PolicyDecision (from coaching_policy) and returns a V5Coaching-compatible
dict with narrative, question, hint, plan, teaching_focus_label.

Voice principles (the teaching contract):
    Every message is ONE of:
      1. a principle named ("king safety", "development")
      2. a pattern named ("hanging piece on f6", "knight fork")
      3. a question the student should ask themselves
      4. a concrete threat

    NEVER: "Stockfish thinks X is better" or "Qd1 was sharper".

Voice differences:
    CHATTY   — simple language, warm, speaks every turn, short questions
    MEDIUM   — balanced, names principle + one question
    FOCUSED  — concise, peer-level, Socratic — often pure question form
"""

import random
from typing import Dict, Optional

from services.move_critique import MoveCritique, DeviationType, Principle
from services.coaching_policy import PolicyDecision, Voice


# ─────────────────────────────────────────────────────────────────────────────
# Principle labels (short, user-facing)
# ─────────────────────────────────────────────────────────────────────────────

PRINCIPLE_LABEL = {
    Principle.PIECE_SAFETY: "Piece safety",
    Principle.KING_SAFETY: "King safety",
    Principle.DEVELOPMENT: "Development",
    Principle.CENTRAL_CONTROL: "Central control",
    Principle.TACTICAL_AWARENESS: "Tactical awareness",
    Principle.OPPONENT_THREATS: "Opponent threats",
    Principle.PIECE_ACTIVITY: "Piece activity",
    Principle.TEMPO: "Tempo",
}


# ─────────────────────────────────────────────────────────────────────────────
# Template sets
# Each (DeviationType, Voice) key returns a list of {narrative, question, hint}.
# Placeholders: {played}, {best}, {pattern}, {principle}
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATES = {
    # ─── BEST_MOVE ───
    (DeviationType.BEST_MOVE, Voice.CHATTY): [
        {"narrative": "Yes! {played} — that's the move.", "question": "Can you see why it's strong?", "hint": "Look at what your piece does from that square."},
        {"narrative": "Good one! {played} is exactly right.", "question": "What was the idea behind it?", "hint": "Think about what changes on the board."},
    ],
    (DeviationType.BEST_MOVE, Voice.MEDIUM): [
        {"narrative": "{played} — that's the engine's top pick.", "question": None, "hint": None},
    ],
    (DeviationType.BEST_MOVE, Voice.FOCUSED): [
        {"narrative": "", "question": None, "hint": None},   # silent unless milestone; handled elsewhere
    ],

    # ─── ON_PLAN_NUDGE — small execution difference ───
    (DeviationType.ON_PLAN_NUDGE, Voice.CHATTY): [
        {"narrative": "Your idea is right — keep going.", "question": "What's your plan for the next move?", "hint": "Think about which piece needs work next."},
        {"narrative": "Good direction with {played}.", "question": "What are you trying to do in this position?", "hint": "Stick with a plan — don't jump between ideas."},
    ],
    # MEDIUM + FOCUSED: suppressed by policy, no templates needed

    # ─── RIGHT_IDEA_WRONG_SQUARE ───
    (DeviationType.RIGHT_IDEA_WRONG_SQUARE, Voice.CHATTY): [
        {"narrative": "You picked the right piece to move — good thinking.", "question": "Could that piece find an even better square?", "hint": "Compare what it does from {played}'s square vs {best}'s square."},
    ],
    (DeviationType.RIGHT_IDEA_WRONG_SQUARE, Voice.MEDIUM): [
        {"narrative": "Right piece, different square would be sharper.", "question": "What does {best} do that {played} doesn't?", "hint": None},
    ],

    # ─── PRINCIPLE_MISS ───
    (DeviationType.PRINCIPLE_MISS, Voice.CHATTY): [
        {"narrative": "This moment needs {principle}. {played} doesn't serve that yet.", "question": "What would get your pieces working better?", "hint": "Ask: what does each of my pieces want to do next?"},
        {"narrative": "The position is asking for {principle} right now.", "question": "Which move would help with that?", "hint": "Think about the big idea before the specific move."},
    ],
    (DeviationType.PRINCIPLE_MISS, Voice.MEDIUM): [
        {"narrative": "The position calls for {principle} — not what {played} gives.", "question": "What's the most urgent thing here?", "hint": None},
        {"narrative": "This is a {principle} moment.", "question": "Which of your pieces is most in need of help?", "hint": None},
    ],
    (DeviationType.PRINCIPLE_MISS, Voice.FOCUSED): [
        {"narrative": "", "question": "What does this position need more than {played}?", "hint": "Think: {principle}."},
    ],

    # ─── TACTICAL_MISS ───
    (DeviationType.TACTICAL_MISS, Voice.CHATTY): [
        {"narrative": "There was a tactic here — {pattern}.", "question": "Can you find a move that takes advantage?", "hint": "Look at all your pieces and what they attack."},
        {"narrative": "You missed {pattern} in this position.", "question": "What piece could have created it?", "hint": "Walk through each of your attacking pieces one by one."},
    ],
    (DeviationType.TACTICAL_MISS, Voice.MEDIUM): [
        {"narrative": "You missed {pattern}.", "question": "What would {best} have achieved?", "hint": None},
    ],
    (DeviationType.TACTICAL_MISS, Voice.FOCUSED): [
        {"narrative": "", "question": "Anything tactical here?", "hint": "{pattern}."},
    ],

    # ─── WALKED_INTO ───
    (DeviationType.WALKED_INTO, Voice.CHATTY): [
        {"narrative": "Careful — {played} allows {pattern}.", "question": "Did you check what I could do after your move?", "hint": "Before every move, ask: what does my opponent threaten now?"},
        {"narrative": "Watch out — {played} leaves {pattern}.", "question": "Can you see what's in trouble?", "hint": "Look for pieces that can now be attacked."},
    ],
    (DeviationType.WALKED_INTO, Voice.MEDIUM): [
        {"narrative": "{played} allows {pattern}.", "question": "What's my reply going to threaten?", "hint": None},
    ],
    (DeviationType.WALKED_INTO, Voice.FOCUSED): [
        {"narrative": "", "question": "What does {played} allow?", "hint": "{pattern}."},
    ],

    # ─── DIRECTIONLESS ─── (only CHATTY reaches this — others silenced)
    (DeviationType.DIRECTIONLESS, Voice.CHATTY): [
        {"narrative": "Okay move — keep thinking about what each piece is doing.", "question": "What's the plan from here?", "hint": "Pick one goal: safer king, more active pieces, or fighting for the center."},
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────

def _pick(critique: MoveCritique, voice: Voice) -> Optional[Dict]:
    """Pick a template, return a dict of {narrative, question, hint} with placeholders filled."""
    key = (critique.deviation_type, voice)
    pool = _TEMPLATES.get(key)
    if not pool:
        return None
    tpl = random.choice(pool)

    principle_label = (
        PRINCIPLE_LABEL.get(critique.teaching_focus, "").lower()
        if critique.teaching_focus else ""
    )
    pattern = critique.walked_into_pattern or critique.tactical_pattern_missed or ""

    def fill(s: Optional[str]) -> Optional[str]:
        if not s:
            return s
        return s.format(
            played=critique.played_move_san or "your move",
            best=critique.best_move_san or "a different move",
            pattern=pattern,
            principle=principle_label or "a clearer plan",
        )

    return {
        "narrative": fill(tpl.get("narrative")) or "",
        "question": fill(tpl.get("question")),
        "hint": fill(tpl.get("hint")),
    }


def render_critique(critique: MoveCritique, decision: PolicyDecision) -> Optional[Dict]:
    """Render a MoveCritique into text fields for V5Coaching.

    Returns None if policy says silent or if no template matches.
    Returns dict with narrative, question, hint, teaching_focus_label, principle, pattern.
    """
    if not decision.should_speak:
        return None

    rendered = _pick(critique, decision.voice)
    if not rendered:
        return None

    # Add structured fields the renderer / frontend can use for non-text UI
    focus = critique.teaching_focus
    rendered["teaching_focus_label"] = PRINCIPLE_LABEL.get(focus) if focus else None
    rendered["teaching_focus_key"] = focus.value if focus else None
    rendered["deviation_type"] = critique.deviation_type.value
    rendered["voice"] = decision.voice.value

    # Milestone flag (e.g. student avoided a known weakness)
    if decision.is_milestone and decision.connect_to_weakness:
        rendered["milestone"] = True
        rendered["pattern_memory"] = (
            f"Nice — you avoided {decision.connect_to_weakness.replace('_', ' ')} this time."
        )

    return rendered
