"""The fourth geometry-gaps queue: Claude's reason, judged by the board.

Mohit 2026-10-29: "add a section on claude reason for those positions too, so
I can verify them right there."

The routes carry little logic -- ordering, validation, and which collection a
ruling lands in -- so that is what is tested, against a small in-memory stand-in
for the two collections. No engine, no Mongo.
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

from routes import admin_claude_reasons as mod  # noqa: E402


# ---------------------------------------------------------------------------
# a motor-shaped stand-in: only the calls the routes make
# ---------------------------------------------------------------------------
class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return list(self._rows)


class _Collection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.upserts = []

    def _match(self, query):
        def ok(r):
            return all(r.get(k) == v for k, v in (query or {}).items())
        return [r for r in self.rows if ok(r)]

    async def distinct(self, field, query=None):
        return sorted({r.get(field) for r in self._match(query) if r.get(field) is not None})

    def find(self, query=None, projection=None):
        return _Cursor([dict(r) for r in self._match(query)])

    async def find_one(self, query=None, projection=None):
        m = self._match(query)
        return dict(m[0]) if m else None

    async def count_documents(self, query=None):
        return len(self._match(query))

    async def update_one(self, query, update, upsert=False):
        self.upserts.append((query, update, upsert))
        body = dict(update.get("$set") or {})
        m = self._match(query)
        if m:
            m[0].update(body)
        elif upsert:
            self.rows.append(body)


class _DB:
    def __init__(self, reviews):
        self.claude_reason_reviews = _Collection(reviews)
        self.claude_reason_rulings = _Collection()


class _User:
    user_id = "u_test"
    email = "Mohit@Example.com"


REVIEWS = [
    {"key": "g1:9:Nc6", "idx": 3, "fen": "f1", "played_san": "Nc6", "best_san": "h6",
     "bucket": "geometry", "reason": "ignores the pin", "judge_overall": "confirmed",
     "probes": [{"kind": "relation", "verdict": "CONFIRMED"}]},
    {"key": "g2:12:Bh4", "idx": 1, "fen": "f2", "played_san": "Bh4", "best_san": "Be3",
     "bucket": "placement", "reason": "wrong square", "judge_overall": "refuted",
     "probes": [{"kind": "placement", "verdict": "refuted"}]},
    {"key": "g3:4:d5", "idx": 2, "fen": "f3", "played_san": "d5", "best_san": "e5",
     "bucket": "grading problem", "reason": "the Scandinavian", "judge_overall": "cannot_test",
     "probes": [{"kind": "untestable", "verdict": "cannot test"}]},
]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def db():
    d = _DB([dict(r) for r in REVIEWS])
    mod.set_db(d)
    yield d
    mod.set_db(None)


class TestItLivesOnTheGeometryGapsPage:
    def test_the_three_routes_exist(self):
        paths = {r.path for r in mod.router.routes}
        assert "/admin/geometry-gaps/claude-reasons/next" in paths
        assert "/admin/geometry-gaps/claude-reasons" in paths
        assert "/admin/geometry-gaps/claude-reasons/results" in paths

    def test_it_is_mounted(self):
        """A router nobody includes serves nothing. server.py mounts it beside
        the other geometry-gaps queues."""
        src = open(os.path.join(_BACKEND_ROOT, "server.py"), encoding="utf-8").read()
        assert "admin_claude_reasons" in src
        assert "admin_claude_reason_routes.set_db(db)" in src

    def test_it_uses_the_same_gate_as_the_other_queues(self):
        """GEOMETRY_REVIEWER_EMAILS is the only gate Farhan holds; this queue
        must be reachable through it and nothing wider."""
        import inspect
        src = inspect.getsource(mod)
        assert "require_geometry_reviewer" in src
        assert "require_admin" not in src.replace("require_geometry_reviewer", "")


class TestWhatNextServes:
    def test_confirmed_comes_first(self, db):
        out = _run(mod.next_claude_reason(judge=None, bucket=None, user=_User()))
        assert out["key"] == "g1:9:Nc6"
        assert out["queue"] == "claude"
        assert out["remaining"] == 3

    def test_the_page_gets_the_fields_the_board_needs(self, db):
        """The board and the line replay read these on every queue."""
        out = _run(mod.next_claude_reason(judge=None, bucket=None, user=_User()))
        for k in ("fen", "played_san", "best_san", "pv_after_played", "pv_after_best",
                  "reason", "probes", "judge_overall", "bucket"):
            assert k in out, k

    def test_a_ruled_position_is_skipped(self, db):
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "agree"}, _User()))
        out = _run(mod.next_claude_reason(judge=None, bucket=None, user=_User()))
        assert out["key"] == "g2:12:Bh4"
        assert out["ruled_count"] == 1

    def test_the_judge_filter_narrows_it(self, db):
        out = _run(mod.next_claude_reason(judge="cannot_test", bucket=None, user=_User()))
        assert out["key"] == "g3:4:d5"

    def test_when_everything_is_ruled_it_says_so(self, db):
        for r in REVIEWS:
            _run(mod.rule_claude_reason({"key": r["key"], "verdict": "unsure"}, _User()))
        with pytest.raises(HTTPException) as e:
            _run(mod.next_claude_reason(judge=None, bucket=None, user=_User()))
        assert e.value.status_code == 404


class TestRecordingAVerdict:
    def test_it_lands_in_its_own_collection(self, db):
        """Never caption_why_authoring or geometry_gap_rulings: those results
        endpoints read every row and would count these as theirs."""
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "disagree",
                                     "note": "it is the bishop pair"}, _User()))
        rows = db.claude_reason_rulings.rows
        assert len(rows) == 1
        assert rows[0]["verdict"] == "disagree"
        assert rows[0]["note"] == "it is the bishop pair"
        assert rows[0]["author_email"] == "mohit@example.com"

    def test_the_ruling_carries_what_was_judged(self, db):
        """So a reseed of the review set cannot orphan it, and the results
        read without a join."""
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "agree"}, _User()))
        row = db.claude_reason_rulings.rows[0]
        assert row["judge_overall"] == "confirmed"
        assert row["reason_reviewed"] == "ignores the pin"
        assert row["fen"] == "f1"

    def test_ruling_twice_updates_rather_than_duplicates(self, db):
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "agree"}, _User()))
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "disagree"}, _User()))
        assert len(db.claude_reason_rulings.rows) == 1
        assert db.claude_reason_rulings.rows[0]["verdict"] == "disagree"

    @pytest.mark.parametrize("payload,status", [
        ({"verdict": "agree"}, 400),                          # no key
        ({"key": "g1:9:Nc6", "verdict": "maybe"}, 400),       # not a verdict
        ({"key": "nope", "verdict": "agree"}, 404),           # not in the set
    ])
    def test_bad_input_is_refused(self, db, payload, status):
        with pytest.raises(HTTPException) as e:
            _run(mod.rule_claude_reason(payload, _User()))
        assert e.value.status_code == status

    def test_a_long_note_is_cut_not_rejected(self, db):
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "agree",
                                     "note": "x" * 5000}, _User()))
        assert len(db.claude_reason_rulings.rows[0]["note"]) == 2000


class TestResults:
    def test_the_grid_is_judge_then_human(self, db):
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "disagree",
                                     "note": "bishop pair"}, _User()))
        _run(mod.rule_claude_reason({"key": "g2:12:Bh4", "verdict": "agree"}, _User()))
        out = _run(mod.claude_reason_results(_User()))
        assert out["total"] == 2 and out["in_set"] == 3
        assert out["by_judge_then_verdict"] == {"confirmed": {"disagree": 1},
                                                "refuted": {"agree": 1}}

    def test_the_cell_that_matters_is_listed(self, db):
        """judge=confirmed x human=disagree is the one way the engine can be
        wrong while every number is right."""
        _run(mod.rule_claude_reason({"key": "g1:9:Nc6", "verdict": "disagree",
                                     "note": "bishop pair"}, _User()))
        out = _run(mod.claude_reason_results(_User()))
        assert out["disagreed_with_confirmed"] == [
            {"fen": "f1", "played_san": "Nc6", "reason": "ignores the pin",
             "note": "bishop pair"}]
