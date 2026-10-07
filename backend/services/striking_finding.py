"""The one thing about this player worth interrupting them with.

Mohit, 2026-10-07: *"it's not the representation only, it's the data too that is
not giving me enough value on home page"*. He was right, and the diagnosis is
embarrassing: over two days of measuring his games the home page ended up saying

    You have played on most days this month.
    About the same as your usual week.
    Games you lost on the clock rather than on the board.

while these were measured and left in a terminal:

    68 of his 156 analysed timeout losses were games he was WINNING
    his win rate within a sitting runs 41% / 33% / 22% / 14%
    he gained about 240 rating points while tactical conversion did not move
    pins and skewers are 59% of every chance he gets and he takes 43%

A weekly summary is something a player can work out for themselves. A finding is
something they cannot. This module serves findings.

A FINDING HAS TO EARN ITS PLACE. Each one here passed two tests before it was
written: enough evidence for this player, and enough players for it to be a
reading rather than a coincidence about one account. The counts are recorded
against each so a later reader can see what it rested on.

ON NUMBERS. The standing rule is no numbers in user-facing text, and this module
breaks it deliberately for counts of games. "You have lost games you were
winning on the clock" is a shrug; "sixty-eight games you were winning, lost on
the clock" is the entire point. The number IS the finding. Rates, percentages
and scores stay banned -- those are the ones that mislead.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

# A finding needs this many events before it is said out loud. Measured over 70
# players: at five or more analysed timeout losses, 26 players qualify and 18 of
# them lose a third or more of those from winning positions.
MIN_EVENTS = 5
MIN_SHARE = 0.30

_WORDS = {
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
    20: "twenty",
}


def spell(count: int) -> str:
    """Small counts as words, larger ones as digits.

    Spelling out the small ones keeps the sentence reading like speech. Past
    twenty it stops helping and starts sounding like a children's book, and the
    digit carries more weight anyway -- "96 games" should look like 96 games.
    """
    return _WORDS.get(int(count), str(int(count)))


def won_games_lost_on_time(winning: int, analysed_timeouts: int
                           ) -> Optional[Dict[str, Any]]:
    """Games they were winning and lost on the clock.

    The strongest finding available, and the one with the sharpest edge: it is
    not a weakness in their chess at all, it is their chess being thrown away
    after the hard part was done.
    """
    if winning < MIN_EVENTS or analysed_timeouts <= 0:
        return None
    if winning / analysed_timeouts < MIN_SHARE:
        return None
    return {
        "kind": "won_games_lost_on_time",
        "headline": "You have lost %s games you were already winning, on the "
                    "clock." % spell(winning),
        "line": "Not to a better move. The position was won and the time ran "
                "out.",
        "next": "The work is not more tactics. It is noticing, while you are "
                "ahead, that the clock has become the danger.",
        "evidence": {"winning": winning, "analysed_timeouts": analysed_timeouts},
    }


def results_fade_in_a_sitting(fade_points: Optional[float]
                              ) -> Optional[Dict[str, Any]]:
    """Results fall away across a session while the tactical eye holds.

    Rare -- two players of seventy -- and worth keeping because when it fires it
    is unarguable and nobody else can tell them. The population curve is flat at
    48/49/48, so this is a fact about the person, not about chess.
    """
    if not fade_points or fade_points < 8.0:
        return None
    return {
        "kind": "results_fade",
        "headline": "You are a different player by your third game of a sitting.",
        "line": "Your results fall away as a session goes on. Your eye for "
                "tactics does not, so it is not that you stop seeing things.",
        "next": "Most players hold steady across a session. You do not. Stop "
                "while it is still going well.",
        "evidence": {"fade_points": round(fade_points, 1)},
    }


def one_family_dominates(shapes: Optional[List[Mapping[str, Any]]]
                         ) -> Optional[Dict[str, Any]]:
    """Most of what the board offers is one family of tactic, and they miss it.

    Only said when the family is both the LARGEST source of chances and among
    the worst taken. A weak shape they rarely meet is not worth a headline.
    """
    if not shapes:
        return None
    usable = [s for s in shapes if s.get("judgeable")]
    if len(usable) < 3:
        return None
    alignment = [s for s in usable if s.get("shape") in ("pin", "skewer")]
    if len(alignment) < 2:
        return None
    total = sum(s["chances"] for s in usable)
    share = sum(s["chances"] for s in alignment) / max(total, 1)
    taken = sum(s["took"] for s in alignment) / max(
        sum(s["chances"] for s in alignment), 1)
    best = max(usable, key=lambda s: s["share"])
    if share < 0.4 or taken >= best["share"] - 0.15:
        return None
    return {
        "kind": "alignment_dominates",
        "headline": "Most of what the board hands you is one idea, and it is "
                    "the one you miss.",
        "line": "Pins and skewers are the largest share of your chances by "
                "far, and the share you take is the lowest of any shape.",
        "next": "Two pieces on a line is the pattern. Find the line before you "
                "look for the move.",
        "evidence": {"alignment_share": round(share, 3),
                     "alignment_taken": round(taken, 3)},
    }


# Strongest first. The page shows ONE, because a page with three findings on it
# is a report again.
def choose_finding(candidates: List[Optional[Mapping[str, Any]]]
                   ) -> Optional[Dict[str, Any]]:
    for candidate in candidates:
        if candidate:
            return dict(candidate)
    return None
