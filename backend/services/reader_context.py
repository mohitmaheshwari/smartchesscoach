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
           move_evaluations: List[Dict],
           game_id: Optional[str] = None) -> Dict[str, Any]:
    """Per-game, per-user context. Four reads. Never raises.

    `game_id` is optional so existing callers keep working; without it the
    SEEN-BEFORE facts are skipped rather than guessed, because "have we
    flagged this before" cannot be answered without knowing which game is
    "now".
    """
    ctx: Dict[str, Any] = {
        "pace_seconds": game_pace(move_evaluations),
        "decay": {},
        "trained": set(),
        "pattern_here": {},     # move_number -> pattern_id, THIS game
        "pattern_before": {},   # pattern_id -> what happened in EARLIER games
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
    if game_id:
        _gather_seen_before(db, user_id, game_id, ctx)
    return ctx


def _gather_seen_before(db, user_id: str, game_id: str,
                        ctx: Dict[str, Any]) -> None:
    """Has this player been shown this exact pattern in an EARLIER game?

    Mohit 2026-10-27: "have we coached him on this and asked to correct
    ... he reviewed this game, we taught him that this was an issue, so
    games should be connected, like a real coach does."

    `user_pattern_events` is the one collection that can answer it:
    142,392 rows, every one carrying user_id, game_id, move_number,
    pattern_id and outcome. `user_concept_understanding` was the obvious
    candidate and is the wrong one -- its `shown_games` holds 39 entries
    across Mohit's 916 games, and its `shown_count` is a RENDER counter
    (32,807 on a concept linked to 10 games), so neither field can carry
    this.

    `pattern_id` is also the vocabulary `data/pattern_catalog.json`
    bridges to concepts, so nothing new has to be mapped. The coarse
    `cognitive_gap` on the move row cannot be used: it has six values for
    this user, against dozens of pattern ids.

    Two reads, both indexed on user_id: this game's events to learn which
    pattern each move belongs to, and the earlier events for history.
    """
    try:
        for row in db.user_pattern_events.find(
                {"user_id": user_id, "game_id": game_id},
                {"_id": 0, "move_number": 1, "pattern_id": 1}):
            mn, pid = row.get("move_number"), row.get("pattern_id")
            if mn is not None and pid:
                ctx["pattern_here"][int(mn)] = str(pid)
    except Exception as exc:
        logger.debug("[reader_context] this-game patterns unavailable: %r", exc)
        return
    wanted = set(ctx["pattern_here"].values())
    if not wanted:
        return
    try:
        for row in db.user_pattern_events.find(
                {"user_id": user_id,
                 "game_id": {"$ne": game_id},
                 "pattern_id": {"$in": sorted(wanted)}},
                {"_id": 0, "pattern_id": 1, "game_id": 1, "outcome": 1,
                 "created_at": 1}).sort("created_at", -1):
            pid = str(row.get("pattern_id"))
            seen = ctx["pattern_before"].setdefault(
                pid, {"games": set(), "last_outcome": None})
            if row.get("game_id"):
                seen["games"].add(str(row["game_id"]))
            # Sorted newest first, so the first outcome seen is the latest.
            if seen["last_outcome"] is None and row.get("outcome"):
                seen["last_outcome"] = str(row["outcome"])
    except Exception as exc:
        logger.debug("[reader_context] pattern history unavailable: %r", exc)


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
    # SEEN BEFORE -- the same pattern, in an earlier game of their own.
    # Booleans only. The house rule is no failure scoreboard, so this
    # never says how many times: "we looked at this in an earlier game"
    # is a coach's sentence, "your 7th time" is a tally.
    mn = move.get("move_number")
    if mn is not None:
        try:
            pid = (ctx.get("pattern_here") or {}).get(int(mn))
        except (TypeError, ValueError):
            pid = None
        if pid:
            seen = (ctx.get("pattern_before") or {}).get(pid)
            if seen and seen.get("games"):
                out["we_flagged_this_in_an_earlier_game"] = True
                if seen.get("last_outcome") == "miss":
                    out["they_missed_it_last_time_too"] = True
                elif seen.get("last_outcome"):
                    out["they_got_it_right_last_time"] = True
    return out
