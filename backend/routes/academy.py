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
    return {
        "consent": f"{site}/consent/{student['consent_token']}",
        "report": f"{site}/r/{student['report_token']}",
        "homework": f"{site}/homework/{student['homework_token']}",
    }


def _consent_message(student: Dict[str, Any], academy: Dict[str, Any]) -> str:
    return (f"Hello {student.get('parent_name') or ''}. {academy['name']} uses ChessGuru to "
            f"follow {student['display_name']}'s online chess games and send you a short weekly "
            f"report. Please read and agree here: {_links(student)['consent']}").replace("  ", " ")


def _report_message(student: Dict[str, Any], academy: Dict[str, Any]) -> str:
    links = _links(student)
    return (f"{student['display_name']}'s chess week from {academy['name']}: {links['report']} "
            f"This week's homework: {links['homework']}")


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


async def build_week(student: Dict[str, Any], start=None) -> Optional[Dict[str, Any]]:
    """Rebuild one child's week and store it. Returns the stored row."""
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
    # A coach's confirmation survives the rebuild when the good moment is the
    # same move; a different move is a new moment and starts unconfirmed.
    old = await db[svc.WEEKS].find_one({"student_id": student["student_id"],
                                        "week_start": start.isoformat()}, {"_id": 0, "good_moment": 1})
    old_good, new_good = (old or {}).get("good_moment") or {}, week.get("good_moment")
    if new_good and old_good.get("confirmed_by_name") and \
            (old_good.get("fen"), old_good.get("move_uci")) == (new_good["fen"], new_good["move_uci"]):
        for key in ("confirmed_by_name", "confirmed_by", "confirmed_at"):
            new_good[key] = old_good.get(key)
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
        "homework_token": svc.new_token(),
        "created_by": user.user_id, "created_at": _now(), "deleted_at": None,
    }
    await db[svc.STUDENTS].insert_one(dict(student))
    return {"student_id": student["student_id"], "links": _links(student),
            "whatsapp": svc.whatsapp_link(phone, _consent_message(student, batch["academy"]))}


def _row_for_table(student, week, homework_status) -> Dict[str, Any]:
    habit = (week or {}).get("habit")
    habit_id = (habit or {}).get("id")
    games = int(((week or {}).get("games") or {}).get("count") or 0)
    return {
        "student_id": student["student_id"],
        "name": student["display_name"],
        "consent": (student.get("consent") or {}).get("status"),
        "habit": svc.HABIT_WORDS[habit_id]["short"] if habit_id in svc.HABIT_WORDS
        else ("Nothing stood out" if games else "No games this week"),
        "trend": (week or {}).get("trend") or "none",
        "trend_words": svc.TREND_WORDS.get((week or {}).get("trend") or "none"),
        "games_words": "None" if games == 0 else ("A few" if games < 5 else "Many"),
        "homework": homework_status,
        "homework_words": svc.HOMEWORK_WORDS.get(homework_status, homework_status),
        "needs_you": svc.needs_coach(student, week, homework_status),
    }


@router.get("/batch/{batch_id}")
async def batch_view(batch_id: str, user: User = Depends(get_current_user)):
    batch = await _batch_for(user, batch_id)
    start = svc.week_start().isoformat()
    students = await db[svc.STUDENTS].find({"batch_id": batch_id, "deleted_at": None},
                                           {"_id": 0}).sort("display_name", 1).to_list(200)
    rows, weeks = [], []
    for s in students:
        week = await db[svc.WEEKS].find_one({"student_id": s["student_id"], "week_start": start},
                                            {"_id": 0, "better_moves": 0})
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
    academy = student["academy"]
    return {
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
    row = await build_week(student)
    return {"ok": True, "built_at": (row or {}).get("built_at")}


@router.post("/student/{student_id}/report")
async def approve_report(student_id: str, payload: Dict[str, Any] = Body(default={}),
                         user: User = Depends(get_current_user)):
    student = await _student_for(user, student_id)
    batch = await db[svc.BATCHES].find_one({"batch_id": student["batch_id"]}, {"_id": 0}) or {}
    start = svc.week_start().isoformat()
    week = await db[svc.WEEKS].find_one({"student_id": student_id, "week_start": start}, {"_id": 0})
    if not week:
        raise HTTPException(409, "This week has not been read yet. Press Refresh first.")
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
                                          _report_message(student, student["academy"]))}


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
    "We read the chess games your child plays online, on the account you name.",
    "We use them to show your child's coach and you which habits to work on.",
    "We keep your child's first name, the chess account name and your phone number.",
    "We do not show your child to other people, and no one can message your child.",
    "You can stop at any time from the report. We then delete your child's games.",
]


@router.get("/consent/{token}")
async def consent_page(token: str):
    student = await _student_by("consent_token", token)
    academy = await db[svc.ACADEMIES].find_one({"academy_id": student["academy_id"]}, {"_id": 0}) or {}
    if student.get("deleted_at"):
        return {"status": "deleted", "academy": academy.get("name"), "child_name": student["display_name"]}
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
        asyncio.create_task(_first_sync(student["child_user_id"]))
    return {"ok": True, "status": "given"}


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
    uid = student.get("child_user_id")
    if uid:
        game_ids = [g["game_id"] for g in await db.games.find({"user_id": uid}, {"_id": 0, "game_id": 1}).to_list(10000)]
        await db.users.update_one({"user_id": uid},
                                  {"$unset": {"lichess_username": "", "chess_com_username": "",
                                              "chesscom_username": ""},
                                   "$set": {"deleted_at": _now()}})
        if game_ids:
            await db.game_analyses.delete_many({"game_id": {"$in": game_ids}})
            await db.analysis_queue.delete_many({"game_id": {"$in": game_ids}})
        await db.games.delete_many({"user_id": uid})
        await db.move_observations.delete_many({"user_id": uid})
    for coll in (svc.WEEKS, svc.REPORTS, svc.ATTEMPTS, EVIDENCE):
        await db[coll].delete_many({"student_id": student["student_id"]})
    for side in ("white_student_id", "black_student_id"):
        await db[svc.CLASS_GAMES].delete_many({side: student["student_id"]})
    await db[svc.STUDENTS].update_one(
        {"student_id": student["student_id"]},
        {"$set": {"deleted_at": _now(), "deleted_reason": reason, "deleted_by": by,
                  "consent.status": "withdrawn", "lichess_username": None,
                  "chesscom_username": None, "parent_phone": None, "parent_name": None}})


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
        return {"status": "none", "child_name": student["display_name"], "academy": academy.get("name")}
    await db[svc.REPORTS].update_one({"report_id": report["report_id"]},
                                     {"$inc": {"opens": 1}, "$set": {"last_opened_at": _now()},
                                      "$min": {"first_opened_at": _now()}})
    return {"status": "ready", "academy": academy.get("name"), "week_start": report["week_start"],
            "report": report["payload"], "homework_link": _links(student)["homework"],
            "stop_link": f"{_site()}/consent/{student['consent_token']}"}


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
