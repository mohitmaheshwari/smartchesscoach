"""
Truth-line generator — produces the 3-line headline (identity / anchor /
forward trigger) shown FIRST on the post-game screen. Coach Voice.

Strictly separate from the Decryption generator. Truth never sees
Decryption output, never reads V5 plan prose. It only looks at structural
move data (move_number, san, cp_loss, severity, is_user_move) and the
game-reason classification. This is the "do not let voices blend" rule
from project_decryption_voice.md enforced at the input boundary.

No LLM. Deterministic templates per scenario, with hash-based variant
selection so the same line doesn't appear game after game. Hard-validated
on output via validators.validate_truth_block().
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .validators import validate_truth_block, TRUTH_LINE_MAX_WORDS

logger = logging.getLogger(__name__)


# ── Scenario archetypes ───────────────────────────────────────────────
# Map game_reason_classifier categories to four behavioral archetypes
# that drive Truth voice. Each archetype gets its own pool of identity,
# anchor verb-phrase, and trigger lines.

SCENARIO_BLUNDERED = "blundered"   # decisive blunder, was equal/winning
SCENARIO_THREW = "threw"           # was winning, simplified/relaxed away
SCENARIO_SQUEEZED = "squeezed"     # gradual passivity, no single moment
SCENARIO_OUTPLAYED = "outplayed"   # opponent saw a plan; no clear failure


_REASON_TO_SCENARIO = {
    "threw_winning": SCENARIO_THREW,
    "one_move_blunder": SCENARIO_BLUNDERED,
    "tactical_miss": SCENARIO_BLUNDERED,
    "calculation_error": SCENARIO_BLUNDERED,
    "opening_disaster": SCENARIO_BLUNDERED,
    "positional": SCENARIO_SQUEEZED,
    "endgame_collapse": SCENARIO_SQUEEZED,
    "time_collapse": SCENARIO_BLUNDERED,
}


def _classify_scenario(game_reason: str, blunder_count: int) -> str:
    """Map game_reason_classifier output → Truth scenario."""
    s = _REASON_TO_SCENARIO.get(game_reason or "")
    if s:
        return s
    # Fallback: a loss with no clear blunder pattern is "outplayed".
    # A loss with blunders but no clean classification falls back to
    # "squeezed" which has the safest copy.
    if blunder_count == 0:
        return SCENARIO_OUTPLAYED
    return SCENARIO_SQUEEZED


# ── Identity lines (line 1 of Truth) ──────────────────────────────────
# All <= 12 words. Identity-level: about a habit, not a single move.

IDENTITY_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "You didn't lose this. You stopped looking at their pieces.",
        "You didn't lose this. You attacked without checking their reply.",
        "You didn't lose this. You stopped seeing what they could do.",
    ],
    SCENARIO_THREW: [
        "You didn't get outplayed. You relaxed.",
        "You didn't get outplayed. You stopped working when you started winning.",
        "You didn't lose to them. You traded the game away.",
    ],
    SCENARIO_SQUEEZED: [
        "You didn't lose to them. You let them run the game.",
        "You didn't get outplayed. You went passive.",
        "You didn't lose this. You stopped having a plan.",
    ],
    SCENARIO_OUTPLAYED: [
        "They outplayed you. There's no move to undo.",
        "They were sharper. You played within your range.",
        "They saw a plan you didn't.",
    ],
}


# ── Anchor verb phrases (line 2 of Truth) ─────────────────────────────
# Slotted into "Move N — {phrase}." or "Move N — you {phrase}."
# Kept short so the full anchor stays under the 12-word cap even with
# higher move numbers.

ANCHOR_PHRASES_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "you played {san} without checking their reply",
        "you went after {san} and missed their threat",
        "{san} walked into their answer",
    ],
    SCENARIO_THREW: [
        "you traded thinking the game was over",
        "you stopped pressing when {san} came",
        "{san} simplified into a lost position",
    ],
    SCENARIO_SQUEEZED: [
        "you had no piece free to challenge them",
        "your pieces were already tied down",
        "{san} was reactive — like every move before it",
    ],
    SCENARIO_OUTPLAYED: [
        "their plan was already moving",
        "their pieces had a direction yours didn't",
        "{san} answered their threat — not yours",
    ],
}


# ── Forward triggers (line 3 of Truth) ────────────────────────────────
# Mutterable mid-game. Short — most under 7 words.

TRIGGER_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "What are they threatening?",
        "Before every move: what changed for them?",
        "Every move: check their reply first.",
    ],
    SCENARIO_THREW: [
        "Winning is when the work starts.",
        "When you're winning, slow down.",
        "Don't relax when you're winning.",
    ],
    SCENARIO_SQUEEZED: [
        "Find work for every piece.",
        "Every piece needs a job that isn't defending.",
        "Stop reacting. Start choosing.",
    ],
    SCENARIO_OUTPLAYED: [
        "Watch their plan, not just yours.",
        "Notice what their pieces are pointed at.",
        "Their plan is half the game.",
    ],
}


def _pick_variant(pool: List[str], game_id: str) -> str:
    """Deterministic pick — same game always yields the same variant.
    Hashing on game_id spreads variants across users so the same scenario
    doesn't always render the same phrasing on every screen.
    """
    if not pool:
        return ""
    idx = hash(game_id or "") % len(pool)
    return pool[idx]


def _format_anchor(critical_move: Dict, scenario: str, game_id: str) -> str:
    """Build line 2 — 'Move N — {scenario phrase}.'

    critical_move: dict with at minimum move_number + move_san.
    """
    move_num = critical_move.get("move_number") or critical_move.get("ply") or "?"
    move_san = critical_move.get("move_san") or "?"

    pool = ANCHOR_PHRASES_BY_SCENARIO.get(scenario) or ANCHOR_PHRASES_BY_SCENARIO[SCENARIO_BLUNDERED]
    phrase_template = _pick_variant(pool, game_id)
    phrase = phrase_template.format(san=move_san)

    line = f"Move {move_num} — {phrase}."
    return line


def _shrink_to_budget(line: str, max_words: int = TRUTH_LINE_MAX_WORDS) -> str:
    """Pull words off the END until the line fits the budget. Keeps the
    period if there is one. Used as the last-resort safety so a stretched
    template never ships an over-budget line.
    """
    if len(line.split()) <= max_words:
        return line
    period = line.endswith(".")
    words = line.split()
    while len(words) > max_words:
        words.pop()
    out = " ".join(words)
    if period and not out.endswith("."):
        out += "."
    return out


# ── Public API ────────────────────────────────────────────────────────

def pick_critical_move(decryption_v5_data: List[Dict]) -> Optional[Dict]:
    """Find the user's most decisive losing move from V5 structural data.

    Note: we read ONLY structural fields (move_number, move_san, cp_loss,
    severity, is_user_move). We do NOT read narrative, plan, or any V5
    prose — Truth must not see Decryption inputs.
    """
    if not decryption_v5_data:
        return None
    user_mistakes = [
        m for m in decryption_v5_data
        if m.get("is_user_move") and m.get("is_mistake")
        and (m.get("cp_loss") or 0) >= 50
    ]
    if not user_mistakes:
        return None
    user_mistakes.sort(key=lambda m: -(m.get("cp_loss") or 0))
    chosen = user_mistakes[0]
    # Return only structural fields so Decryption-flavored prose can't
    # leak into Truth via shared state.
    return {
        "move_number": chosen.get("move_number"),
        "move_san": chosen.get("move_san"),
        "cp_loss": chosen.get("cp_loss"),
        "severity": chosen.get("severity"),
    }


def generate_truth_line(
    *,
    decryption_v5_data: List[Dict],
    game_reason: str,
    game_id: str,
    user_won: bool = False,
) -> Optional[Dict[str, str]]:
    """Build the 3-line Truth headline for a finished game.

    Args:
        decryption_v5_data: list of move dicts (V5 schema). Read for
            structural fields only.
        game_reason: output of game_reason_classifier (e.g.
            "threw_winning", "one_move_blunder", "positional"). Drives
            scenario selection.
        game_id: stable hash key for variant selection.
        user_won: skip Truth generation entirely if the user won.

    Returns:
        {"identity": str, "anchor": str, "trigger": str, "scenario": str}
        or None if Truth shouldn't render (user won, no decisive move,
        or validation could not be satisfied even with fallbacks).
    """
    if user_won:
        return None

    critical = pick_critical_move(decryption_v5_data)
    if not critical:
        return None

    blunder_count = sum(
        1 for m in (decryption_v5_data or [])
        if m.get("is_user_move") and m.get("severity") == "blunder"
    )

    scenario = _classify_scenario(game_reason or "", blunder_count)

    identity = _pick_variant(IDENTITY_BY_SCENARIO[scenario], game_id)
    anchor = _format_anchor(critical, scenario, game_id)
    trigger = _pick_variant(TRIGGER_BY_SCENARIO[scenario], game_id)

    # Apply final budget trim (rare safety net for very long move SANs).
    identity = _shrink_to_budget(identity)
    anchor = _shrink_to_budget(anchor)
    trigger = _shrink_to_budget(trigger)

    ok, reason = validate_truth_block(identity, anchor, trigger)
    if not ok:
        logger.warning(
            f"[truth_line] validation failed for game={game_id} scenario={scenario}: {reason}"
            f" — falling back to safe variants"
        )
        identity = IDENTITY_BY_SCENARIO[scenario][0]
        # Ultra-short anchor fallback that always fits the budget.
        move_num = critical.get("move_number") or "?"
        anchor = f"Move {move_num} — your move was decisive."
        trigger = TRIGGER_BY_SCENARIO[scenario][0]
        ok2, reason2 = validate_truth_block(identity, anchor, trigger)
        if not ok2:
            logger.error(f"[truth_line] safe fallback also invalid: {reason2}")
            return None

    return {
        "identity": identity,
        "anchor": anchor,
        "trigger": trigger,
        "scenario": scenario,
    }
