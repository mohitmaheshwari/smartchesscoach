"""A pattern page must announce the pattern the player asked for, and find its puzzles.

/training/pattern/opening_knowledge rendered "Let's Practise Calculate The
Reply" over "No puzzles ... yet", while 293 opening_knowledge positions sat in
the pool. Two bugs, one screen: the label collapsed to a binary, and the
pattern was mapped to a pattern_type that does not exist in the data.
"""
import pytest

from services.coaching_puzzle_service import (
    DEFAULT_COACHING,
    PATTERN_COACHING,
    WEAKNESS_TO_PATTERN_TYPES,
)

# Every topic primary_weakness_picker can write.
WRITABLE = [
    "piece_safety", "king_safety", "missed_tactic", "tactical_oversight",
    "calculation_depth", "piece_activity", "pawn_structure",
    "opening_knowledge", "endgame_technique", "threat_awareness",
    "punish_blunders",
]


@pytest.mark.parametrize("pattern", [p for p in WRITABLE if p != "calculation_depth"])
def test_no_pattern_is_announced_as_calculate_the_reply(pattern):
    """Only calculation_depth may be called "Calculate the Reply"."""
    coaching = PATTERN_COACHING.get(pattern) or DEFAULT_COACHING
    assert coaching["lesson"] != "Calculate the Reply", (
        f"{pattern} announces itself as a calculation lesson"
    )


def test_calculation_depth_keeps_its_own_label():
    assert PATTERN_COACHING["calculation_depth"]["lesson"] == "Calculate the Reply"


@pytest.mark.parametrize("pattern", WRITABLE)
def test_every_pattern_has_coaching_copy_that_is_plain_ascii(pattern):
    coaching = PATTERN_COACHING.get(pattern) or DEFAULT_COACHING
    for field in ("lesson", "what_to_look_for", "why_this_matters"):
        assert coaching.get(field), f"{pattern} missing {field}"
        assert coaching[field].isascii(), f"{pattern}.{field} has non-ascii text"


@pytest.mark.parametrize("pattern", [
    "opening_knowledge", "pawn_structure", "piece_activity", "endgame_technique",
])
def test_pattern_asks_for_its_own_pattern_type_first(pattern):
    """These four all mapped ONLY to "positional", which has no rows at all.

    The extractor stores the literal pattern name, so the query has to ask for
    that. Mapping solely to an alias that matches nothing is indistinguishable
    from "this player has no puzzles".
    """
    mapped = WEAKNESS_TO_PATTERN_TYPES.get(pattern) or []
    assert mapped, f"{pattern} has no pattern types"
    assert mapped[0] == pattern, (
        f"{pattern} asks for {mapped[0]!r} before its own name"
    )


def test_time_collapse_still_has_no_puzzle_mapping():
    """Losing on the clock is not trained by solving positions."""
    assert "time_collapse" not in WEAKNESS_TO_PATTERN_TYPES
