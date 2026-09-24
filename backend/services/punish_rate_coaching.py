"""What the player does with the chances their opponent hands them.

Every user in the corpus is handed material by their opponent regularly, and
every one of them lets some of it go. It is measured on every move, stored on
every observation, and until now read by nobody: `punished_opponent_blunder`
and `missed_opponent_blunder` have been written to move_observations since the
deriver was built, and nothing turns them into something a player sees.

DESIGN NOTES, because two measurements shaped the words below.

1. NO NUMBERS, EVER, in anything the player reads. Mohit's instruction. A
   percentage turns coaching into a report card, and the audience is 600-1500.
   The rate decides which sentence to use; it never appears in the sentence.

2. THE SPREAD IS SMALL, so the rate is not the message. Measured over 53 users
   with at least 10 chances each, share of chances taken:

       lowest 0.34 | quartile 0.52 | median 0.57 | quartile 0.62 | highest 0.77

       30-39%   5 users
       40-49%   3
       50-59%  24
       60-69%  19
       70-79%   2

   Forty-three of fifty-three sit between 0.50 and 0.69. A three-tier score
   would tell almost everyone the same thing, which is the repetition problem
   this feature is supposed to relieve. So the HABIT is the message -- the same
   closing line for everyone -- and the band only warms or cools the opening
   clause. Band edges are the measured quartiles, not invented round numbers.

3. NOT A FAILURE SCOREBOARD. No tallies, no "you missed N chances". The framing
   is what is on offer, because there is always another one next game.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# The measured quartiles above. Below the lower one is the bottom quarter of
# players; above the upper one is the top quarter.
LOWER_QUARTILE = 0.52
UPPER_QUARTILE = 0.62

# Fewer chances than this and the rate is noise, not a pattern.
MIN_CHANCES = 10

_HABIT = "After they move, ask one thing: what did that leave behind?"

_OPENERS = {
    "low": "Your opponents keep handing you material, and a lot of it goes by.",
    "mid": "Your opponents keep handing you material. You take some of it, and some slips past.",
    "high": "Your opponents keep handing you material, and you spot most of it.",
}


def band_for(rate: float) -> str:
    """Which quarter of the player population this rate sits in."""
    if rate < LOWER_QUARTILE:
        return "low"
    if rate > UPPER_QUARTILE:
        return "high"
    return "mid"


def punish_rate_line(
    chances_taken: int,
    chances_total: int,
) -> Optional[Dict[str, Any]]:
    """The coaching line, or None when there is not enough to say it.

    Returns the rate alongside the text so callers can rank or store it. The
    rate must not be rendered.
    """
    if chances_total < MIN_CHANCES or chances_taken < 0:
        return None
    if chances_taken > chances_total:
        return None
    rate = chances_taken / float(chances_total)
    band = band_for(rate)
    return {
        "band": band,
        "rate": rate,                      # internal only; never shown
        "chances_total": chances_total,    # internal only; never shown
        "headline": _OPENERS[band],
        "habit": _HABIT,
        "text": "%s %s" % (_OPENERS[band], _HABIT),
    }


def punish_counts_from_observations(observations) -> Dict[str, int]:
    """Count chances and chances taken from stored move observations.

    Recomputed from `execution_quality` and `cp_loss` rather than read from the
    stored booleans, because rows written before 2026-09-25 used a stricter bar
    that counted a good-but-not-best move as failing to punish.
    """
    taken = total = 0
    for obs in observations or []:
        if not (obs.get("missed_opponent_blunder")
                or obs.get("punished_opponent_blunder")):
            continue
        total += 1
        quality = obs.get("execution_quality")
        try:
            cp_loss = abs(int(obs.get("cp_loss") or 0))
        except (TypeError, ValueError):
            cp_loss = 0
        if quality in ("best", "excellent", "good", "brilliant") and cp_loss < 50:
            taken += 1
    return {"chances_taken": taken, "chances_total": total}
