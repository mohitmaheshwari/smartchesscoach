"""
The Mirror
==========

For the home page "Evidence" slot: a one-sentence verdict on the user's
most recent game, spoken through the lens of their known habits.

Core question: did this game repeat who you usually are, or did it
break the pattern?

Honest rules:
- Win/loss is backdrop, not verdict. "You won but played like usual"
  is more valuable than "You won".
- No invention. If we don't have ≥3 recent-game patterns established,
  we say so ("still reading your game") instead of fabricating a verdict.
- Reads from the same `game_analyses.stockfish_analysis.move_evaluations`
  that everything else in the system uses. No parallel signal sources.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Two voice forms per pattern.
#   "verb"   — past-tense action ("hung a piece") for the repeated case.
#   "noun"   — noun phrase ("hung pieces") for the broke-pattern case ("No X").
# Keeps grammar natural without template gymnastics.
_PATTERN_VOICE: Dict[str, Dict[str, str]] = {
    "piece_safety":       {"verb": "hung a piece",                "noun": "hung pieces"},
    "king_safety":        {"verb": "exposed your king",           "noun": "king-safety slips"},
    "tactical_oversight": {"verb": "missed a tactic",             "noun": "missed tactics"},
    "calculation_depth":  {"verb": "stopped calculating early",   "noun": "shallow calculation"},
    "missed_tactic":      {"verb": "missed a tactic",             "noun": "missed tactics"},
    "opening_knowledge":  {"verb": "drifted from opening theory", "noun": "opening drift"},
    "pawn_structure":     {"verb": "damaged your pawn structure", "noun": "pawn-structure damage"},
    "piece_activity":     {"verb": "left pieces passive",         "noun": "passive pieces"},
    "endgame_technique":  {"verb": "slipped in the endgame",      "noun": "endgame slips"},
    "time_pressure":      {"verb": "rushed under time pressure",  "noun": "time-pressure rushing"},
}

# How many of the last N games must contain a pattern for it to count as
# "established". Keep this aligned with the pattern_decay_service bar for
# ACTIVE — we don't want the Mirror to flag something the rest of the
# system hasn't decided is a real pattern yet.
_RECENT_WINDOW = 15
_ESTABLISHED_MIN_OCCURRENCES = 3


def _pattern_voice(pattern: str, form: str = "verb") -> str:
    entry = _PATTERN_VOICE.get(pattern)
    if entry:
        return entry.get(form) or entry.get("verb") or pattern.replace("_", " ")
    # Fallback for unmapped patterns — use the raw tag, readable form.
    readable = pattern.replace("_", " ")
    return readable


async def _load_game_analysis(db, user_id: str, game_id: str) -> Dict:
    """Fetch the one game-analysis doc we need, returning the bits used by
    the mirror + the home-page UI (gaps, accuracy, critical fen, total_moves).
    Returns {} when nothing usable.
    """
    if not game_id:
        return {}
    doc = await db.game_analyses.find_one(
        {"user_id": user_id, "game_id": game_id},
        {
            "_id": 0,
            "stockfish_analysis.move_evaluations": 1,
            "stockfish_analysis.accuracy": 1,
        },
    )
    if not doc:
        return {}
    sf = doc.get("stockfish_analysis") or {}
    moves = sf.get("move_evaluations") or []
    if not moves:
        return {"accuracy": sf.get("accuracy"), "total_moves": 0}

    gaps = sorted({m.get("cognitive_gap") for m in moves if m.get("cognitive_gap")})
    # Critical position = fen_before of the move with the largest cp_loss
    # (mate sentinels excluded).
    critical_fen = None
    worst_cp = 0
    for m in moves:
        cp = m.get("cp_loss")
        if cp is None:
            continue
        cp_abs = abs(cp)
        if cp_abs > 3000:  # mate sentinel — skip
            continue
        if cp_abs > worst_cp:
            worst_cp = cp_abs
            critical_fen = m.get("fen_before")

    return {
        "gaps": gaps,
        "accuracy": sf.get("accuracy"),
        "total_moves": len(moves),
        "critical_fen": critical_fen,
    }


async def _established_patterns(db, user_id: str) -> Tuple[List[str], int]:
    """Identify the user's currently-established patterns: those that
    appeared in at least _ESTABLISHED_MIN_OCCURRENCES of the most recent
    _RECENT_WINDOW analyzed games (excluding the one being evaluated).

    Returns (patterns, sample_size). patterns is ordered most-frequent-first.
    Empty list means "not enough signal yet".
    """
    cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "created_at": 1},
    ).sort("created_at", -1).limit(_RECENT_WINDOW)
    games = await cursor.to_list(_RECENT_WINDOW)
    if not games:
        return [], 0

    game_ids = [g.get("game_id") for g in games if g.get("game_id")]
    if not game_ids:
        return [], 0

    counter: Counter = Counter()
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        distinct_gaps = {m.get("cognitive_gap") for m in moves if m.get("cognitive_gap")}
        for g in distinct_gaps:
            counter[g] += 1

    established = [p for p, c in counter.most_common() if c >= _ESTABLISHED_MIN_OCCURRENCES]
    return established, len(game_ids)


async def _find_latest_game(db, user_id: str) -> Optional[Dict]:
    """Return the most recent analyzed imported game for this user. Only
    analyzed games qualify — we can't mirror what we haven't measured.
    """
    g = await db.games.find_one(
        {"user_id": user_id, "is_analyzed": True},
        {
            "_id": 0,
            "game_id": 1,
            "result": 1,
            "user_color": 1,
            "opponent": 1,
            "opening": 1,
            "created_at": 1,
            "imported_at": 1,
        },
        sort=[("imported_at", -1)],
    )
    return g


async def _find_window_games(db, user_id: str, since) -> List[Dict]:
    """Return analyzed imported games imported strictly AFTER `since`.
    Newest first. This is the set the Mirror will aggregate over.

    `imported_at` is stored as an ISO-string in `db.games`, so we
    serialize the threshold to ISO before querying. UTC ISO-8601 sorts
    lexicographically the same way it does temporally.
    """
    from datetime import datetime
    if isinstance(since, datetime):
        since_str = since.isoformat()
    else:
        since_str = str(since)
    cursor = db.games.find(
        {
            "user_id": user_id,
            "is_analyzed": True,
            "imported_at": {"$gt": since_str},
        },
        {
            "_id": 0,
            "game_id": 1,
            "result": 1,
            "user_color": 1,
            "opponent": 1,
            "opening": 1,
            "created_at": 1,
            "imported_at": 1,
            "move_time_stats": 1,
        },
    ).sort("imported_at", -1)
    games = await cursor.to_list(50)
    return games


def _time_discipline_line(games_data: List[Dict]) -> str:
    """Build a coach-voice "you rushed" / "you took your time" line from
    move-time stats across the window. Honest gating: returns "" when
    too few games carry timing data, or when no signal is strong enough
    to mention.
    """
    timed = [g for g in games_data if g.get("move_time_stats")]
    if not timed:
        return ""

    rushed = [g for g in timed if g["move_time_stats"].get("rushed_critical")]
    took_time = [g for g in timed if g["move_time_stats"].get("took_time_critical")]

    n_timed = len(timed)
    n_rushed = len(rushed)
    n_took = len(took_time)

    if n_timed == 1:
        # Single-game line — tie to the actual move.
        st = timed[0]["move_time_stats"]
        t = st.get("critical_move_time_s")
        med = st.get("median_user_move_s")
        mn = st.get("critical_move_number")
        if st.get("rushed_critical") and t is not None and med:
            return (
                f"And you spent {t}s on the critical move (move {mn}) — "
                f"fast even for you (your median is {med}s)."
            )
        if st.get("took_time_critical") and t is not None and med:
            return (
                f"You actually thought on the critical move ({t}s on move {mn}, "
                f"vs your usual {med}s)."
            )
        return ""

    # Aggregate across N games.
    if n_rushed >= 2 and n_rushed >= n_timed - 1:
        return f"You rushed the critical move in {n_rushed} of {n_timed}."
    if n_took >= 2 and n_took >= n_timed - 1:
        return f"You took your time on critical moves in {n_took} of {n_timed} — that's discipline."
    return ""


def _result_word(result: str, user_color: str) -> str:
    r = (result or "").strip()
    uc = (user_color or "white").lower()
    if "1/2" in r:
        return "drew"
    if r == "1-0":
        return "won" if uc == "white" else "lost"
    if r == "0-1":
        return "won" if uc == "black" else "lost"
    return ""


def _compose_verdict(
    outcome: str,
    game_gaps: List[str],
    established: List[str],
    sample_size: int,
) -> Dict[str, str]:
    """Compose the coach-voice mirror verdict. Returns:
        { "tone": <tag>, "headline": <one line>, "detail": <optional second> }
    Tone tags: repeated, broke_pattern, clean, no_profile_yet.
    """
    if not established:
        # Not enough data to say anything honest about patterns.
        return {
            "tone": "no_profile_yet",
            "headline": (
                f"Still reading your game. Play a few more and I'll "
                f"start spotting your patterns."
            ),
            "detail": "",
        }

    repeated = [p for p in established if p in game_gaps]
    broke = [p for p in established if p not in game_gaps]

    if repeated:
        first = _pattern_voice(repeated[0])
        extras = ""
        if len(repeated) > 1:
            second = _pattern_voice(repeated[1])
            extras = f" Also {second}."
        if outcome == "won":
            headline = f"You won — but you {first} again."
            detail = (
                "Opponent didn't capitalize this time." + extras
            ).strip()
        elif outcome == "lost":
            headline = f"You lost, and it was your usual — you {first}."
            detail = extras.strip()
        elif outcome == "drew":
            headline = f"Drew it — but you {first} again."
            detail = extras.strip()
        else:
            headline = f"You {first} again."
            detail = extras.strip()
        return {"tone": "repeated", "headline": headline, "detail": detail}

    # Clean vs established patterns.
    if broke:
        first = _pattern_voice(broke[0], form="noun")
        if outcome == "won":
            headline = f"Clean win. No {first} this time."
        elif outcome == "lost":
            headline = f"You lost — but you broke pattern. No {first}."
        elif outcome == "drew":
            headline = f"Drew it cleanly. No {first}."
        else:
            headline = f"Pattern-free game. No {first}."
        return {"tone": "broke_pattern", "headline": headline, "detail": ""}

    return {
        "tone": "clean",
        "headline": "Clean game. No repeat patterns.",
        "detail": "",
    }


def _aggregate_verdict(
    games_data: List[Dict],
    established: List[str],
    last_snapshot: Optional[Dict],
) -> Dict[str, str]:
    """Compose a coach-voice verdict for a multi-game window.

    games_data: per-game [{outcome, gaps}], newest first.
    established: patterns currently flagged as recurring across the user's
                 broader history.
    last_snapshot: the most recent CLOSED window (if any), used for the
                 "you listened" comparison.
    """
    n = len(games_data)
    wins = sum(1 for g in games_data if g["outcome"] == "won")
    losses = sum(1 for g in games_data if g["outcome"] == "lost")
    draws = sum(1 for g in games_data if g["outcome"] == "drew")
    score = f"{wins}-{losses}-{draws}"

    # Patterns that recurred in this window.
    repeated_count: Dict[str, int] = {p: 0 for p in established}
    for g in games_data:
        for gap in g["gaps"]:
            if gap in repeated_count:
                repeated_count[gap] += 1
    repeated = [(p, c) for p, c in repeated_count.items() if c > 0]
    repeated.sort(key=lambda x: -x[1])

    # No established patterns → don't mirror, just say honest.
    if not established:
        return {
            "tone": "no_profile_yet",
            "headline": (
                f"Across {n} games: {score}. Still reading your patterns — "
                f"play a few more and I'll have your profile."
            ),
            "detail": "",
            "listening": "",
        }

    # Listening signal: did patterns flagged last time disappear?
    listening = ""
    if last_snapshot:
        prev_flagged = set(last_snapshot.get("patterns_flagged") or [])
        now_repeated = {p for p, _ in repeated}
        improved = prev_flagged - now_repeated
        persisted = prev_flagged & now_repeated
        if prev_flagged and improved and not persisted:
            voice = _pattern_voice(next(iter(improved)), form="noun")
            listening = (
                f"Last session was {voice}. {n} new games, none. You listened."
            )
        elif persisted:
            voice = _pattern_voice(next(iter(persisted)))
            listening = (
                f"Same {voice} pattern as last session. Still happening."
            )

    if not repeated:
        # Clean window across all established patterns.
        headline = f"Across {n} games: {score}. No repeated patterns."
        detail = "This is what growth looks like."
        return {"tone": "broke_pattern", "headline": headline,
                "detail": detail, "listening": listening}

    # Mixed or all-repeated window.
    top_pattern, top_count = repeated[0]
    voice_verb = _pattern_voice(top_pattern, form="verb")

    if top_count == n:
        headline = f"Across {n} games: {score}. You {voice_verb} in all of them."
        detail = "Same old."
    else:
        headline = (
            f"Across {n} games: {score}. You {voice_verb} in {top_count} of {n}."
        )
        clean = n - top_count
        if clean == 1:
            detail = "One was clean — that's the outlier."
        else:
            detail = f"{clean} were clean — partial progress."

    if len(repeated) > 1:
        second_pattern, _ = repeated[1]
        detail = f"{detail} Also {_pattern_voice(second_pattern)}."

    return {
        "tone": "repeated",
        "headline": headline,
        "detail": detail,
        "listening": listening,
    }


async def build_game_mirror(db, user_id: str) -> Optional[Dict]:
    """Window-aware Mirror.

    Behavior:
      • Window = analyzed imported games imported AFTER the user's
        stored `mirror_window.opened_at` (capped at WINDOW_MAX_HOURS).
      • 0 games in window → return None (don't render anything).
      • 1 game → per-game voice (existing behavior).
      • 2+ games → aggregate voice ("across N games: W-L-D, you X in K
        of N, ...") + a "you listened" line when the previous closed
        window flagged a pattern that disappeared this window.

    Returns shape compatible with HomePage's `last_session` slot, plus
    extras (`window_size`, `game_ids`, `opened_at`) so the Lab session
    panel can scope to the same games.
    """
    from services.mirror_engagement import (
        get_window_open_floor,
        latest_snapshot,
    )

    floor = await get_window_open_floor(db, user_id)
    games = await _find_window_games(db, user_id, floor)
    if not games:
        return None

    # Pull analyses once. Build per-game records.
    games_data: List[Dict] = []
    union_gaps: set = set()
    for g in games:
        gid = g.get("game_id")
        analysis = await _load_game_analysis(db, user_id, gid)
        gaps = analysis.get("gaps") or []
        union_gaps.update(gaps)
        outcome = _result_word(g.get("result"), g.get("user_color"))
        games_data.append({
            "game_id": gid,
            "result": g.get("result"),
            "user_color": (g.get("user_color") or "white").lower(),
            "opponent": g.get("opponent"),
            "opening": g.get("opening"),
            "outcome": outcome,
            "gaps": gaps,
            "critical_fen": analysis.get("critical_fen"),
            "accuracy": analysis.get("accuracy"),
            "total_moves": analysis.get("total_moves"),
            "move_time_stats": g.get("move_time_stats"),
        })

    established, sample_size = await _established_patterns(db, user_id)

    # Compose verdict — single-game uses old voice, multi-game uses aggregate.
    if len(games_data) == 1:
        g0 = games_data[0]
        verdict = _compose_verdict(g0["outcome"], g0["gaps"], established, sample_size)
        verdict["listening"] = ""  # single-game has no listening line
    else:
        prev = await latest_snapshot(db, user_id)
        verdict = _aggregate_verdict(games_data, established, prev)

    # Story = headline + detail + listening + time discipline, joined.
    parts = [verdict.get("headline") or ""]
    if verdict.get("detail"):
        parts.append(verdict["detail"])
    if verdict.get("listening"):
        parts.append(verdict["listening"])
    time_line = _time_discipline_line(games_data)
    if time_line:
        parts.append(time_line)
    story = " ".join(p for p in parts if p).strip()

    # Pick the "worst" game for the board thumb — highest critical cp_loss
    # is too granular here; just use newest with a critical_fen.
    thumb_game = next((g for g in games_data if g.get("critical_fen")), games_data[0])

    # Patterns that actually repeated this window — for snapshot when
    # the window closes (engagement endpoint reads this).
    repeated_now = sorted({
        p for p in established
        if any(p in g["gaps"] for g in games_data)
    })

    return {
        # Backward-compat last_session shape (HomePage reads these):
        "game_id": thumb_game.get("game_id"),
        "result": thumb_game.get("result"),
        "user_color": thumb_game.get("user_color"),
        "opponent": thumb_game.get("opponent"),
        "opening": thumb_game.get("opening"),
        "critical_fen": thumb_game.get("critical_fen"),
        "accuracy": thumb_game.get("accuracy"),
        "total_moves": thumb_game.get("total_moves"),
        "story": story,
        # Window context:
        "window_size": len(games_data),
        "game_ids": [g["game_id"] for g in games_data],
        "opened_at": floor.isoformat() if hasattr(floor, "isoformat") else str(floor),
        "outcomes": {
            "won": sum(1 for g in games_data if g["outcome"] == "won"),
            "lost": sum(1 for g in games_data if g["outcome"] == "lost"),
            "drawn": sum(1 for g in games_data if g["outcome"] == "drew"),
        },
        "patterns_repeated": repeated_now,
        "mirror": {
            **verdict,
            "established_patterns": established,
            "sample_size": sample_size,
        },
    }
