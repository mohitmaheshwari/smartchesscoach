"""
The Progress-page narrative ranks weaknesses by raw problem_lifecycle
category ("time_collapse", "threw_winning", ...), while the puzzle system
keys its pattern_type mapping off the cognitive_gap taxonomy
("time_pressure", "piece_safety", ...) — two names for the same underlying
"blunders when the clock runs low" pattern. WEAKNESS_TO_PATTERN_TYPES only
had "time_pressure", not "time_collapse", so
CoachingPuzzleService._get_community_puzzles() built a MongoDB query for
`pattern_type: {"$in": ["time_collapse"]}` — a value nothing is ever
tagged with — and silently returned zero puzzles.

Reported live 2026-09-09: "Time discipline" (time_collapse) was the
Progress page's #1-ranked active focus (legitimately: highest raw count),
but clicking through loaded no puzzle at all.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.coaching_puzzle_service import WEAKNESS_TO_PATTERN_TYPES


def test_time_collapse_resolves_to_the_same_puzzles_as_time_pressure():
    assert "time_collapse" in WEAKNESS_TO_PATTERN_TYPES
    assert WEAKNESS_TO_PATTERN_TYPES["time_collapse"] == WEAKNESS_TO_PATTERN_TYPES["time_pressure"]


def test_time_collapse_does_not_fall_through_to_an_empty_lookup():
    # The old behavior: an unmapped key falls back to [weakness_pattern]
    # itself, i.e. ["time_collapse"] — a pattern_type nothing is tagged
    # with, so the $in query matches nothing. Confirm the alias actually
    # points at real, populated pattern_type values instead.
    pattern_types = WEAKNESS_TO_PATTERN_TYPES.get("time_collapse", ["time_collapse"])
    assert pattern_types != ["time_collapse"]
    assert "hanging_piece" in pattern_types
