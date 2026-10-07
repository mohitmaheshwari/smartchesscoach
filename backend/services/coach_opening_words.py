"""What the coach says first: the good thing, then the costly one.

docs/home_as_a_coach_scope.md

Mohit, 2026-10-07: a human coach reads your games and tells you what is good AND
what is bad before training anything. The product had the bad half built in
depth and the good half as a single word in the corner of a card.

THE STRENGTH LEADS, AND THAT IS NOT DECORATION. Every element on the old page
was a deficit. A coach who only ever names faults loses the client in three
sessions, and this is the one product decision in this file that is about the
relationship rather than the data.

THE STORED STRENGTH NARRATIVE CANNOT BE RENDERED. All 39 read like this:

    "Low blunder rate: you land at 4.6%, vs the cohort average of 6.7% at your
     rating vs the beginner band. That's +0.9σ -- a real signature."

Percentages, a cohort comparison that the no-comparison rule forbids, and sigma
notation aimed at a 1200 player. So the words here are authored per strength
`kind`, from the label alone, and a label nobody has written for stays silent
rather than being dressed up.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Authored per stored strength label. The label text is what the picker chose;
# these turn it into something a coach would actually say out loud.
STRENGTH_WORDS: Mapping[str, str] = {
    # The most common strength of the thirty-nine (8 players) and the one that
    # had no words at all, which is how it reached nobody. It is also the scope
    # item marked "never shown": 487 moves flagged brilliant per 600 games, and
    # not one of them has ever been put in front of the player who played it.
    # Saying so is the small version. Showing the move is the real one, and it
    # is Movement 1's next piece of work, not a line of text.
    "Brilliant moves":
        "You have played moves I would not expect at your level. Not safe "
        "moves that happened to work -- moves you had to see.",
    "Low blunder rate":
        "You are hard to beat by accident. You blunder less than almost "
        "anything else you do.",
    "Low mistake rate":
        "Your moves are steady. Mistakes are not what is costing you.",
    "Threat awareness":
        "You notice what your opponent is trying to do. That is not common at "
        "any level.",
    "Best-move accuracy in critical moments":
        "When the position actually matters, you tend to find the move. The "
        "sharp moments are not your problem.",
    "Overall move accuracy":
        "Your play holds together. Move by move you are solid.",
    "Winning free pawns":
        "You take what is left loose. Free material does not get past you.",
    "Punishing opponent blunders":
        "When they give you something, you take it. That is a real habit and "
        "most players at your level do not have it.",
    "Rook forks":
        "You see rook forks. That shape is already yours.",
    "Knight forks":
        "You see knight forks. That shape is already yours.",
    "Hidden attacks":
        "You spot what opens up behind a move. That is a hard thing to see.",
    "Pin tactics":
        "You find pins. Two of their pieces on one line and you see it.",
    "Double attacks":
        "You go for the move that hits two things at once, instead of taking "
        "the first thing you see.",
    "Spotting loose material":
        "Nothing of theirs sits loose for long. You notice what is unguarded.",
    "Long-range piece play":
        "You give your bishops and rooks lines to work on. That is a slower "
        "kind of good and most players never get there.",
    "Overloaded-defender tactics":
        "You notice when one of their pieces is guarding two things, and you "
        "make it choose.",
    "Exploiting weak squares":
        "You find the squares they cannot defend any more and put a piece "
        "there.",
    # The picker's own labels for these two carry words a 1200 player does not
    # have ("Zwischenzug", "Fianchetto"), so the sentence says the idea in
    # plain words instead of repeating the label back.
    "Zwischenzug":
        "You do not always play the move they are waiting for. You slip in "
        "something of your own first.",
    "Fianchetto-hole play":
        "When their bishop leaves the corner, you know which square to aim "
        "for.",
}


def strength_words(strength: Optional[Mapping[str, Any]]) -> Optional[str]:
    """What to say about the good thing, or None.

    None when nobody has written for this label. The stored narrative is never
    a fallback -- it is the thing being replaced.
    """
    if not strength:
        return None
    return STRENGTH_WORDS.get(str(strength.get("label") or "").strip())


def opening_words(strength: Optional[Mapping[str, Any]],
                  finding: Optional[Mapping[str, Any]],
                  focus_why: Optional[str]) -> Dict[str, Any]:
    """The coach's first paragraph: the good thing, then the costly one.

    Returns the pieces rather than one blob so the surface can space them. The
    order is fixed and is the point: good first.
    """
    lines = []
    good = strength_words(strength)
    if good:
        lines.append({"kind": "strength", "text": good})

    # The costly thing. A finding outranks the focus explanation because it is
    # the thing the player could not have worked out alone.
    if finding and finding.get("headline"):
        costly = finding["headline"]
        if finding.get("line"):
            costly = "%s %s" % (costly, finding["line"])
        lines.append({"kind": "cost", "text": costly})
    elif focus_why:
        lines.append({"kind": "cost", "text": focus_why})

    return {
        "measured": bool(lines),
        "lead": "I have been through your games." if lines else None,
        "lines": lines,
    }
