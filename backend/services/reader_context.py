"""What the coach knows about the player, for one game's captions.

Mohit: "one move blunder is there, but that can be easily showed by arrow
... where is the teaching and the memory of player ... game review should
also consider the time taken to make that move, why he made that move?"

Right, and the arrow already says WHAT. These are the three things a coach
adds, all measured as present in the data before this was written:

  TIME      `time_spent_seconds` is on 69.4% of moves. For blunders of
            200cp or more the MEDIAN is 7 seconds: half are played in
            under seven. That is not a knowledge problem, and it is the
            direct answer to "why did he play it".

  LATELY    93% of user+gap pairs recur, one user's missed_tactic 157
            times. So "this keeps happening" is available -- but NEVER as
            a count. The house rule is no failure scoreboard, so the
            decay service's own words are used: a pattern is active,
            declining or fading, and a clean streak is something to say
            out loud.

  TRAINED   whether they have solved puzzles on this pattern. It splits
            "never learnt it" from "learnt it and did not look", which
            need opposite coaching, and the move alone cannot tell them
            apart.

Gathered ONCE per game, not per card: the decay state and the training
history are per-user facts that do not change mid-game. Two reads per
game, with a sync handle, so the analysis worker can use it as it stands.

Everything here is read-only and every failure is swallowed. A caption
that loses its context is thinner; a caption that fails to generate is
nothing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# A move is "quick for this player" when it is this fraction of the median
# time they spent in THIS game. Relative, not absolute: three seconds is
# fast for someone averaging thirty and normal in a bullet game.
QUICK_FRACTION = 0.4

# Below this the median is not a useful baseline -- a game with four timed
# moves tells us nothing about the player's normal pace.
MIN_TIMED_MOVES = 8


def game_pace(move_evaluations: List[Dict]) -> Optional[float]:
    """The median seconds this player spent per move in this game."""
    times = sorted(
        float(m["time_spent_seconds"]) for m in (move_evaluations or [])
        if isinstance(m.get("time_spent_seconds"), (int, float))
        and float(m["time_spent_seconds"]) >= 0
    )
    if len(times) < MIN_TIMED_MOVES:
        return None
    return times[len(times) // 2]


def gather(db, user_id: Optional[str],
           move_evaluations: List[Dict]) -> Dict[str, Any]:
    """Per-game, per-user context. Two reads. Never raises."""
    ctx: Dict[str, Any] = {
        "pace_seconds": game_pace(move_evaluations),
        "decay": {},
        "trained": set(),
    }
    if db is None or not user_id:
        return ctx
    try:
        row = db.user_pattern_decay.find_one(
            {"user_id": user_id}, {"scores": 1, "_id": 0}) or {}
        scores = row.get("scores") or {}
        for pattern, s in scores.items():
            if not isinstance(s, dict):
                continue
            ctx["decay"][pattern] = {
                "state": s.get("state"),
                "clean_streak": int(s.get("clean_streak") or 0),
            }
    except Exception as exc:
        logger.debug("[reader_context] decay unavailable: %r", exc)
    try:
        # Patterns they have actually got RIGHT in training. A wrong
        # attempt is not evidence they know it.
        for p in db.puzzle_attempts.distinct(
                "issue_type", {"user_id": user_id, "correct": True}):
            if p:
                ctx["trained"].add(str(p))
    except Exception as exc:
        logger.debug("[reader_context] training history unavailable: %r", exc)
    return ctx


def for_move(ctx: Dict[str, Any], move: Dict[str, Any]) -> Dict[str, Any]:
    """The reader-facing context for ONE card, or {} when there is none.

    Only states what is known. A move with no clock gets no time fact
    rather than a guessed one, which matters because 30.6% of moves have
    no time at all.
    """
    out: Dict[str, Any] = {}
    secs = move.get("time_spent_seconds")
    pace = ctx.get("pace_seconds")
    if isinstance(secs, (int, float)) and secs >= 0:
        out["seconds_on_this_move"] = int(round(float(secs)))
        if pace:
            out["their_usual_seconds_this_game"] = int(round(pace))
            # Said as a judgement the engine can defend: this move took
            # far less than their own normal, in their own game.
            if float(secs) <= pace * QUICK_FRACTION:
                out["quick_for_this_player"] = True
    gap = move.get("cognitive_gap")
    if gap:
        d = (ctx.get("decay") or {}).get(gap) or {}
        state = d.get("state")
        if state in ("active", "declining", "fading"):
            # The decay service's own vocabulary, never a count. A count
            # is a failure scoreboard and this product does not show one.
            out["this_weakness_lately"] = state
            if state == "declining" and d.get("clean_streak"):
                out["clean_games_in_a_row"] = int(d["clean_streak"])
        if gap in (ctx.get("trained") or set()):
            # Changes the lesson entirely: not "learn this" but "you know
            # this one, you did not look".
            out["they_have_solved_puzzles_on_this"] = True
    return out
