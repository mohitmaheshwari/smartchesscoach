"""A recommendation has to answer three questions.

A card that says "work on time management" and nothing else cannot be argued
with. Before this, the decision carried one free-text `evidence` line -- for a
repair candidate, the fixed sentence "I found this in several of your recent
games." The count that sentence rests on was computed two lines above it, to
pass the >=3 gate, and then thrown away. Nothing said why this activity rather
than another, and nothing said what would move us off the subject.

So every candidate now carries:
    why_subject    what in HIS play put this here
    why_activity   why review rather than teach, or the reverse
    change_signal  the observation that would change direction
    observed       the counts behind them, for the app and for an auditor

The three strings are player-facing and carry no numbers; `observed` carries
the numbers and is not rendered at the player.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import pytest

from services.personal_curriculum import (
    ContractViolation,
    CurriculumCandidate,
    CurriculumDestination,
    CurriculumJustification,
    CurriculumOutcome,
    EvidenceStatus,
    LessonCapability,
    StudentState,
    _JUSTIFICATION_TEXT,
    _observe_candidate,
    _repair_candidate,
    justify,
)


def _destination() -> CurriculumDestination:
    return CurriculumDestination(
        href="/training/pattern/piece_safety",
        medium="puzzles",
        capability=LessonCapability.GUIDED_PRACTICE,
        content_kind="concept",
        content_id="piece_safety",
        canonical_source="test",
    )


def _candidate(**over) -> CurriculumCandidate:
    base = dict(
        outcome=CurriculumOutcome.REPAIR,
        student_state=StudentState.LEARNING,
        title="Undefended pieces",
        reason="Check what can be taken before you move.",
        evidence_summary="I found this in several of your recent games.",
        evidence_status=EvidenceStatus.TRUSTWORTHY,
        destination=_destination(),
        evidence_owner="test",
    )
    base.update(over)
    return CurriculumCandidate(**base)


def test_every_outcome_has_registered_wording():
    """A new outcome must not be able to reach a player unexplained."""
    missing = [o for o in CurriculumOutcome if o not in _JUSTIFICATION_TEXT]
    assert not missing, f"outcomes with no justification wording: {missing}"


def test_a_candidate_without_one_is_given_one():
    candidate = _candidate()
    assert candidate.justification is not None
    assert candidate.justification.why_subject
    assert candidate.justification.why_activity
    assert candidate.justification.change_signal


def test_the_three_answers_reach_the_public_shape():
    payload = _candidate().public_dict()
    just = payload["justification"]
    assert set(just) == {"why_subject", "why_activity", "change_signal", "observed"}
    for key in ("why_subject", "why_activity", "change_signal"):
        assert just[key].strip(), key


def test_player_facing_text_carries_no_counts():
    """The numbers belong in `observed`, not in the sentence shown to him."""
    for outcome in CurriculumOutcome:
        why_subject, why_activity, change_signal = _JUSTIFICATION_TEXT[outcome]
        for text in (why_subject, why_activity, change_signal):
            assert not any(ch.isdigit() for ch in text), (outcome, text)


def test_the_activity_differs_by_outcome():
    """Review and teach must not be explained with the same sentence."""
    review = justify(CurriculumOutcome.REVIEW).why_activity
    expand = justify(CurriculumOutcome.EXPAND).why_activity
    repair = justify(CurriculumOutcome.REPAIR).why_activity
    assert len({review, expand, repair}) == 3


def test_blank_text_is_refused():
    with pytest.raises(ContractViolation):
        CurriculumJustification(
            why_subject="", why_activity="a", change_signal="b"
        )


def test_repair_carries_the_count_its_sentence_rests_on():
    # the count lives under baseline_metric; _focus_occurrence_count reads it
    # from there, not from the top level
    focus = {
        "topic_key": "piece_safety",
        "baseline_metric": {"occurrence_count": 7},
        "focus_id": "f1",
    }
    candidate = _repair_candidate(focus)
    assert candidate is not None
    observed = candidate.justification.observed
    assert observed["recent_occurrences"] == 7
    assert observed["topic_key"] == "piece_safety"
    # and the player sentence still says nothing numeric
    assert not any(ch.isdigit() for ch in candidate.justification.why_subject)


def test_observe_carries_how_many_games_are_still_wanted():
    candidate = _observe_candidate(2)
    observed = candidate.justification.observed
    assert observed["analyzed_games"] == 2
    assert observed["games_still_wanted"] == 3


def test_a_review_counts_games_and_does_not_claim_opportunities():
    """The review trigger is "games have been played", not "chances arose".

    Treating a game count as opportunity evidence is how a concept gets marked
    improved on games that never offered a chance to use it. The field is named
    for what was counted, and the opportunity slot is explicitly unknown.
    """
    candidate = _candidate(
        outcome=CurriculumOutcome.REVIEW,
        student_state=StudentState.CAN_DO_WITH_HELP,
        observed_evidence={
            "analyzed_games_since_lesson": 61,
            "opportunities_since_lesson": None,
            "lesson_id": "piece_safety",
            "counted_by": "learning_sessions",
        },
    )
    observed = candidate.justification.observed
    assert observed["analyzed_games_since_lesson"] == 61
    assert observed["opportunities_since_lesson"] is None
    assert "opportun" not in candidate.justification.why_subject.lower()


def test_a_supplied_justification_is_kept():
    mine = CurriculumJustification(
        why_subject="a", why_activity="b", change_signal="c", observed={"n": 1}
    )
    candidate = _candidate(justification=mine)
    assert candidate.justification is mine
