"""The Why queue checker: a second agent's verdict decides whether a gate-passed
study goes live without a person (docs/why_queue_checker_scope.md)."""
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import why_queue_worker as worker  # noqa: E402
from services import why_queue, why_study  # noqa: E402

PASSED = {"passed": True, "no_lesson": False, "failures": []}
FAILED = {"passed": False, "no_lesson": False, "failures": ["x"]}
NO_LESSON = {"passed": True, "no_lesson": True, "failures": []}


@pytest.fixture
def flags(monkeypatch):
    def set_flags(*, auto=False, checker=False):
        monkeypatch.setattr(worker, "AUTO_PUBLISH", auto)
        monkeypatch.setattr(worker, "CHECKER_PUBLISH", checker)
    return set_flags


def test_checker_agree_publishes_only_with_the_flag(flags):
    flags(checker=False)
    assert worker.decide_status(PASSED, {"verdict": "agree"}) == "held_for_review"
    flags(checker=True)
    assert worker.decide_status(PASSED, {"verdict": "agree"}) == "published"


def test_checker_disagree_or_missing_waits_for_a_person(flags):
    flags(checker=True)
    assert worker.decide_status(PASSED, {"verdict": "disagree"}) == "held_for_review"
    assert worker.decide_status(PASSED, None) == "held_for_review"


def test_gate_failure_and_no_lesson_are_never_published_by_the_checker(flags):
    flags(checker=True)
    assert worker.decide_status(FAILED, {"verdict": "agree"}) == "held"
    assert worker.decide_status(NO_LESSON, None) == "no_lesson"


def test_models_are_named_and_different():
    assert worker.DEFAULT_MODEL == "claude-opus-5-5"
    assert worker.DEFAULT_CHECKER_MODEL == "claude-fable-5-1"
    assert worker.DEFAULT_MODEL != worker.DEFAULT_CHECKER_MODEL


def test_check_verdict_treats_anything_but_agree_as_disagree():
    assert why_study.check_verdict({"verdict": "agree", "problem": "", "own_reading": "r"})["verdict"] == "agree"
    for odd in ({"verdict": "Agree "}, ):
        assert why_study.check_verdict(odd)["verdict"] == "agree"
    for bad in ({"verdict": "unsure"}, {"verdict": ""}, {}, None):
        assert why_study.check_verdict(bad)["verdict"] == "disagree"


def test_check_prompt_carries_packet_then_study():
    text = why_study.check_prompt({"played_san": "e5", "better_san": "c3"},
                                  {"reason": "Their e5 does not win back the pawn.",
                                   "claims": [{"kind": "attacks", "label": "c3 hits d4", "subject": "c3",
                                               "target": "d4", "verified": True, "failure": None}]})
    assert text.index("The packet") < text.index("The colleague's study")
    assert "Their e5 does not win back the pawn." in text
    # The replay result is not shown: the checker judges the meaning, not the gate.
    assert "verified" not in text


def test_run_checker_failure_is_a_disagree(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("cli down")
    monkeypatch.setattr(worker, "run_claude", boom)
    out = worker.run_checker({"played_san": "e5"}, {"reason": "r", "claims": []}, cwd=tmp_path)
    assert out["verdict"] == "disagree" and "did not answer" in out["problem"]


def test_run_checker_passes_the_checker_model(monkeypatch, tmp_path):
    seen = {}

    def fake(system, user, schema, *, cwd, model=None):
        seen["model"], seen["schema"] = model, schema
        return {"answer": {"verdict": "agree", "problem": "", "own_reading": "c3 wins the pawn back"},
                "cost_usd": 0.1, "model": model}
    monkeypatch.setattr(worker, "run_claude", fake)
    out = worker.run_checker({}, {"reason": "r", "claims": []}, cwd=tmp_path)
    assert seen["model"] == worker.CHECKER_MODEL and seen["schema"] is why_study.CHECK_SCHEMA
    assert out["verdict"] == "agree" and out["own_reading"] == "c3 wins the pawn back"


def test_review_row_shows_the_checker_and_a_live_checker_publish():
    row = why_queue.review_row({
        "key": "k", "status": why_queue.PUBLISHED, "ruled_by": "checker", "reason": "r",
        "gate": {"passed": True, "failures": []}, "claims": [],
        "check": {"verdict": "agree", "problem": "", "own_reading": "c3 wins it back", "model": "claude-fable-5-1"},
    })
    checker = [p for p in row["probes"] if p["kind"] == "checker"]
    assert checker and checker[0]["verdict"].startswith("agree")
    assert "published by the checker" in row["bucket"]
