"""The picker may not choose a topic the plan surface will refuse.

Two halves disagreed. The ranking chose whatever the player's games showed
most of; the plan surface only accepts topics whose detector is graded
`plan`. Nothing errored when they disagreed -- a focus was written, and every
reader quietly refused it.

The visible cost was the worst possible. The Home page treats "no usable
focus" as "I have not seen you play yet", so it told people with analysed
games to go and play a game or two. Measured on production 2026-09-17:

    active weakness focuses        54
    refused by the plan gate       11   (all with analysed games)
    plan-graded detectors          1    gap:piece_safety:destination_safety_exact

One of the 11 was stamped perfectly and still refused: `threat_awareness` is
only graded `shadow`. The other 10 predate the stamping and carry no quality
id at all. `scripts/repair_unplannable_focuses.py` clears both; this file
stops the picker creating more.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import detector_quality as dq  # noqa: E402


def test_only_plan_graded_topics_are_plannable():
    """`piece_safety` is the one topic with a plan-graded detector today.

    If this starts failing because another topic became plannable, that is
    good news -- update the list. It failing the other way means a detector
    lost its grade and every user on that focus is about to go quiet.
    """
    assert dq.topic_can_be_planned("piece_safety")
    for topic in (
        "threat_awareness",
        "missed_tactic",
        "tactical_oversight",
        "punish_blunders",
        "king_safety",
        "calculation_depth",
    ):
        assert not dq.topic_can_be_planned(topic), topic


def test_plannable_agrees_with_the_gate_that_reads_the_document():
    """The picker's question and the reader's question must have one answer.

    `topic_can_be_planned` is asked before writing;
    `focus_document_is_authorized` is asked on every read. If they can
    disagree, the bug comes straight back in a new shape.
    """
    for topic in ("piece_safety", "threat_awareness", "missed_tactic"):
        quality_id = dq.gap_quality_id(topic, None)
        subtypes = dq.authorized_gap_subtypes(topic)
        # A topic is plannable exactly when it has a plan-graded subtype.
        assert dq.topic_can_be_planned(topic) == bool(subtypes), topic
        # And the wildcard id alone is never enough to pass the read gate.
        if not subtypes:
            assert not dq.focus_document_is_authorized(
                {"detector_quality_id": quality_id}
            ), topic


def test_a_document_with_a_plan_graded_id_is_authorized():
    quality_id = dq.gap_quality_id("piece_safety", "destination_safety_exact")
    assert dq.focus_document_is_authorized({"detector_quality_id": quality_id})


def test_the_picker_filters_candidates_before_ranking_them():
    """In the source, because the alternative is a live database.

    The filter has to sit between building the candidate list and choosing
    the winner. Putting it after the choice would mean picking a topic and
    then discarding it, leaving the user with nothing when a usable
    second-best existed.
    """
    src = io.open(
        BACKEND / "services" / "primary_weakness_picker.py", encoding="utf-8"
    ).read()
    assert "topic_can_be_planned" in src, "the picker must ask the question"

    build = src.index("candidates: List[Dict[str, Any]] = []")
    filt = src.index("topic_can_be_planned(c[\"topic\"])", build)
    cooldown = src.index("# Cooldown filter", build)
    winner = src.index("winner = fresh[0]", build)
    assert build < filt < cooldown < winner, (
        "the plannable filter must run before the winner is chosen"
    )


def test_the_cooldown_filter_reads_the_filtered_list():
    """A one-word slip here would silently restore the old behaviour."""
    src = io.open(
        BACKEND / "services" / "primary_weakness_picker.py", encoding="utf-8"
    ).read()
    assert "for c in plannable:" in src, (
        "cooldown must iterate the plannable list, not the raw candidates"
    )


def test_what_we_could_not_coach_is_recorded_rather_than_dropped():
    """"Nothing scored" and "plenty scored, none of it usable" are different
    situations, and only one of them means the user is fine.
    """
    src = io.open(
        BACKEND / "services" / "primary_weakness_picker.py", encoding="utf-8"
    ).read()
    assert 'winner["not_plannable"]' in src
    assert '"not_plannable": picked.get("not_plannable", [])' in src, (
        "it has to reach the stored document, not just the in-memory winner"
    )


def test_enforcement_off_plans_everything():
    """With the gate disabled, `focus_document_is_authorized` accepts an
    unstamped document, so the picker must not be stricter than the reader.
    """
    import os
    from unittest import mock

    with mock.patch.dict(os.environ, {"DETECTOR_QUALITY_GATE_ENFORCED": "false"}):
        # Re-read through the module's own accessor rather than a cached bool.
        if not dq.enforcement_enabled():
            assert dq.topic_can_be_planned("threat_awareness")
            assert dq.focus_document_is_authorized({})
