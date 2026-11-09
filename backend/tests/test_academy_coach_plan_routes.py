"""The coach plan end to end on the real routes: build, coach approves, the
child reflects by tapping, the coach reads the cause.

Uses the small Mongo from test_academy_routes and a fake engine.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from routes import academy_coach_plan as plan_routes
from services import academy_service as svc
from services import coach_plan_service as cp
from test_academy_routes import COACH, STRANGER, _Req, _setup, db, routes, run  # noqa: F401
from test_coach_plan_service import QG4_FEN, QG4_PGN, FakeEngine


@pytest.fixture
def child(db, monkeypatch):  # noqa: F811
    _, batch, _, student = _setup(db)
    run(routes.give_consent(student["consent_token"], _Req(),
                            {"agree": True, "parent_name": "Meena", "is_parent": True}))
    student = db[svc.STUDENTS].rows[0]
    uid = student["child_user_id"]
    begin, _ = svc.week_bounds_utc(svc.week_start())
    db.games.rows.append({"user_id": uid, "game_id": "g1", "is_analyzed": True, "result": "0-1",
                          "user_color": "white", "played_at_utc": begin + timedelta(hours=5),
                          "pgn": QG4_PGN})
    db.move_observations.rows.append({"user_id": uid, "game_id": "g1", "ply": 3,
                                      "missed_pattern": "piece_safety", "subtype": "destination_safety_exact",
                                      "eval_before": 0, "fen_before": QG4_FEN, "move_uci": "d1g4",
                                      "time_spent_seconds": 4})

    def fake_moments(chosen, games, pgns, cached):
        return [cp.build_moment(o, {**games[o["game_id"]], "pgn": pgns.get(o["game_id"], "")},
                                FakeEngine("e4d5")) for o in chosen]
    monkeypatch.setattr(plan_routes, "_engine_moments", fake_moments)
    return batch, student


def _week(db, student):
    return next(r for r in db[svc.WEEKS].rows if r["student_id"] == student["student_id"])


def test_the_whole_plan_flow(db, child):  # noqa: F811
    batch, student = child
    run(routes.build_week(student))
    plan = _week(db, student)["coach_plan"]
    assert plan["status"] == "draft"
    assert plan["problem"]["quality_id"] == "gap:piece_safety:destination_safety_exact"
    assert plan["problem"]["games_lost"] == 1
    assert len(plan["moments"]) == 1 and plan["moments"][0]["test"]["answer"][0]["sq"] == "c8"

    token = student["class_token"] or run(routes._class_token(student))
    assert run(plan_routes.child_plan(token))["available"] is False   # not before the coach approves

    view = run(routes.student_view(student["student_id"], user=COACH))
    assert view["plan"]["status"] == "draft" and view["plan"]["moments"][0]["done"] is False

    second = plan["rule_options"][1]["id"]
    run(plan_routes.approve_plan(student["student_id"], {"rule_id": second}, user=COACH))
    plan = _week(db, student)["coach_plan"]
    assert plan["status"] == "approved" and plan["rule"]["id"] == second
    assert plan["actions"][-1]["action"] == "approved_rule_changed"

    page = run(plan_routes.child_plan(token))
    assert page["available"] and len(page["moments"]) == 1
    assert "game_id" not in page["moments"][0]
    key = page["moments"][0]["key"]

    out = run(plan_routes.child_answer(token, key, {"picks": [{"kind": "develop"}], "tapped": ["c8"],
                                                    "seen_in_game": "no"}))
    assert out["card"]["found_when_asked"] is True
    assert out["card"]["wanted"] == ["bring the queen into play"]
    assert _week(db, student)["coach_plan"]["cause"]["kind"] == "not_looking"

    view = run(routes.student_view(student["student_id"], user=COACH))
    assert view["plan"]["moments"][0]["done"] is True
    assert view["plan"]["cause"]["kind"] == "not_looking"
    row = run(routes.batch_view(batch["batch_id"], user=COACH))["rows"][0]
    assert row["plan"]["status"] == "approved" and row["plan"]["cause_words"].startswith("Not looking")

    run(routes.build_week(student))                     # the rebuild keeps the approved plan
    assert _week(db, student)["coach_plan"]["status"] == "approved"


def test_strangers_cannot_approve_and_children_cannot_answer_unknown_moments(db, child):  # noqa: F811
    _, student = child
    run(routes.build_week(student))
    with pytest.raises(HTTPException):
        run(plan_routes.approve_plan(student["student_id"], {}, user=STRANGER))
    run(plan_routes.approve_plan(student["student_id"], {}, user=COACH))
    token = student["class_token"] or run(routes._class_token(student))
    with pytest.raises(HTTPException) as e:
        run(plan_routes.child_answer(token, "nope", {"tapped": []}))
    assert e.value.status_code == 404


def test_approve_all_approves_drafts(db, child):  # noqa: F811
    batch, student = child
    run(routes.build_week(student))
    out = run(plan_routes.approve_all(batch["batch_id"], user=COACH))
    assert out["approved"] == 1
    assert _week(db, student)["coach_plan"]["status"] == "approved"
