"""Today's tasks: the daily coach plan (docs/daily_coach_plan_scope.md).

Each day a player gets a short list, fixed when the day starts:
  fix       - this week's plan work from his own games (or his last game)
  new       - one new thing a day, never one already done: a tactic idea from
              the Lichess ladder (data/daily_themes.json), a trap his own games
              reach, or an opening / endgame lesson at his level
  look_back - one position on an idea he learned a few days ago
  play      - games at the clock that suits him, or the lesson's position

The long list is stored; the size he picks (short / normal / long) is how many
of its tasks are shown, so changing size never reshuffles the day. A task is
done when its proof exists: puzzles solved on its topic today, games played at
its clock today, or the page opened. Fix ticks are written to the weekly plan's
own record (plan_activity), so the plan card and the day card never disagree.

Pure functions take everything they need; the async functions read and write.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

COLLECTION = "daily_plans"
SIZES = {"short": 2, "normal": 3, "long": 4}
DEFAULT_SIZE = "normal"
DEFAULT_TZ = "Asia/Kolkata"

# Provisional until measured on the coach-pages players (scope, open question 1).
THEME_PUZZLES = 6
# Days after an idea is learned that it comes back as a look back (open question 3).
LOOK_BACK_DAYS = (3, 10)
CLOCK_GAMES = 2

# A theme is offered only where Lichess has plenty of its puzzles inside the
# player's own puzzle window (topic_practice_themes.rating_window), so the
# task never runs dry, and only where its typical puzzle is not far below him
# (scope, open question 2: the start of the ladder is provisional).
MIN_THEME_SUPPLY = 200
THEME_FLOOR_BELOW = 400

DATA = Path(__file__).resolve().parent.parent / "data"
_SUPPLY: Dict[str, Dict[int, int]] = {}
_TREE: Dict[str, dict] = {}
_TC = re.compile(r'\[TimeControl "(\d+)\+(\d+)"\]')

LESSON_KINDS = ("opening", "endgame", "trap_set")
LESSON_WORDS = {
    "opening": "An opening lesson at your level.",
    "endgame": "An endgame lesson at your level.",
    "trap_set": "Traps in an opening at your level.",
}
TRAP_WORDS = {
    "caught": "This trap has caught you before. Learn the line so you see it coming.",
    "waiting": "Your games reach this trap. Learn it before an opponent uses it on you.",
    "could_set": "Your games reach this trap. Learn the line and set it.",
}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def theme_supply() -> Dict[str, Dict[int, int]]:
    """theme -> {100-point rating bucket: puzzles}, counted over all of
    lichess_puzzles (data/daily_theme_supply.json)."""
    if not _SUPPLY:
        raw = json.loads((DATA / "daily_theme_supply.json").read_text(encoding="utf-8"))
        for theme, buckets in raw.get("supply", raw).items():
            if isinstance(buckets, dict):
                _SUPPLY[theme] = {int(b): int(n) for b, n in buckets.items()}
    return _SUPPLY


def supply_in_window(theme: str, low: int, high: int) -> int:
    return sum(n for b, n in theme_supply().get(theme, {}).items() if b + 99 >= low and b <= high)


def skill_tree() -> Dict[str, dict]:
    if not _TREE:
        raw = json.loads((DATA / "coaching" / "skill_tree.json").read_text(encoding="utf-8"))["skills"]
        _TREE.update({k: v for k, v in raw.items() if isinstance(v, dict)})
    return _TREE


# --------------------------------------------------------------------------
# Day and time zone
# --------------------------------------------------------------------------
def zone(tz_name: Optional[str]):
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(str(tz_name or DEFAULT_TZ))
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def local_day(now: datetime, tz) -> date:
    return now.astimezone(tz).date()


def day_bounds_utc(day: date, tz) -> Tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def week_days(day: date) -> List[date]:
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


# --------------------------------------------------------------------------
# Candidates for "new"
# --------------------------------------------------------------------------
def theme_candidates(rating: Optional[int], done_ids: set) -> List[Dict[str, Any]]:
    from services.topic_practice_themes import daily_themes, rating_window

    low, high = rating_window(rating)
    level = rating or 1200
    out = []
    for row in daily_themes().values():
        item_id = f"theme:{row['key']}"
        if item_id in done_ids or row["median"] < level - THEME_FLOOR_BELOW:
            continue
        if supply_in_window(row["theme"], low, high) < MIN_THEME_SUPPLY:
            continue
        out.append({
            "id": item_id, "kind": "theme", "title": row["title"], "text": row["idea"],
            "action": "puzzles", "topic": f"theme-{row['key']}", "count": THEME_PUZZLES,
            "url": f"/training/theme/theme-{row['key']}?count={THEME_PUZZLES}&from=today",
        })
    return out


def trap_candidates(traps: Optional[Mapping[str, Sequence[Mapping[str, Any]]]], done_ids: set) -> List[Dict[str, Any]]:
    out = []
    for case in ("caught", "waiting", "could_set"):
        for t in (traps or {}).get(case) or ():
            item_id = f"trap:{t.get('key')}"
            url = t.get("school_url") or t.get("practice_url")
            if not t.get("key") or not url or item_id in done_ids or any(o["id"] == item_id for o in out):
                continue
            out.append({"id": item_id, "kind": "trap", "title": f"A trap: {t.get('name')}",
                        "text": TRAP_WORDS[case], "action": "open", "url": url,
                        "practice_url": t.get("practice_url")})
    return out


def lesson_candidates(rating: Optional[int], done_ids: set) -> List[Dict[str, Any]]:
    from services.today_composer import _action_for_band

    level = rating or 1200
    out = []
    for skill_id, node in skill_tree().items():
        kind = node.get("kind")
        item_id = f"lesson:{skill_id}"
        if kind not in LESSON_KINDS or item_id in done_ids:
            continue
        if not (int(node.get("rating_min") or 0) <= level <= int(node.get("rating_max") or 9999)):
            continue
        href = _action_for_band("intermediate", {"kind": kind, "content_ref": node.get("content_ref") or "",
                                                 "skill_id": skill_id})["href"]
        out.append({"id": item_id, "kind": "lesson", "title": node.get("label") or skill_id,
                    "text": LESSON_WORDS[kind], "action": "open", "url": href,
                    "tier": node.get("tier") or 0})
    out.sort(key=lambda o: o["tier"])
    return out


def pick_new(rating: Optional[int], traps, done_ids: set, yesterday_kind: Optional[str]) -> Optional[Dict[str, Any]]:
    """One new item. Kinds take turns: never the same kind two days running
    while another kind has something to offer."""
    pools = {
        "theme": theme_candidates(rating, done_ids),
        "trap": trap_candidates(traps, done_ids),
        "lesson": lesson_candidates(rating, done_ids),
    }
    order = ["theme", "trap", "lesson"]
    if yesterday_kind in order:
        order.remove(yesterday_kind)
        order.append(yesterday_kind)
    for kind in order:
        if pools[kind]:
            return pools[kind][0]
    return None


# --------------------------------------------------------------------------
# The other tasks
# --------------------------------------------------------------------------
def pick_fix(file: Mapping[str, Any], week_done: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The next undone piece of this week's plan work, else the last game."""
    done = (week_done or {}).get("done") or {}
    for step in ((file.get("plan") or {}).get("steps") or []):
        work = step.get("work") or {}
        step_done = done.get(step.get("key")) or {}
        topic = step.get("title") or ""
        for item in work.get("find") or []:
            if item.get("ref") not in (step_done.get("find") or []):
                return {"id": f"fix:find:{item['ref']}", "kind": "fix", "action": "open",
                        "title": "Find the better move in one of your games.",
                        "text": f"This week's step: {topic[:1].lower() + topic[1:]}.",
                        "url": item.get("url"), "step_key": step.get("key"), "plan_action": "find",
                        "ref": item.get("ref")}
        for item in work.get("play") or []:
            if item.get("ref") not in (step_done.get("play") or []):
                return {"id": f"fix:play:{item['ref']}", "kind": "fix", "action": "play_position",
                        "title": "Play a position from your games.",
                        "text": f"Play it against your coach until the better move comes easily. This week's step: "
                                f"{topic[:1].lower() + topic[1:]}.",
                        "position": {k: item.get(k) for k in ("fen", "user_color", "source_game_id")},
                        "step_key": step.get("key"), "plan_action": "play", "ref": item.get("ref")}
    last = file.get("last_game") or {}
    if last.get("review_url") and not last.get("clean"):
        return {"id": f"fix:last:{last.get('game_id')}", "kind": "fix", "action": "open",
                "title": "Look at your last game at the move that decided it.",
                "text": "Find the better move before you look at the answer.", "url": last["review_url"]}
    return None


def pick_look_back(history: Sequence[Mapping[str, Any]], today: date) -> Optional[Dict[str, Any]]:
    """The most overdue idea learned LOOK_BACK_DAYS ago that has not had that
    look back yet. `history`: earlier day documents, any order."""
    learned: Dict[str, Tuple[date, Mapping[str, Any]]] = {}
    looks: Dict[str, int] = {}
    for doc in history:
        d = date.fromisoformat(doc["day"])
        for t in doc.get("tasks") or []:
            if not t.get("done_at"):
                continue
            if t.get("slot") == "new" and t.get("kind") in ("theme", "trap"):
                learned.setdefault(t["id"], (d, t))
            elif t.get("slot") == "look_back":
                looks[t.get("of")] = looks.get(t.get("of"), 0) + 1
    due = []
    for item_id, (d, t) in learned.items():
        n = looks.get(item_id, 0)
        if n < len(LOOK_BACK_DAYS) and (today - d).days >= LOOK_BACK_DAYS[n]:
            due.append(((today - d).days - LOOK_BACK_DAYS[n], d, t))
    if not due:
        return None
    _, d, t = max(due, key=lambda x: x[0])
    when = d.strftime("%A")
    if t["kind"] == "theme":
        return {"id": f"look:{t['id']}:{today.isoformat()}", "of": t["id"], "kind": "theme", "action": "puzzles",
                "title": f"Look back: {t['title'].lower()}.",
                "text": f"You learned this on {when}. One puzzle to show it stuck.",
                "topic": t["topic"], "count": 1, "url": f"/training/theme/{t['topic']}?count=1&from=today"}
    url = t.get("practice_url") or t.get("url")
    return {"id": f"look:{t['id']}:{today.isoformat()}", "of": t["id"], "kind": "trap", "action": "open",
            "title": f"Look back: {t['title'][:1].lower() + t['title'][1:]}.",
            "text": f"You learned it on {when}. Play it against your coach.", "url": url}


def pick_play(file: Mapping[str, Any], new: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    advice = file.get("clock_advice") or {}
    if advice.get("instead"):
        clock = advice["instead"]
        return {"id": f"play:clock:{clock}", "kind": "clock", "action": "games", "clock": clock,
                "count": CLOCK_GAMES, "title": f"Two games at {clock}.",
                "text": f"Your {clock} games go better than your {', '.join(advice.get('clocks') or [])} games."}
    if new and new.get("kind") == "trap" and new.get("practice_url"):
        return {"id": f"play:{new['id']}", "kind": "play", "action": "open", "url": new["practice_url"],
                "title": "Play today's trap against your coach.", "text": "Set it up and see it work on the board."}
    return {"id": "play:coach", "kind": "play", "action": "open", "url": "/play-with-coach",
            "title": "Play a game against your coach.", "text": "Use what you worked on today."}


def build_tasks(file: Mapping[str, Any], week_done: Mapping[str, Any], history: Sequence[Mapping[str, Any]],
                today: date) -> List[Dict[str, Any]]:
    """The long list for the day, in order: fix, new, look back, play."""
    done_ids = {t["id"] for doc in history for t in doc.get("tasks") or []
                if t.get("slot") == "new" and t.get("done_at")}
    newest = sorted(history, key=lambda d: d["day"])[-1:] if history else []
    yesterday_kind = next((t.get("kind") for d in newest for t in d.get("tasks") or [] if t.get("slot") == "new"), None)
    tasks: List[Dict[str, Any]] = []
    fix = pick_fix(file, week_done)
    if fix:
        tasks.append({**fix, "slot": "fix"})
    new = pick_new(file.get("rating"), file.get("traps"), done_ids, yesterday_kind)
    if new:
        tasks.append({**new, "slot": "new"})
    look = pick_look_back(history, today)
    if look:
        tasks.append({**look, "slot": "look_back"})
    tasks.append({**pick_play(file, new), "slot": "play"})
    return tasks


# --------------------------------------------------------------------------
# Done
# --------------------------------------------------------------------------
def clock_of(pgn: Any) -> Optional[str]:
    from services.play_advice import clock_name

    m = _TC.search(str(pgn or ""))
    return clock_name(int(m.group(1)), int(m.group(2))) if m else None


def apply_proofs(tasks: List[Dict[str, Any]], attempts_by_topic: Mapping[str, int],
                 clocks_today: Mapping[str, int], week_done: Mapping[str, Any], now: datetime) -> bool:
    """Ticks tasks whose proof now exists. Returns True when anything changed."""
    done = (week_done or {}).get("done") or {}
    changed = False
    for t in tasks:
        if t.get("done_at"):
            continue
        ok = False
        if t.get("action") == "puzzles":
            ok = attempts_by_topic.get(t.get("topic"), 0) >= int(t.get("count") or 1)
        elif t.get("action") == "games":
            ok = clocks_today.get(t.get("clock"), 0) >= int(t.get("count") or 1)
        elif t.get("slot") == "fix" and t.get("step_key"):
            ok = t.get("ref") in ((done.get(t["step_key"]) or {}).get(t.get("plan_action")) or [])
        if ok:
            t["done_at"] = now
            changed = True
    return changed


def shown(doc: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(doc.get("tasks") or [])[:SIZES.get(doc.get("size"), SIZES[DEFAULT_SIZE])]


def day_state(doc: Optional[Mapping[str, Any]]) -> str:
    if not doc:
        return "none"
    tasks = shown(doc)
    n = sum(1 for t in tasks if t.get("done_at"))
    return "done" if tasks and n == len(tasks) else "part" if n else "none"


# --------------------------------------------------------------------------
# Reading and writing
# --------------------------------------------------------------------------
async def _proofs(db, user_id: str, tasks: Sequence[Mapping[str, Any]], day: date, tz) -> Tuple[Dict[str, int], Dict[str, int]]:
    start, end = day_bounds_utc(day, tz)
    topics = [t["topic"] for t in tasks if t.get("action") == "puzzles" and not t.get("done_at")]
    attempts: Dict[str, int] = {}
    if topics:
        async for a in db.puzzle_attempts.find({"user_id": user_id, "topic": {"$in": topics}, "at": {"$gte": start, "$lt": end}},
                                               {"_id": 0, "topic": 1}):
            attempts[a["topic"]] = attempts.get(a["topic"], 0) + 1
    clocks: Dict[str, int] = {}
    if any(t.get("action") == "games" and not t.get("done_at") for t in tasks):
        async for g in db.games.find({"user_id": user_id, "played_at_utc": {"$gte": start, "$lt": end}},
                                     {"_id": 0, "pgn": 1}):
            c = clock_of(g.get("pgn"))
            if c:
                clocks[c] = clocks.get(c, 0) + 1
    return attempts, clocks


async def today(db, user_id: str, tz_name: Optional[str], now: Optional[datetime] = None,
                store: bool = True) -> Dict[str, Any]:
    """Today's plan, made on the first call of the day, with fresh ticks, and the week.

    `store=False` (a super-admin's view-as) shows the day without writing it:
    the player's own first visit fixes his day, in his own time zone."""
    from routes.home import coach_file_for
    from services import player_coach_file as pcf

    now = now or datetime.now(timezone.utc)
    tz = zone(tz_name)
    day = local_day(now, tz)
    file = await coach_file_for(user_id)
    if file.get("state") != "ready":
        return {"state": "building"}
    week_done = await pcf.week_activity(db, user_id, now=now)
    doc = await db[COLLECTION].find_one({"user_id": user_id, "day": day.isoformat()}, {"_id": 0})
    if not doc:
        history = await db[COLLECTION].find({"user_id": user_id, "day": {"$lt": day.isoformat()}},
                                            {"_id": 0, "day": 1, "size": 1, "tasks": 1}).sort("day", -1).limit(60).to_list(None)
        doc = {"user_id": user_id, "day": day.isoformat(), "tz": str(getattr(tz, "key", DEFAULT_TZ)),
               "size": (history[0].get("size") if history else None) or DEFAULT_SIZE,
               "tasks": build_tasks(file, week_done, history, day), "created_at": now}
        if store:
            await db[COLLECTION].update_one({"user_id": user_id, "day": doc["day"]}, {"$setOnInsert": doc}, upsert=True)
            doc = await db[COLLECTION].find_one({"user_id": user_id, "day": day.isoformat()}, {"_id": 0})
    attempts, clocks = await _proofs(db, user_id, doc["tasks"], day, tz)
    if apply_proofs(doc["tasks"], attempts, clocks, week_done, now) and store:
        await db[COLLECTION].update_one({"user_id": user_id, "day": doc["day"]}, {"$set": {"tasks": doc["tasks"]}})
    week = await db[COLLECTION].find({"user_id": user_id, "day": {"$in": [d.isoformat() for d in week_days(day)]}},
                                     {"_id": 0, "day": 1, "size": 1, "tasks": 1}).to_list(None)
    by_day = {w["day"]: w for w in week}
    by_day[doc["day"]] = doc
    return payload(doc, [(d, day_state(by_day.get(d.isoformat()))) for d in week_days(day)], day)


def payload(doc: Mapping[str, Any], week: Sequence[Tuple[date, str]], day: date) -> Dict[str, Any]:
    keep = ("id", "slot", "kind", "action", "title", "text", "url", "position", "count", "clock")
    tasks = [{**{k: t.get(k) for k in keep if t.get(k) is not None}, "done": bool(t.get("done_at"))} for t in shown(doc)]
    return {
        "state": "ready",
        "day": doc["day"],
        "size": doc.get("size") or DEFAULT_SIZE,
        "sizes": list(SIZES),
        "tasks": tasks,
        "all_done": bool(tasks) and all(t["done"] for t in tasks),
        "week": [{"day": d.isoformat(), "label": d.strftime("%a"), "state": s, "today": d == day} for d, s in week],
    }


async def tick(db, user_id: str, task_id: str, tz_name: Optional[str], now: Optional[datetime] = None) -> bool:
    """He opened a task that is done by opening (a game moment, a lesson, a
    position). Puzzle and game tasks tick only from their proof."""
    from services import player_coach_file as pcf

    now = now or datetime.now(timezone.utc)
    day = local_day(now, zone(tz_name)).isoformat()
    doc = await db[COLLECTION].find_one({"user_id": user_id, "day": day}, {"_id": 0, "tasks": 1})
    task = next((t for t in (doc or {}).get("tasks") or [] if t.get("id") == task_id), None)
    if not task or task.get("action") not in ("open", "play_position"):
        return False
    if task.get("step_key") and task.get("plan_action"):
        await pcf.record_activity(db, user_id, task["step_key"], task["plan_action"], task.get("ref") or "", now=now)
    if not task.get("done_at"):
        await db[COLLECTION].update_one({"user_id": user_id, "day": day, "tasks.id": task_id},
                                        {"$set": {"tasks.$.done_at": now}})
    return True


async def set_size(db, user_id: str, size: str, tz_name: Optional[str], now: Optional[datetime] = None) -> bool:
    if size not in SIZES:
        return False
    now = now or datetime.now(timezone.utc)
    day = local_day(now, zone(tz_name)).isoformat()
    res = await db[COLLECTION].update_one({"user_id": user_id, "day": day}, {"$set": {"size": size}})
    return res.matched_count == 1
