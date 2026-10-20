"""The loop report has to be able to FAIL, or it is decoration.

A coverage report that calls everything complete is worse than none: it
launders a broken loop into a green row. These pin the three judgements the
report makes on its own, each with the negative case beside the positive one.
"""
import importlib.util
import os

SPEC = importlib.util.spec_from_file_location(
    "coaching_loop_report",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "coaching_loop_report.py"),
)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def row(**kw):
    base = {
        "quality_id": "gap:x:y", "family": "x", "grade": "PLAN",
        "plan_users": 1, "content_id": "c", "has_grader": True,
        "puzzles": 10, "applied": 5, "missed": 5,
    }
    base.update(kw)
    return base


class TestFamilySplit:
    def test_a_gap_id_yields_the_family_that_focus_and_puzzles_key_on(self):
        assert report._family("gap:piece_safety:simple_hang") == "piece_safety"
        assert report._family("gap:missed_tactic:missed_fork") == "missed_tactic"

    def test_non_gap_ids_have_no_family_rather_than_a_guessed_one(self):
        # concept:* and tactic:* ids are not family-structured. Returning a
        # token here would silently join them to an unrelated puzzle pool.
        assert report._family("concept:endgame_opposition") is None
        assert report._family("tactic:fork_with_stored_payoff") is None
        assert report._family("gap:incomplete") is None


class TestLoopComplete:
    def test_all_five_stages_present_is_complete(self):
        complete, missing = report.loop_complete(row())
        assert complete and missing == ()

    def test_a_shadow_detector_breaks_stage_one(self):
        complete, missing = report.loop_complete(row(grade="SHADOW"))
        assert not complete and "1 detect" in missing

    def test_no_observed_application_breaks_stage_five(self):
        """The piece_safety-only state of the product today."""
        complete, missing = report.loop_complete(row(applied=0, missed=0))
        assert not complete and "5 observe" in missing

    def test_a_grader_alone_satisfies_teaching_without_contract_content(self):
        # Several gap families have a question + grading spec but no entry in
        # the contract index. Requiring both would report them as untaught.
        complete, _ = report.loop_complete(row(content_id=None, has_grader=True))
        assert complete

    def test_missing_stages_are_all_named_not_just_the_first(self):
        _, missing = report.loop_complete(
            row(grade="DISABLED", plan_users=0, puzzles=0, applied=0, missed=0))
        assert set(missing) == {"1 detect", "2 plan", "4 practise", "5 observe"}


class TestUnfitness:
    def test_a_concept_that_can_only_be_failed_is_flagged(self):
        """gap:piece_safety:simple_hang measured 0 applied / 607 missed."""
        assert report.unfitness(row(applied=0, missed=607)) == report.UNFIT_NO_SUCCESS

    def test_a_concept_that_can_only_succeed_is_also_flagged(self):
        # The mirror matters: congratulation-only detection cannot show decline.
        assert report.unfitness(row(applied=99, missed=0)) == report.UNFIT_NO_FAILURE

    def test_a_two_sided_concept_is_not_flagged(self):
        assert report.unfitness(row(applied=3595, missed=1535)) is None

    def test_silence_is_not_unfitness(self):
        # No observations at all is a stage-5 gap, reported there. Calling it
        # unfit as well would double-count one problem as two.
        assert report.unfitness(row(applied=0, missed=0)) is None
