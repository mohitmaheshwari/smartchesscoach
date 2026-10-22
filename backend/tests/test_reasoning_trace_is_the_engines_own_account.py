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

    def test_a_step_that_finds_nothing_is_reported_as_finding_nothing(self):
        """Rewritten deliberately. It used to assert step 3 reported `ran:
        False` on this card, which is what made me tell Mohit the engine had
        fewer working steps than the docs claim. Step 3 IS performed on every
        card -- it just finds nothing here, and those are different facts."""
        steps = {s["step"]: s for s in reason_about(study()).steps()}
        assert steps[3]["performed"] is True
        assert steps[3]["found"] is False
        assert "found nothing" in steps[3]["note"]

    def test_step_eight_is_honest_about_having_nothing_to_say(self):
        """A move the engine cannot explain must not report a sentence."""
        rep = reason_about(MoveUnderStudy(
            fen_before=chess.STARTING_FEN, played_san="e4", best_san="d4",
            pv_played=["e5", "Nf3"], pv_best=[], cp_loss=120,
            mover_is_user=True))
        step8 = next(s for s in rep.steps() if s["step"] == 8)
        assert rep.resolved is False
        assert step8["found"] is False
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


class TestTheShippedCardLeads:
    """The first card Mohit opened on this page misled him, and this is why.

    Game 6f467b1f, ply 2: white played Qg3 when Qxg7 took a free pawn. The
    page showed the framework's answer -- `returns_home`, a SYMPTOM about a
    piece going back -- and he read it as what the system thinks:

        "this clearly takes up the undefended piece there at g7, so not sure
         what are you trying to tell me there?"
        "this was the easiest, one move thing and our detectors are pretty
         capable of seeing, why this was even asked??"

    He was right twice over. g7 was a free pawn, and the product had already
    said so. The SHIPPED caption for that card reads:

        "Opponent's Qg3 is a mistake -- they had Qxg7, grabbing your pawn on
         g7 for free. Play O-O -- it tucks your king away from the middle."

    So nothing was broken except this page, which led with a parallel engine
    that reaches no player. A note saying "not wired" sat right beside it and
    was nowhere near enough.

    The scope doc asked this exact question -- "does the caption on tab 1 come
    from the real caption layer? It must, or the page shows a sentence no
    player would see" -- and V1 answered it wrongly. One real card settled it.
    """

    def test_a_stored_render_is_read_as_the_shipped_card(self):
        from routes.admin_reasoning_trace import _shipped_card
        fen = "r2qk2r/5ppp/p1p1pn2/3p4/5BQ1/2P1P3/P1P2PPP/R4RK1 w kq - 1 13"
        analysis = {"decryption_v5_data": [
            {"fen_before": fen, "move_san": "Qg3", "caption_tier": "MID",
             "caption": "Opponent's Qg3 is a mistake - they had Qxg7, "
                        "grabbing your pawn on g7 for free.",
             "caption_explanation": {"provenance": ["R12_blunder"],
                                     "confidence": "verified"},
             "caption_verification": {"verdict": "pass"}},
        ]}
        got = _shipped_card(analysis, fen, "Qg3")
        assert got["found"] is True
        assert "for free" in got["caption"]
        assert got["verified"] == "pass"
        assert got["provenance"] == ["R12_blunder"]

    def test_it_matches_on_the_position_not_only_the_move_name(self):
        """A move name repeats across a game; fen_before identifies one ply."""
        from routes.admin_reasoning_trace import _shipped_card
        a = "8/8/8/8/8/8/8/K6k w - - 0 1"
        b = "8/8/8/8/8/8/7K/7k w - - 0 2"
        analysis = {"decryption_v5_data": [
            {"fen_before": a, "move_san": "Qg3", "caption": "the first one"},
            {"fen_before": b, "move_san": "Qg3", "caption": "the second one"},
        ]}
        assert _shipped_card(analysis, b, "Qg3")["caption"] == "the second one"

    def test_a_game_with_no_render_says_so_rather_than_guessing(self):
        from routes.admin_reasoning_trace import _shipped_card
        got = _shipped_card({}, "8/8/8/8/8/8/8/K6k w - - 0 1", "Ka2")
        assert got["found"] is False
        assert got["caption"] is None
        assert "no stored V5 render" in got["why"]

    def test_a_rendered_game_with_no_card_for_this_ply_says_that_instead(self):
        from routes.admin_reasoning_trace import _shipped_card
        got = _shipped_card(
            {"decryption_v5_data": [{"fen_before": "x", "move_san": "e4"}]},
            "8/8/8/8/8/8/8/K6k w - - 0 1", "Ka2")
        assert got["found"] is False
        assert "no card" in got["why"]


class TestAStepThatLooksAndFindsNothingSaysSo:
    """Mohit: "why step 3, 4 and 5 are not working?"

    They were working. Measured over 21,746 cards:

        framework ran                   20,172
        step 3/4 question ASKED         20,172   every card it ran on
        step 3/4 question ANSWERED         761    3.5%
        step 5 fact COMPUTED               761    3.5%   <- identical
        step 5 fact TRUE                   736    3.4%

    The display rendered "asked and found nothing" and "never performed" as
    the same "not reached", so a reader could only conclude the steps were
    dead. The page even contradicted itself: the questions table showed
    blocked_a_plan as ASKED while the steps table said step 3 was not
    reached.

    The identical 761 is the real finding and is kept visible: `in_the_way`
    is only computed inside q_blocked_a_plan's answer, so steps 3, 4 and 5
    are ONE question wearing three labels.
    """

    def test_a_step_that_was_asked_reports_performed(self):
        rep = reason_about(study())
        s3 = next(s for s in rep.steps() if s["step"] == 3)
        assert s3["performed"] is True, "it IS asked on every card"
        assert s3["found"] is False, "and it finds nothing on this one"
        assert "found nothing" in s3["note"]

    def test_the_steps_table_agrees_with_the_questions_table(self):
        """The contradiction that made this visible: if the question is listed
        as asked, the step must not claim it never ran."""
        rep = reason_about(study())
        asked = {a.concept for a in rep.asked}
        s3 = next(s for s in rep.steps() if s["step"] == 3)
        assert ("blocked_a_plan" in asked) == s3["performed"]

    def test_step_five_is_honest_that_it_rides_on_step_three(self):
        rep = reason_about(study())
        s5 = next(s for s in rep.steps() if s["step"] == 5)
        assert s5["performed"] is False
        assert "only computed when the plan question answers" in s5["note"]
        assert "blocked_a_plan" in s5["by"], (
            "the attribution must say the three share one question")

    def test_found_implies_performed_for_every_step(self):
        for pv in (("Bxd4", "Qe3", "Bf6"), ("Bxd4", "Kh1", "Bxc3")):
            for s in reason_about(study(pv=pv)).steps():
                if s["found"]:
                    assert s["performed"], s
