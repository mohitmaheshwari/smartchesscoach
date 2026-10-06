"""Precompute the week, rhythm and session readings into `user_tactical_eye`.

Mohit asked how the week is going, how regular he is, and whether he is
learning. All three are computable from data we already hold and none of them
were stored, so the home card could only show a context-free ratio.

Running the opportunity gate over one player's twenty thousand moves takes about
twenty seconds, so this is a batch job for the same reason
`compute_tactical_eye.py` is. It writes into the same per-player document rather
than adding a collection.

Safe by default: prints rows and writes nothing without --apply.

    python scripts/compute_habit_reading.py
    python scripts/compute_habit_reading.py --apply
    python scripts/compute_habit_reading.py --user-id user_x --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import datetime
import os
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.pattern_decay_service import refresh_user_pattern_decay  # noqa: E402
from services.chess_habit_reading import (  # noqa: E402
    LATER_FROM_GAME, results_fade, rhythm, session_curve, week_vs_usual,
)
from services.game_outcome import user_won  # noqa: E402
from services.opportunity_gate import observe  # noqa: E402
from services.two_layer_diagnosis import CACHE_COLLECTION  # noqa: E402

UTC = datetime.timezone.utc
# Games closer together than this belong to the same sitting. Chosen to match
# the measurement that found the fade; changing it invalidates the stored curve.
SESSION_GAP_MINUTES = 45


def _when(game):
    for key in ("played_at_utc", "date_played"):
        value = game.get(key)
        stamp = None
        if isinstance(value, datetime.datetime):
            stamp = value
        elif isinstance(value, str):
            try:
                stamp = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                stamp = None
        if stamp is not None:
            return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return None


def _sessions(rows):
    """Games grouped into sittings, each already time-ordered."""
    if not rows:
        return []
    out, current = [], [rows[0]]
    for previous, nxt in zip(rows, rows[1:]):
        if (nxt[0] - previous[0]).total_seconds() <= SESSION_GAP_MINUTES * 60:
            current.append(nxt)
        else:
            out.append(current)
            current = [nxt]
    out.append(current)
    return out


def _fade(sessions, chances_by_game):
    """(early, later) as (chances, taken), by position within a sitting."""
    early, later = [0, 0], [0, 0]
    for session in sessions:
        for index, (_stamp, game_id) in enumerate(session):
            got = chances_by_game.get(game_id)
            if not got:
                continue
            slot = early if index < LATER_FROM_GAME - 1 else later
            slot[0] += got[0]
            slot[1] += got[1]
    return tuple(early), tuple(later)


def _fade_points(early, later):
    if early[0] == 0 or later[0] == 0:
        return None
    return (100.0 * early[1] / early[0]) - (100.0 * later[1] / later[0])


async def compute(db, user_id):
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "played_at_utc": 1, "date_played": 1,
         "result": 1, "user_color": 1},
    ).to_list(8000)
    won_by_game = {g["game_id"]: (1 if user_won(g) else 0) for g in games}
    rows = sorted(
        [(_when(g), g["game_id"]) for g in games if _when(g)], key=lambda r: r[0])
    if not rows:
        return None
    stamp_of = {gid: t for t, gid in rows}

    best = {}
    async for doc in db.game_analyses.find(
        {"game_id": {"$in": list(stamp_of)}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for move in ((doc.get("stockfish_analysis") or {}).get("move_evaluations") or []):
            if move.get("fen_before"):
                best[(doc["game_id"], move["fen_before"])] = (
                    move.get("best_move_uci") or move.get("best_move"))

    per_game = collections.defaultdict(lambda: [0, 0])
    per_week = collections.defaultdict(lambda: [0, 0])
    async for obs in db.move_observations.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "fen_before": 1, "move_uci": 1},
    ):
        game_id = obs.get("game_id")
        stamp = stamp_of.get(game_id)
        if not stamp:
            continue
        seen = observe(obs.get("fen_before"),
                       best.get((game_id, obs.get("fen_before"))),
                       obs.get("move_uci"))
        if not seen:
            continue
        took = 1 if seen["took"] else 0
        per_game[game_id][0] += 1
        per_game[game_id][1] += took
        key = stamp.isocalendar()[:2]
        per_week[key][0] += 1
        per_week[key][1] += took

    weeks = sorted(per_week)
    this_week = tuple(per_week[weeks[-1]]) if weeks else (0, 0)
    prior = [tuple(per_week[k]) for k in weeks[:-1]]

    today = datetime.datetime.now(UTC).date()
    days = collections.Counter(t.date() for t, _ in rows)
    recent_days = sum(1 for d in days if (today - d).days <= 28)
    per_day = statistics.median(days.values()) if days else None

    sessions = _sessions(rows)
    early, later = _fade(sessions, per_game)
    half = len(sessions) // 2
    halves = []
    for part in (sessions[:half], sessions[half:]):
        halves.append(_fade_points(*_fade(part, per_game)))

    # The same split, but counting GAMES WON rather than chances taken. The two
    # disagree for at least one player and the disagreement is the finding.
    per_game_result = {gid: (1, won) for gid, won in won_by_game.items()}
    r_early, r_later = _fade(sessions, per_game_result)
    r_halves = []
    for part in (sessions[:half], sessions[half:]):
        r_halves.append(_fade_points(*_fade(part, per_game_result)))

    # Cached for the home session, which must not spend two seconds
    # recomputing decay on a page load. `refresh_user_pattern_decay` persists
    # nothing of its own, so this is the only store there is.
    try:
        decay = await refresh_user_pattern_decay(db, user_id) or {}
    except Exception:
        decay = {}
    from services.home_session import _recent_good_move
    try:
        good = await _recent_good_move(db, user_id)
    except Exception:
        good = None

    return {
        "decay": decay,
        "good_move": good,
        "week": week_vs_usual(this_week, prior),
        "rhythm": rhythm(recent_days, per_day),
        "session": session_curve(early, later, halves),
        "results": results_fade(r_early, r_later, _fade_points(early, later),
                                r_halves),
    }


async def main_async(apply, only_user):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    users = [only_user] if only_user else await db.move_observations.distinct("user_id")
    print("players: %d%s" % (len(users), "" if apply else "   (dry run)"))

    tally = collections.Counter()
    for user_id in users:
        try:
            reading = await compute(db, user_id)
        except Exception as exc:
            tally["error:" + type(exc).__name__] += 1
            continue
        if reading is None:
            tally["no games"] += 1
            continue
        for key in ("week", "rhythm", "session", "results"):
            tally[key if reading[key] else "no " + key] += 1
        if reading["results"]:
            print("   %-24s RESULTS FADE %.1f points" % (
                user_id[:22], reading["results"]["fade_points"]))
        if not apply:
            continue
        await db[CACHE_COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "habits_computed_at": datetime.datetime.now(UTC),
                "decay": reading["decay"],
                "good_move": reading["good_move"],
                "decay_computed_at": datetime.datetime.now(UTC),
                "week": reading["week"],
                "rhythm": reading["rhythm"],
                "session": reading["session"],
                "results": reading["results"],
            }},
            upsert=True,
        )
    print()
    for key, count in tally.most_common():
        print("   %-18s %d" % (key, count))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply, args.user_id))


if __name__ == "__main__":
    raise SystemExit(main())
