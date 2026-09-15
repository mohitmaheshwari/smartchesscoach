"""One stable ordering rule for answer-bearing coaching choices.

The order is derived from the position/evidence identity rather than process
randomness. Reloading cannot reroll an answer and no coaching surface needs to
know which choice is correct in order to arrange the visible options.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence


class DeterministicChoiceOrderError(ValueError):
    """Raised when an answer choice cannot be ordered without ambiguity."""


def order_deterministic_choices(
    choices: Sequence[Mapping[str, Any]],
    *,
    seed: str,
    trailing_ids: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Return a stable hash order while keeping opt-out choices last.

    The seed must identify the position or immutable evidence packet. Choice
    correctness is deliberately not an input: the same rule works for both
    answer-bearing and answer-free clients without leaking the key.
    """
    normalized_seed = str(seed or "").strip()
    if not normalized_seed:
        raise DeterministicChoiceOrderError("choice-order seed is required")
    normalized = [dict(choice) for choice in choices]
    ids = [str(choice.get("id") or "").strip() for choice in normalized]
    if any(not choice_id for choice_id in ids) or len(ids) != len(set(ids)):
        raise DeterministicChoiceOrderError(
            "choice ids must be non-empty and unique"
        )
    trailing = tuple(str(value or "").strip() for value in trailing_ids)
    if any(not value for value in trailing) or len(trailing) != len(set(trailing)):
        raise DeterministicChoiceOrderError(
            "trailing choice ids must be non-empty and unique"
        )
    unknown_trailing = set(trailing) - set(ids)
    if unknown_trailing:
        raise DeterministicChoiceOrderError(
            f"unknown trailing choice ids: {sorted(unknown_trailing)}"
        )

    trailing_set = set(trailing)
    ordered = sorted(
        (
            choice
            for choice in normalized
            if str(choice["id"]).strip() not in trailing_set
        ),
        key=lambda choice: hashlib.sha256(
            f"{normalized_seed}:{str(choice['id']).strip()}".encode("utf-8")
        ).hexdigest(),
    )
    by_id = {str(choice["id"]).strip(): choice for choice in normalized}
    ordered.extend(by_id[choice_id] for choice_id in trailing)
    return ordered


__all__ = [
    "DeterministicChoiceOrderError",
    "order_deterministic_choices",
]
