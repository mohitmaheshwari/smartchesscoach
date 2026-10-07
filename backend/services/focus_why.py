"""Why this topic, and not another one.

Mohit, 2026-10-07: the card says "Time management -- ask one question every few
moves" and gives no reason to care. *"Now the player understands why ChessGuru
selected this lesson. That's extremely important for an AI coach."* He is right,
and it is the one thing in that design which is missing, deliverable today and
changes how the coaching feels.

HIS VERSION HAD A NUMBER IN IT -- "I found this pattern in 4 of your last 7
games" -- and the standing rule is no numbers in anything a player reads. The
stored `coaching_narrative` is worse: "235 events across 800 games. 68% of them
(159 events) are games lost on time". None of that can be rendered.

So the why is built from the SHAPE of the evidence rather than its size. The
`subtype_histogram` says which kind of mistake dominates, and naming that kind is
both more specific than a count and sayable without one. "Most of it is one
thing: the piece you moved could be taken on the square it landed on" tells a
player more than "I found this in four games".

THE SET IS SMALL AND CLOSED. Measured across all 53 active focuses on prod,
exactly six (topic, subtype) pairs occur:

    piece_safety    / destination_safety_exact   30 players
    king_safety     / ignored_king_attack        13
    time_management / chronic_timeout             4
    time_management / time_pressure_blunder       3
    missed_tactic   / missed_skewer               2
    time_management / slow_paralysis              1

Every one is authored. A pair with no wording returns nothing rather than a
generic sentence, because a vague why is worse than no why -- it reads like the
product is guessing.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# A subtype has to be this much of the evidence before the line may say "most of
# it is one thing". Below it the focus is a mix, and claiming a single cause
# would be a tidier story than the games support.
DOMINANT_SHARE = 0.5

LEAD = "Most of it is one thing."

# subtype -> what that mistake actually looks like on the board, in the plainest
# words the idea allows.
WHY_BY_SUBTYPE: Mapping[str, str] = {
    "destination_safety_exact":
        "The piece you moved could be taken on the square it landed on.",
    "simple_hang":
        "A piece was left where it could simply be taken.",
    "ignored_king_attack":
        "Something was coming at your king, and the move you played did not "
        "deal with it.",
    "chronic_timeout":
        "Games you lost on the clock rather than on the board.",
    "time_pressure_blunder":
        "The mistakes arrive once your clock is already low.",
    "slow_paralysis":
        "Long thinks early that leave you nothing for the end.",
    "missed_skewer":
        "Two of their pieces on one line, and the move that attacks them going "
        "unplayed.",
    "missed_pin":
        "Two of their pieces on one line, and the move that pins them going "
        "unplayed.",
    "missed_fork":
        "A move that would have hit two things at once, not played.",
    "tactical_seq_loss":
        "The piece was safe for a move, and not once they answered.",
}


def _dominant(histogram: Optional[Mapping[str, Any]]):
    """(subtype, share) for the biggest entry, or None."""
    if not isinstance(histogram, Mapping) or not histogram:
        return None
    counts = {}
    for name, entry in histogram.items():
        if isinstance(entry, Mapping):
            value = entry.get("count")
        else:
            value = entry
        if isinstance(value, (int, float)) and value > 0:
            counts[name] = float(value)
    if not counts:
        return None
    total = sum(counts.values())
    name = max(counts, key=counts.get)
    return name, counts[name] / total


def build_why(focus: Optional[Mapping[str, Any]]) -> Optional[Dict[str, str]]:
    """One sentence saying what this focus actually is, or None.

    None is a real answer. A focus whose evidence is genuinely mixed, or whose
    dominant subtype nobody has written wording for, gets no why rather than a
    sentence that could describe anything.
    """
    if not focus:
        return None
    dominant = _dominant(focus.get("subtype_histogram"))
    if dominant is None:
        return None
    subtype, share = dominant
    if share < DOMINANT_SHARE:
        return None
    line = WHY_BY_SUBTYPE.get(subtype)
    if not line:
        return None
    return {"subtype": subtype, "lead": LEAD, "line": line}
