"""Movement 3: play me.

docs/home_as_a_coach_scope.md

This is the half of coaching the product already has and buries in a nav tile.
A human coach does not only read your games -- he sits down and plays you, and
talks while you play. And it is the one place the product beats him rather than
imitating him: always there, never tired, sees every move.

EVERY SENTENCE HERE IS A PROMISE AND HAS BEEN CHECKED AGAINST THE CODE.

"I will stop you before the mistake" -- the pre-move guardian. Verified
2026-10-07: the call in CoachPlay.jsx is skipped when `unifiedExperience` is on,
and prod has PWC_UNIFIED_EXPERIENCE_V1_ENABLED=false with the rollout limited to
admin roles, so the guardian runs for every real player. It also demonstrably
fires: 22 sessions carry a move the player pushed through a warning, and there
are 45 critical_interrupt messages. Mohit's own sessions are among them.

If that flag is ever turned on for real users, this promise stops being true for
them and `invitation()` has to take the flag into account. That is why the check
is written down here instead of being a thing somebody has to remember.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

HREF = "/play-with-coach"


def invitation(played_before: bool = False) -> Dict[str, Any]:
    """The offer, in a coach's words rather than a feature's.

    No minutes figure is claimed. Time controls are the player's choice at
    setup, so "twenty minutes" would be us deciding something they decide.
    """
    if played_before:
        # Someone who has sat down before does not need to be sold it. He needs
        # to be asked again, which is what a coach with a free hour does.
        return {
            "href": HREF,
            "lead": "Want to play?",
            "line": "Same as last time. I will stop you before the mistakes "
                    "and tell you what I saw.",
            "cta": "Sit down",
        }
    return {
        "href": HREF,
        "lead": "Play me.",
        "line": "This is the part a coach does that a puzzle cannot. I will "
                "stop you before the mistakes, while you can still change "
                "your mind, and tell you why.",
        "cta": "Sit down",
    }


async def build(db, user_id: str) -> Dict[str, Any]:
    """The invitation, aware of whether they have played before."""
    try:
        played = await db.coach_sessions.count_documents(
            {"user_id": user_id}, limit=1)
    except Exception:
        played = 0
    return invitation(played_before=bool(played))
