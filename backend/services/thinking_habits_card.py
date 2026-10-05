"""Which thinking step is breaking down, in words, for the ones we can measure.

Mohit, 2026-10-05, on whether the thinking score and the area grades are the
same thing. Measured on 59 players who carry both readings, and the answer was
worse than redundancy -- where they overlapped they disagreed:

    piece_safety  <-> threat_awareness   AGREED      56 / 60 / 68 / 72 across grades
    king_safety   <-> king_safety        NO RELATION 88.8 / 90.5 / 85.8 / 89.4
    missed_tactic <-> tactical_vision    CONTRADICTED "Needs work" averaged 92.6

A player could read "Keeping your king safe - Needs work" and a king-safety
score near ninety in the next card down.

WHY THE CONTRADICTING HABITS ARE GONE. They are the saturated ones. More than
half the population scores exactly 100 on king_safety (52%), patience (56%) and
tactical_vision (55%), so those scores cannot separate anybody and their
apparent disagreement with the areas was noise wearing a number. Dropping every
habit whose MEDIAN sits at the ceiling removes both contradictions at once --
that is one rule, not three special cases.

What survives is what discriminates:

    threat_awareness    ceiling 0%    q1 55.7   median 63.8
    move_verification   ceiling 20%   q1 82.9   median 93.1

threat_awareness overlaps the piece_safety area and AGREES with it, so it is
kept as a different question about the same evidence -- the area says where, the
habit says which step. move_verification maps from calculation_depth, which is
not an area at all, so it is the one genuinely new thing here.

NO SCORE IS RENDERED. The old card showed 0-100 and progress bars. Across the
population that number runs p10 77 to p90 92, which is every player getting a B,
and it broke the rule every other card on the page follows.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

# Measured 2026-10-05 over the 59 players with enough games. The cut is the
# LOWER QUARTILE of each habit, the same choice behaviour_profile makes and for
# the same reason: a strong claim about a few people beats a weak one about half
# of them. Re-measure these if the scorer changes, because they are quartiles of
# the population the scorer produced.
CUTS: Mapping[str, float] = {
    "threat_awareness": 55.7,
    "move_verification": 82.9,
}

# Named so the next reader does not rediscover why three habits vanished. A
# habit belongs here when more than half the population scores at the ceiling:
# it is not that these players have no king-safety problem, it is that this
# measure cannot tell which of them does.
SATURATED_AND_SILENT: Mapping[str, str] = {
    "king_safety": "median at the ceiling; 52% of players score exactly 100",
    "patience": "median at the ceiling; 56% of players score exactly 100",
    "tactical_vision": "median at the ceiling; 55% of players score exactly 100",
}

# What the player reads. Each names the habit and the fix, and neither carries a
# number or a piece of jargon.
SENTENCES: Mapping[str, Dict[str, str]] = {
    "threat_awareness": {
        "headline": "You are moving before you look at their threats.",
        "body": "Most of your mistakes come right after their move changed "
                "something, and the reply goes in before that change is read.",
        "next": "Before each move, ask one question: what did their last move "
                "attack?",
    },
    "move_verification": {
        "headline": "You commit to a move before checking it.",
        "body": "The move that looks strongest often stops looking strong once "
                "they answer, and that is where these errors sit.",
        "next": "Pick your move, then play their best reply in your head "
                "before you touch it.",
    },
}

SCHEMA_VERSION = "thinking_habits_card.v1"


def eligible_habits() -> List[str]:
    """The habits allowed to speak, worst-measured first."""
    return sorted(CUTS, key=lambda habit: CUTS[habit])


def build_card(habit_progress: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The card, from `calculate_thinking_progress()["habit_progress"]`.

    Returns `measured: False` rather than a cheerful line when nothing is at an
    end. Saying "your thinking is fine" off a saturated measure would be the
    same mistake the balanced behaviour line made.
    """
    lines: List[Dict[str, str]] = []
    for habit in eligible_habits():
        entry = (habit_progress or {}).get(habit)
        if not isinstance(entry, Mapping):
            continue
        score = entry.get("current_score")
        if not isinstance(score, (int, float)):
            continue
        if float(score) > CUTS[habit]:
            continue
        words = SENTENCES.get(habit)
        if not words:
            continue
        lines.append({"habit": habit, **words})

    return {
        "schema_version": SCHEMA_VERSION,
        "measured": bool(lines),
        "lines": lines,
        # For the operator reading an API response, never for the player.
        "_silent_habits": dict(SATURATED_AND_SILENT),
    }
