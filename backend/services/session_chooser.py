"""Which kind of day is today — the decision that makes Home a coach.

docs/home_session_scope.md

Mohit, 2026-10-06: the session should have a shape, and the coach should choose
which shape today deserves. Everything else on Home already exists in some form.
The chooser does not exist anywhere, and it is the product.

    APPRECIATE   there is fresh evidence they did the thing right
    IMPROVE      the focus has practice positions actually behind it
    CHALLENGE    neither of the above has anything to say

ORDER MATTERS AND IT IS NOT ARBITRARY. A player who has just done something right
is told so first. The product currently opens every session by naming a weakness,
and for something people do for fun that reads as homework.

DISCOVER IS NOT HERE and its absence is a measured decision, not an oversight.
There are 192,307 deflection puzzles and 15,445 interference puzzles in the
corpus and no authored lesson for either, so "teach me" would open positions with
no explanation. Detection is not teaching. It returns when there is something to
read.

THE SUPPLY CHECK ON IMPROVE IS NOT OPTIONAL. `king_safety` has 151 community
puzzles and 341 coach positions and zero that pass verification; twelve players
have had a focus whose practice button led to an empty page. A mode that cannot
be acted on is not a mode.

Pure functions: they take evidence, not a database, so the decision can be tested
without one.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

APPRECIATE = "appreciate"
IMPROVE = "improve"
CHALLENGE = "challenge"

# APPRECIATION IS AN EVENT, NOT A STATE. This is the correction that matters.
#
# The first version celebrated any pattern that was currently quiet, and measured
# across 70 players it answered APPRECIATE for 55 of them and IMPROVE for NOBODY.
# The focus — the core of the product — could never lead, because most players
# have some pattern that has gone quiet at any given moment.
#
# "You have stopped doing this" lands once. Said every day for a month it is
# noise, and it buries the thing they are actually working on.
#
# So the window is where the streak has JUST crossed into meaning something.
# Measured over the 102 quiet patterns on prod: p25 three games, median five,
# p75 eight, and a streak of exactly three is the commonest single value. Three
# to five is "this just went quiet". Beyond that it is established and the focus
# leads again.
#
# A proper implementation records which appreciations have already been shown and
# retires them. This window is a proxy for that store, and it is the first thing
# to replace when the store exists.
MIN_CLEAN_GAMES = 3
MAX_CLEAN_GAMES_TO_CELEBRATE = 5

# A sound sacrifice is only news for a few games. Beyond that it is a fact about
# their history, not about this week.
BRILLIANT_RECENT_GAMES = 3


def _appreciate_from_clean_pattern(patterns: Optional[Mapping[str, Any]]
                                   ) -> Optional[Dict[str, Any]]:
    """A weakness that has gone quiet, which is the strongest thing we can say."""
    best = None
    for name, data in (patterns or {}).items():
        if not isinstance(data, Mapping):
            continue
        if data.get("state") not in ("declining", "fading"):
            continue
        streak = data.get("clean_streak")
        if not isinstance(streak, (int, float)):
            continue
        # Outside the window it is either a coincidence or old news.
        if streak < MIN_CLEAN_GAMES or streak > MAX_CLEAN_GAMES_TO_CELEBRATE:
            continue
        if best is None or streak > best[1]:
            best = (name, streak)
    if best is None:
        return None
    return {
        "kind": "clean_pattern",
        "pattern": best[0],
        "headline": "Something you have been working on is starting to show.",
        "line": "It has not turned up in your recent games.",
    }


def _appreciate_from_good_move(good_move: Optional[Mapping[str, Any]]
                               ) -> Optional[Dict[str, Any]]:
    """A sound sacrifice: they gave up material and it was still the best move.

    Not a vanity badge. 100% of moves flagged this way are also the engine's
    choice, and the evaluation barely moves, which is what a SOUND sacrifice
    looks like — it holds the advantage rather than creating one.
    """
    if not good_move or not good_move.get("fen"):
        return None
    games_ago = good_move.get("games_ago")
    if isinstance(games_ago, (int, float)) and games_ago > BRILLIANT_RECENT_GAMES:
        return None
    return {
        "kind": "good_move",
        "fen": good_move.get("fen"),
        "move_san": good_move.get("move_san"),
        "game_id": good_move.get("game_id"),
        "headline": "You found something here worth keeping.",
        "line": "You gave up material and it was still the best move on the board.",
    }


def appreciation_key(evidence: Mapping[str, Any]) -> str:
    """A stable name for one thing worth celebrating, so it is shown once.

    Measured before this existed: the chooser answered APPRECIATE for 49 of 70
    players and IMPROVE for 4, because both appreciation signals are common at
    any given moment. Celebrating is only powerful if it is rare, and the way to
    make it rare is to retire each one after it has been seen.
    """
    kind = str(evidence.get("kind") or "")
    if kind == "clean_pattern":
        return "clean_pattern:%s" % evidence.get("pattern")
    if kind == "good_move":
        return "good_move:%s" % evidence.get("fen")
    return kind


def choose(patterns: Optional[Mapping[str, Any]] = None,
           good_move: Optional[Mapping[str, Any]] = None,
           focus: Optional[Mapping[str, Any]] = None,
           focus_has_practice: bool = False,
           already_shown: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Today's mode, and why.

    `why` is returned so the decision can be read back in a log or a test. A
    chooser whose reasoning cannot be inspected is a random number generator with
    good manners.
    """
    seen = set(already_shown or ())
    appreciate = None
    for candidate in (_appreciate_from_clean_pattern(patterns),
                      _appreciate_from_good_move(good_move)):
        if candidate and appreciation_key(candidate) not in seen:
            appreciate = candidate
            break
    if appreciate:
        return {"mode": APPRECIATE, "why": appreciate["kind"],
                "evidence": appreciate}

    if focus and focus_has_practice:
        return {
            "mode": IMPROVE,
            "why": "focus_with_practice",
            "evidence": {
                "kind": "focus",
                "topic_key": focus.get("topic_key"),
                "headline": "Let us keep working on the one thing.",
                # NOT coaching_label: 30 of 52 contain a number.
                "line": focus.get("topic_label") or "",
            },
        }

    # Always available: the corpus is effectively unlimited and rating-matched.
    return {
        "mode": CHALLENGE,
        "why": ("focus_without_practice" if focus else "no_focus"),
        "evidence": {
            "kind": "challenge",
            "headline": "Let us see what you can do.",
            "line": "Positions a little above where you usually play.",
        },
    }


def build_blocks(mode: str, evidence: Mapping[str, Any],
                 focus: Optional[Mapping[str, Any]] = None,
                 focus_has_practice: bool = False,
                 challenge_available: bool = True) -> List[Dict[str, Any]]:
    """The session underneath the headline.

    The mode says which block LEADS. The session may still carry the others,
    because a day that only celebrates teaches nothing and a day that only
    corrects is the homework problem again.

    Minutes are the one number this product shows a player on purpose: a session
    with no sense of length is a session nobody starts. See the scope.
    """
    blocks: List[Dict[str, Any]] = []

    # An appreciate BLOCK only earns its place when there is something to look
    # at. When the celebration is "a pattern has gone quiet" there is no board
    # and no position, and the headline above already says it -- a block
    # repeating it in smaller type is noise.
    if mode == APPRECIATE and evidence.get("fen"):
        blocks.append({
            "kind": APPRECIATE,
            "title": "The move you got right",
            "detail": evidence.get("line", ""),
            "minutes": 2,
            "fen": evidence.get("fen"),
        })

    if focus and focus_has_practice:
        blocks.append({
            "kind": IMPROVE,
            "title": (focus.get("topic_label") or "Your focus"),
            "detail": "Positions from your own games.",
            "minutes": 5,
            "topic_key": focus.get("topic_key"),
        })

    if challenge_available:
        blocks.append({
            "kind": CHALLENGE,
            "title": "Unseen positions",
            "detail": "No hints unless you ask.",
            "minutes": 2,
        })

    return blocks


def total_minutes(blocks: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(b.get("minutes") or 0) for b in blocks)
