"""The expected answer must not sit in a fixed slot.

Before this, `_reason_choices` returned a hard-coded order in which the
expected answer was the FIRST option for every lesson kind:

    opening -> continues_plan     (first)
    trap    -> answers_threat     (first)
    concept -> keeps_piece_safe   (first)

A player who always clicked the top choice was always right, so the reason
question measured nothing at all.

The fix shuffles deterministically from the position identity rather than
randomly, so the same position always renders the same order -- a player
cannot reroll it by reloading, and a stored answer still means what it meant
when it was given.

A note on the approach: an earlier attempt (codex/piece-safety-lesson-hotfix)
swapped the expected answer out of slot 0 whenever the hash put it there.
That trades "always first" for "never first", which is just as learnable.
This shuffles uniformly and asserts the distribution below.
"""
import sys
from collections import Counter
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.personalized_lesson_adapter import _reason_choices  # noqa: E402

KINDS = {
    "opening": "continues_plan",
    "trap": "answers_threat",
    "concept": "keeps_piece_safe",
}


@pytest.mark.parametrize("kind,expected", sorted(KINDS.items()))
def test_the_expected_answer_is_not_always_first(kind, expected):
    positions = [f"position-{i}" for i in range(200)]
    slots = Counter(
        [c["id"] for c in _reason_choices(kind, expected_id=expected, seed=p)].index(expected)
        for p in positions
    )
    assert slots[0] > 0, "the expected answer never appears first -- 'never click first' now wins"
    assert len(slots) > 1, "the expected answer sits in one fixed slot"
    # No slot may carry the whole distribution.
    assert max(slots.values()) < len(positions), f"degenerate distribution: {dict(slots)}"


@pytest.mark.parametrize("kind,expected", sorted(KINDS.items()))
def test_the_order_is_stable_for_one_position(kind, expected):
    """A reload must not reroll the answer order."""
    a = _reason_choices(kind, expected_id=expected, seed="puzzle-42")
    for _ in range(5):
        assert _reason_choices(kind, expected_id=expected, seed="puzzle-42") == a


@pytest.mark.parametrize("kind,expected", sorted(KINDS.items()))
def test_different_positions_can_differ(kind, expected):
    orders = {
        tuple(c["id"] for c in _reason_choices(kind, expected_id=expected, seed=f"p{i}"))
        for i in range(50)
    }
    assert len(orders) > 1, "every position renders the same order"


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_opt_out_stays_last_and_choices_are_intact(kind):
    for seed in ("", "a", "b", "zzz"):
        got = _reason_choices(kind, expected_id=KINDS[kind], seed=seed)
        assert got[-1]["id"] == "not_sure", "the opt-out must stay last"
        assert len({c["id"] for c in got}) == len(got), "a choice was duplicated"
        assert all(c.get("label") for c in got), "a choice lost its label"
        assert KINDS[kind] in {c["id"] for c in got}, "the expected answer disappeared"


def test_no_seed_keeps_the_original_order():
    """Callers that pass no seed must be unaffected."""
    assert [c["id"] for c in _reason_choices("opening")] == [
        "continues_plan", "wins_now", "not_sure"]
