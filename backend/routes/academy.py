"""Academy pilot routes: staff pages, and the three links a family receives.

docs/academy_pilot_scope.md. The rules live in services/academy_service.py;
this file reads and writes Mongo and checks who may see what.

Two kinds of caller:

  * Staff -- an owner or coach of an academy, signed in. They see every batch
    and child of their academy, and nothing of any other academy.
  * A family -- no account. Each child carries three long random tokens: the
    consent link, the report link and the homework link. A token opens only
    its own page.

A child is a `users` document with no email and no password, made here. Its
Lichess or Chess.com username is written ONLY when the parent agrees; the
background sync imports for any user with a username, so nothing about the
child is fetched before consent. "Stop and delete" removes the username and
the child's games, analyses and reports.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import chess
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from routes.auth import User, get_current_user
from services import academy_service as svc
from services.account_deletion import delete_user_rows
from services import first_steps as fs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/academy", tags=["Academy"])
db = None


def set_db(database) -> None:
    global db
    db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _site() -> str:
    return (os.environ.get("FRONTEND_URL") or "https://chessguru.ai").rstrip("/")


def _clean(text: Any, limit: int = 80) -> str:
    return " ".join(str(text or "").split())[:limit]


def _username(text: Any) -> Optional[str]:
    value = _clean(text, 40)
    if not value:
        return None
    if not all(ch.isalnum() or ch in "-_" for ch in value):
        raise HTTPException(400, "A username has only letters, numbers, - and _.")
    return value


async def ensure_indexes(database) -> None:
    await database[svc.STAFF].create_index([("user_id", 1)])
    await database[svc.STAFF].create_index([("academy_id", 1), ("user_id", 1)], unique=True)
    await database[svc.BATCHES].create_index([("academy_id", 1)])
    await database[svc.STUDENTS].create_index([("batch_id", 1)])
    for token in ("consent_token", "report_token", "homework_token"):
        await database[svc.STUDENTS].create_index([(token, 1)], unique=True)
    await database[svc.WEEKS].create_index([("student_id", 1), ("week_start", 1)], unique=True)
    await database[svc.REPORTS].create_index([("student_id", 1), ("approved_at", -1)])
    await database[svc.ATTEMPTS].create_index([("student_id", 1), ("week_start", 1)])
    await database[svc.CLASS_GAMES].create_index([("batch_id", 1), ("created_at", -1)])
    for token in ("white_token", "black_token"):
        await database[svc.CLASS_GAMES].create_index([(token, 1)], unique=True)
    # Children added before classes existed have no class token until first use.
    await database[svc.STUDENTS].create_index(
        [("class_token", 1)], unique=True, partialFilterExpression={"class_token": {"$type": "string"}})
    await database[fs.SESSIONS].create_index([("session_id", 1)], unique=True)
    await database[fs.SESSIONS].create_index([("student_id", 1), ("started_at", 1)])


# ---------------------------------------------------------------------------
# access
# ---------------------------------------------------------------------------
def _is_admin(user: User) -> bool:
    return user.role in ("admin", "super_admin")


async def _role_in(user: User, academy_id: str) -> Optional[str]:
    row = await db[svc.STAFF].find_one({"academy_id": academy_id, "user_id": user.user_id},
                                       {"_id": 0, "role": 1})
    if row:
        return row["role"]
    return "admin" if _is_admin(user) else None


async def _academy_for(user: User, academy_id: str, owner_only: bool = False) -> Dict[str, Any]:
    academy = await db[svc.ACADEMIES].find_one({"academy_id": academy_id}, {"_id": 0})
    if not academy:
        raise HTTPException(404, "No such academy.")
    role = await _role_in(user, academy_id)
    if role is None or (owner_only and role not in ("owner", "admin")):
        raise HTTPException(403, "This academy is not yours.")
    academy["my_role"] = role
    return academy


async def _batch_for(user: User, batch_id: str) -> Dict[str, Any]:
    batch = await db[svc.BATCHES].find_one({"batch_id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(404, "No such batch.")
    batch["academy"] = await _academy_for(user, batch["academy_id"])
    return batch


async def _student_for(user: User, student_id: str) -> Dict[str, Any]:
    student = await db[svc.STUDENTS].find_one({"student_id": student_id, "deleted_at": None},
                                              {"_id": 0})
    if not student:
        raise HTTPException(404, "No such child.")
    student["academy"] = await _academy_for(user, student["academy_id"])
    return student


def _links(student: Dict[str, Any]) -> Dict[str, str]:
    site = _site()
    links = {
        "consent": f"{site}/consent/{student['consent_token']}",
        "report": f"{site}/r/{student['report_token']}",
        "homework": f"{site}/homework/{student['homework_token']}",
    }
    if student.get("class_token"):
        links["class"] = f"{site}/class/{student['class_token']}"
    return links


def _consent_message(student: Dict[str, Any], academy: Dict[str, Any]) -> str:
    return (f"Hello {student.get('parent_name') or ''}. {academy['name']} uses ChessGuru for "
            f"{student['display_name']}'s chess lessons and games, and to send you a short weekly "
            f"report. Please read and agree here: {_links(student)['consent']}").replace("  ", " ")


def _class_message(student: Dict[str, Any]) -> str:
    return (f"Hello {student.get('parent_name') or ''}. Here is {student['display_name']}'s chess class "
            f"on ChessGuru. Open it on a phone or tablet and let {student['display_name']} play: "
            f"{_links(student).get('class', '')}").replace("  ", " ")


def _report_message(student: Dict[str, Any], academy: Dict[str, Any], has_homework: bool = True) -> str:
    links = _links(student)
    text = f"{student['display_name']}'s chess week from {academy['name']}: {links['report']}"
    return f"{text} This week's homework: {links['homework']}" if has_homework else text


# ---------------------------------------------------------------------------
# weekly snapshot (background and on request of a coach)
# ---------------------------------------------------------------------------
async def _games_for_week(user_id: str, start) -> List[Dict[str, Any]]:
    from services.game_outcome import user_outcome
    begin, end = svc.week_bounds_utc(start)
    rows = await db.games.find(
        {"user_id": user_id, "played_at_utc": {"$gte": begin, "$lt": end}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at_utc": 1,
         "opponent_rating": 1, "user_rating": 1, "is_analyzed": 1},
    ).to_list(500)
    out = []
    for g in rows:
        played = g.get("played_at_utc")
        local = played.replace(tzinfo=timezone.utc).astimezone(svc.IST) if isinstance(played, datetime) else None
        out.append({**g, "outcome": user_outcome(g),
                    "played_at": played.isoformat() if isinstance(played, datetime) else "",
                    "played_day": local.date().isoformat() if local else None})
    return out


async def _observations(user_id: str, game_ids: List[str]) -> List[Dict[str, Any]]:
    if not game_ids:
        return []
    return await db.move_observations.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "ply": 1, "fen_before": 1, "move_uci": 1, "color": 1,
         "execution_quality": 1, "eval_before": 1, "eval_after": 1},
    ).to_list(20000)


async def _better_moves(habit: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """The engine's move at each evidence position, from that one game's stored
    analysis, kept only when it is itself safe. Background only: never on a
    family's or coach's page load (game_analyses documents are large)."""
    out: Dict[str, str] = {}
    for event in (habit or {}).get("evidence") or []:
        doc = await db.game_analyses.find_one(
            {"game_id": event["game_id"]},
            {"_id": 0, "stockfish_analysis.move_evaluations.fen_before": 1,
             "stockfish_analysis.move_evaluations.best_move_uci": 1})
        rows = ((doc or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        for row in rows:
            if row.get("fen_before") and row["fen_before"].split(" ")[:4] == event["fen"].split(" ")[:4]:
                safe = svc.safe_better_move(event["fen"], row.get("best_move_uci"))
                if safe:
                    out[f"{event['game_id']}:{event['ply']}"] = safe
                break
    return out


def _class_week(sessions: List[Dict[str, Any]], start, all_done: bool) -> Dict[str, Any]:
    """What this child did in class in the given IST week."""
    begin, end = svc.week_bounds_utc(start)
    learnt: List[str] = []
    practised: List[str] = []
    for s in sessions:
        if s.get("kind") != "class" or not s.get("finished_at"):
            continue
        when = datetime.fromisoformat(s["finished_at"]).astimezone(timezone.utc).replace(tzinfo=None)
        if not begin <= when < end:
            continue
        cls = fs.class_by_id(s["class_id"])
        title = cls["title"].lower()
        if s.get("passed") and not s.get("practice"):
            if cls["learnt"] not in learnt:
                learnt.append(cls["learnt"])
            if title in practised:
                practised.remove(title)
        elif title not in practised and cls["learnt"] not in learnt:
            practised.append(title)
    return {"learnt": learnt, "practised": practised, "all_done": all_done}


async def build_week(student: Dict[str, Any], start=None, with_plan: bool = True) -> Optional[Dict[str, Any]]:
    """Rebuild one child's week and store it. Returns the stored row.

    `with_plan=False` keeps the stored coach plan as it is: the plan runs the
    engine (about a minute and a half for one child on the shared server,
    measured 2026-11-09), so a coach's Refresh rebuilds the week at once and
    leaves the plan to a background task."""
    if (student.get("consent") or {}).get("status") != "given" or not student.get("child_user_id"):
        return None
    start = start or svc.week_start()
    uid = student["child_user_id"]
    games = await _games_for_week(uid, start)
    obs = await _observations(uid, [g["game_id"] for g in games])
    prev = await db[svc.WEEKS].find_one(
        {"student_id": student["student_id"], "week_start": (start - timedelta(days=7)).isoformat()},
        {"_id": 0})
    if prev is None:
        prev_games = await _games_for_week(uid, start - timedelta(days=7))
        prev_obs = await _observations(uid, [g["game_id"] for g in prev_games])
        prev = svc.summarise_week(prev_games, prev_obs)
    week = svc.summarise_week(games, obs, prev)
    week["better_moves"] = await _better_moves(week.get("habit"))
    sessions = await _sessions(student["student_id"])
    week["classes"] = _class_week(sessions, start, _overview(student, sessions)["all_done"])
    # A coach's confirmation survives the rebuild when the good moment is the
    # same move; a different move is a new moment and starts unconfirmed.
    old = await db[svc.WEEKS].find_one({"student_id": student["student_id"],
                                        "week_start": start.isoformat()},
                                       {"_id": 0, "good_moment": 1, "coach_plan": 1})
    # The coach plan (docs/coach_assistant_plan_scope.md). A failure here must
    # not stop the week the coach already relies on, so it keeps the old plan.
    try:
        from routes.academy_coach_plan import build_plan
        if with_plan:
            week["coach_plan"] = await build_plan(student, start, old, games)
        elif (old or {}).get("coach_plan"):
            week["coach_plan"] = old["coach_plan"]
    except Exception as exc:
        logger.error("coach plan build failed for %s: %s", student.get("student_id"), exc)
        if (old or {}).get("coach_plan"):
            week["coach_plan"] = old["coach_plan"]
    old_good, new_good = (old or {}).get("good_moment") or {}, week.get("good_moment")
    if new_good and old_good.get("confirmed_by_name") and \
            (old_good.get("fen"), old_good.get("move_uci")) == (new_good["fen"], new_good["move_uci"]):
        for key in ("confirmed_by_name", "confirmed_by", "confirmed_at"):
            new_good[key] = old_good.get(key)
    # A coach may approve while the engine was working; an approval stored in
    # the meantime wins over the draft computed before it.
    if (week.get("coach_plan") or {}).get("status") in ("draft", "none"):
        now_row = await db[svc.WEEKS].find_one({"student_id": student["student_id"],
                                                "week_start": start.isoformat()},
                                               {"_id": 0, "coach_plan": 1})
        if ((now_row or {}).get("coach_plan") or {}).get("status") in ("approved", "skipped"):
            week["coach_plan"] = now_row["coach_plan"]
    row = {**week, "student_id": student["student_id"], "week_start": start.isoformat(),
           "built_at": _now()}
    await db[svc.WEEKS].update_one({"student_id": student["student_id"],
                                    "week_start": start.isoformat()},
                                   {"$set": row}, upsert=True)
    return row


# The ordinary sync fetches 50 games a pass oldest-first and queues only the 3
# newest of each pass for analysis (journey_service.sync_user_games). That is
# right for an adult who opens the app; a child never does, so most of a busy
# week would stay unread. Academy children get their last two weeks queued
# here, below every ordinary job (the worker takes the highest priority first
# and ordinary syncs use 5..9), so no adult's analysis waits on a child's.
ACADEMY_QUEUE_PRIORITY = 3
BACKFILL_DAYS = 14
BACKFILL_MAX_GAMES = 40
SKIP_SPEEDS = ("bullet", "ultrabullet")


async def queue_unanalysed(user_id: str) -> int:
    since = datetime.utcnow() - timedelta(days=BACKFILL_DAYS)
    rows = await db.games.find(
        {"user_id": user_id, "played_at_utc": {"$gte": since}, "is_analyzed": {"$ne": True}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "time_control_category": 1,
         "analysis_status": 1},
    ).sort("played_at_utc", -1).to_list(BACKFILL_MAX_GAMES * 2)
    queued = 0
    for g in rows:
        if queued >= BACKFILL_MAX_GAMES:
            break
        if str(g.get("time_control_category") or "").lower() in SKIP_SPEEDS:
            continue
        if g.get("analysis_status") == "skipped" or not g.get("pgn"):
            continue
        await db.analysis_queue.update_one(
            {"game_id": g["game_id"], "user_id": user_id},
            {"$setOnInsert": {"game_id": g["game_id"], "user_id": user_id, "pgn": g["pgn"],
                              "user_color": g.get("user_color", "white"), "status": "pending",
                              "priority": ACADEMY_QUEUE_PRIORITY, "auto_synced": True,
                              "source": "academy_backfill",
                              "queued_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        queued += 1
    return queued


async def build_all_weeks() -> int:
    n = 0
    async for student in db[svc.STUDENTS].find({"deleted_at": None, "consent.status": "given"},
                                               {"_id": 0}):
        try:
            if student.get("child_user_id"):
                await queue_unanalysed(student["child_user_id"])
            if await build_week(student):
                n += 1
        except Exception as exc:  # one child's bad row must not stop the rest
            logger.error("academy week build failed for %s: %s", student.get("student_id"), exc)
    return n


async def academy_week_loop() -> None:
    await asyncio.sleep(240)
    while True:
        try:
            n = await build_all_weeks()
            logger.info("Academy weeks rebuilt for %d children", n)
        except Exception as exc:
            logger.error("Academy week loop error: %s", exc)
        await asyncio.sleep(2 * 3600)


async def _homework_status(student_id: str, start: str, has_homework: bool) -> str:
    if not has_homework:
        return "none"
    attempt = await db[svc.ATTEMPTS].find_one({"student_id": student_id, "week_start": start},
                                              {"_id": 0, "status": 1}, sort=[("started_at", -1)])
    return (attempt or {}).get("status") or "not_started"


# ---------------------------------------------------------------------------
# staff: academy, coaches, batches
# ---------------------------------------------------------------------------
@router.get("/me")
async def my_academies(user: User = Depends(get_current_user)):
    rows = await db[svc.STAFF].find({"user_id": user.user_id}, {"_id": 0}).to_list(50)
    ids = [r["academy_id"] for r in rows]
    roles = {r["academy_id"]: r["role"] for r in rows}
    academies = await db[svc.ACADEMIES].find({"academy_id": {"$in": ids}}, {"_id": 0}).to_list(50)
    out = []
    for a in academies:
        batches = await db[svc.BATCHES].find({"academy_id": a["academy_id"]}, {"_id": 0}).to_list(100)
        for b in batches:
            b["children"] = await db[svc.STUDENTS].count_documents(
                {"batch_id": b["batch_id"], "deleted_at": None})
        staff = await db[svc.STAFF].find({"academy_id": a["academy_id"]},
                                         {"_id": 0, "user_id": 1, "name": 1, "email": 1, "role": 1}).to_list(50)
        out.append({**a, "my_role": roles[a["academy_id"]], "batches": batches, "staff": staff})
    return {"academies": out}


@router.post("")
async def create_academy(payload: Dict[str, Any] = Body(...), user: User = Depends(get_current_user)):
    """An academy, or -- with kind "family" -- a parent's own home set-up.

    A family is the same shape with one batch called "Home": the parent is the
    owner and the coach, and agrees on the consent page for their own child.
    """
    family = payload.get("kind") == "family"
    name = _clean(payload.get("name")) or (f"{user.name}'s family" if family else "")
    if len(name) < 2:
        raise HTTPException(400, "Give the academy a name.")
    academy = {"academy_id": svc.new_id("acad"), "name": name, "city": _clean(payload.get("city"), 60),
               "kind": "family" if family else "academy",
               "owner_user_id": user.user_id, "created_at": _now()}
    await db[svc.ACADEMIES].insert_one(dict(academy))
    await db[svc.STAFF].insert_one({"academy_id": academy["academy_id"], "user_id": user.user_id,
                                    "name": user.name, "email": (user.email or "").lower(),
                                    "role": "owner", "added_at": _now()})
    if family:
        batch = {"batch_id": svc.new_id("batch"), "academy_id": academy["academy_id"], "name": "Home",
                 "coach_name": user.name, "created_by": user.user_id, "created_at": _now()}
        await db[svc.BATCHES].insert_one(dict(batch))
        academy["batch_id"] = batch["batch_id"]
    return academy


@router.post("/{academy_id}/coaches")
async def add_coach(academy_id: str, payload: Dict[str, Any] = Body(...),
                    user: User = Depends(get_current_user)):
    await _academy_for(user, academy_id, owner_only=True)
    email = _clean(payload.get("email"), 120).lower()
    if "@" not in email:
        raise HTTPException(400, "Enter the coach's email.")
    coach = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "name": 1, "email": 1})
    if not coach:
        raise HTTPException(404, "No ChessGuru account uses that email. Ask the coach to sign in once first.")
    await db[svc.STAFF].update_one(
        {"academy_id": academy_id, "user_id": coach["user_id"]},
        {"$setOnInsert": {"academy_id": academy_id, "user_id": coach["user_id"],
                          "name": coach.get("name"), "email": email, "role": "coach",
                          "added_at": _now()}},
        upsert=True)
    return {"ok": True, "user_id": coach["user_id"], "name": coach.get("name")}


@router.post("/{academy_id}/batches")
async def create_batch(academy_id: str, payload: Dict[str, Any] = Body(...),
                       user: User = Depends(get_current_user)):
    await _academy_for(user, academy_id)
    name = _clean(payload.get("name"))
    if len(name) < 2:
        raise HTTPException(400, "Give the batch a name.")
    batch = {"batch_id": svc.new_id("batch"), "academy_id": academy_id, "name": name,
             "coach_name": _clean(payload.get("coach_name")) or user.name,
             "created_by": user.user_id, "created_at": _now()}
    await db[svc.BATCHES].insert_one(dict(batch))
    return batch


# ---------------------------------------------------------------------------
# staff: children
# ---------------------------------------------------------------------------
@router.post("/batch/{batch_id}/students")
async def add_student(batch_id: str, payload: Dict[str, Any] = Body(...),
                      user: User = Depends(get_current_user)):
    batch = await _batch_for(user, batch_id)
    name = _clean(payload.get("display_name"), 40)
    if len(name) < 1:
        raise HTTPException(400, "Enter the child's first name.")
    phone = svc.normalise_phone(payload.get("parent_phone"))
    if not phone:
        raise HTTPException(400, "Enter the parent's WhatsApp number.")
    lichess = _username(payload.get("lichess_username"))
    chesscom = _username(payload.get("chesscom_username"))
    child_user_id = f"user_{os.urandom(6).hex()}"
    # A child account: no email, no password, so no login and no email job can
    # reach it. The usernames wait on the student row until the parent agrees.
    await db.users.insert_one({
        "user_id": child_user_id, "name": name, "role": "student",
        "academy_id": batch["academy_id"], "managed_by_academy": True,
        "email_opt_out": True, "email_notifications": False,
        "created_at": _now(),
    })
    student = {
        "student_id": svc.new_id("kid"), "academy_id": batch["academy_id"], "batch_id": batch_id,
        "display_name": name, "lichess_username": lichess, "chesscom_username": chesscom,
        "parent_name": _clean(payload.get("parent_name"), 60), "parent_phone": phone,
        "child_user_id": child_user_id,
        "consent": {"status": "pending", "text_version": svc.CONSENT_TEXT_VERSION},
        "consent_token": svc.new_token(), "report_token": svc.new_token(),
        "homework_token": svc.new_token(), "class_token": svc.new_token(),
        "created_by": user.user_id, "created_at": _now(), "deleted_at": None,
    }
    await db[svc.STUDENTS].insert_one(dict(student))
    return {"student_id": student["student_id"], "links": _links(student),
            "whatsapp": svc.whatsapp_link(phone, _consent_message(student, batch["academy"]))}


def _row_for_table(student, week, homework_status) -> Dict[str, Any]:
    habit = (week or {}).get("habit")
    habit_id = (habit or {}).get("id")
    games = int(((week or {}).get("games") or {}).get("count") or 0)
    analysed = int(((week or {}).get("games") or {}).get("analysed") or 0)
    if habit_id in svc.HABIT_WORDS:
        habit_words = svc.HABIT_WORDS[habit_id]["short"]
    elif not games:
        classes = (week or {}).get("classes") or {}
        habit_words = "In lessons" if classes.get("learnt") or classes.get("practised") else "No games this week"
    elif not analysed:
        habit_words = "Games still being read"
    else:
        habit_words = "Nothing stood out"
    return {
        "student_id": student["student_id"],
        "name": student["display_name"],
        "consent": (student.get("consent") or {}).get("status"),
        "habit": habit_words,
        "trend": (week or {}).get("trend") or "none",
        "trend_words": svc.TREND_WORDS.get((week or {}).get("trend") or "none"),
        "games_words": "None" if games == 0 else ("A few" if games < 5 else "Many"),
        "homework": homework_status,
        "homework_words": svc.HOMEWORK_WORDS.get(homework_status, homework_status),
        "needs_you": svc.needs_coach(student, week, homework_status),
        "plan": _plan_summary(week),
    }


def _plan_summary(week) -> Dict[str, Any]:
    from routes.academy_coach_plan import plan_summary
    return plan_summary(week)


@router.get("/batch/{batch_id}")
async def batch_view(batch_id: str, user: User = Depends(get_current_user)):
    batch = await _batch_for(user, batch_id)
    start = svc.week_start().isoformat()
    students = await db[svc.STUDENTS].find({"batch_id": batch_id, "deleted_at": None},
                                           {"_id": 0}).sort("display_name", 1).to_list(200)
    rows, weeks = [], []
    for s in students:
        week = await db[svc.WEEKS].find_one({"student_id": s["student_id"], "week_start": start},
                                            {"_id": 0, "better_moves": 0, "coach_plan.moments": 0})
        weeks.append(week)
        status = await _homework_status(s["student_id"], start, bool((week or {}).get("homework")))
        rows.append(_row_for_table(s, week, status))
    need = [r for r in rows if r["needs_you"]]
    if not rows:
        summary = "Add the first child to this batch."
    elif need:
        summary = (f"{svc.number_word(len(need))} "
                   f"{'child needs' if len(need) == 1 else 'children need'} you this week.")
    else:
        summary = "Every child is on track this week."
    return {"batch": {k: v for k, v in batch.items() if k != "academy"},
            "academy": {"academy_id": batch["academy"]["academy_id"], "name": batch["academy"]["name"],
                        "kind": batch["academy"].get("kind", "academy")},
            "week_start": start, "summary": summary, "topic": svc.class_topic(weeks), "rows": rows}


@router.get("/student/{student_id}")
async def student_view(student_id: str, user: User = Depends(get_current_user)):
    student = await _student_for(user, student_id)
    batch = await db[svc.BATCHES].find_one({"batch_id": student["batch_id"]}, {"_id": 0})
    start = svc.week_start().isoformat()
    week = await db[svc.WEEKS].find_one({"student_id": student_id, "week_start": start}, {"_id": 0})
    last = await db[svc.REPORTS].find_one({"student_id": student_id}, {"_id": 0, "payload": 0},
                                          sort=[("approved_at", -1)])
    status = await _homework_status(student_id, start, bool((week or {}).get("homework")))
    preview = None
    if week:
        preview = svc.render_report(week, child_name=student["display_name"],
                                    batch_name=(batch or {}).get("name", ""),
                                    coach_name=(batch or {}).get("coach_name", ""),
                                    better_moves=week.get("better_moves"))
        preview["blocked"] = svc.report_blocked(week)
    academy = student["academy"]
    await _class_token(student)
    first_steps = None
    if (student.get("consent") or {}).get("status") == "given":
        first_steps = await first_steps_for_staff(student)
    from routes.academy_coach_plan import coach_view
    return {
        "plan": await coach_view(student, week, start),
        "first_steps": first_steps,
        "whatsapp_class": svc.whatsapp_link(student["parent_phone"], _class_message(student)),
        "student": {k: student.get(k) for k in ("student_id", "display_name", "lichess_username",
                                                "chesscom_username", "parent_name", "parent_phone",
                                                "batch_id", "consent")},
        "batch": {"batch_id": student["batch_id"], "name": (batch or {}).get("name")},
        "academy": {"academy_id": academy["academy_id"], "name": academy["name"],
                    "kind": academy.get("kind", "academy")},
        "week_start": start, "week_built_at": (week or {}).get("built_at"),
        "row": _row_for_table(student, week, status),
        "preview": preview, "last_report": last, "links": _links(student),
        "whatsapp_consent": svc.whatsapp_link(student["parent_phone"], _consent_message(student, academy)),
    }


@router.post("/student/{student_id}/refresh")
async def refresh_student(student_id: str, user: User = Depends(get_current_user)):
    student = await _student_for(user, student_id)
    if (student.get("consent") or {}).get("status") != "given":
        raise HTTPException(409, "The parent has not agreed yet, so there is nothing to read.")
    row = await build_week(student, with_plan=False)
    _in_background(build_week(student))  # the coach plan needs the engine
    return {"ok": True, "built_at": (row or {}).get("built_at"), "plan_building": True}


@router.post("/student/{student_id}/report")
async def approve_report(student_id: str, payload: Dict[str, Any] = Body(default={}),
                         user: User = Depends(get_current_user)):
    student = await _student_for(user, student_id)
    batch = await db[svc.BATCHES].find_one({"batch_id": student["batch_id"]}, {"_id": 0}) or {}
    start = svc.week_start().isoformat()
    week = await db[svc.WEEKS].find_one({"student_id": student_id, "week_start": start}, {"_id": 0})
    if not week:
        raise HTTPException(409, "This week has not been read yet. Press Refresh first.")
    blocked = svc.report_blocked(week)
    if blocked:
        raise HTTPException(409, blocked)
    note = _clean(payload.get("coach_note"), 400)
    rendered = svc.render_report(week, child_name=student["display_name"],
                                 batch_name=batch.get("name", ""),
                                 coach_name=batch.get("coach_name", ""), coach_note=note,
                                 better_moves=week.get("better_moves"))
    report = {"report_id": svc.new_id("rep"), "student_id": student_id, "week_start": start,
              "payload": rendered, "coach_note": note, "approved_by": user.user_id,
              "approved_by_name": user.name, "approved_at": _now(), "opens": 0}
    await db[svc.REPORTS].insert_one(dict(report))
    return {"ok": True, "report_id": report["report_id"], "link": _links(student)["report"],
            "whatsapp": svc.whatsapp_link(student["parent_phone"],
                                          _report_message(student, student["academy"],
                                                          bool(week.get("homework"))))}


EVIDENCE = "academy_coach_evidence"


@router.post("/student/{student_id}/confirm-good-moment")
async def confirm_good_moment(student_id: str, payload: Dict[str, Any] = Body(default={}),
                              user: User = Depends(get_current_user)):
    """The coach says this week's good moment shows the child understands.

    Kept on the week (so the report says it, in the coach's name) and as its
    own evidence row, the same shape the lesson-evidence queue keeps, so the
    mastery work can read coach-approved real-game moves later. A rebuild of
    the week keeps the confirmation when the same move is still the good
    moment.
    """
    student = await _student_for(user, student_id)
    batch = await db[svc.BATCHES].find_one({"batch_id": student["batch_id"]}, {"_id": 0}) or {}
    start = svc.week_start().isoformat()
    week = await db[svc.WEEKS].find_one({"student_id": student_id, "week_start": start}, {"_id": 0})
    good = (week or {}).get("good_moment")
    if not good:
        raise HTTPException(409, "There is no good moment this week to confirm.")
    name = _clean(payload.get("coach_name"), 60) or batch.get("coach_name") or user.name
    confirmation = {"confirmed_by_name": name, "confirmed_by": user.user_id, "confirmed_at": _now()}
    await db[svc.WEEKS].update_one({"student_id": student_id, "week_start": start},
                                   {"$set": {f"good_moment.{k}": v for k, v in confirmation.items()}})
    await db[EVIDENCE].update_one(
        {"student_id": student_id, "fen": good["fen"], "move_uci": good["move_uci"]},
        {"$set": {"student_id": student_id, "child_user_id": student.get("child_user_id"),
                  "academy_id": student["academy_id"], "kind": good["kind"], "piece": good.get("piece"),
                  "fen": good["fen"], "move_uci": good["move_uci"], "game_id": good.get("game_id"),
                  "ply": good.get("ply"), "week_start": start, **confirmation}},
        upsert=True)
    return {"ok": True, "confirmed_by_name": name}


@router.post("/student/{student_id}/sent")
async def mark_sent(student_id: str, user: User = Depends(get_current_user)):
    """The coach pressed "Send on WhatsApp". We cannot see whether the message
    went, only that the button was pressed, and the record says exactly that."""
    await _student_for(user, student_id)
    last = await db[svc.REPORTS].find_one({"student_id": student_id}, {"_id": 0, "report_id": 1},
                                          sort=[("approved_at", -1)])
    if last:
        await db[svc.REPORTS].update_one({"report_id": last["report_id"]},
                                         {"$set": {"whatsapp_opened_at": _now()}})
    return {"ok": True}


@router.delete("/student/{student_id}")
async def remove_student(student_id: str, user: User = Depends(get_current_user)):
    student = await _student_for(user, student_id)
    await _delete_child_data(student, reason="removed_by_academy", by=user.user_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# family: consent
# ---------------------------------------------------------------------------
async def _student_by(field: str, token: str) -> Dict[str, Any]:
    if not token or len(token) < 16:
        raise HTTPException(404, "This link is not valid.")
    student = await db[svc.STUDENTS].find_one({field: token}, {"_id": 0})
    if not student:
        raise HTTPException(404, "This link is not valid.")
    return student


CONSENT_POINTS = [
    "If your child has an online chess account, we read the games they play there.",
    "If your child takes ChessGuru classes, we keep their answers, so the next class fits what they found hard.",
    "We use the games and answers to show your child's coach and you what to work on.",
    "We keep your child's first name, the chess account name and your phone number.",
    "We do not show your child to other people, and no one can message your child.",
    "You can stop at any time from the report. We then delete everything we hold about your child.",
]


@router.get("/consent/{token}")
async def consent_page(token: str):
    student = await _student_by("consent_token", token)
    academy = await db[svc.ACADEMIES].find_one({"academy_id": student["academy_id"]}, {"_id": 0}) or {}
    if student.get("deleted_at"):
        return {"status": "deleted", "academy": academy.get("name")}
    return {"status": (student.get("consent") or {}).get("status"), "academy": academy.get("name"),
            "child_name": student["display_name"],
            "accounts": [x for x in (student.get("lichess_username") and f"Lichess: {student['lichess_username']}",
                                     student.get("chesscom_username") and f"Chess.com: {student['chesscom_username']}") if x],
            "points": CONSENT_POINTS, "text_version": svc.CONSENT_TEXT_VERSION}


@router.post("/consent/{token}")
async def give_consent(token: str, request: Request, payload: Dict[str, Any] = Body(...)):
    student = await _student_by("consent_token", token)
    if student.get("deleted_at"):
        raise HTTPException(410, "This child was removed. Ask the academy for a new link.")
    if payload.get("agree") is not True:
        raise HTTPException(400, "Tick the box to agree.")
    by = _clean(payload.get("parent_name"), 60)
    if len(by) < 2:
        raise HTTPException(400, "Enter your name.")
    if not payload.get("is_parent"):
        raise HTTPException(400, "Only a parent or guardian can agree.")
    consent = {"status": "given", "given_by_name": by, "given_at": _now(),
               "text_version": svc.CONSENT_TEXT_VERSION,
               "user_agent": _clean(request.headers.get("user-agent"), 200)}
    await db[svc.STUDENTS].update_one({"student_id": student["student_id"]},
                                      {"$set": {"consent": consent}})
    update = {k: v for k, v in (("lichess_username", student.get("lichess_username")),
                                ("chess_com_username", student.get("chesscom_username"))) if v}
    if update:
        # Start the import at the beginning of last week, not three months
        # back: the report and the trend need these two weeks, and the
        # ordinary first sync would spend its passes on August.
        start = datetime.combine(svc.week_start() - timedelta(days=7), datetime.min.time(),
                                 tzinfo=svc.IST)
        update["last_game_sync"] = start.astimezone(timezone.utc).isoformat()
        await db.users.update_one({"user_id": student["child_user_id"]}, {"$set": update})
        _in_background(_first_sync(student["child_user_id"]))
    return {"ok": True, "status": "given"}


_BACKGROUND: set = set()


def _in_background(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND.add(task)  # the loop keeps only a weak reference to a task
    task.add_done_callback(_BACKGROUND.discard)


async def _first_sync(user_id: str) -> None:
    """Import the child's games now rather than at the next scheduled sync, so
    the coach sees a week the same day the parent agrees."""
    try:
        from journey_service import sync_user_games
        doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if doc:
            await sync_user_games(db, user_id, doc)
            await queue_unanalysed(user_id)
    except Exception as exc:
        logger.error("first sync for academy child %s failed: %s", user_id, exc)


async def _delete_child_data(student: Dict[str, Any], *, reason: str, by: str) -> None:
    """Everything keyed to the child goes, not only the games.

    The consent page promises deletion. Profiles, pattern rows, scores and
    notifications are all derived from the games and all carry the child's
    user_id, which belongs to this child alone (made here, never shared), so
    every collection is swept for it. What stays is a row with no personal
    detail, so a link that is opened later can say the child has gone.
    """
    uid = student.get("child_user_id")
    if uid:
        await delete_user_rows(db, uid, keep={svc.ACADEMIES, svc.STAFF, svc.BATCHES, svc.STUDENTS})
    for coll in (svc.WEEKS, svc.REPORTS, svc.ATTEMPTS, EVIDENCE, fs.SESSIONS):
        await db[coll].delete_many({"student_id": student["student_id"]})
    for side in ("white_student_id", "black_student_id"):
        await db[svc.CLASS_GAMES].delete_many({side: student["student_id"]})
    await db[svc.STUDENTS].update_one(
        {"student_id": student["student_id"]},
        {"$set": {"deleted_at": _now(), "deleted_reason": reason, "deleted_by": by,
                  "consent.status": "withdrawn", "display_name": "", "lichess_username": None,
                  "chesscom_username": None, "parent_phone": None, "parent_name": None},
         "$unset": {"first_steps": "", "consent.given_by_name": "", "consent.user_agent": ""}})


@router.post("/consent/{token}/withdraw")
async def withdraw_consent(token: str):
    student = await _student_by("consent_token", token)
    if not student.get("deleted_at"):
        await _delete_child_data(student, reason="parent_withdrew", by="parent")
    return {"ok": True, "status": "deleted"}


# ---------------------------------------------------------------------------
# family: report
# ---------------------------------------------------------------------------
@router.get("/report/{token}")
async def report_page(token: str):
    student = await _student_by("report_token", token)
    if student.get("deleted_at"):
        return {"status": "deleted"}
    report = await db[svc.REPORTS].find_one({"student_id": student["student_id"]}, {"_id": 0},
                                            sort=[("approved_at", -1)])
    academy = await db[svc.ACADEMIES].find_one({"academy_id": student["academy_id"]},
                                               {"_id": 0, "name": 1}) or {}
    if not report:
        return {"status": "none", "child_name": student["display_name"], "academy": academy.get("name"),
                "stop_link": f"{_site()}/consent/{student['consent_token']}"}
    await db[svc.REPORTS].update_one({"report_id": report["report_id"]},
                                     {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now()},
                                      "$min": {"first_opened_at": _now()}})
    return {"status": "ready", "academy": academy.get("name"), "week_start": report["week_start"],
            "report": report["payload"],
            "homework_link": _links(student)["homework"] if await _has_homework(student, report) else None,
            "stop_link": f"{_site()}/consent/{student['consent_token']}"}


async def _has_homework(student: Dict[str, Any], report: Dict[str, Any]) -> bool:
    week = await db[svc.WEEKS].find_one({"student_id": student["student_id"],
                                         "week_start": report.get("week_start")},
                                        {"_id": 0, "homework": 1})
    return bool((week or {}).get("homework"))


# ---------------------------------------------------------------------------
# family: homework (Win it back)
# ---------------------------------------------------------------------------
def homework_opponent(rating: int):
    """The engine at the real opponent's strength.

    CoachOpponent floors its strength at COACH_MIN_RATING because in Play with
    Coach the coach must punish every mistake. Homework is the opposite case:
    the child replays a game against someone of the real opponent's strength,
    so the floor is taken back off here, for this use only.
    """
    from coach_play.coach_opponent import (CoachOpponent, rating_to_skill_level,
                                           rating_to_uci_elo, _pwc_coach_uci_elo_enabled)
    opponent = CoachOpponent(user_rating=rating)
    opponent.skill_level = rating_to_skill_level(rating)
    opponent.uci_elo = rating_to_uci_elo(rating) if _pwc_coach_uci_elo_enabled() else None
    return opponent


async def _homework_context(token: str):
    student = await _student_by("homework_token", token)
    if student.get("deleted_at"):
        raise HTTPException(410, "This link has been stopped.")
    start = svc.week_start().isoformat()
    week = await db[svc.WEEKS].find_one({"student_id": student["student_id"], "week_start": start},
                                        {"_id": 0, "homework": 1})
    homework = (week or {}).get("homework")
    if not homework:
        # Last week's homework stays playable until a new one exists.
        week = await db[svc.WEEKS].find_one({"student_id": student["student_id"],
                                             "homework": {"$ne": None}},
                                            {"_id": 0, "homework": 1, "week_start": 1},
                                            sort=[("week_start", -1)])
        homework = (week or {}).get("homework")
        start = (week or {}).get("week_start") or start
    return student, homework, start


def _attempt_view(attempt: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not attempt:
        return None
    return {"attempt_id": attempt["attempt_id"], "fen": attempt["fen"], "status": attempt["status"],
            "moves": attempt.get("moves", []),
            "result_words": svc.HOMEWORK_RESULT_WORDS.get(attempt["status"])}


@router.get("/homework/{token}")
async def homework_page(token: str):
    student, homework, start = await _homework_context(token)
    if not homework:
        return {"status": "none", "child_name": student["display_name"]}
    attempt = await db[svc.ATTEMPTS].find_one({"student_id": student["student_id"], "week_start": start},
                                              {"_id": 0}, sort=[("started_at", -1)])
    return {"status": "ready", "child_name": student["display_name"], "fen": homework["fen"],
            "color": homework["color"], "attempt": _attempt_view(attempt),
            "lines": ["You were winning here. Then one move let it slip.",
                      "Play it again. Try to win it back."]}


@router.post("/homework/{token}/start")
async def homework_start(token: str):
    student, homework, start = await _homework_context(token)
    if not homework:
        raise HTTPException(404, "There is no homework yet.")
    attempt = {"attempt_id": svc.new_id("try"), "student_id": student["student_id"],
               "week_start": start, "start_fen": homework["fen"], "fen": homework["fen"],
               "color": homework["color"],
               "opponent_rating": int(homework.get("opponent_rating") or 1200),
               "moves": [], "status": "playing", "started_at": _now()}
    await db[svc.ATTEMPTS].insert_one(dict(attempt))
    return _attempt_view(attempt)


async def _finish(attempt: Dict[str, Any], board: chess.Board) -> str:
    pawns = None
    if not board.is_game_over():
        try:
            pawns, mate = await homework_opponent(attempt["opponent_rating"]).get_evaluation(board.fen())
            if mate is not None:
                pawns = 99.0 if mate > 0 else -99.0
        except Exception as exc:
            logger.error("homework evaluation failed: %s", exc)
    return svc.homework_verdict(board, attempt["color"], pawns)


@router.post("/homework/{token}/move")
async def homework_move(token: str, payload: Dict[str, Any] = Body(...)):
    student, _, _ = await _homework_context(token)
    attempt = await db[svc.ATTEMPTS].find_one({"attempt_id": payload.get("attempt_id"),
                                               "student_id": student["student_id"]}, {"_id": 0})
    if not attempt or attempt["status"] != "playing":
        raise HTTPException(409, "Start a new try first.")
    board = chess.Board(attempt["fen"])
    child = chess.WHITE if attempt["color"] == "white" else chess.BLACK
    if board.turn != child:
        raise HTTPException(409, "Wait for the other side to move.")
    try:
        move = chess.Move.from_uci(str(payload.get("uci") or ""))
    except ValueError:
        raise HTTPException(400, "That is not a move.")
    if move not in board.legal_moves:
        promo = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
        if promo in board.legal_moves:
            move = promo
        else:
            raise HTTPException(400, "That move is not allowed here.")
    moves = list(attempt.get("moves") or [])
    moves.append({"by": "child", "uci": move.uci(), "san": board.san(move)})
    board.push(move)
    reply = None
    child_moves = sum(1 for m in moves if m["by"] == "child")
    if not board.is_game_over() and child_moves < svc.HOMEWORK_MAX_CHILD_MOVES:
        san = await homework_opponent(attempt["opponent_rating"]).get_move(
            board.fen(), [m["uci"] for m in moves])
        if san:
            reply_move = board.parse_san(san)
            reply = {"by": "engine", "uci": reply_move.uci(), "san": san}
            moves.append(reply)
            board.push(reply_move)
    status = "playing"
    if board.is_game_over() or child_moves >= svc.HOMEWORK_MAX_CHILD_MOVES:
        status = await _finish(attempt, board)
    update = {"fen": board.fen(), "moves": moves, "status": status, "updated_at": _now()}
    if status != "playing":
        update["finished_at"] = _now()
    await db[svc.ATTEMPTS].update_one({"attempt_id": attempt["attempt_id"]}, {"$set": update})
    return {**_attempt_view({**attempt, **update}), "reply": reply}


# ---------------------------------------------------------------------------
# class games: two children of one batch play each other on the site
# ---------------------------------------------------------------------------
# No clocks, no chat, no strangers: a coach pairs two children of the same
# batch and each gets a link. Every move is saved as it is played, so a game
# survives a deploy. A finished game is written to each child's `games` like
# an imported game and queued for analysis, so it reaches the weekly report.
def _class_view(game: Dict[str, Any], color: Optional[str] = None) -> Dict[str, Any]:
    board = chess.Board(game["fen"])
    moves = game.get("moves") or []
    out = {
        "class_game_id": game["class_game_id"], "fen": game["fen"],
        "moves": [m["san"] for m in moves], "ply": len(moves),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "status": game["status"], "status_words": svc.CLASS_STATUS_WORDS.get(game["status"]),
        "white_name": game["white_name"], "black_name": game["black_name"],
        "last_move": moves[-1]["uci"] if moves else None,
    }
    if color:
        out["my_color"] = color
        out["opponent_name"] = game["black_name"] if color == "white" else game["white_name"]
        out["result_words"] = svc.class_result_words(game.get("outcome"), color)
    return out


@router.post("/batch/{batch_id}/class-games")
async def create_class_game(batch_id: str, payload: Dict[str, Any] = Body(...),
                            user: User = Depends(get_current_user)):
    batch = await _batch_for(user, batch_id)
    white_id, black_id = payload.get("white_student_id"), payload.get("black_student_id")
    if not white_id or not black_id or white_id == black_id:
        raise HTTPException(400, "Pick two different children.")
    sides = {}
    for color, sid in (("white", white_id), ("black", black_id)):
        s = await db[svc.STUDENTS].find_one({"student_id": sid, "batch_id": batch_id, "deleted_at": None},
                                            {"_id": 0})
        if not s:
            raise HTTPException(404, "Both children must be in this batch.")
        if (s.get("consent") or {}).get("status") != "given":
            raise HTTPException(409, f"{s['display_name']}'s parent has not agreed yet.")
        sides[color] = s
    game = {"class_game_id": svc.new_id("cg"), "academy_id": batch["academy_id"], "batch_id": batch_id,
            "white_student_id": white_id, "black_student_id": black_id,
            "white_name": sides["white"]["display_name"], "black_name": sides["black"]["display_name"],
            "white_token": svc.new_token(), "black_token": svc.new_token(),
            "fen": chess.STARTING_FEN, "moves": [], "status": "playing",
            "created_by": user.user_id, "created_at": _now(), "updated_at": _now()}
    await db[svc.CLASS_GAMES].insert_one(dict(game))
    site = _site()
    links = {c: f"{site}/play/{game[c + '_token']}" for c in ("white", "black")}
    whatsapp = {}
    for c in ("white", "black"):
        other = game["black_name"] if c == "white" else game["white_name"]
        whatsapp[c] = svc.whatsapp_link(
            sides[c].get("parent_phone"),
            f"{sides[c]['display_name']} has a class game against {other}: {links[c]}")
    return {"class_game_id": game["class_game_id"], "links": links, "whatsapp": whatsapp}


@router.get("/batch/{batch_id}/class-games")
async def list_class_games(batch_id: str, user: User = Depends(get_current_user)):
    await _batch_for(user, batch_id)
    rows = await db[svc.CLASS_GAMES].find({"batch_id": batch_id}, {"_id": 0}).sort(
        "created_at", -1).to_list(20)
    site = _site()
    return {"games": [{**_class_view(g),
                       "links": {c: f"{site}/play/{g[c + '_token']}" for c in ("white", "black")}}
                      for g in rows]}


async def _class_game_by(token: str):
    if not token or len(token) < 16:
        raise HTTPException(404, "This link is not valid.")
    for color in ("white", "black"):
        game = await db[svc.CLASS_GAMES].find_one({f"{color}_token": token}, {"_id": 0})
        if game:
            return game, color
    raise HTTPException(404, "This link is not valid.")


async def _store_class_game(game: Dict[str, Any]) -> None:
    """Write the finished game to each child's games and queue it for analysis."""
    played = datetime.now(timezone.utc)
    sans = [m["san"] for m in game.get("moves") or []]
    if len(sans) < 2:
        return
    result = (game.get("outcome") or {}).get("result", "*")
    pgn = svc.class_game_pgn(game["white_name"], game["black_name"], sans, result, played,
                             "ChessGuru class game")
    for color in ("white", "black"):
        student = await db[svc.STUDENTS].find_one({"student_id": game[f"{color}_student_id"],
                                                   "deleted_at": None}, {"_id": 0})
        if not student or (student.get("consent") or {}).get("status") != "given":
            continue
        uid = student["child_user_id"]
        game_id = f"class_{game['class_game_id']}_{color}"
        opponent = game["black_name"] if color == "white" else game["white_name"]
        await db.games.update_one({"game_id": game_id}, {"$setOnInsert": {
            "game_id": game_id, "user_id": uid, "platform": "chessguru", "pgn": pgn,
            "user_color": color, "result": result, "opponent_name": opponent, "opponent": opponent,
            "white_player": game["white_name"], "black_player": game["black_name"],
            "time_control": "untimed", "time_control_category": "classical",
            "played_at_utc": played.replace(tzinfo=None), "date_played": played.isoformat(),
            "imported_at": played.isoformat(), "is_analyzed": False, "analysis_status": "queued",
            "class_game_id": game["class_game_id"], "academy_id": game["academy_id"]}}, upsert=True)
        await db.analysis_queue.update_one({"game_id": game_id, "user_id": uid}, {"$setOnInsert": {
            "game_id": game_id, "user_id": uid, "pgn": pgn, "user_color": color, "status": "pending",
            "priority": ACADEMY_QUEUE_PRIORITY + 1, "auto_synced": True,
            "source": "academy_class_game", "queued_at": played.isoformat()}}, upsert=True)
        _in_background(_rebuild_week(student["student_id"]))


@router.get("/play/{token}")
async def class_game_page(token: str):
    game, color = await _class_game_by(token)
    return _class_view(game, color)


@router.post("/play/{token}/move")
async def class_game_move(token: str, payload: Dict[str, Any] = Body(...)):
    game, color = await _class_game_by(token)
    if game["status"] != "playing":
        raise HTTPException(409, "This game has ended.")
    board = chess.Board(game["fen"])
    if ("white" if board.turn == chess.WHITE else "black") != color:
        raise HTTPException(409, "Wait for the other side to move.")
    ply = len(game.get("moves") or [])
    if payload.get("ply") is not None and int(payload["ply"]) != ply:
        raise HTTPException(409, "The board changed. It has been refreshed.")
    try:
        move = chess.Move.from_uci(str(payload.get("uci") or ""))
    except ValueError:
        raise HTTPException(400, "That is not a move.")
    if move not in board.legal_moves:
        promo = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
        if promo not in board.legal_moves:
            raise HTTPException(400, "That move is not allowed here.")
        move = promo
    entry = {"uci": move.uci(), "san": board.san(move), "at": _now()}
    board.push(move)
    outcome = svc.class_game_outcome(board)
    update = {"fen": board.fen(), "updated_at": _now(),
              "status": outcome["status"] if outcome else "playing"}
    if outcome:
        update["outcome"] = outcome
        update["finished_at"] = _now()
    # Only one move per ply can land: the second of two racing taps matches
    # nothing and is told to refresh.
    res = await db[svc.CLASS_GAMES].update_one(
        {"class_game_id": game["class_game_id"], "fen": game["fen"]},
        {"$set": {**update, "moves": (game.get("moves") or []) + [entry]}})
    if getattr(res, "matched_count", 1) == 0:
        raise HTTPException(409, "The board changed. It has been refreshed.")
    game = await db[svc.CLASS_GAMES].find_one({"class_game_id": game["class_game_id"]}, {"_id": 0})
    if outcome:
        await _store_class_game(game)
    return _class_view(game, color)


@router.post("/play/{token}/resign")
async def class_game_resign(token: str):
    game, color = await _class_game_by(token)
    if game["status"] != "playing":
        raise HTTPException(409, "This game has ended.")
    outcome = svc.class_game_outcome(chess.Board(game["fen"]), resigned=color)
    await db[svc.CLASS_GAMES].update_one({"class_game_id": game["class_game_id"]},
                                         {"$set": {"status": outcome["status"], "outcome": outcome,
                                                   "finished_at": _now(), "updated_at": _now()}})
    game = await db[svc.CLASS_GAMES].find_one({"class_game_id": game["class_game_id"]}, {"_id": 0})
    await _store_class_game(game)
    return _class_view(game, color)


@router.post("/homework/{token}/stop")
async def homework_stop(token: str, payload: Dict[str, Any] = Body(...)):
    student, _, _ = await _homework_context(token)
    attempt = await db[svc.ATTEMPTS].find_one({"attempt_id": payload.get("attempt_id"),
                                               "student_id": student["student_id"]}, {"_id": 0})
    if not attempt or attempt["status"] != "playing":
        raise HTTPException(409, "This try has already ended.")
    status = await _finish(attempt, chess.Board(attempt["fen"]))
    await db[svc.ATTEMPTS].update_one({"attempt_id": attempt["attempt_id"]},
                                      {"$set": {"status": status, "finished_at": _now()}})
    return _attempt_view({**attempt, "status": status})


# ---------------------------------------------------------------------------
# family: first steps classes (docs/first_steps_scope.md)
# ---------------------------------------------------------------------------
# A child with no games learns the rules here, from the class link. Every tap
# is judged by services/first_steps.py on the server and kept as evidence on
# the class session, which carries the child's user_id so "Stop and delete"
# sweeps it with everything else.
REVEAL_AFTER = 2  # wrong tries before "Show me" is offered (or, on a check item, the answer)


async def _class_token(student: Dict[str, Any]) -> str:
    """Children added before classes existed get their class link on first use."""
    if student.get("class_token"):
        return student["class_token"]
    await db[svc.STUDENTS].update_one({"student_id": student["student_id"], "class_token": None},
                                      {"$set": {"class_token": svc.new_token()}})
    fresh = await db[svc.STUDENTS].find_one({"student_id": student["student_id"]}, {"_id": 0, "class_token": 1})
    student["class_token"] = fresh["class_token"]
    return student["class_token"]


async def _class_child(token: str) -> Dict[str, Any]:
    student = await _student_by("class_token", token)
    if student.get("deleted_at"):
        raise HTTPException(410, "This link no longer works.")
    if (student.get("consent") or {}).get("status") != "given" or not student.get("child_user_id"):
        raise HTTPException(409, "A parent needs to agree first. Ask your coach for the link.")
    return student


async def _sessions(student_id: str) -> List[Dict[str, Any]]:
    return await db[fs.SESSIONS].find({"student_id": student_id}, {"_id": 0}).sort("started_at", 1).to_list(500)


def _passed(sessions: List[Dict[str, Any]]) -> List[str]:
    return [s["class_id"] for s in sessions if s.get("kind") == "class" and s.get("passed")]


def _item_content(ref: Dict[str, Any]) -> Dict[str, Any]:
    if ref["owner"] == "placement":
        item = next(i for i in fs.load_content()["placement"]["items"] if i["id"] == ref["item_id"])
    else:
        item = fs.item_by_id(fs.class_by_id(ref["owner"]), ref["item_id"])
    return {**item, "part": ref.get("part") or item.get("part"),
            "test": False if ref.get("warm") else item.get("test", False)}


def _session_view(session: Dict[str, Any]) -> Dict[str, Any]:
    refs = session["items"]
    i = session["index"]
    current = None
    if i < len(refs):
        ref = refs[i]
        item = _item_content(ref)
        st = session["item_state"].get(ref["item_id"], {})
        current = fs.public_item(item, st.get("state"))
        current.update({"wrong": st.get("wrong", 0), "solved": st.get("solved", False),
                        "finished": st.get("finished", False), "revealed": st.get("revealed", False),
                        "can_reveal": (not item.get("test") and st.get("wrong", 0) >= REVEAL_AFTER
                                       and not st.get("finished")),
                        "can_retry": item["kind"] in ("stars", "game") and st.get("finished", False)
                                     and not st.get("solved"),
                        "can_skip": ref["owner"] == "placement" and not st.get("finished")})
    return {"session_id": session["session_id"], "kind": session["kind"], "class_id": session.get("class_id"),
            "title": session.get("title"), "index": i, "count": len(refs),
            "parts": [r.get("part") for r in refs], "stars": session.get("stars", 0),
            "current": current, "finished_at": session.get("finished_at"), "summary": session.get("summary")}


def _overview(student: Dict[str, Any], sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    level = (student.get("first_steps") or {}).get("level")
    passed = _passed(sessions)
    nxt = fs.next_class(level, passed) if level is not None else None
    start_order = fs.class_by_id(fs.LEVEL_START[level])["order"] if level is not None else 1
    return {
        "child_name": student["display_name"],
        "placed": level is not None, "level": level,
        "classes": [{"id": c["id"], "title": c["title"], "passed": c["id"] in passed,
                     "skipped": level is not None and c["order"] < start_order}
                    for c in fs.classes()],
        "next": {"id": nxt["id"], "title": nxt["title"]} if nxt else None,
        "all_done": level is not None and nxt is None,
        "stars": sum(int(s.get("stars") or 0) for s in sessions if s.get("finished_at")),
    }


@router.get("/class/{token}")
async def class_home(token: str):
    student = await _class_child(token)
    sessions = await _sessions(student["student_id"])
    open_ = next((s for s in reversed(sessions) if not s.get("finished_at")), None)
    from routes.academy_coach_plan import class_home_reflect
    return {**_overview(student, sessions), "open": _session_view(open_) if open_ else None,
            "reflect": await class_home_reflect(student)}


@router.post("/class/{token}/start")
async def class_start(token: str):
    student = await _class_child(token)
    sessions = await _sessions(student["student_id"])
    open_ = next((s for s in reversed(sessions) if not s.get("finished_at")), None)
    if open_:
        return _session_view(open_)
    level = (student.get("first_steps") or {}).get("level")
    if level is None:
        placement = fs.load_content()["placement"]
        refs = [{"owner": "placement", "item_id": i["id"], "part": i["part"]} for i in placement["items"]]
        kind, class_id, title = "placement", None, placement["title"]
    else:
        passed = _passed(sessions)
        cls = fs.next_class(level, passed)
        if cls is None:
            raise HTTPException(409, "Every class is done. Time for real games!")
        prev_cls = next((c for c in reversed(fs.classes())
                         if c["order"] < cls["order"] and c["id"] in passed), None)
        prev_session = next((s for s in reversed(sessions)
                             if prev_cls and s.get("class_id") == prev_cls["id"]), None)
        warm = fs.warm_up_for(cls, prev_cls, (prev_session or {}).get("mistakes") or {})
        refs = [{"owner": prev_cls["id"], "item_id": w["id"], "part": "Warm-up", "warm": True,
                 "why": w.get("why")} for w in warm]
        refs += [{"owner": cls["id"], "item_id": i["id"], "part": i["part"]}
                 for i in cls["items"] if not i.get("recall_only")]
        kind, class_id, title = "class", cls["id"], cls["title"]
    return await _new_session(student, kind, class_id, title, refs)


async def _new_session(student: Dict[str, Any], kind: str, class_id: Optional[str], title: str,
                       refs: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    session = {"session_id": svc.new_id("cls"), "student_id": student["student_id"],
               "user_id": student["child_user_id"], "academy_id": student["academy_id"],
               "kind": kind, "class_id": class_id, "title": title, "items": refs, "index": 0,
               "item_state": {}, "mistakes": {}, "stars": 0, "started_at": _now(),
               "content_version": fs.load_content().get("schema_version"), **extra}
    await db[fs.SESSIONS].insert_one(dict(session))
    return _session_view(session)


@router.post("/class/{token}/practise")
async def class_practise(token: str, payload: Dict[str, Any] = Body(...)):
    """Do a finished lesson again. Lesson 8 used to end on a page with no button,
    so a child who had finished everything had nothing left to do here."""
    student = await _class_child(token)
    sessions = await _sessions(student["student_id"])
    open_ = next((s for s in reversed(sessions) if not s.get("finished_at")), None)
    if open_:
        return _session_view(open_)
    row = next((c for c in _overview(student, sessions)["classes"] if c["id"] == payload.get("class_id")), None)
    if not row or not (row["passed"] or row["skipped"]):
        raise HTTPException(409, "Finish this lesson first.")
    cls = fs.class_by_id(row["id"])
    refs = [{"owner": cls["id"], "item_id": i["id"], "part": i["part"]}
            for i in cls["items"] if not i.get("recall_only")]
    return await _new_session(student, "class", cls["id"], cls["title"], refs, practice=True)


async def _open_session(student: Dict[str, Any], session_id: Any) -> Dict[str, Any]:
    session = await db[fs.SESSIONS].find_one({"session_id": session_id, "student_id": student["student_id"]},
                                             {"_id": 0})
    if not session or session.get("finished_at"):
        raise HTTPException(409, "This class has ended. Start the next one.")
    return session


@router.post("/class/{token}/answer")
async def class_answer(token: str, payload: Dict[str, Any] = Body(...)):
    student = await _class_child(token)
    session = await _open_session(student, payload.get("session_id"))
    ref = session["items"][session["index"]]
    if payload.get("item_id") != ref["item_id"]:
        raise HTTPException(409, "That question has moved on. Reload the class.")
    item = _item_content(ref)
    st = dict(session["item_state"].get(ref["item_id"]) or {"wrong": 0, "tries": 0})
    if st.get("finished"):
        return {"result": {"outcome": "ignored"}, "session": _session_view(session)}
    answer = payload.get("answer") or {}
    if answer.get("skip"):  # placement only: "I don't know yet"
        if ref["owner"] != "placement":
            raise HTTPException(409, "This one can't be skipped.")
        result = {"outcome": "skipped", "kind": None, "say": "That's fine. We'll learn it together."}
    elif answer.get("reveal"):
        if item.get("test") or st.get("wrong", 0) < REVEAL_AFTER:
            raise HTTPException(409, "Try once more first.")
        result = {"outcome": "revealed", "kind": None, "say": "Here it is.", "reveal": fs.reveal(item)}
    else:
        try:
            result = fs.grade(item, answer, st.get("state"))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, "That answer could not be read.")
    outcome = result["outcome"]
    if outcome == "ignored":
        return {"result": result, "session": _session_view(session)}
    st["tries"] = st.get("tries", 0) + 1
    if "state" in result:
        st["state"] = result["state"]
    inc: Dict[str, int] = {}
    if outcome == "wrong":
        st["wrong"] = st.get("wrong", 0) + 1
        kind = result.get("kind") or "wrong"
        kinds = dict(st.get("kinds") or {})
        kinds[kind] = kinds.get(kind, 0) + 1
        st["kinds"] = kinds
        inc[f"mistakes.{kind}"] = 1
        if item.get("test"):
            # A check item gives no hints. After the second miss it shows the answer and is failed.
            if st["wrong"] < REVEAL_AFTER:
                result["say"] = "Not quite. Try once more."
            else:
                result["say"] = "Here is the answer. We'll practise it again."
                result["reveal"] = fs.reveal(item)
                st["finished"], st["revealed"] = True, True
    elif outcome == "right":
        st["solved"], st["finished"] = True, True
        st["clean"] = st.get("wrong", 0) == 0 and not st.get("revealed")
        if not item.get("test") and session.get("stars", 0) < 5:
            inc["stars"] = 1
    elif outcome in ("done", "skipped", "revealed"):
        st["finished"] = True
        st["revealed"] = bool(st.get("revealed") or outcome == "revealed")
        if result.get("kind"):
            inc[f"mistakes.{result['kind']}"] = 1
    update: Dict[str, Any] = {"$set": {f"item_state.{ref['item_id']}": st, "updated_at": _now()}}
    if inc:
        update["$inc"] = inc
    await db[fs.SESSIONS].update_one({"session_id": session["session_id"]}, update)
    session = await db[fs.SESSIONS].find_one({"session_id": session["session_id"]}, {"_id": 0})
    return {"result": {k: v for k, v in result.items() if k != "state"}, "session": _session_view(session)}


@router.post("/class/{token}/retry")
async def class_retry(token: str, payload: Dict[str, Any] = Body(...)):
    """Play a stars level or a game again. Earlier tries stay counted."""
    student = await _class_child(token)
    session = await _open_session(student, payload.get("session_id"))
    ref = session["items"][session["index"]]
    item = _item_content(ref)
    st = dict(session["item_state"].get(ref["item_id"]) or {})
    if item["kind"] not in ("stars", "game") or st.get("solved"):
        raise HTTPException(409, "This one can't be played again.")
    st.update({"state": {}, "finished": False, "retries": st.get("retries", 0) + 1})
    await db[fs.SESSIONS].update_one({"session_id": session["session_id"]},
                                     {"$set": {f"item_state.{ref['item_id']}": st}})
    session["item_state"][ref["item_id"]] = st
    return _session_view(session)


@router.post("/class/{token}/next")
async def class_next(token: str, payload: Dict[str, Any] = Body(...)):
    student = await _class_child(token)
    session = await _open_session(student, payload.get("session_id"))
    ref = session["items"][session["index"]]
    if not (session["item_state"].get(ref["item_id"]) or {}).get("finished"):
        raise HTTPException(409, "Finish this one first.")
    index = session["index"] + 1
    if index < len(session["items"]):
        await db[fs.SESSIONS].update_one({"session_id": session["session_id"]},
                                         {"$set": {"index": index, "updated_at": _now()}})
        session["index"] = index
        return _session_view(session)
    return await _finish_class(student, session)


async def _finish_class(student: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    states = session["item_state"]
    name = student["display_name"]
    update: Dict[str, Any] = {"finished_at": _now(), "index": len(session["items"])}
    if session["kind"] == "placement":
        results = {}
        for ref in session["items"]:
            results[_item_content(ref)["result"]] = bool((states.get(ref["item_id"]) or {}).get("clean"))
        level = fs.placement_level(results)
        await db[svc.STUDENTS].update_one({"student_id": student["student_id"]},
                                          {"$set": {"first_steps.level": level, "first_steps.placed_at": _now(),
                                                    "first_steps.placement": results}})
        first = fs.class_by_id(fs.LEVEL_START[level])
        summary = {"say": f"Your first lesson is {first['title'].lower()}.",
                   "next": first["title"], "level": level}
    else:
        cls = fs.class_by_id(session["class_id"])
        tests = [r for r in session["items"] if not r.get("warm") and _item_content(r).get("test")]
        passed = all((states.get(r["item_id"]) or {}).get("solved")
                     and not (states.get(r["item_id"]) or {}).get("revealed") for r in tests)
        later = [c for c in fs.classes() if c["order"] > cls["order"]]
        nxt = (later[0] if later else None) if passed else cls
        update["passed"] = passed
        played = [r for r in session["items"] if r["item_id"] in states]
        practice = bool(session.get("practice"))
        if practice:
            say = (f"Well done. {name} still knows {cls['learnt']}." if passed
                   else f"That one is worth another go. {name} can practise {cls['title'].lower()} again.")
            parent = None
        elif passed and not later:
            say = f"{name} now knows {cls['learnt']}. That was the last lesson. Real games come next."
            parent = f"Today {name} learnt {cls['learnt']}."
        elif passed:
            say = f"{name} now knows {cls['learnt']}. The next lesson starts by checking it has stuck."
            parent = f"Today {name} learnt {cls['learnt']}."
        else:
            say = f"The check at the end did not go through. The next lesson repeats {cls['title'].lower()}."
            parent = f"Today {name} practised {cls['title'].lower()}. One more class on it, then the next one."
        summary = {"say": say, "parent": parent, "passed": passed,
                   "steps": len(played),
                   "first_try": sum(1 for r in played if (states.get(r["item_id"]) or {}).get("clean")),
                   "notes": fs.coach_notes(session.get("mistakes") or {}),
                   "next": None if practice else (nxt["title"] if nxt else None),
                   "all_done": passed and not later and not practice}
    update["summary"] = summary
    await db[fs.SESSIONS].update_one({"session_id": session["session_id"]}, {"$set": update})
    session.update(update)
    if session["kind"] != "placement":
        _in_background(_rebuild_week(student["student_id"]))
    return _session_view(session)


async def _rebuild_week(student_id: str) -> None:
    """A finished lesson is report material, so the coach and the parent's
    report should not wait for the two-hourly loop."""
    try:
        student = await db[svc.STUDENTS].find_one({"student_id": student_id}, {"_id": 0})
        if student and not student.get("deleted_at"):
            await build_week(student)
    except Exception as exc:
        logger.error("week rebuild after a lesson failed for %s: %s", student_id, exc)


async def first_steps_for_staff(student: Dict[str, Any]) -> Dict[str, Any]:
    """What the coach sees: where the child is in the eight classes and what
    the taps have shown in the last three classes."""
    sessions = await _sessions(student["student_id"])
    done = [s for s in sessions if s.get("kind") == "class" and s.get("finished_at")]
    mistakes: Dict[str, int] = {}
    for s in done[-3:]:
        for k, v in (s.get("mistakes") or {}).items():
            mistakes[k] = mistakes.get(k, 0) + v
    last = done[-1] if done else None
    return {**_overview(student, sessions),
            "last": {"title": last["title"], "passed": last.get("passed"), "finished_at": last.get("finished_at"),
                     "parent": (last.get("summary") or {}).get("parent")} if last else None,
            "notes": fs.coach_notes(mistakes)}
