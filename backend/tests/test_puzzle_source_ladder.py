"""Own games first, community next, Lichess to top up -- and never as evidence.

The ladder was built correctly and then Source 3 was switched off for every
pattern except calculation_depth, so users practised almost entirely on their
own handful of positions. These lock the intended shape.
"""
import inspect

from services.coaching_puzzle_service import (
    CoachingPuzzleService,
    WEAKNESS_TO_PUZZLE_THEMES,
)

WRITABLE = [
    "piece_safety", "king_safety", "missed_tactic", "tactical_oversight",
    "calculation_depth", "opening_knowledge", "endgame_technique",
]


def test_lichess_is_not_restricted_to_a_single_pattern():
    """The old gate returned [] unless the pattern was calculation_depth."""
    src = inspect.getsource(CoachingPuzzleService._get_lichess_puzzles)
    assert 'weakness_pattern != "calculation_depth"' not in src, (
        "Source 3 is gated to one pattern again; 11 patterns would get no "
        "Lichess supply"
    )


def test_every_writable_pattern_can_reach_lichess_themes():
    """A pattern with no theme mapping silently gets nothing from Source 3."""
    missing = [p for p in WRITABLE if not WEAKNESS_TO_PUZZLE_THEMES.get(p)]
    assert not missing, f"no Lichess theme mapping for: {missing}"


def test_verified_evidence_paths_never_pull_lichess():
    """Phase 8 / verified mastery must not be proved by a stranger's puzzle.

    A Lichess position is not from the player's games, so it can show they
    can solve that TYPE, never that they fixed their own weakness.
    """
    src = inspect.getsource(CoachingPuzzleService.get_prescribed_training)
    assert "not required_quality_id" in src, (
        "the guard that keeps Lichess out of required-quality (verified) "
        "prescriptions is gone"
    )


def test_personal_positions_are_requested_before_lichess():
    """Own games are pulled first so the session leads with the player's own
    mistakes, and Lichess only fills what is left."""
    src = inspect.getsource(CoachingPuzzleService.get_prescribed_training)
    own = src.find("_get_puzzles_from_user_games")
    community = src.find("_get_community_puzzles")
    lichess = src.find("_get_lichess_puzzles")
    assert -1 < own < lichess, "own games must be fetched before Lichess"
    assert -1 < community < lichess, "community must be fetched before Lichess"


def test_lichess_rows_declare_their_provenance():
    src = inspect.getsource(CoachingPuzzleService._get_lichess_puzzles)
    assert '"source": "lichess"' in src, (
        "Lichess rows must be tagged so downstream can tell them from the "
        "player's own positions"
    )
