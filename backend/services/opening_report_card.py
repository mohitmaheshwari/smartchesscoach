"""
Per-User Opening Report Card
============================

Aggregates a user's games by canonical opening + color, computing:
  - games played
  - wins / losses / draws
  - win rate
  - average accuracy

Then identifies the ONE problem opening — the family where the user is
both playing frequently AND losing consistently. Returns coach-voice
copy for surfacing on the Lab page.

Key principle: facts only. If "you're losing 73% of Italian games as
white" isn't literally true in the data, we don't say it.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List

from services.opening_normalizer import normalize_opening

logger = logging.getLogger(__name__)

# Minimum game count before we'll flag an opening as a "problem." Below
# this we don't have enough signal to call it out — small samples produce
# misleading win rates.
MIN_GAMES_FOR_INSIGHT = 3


def _derive_outcome(result: str, user_color: str) -> str:
    """Return 'win' / 'loss' / 'draw' from PGN result + user_color."""
    r = (result or "").strip()
    uc = (user_color or "white").lower()
    if "1/2" in r:
        return "draw"
    if r == "1-0":
        return "win" if uc == "white" else "loss"
    if r == "0-1":
        return "win" if uc == "black" else "loss"
    return "unknown"


async def get_user_opening_report(db, user_id: str) -> Dict:
    """
    Scan all analyzed games for `user_id` and build an opening report.

    Returns dict:
      has_data: bool
      total_games: int
      as_white: {canonical_name: {games, wins, losses, draws, win_rate, accuracy_avg}}
      as_black: same
      problem_opening: {
        name, color, games, wins, losses, win_rate, accuracy_avg,
        headline, subline, training_weakness
      } | None
      all_openings_flat: [per-entry records, sorted by games desc]
    """
    empty = {
        "has_data": False,
        "total_games": 0,
        "as_white": {},
        "as_black": {},
        "problem_opening": None,
        "all_openings_flat": [],
    }

    # Pull games
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "opening": 1, "result": 1, "user_color": 1},
    ).to_list(1000)
    if not games:
        return empty

    # Pull accuracy per game from game_analyses (cheap — just accuracy field)
    game_ids = [g.get("game_id") for g in games if g.get("game_id")]
    acc_map: Dict[str, float] = {}
    try:
        async for a in db.game_analyses.find(
            {"user_id": user_id, "game_id": {"$in": game_ids}},
            {"_id": 0, "game_id": 1, "stockfish_analysis.accuracy": 1},
        ):
            sf = a.get("stockfish_analysis") or {}
            acc = sf.get("accuracy")
            if acc is not None:
                acc_map[a["game_id"]] = float(acc)
    except Exception as e:
        logger.debug(f"accuracy lookup failed: {e}")

    # Aggregate by (color, opening_family)
    by_color: Dict[str, Dict[str, Dict]] = {"white": defaultdict(lambda: _blank_bucket()),
                                            "black": defaultdict(lambda: _blank_bucket())}

    for g in games:
        color = (g.get("user_color") or "white").lower()
        if color not in ("white", "black"):
            continue
        family = normalize_opening(g.get("opening"))
        outcome = _derive_outcome(g.get("result"), color)

        bucket = by_color[color][family]
        bucket["games"] += 1
        if outcome == "win":
            bucket["wins"] += 1
        elif outcome == "loss":
            bucket["losses"] += 1
        elif outcome == "draw":
            bucket["draws"] += 1
        accuracy = acc_map.get(g.get("game_id"))
        if accuracy is not None:
            bucket["_acc_total"] += accuracy
            bucket["_acc_count"] += 1

    # Finalize each bucket
    def _finalize(buckets: Dict[str, Dict]) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for name, b in buckets.items():
            games_ct = b["games"]
            win_rate = (b["wins"] / games_ct) if games_ct > 0 else 0.0
            avg_acc = (b["_acc_total"] / b["_acc_count"]) if b["_acc_count"] > 0 else None
            out[name] = {
                "games": games_ct,
                "wins": b["wins"],
                "losses": b["losses"],
                "draws": b["draws"],
                "win_rate": round(win_rate, 3),
                "accuracy_avg": round(avg_acc, 1) if avg_acc is not None else None,
            }
        return out

    as_white = _finalize(by_color["white"])
    as_black = _finalize(by_color["black"])

    # Build a flat list and identify the problem opening
    flat: List[Dict] = []
    for color, openings_map in (("white", as_white), ("black", as_black)):
        for name, stats in openings_map.items():
            if name == "Other":
                continue  # don't flag "Other" — not actionable
            entry = {"name": name, "color": color, **stats}
            flat.append(entry)

    flat.sort(key=lambda e: -e["games"])

    # Problem opening: the entry with the highest (games * loss_rate) where
    # games >= MIN_GAMES_FOR_INSIGHT. Multiplicative ranking means a frequent
    # opening with a bad record outranks a rare one with a terrible record.
    eligible = [
        e for e in flat
        if e["games"] >= MIN_GAMES_FOR_INSIGHT
        and e["win_rate"] < 0.5  # losing or near-50/50
    ]

    problem = None
    if eligible:
        eligible.sort(key=lambda e: -(e["games"] * (1.0 - e["win_rate"])))
        top = eligible[0]
        loss_pct = int(round((1.0 - top["win_rate"]) * 100))
        times_word = "time" if top["games"] == 1 else "times"
        headline = (
            f"You're losing {loss_pct}% of your {top['name']} games as {top['color']}."
        )
        subline_parts = [
            f"{top['games']} {times_word} played",
            f"{top['wins']} wins",
        ]
        if top.get("accuracy_avg") is not None:
            subline_parts.append(f"avg accuracy {top['accuracy_avg']}%")
        subline = ", ".join(subline_parts) + "."
        problem = {
            **top,
            "headline": headline,
            "subline": subline,
            # Route to opening_knowledge training — the most relevant gap.
            "training_weakness": "opening_knowledge",
        }

    return {
        "has_data": bool(flat),
        "total_games": len(games),
        "as_white": as_white,
        "as_black": as_black,
        "problem_opening": problem,
        "all_openings_flat": flat,
    }


def _blank_bucket() -> Dict:
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "_acc_total": 0.0,
        "_acc_count": 0,
    }
