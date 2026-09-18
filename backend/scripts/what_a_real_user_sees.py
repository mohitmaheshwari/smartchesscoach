#!/usr/bin/env python3
"""What does a real user actually see?

Every gate in this product fails closed and fails quietly. A focus the plan
surface refuses, a page whose enrolment flag is off, a home variant keyed to
role — none of them raise, none of them log, and all of them are invisible
from an admin login because admins are exempt from most of the gates.

On 2026-09-17/18 that produced, all at once and all unnoticed:

  - a different Home page for the 3 privileged accounts than for everyone else
  - 11 users whose active focus no surface would act on
  - a coach conversation that told a player with 52 analysed games that it had
    never seen them play
  - 12 users who had earned a place in the Progress cohort and never got one,
    because enrolment ran once by hand and nothing runs it again

Every one would have shown up here on the day it started. So this runs the key
pages for a sample of ORDINARY users, prints what came back, and compares it
against a privileged account — because "works for me" is exactly the failure.

It is also a check on guesswork. Asked how bad the Progress page was, the
first answer given from reading flags was "off for 125 of 128 users"; the
real figure, from running it, is 27 of 45 ordinary accounts alive, and the
27 are the ones with enough games to have a projection worth showing. Read
the pages, do not reason about the gates.

    python scripts/what_a_real_user_sees.py                # 8 random users
    python scripts/what_a_real_user_sees.py --users 20
    python scripts/what_a_real_user_sees.py --user user_abc123
    python scripts/what_a_real_user_sees.py --json         # for a cron

Exit code is 1 when a page is alive for the privileged account and dead for
ordinary users, which is the specific shape worth waking someone for.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


class _StubUser:
    """Enough of the User model for a route handler to run.

    Calling the handlers directly rather than over HTTP keeps this runnable
    for any account, including the many with no live session. It does not
    exercise nginx or auth; those failures show up in the access log instead.
    """

    def __init__(self, doc: Dict[str, Any]):
        self.user_id = doc.get("user_id")
        self.email = doc.get("email")
        self.name = doc.get("name")
        self.role = doc.get("role") or "user"
        self.is_reviewer = bool(doc.get("is_reviewer"))


async def _home_dashboard(db, user):
    import routes.home as home

    home.db = db
    result = await home.get_home_dashboard_v2(user=user)
    analysed = result.get("games_analyzed") or 0
    return {
        "alive": bool(analysed),
        "detail": f"{analysed} analysed, accuracy {result.get('accuracy')}",
    }


async def _coach_conversation(db, user):
    import routes.home as home

    home.db = db
    result = await home.get_home_coach_conversation(user=user)
    has = bool(result.get("has_conversation"))
    return {
        "alive": has,
        "detail": result.get("topic_label") or "no conversation",
    }


async def _active_focus(db, user):
    from services.focus_bridge import get_active_focus_bundle

    bundle = await get_active_focus_bundle(db, user.user_id)
    topic = (bundle or {}).get("topic_key")
    return {"alive": bool(topic), "detail": topic or "no usable focus"}


async def _progress(db, user):
    import routes.player as player

    player.db = db
    result = await player.get_complete_coaching_progress(user=user)
    enabled = bool(result.get("enabled"))
    return {
        "alive": enabled,
        "detail": "enabled" if enabled else f"off: {result.get('reason')}",
    }


async def _lesson_supply(db, user):
    """Can we actually put a lesson in front of them?"""
    from services.personalized_lesson_adapter import (
        LessonUnavailable,
        _concept_descriptor,
    )

    try:
        descriptor = await _concept_descriptor(
            db, user.user_id, "piece_safety", {"limit": 5}
        )
    except LessonUnavailable as exc:
        return {"alive": False, "detail": str(exc)[:60]}
    items = descriptor.get("items") or []
    return {"alive": bool(items), "detail": f"{len(items)} positions"}


PAGES = [
    ("home dashboard", _home_dashboard),
    ("coach conversation", _coach_conversation),
    ("active focus", _active_focus),
    ("progress", _progress),
    ("lesson supply", _lesson_supply),
]

PROGRESS_FLAG = "personalized_game_review_coach"


async def _enrolment_gap(db) -> Dict[str, Any]:
    """Who has earned a cohort place and never got one.

    The Progress cohort was enrolled once, on 2026-09-12, by a script someone
    ran by hand. Nothing enrols anyone afterwards, so a user who crosses the
    bar on the 13th never gets in and nothing anywhere says so. Farhan signed
    up on the 16th with 56 analysed games and will wait forever.

    The bar is inferred from the cohort rather than hardcoded: the fewest
    analysed games any enrolled member has. If someone changes the entry rule,
    this follows it instead of going stale.
    """
    with_games = await db.games.distinct("user_id", {"is_analyzed": True})
    users = await db.users.find(
        {"user_id": {"$in": with_games}}, {"_id": 0}
    ).to_list(2000)

    enrolled, unenrolled = [], []
    for doc in users:
        counted = (doc, await db.games.count_documents(
            {"user_id": doc["user_id"], "is_analyzed": True}))
        if PROGRESS_FLAG in (doc.get("feature_flags") or {}):
            enrolled.append(counted)
        else:
            unenrolled.append(counted)

    if not enrolled:
        return {"bar": None, "qualified_but_missing": [], "correctly_excluded": 0}

    bar = min(n for _, n in enrolled)
    missing = [(d, n) for d, n in unenrolled if n >= bar]
    return {
        "bar": bar,
        "enrolled": len(enrolled),
        "qualified_but_missing": [
            {"user_id": d["user_id"], "email": d.get("email"), "analysed": n}
            for d, n in sorted(missing, key=lambda x: -x[1])
        ],
        "correctly_excluded": len(unenrolled) - len(missing),
    }


async def _check(db, user_doc) -> Dict[str, Any]:
    user = _StubUser(user_doc)
    pages: Dict[str, Any] = {}
    for label, fn in PAGES:
        try:
            pages[label] = await fn(db, user)
        except Exception as exc:  # a raising page is a dead page
            pages[label] = {
                "alive": False,
                "detail": f"{type(exc).__name__}: {str(exc)[:50]}",
            }
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "pages": pages,
    }


async def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=8)
    parser.add_argument("--user", default=None, help="check one account")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]

    if args.user:
        doc = await db.users.find_one({"user_id": args.user}, {"_id": 0})
        ordinary_docs = [doc] if doc else []
    else:
        # Ordinary means: not privileged, and has games. A user with no games
        # SHOULD see empty pages, so including them would only add noise.
        with_games = await db.games.distinct("user_id", {"is_analyzed": True})
        ordinary_docs = await db.users.find(
            {"user_id": {"$in": with_games},
             "role": {"$nin": ["admin", "super_admin"]}},
            {"_id": 0},
        ).to_list(1000)
        random.shuffle(ordinary_docs)
        ordinary_docs = ordinary_docs[: args.users]

    privileged_doc = await db.users.find_one(
        {"role": "super_admin"}, {"_id": 0}
    )

    ordinary = [await _check(db, d) for d in ordinary_docs if d]
    privileged = await _check(db, privileged_doc) if privileged_doc else None
    gap = await _enrolment_gap(db)

    # The finding that matters: alive for the privileged account, dead for
    # ordinary ones. That is the shape every miss this week had.
    exempt_only: List[str] = []
    for label, _ in PAGES:
        if not privileged or not privileged["pages"][label]["alive"]:
            continue
        alive = sum(1 for r in ordinary if r["pages"][label]["alive"])
        if ordinary and alive == 0:
            exempt_only.append(label)

    if args.json:
        print(json.dumps({
            "ordinary": ordinary,
            "privileged": privileged,
            "alive_for_admin_only": exempt_only,
            "enrolment_gap": gap,
        }, indent=2, default=str))
        return 1 if (exempt_only or gap["qualified_but_missing"]) else 0

    labels = [label for label, _ in PAGES]
    print(f"{'account':34}" + "".join(f"{lab[:17]:19}" for lab in labels))
    print("-" * (34 + 19 * len(labels)))
    for row in ordinary:
        line = f"{str(row['email'])[:32]:34}"
        for lab in labels:
            page = row["pages"][lab]
            line += f"{('OK  ' if page['alive'] else 'DEAD') + ' ' + str(page['detail'])[:13]:19}"
        print(line)
    if privileged:
        print("-" * (34 + 19 * len(labels)))
        line = f"{('[admin] ' + str(privileged['email'])[:24]):34}"
        for lab in labels:
            page = privileged["pages"][lab]
            line += f"{('OK  ' if page['alive'] else 'DEAD') + ' ' + str(page['detail'])[:13]:19}"
        print(line)

    print()
    for lab in labels:
        alive = sum(1 for r in ordinary if r["pages"][lab]["alive"])
        print(f"  {lab:22} alive for {alive} of {len(ordinary)} ordinary users")

    missing = gap.get("qualified_but_missing") or []
    if gap.get("bar") is not None:
        print(f"\n  progress cohort: {gap['enrolled']} enrolled, entry bar is "
              f"{gap['bar']} analysed games")
        print(f"    below the bar, correctly excluded: {gap['correctly_excluded']}")
        print(f"    AT OR ABOVE THE BAR AND NOT ENROLLED: {len(missing)}")
        for row in missing[:15]:
            print(f"      {str(row['email'])[:40]:42} {row['analysed']:5} analysed")
        if missing:
            print("    Enrolment ran once by hand and nothing runs it again.")

    if exempt_only:
        print("\n  ALIVE FOR THE ADMIN AND DEAD FOR EVERY ORDINARY USER:")
        for lab in exempt_only:
            print(f"    - {lab}")
        print("  This is the shape that hides: it works when you check it.")

    return 1 if (exempt_only or missing) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
