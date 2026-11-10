"""Coach plan routes: the coach approves, the child reflects by tapping.

docs/coach_assistant_plan_scope.md (signed 2026-11-09). The plan lives on the
week row (`academy_student_weeks.coach_plan`); the child's answers go in
`reflection_sessions` through the same writer the game-review reflection uses
(`store_event_reflection`), as reflection_kind "coach_plan_moment".

Access goes through routes.academy's own checks (_student_for, _batch_for,
_class_child), so who may see what is decided in one place.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from routes import academy as A
from routes.auth import User, get_current_user
from services import academy_service as svc
from services import coach_plan_service as cp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/academy", tags=["Academy coach plan"])

KIND = "coach_plan_moment"
SCHEMA = "coach_plan_reflection.v1"
PICK_KINDS = {"attack", "defend", "develop", "escape", "other"}
SEEN = {"no", "ok", "unsure"}


def _db():
    return A.db


# ---------------------------------------------------------------------------
# build (background: the two-hourly week rebuild and the coach's Refresh)
# ---------------------------------------------------------------------------
async def _recent_games(uid: str, start) -> Dict[str, Dict[str, Any]]:
    from services.game_outcome import user_outcome
    _, end = svc.week_bounds_utc(start)
    since = end - timedelta(days=cp.LOOKBACK_DAYS)
    rows = await _db().games.find(
        {"user_id": uid, "is_analyzed": True, "played_at_utc": {"$gte": since, "$lt": end}},
        {"_id": 0, "game_id": 1, "result": 1, "user_color": 1, "played_at_utc": 1,
         "termination": 1, "game_outcome": 1},
    ).to_list(200)
    out = {}
    for g in rows:
        played = g.get("played_at_utc")
        out[g["game_id"]] = {**g, "outcome": user_outcome(g),
                             "played_at": played.isoformat() if isinstance(played, datetime) else ""}
    return out


async def _plan_observations(uid: str, game_ids: List[str]) -> List[Dict[str, Any]]:
    if not game_ids:
        return []
    rows = await _db().move_observations.find(
        {"user_id": uid, "game_id": {"$in": game_ids},
         "$or": [{"missed_pattern": {"$ne": None}}, {"development_decision": "missed"}]},
        {"_id": 0, "game_id": 1, "ply": 1, "move_number": 1, "fen_before": 1, "move_uci": 1,
         "missed_pattern": 1, "subtype": 1, "eval_before": 1, "time_spent_seconds": 1,
         "development_decision": 1},
    ).to_list(5000)
    if await _development_eligible(uid):
        for r in rows:
            r["_development_eligible"] = True
    return rows


async def _development_eligible(uid: str) -> bool:
    """Lock A1: the child's development rate over the last 80 analysed games.
    Reads only move_observations rows that carry a development decision."""
    recent = await _db().games.find({"user_id": uid, "is_analyzed": True}, {"_id": 0, "game_id": 1}
                                    ).sort("played_at_utc", -1).limit(cp.DEVELOPMENT_GAMES).to_list(cp.DEVELOPMENT_GAMES)
    if not recent:
        return False
    rows = await _db().move_observations.find(
        {"user_id": uid, "game_id": {"$in": [g["game_id"] for g in recent]},
         "development_decision": {"$in": ["applied", "missed"]}},
        {"_id": 0, "development_decision": 1, "missed_pattern": 1}).to_list(4000)
    return cp.development_rate(rows)["eligible"]


def _engine_moments(chosen, games, pgns, cached):
    """Runs in a worker thread: one engine for the few moments of one child."""
    import chess.engine
    from config import STOCKFISH_PATH
    out = []
    engine = None
    try:
        for o in chosen:
            key = cp.moment_key(o)
            if key in cached:
                out.append(cached[key])
                continue
            if engine is None:
                engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            m = cp.build_moment(o, {**games[o["game_id"]], "pgn": pgns.get(o["game_id"], "")}, engine)
            if m:
                out.append(m)
    finally:
        if engine is not None:
            engine.quit()
    return out


async def build_plan(student: Dict[str, Any], start, week_row_old: Optional[Dict[str, Any]],
                     week_games: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The plan for this week. An approved or skipped plan is kept as it was
    (the child may already be working on it); only its check is refreshed."""
    uid = student["child_user_id"]
    old = (week_row_old or {}).get("coach_plan")
    games = await _recent_games(uid, start)
    obs = await _plan_observations(uid, list(games))

    prev_row = await _db()[svc.WEEKS].find_one(
        {"student_id": student["student_id"], "week_start": (start - timedelta(days=7)).isoformat()},
        {"_id": 0, "coach_plan.status": 1, "coach_plan.problem": 1, "coach_plan.baseline": 1})
    prev_plan = (prev_row or {}).get("coach_plan") or {}
    last_check = None
    if prev_plan.get("status") == "approved":
        week_ids = {g["game_id"] for g in week_games if g.get("game_id") in games}
        week_games_map = {gid: games[gid] for gid in week_ids}
        week_obs = [o for o in obs if o["game_id"] in week_ids]
        if prev_plan["problem"]["quality_id"] == cp.DEVELOPMENT_QID:
            # Last week's development plan is checked even if the child has
            # since moved above the cut-off; otherwise the check reads 0 and
            # says "fewer". A copy, so this week's ranking is not affected.
            week_obs = [{**o, "_development_eligible": True} for o in week_obs]
        last_check = cp.week_check(prev_plan["problem"]["quality_id"], week_games_map, week_obs,
                                   prev_plan.get("baseline"))

    if old and old.get("status") in ("approved", "skipped"):
        return {**old, "last_check": last_check}

    ranked = cp.rank_problems(games, obs)
    if not ranked:
        reason = ("Not enough analysed games yet." if len(games) < 3
                  else "None of the problems we can check showed up in the last four weeks.")
        return {"status": "none", "reason": reason, "last_check": last_check, "built_at": A._now()}
    top = ranked[0]
    chosen = cp.choose_moments(top, cp.MOMENTS_PER_WEEK + 2)
    pgn_rows = await _db().games.find({"game_id": {"$in": [o["game_id"] for o in chosen]}},
                                      {"_id": 0, "game_id": 1, "pgn": 1}).to_list(20)
    pgns = {r["game_id"]: r.get("pgn") or "" for r in pgn_rows}
    cached = {m["key"]: m for m in (old or {}).get("moments") or []}
    try:
        moments = await asyncio.to_thread(_engine_moments, chosen, games, pgns, cached)
    except Exception as exc:  # engine trouble: keep what we had rather than show nothing new
        logger.error("coach plan moments failed for %s: %s", student["student_id"], exc)
        if old:
            return old
        moments = []
    moments = moments[:cp.MOMENTS_PER_WEEK]
    kind, pattern = top["kind"], top["pattern"]
    options = cp.rule_options(kind, pattern)
    old_rule = ((old or {}).get("rule") or {}).get("id")
    rule = next((r for r in options if r["id"] == old_rule), options[0])
    return {
        "status": "draft" if moments else "none",
        "reason": None if moments else "The moments for this problem could not be checked on the board.",
        "problem": {k: top[k] for k in ("quality_id", "label", "kind", "pattern", "games_lost", "games", "moments")},
        "runners_up": [{k: r[k] for k in ("quality_id", "label", "games_lost", "games", "moments")}
                       for r in ranked[1:4]],
        "moments": moments,
        "warning_sign": cp.sign_for(kind, pattern),
        "rule": rule, "rule_options": options,
        "baseline": cp.baseline_for(top, games),
        "last_check": last_check,
        "cause": cp.cause_from([], top["quality_id"]),
        "built_at": A._now(),
        "actions": (old or {}).get("actions") or [],
    }


# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------
async def _answers(student_id: str, start: str) -> Dict[str, Dict[str, Any]]:
    rows = await _db().reflection_sessions.find(
        {"reflection_kind": KIND, "event.student_id": student_id, "event.week_start": start},
        {"_id": 0, "event.event_id": 1, "response": 1}).to_list(50)
    return {r["event"]["event_id"]: r.get("response") or {} for r in rows}


def plan_summary(week: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The batch-table cell; reads only fields the batch projection keeps."""
    p = (week or {}).get("coach_plan") or {}
    return {"status": p.get("status") or "none",
            "problem_label": (p.get("problem") or {}).get("label"),
            "cause_words": (p.get("cause") or {}).get("words") if (p.get("cause") or {}).get("answered") else None,
            "reason": p.get("reason")}


async def coach_view(student: Dict[str, Any], week: Optional[Dict[str, Any]], start: str) -> Dict[str, Any]:
    p = (week or {}).get("coach_plan")
    if not p:
        return {"status": "none", "reason": "This week has not been read yet. Press Refresh."}
    answers = await _answers(student["student_id"], start)
    moments = []
    for m in p.get("moments") or []:
        a = answers.get(m["key"])
        moments.append({"key": m["key"], "san": m["san"], "date": m.get("date"), "kind": m["kind"],
                        "pattern": m.get("pattern"), "taker_words": cp.taker_words(m),
                        "costs_result": m.get("costs_result"), "done": bool(a),
                        "answers": cp.answer_card(m, a) if a else None})
    return {k: p.get(k) for k in ("status", "reason", "problem", "runners_up", "warning_sign", "rule",
                                  "rule_options", "last_check", "approved_by_name", "approved_at",
                                  "skipped_at")} | {
        "moments": moments,
        "cause": cp.cause_from(list(answers.values()), (p.get("problem") or {}).get("quality_id"))}


# ---------------------------------------------------------------------------
# coach actions
# ---------------------------------------------------------------------------
async def _this_week(student_id: str):
    start = svc.week_start().isoformat()
    week = await _db()[svc.WEEKS].find_one({"student_id": student_id, "week_start": start}, {"_id": 0})
    return start, week


async def _approve(student: Dict[str, Any], user: User, rule_id: Optional[str]) -> Dict[str, Any]:
    start, week = await _this_week(student["student_id"])
    p = (week or {}).get("coach_plan") or {}
    if p.get("status") not in ("draft", "approved"):
        raise HTTPException(409, p.get("reason") or "There is no plan to approve this week.")
    rule = p["rule"]
    action = {"at": A._now(), "by": user.user_id, "action": "approved_unchanged"}
    if rule_id and rule_id != rule["id"]:
        chosen = next((r for r in p.get("rule_options") or [] if r["id"] == rule_id), None)
        if not chosen:
            raise HTTPException(400, "That rule is not one of the options.")
        action = {**action, "action": "approved_rule_changed", "from": rule["id"], "to": rule_id}
        rule = chosen
    await _db()[svc.WEEKS].update_one(
        {"student_id": student["student_id"], "week_start": start},
        {"$set": {"coach_plan.status": "approved", "coach_plan.rule": rule,
                  "coach_plan.approved_by": user.user_id, "coach_plan.approved_by_name": user.name,
                  "coach_plan.approved_at": A._now()},
         "$push": {"coach_plan.actions": action}})
    return {"ok": True, "status": "approved", "rule": rule}


@router.post("/student/{student_id}/plan/approve")
async def approve_plan(student_id: str, payload: Dict[str, Any] = Body(default={}),
                       user: User = Depends(get_current_user)):
    student = await A._student_for(user, student_id)
    return await _approve(student, user, (payload or {}).get("rule_id"))


@router.post("/student/{student_id}/plan/skip")
async def skip_plan(student_id: str, user: User = Depends(get_current_user)):
    student = await A._student_for(user, student_id)
    start, week = await _this_week(student_id)
    if not (week or {}).get("coach_plan"):
        raise HTTPException(409, "There is no plan this week.")
    await _db()[svc.WEEKS].update_one(
        {"student_id": student_id, "week_start": start},
        {"$set": {"coach_plan.status": "skipped", "coach_plan.skipped_at": A._now()},
         "$push": {"coach_plan.actions": {"at": A._now(), "by": user.user_id, "action": "skipped"}}})
    return {"ok": True, "status": "skipped"}


@router.post("/batch/{batch_id}/plans/approve-all")
async def approve_all(batch_id: str, user: User = Depends(get_current_user)):
    await A._batch_for(user, batch_id)
    start = svc.week_start().isoformat()
    n = 0
    async for s in _db()[svc.STUDENTS].find({"batch_id": batch_id, "deleted_at": None},
                                            {"_id": 0, "student_id": 1}):
        week = await _db()[svc.WEEKS].find_one({"student_id": s["student_id"], "week_start": start},
                                               {"_id": 0, "coach_plan.status": 1})
        if ((week or {}).get("coach_plan") or {}).get("status") == "draft":
            student = await A._student_for(user, s["student_id"])
            await _approve(student, user, None)
            n += 1
    return {"ok": True, "approved": n}


# ---------------------------------------------------------------------------
# the child (no account: the class link's token)
# ---------------------------------------------------------------------------
async def class_home_reflect(student: Dict[str, Any]) -> Dict[str, Any]:
    """The one line the child's class home needs: is there a plan, and is it done."""
    start, week = await _this_week(student["student_id"])
    p = (week or {}).get("coach_plan") or {}
    if p.get("status") != "approved":
        return {"available": False, "all_done": False}
    keys = {m["key"] for m in p.get("moments") or []}
    answered = set(await _answers(student["student_id"], start))
    return {"available": True, "all_done": bool(keys) and keys <= answered}


@router.get("/class/{token}/reflect")
async def child_plan(token: str):
    student = await A._class_child(token)
    start, week = await _this_week(student["student_id"])
    p = (week or {}).get("coach_plan") or {}
    if p.get("status") != "approved":
        return {"available": False, "child_name": student["display_name"],
                "reason": "Your coach has not set this week's plan yet."}
    answers = await _answers(student["student_id"], start)
    return {"available": True, "child_name": student["display_name"],
            "warning_sign": p.get("warning_sign"), "rule": p.get("rule"),
            "moments": [{**cp.public_moment(m), "done": m["key"] in answers} for m in p.get("moments") or []]}


def _clean_answers(m: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    picks = []
    for p in (raw.get("picks") or [])[:8]:
        if isinstance(p, dict) and p.get("kind") in PICK_KINDS:
            sq = p.get("sq")
            picks.append({"kind": p["kind"], "sq": sq if isinstance(sq, str) and len(sq) == 2 else None})
    tapped = [t for t in (raw.get("tapped") or [])[:16] if isinstance(t, str) and len(t) <= 5]
    practice = [t for t in (raw.get("practice") or [])[:10] if isinstance(t, str) and len(t) <= 5]
    seen = raw.get("seen_in_game") if raw.get("seen_in_game") in SEEN else "unsure"
    return {"picks": picks, "tapped": tapped, "practice": practice, "seen_in_game": seen,
            "found_when_asked": found_when_asked(m, tapped)}


def found_when_asked(m: Dict[str, Any], tapped: List[str]) -> bool:
    """Graded here, from the board facts, not taken from the page."""
    test = m.get("test") or {}
    if test.get("kind") == "find_move":
        return any(t in set(test.get("accept") or []) for t in tapped[:3])
    answer = {a["sq"] for a in test.get("answer") or []}
    taps = set(tapped)
    if m.get("kind") == "king_attack":
        need = (len(answer) + 1) // 2
        return len(taps & answer) >= need and len(taps - answer) <= 1
    return bool(answer) and answer <= taps


@router.post("/class/{token}/reflect/{key:path}")
async def child_answer(token: str, key: str, payload: Dict[str, Any] = Body(...)):
    from services.review_reflection_service import store_event_reflection
    student = await A._class_child(token)
    start, week = await _this_week(student["student_id"])
    p = (week or {}).get("coach_plan") or {}
    if p.get("status") != "approved":
        raise HTTPException(409, "Your coach has not set this week's plan yet.")
    m = next((x for x in p.get("moments") or [] if x["key"] == key), None)
    if not m:
        raise HTTPException(404, "That moment is not in this week's plan.")
    answers = _clean_answers(m, payload or {})
    now = datetime.now(timezone.utc).isoformat()
    doc = {"reflection_id": f"cpr_{student['student_id']}_{start}_{key}",
           "user_id": student["child_user_id"], "game_id": m["game_id"],
           "reflection_kind": KIND, "schema_version": SCHEMA, "updated_at": now,
           "event": {"event_id": key, "quality_id": m["quality_id"], "kind": m["kind"],
                     "pattern": m.get("pattern"), "student_id": student["student_id"],
                     "week_start": start, "source": "academy_coach_plan"},
           "response": answers}
    await store_event_reflection(_db().reflection_sessions, doc)
    all_answers = await _answers(student["student_id"], start)
    await _db()[svc.WEEKS].update_one({"student_id": student["student_id"], "week_start": start},
                                      {"$set": {"coach_plan.cause": cp.cause_from(list(all_answers.values()),
                                                                          (p.get("problem") or {}).get("quality_id"))}})
    return {"ok": True, "card": cp.answer_card(m, answers)}
