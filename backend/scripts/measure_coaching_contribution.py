#!/usr/bin/env python3
"""Measure what ChessGuru actually contributed, not what a user did anyway.

A plain before-and-after chart cannot support the claim it appears to make.
Players sign up when they are on a bad run, which means they are already
playing below their real strength and will drift back up with no help from
anyone, and the people who use a coaching tool are the people who would
have worked at their chess regardless. Both effects push a naive chart the
same way: they make the product look good. Rating is also far too noisy at
this sample size to separate any of it.

So this measures something narrower and defensible instead. For each focus
we put in front of a user we already store a baseline: how often they made
that specific mistake before we said anything. This compares that against
the same rate afterwards, and -- the part that makes it a claim rather
than a coincidence -- against the mistakes we did *not* teach them over the
very same games.

    contribution = (taught_after - taught_before)
                 - (untaught_after - untaught_before)

If somebody simply got better, everything improves together and the
difference is zero, which is the honest answer. Only a taught weakness
falling faster than their untaught ones is evidence we did something. That
comparison is within a single player, so it survives motivation, playing
more, and drifting back to their real strength: those lift the control
just as much as the treatment.

The script reports its own funnel. Where a user has too few games after
the focus started to say anything, it says so rather than producing a
number, because "not enough evidence yet" is a real finding and a fabricated
percentage is not.

Usage:
    python backend/scripts/measure_coaching_contribution.py
    MIN_GAMES_AFTER=10 python backend/scripts/measure_coaching_contribution.py
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
# Below this, a rate is dominated by which openings they happened to play.
MIN_GAMES_EACH_SIDE = int(os.environ.get("MIN_GAMES_AFTER", "8"))


def as_dt(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        cleaned = value.replace("Z", "").split("+")[0]
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned[:26], fmt)
            except ValueError:
                continue
    return None


def user_move_history(db, user_id):
    """Every analysed user move, as (played_at, cognitive_gap).

    Opponent moves are excluded: they are not this player's mistakes. The
    field is `is_opponent_move` and there is no `is_user_move`, so the test
    has to be a negation.
    """
    games = {}
    for game in db.games.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "date_played_iso": 1, "date_played": 1},
    ):
        played = as_dt(game.get("date_played_iso") or game.get("date_played"))
        if played:
            games[game.get("game_id")] = played

    history = []
    if not games:
        return history
    for doc in db.game_analyses.find(
        {"game_id": {"$in": list(games)}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        played = games.get(doc.get("game_id"))
        if not played:
            continue
        moves = (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []
        for move in moves:
            if move.get("is_opponent_move"):
                continue
            history.append((played, doc.get("game_id"), move.get("cognitive_gap")))
    return history


def rates(history, topic):
    """Mistakes per 100 moves for the taught topic and for everything else."""
    total = len(history)
    if not total:
        return None, None, 0, 0
    taught = sum(1 for _, _, gap in history if gap == topic)
    other = sum(1 for _, _, gap in history if gap and gap != topic)
    n_games = len({gid for _, gid, _ in history})
    return 100.0 * taught / total, 100.0 * other / total, total, n_games


def main() -> int:
    db = MongoClient(MONGO_URL)[DB_NAME]

    # Strengths are stored in this collection too, and counting them as
    # things we taught would inflate everything.
    focuses = list(
        db.user_active_focus.find(
            {"type": "weakness"},
            {"_id": 0, "user_id": 1, "topic_key": 1, "started_at": 1,
             "baseline_metric": 1, "status": 1},
        )
    )
    print(f"  weakness focuses on record        : {len(focuses)}")

    # A focus that gets superseded is re-written as a new row with the same
    # start, so the same teaching period appears four or five times. Counting
    # each one separately would quietly multiply the sample and let a handful
    # of users dominate the result. One period per user and topic, earliest
    # start wins.
    deduped = {}
    for focus in focuses:
        key = (focus.get("user_id"), focus.get("topic_key"))
        started = as_dt(focus.get("started_at"))
        if not all(key) or started is None:
            continue
        if key not in deduped or started < deduped[key][0]:
            deduped[key] = (started, focus)
    focuses = [f for _, f in deduped.values()]
    print(f"  distinct teaching periods         : {len(focuses)}")

    # A focus row only means the system *chose* something to work on. It is
    # not evidence the user was ever taught it, and attributing a change to
    # a lesson nobody opened would be the same wishful arithmetic this script
    # exists to avoid. Engagement is tracked separately so both numbers can
    # be reported.
    engaged_users = {
        d.get("user_id")
        for d in db.learning_sessions.find({}, {"_id": 0, "user_id": 1})
        if d.get("user_id")
    } | {
        d.get("user_id")
        for d in db.puzzle_attempts.find({}, {"_id": 0, "user_id": 1})
        if d.get("user_id")
    }
    print(f"  users who actually did a lesson   : {len(engaged_users)}")

    funnel = Counter()
    cache = {}
    results = []

    for focus in focuses:
        user_id = focus.get("user_id")
        topic = focus.get("topic_key")
        started = as_dt(focus.get("started_at"))
        if not (user_id and topic and started):
            funnel["no user, topic or start time"] += 1
            continue
        if user_id not in cache:
            cache[user_id] = user_move_history(db, user_id)
        history = cache[user_id]
        if not history:
            funnel["no analysed games at all"] += 1
            continue

        before = [row for row in history if row[0] < started]
        after = [row for row in history if row[0] >= started]
        n_before = len({gid for _, gid, _ in before})
        n_after = len({gid for _, gid, _ in after})
        if n_after < MIN_GAMES_EACH_SIDE:
            funnel[f"fewer than {MIN_GAMES_EACH_SIDE} games since we taught it"] += 1
            continue
        if n_before < MIN_GAMES_EACH_SIDE:
            funnel[f"fewer than {MIN_GAMES_EACH_SIDE} games before we taught it"] += 1
            continue

        t_before, o_before, _, _ = rates(before, topic)
        t_after, o_after, _, _ = rates(after, topic)
        if None in (t_before, o_before, t_after, o_after):
            funnel["no usable move data"] += 1
            continue

        taught_change = t_after - t_before
        control_change = o_after - o_before
        results.append({
            "user_id": user_id, "topic": topic,
            "games_before": n_before, "games_after": n_after,
            "taught_before": t_before, "taught_after": t_after,
            "control_before": o_before, "control_after": o_after,
            "taught_change": taught_change, "control_change": control_change,
            "contribution": taught_change - control_change,
            "engaged": user_id in engaged_users,
        })
        funnel["measurable"] += 1

    print("  funnel:")
    for reason, count in funnel.most_common():
        print(f"     {reason:46} {count}")

    if not results:
        print()
        print("  Nothing is measurable yet, and that is the finding.")
        print("  No contribution figure can be reported from this data.")
        return 0

    print()
    print(f"  measurable focus periods: {len(results)}")
    print(f"  distinct users          : {len({r['user_id'] for r in results})}")
    print()
    print("  %-20s %-16s %6s %6s  %8s %8s %8s" % (
        "user", "topic", "gms<", "gms>", "taught", "control", "ours"))
    for r in sorted(results, key=lambda r: r["contribution"]):
        print("  %-20s %-16s %6d %6d  %+8.2f %+8.2f %+8.2f" % (
            r["user_id"][:20], r["topic"][:16], r["games_before"], r["games_after"],
            r["taught_change"], r["control_change"], r["contribution"]))

    engaged = [r for r in results if r["engaged"]]
    print()
    print(f"  of those, periods where the user actually did a lesson: {len(engaged)}")
    if engaged:
        vals = [r["contribution"] for r in engaged]
        better = sum(1 for v in vals if v < 0)
        print(f"     median {statistics.median(vals):+.2f}   "
              f"taught weakness fell faster in {better}/{len(vals)}")
    else:
        print("     none. Every measurable period belongs to a user who never")
        print("     opened a lesson, so none of this can be attributed to us.")

    contributions = [r["contribution"] for r in results]
    print()
    print("  A negative number means the taught mistake fell faster than the")
    print("  untaught ones, which is the direction that would credit us.")
    print(f"     median : {statistics.median(contributions):+.2f} per 100 moves")
    print(f"     mean   : {statistics.fmean(contributions):+.2f}")
    helped = sum(1 for c in contributions if c < 0)
    print(f"     focus periods where the taught weakness fell faster: "
          f"{helped}/{len(contributions)}")
    if len(results) < 20:
        print()
        print("  Too few periods to claim anything in public. Treat this as an")
        print("  instrument check, not a result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
