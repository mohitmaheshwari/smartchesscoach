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

    return {
        "schema_version": "home_session.v1",
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
