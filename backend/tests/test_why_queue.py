"""The Why queue: what the route stores when the button finds nothing, what it
shows when a study is published, and how a human's ruling moves a study.

No engine, no Mongo: a small motor-shaped stand-in that understands the three
update operators the service uses.
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

from routes import admin_claude_reasons as admin  # noqa: E402
from services import why_queue as wq  # noqa: E402

FEN = "rn2kbnr/pbp1pppp/1p2q3/8/8/2N2P2/PPPPB1PP/R1BQK1NR w KQkq - 1 6"


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    async def to_list(self, length=None):
        return list(self._rows)


class _Collection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.indexes = []

    def _match(self, query):
        def one(r, k, v):
            if isinstance(v, dict) and "$in" in v:
                return r.get(k) in v["$in"]
            return r.get(k) == v
        return [r for r in self.rows if all(one(r, k, v) for k, v in (query or {}).items())]

    async def create_index(self, *a, **k):
        self.indexes.append(a)

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
        m = self._match(query)
        if m:
            row = m[0]
        elif upsert:
            row = dict(query)
            row.update(update.get("$setOnInsert") or {})
            self.rows.append(row)
        else:
            return
        row.update(update.get("$set") or {})
        for k, v in (update.get("$addToSet") or {}).items():
            row.setdefault(k, [])
            if v not in row[k]:
                row[k].append(v)
        for k, v in (update.get("$inc") or {}).items():
            row[k] = row.get(k, 0) + v


class _DB:
    def __init__(self):
        self.why_queue = _Collection()
        self.why_reasons = _Collection()
        self.claude_reason_reviews = _Collection()
        self.claude_reason_rulings = _Collection()

    def __getitem__(self, name):
        return getattr(self, name)


class _User:
    user_id = "u_mohit"
    email = "mohit@example.com"


def _run(coro):
    # A fresh loop each time: run after the other why/reasoning files, the
    # module-level loop was already closed and every test here failed with
    # "There is no current event loop" (16 of 17, 2026-11-05); alone it passed.
    return asyncio.run(coro)


def _nothing(reason="no_mechanism"):
    return {"found": False, "reason": reason, "better_move": "d4",
            "differential": {"engine": "differential", "found": False, "reason": reason, "class": "mistake",
                             "gap_cp": 165, "better_move": "d4"}}


def _ask(db, out, **over):
    kw = dict(fen_before=FEN, played_san="b3", game_id="g1", move_number=6, opponent=True, user_id="u_x",
              stored_best="d4", stored_class="mistake", rating=700, differential=out.get("differential"))
    kw.update(over)
    return _run(wq.on_nothing_found(db, out, **kw))


class TestTheKey:
    def test_one_key_per_position_not_per_game(self):
        a = wq.position_key(FEN, "b3")
        b = wq.position_key(FEN.replace(" 1 6", " 7 12"), "b3")
        assert a == b
        assert wq.position_key(FEN, "d4") != a


class TestQueueing:
    def test_a_silent_click_queues_the_position_and_tells_the_card(self):
        db = _DB()
        out = _ask(db, _nothing())
        assert out["found"] is False
        assert out["study"] == {"state": "studying", "text": wq.STUDYING_LINE}
        row = db.why_queue.rows[0]
        assert row["status"] == wq.QUEUED and row["played_san"] == "b3"
        assert row["requests"][0]["game_id"] == "g1" and row["requests"][0]["side"] == "opponent"
        assert row["differential"]["better_move"] == "d4"

    def test_the_same_position_from_another_game_adds_an_asker_not_a_row(self):
        db = _DB()
        _ask(db, _nothing())
        _ask(db, _nothing(), game_id="g2", move_number=9, opponent=False, user_id="u_y")
        assert len(db.why_queue.rows) == 1
        assert [r["game_id"] for r in db.why_queue.rows[0]["requests"]] == ["g1", "g2"]

    def test_the_engines_own_choice_is_not_queued(self):
        db = _DB()
        for reason in ("engine_choice", "no_gap", "engine_error"):
            out = _ask(db, _nothing(reason))
            assert "study" not in out
        assert db.why_queue.rows == []

    def test_a_running_study_still_reads_as_studying(self):
        db = _DB()
        _ask(db, _nothing())
        db.why_queue.rows[0]["status"] = wq.RUNNING
        out = _ask(db, _nothing())
        assert out["study"]["state"] == "studying"

    def test_a_queue_failure_never_breaks_the_button(self):
        class _Broken(_DB):
            def __getitem__(self, name):
                raise RuntimeError("mongo down")
        out = _ask(_Broken(), _nothing())
        assert out["found"] is False and "study" not in out


def _reason(status, **over):
    row = {"key": wq.position_key(FEN, "b3"), "fen_before": FEN, "played_san": "b3", "better_san": "d4",
           "side": "opponent", "status": status, "created_at": "2026-11-02T10:00:00+00:00",
           "reason": "After b3, Qg6 attacks the g2 pawn and nothing guards it. d4 opens the queen's road.",
           "claims": [{"kind": "attacks", "label": "the queen on g6 attacks g2", "after": ["b3", "Qg6"],
                       "subject": "g6", "target": "g2", "verified": True, "failure": None}],
           "gate": {"passed": True, "failures": []}, "requests": [{"game_id": "g1", "move_number": 6}]}
    row.update(over)
    return row


class TestWhatTheCardGets:
    def test_a_published_study_is_the_answer(self):
        db = _DB()
        db.why_reasons.rows.append(_reason(wq.PUBLISHED, published_at="2026-11-02T11:00:00+00:00"))
        out = _ask(db, _nothing())
        assert out["found"] is True and out["engine"] == "studied"
        assert out["text"].startswith("After b3, Qg6 attacks")
        assert out["better_move"] == "d4" and out["arrows"] == [{"from": "g6", "to": "g2"}]
        assert out["study"]["state"] == "published"
        assert db.why_queue.rows == []          # nothing re-queued

    def test_a_study_waiting_for_a_human_reads_as_studying_and_shows_no_text(self):
        db = _DB()
        db.why_reasons.rows.append(_reason(wq.HELD_FOR_REVIEW))
        out = _ask(db, _nothing())
        assert out["found"] is False
        assert out["study"]["state"] == "studying"
        assert "Qg6" not in str(out)

    def test_a_gate_failed_study_also_reads_as_studying(self):
        db = _DB()
        db.why_reasons.rows.append(_reason(wq.HELD, gate={"passed": False, "failures": ["g2 is defended"]}))
        out = _ask(db, _nothing())
        assert out["study"]["state"] == "studying" and out["found"] is False

    def test_no_lesson_is_said_honestly(self):
        db = _DB()
        db.why_reasons.rows.append(_reason(wq.NO_LESSON, reason=None, no_lesson_why="just worse"))
        out = _ask(db, _nothing())
        assert out["study"] == {"state": "no_lesson", "text": wq.NO_LESSON_LINE}

    def test_a_rejected_study_adds_nothing(self):
        db = _DB()
        db.why_reasons.rows.append(_reason(wq.REJECTED))
        out = _ask(db, _nothing())
        assert "study" not in out and db.why_queue.rows == []


class TestTheReviewTab:
    @pytest.fixture
    def db(self):
        d = _DB()
        admin.set_db(d)
        yield d
        admin.set_db(None)

    def test_a_held_study_is_served_first_in_the_panels_shape(self, db):
        db.claude_reason_reviews.rows.append(
            {"key": "seed:1", "idx": 1, "fen": "f", "played_san": "Nc6", "best_san": "h6",
             "judge_overall": "confirmed", "reason": "seeded", "probes": []})
        db.why_reasons.rows.append(_reason(wq.HELD_FOR_REVIEW))
        row = _run(admin.next_claude_reason(judge=None, bucket=None, user=_User()))
        assert row["source"] == "why_queue" and row["queue"] == "claude"
        assert row["judge_overall"] == "confirmed" and row["best_san"] == "d4"
        assert row["probes"][0]["verdict"] == "passed"
        assert row["bucket"].startswith("why queue")

    def test_the_reviewer_sees_how_it_reads(self, db):
        db.why_reasons.rows.append(_reason(
            wq.HELD_FOR_REVIEW,
            readability={"sentences": 3, "words": 41, "longest_sentence_words": 17, "hard_words": ["undefended"]}))
        row = _run(admin.next_claude_reason(judge=None, bucket=None, user=_User()))
        plain = [p for p in row["probes"] if p["kind"] == "readability"]
        assert plain and "17 words" in plain[0]["verdict"] and "undefended" in plain[0]["verdict"]

    def test_a_gate_failed_study_reads_refuted_and_names_the_failure(self, db):
        db.why_reasons.rows.append(_reason(
            wq.HELD, gate={"passed": False, "failures": ["the queen on g6 attacks g2: g2 is defended"]},
            claims=[{"kind": "attacks", "label": "the queen on g6 attacks g2", "verified": False,
                     "failure": "g2 is defended"}]))
        row = _run(admin.next_claude_reason(judge=None, bucket=None, user=_User()))
        assert row["judge_overall"] == "refuted"
        assert "g2 is defended" in row["bucket"]
        assert row["probes"][0]["verdict"].startswith("FAILED")

    def test_agree_publishes_and_disagree_rejects(self, db):
        db.why_reasons.rows.append(_reason(wq.HELD_FOR_REVIEW))
        key = db.why_reasons.rows[0]["key"]
        out = _run(admin.rule_claude_reason({"key": key, "verdict": "agree"}, user=_User()))
        assert out["study_status"] == wq.PUBLISHED
        assert db.why_reasons.rows[0]["status"] == wq.PUBLISHED and db.why_reasons.rows[0]["published_at"]
        assert db.claude_reason_rulings.rows[0]["source"] == "why_queue"
        # ruled rows leave the queue
        with pytest.raises(HTTPException):
            _run(admin.next_claude_reason(judge=None, bucket=None, user=_User()))
        db.why_reasons.rows.append(_reason(wq.HELD_FOR_REVIEW, key="other", fen_before=FEN.replace("b3", "")))
        out = _run(admin.rule_claude_reason({"key": "other", "verdict": "disagree", "note": "not the lesson"},
                                            user=_User()))
        assert out["study_status"] == wq.REJECTED
        assert db.why_reasons.rows[1]["ruling_note"] == "not the lesson"

    def test_results_count_the_live_queue(self, db):
        db.why_reasons.rows.append(_reason(wq.PUBLISHED))
        db.why_reasons.rows.append(_reason(wq.HELD, key="k2"))
        out = _run(admin.claude_reason_results(user=_User()))
        assert out["why_queue"]["published"] == 1 and out["why_queue"]["held"] == 1

    def test_the_seeded_set_still_rules_as_before(self, db):
        db.claude_reason_reviews.rows.append(
            {"key": "seed:1", "idx": 1, "fen": "f", "played_san": "Nc6", "best_san": "h6",
             "judge_overall": "confirmed", "reason": "seeded", "probes": []})
        out = _run(admin.rule_claude_reason({"key": "seed:1", "verdict": "agree"}, user=_User()))
        assert "study_status" not in out
        assert db.claude_reason_rulings.rows[0]["source"] == "seeded"
