"""The fifth geometry-gaps queue: did this real-game move show the lesson's idea?

docs/phase1_lesson_evidence_review_scope.md, WS1. Tested against a small
in-memory stand-in for the collections and one real position: a white knight
on f3 where Ne5 and Ng5 hang it to a pawn and Nd4 is safe. No engine, no Maia,
no Mongo -- the probabilities are supplied, the way the seeder supplies them.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from routes import admin_lesson_evidence as routes  # noqa: E402
from services import lesson_evidence_review as svc  # noqa: E402
from services.destination_safety_detector import QUALITY_ID  # noqa: E402

FEN = "6k1/8/3p1p2/8/8/5N2/8/6K1 w - - 0 1"


def _event(outcome="applied", key="grl_a", source="organic_game", quality=QUALITY_ID):
    return {
        "event_type": "lesson_result",
        "idempotency_key": key,
        "skill_id": "piece_safety_simple_hang",
        "occurred_at": "2026-10-01 10:00:00",
        "lesson_result": {"application": {
            "source_type": source, "detector_quality_id": quality, "outcome": outcome,
        }},
    }


def _obs(move="f3d4", quality="good"):
    return {"fen_before": FEN, "move_uci": move, "execution_quality": quality,
            "game_id": "g1", "ply": 1, "move_number": 1, "cp_loss": 0}


# ---------------------------------------------------------------------------
# rules 1, 3, 4
# ---------------------------------------------------------------------------
def test_the_position_has_exactly_the_two_hanging_knight_moves():
    assert svc.hanging_moves(FEN) == ["f3e5", "f3g5"]


def test_a_kept_safe_move_is_a_candidate():
    assert svc.candidate_rejection(_event(), _obs(), 1200) is None


def test_a_stored_kept_label_is_rechecked_against_the_detector():
    # The ledger says "applied", but Ne5 hangs the knight today.
    assert svc.candidate_rejection(_event(), _obs("f3e5"), 1200) == "outcome_disagrees_with_detector"


@pytest.mark.parametrize("event,obs,rating,reason", [
    (_event(outcome="missed"), _obs(), 1200, "not_kept"),
    (_event(source="lesson"), _obs(), 1200, "not_a_real_game"),
    (_event(quality="gap:missed_tactic:fork"), _obs(), 1200, "other_concept"),
    (_event(), _obs(quality="mistake"), 1200, "move_was_a_mistake"),
    (_event(), _obs(quality="blunder"), 1200, "move_was_a_mistake"),
    (_event(), None, 1200, "no_stored_position"),
    (_event(), _obs(), None, "no_rating"),
])
def test_rejections_name_the_rule(event, obs, rating, reason):
    assert svc.candidate_rejection(event, obs, rating) == reason


# ---------------------------------------------------------------------------
# rule 2: temptation
# ---------------------------------------------------------------------------
def _row(probabilities):
    return svc.review_row(
        _event(), _obs(), user_id="u1", user_rating=1200, opponent_rating=1210,
        probabilities=probabilities, record={"kept": 3, "lost": 2},
        first_lesson_at="2026-09-02T08:00:00",
    )


def test_temptation_sums_only_the_hanging_moves():
    row = _row({"f3d4": 0.6, "f3e5": 0.04, "f3g5": 0.03})
    assert row["temptation"] == pytest.approx(0.07)
    assert [m["san"] for m in row["tempting_moves"]] == ["Ne5", "Ng5"]
    assert row["tempting_moves"][0]["piece"] == "knight"


def test_probability_on_safe_moves_does_not_count():
    # Negative control: plenty of probability mass, none of it on a hanging move.
    assert _row({"f3d4": 0.7, "f3h4": 0.3}) is None


def test_below_the_floor_is_not_served():
    assert _row({"f3e5": 0.02, "f3g5": 0.02}) is None
    assert _row({"f3e5": 0.03, "f3g5": 0.02}) is not None  # exactly 0.05


def test_the_row_carries_what_the_card_shows():
    row = _row({"f3e5": 0.2})
    assert row["played_san"] == "Nd4"
    assert row["side_to_move"] == "white"
    assert row["pair"] == "u1|piece_safety_simple_hang"
    assert row["record"] == {"kept": 3, "lost": 2}
    assert row["after_first_lesson"] is True
    assert row["detector_quality_id"] == QUALITY_ID


# ---------------------------------------------------------------------------
# order: one pair at a time, approved pairs last, never by volume
# ---------------------------------------------------------------------------
def _r(key, pair, t):
    return {"key": key, "pair": pair, "temptation": t}


def test_one_row_per_pair_most_tempting_first():
    rows = [_r("a1", "A", 0.1), _r("a2", "A", 0.3), _r("b1", "B", 0.2)]
    queue = svc.order_queue(rows, [])
    assert sorted(r["key"] for r in queue) == ["a2", "b1"]


def test_a_pair_with_a_yes_waits_behind_pairs_without_one():
    rows = [_r("a1", "A", 0.1), _r("a2", "A", 0.3), _r("b1", "B", 0.2), _r("b2", "B", 0.2)]
    rulings = [{"key": "a2", "pair": "A", "verdict": "yes"},
               {"key": "b2", "pair": "B", "verdict": "no"}]
    queue = svc.order_queue(rows, rulings)
    assert [r["key"] for r in queue] == ["b1", "a1"]


def test_a_big_pair_does_not_crowd_out_a_small_one():
    rows = [_r(f"a{i}", "A", 0.5) for i in range(50)] + [_r("b1", "B", 0.06)]
    queue = svc.order_queue(rows, [])
    assert {r["pair"] for r in queue} == {"A", "B"}
    assert len(queue) == 2


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return list(self._rows)


class _Collection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.writes = []

    def _match(self, query):
        return [r for r in self.rows if all(r.get(k) == v for k, v in (query or {}).items())]

    def find(self, query=None, projection=None):
        return _Cursor([dict(r) for r in self._match(query)])

    async def find_one(self, query=None, projection=None):
        m = self._match(query)
        return dict(m[0]) if m else None

    async def update_one(self, query, update, upsert=False):
        self.writes.append((query, update))
        body = dict(update.get("$set") or {})
        m = self._match(query)
        if m:
            m[0].update(body)
        elif upsert:
            self.rows.append(body)


class _DB:
    def __init__(self, reviews):
        self.lesson_evidence_reviews = _Collection(reviews)
        self.lesson_evidence_rulings = _Collection()
        self.learning_sessions = _Collection([{"session_id": "s1", "events": []}])


class _User:
    user_id = "u_admin"
    email = "Coach@Example.com"


@pytest.fixture
def db():
    row = _row({"f3e5": 0.2})
    database = _DB([row])
    routes.set_db(database)
    yield database
    routes.set_db(None)


def _run(coro):
    return asyncio.run(coro)


def test_next_serves_the_row(db):
    out = _run(routes.next_lesson_evidence(user=_User()))
    assert out["key"] == "grl_a"
    assert out["queue"] == "lesson"
    assert out["pairs_waiting"] == 1


def test_next_says_nothing_is_seeded_when_empty():
    routes.set_db(_DB([]))
    try:
        with pytest.raises(HTTPException) as e:
            _run(routes.next_lesson_evidence(user=_User()))
        assert e.value.status_code == 404
        assert "seeded" in e.value.detail
    finally:
        routes.set_db(None)


def test_a_ruling_lands_in_rulings_and_never_in_the_ledger(db):
    out = _run(routes.rule_lesson_evidence(
        payload={"key": "grl_a", "verdict": "YES", "note": "clear", "reviewer_name": "Farhan"},
        user=_User()))
    assert out == {"ok": True, "key": "grl_a", "verdict": "yes"}
    ruling = db.lesson_evidence_rulings.rows[0]
    assert ruling["pair"] == "u1|piece_safety_simple_hang"
    assert ruling["reviewer_name"] == "Farhan"
    assert ruling["after_first_lesson"] is True
    assert ruling["author_email"] == "coach@example.com"
    assert db.learning_sessions.writes == []
    assert db.lesson_evidence_reviews.writes == []
    with pytest.raises(HTTPException) as e:
        _run(routes.next_lesson_evidence(user=_User()))
    assert e.value.status_code == 404


@pytest.mark.parametrize("payload,status", [
    ({"verdict": "yes"}, 400),
    ({"key": "grl_a", "verdict": "agree"}, 400),
    ({"key": "grl_missing", "verdict": "yes"}, 404),
])
def test_bad_rulings_are_refused(db, payload, status):
    with pytest.raises(HTTPException) as e:
        _run(routes.rule_lesson_evidence(payload=payload, user=_User()))
    assert e.value.status_code == status
    assert db.lesson_evidence_rulings.rows == []


def test_results_list_every_no_as_a_bug_report(db):
    _run(routes.rule_lesson_evidence(
        payload={"key": "grl_a", "verdict": "no", "note": "any move was safe here"}, user=_User()))
    out = _run(routes.lesson_evidence_results(user=_User()))
    assert out["by_verdict"] == {"no": 1}
    assert out["pairs_approved"] == 0
    assert out["ruled_no"][0]["note"] == "any move was safe here"
