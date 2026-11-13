"""Plan outcomes: the evidence a "+200 if you follow it" claim needs.

Mohit, 2026-11-13: "until I create a very good plan and prove this can get you
+200 if you follow it, and then track if they are following the plan... that's
the product". For every player with a plan week: per week, the step, its
Sunday verdict, how much of the week's work he did (plan_activity), how many
games he played and his real rating that week (the median of his game ratings,
services/rating_resolver), against his rating before the plan started.

Read-only, admin only. It reports; it never decides anything for a player.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

BASELINE_GAMES = 10


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _median_rating(games: List[Dict[str, Any]]) -> Optional[int]:
    from services.rating_resolver import get_game_user_rating

    vals = [int(r) for r in (get_game_user_rating(dict(g)) for g in games) if r]
    return int(statistics.median(vals)) if vals else None


async def player_outcome(db, user_id: str) -> Optional[Dict[str, Any]]:
    weeks = await db.player_plan_weeks.find({"user_id": user_id}, {"_id": 0}).sort("week_start", 1).to_list(200)
    if not weeks:
        return None
    first = datetime.fromisoformat(weeks[0]["week_start"]).replace(tzinfo=timezone.utc)
    fields = {"_id": 0, "game_id": 1, "played_at_utc": 1, "user_color": 1, "white_rating": 1, "black_rating": 1,
              "user_rating": 1, "user_rating_at_time": 1, "pgn": 1}
    before = await db.games.find({"user_id": user_id, "played_at_utc": {"$lt": first}}, fields
                                 ).sort("played_at_utc", -1).limit(BASELINE_GAMES).to_list(BASELINE_GAMES)
    since = await db.games.find({"user_id": user_id, "played_at_utc": {"$gte": first}}, fields).to_list(2000)
    activity: Dict[str, Dict[str, int]] = {}
    async for a in db.plan_activity.find({"user_id": user_id}, {"_id": 0, "week_start": 1, "action": 1}):
        w = activity.setdefault(a["week_start"], {"learn": 0, "find": 0, "play": 0})
        w[a["action"]] = w.get(a["action"], 0) + 1
    baseline = _median_rating(before)
    rows = []
    for w in weeks:
        start = datetime.fromisoformat(w["week_start"]).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=7)
        in_week = [g for g in since if (t := _when(g.get("played_at_utc"))) and start <= t < end]
        rating = _median_rating(in_week)
        work = activity.get(w["week_start"], {"learn": 0, "find": 0, "play": 0})
        rows.append({
            "week_start": w["week_start"],
            "step": (w.get("step") or {}).get("title"),
            "step_key": w.get("step_key"),
            "verdict_on_last_week": (w.get("verdict") or {}).get("status"),
            "work": work,
            "did_work": bool(work.get("learn") or work.get("find") or work.get("play")),
            "games": len(in_week),
            "rating": rating,
            "change": (rating - baseline) if (rating is not None and baseline is not None) else None,
        })
    latest = next((r for r in reversed(rows) if r["rating"] is not None), None)
    return {
        "user_id": user_id,
        "baseline_rating": baseline,
        "weeks": rows,
        "weeks_on_plan": len(rows),
        "weeks_with_work": sum(r["did_work"] for r in rows),
        "change_now": latest["change"] if latest else None,
    }


async def all_outcomes(db) -> Dict[str, Any]:
    users = await db.player_plan_weeks.distinct("user_id")
    players = [o for o in [await player_outcome(db, u) for u in users] if o]
    followed = [p["change_now"] for p in players if p["change_now"] is not None and p["weeks_with_work"] >= max(1, p["weeks_on_plan"] // 2)]
    not_followed = [p["change_now"] for p in players if p["change_now"] is not None and p["weeks_with_work"] < max(1, p["weeks_on_plan"] // 2)]
    return {
        "players": sorted(players, key=lambda p: -(p["weeks_with_work"])),
        "summary": {
            "players": len(players),
            "followed": len(followed),
            "followed_median_change": statistics.median(followed) if followed else None,
            "not_followed": len(not_followed),
            "not_followed_median_change": statistics.median(not_followed) if not_followed else None,
        },
    }
