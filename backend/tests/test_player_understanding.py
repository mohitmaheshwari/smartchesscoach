"""The app needs the player understanding as data, not as a document.

The decision could not consult what the player had shown, because nothing
assembled it at player level: `personalized_teaching.profile` is built only
when the destination is a personalized lesson, so a clock focus left it null
and the chooser had nothing to read.

The four things it has to answer, and the traps in each:

  strengths / difficulties   from user_active_focus, which carries a metric and
                             a cohort comparison and NO game references -- so
                             supporting_games is empty and says why
  shown without help         assistance is a list, a flag, or a help request;
                             any of them means the attempt was assisted
  taught but untested        taught and never answered unassisted. That is an
                             untested claim, not a failure
  current goal               carried from the decision with its justification

And one thing it must NOT answer: mastery. Every surviving `mastered_at` on
this account sits on a concept the product never showed him, so the stamps are
not read at all.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.personal_teaching_profile import build_player_understanding


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    async def to_list(self, _limit):
        return list(self._rows)


class _Coll:
    def __init__(self, rows):
        self._rows = rows

    def find(self, query, _proj=None):
        rows = self._rows
        if "status" in query:
            rows = [r for r in rows if r.get("status") == query["status"]]
        return _Cursor(rows)


class _Db:
    def __init__(self, focus=(), sessions=()):
        self.user_active_focus = _Coll(list(focus))
        self.learning_sessions = _Coll(list(sessions))


def _session(skill, attempts, *, kind="concept", updated="2026-10-01"):
    return {
        "skill_id": skill,
        "content_kind": kind,
        "updated_at": updated,
        "events": [{"event_type": "answer_submitted", "attempt": a} for a in attempts],
    }


def _build(db, decision=None):
    return asyncio.get_event_loop().run_until_complete(
        build_player_understanding(db, "u1", decision=decision)
    )


def test_strengths_and_difficulties_split_on_type():
    db = _Db(focus=[
        {"type": "strength", "status": "active", "label": "Low blunder rate",
         "user_value": 0.04, "cohort_mean": 0.07, "metric_key": "blunder_rate"},
        {"type": "weakness", "status": "active", "label": "Hanging pieces",
         "user_value": 0.3, "cohort_mean": 0.1, "metric_key": "piece_safety"},
        {"type": "weakness", "status": "resolved", "label": "Old thing"},
    ])
    out = _build(db)
    assert [s["label"] for s in out["strengths"]] == ["Low blunder rate"]
    assert [d["label"] for d in out["difficulties"]] == ["Hanging pieces"]


def test_focus_rows_do_not_pretend_to_have_game_references():
    db = _Db(focus=[{"type": "weakness", "status": "active", "label": "x"}])
    out = _build(db)
    assert out["difficulties"][0]["supporting_games"] == []
    assert any("game references" in limit for limit in out["limits"])


def test_an_unassisted_correct_answer_counts_as_shown_without_help():
    db = _Db(sessions=[_session("piece_safety", [
        {"correct": True},
        {"correct": False},
    ])])
    out = _build(db)
    assert [r["skill_id"] for r in out["shown_without_help"]] == ["piece_safety"]
    assert out["shown_without_help"][0]["unassisted_correct"] == 1
    assert out["shown_without_help"][0]["unassisted_attempts"] == 2


def test_help_in_any_of_its_three_shapes_makes_an_attempt_assisted():
    for assisted in (
        {"correct": True, "assistance": ["hint"]},
        {"correct": True, "requested_help": ["show_on_board"]},
        {"correct": True, "assistance": "hint"},
    ):
        db = _Db(sessions=[_session("skill_x", [assisted])])
        out = _build(db)
        assert out["shown_without_help"] == [], assisted
        assert [r["skill_id"] for r in out["only_with_help"]] == ["skill_x"], assisted


def test_taught_and_never_answered_unassisted_is_untested_not_failed():
    db = _Db(sessions=[_session("opening_caro_kann_black", [
        {"correct": False, "assistance": ["hint"]},
    ])])
    out = _build(db)
    assert [r["skill_id"] for r in out["untested"]] == ["opening_caro_kann_black"]
    assert any("not evidence of failure" in limit for limit in out["limits"])


def test_a_session_with_no_attempts_is_still_taught_and_untested():
    db = _Db(sessions=[_session("geometry_diagonal_lines", [])])
    out = _build(db)
    assert [r["skill_id"] for r in out["taught"]] == ["geometry_diagonal_lines"]
    assert [r["skill_id"] for r in out["untested"]] == ["geometry_diagonal_lines"]
    assert out["taught"][0]["attempts"] == 0


def test_attempts_are_read_from_the_events_and_not_a_collection():
    """`lesson_attempts` exists and is empty; anything reading it finds zero."""
    db = _Db(sessions=[{
        "skill_id": "piece_safety",
        "updated_at": "2026-10-01",
        "events": [
            {"event_type": "lesson_started"},
            {"event_type": "answer_submitted", "attempt": {"correct": True}},
        ],
    }])
    out = _build(db)
    assert out["taught"][0]["attempts"] == 1


def test_no_mastery_claim_is_made_anywhere():
    db = _Db(sessions=[_session("piece_safety", [{"correct": True}])])
    out = _build(db)
    blob = repr(out).lower()
    assert "mastered" not in blob.replace("mastery stamps are not read", "")
    assert "reliable" not in blob


def test_the_current_goal_carries_its_justification():
    decision = {"primary": {
        "title": "Time management",
        "outcome": "repair",
        "justification": {
            "why_subject": "Your clock is ending these games, not your moves.",
            "why_activity": "This one is not a lesson.",
            "change_signal": "A control you can finish takes this off the list.",
            "observed": {"recent_occurrences": 231},
        },
    }}
    out = _build(_Db(), decision=decision)
    goal = out["current_goal"]
    assert goal["title"] == "Time management"
    assert goal["why_activity"] == "This one is not a lesson."
    assert goal["observed"]["recent_occurrences"] == 231


def test_an_empty_player_says_so_rather_than_inventing_sections():
    out = _build(_Db())
    assert out["strengths"] == [] and out["difficulties"] == []
    assert out["taught"] == [] and out["current_goal"] is None
    assert any("No learning sessions" in limit for limit in out["limits"])
    assert any("No active focus rows" in limit for limit in out["limits"])


def test_every_section_names_where_it_came_from():
    db = _Db(
        focus=[{"type": "strength", "status": "active", "label": "x"}],
        sessions=[_session("piece_safety", [{"correct": True}])],
    )
    out = _build(db)
    assert out["strengths"][0]["counted_by"] == "user_active_focus"
    assert out["taught"][0]["counted_by"] == "learning_sessions.events[].attempt"
    assert "user_active_focus" in out["counted_by"]
