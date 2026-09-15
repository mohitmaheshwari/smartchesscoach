from __future__ import annotations

from collections import Counter

import pytest

from services.deterministic_choice_order import (
    DeterministicChoiceOrderError,
    order_deterministic_choices,
)


CHOICES = (
    {"id": "proved", "label": "The line is proved."},
    {"id": "guess", "label": "The line is only a guess."},
)


def test_choice_order_is_stable_but_not_fixed_to_one_answer_slot():
    one = order_deterministic_choices(CHOICES, seed="position-17")
    assert order_deterministic_choices(CHOICES, seed="position-17") == one
    slots = Counter(
        next(
            index
            for index, choice in enumerate(
                order_deterministic_choices(CHOICES, seed=f"position-{number}")
            )
            if choice["id"] == "proved"
        )
        for number in range(200)
    )
    assert set(slots) == {0, 1}
    assert max(slots.values()) < 200


def test_trailing_opt_out_remains_last_without_affecting_candidate_order():
    choices = (*CHOICES, {"id": "not_sure", "label": "I am not sure."})
    ordered = order_deterministic_choices(
        choices,
        seed="position-18",
        trailing_ids=("not_sure",),
    )
    assert ordered[-1]["id"] == "not_sure"
    assert {choice["id"] for choice in ordered} == {
        "proved",
        "guess",
        "not_sure",
    }


@pytest.mark.parametrize(
    "choices,seed",
    [
        (({"id": "same"}, {"id": "same"}), "position"),
        (({"id": ""}, {"id": "other"}), "position"),
        (CHOICES, ""),
    ],
)
def test_invalid_choice_identity_fails_closed(choices, seed):
    with pytest.raises(DeterministicChoiceOrderError):
        order_deterministic_choices(choices, seed=seed)
