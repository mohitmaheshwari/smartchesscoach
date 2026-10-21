"""The admin page must read the engine, never keep its own copy of the steps.

docs/reasoning_trace_admin_scope.md states the one design rule: the steps
shown on /admin/reasoning-trace are emitted by `reason_about`, not described
by the route or the page. The reason is that a page holding its own account of
the procedure is correct the day it is written and silently wrong the first
time a question is added -- and a page cannot fail a test for being stale.

So these tests pin the properties that make the page self-correcting:

  * every question in the registry appears in the trace, including the silent
    ones -- the dropped and silent rows are the whole point of the page;
  * every question has a recorded origin, so a new one cannot ship without
    saying where it came from;
  * the trace reports a step as NOT RUN when nothing runs it, rather than
    implying work the engine does not do.
"""
import json
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.admin_reasoning_trace import PROVENANCE_PATH, _arrow  # noqa: E402
from services.move_reasoning import (  # noqa: E402
    REGISTRY,
    THE_EIGHT_STEPS,
    MoveUnderStudy,
    reason_about,
)

# The loose-pawn card: d4 hangs, Rfd1 would hold it, Rae1 does not.
RAE1 = "r2qk2r/5ppp/p1p1pb2/3p4/3P4/2N2Q1P/PPP2PP1/R4RK1 w kq - 0 13"


def study(pv=("Bxd4", "Qe3", "Bf6"), played="Rae1", best="Rfd1", cp=188):
    return MoveUnderStudy(fen_before=RAE1, played_san=played, best_san=best,
                          pv_played=list(pv), pv_best=[], cp_loss=cp,
                          mover_is_user=True)


class TestTheTraceAccountsForEveryQuestion:
    def test_every_registry_question_appears(self):
        """A question that fires on nothing must still be listed as silent.
        engine_undoes_it has 4,650 findings and 30% survive, and no screen in
        this repo says so -- that is the gap this page closes."""
        rep = reason_about(study())
        assert {a.concept for a in rep.asked} == {q.concept for q in REGISTRY}

    def test_silent_questions_are_recorded_as_silent(self):
        rep = reason_about(study())
        silent = [a for a in rep.asked if a.verdict == "no answer"]
        assert silent, "on this card most questions have nothing to say"
        assert all(not a.answered for a in silent)

    def test_a_dropped_answer_carries_the_rule_s_own_reason(self):
        """Not a category name. The reason a reader wants is the sentence the
        rule itself produced."""
        rep = reason_about(study(pv=("Bxd4", "Kh1", "Bxc3")))
        dropped = [a for a in rep.asked if a.verdict == "dropped"]
        assert dropped
        assert any("not the story" in a.reason for a in dropped), \
            [a.reason for a in dropped]

    def test_kept_and_dropped_match_the_findings(self):
        """The trace is the same work, not a second opinion about it."""
        rep = reason_about(study())
        kept = {a.concept for a in rep.asked if a.verdict == "kept"}
        assert kept == {f.concept for f in rep.findings}


class TestTheStepsComeFromTheEngine:
    def test_all_eight_are_reported(self):
        rep = reason_about(study())
        assert [s["step"] for s in rep.steps()] == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_a_step_nothing_runs_is_reported_as_not_run(self):
        """Steps 3-5 are the plan questions. On this card no plan question
        answers, and the page must say so rather than imply it ran. If these
        ever read `ran` on every sample, the engine has fewer working steps
        than the documentation claims."""
        steps = {s["step"]: s for s in reason_about(study()).steps()}
        assert steps[3]["ran"] is False
        assert "no plan question answered" in steps[3]["note"]

    def test_step_eight_is_honest_about_having_nothing_to_say(self):
        """A move the engine cannot explain must not report a sentence."""
        rep = reason_about(MoveUnderStudy(
            fen_before=chess.STARTING_FEN, played_san="e4", best_san="d4",
            pv_played=["e5", "Nf3"], pv_best=[], cp_loss=120,
            mover_is_user=True))
        step8 = next(s for s in rep.steps() if s["step"] == 8)
        assert rep.resolved is False
        assert step8["ran"] is False
        assert "nothing survived" in step8["note"]

    def test_the_step_names_live_with_the_engine(self):
        """If this list moves into the page or the route, the page can drift.
        It is defined next to the code that performs the steps, on purpose."""
        assert len(THE_EIGHT_STEPS) == 8
        assert all(isinstance(n, int) and name for n, name, _ in THE_EIGHT_STEPS)


class TestProvenanceIsRecordedForEveryQuestion:
    @pytest.fixture(scope="class")
    def raw(self):
        return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    def test_no_question_ships_without_an_origin(self, raw):
        missing = [q.concept for q in REGISTRY if q.concept not in raw]
        assert not missing, (
            f"{missing} have no entry in question_provenance.json. A question "
            f"whose origin is not recorded cannot be argued with later.")

    def test_each_entry_says_how_it_was_found(self, raw):
        for q in REGISTRY:
            e = raw[q.concept]
            assert e.get("title"), q.concept
            assert e.get("found_by"), q.concept

    def test_recorded_sample_positions_are_real(self, raw):
        """A provenance board that does not replay is worse than no board: it
        presents a fabricated position as evidence."""
        for q in REGISTRY:
            e = raw[q.concept]
            for key in ("discovery_samples", "defect_samples"):
                for s in e.get(key) or []:
                    if not s.get("fen"):
                        continue          # recorded without a position, stated
                    board = chess.Board(s["fen"])
                    board.parse_san(s["played"])     # raises if not legal
                    if s.get("best"):
                        chess.Board(s["fen"]).parse_san(s["best"])

    def test_discovery_and_defect_samples_are_kept_apart(self, raw):
        """Presenting a defect as a discovery would rewrite history in the
        engine's favour, so the two lists never merge."""
        for q in REGISTRY:
            e = raw[q.concept]
            assert "discovery_samples" in e, q.concept
            assert "defect_samples" in e, q.concept


class TestTheArrowShapeMatchesTheBoard:
    def test_an_arrow_is_a_from_to_colour_triple(self):
        """LichessBoard takes [from, to, colour]. The first version of this
        returned an object, which draws nothing and reports no error."""
        assert _arrow(RAE1, "Rae1", "red") == ["a1", "e1", "red"]

    def test_an_illegal_move_draws_no_arrow(self):
        assert _arrow(RAE1, "Qxz9", "red") is None
        assert _arrow(RAE1, "", "green") is None
