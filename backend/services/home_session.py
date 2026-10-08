"""Today's session: gather the evidence, let the chooser decide, record it.

docs/home_session_scope.md

The chooser is a pure function and deliberately knows nothing about a database.
This is the layer that feeds it and writes down what was shown, which is what
makes appreciation an event rather than a state — measured, celebrating any
currently-quiet pattern gave APPRECIATE to 55 of 70 players and IMPROVE to none.

THREE SIGNALS, not a progress block. Mohit asked for improving / working on /
strength and all three exist: 48 of 57 players have an improving pattern, 52 a
focus, 39 a strength. It is the best-supported part of the design.

WHAT IS RECORDED AND WHERE. The shown appreciations live as a list on the
player's existing reading document rather than in a new collection. They are a
property of the reading, they are small, and a separate collection for a list of
strings would be a table nobody else ever joins.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from services.session_chooser import (
    APPRECIATE, appreciation_key, build_blocks, choose, total_minutes,
)

# NEVER use `coaching_label` for anything a player reads. Measured on prod:
# 30 of 52 active focuses have a number in it -- "Piece safety (100% critical)",
# "Time management (90% critical)" -- which is both a number and jargon, and it
# is already live. `topic_key` is clean and is what the label is derived from.
_NUMBERS = re.compile(r"[0-9%]")


def clean_label(*candidates: Any) -> str:
    """The first candidate that is readable and carries no number."""
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text or _NUMBERS.search(text):
            continue
        return text.replace("_", " ")
    return ""


READING_COLLECTION = "user_tactical_eye"
SHOWN_FIELD = "appreciations_shown"

# How far back to look for a sound sacrifice. The chooser then decides whether
# it is recent enough to be news; this only bounds the query.
RECENT_GAMES = 12


async def _recent_good_move(db, user_id: str) -> Optional[Dict[str, Any]]:
    """The most recent sound sacrifice, with a REAL distance in games.

    `games_ago` must be real. An earlier measurement hardcoded it to 1 for
    anything in the last twelve games, which faked recency and made the chooser
    look like it was appreciating everybody.
    """
    recent = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1},
    ).sort("played_at_utc", -1).limit(RECENT_GAMES).to_list(RECENT_GAMES)
    order = {g["game_id"]: index for index, g in enumerate(recent)}
    if not order:
        return None

    best: Optional[Dict[str, Any]] = None
    async for doc in db.game_analyses.find(
        {"game_id": {"$in": list(order)}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        for move in ((doc.get("stockfish_analysis") or {}).get("move_evaluations") or []):
            if move.get("is_opponent_move") or not move.get("is_brilliant"):
                continue
            ago = order[doc["game_id"]]
            if best is None or ago < best["games_ago"]:
                best = {
                    "fen": move.get("fen_before"),
                    "move_san": move.get("move_san") or move.get("move"),
                    "games_ago": ago,
                    "game_id": doc["game_id"],
                }
            break
    return best


async def _signals(db, user_id: str, patterns: Mapping[str, Any],
                   focus: Optional[Mapping[str, Any]]) -> List[Dict[str, str]]:
    """Improving, working on, strength. Three, and no more."""
    out: List[Dict[str, str]] = []

    improving = None
    for name, data in (patterns or {}).items():
        if not isinstance(data, Mapping) or data.get("state") not in ("declining", "fading"):
            continue
        streak = data.get("clean_streak") or 0
        if improving is None or streak > improving[1]:
            improving = (name, streak)
    if improving:
        out.append({"kind": "improving", "label": improving[0].replace("_", " ")})

    if focus:
        label = clean_label(focus.get("topic_label"), focus.get("topic_key"))
        if label:
            out.append({"kind": "working_on", "label": label})

    # A strength document is shaped differently from a weakness: it carries
    # `label` ("Low blunder rate") and no topic_key at all. Reading the weakness
    # fields here returned an empty label for all 39 players who have one.
    strength = await db.user_active_focus.find_one(
        {"user_id": user_id, "status": "active", "type": "strength"}, {"_id": 0})
    if strength:
        label = clean_label(strength.get("label"), strength.get("metric_key"))
        if label:
            out.append({"kind": "strength", "label": label})
    return out


async def build_session(db, user_id: str) -> Dict[str, Any]:
    """Today's session for this player."""
    from services.area_practice_links import practice_link
    from services.pattern_decay_service import refresh_user_pattern_decay

    # Read the cached decay rather than recomputing it. Measured: a live
    # refresh is 2.0 seconds and the recent-good-move scan another 0.6, which is
    # most of a 3.3 second page load. `refresh_user_pattern_decay` persists
    # nothing itself, so scripts/compute_habit_reading.py caches it here.
    cached = await db[READING_COLLECTION].find_one(
        {"user_id": user_id},
        {"_id": 0, SHOWN_FIELD: 1, "decay": 1, "good_move": 1}) or {}
    patterns = cached.get("decay")
    if patterns is None:
        # Never computed for this player yet. Correct and slow beats fast and
        # wrong; the batch job will make it fast.
        try:
            patterns = await refresh_user_pattern_decay(db, user_id) or {}
        except Exception:
            patterns = {}

    focus = await db.user_active_focus.find_one(
        {"user_id": user_id, "status": "active", "type": {"$ne": "strength"}},
        {"_id": 0})

    has_practice = False
    if focus:
        # The supply check is not optional: king_safety has 151 community
        # puzzles and 341 coach positions and none that pass verification, so a
        # focus can exist with nowhere to practise it.
        has_practice = bool(await practice_link(
            db, user_id, str(focus.get("topic_key") or "")))

    good_move = cached.get("good_move")
    if good_move is None and "good_move" not in cached:
        good_move = await _recent_good_move(db, user_id)

    shown = cached.get(SHOWN_FIELD) or []

    decision = choose(patterns, good_move, focus, has_practice, already_shown=shown)
    blocks = build_blocks(decision["mode"], decision["evidence"], focus,
                          has_practice)

    # Each block gets a destination that EXISTS. There is no session runner, so
    # there is no "start today's session" button -- inventing one would be the
    # dead-button problem this codebase already has twelve instances of.
    practice_href = None
    if focus and has_practice:
        link = await practice_link(db, user_id, str(focus.get("topic_key") or ""))
        practice_href = (link or {}).get("href")
    focus_label = clean_label(
        (focus or {}).get("topic_label"), (focus or {}).get("topic_key"))
    for block in blocks:
        if block["kind"] == "improve":
            if focus_label:
                block["title"] = focus_label
            block["href"] = practice_href
        elif block["kind"] == "challenge":
            # The drill the player's own weakest shape points at, when there is
            # one; otherwise the generic pattern page.
            try:
                from services.motif_drill_service import practice_offer
                offer = await practice_offer(db, user_id)
            except Exception:
                offer = None
            block["href"] = (offer or {}).get("href") or "/training"
        elif block["kind"] == "appreciate" and decision["evidence"].get("game_id"):
            block["href"] = "/game/%s" % decision["evidence"]["game_id"]
    blocks = [b for b in blocks if b["kind"] == "appreciate" or b.get("href")]

    # The one thing worth interrupting them with. Mohit, 2026-10-07: the data on
    # the page was not worth reading -- a weekly summary is something a player
    # can work out for themselves. services/striking_finding.py
    finding = await _finding_for(db, user_id)

    # Why this topic and not another one. Mohit, 2026-10-07: the card gave no
    # reason to care. Built from the SHAPE of the evidence rather than its size,
    # because the stored narrative is "235 events across 800 games, 68% of
    # them..." and none of that can be rendered. services/focus_why.py
    from services.focus_why import build_why
    why_focus = build_why(focus)
    if why_focus:
        for block in blocks:
            if block["kind"] == "improve":
                block["why"] = "%s %s" % (why_focus["lead"], why_focus["line"])

    # THE THREE MOVEMENTS. Mohit, 2026-10-07, after rejecting four rounds of
    # card layouts: *"it still looks like a report"*, and then the process
    # itself -- a coach reads your games, tells you what is good AND what is
    # bad, and plays you. docs/home_as_a_coach_scope.md
    #
    # Returned alongside the existing keys rather than instead of them, so the
    # surface can move over without the current page going dark mid-deploy.
    coach = await _movements(db, user_id, focus, finding, why_focus, decision)

    return {
        "schema_version": "home_session.v1",
        "coach": coach,
        "finding": finding,
        "focus_why": ("%s %s" % (why_focus["lead"], why_focus["line"]))
                     if why_focus else None,
        "mode": decision["mode"],
        # `why` is returned so the decision can be read back. A chooser whose
        # reasoning cannot be inspected is a random number generator with
        # good manners.
        "why": decision["why"],
        "headline": decision["evidence"].get("headline"),
        "line": decision["evidence"].get("line"),
        "fen": decision["evidence"].get("fen"),
        "move_san": decision["evidence"].get("move_san"),
        "signals": await _signals(db, user_id, patterns, focus),
        "blocks": blocks,
        "minutes": total_minutes(blocks),
        "_appreciation_key": (appreciation_key(decision["evidence"])
                              if decision["mode"] == APPRECIATE else None),
    }


async def _movements(db, user_id: str, focus, finding, why_focus,
                     decision) -> Dict[str, Any]:
    """What I know about you, today's board, and the invitation.

    A movement that has nothing to say is LEFT OUT rather than padded. Three
    sections with one real sentence between them is the report again.
    """
    from services.session_chooser import APPRECIATE
    from services.coach_invitation import build as build_invitation
    from services.coach_opening_words import opening_words
    from services.coach_today_position import todays_position

    strength = await db.user_active_focus.find_one(
        {"user_id": user_id, "status": "active", "type": "strength"},
        {"_id": 0, "label": 1})

    known = opening_words(
        strength, finding,
        ("%s %s" % (why_focus["lead"], why_focus["line"])) if why_focus else None)

    # A GOOD MOVE THEY ACTUALLY PLAYED, when the chooser has a fresh one.
    #
    # This is the only thing the retired session card carried that nothing else
    # does, and it reached 29% of players. Movement 1's whole job is the good
    # and the bad, so it belongs here rather than in a panel of its own -- and
    # a position they played well is a better "what I know about you" than any
    # sentence, because they can see it.
    #
    # Still one per player and still retired after it is seen: `appreciation_key`
    # and `record_shown` are untouched, which is what keeps a celebration rare
    # enough to mean something.
    evidence = decision.get("evidence") or {}
    if decision.get("mode") == APPRECIATE and evidence.get("fen"):
        known["good_game"] = {
            "headline": evidence.get("headline"),
            "line": evidence.get("line"),
            "fen": evidence.get("fen"),
            "move_san": evidence.get("move_san"),
            "href": ("/game/%s" % evidence["game_id"]
                     if evidence.get("game_id") else None),
        }
        known["measured"] = True

    # The board is keyed to the focus topic only when their own games can show
    # it. Measured: the strict rule reaches 33 of 49 focused players and misses
    # everyone focused on time_management -- which includes Mohit, the person
    # looking at the page. See coach_today_position.
    try:
        position = await todays_position(
            db, user_id, str((focus or {}).get("topic_key") or "") or None)
    except Exception:
        position = None

    return {
        "known": known if known.get("measured") else None,
        "today": position,
        "play": await build_invitation(db, user_id),
    }


async def record_shown(db, user_id: str, key: Optional[str]) -> None:
    """Retire an appreciation so it is not celebrated again.

    Called when the session is SERVED, not when it is acted on: the player has
    read it either way, and a celebration they ignored is still one they have
    seen.
    """
    if not key:
        return
    await db[READING_COLLECTION].update_one(
        {"user_id": user_id},
        {"$addToSet": {SHOWN_FIELD: key}},
        upsert=True,
    )


async def _finding_for(db, user_id: str) -> Optional[Dict[str, Any]]:
    """The strongest true thing we can say about this player, or None."""
    from services.game_outcome import user_lost
    from services.striking_finding import (
        choose_finding, results_fade_in_a_sitting, won_games_lost_on_time,
    )

    # Won positions lost on the clock. Reaches 18 of 70 players at the bar set
    # in striking_finding; the worst case on prod is 96 games.
    winning = analysed = 0
    timeouts = await db.games.find(
        {"user_id": user_id, "termination": "timeout"},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1}).to_list(3000)
    lost_ids = [g["game_id"] for g in timeouts if user_lost(g)]
    if lost_ids:
        async for doc in db.game_analyses.find(
            {"game_id": {"$in": lost_ids}},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        ):
            own = [m for m in ((doc.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []) if not m.get("is_opponent_move")]
            evals = [m.get("eval_after") for m in own
                     if isinstance(m.get("eval_after"), (int, float))]
            if not evals:
                continue
            analysed += 1
            # eval_after is USER-relative -- confirmed against wins by
            # checkmate, both colours positive. mate_info is NOT, and that
            # distinction has cost two bugs.
            if evals[-1] >= 200:
                winning += 1

    reading = await db[READING_COLLECTION].find_one(
        {"user_id": user_id}, {"_id": 0}) or {}

    # `one_family_dominates` USED to be third here and is deliberately gone.
    # It fired for 42 of 42 evaluable players with the identical sentence,
    # because the shape mix it reads barely varies between people -- the
    # numbers are in its docstring. A finding every player gets is a fact about
    # chess wearing a finding's clothes. Dropping it leaves 31 of 49 focused
    # players with no finding, and movement 1 still has their strength and the
    # reason for their focus, which are both actually theirs.
    return choose_finding([
        won_games_lost_on_time(winning, analysed),
        results_fade_in_a_sitting((reading.get("results") or {}).get("fade_points")),
    ])
