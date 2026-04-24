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
        },
        sort=[("created_at", -1)],
    )
    return g


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


async def build_game_mirror(db, user_id: str) -> Optional[Dict]:
    """Top-level: return the Mirror verdict for the user's latest
    analyzed game, shaped to drop into `last_session` on the home page.
    Returns None if there is nothing to mirror.

    Shape (matches what HomePage.jsx's Evidence section reads):
        {
          game_id, result, story,
          critical_fen, accuracy, total_moves,
          opponent, opening,
          mirror: { tone, headline, detail, game_gaps,
                    established_patterns, sample_size }
        }
    """
    latest = await _find_latest_game(db, user_id)
    if not latest:
        return None

    game_id = latest.get("game_id")
    user_color = (latest.get("user_color") or "white").lower()
    outcome = _result_word(latest.get("result"), user_color)

    analysis = await _load_game_analysis(db, user_id, game_id)
    game_gaps = analysis.get("gaps") or []
    established, sample_size = await _established_patterns(db, user_id)

    verdict = _compose_verdict(outcome, game_gaps, established, sample_size)

    # Merge headline + detail into `story` for the UI (the slot renders
    # italic, single-block text). Keep the `mirror` object attached so
    # callers that want the raw pieces can still read them.
    story = verdict["headline"]
    if verdict.get("detail"):
        story = f"{story} {verdict['detail']}"

    return {
        "game_id": game_id,
        "result": latest.get("result"),
        "user_color": user_color,
        "opponent": latest.get("opponent"),
        "opening": latest.get("opening"),
        "critical_fen": analysis.get("critical_fen"),
        "accuracy": analysis.get("accuracy"),
        "total_moves": analysis.get("total_moves"),
        "story": story,
        "mirror": {
            **verdict,
            "game_gaps": game_gaps,
            "established_patterns": established,
            "sample_size": sample_size,
        },
    }
