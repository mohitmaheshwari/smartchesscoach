"""Admission beyond piece_safety, and the ways it must refuse to.

Until 2026-10-20 `application_results_from_observations` admitted two
hardcoded observation shapes, both piece_safety, so every other concept's
evidence was dropped before it could become a LessonResult. That is why
lesson evidence existed for exactly two gap ids while four PLAN-grade
missed_tactic detectors and a PLAN-grade king_safety detector sat on real
users' plans producing nothing.

The danger in widening is not under-admitting, it is manufacturing successes.
A success has to be a positive observation; if the absence of a failure were
allowed to count, the application rate would become "moves where we noticed
nothing" and every concept would drift toward mastered. These tests pin that
boundary from both sides.
"""
from datetime import datetime, timezone

import pytest

from services.personal_curriculum import ApplicationOutcome, EvidenceSourceType
from services.review_learning_adapter import (
    _ADMITTED_SHAPES,
    application_results_from_observations,
)

WHEN = datetime(2026, 10, 20, tzinfo=timezone.utc)


def observation(**kw):
    base = {"schema_version": 20, "ply": 7}
    base.update(kw)
    return base


def results(*observations):
    return application_results_from_observations(
        game_id="game_test",
        observations=list(observations),
        occurred_at=WHEN,
        source_type=EvidenceSourceType.ORGANIC_GAME,
        assistance=(),
        assistance_measured=True,
    )


class TestMissesAreAdmitted:
    @pytest.mark.parametrize("pattern,subtype,quality_id", [
        ("missed_tactic", "missed_fork", "gap:missed_tactic:missed_fork"),
        ("missed_tactic", "missed_pin", "gap:missed_tactic:missed_pin"),
        ("missed_tactic", "missed_skewer", "gap:missed_tactic:missed_skewer"),
    ])
    def test_a_miss_becomes_evidence_against_its_own_gap_id(
        self, pattern, subtype, quality_id
    ):
        out = results(observation(missed_pattern=pattern, subtype=subtype))
        assert len(out) == 1
        assert out[0].detector_quality_id == quality_id
        assert out[0].application_outcome is ApplicationOutcome.MISSED
        # It must not be filed under the piece_safety identity it used to
        # borrow, or every concept's evidence lands on one skill.
        assert out[0].skill_id != "piece_safety_simple_hang"


class TestSuccessesRequireAPositiveObservation:
    @pytest.mark.parametrize("executed", [
        "knight_fork", "rook_fork", "bishop_fork", "pawn_fork",
    ])
    def test_executing_a_fork_is_an_applied_outcome(self, executed):
        out = results(observation(tactical_pattern_executed=executed))
        assert len(out) == 1
        assert out[0].detector_quality_id == "gap:missed_tactic:missed_fork"
        assert out[0].application_outcome is ApplicationOutcome.APPLIED

    def test_a_success_counted_from_a_wider_population_is_refused(self):
        """Why king_safety was withdrawn after the dry run.

        `responded_to_threat` fires for ANY threat answered, while the miss
        fires only for a king attack ignored, and a success row carries no
        threat-type label to narrow it with. Admitting the pair read 91%
        applied (3,142 against 315) on a concept nobody had improved at.
        """
        assert results(observation(responded_to_threat=True)) == []
        assert "ignored_king_attack" not in {s.subtype for s in _ADMITTED_SHAPES}

    def test_a_quiet_move_is_not_a_success(self):
        """The whole point. No positive observation, no evidence.

        A move that simply did not trip a detector proves nothing, and
        counting it would make the application rate a measure of our own
        blind spots.
        """
        assert results(observation(execution_quality="best")) == []
        assert results(observation(missed_pattern=None, subtype=None)) == []

    def test_a_flag_set_false_is_not_a_success(self):
        assert results(observation(responded_to_threat=False)) == []


class TestRefusals:
    def test_a_subtype_under_the_wrong_pattern_is_skipped_not_relabelled(self):
        # `missed_fork` arriving with pattern `piece_safety` is a disagreement
        # between two fields; inventing a gap id from it would assert a
        # concept neither field claims.
        assert results(
            observation(missed_pattern="piece_safety", subtype="missed_fork")
        ) == []

    @pytest.mark.parametrize("subtype", [
        "missed_mate", "missed_discovered_attack", "ignored_king_attack",
    ])
    def test_shapes_with_no_positive_observation_stay_out(self, subtype):
        """Held back deliberately, and the reason is recorded in the table.

        Admitting these would create concepts that can only ever be failed --
        the exact defect gap:piece_safety:simple_hang already demonstrates at
        0 applied against 607 missed.
        """
        for pattern in ("missed_tactic", "king_safety"):
            assert results(
                observation(missed_pattern=pattern, subtype=subtype)
            ) == []
        assert subtype not in {s.subtype for s in _ADMITTED_SHAPES}

    def test_an_old_schema_observation_is_still_rejected(self):
        assert results(
            observation(schema_version=15, missed_pattern="missed_tactic",
                        subtype="missed_fork")
        ) == []

    def test_an_observation_without_a_ply_is_rejected(self):
        assert results(
            observation(ply=0, missed_pattern="missed_tactic",
                        subtype="missed_fork")
        ) == []


class TestPieceSafetyIsUnchanged:
    def test_simple_hang_keeps_its_original_identity_and_outcome(self):
        out = results(
            observation(missed_pattern="piece_safety", subtype="simple_hang")
        )
        assert len(out) == 1
        assert out[0].detector_quality_id == "gap:piece_safety:simple_hang"
        assert out[0].skill_id == "piece_safety_simple_hang"
        assert out[0].application_outcome is ApplicationOutcome.MISSED


class TestEveryAdmittedShapeIsTwoSided:
    def test_every_shape_declares_a_positive_observation(self):
        """Structural guard: a miss-only shape cannot be added.

        This is what stops the next person adding a concept that can only be
        failed -- it would look like coverage and measure nothing, which is
        gap:piece_safety:simple_hang's defect at 0 applied / 607 missed.
        """
        for shape in _ADMITTED_SHAPES:
            assert shape.applied_values, shape
