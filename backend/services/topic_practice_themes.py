"""Where a topic gets practice when our own games cannot prove one.

docs/home_session_scope.md

THE PROBLEM, MEASURED 2026-10-06. `king_safety` has 151 community puzzles and
341 coach positions and NOT ONE passes verification. It is not a missing
backfill: the admission builder was run against them directly and returned
`generic` for 55 of 60 and `broad/missed_tactic` for the rest, even when
`king_safety` was passed in explicitly.

The reason is that there is no king-safety prover. The builder can prove exact
endgames, forced mate, back-rank mate, free pieces, forks, aligned tactics,
discovered attacks, removal of the defender, piece safety, destination safety
and trapped pieces. Nothing in that list can certify "this position is about
your king being unsafe", so the pipeline correctly refuses to.

And the mate provers cannot rescue them either: of 151 king_safety puzzles,
**none involve mate at all**. They carry a classifier's opinion, not evidence.

THE FIX IS NOT TO CERTIFY OUR OWN POSITIONS. It is to serve positions that
already carry proof. Lichess themes are engine-derived and crowd-rated, and the
supply at a 900-1400 player's level is enormous:

    defensiveMove     34,651     the answer IS a defensive move
    exposedKing       29,469     the king is the reason the position is sharp
    hangingPiece      49,899
    fork              218,813
    discoveredAttack   78,334

A theme is chosen only where the theme's own meaning matches the topic. That
rules out some obvious-looking ones:

    backRankMate   NOT used for king_safety. The solver DELIVERS the mate, so
                   it trains attacking, not defending. The right side of the
                   board matters more than the right word.
    kingsideAttack NOT used for king_safety, for the same reason -- 150,351
                   positions that teach the opposite skill.
"""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

# topic -> (themes, what the player is told they are practising)
#
# Each entry has to answer: when the solver plays the right move here, what did
# they just practise? If the answer is not the topic, the theme does not belong.
THEMES_FOR_TOPIC: Dict[str, Tuple[Sequence[str], str]] = {
    # The solver must find a DEFENSIVE move -- that is the topic exactly. The
    # exposed-king set is included because the king being open is what makes
    # the position sharp, and the solver is the one who has to deal with it.
    "king_safety": (("defensiveMove", "exposedKing"),
                    "Positions where the right move is a defensive one."),

    # Seeing one move further: the shapes that punish a shallow look.
    "tactical_oversight": (("fork", "discoveredAttack", "skewer"),
                           "Positions where something is hiding one move away."),

    # Kept for completeness; our own pool already serves this one well, so the
    # themes are a fallback rather than the first choice.
    "missed_tactic": (("fork", "pin", "skewer", "discoveredAttack"),
                      "Positions with a tactic to find."),
    "piece_safety": (("hangingPiece",),
                     "Positions where something is loose."),
}

# A player is served puzzles around their own level. Below this a position
# teaches nothing; above it the failure is strength, not the topic.
RATING_BELOW = 150
RATING_ABOVE = 250
DEFAULT_RATING = 1200


def themes_for(topic: str) -> Sequence[str]:
    entry = THEMES_FOR_TOPIC.get(str(topic or ""))
    return entry[0] if entry else ()


def blurb_for(topic: str) -> str:
    entry = THEMES_FOR_TOPIC.get(str(topic or ""))
    return entry[1] if entry else ""


def rating_window(rating: object) -> Tuple[int, int]:
    """The band to draw from, around the player's own rating."""
    try:
        value = int(rating)
    except Exception:
        value = DEFAULT_RATING
    return max(600, value - RATING_BELOW), value + RATING_ABOVE


def mongo_query(topic: str, rating: object) -> dict:
    """A query for `lichess_puzzles`, or {} when the topic has no themes."""
    themes = themes_for(topic)
    if not themes:
        return {}
    low, high = rating_window(rating)
    return {"themes": {"$in": list(themes)}, "rating": {"$gte": low, "$lte": high}}


# THE QUESTION COMES FROM THE THEME, NOT THE TOPIC.
#
# The first themed king_safety position served was `8/4n3/P1K5/4k3/8/8/8/8` -- a
# king and pawn endgame -- under the topic's authored question, "Your king is the
# problem in this position." That is simply false about that board. A
# `defensiveMove` puzzle promises one thing only: the right move is a defensive
# one. So that is what the player is asked.
#
# This is the printed-question-against-the-grader fault, and it is the third time
# it has come up in this codebase. The rule: say what the evidence licenses and
# nothing more.
QUESTION_FOR_THEME = {
    "defensiveMove": "The right move here is a defensive one. Find it.",
    "exposedKing": "A king is caught in the open here. Find the move that uses it.",
    "fork": "One move here hits two things at once. Find it.",
    "discoveredAttack": "Moving one piece here opens a line behind it. Find the move.",
    "skewer": "Two pieces are on one line, the bigger one in front. Find the move.",
    "pin": "Two pieces are on one line, the smaller one in front. Find the move.",
    "hangingPiece": "Something here is loose. Find the move that takes it.",
}

# Shown when several themes feed one topic and we cannot say which this is.
GENERIC_THEME_QUESTION = "There is one clearly best move here. Find it."


def question_for_themes(themes) -> str:
    """The question honest for the themes this position actually carries."""
    matched = [QUESTION_FOR_THEME[t] for t in (themes or ())
               if t in QUESTION_FOR_THEME]
    # Exactly one known theme means we can be specific. More than one and the
    # specific sentence might describe the other one.
    return matched[0] if len(matched) == 1 else GENERIC_THEME_QUESTION
