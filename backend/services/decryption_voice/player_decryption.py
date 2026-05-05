"""
Player Decryption — Story + Pattern + Carry-forward.

Three short coaching beats per game that explain WHO the player was in
this game, not what happened on the board. Plan Decryption (decryption.py)
handles the position-grounded prose and stays separate.

All three layers are deterministic templates picked by scenario.
No LLM — Pattern especially must sound like the player's inner voice,
which an LLM consistently fails at (it drifts into coach-narration).

Voice rules from project_decryption_voice.md plus three locked rules
from the 2026-05-04 line-by-line review:

  1. Pattern is the player's inner voice ("you stop watching them"),
     not the coach's external voice ("you stop watching what your
     opponent can do"). Inner voice lands; coach voice misses.

  2. Game Story earns its place by being tight. Two short sentences max.
     No drama, no metaphor.

  3. Carry-forward is mutterable mid-game, not quotable. "Don't relax
     when you're winning" survives a real game; "Winning is when the
     work changes" reads tweet-flavored and dies on the board.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .truth_line import (
    SCENARIO_BLUNDERED,
    SCENARIO_THREW,
    SCENARIO_EQUALIZED,
    SCENARIO_SQUEEZED,
    SCENARIO_OUTPLAYED,
    PIVOT_TIER_EQUALIZED,
    classify_scenario,
    pick_critical_move,
    pick_variant,
)

logger = logging.getLogger(__name__)


# ── Game Story (line 1 — tight, human, no drama) ─────────────────────

STORY_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "You were winning. Move {move_n} flipped the game — and it never came back.",
        "You had it. Move {move_n} gave it away in one stroke.",
        "Move {move_n} broke it. One move did the damage.",
    ],
    SCENARIO_THREW: [
        "You played to win. You got winning. Then you stopped playing.",
        "You built a winning position. Then you handed it over.",
        "It was yours. You stopped working at the wrong time.",
    ],
    SCENARIO_EQUALIZED: [
        "You climbed back in. Move {move_n} sent you back out.",
        "You'd fought your way back. You didn't keep fighting.",
        "It was even again. You let it slip.",
    ],
    SCENARIO_SQUEEZED: [
        "You started solid. By the middlegame you'd lost the initiative without noticing. By move {move_n}, you were just answering their questions.",
        "There was no single mistake. You slowly stopped having a plan.",
        "You held early. Then you stopped pushing — and they kept pushing.",
    ],
    SCENARIO_OUTPLAYED: [
        "They had a plan from early. You didn't see it until too late.",
        "You played calmly. They played sharper.",
        "There's no move to undo. They were better today.",
    ],
}


# ── Pattern (line 2 — the gold) ──────────────────────────────────────
# Identity-level. Player's inner voice about himself. NOT coach prose.

PATTERN_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "You see the attack, but stop watching them.",
        "You attack before you check what they have back.",
        "You commit to plans without checking their reply.",
    ],
    SCENARIO_THREW: [
        "When you're ahead, you relax. You stop trying to win.",
        "Winning makes you careless. The work isn't done; you act like it is.",
        "You celebrate too early. Your opponent doesn't.",
    ],
    SCENARIO_EQUALIZED: [
        "When the chance comes, you stop working before you finish the job.",
        "You ease off after equalizing — that's the second mistake.",
        "You celebrate the comeback before you complete it.",
    ],
    SCENARIO_SQUEEZED: [
        "You keep reacting instead of pushing back. When they take space, you defend instead of challenging it.",
        "You let them set the agenda. Once you're defending, you stay defending.",
        "You don't notice when their plan starts. By the time you do, it's already moving.",
    ],
    SCENARIO_OUTPLAYED: [
        "You didn't see what they were building until it was too late.",
        "You watched your side of the board, not theirs.",
        "Their plan was already moving while yours was still waiting.",
    ],
}


# ── Carry-forward (line 3 — mutterable mid-game, not quotable) ───────

CARRY_FORWARD_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "When you smell a win, slow down — that's when you stop checking.",
        "Before every move, ask: what are they threatening?",
        "Check their reply before you commit.",
    ],
    SCENARIO_THREW: [
        "Don't relax when you're winning.",
        "Stay sharp until they resign.",
        "When you're ahead, slow down.",
    ],
    SCENARIO_EQUALIZED: [
        "Equalizing isn't winning. Keep working.",
        "After they slip, your work begins.",
        "The comeback ends when the position ends.",
    ],
    SCENARIO_SQUEEZED: [
        "Don't just react — push back.",
        "When they take space, challenge it. Don't wait.",
        "Have a plan, even when they have one.",
    ],
    SCENARIO_OUTPLAYED: [
        "Watch what they're doing, not just what you want.",
        "Their plan is half the game.",
        "Notice what their pieces are pointed at.",
    ],
}


def _format_story(template: str, critical_move: Optional[Dict]) -> str:
    """Slot the critical move number if the template uses {move_n}.
    If the move number is unknown, fall back to a non-anchored phrasing
    by stripping the move-anchor clause."""
    move_n = (critical_move or {}).get("move_number")
    if "{move_n}" not in template:
        return template
    if move_n is None:
        # Strip move-anchored clauses — better to ship a generic line
        # than render the literal "{move_n}".
        return (
            template
            .replace("Move {move_n} flipped the game — and it never came back.",
                     "The game flipped, and it never came back.")
            .replace("Move {move_n} gave it away in one stroke.",
                     "It got given away in one stroke.")
            .replace("Move {move_n} broke it. One move did the damage.",
                     "One move broke it.")
            .replace("Move {move_n} sent you back out.",
                     "You got sent back out.")
            .replace(" By move {move_n}, you were just answering their questions.",
                     " You were just answering their questions.")
            .replace("{move_n}", "—")
        )
    return template.replace("{move_n}", str(move_n))


def build_player_decryption(
    *,
    decryption_v5_data: List[Dict],
    game_reason: str,
    game_id: str,
    user_color: str = "white",
) -> Optional[Dict]:
    """Build the Player Decryption block: story + pattern + carry_forward.

    Args:
        decryption_v5_data: list of move dicts (V5 schema). Read for
            structural fields only — same discipline as truth_line.
        game_reason: output of game_reason_classifier (e.g.
            "threw_winning", "one_move_blunder"). Drives scenario.
        game_id: stable hash key for variant selection.

    Returns:
        {"story", "pattern", "carry_forward", "scenario"} or None when
        no decisive moment exists (e.g., user won — caller skips this
        surface entirely).
    """
    critical = pick_critical_move(decryption_v5_data, user_color=user_color)
    if not critical:
        return None

    blunder_count = sum(
        1 for m in (decryption_v5_data or [])
        if m.get("is_user_move") and m.get("severity") == "blunder"
    )
    # Pivot tier picks scenario: 'won' → THREW (had a winning position),
    # 'equalized' → EQUALIZED (came back to even, gave it back). Falls
    # through to game_reason classification when no pivot fires.
    pivot_tier = critical.get("pivot_tier")
    if pivot_tier == PIVOT_TIER_EQUALIZED:
        scenario = SCENARIO_EQUALIZED
    elif critical.get("is_pivot"):
        scenario = SCENARIO_THREW
    else:
        scenario = classify_scenario(game_reason or "", blunder_count)

    # Salt the game_id for each layer so the three lines don't all
    # come from the same pool index — feels less canned across games.
    story_template = pick_variant(STORY_BY_SCENARIO[scenario], game_id + "::story")
    story = _format_story(story_template, critical)

    pattern = pick_variant(PATTERN_BY_SCENARIO[scenario], game_id + "::pattern")
    carry_forward = pick_variant(CARRY_FORWARD_BY_SCENARIO[scenario], game_id + "::carry")

    return {
        "story": story,
        "pattern": pattern,
        "carry_forward": carry_forward,
        "scenario": scenario,
    }
