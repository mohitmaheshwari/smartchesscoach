"""The plan's week: which step he works on this week, and the Sunday verdict
on last week's step (kept -> the next step; not yet -> the same step again).

Mohit, 2026-11-13: "track if they are following the plan and make more
changes on new weaknesses, that's the product". The plan file is a cache
rebuilt after every game, so without this the week's step could change after
any game. This collection is STATE (one row per player per week), written once
per week by the first build of that week, never rebuilt.

Verdicts, each from his own games, no invented thresholds:
  - an OPENING step is checked exactly: we know every game in which he reached
    the line as that side. Kept = reached it in at least OPENING_MIN_REACHED
    games of the week and never played the habit move; not yet = played it;
    no chance = did not reach the line enough.
  - a HABIT step is checked since the step started, with the same test as
    Progress (player_coach_habit.change_state against his rate before the
    step): kept only when that test says "kept" or "better". One clean week is
    not proof (no count of chances exists for a habit).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

COLLECTION = "player_plan_weeks"
OPENING_MIN_REACHED = 2

VERDICT_WORDS = {
    "kept": "Last week's step: kept. On to the next one.",
    "not_yet": "Last week's step showed up again. One more week, with fresh positions.",
    "no_chance": "Last week your games did not give that step enough chances. Same step this week.",
}


def week_bounds(week_start: str) -> tuple:
    start = datetime.fromisoformat(week_start).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def opening_verdict(step_key: str, games_in_week: Sequence[Mapping[str, Any]],
                    first_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    """`step_key` = opening:<side>:<line>:<idea>. `first_rows`: game_id -> the
    first plies of its move_evaluations (move, fen_before, is_opponent_move)."""
    from services.player_coach_file import _idea, OPENING_LAST_MOVE

    _, side, line, idea = step_key.split(":", 3)
    reached = slipped = 0
    for g in games_in_week:
        if g.get("user_color") != side:
            continue
        rows = list(first_rows.get(g["game_id"]) or [])
        family = " ".join(str(r.get("move") or "") for r in rows[:2]).strip()
        if family != line:
            continue
        reached += 1
        for r in rows:
            fen = r.get("fen_before") or ""
            parts = fen.split()
            if r.get("is_opponent_move") or len(parts) < 6:
                continue
            try:
                if int(parts[5]) > OPENING_LAST_MOVE:
                    continue
            except ValueError:
                continue
            if _idea(str(r.get("move") or "")) == idea:
                slipped += 1
                break
    if slipped:
        status = "not_yet"
    elif reached >= OPENING_MIN_REACHED:
        status = "kept"
    else:
        status = "no_chance"
    return {"status": status, "measured": {"reached": reached, "slipped": slipped}}


def habit_verdict(step_key: str, started: Optional[datetime], baseline: Optional[Mapping[str, Any]],
                  games_since: Sequence[Mapping[str, Any]], observations: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    from services import coach_plan_service as cp
    from services.player_coach_habit import change_state

    qid = step_key.split(":", 1)[1]
    ids = {g["game_id"] for g in games_since}
    hits = {o["game_id"] for o in observations if o.get("game_id") in ids and cp.quality_id(o) == qid}
    rate = (baseline or {}).get("rate")
    state = change_state(len(hits), len(ids), rate, min_games=5, hits_then=(baseline or {}).get("hit_games"))
    status = "kept" if state in ("kept", "better") else ("no_chance" if state == "waiting" else "not_yet")
    return {"status": status, "measured": {"games_since": len(ids), "hit_games": len(hits), "rate_before": rate,
                                           "state": state}}


def decide(prev: Optional[Mapping[str, Any]], verdict: Optional[Mapping[str, Any]],
           steps: Sequence[Mapping[str, Any]], kept_keys: Iterable[str]) -> Optional[Mapping[str, Any]]:
    """This week's step: last week's again unless it was kept; otherwise the
    best-ranked step not already kept."""
    kept = set(kept_keys)
    if prev and verdict and verdict.get("status") != "kept":
        same = next((s for s in steps if s.get("key") == prev.get("step_key")), None)
        return same or prev.get("step")
    for s in steps:
        if s.get("key") and s["key"] not in kept and (not prev or s["key"] != prev.get("step_key")):
            return s
    return steps[0] if steps else None


def apply_week(plan: Optional[Dict[str, Any]], week_row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Put the week's step first in the plan, marked this week, and attach last
    week's verdict. The step stays fixed all week whatever the ranking does."""
    if not plan or not week_row.get("step"):
        return plan
    key = week_row["step_key"]
    steps = [s for s in plan["steps"] if s.get("key") != key]
    live = next((s for s in plan["steps"] if s.get("key") == key), None)
    week_step = dict(live or week_row["step"])
    for s in steps:
        s.pop("this_week", None)
    week_step["this_week"] = True
    plan = dict(plan)
    plan["steps"] = ([week_step] + steps)[:len(plan["steps"]) or 1]
    v = week_row.get("verdict")
    plan["last_week"] = ({"status": v["status"], "words": VERDICT_WORDS[v["status"]]} if v else None)
    return plan


# --------------------------------------------------------------------------
# reading and writing (one row per player per week; written once)
# --------------------------------------------------------------------------
def _games_in(games: Sequence[Mapping[str, Any]], start: datetime, end: datetime) -> List[Mapping[str, Any]]:
    return [g for g in games if g.get("is_analyzed") and (t := _when(g.get("played_at_utc"))) and start <= t < end]


def _verdict_for(prev: Mapping[str, Any], games: Sequence[Mapping[str, Any]],
                 first_rows: Mapping[str, Sequence[Mapping[str, Any]]],
                 observations: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    key = prev.get("step_key") or ""
    start, end = week_bounds(prev["week_start"])
    if key.startswith("opening:"):
        return opening_verdict(key, _games_in(games, start, end), first_rows)
    if key.startswith("habit:"):
        started = _when(prev.get("step_started")) or start
        return habit_verdict(key, started, prev.get("baseline"), _games_in(games, started, end), observations)
    return None


def build_row(user_id: str, week_start: str, plan: Optional[Mapping[str, Any]], prev: Optional[Mapping[str, Any]],
              history: Sequence[Mapping[str, Any]], games: Sequence[Mapping[str, Any]],
              first_rows: Mapping[str, Sequence[Mapping[str, Any]]], observations: Sequence[Mapping[str, Any]],
              habit_baseline: Optional[Mapping[str, Any]], now: datetime) -> Optional[Dict[str, Any]]:
    steps = list((plan or {}).get("steps") or [])
    if not steps:
        return None
    verdict = _verdict_for(prev, games, first_rows, observations) if prev else None
    kept = [h["step_key"] for h in history if (h.get("verdict_on_step") or {}).get("status") == "kept"]
    if verdict and verdict["status"] == "kept":
        kept.append(prev["step_key"])
    step = decide(prev, verdict, steps, kept)
    if not step:
        return None
    same = bool(prev and step.get("key") == prev.get("step_key"))
    return {
        "user_id": user_id, "week_start": week_start, "step_key": step.get("key"),
        "step": {k: v for k, v in step.items() if k != "this_week"},
        "step_started": (prev.get("step_started") if same else now),
        "baseline": (prev.get("baseline") if same else (habit_baseline if str(step.get("key", "")).startswith("habit:") else None)),
        "verdict": verdict,
        "previous_step_key": (prev or {}).get("step_key"),
        "created_at": now,
    }


async def ensure_week(db, user_id: str, week_start: str, plan, games, first_rows, observations,
                      habit_baseline, now: Optional[datetime] = None) -> Optional[Mapping[str, Any]]:
    now = now or datetime.now(timezone.utc)
    row = await db[COLLECTION].find_one({"user_id": user_id, "week_start": week_start}, {"_id": 0})
    if row:
        return row
    prev = await db[COLLECTION].find_one({"user_id": user_id, "week_start": {"$lt": week_start}}, {"_id": 0},
                                         sort=[("week_start", -1)])
    history = await db[COLLECTION].find({"user_id": user_id}, {"_id": 0, "step_key": 1, "verdict": 1,
                                                               "previous_step_key": 1}).to_list(200)
    history = [{"step_key": h.get("previous_step_key"), "verdict_on_step": h.get("verdict")} for h in history]
    new = build_row(user_id, week_start, plan, prev, history, games, first_rows, observations, habit_baseline, now)
    if not new:
        return None
    await db[COLLECTION].update_one({"user_id": user_id, "week_start": week_start}, {"$setOnInsert": new}, upsert=True)
    return await db[COLLECTION].find_one({"user_id": user_id, "week_start": week_start}, {"_id": 0})


def ensure_week_sync(db, user_id: str, week_start: str, plan, games, first_rows, observations,
                     habit_baseline, now: Optional[datetime] = None) -> Optional[Mapping[str, Any]]:
    now = now or datetime.now(timezone.utc)
    row = db[COLLECTION].find_one({"user_id": user_id, "week_start": week_start}, {"_id": 0})
    if row:
        return row
    prev = db[COLLECTION].find_one({"user_id": user_id, "week_start": {"$lt": week_start}}, {"_id": 0},
                                   sort=[("week_start", -1)])
    history = [{"step_key": h.get("previous_step_key"), "verdict_on_step": h.get("verdict")}
               for h in db[COLLECTION].find({"user_id": user_id}, {"_id": 0, "verdict": 1, "previous_step_key": 1})]
    new = build_row(user_id, week_start, plan, prev, history, games, first_rows, observations, habit_baseline, now)
    if not new:
        return None
    db[COLLECTION].update_one({"user_id": user_id, "week_start": week_start}, {"$setOnInsert": new}, upsert=True)
    return db[COLLECTION].find_one({"user_id": user_id, "week_start": week_start}, {"_id": 0})
