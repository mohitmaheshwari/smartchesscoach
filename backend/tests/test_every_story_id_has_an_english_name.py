"""A story line must never reach a player as a tag.

Mohit, 2026-10-20, reading a real story: "the story connects tags not the
pieces and doesn't use english much, can't really show like that on app for
users". Measured against the whole corpus that day:

    negative subtypes   74.0% of volume had an English name
    executed motifs      2.8% of volume had one

`build_game_story` now refuses to SHOW a moment it cannot name, which stops
the tag reaching the screen but would hide a real detection if an id were
left unnamed. These tests are the other half of that bargain: the gate is
only honest while every id a classifier can return resolves, so an unnamed
id has to fail here rather than go quiet in production.

Nothing is authored in `game_story`. Negative subtypes and the positive
flags are named in `pattern_catalog.json`; executed motifs are named in
`services.shape_patterns`, whose language was signed off 2026-05-12. A sixth
concept vocabulary would be a bug, not a feature.
"""
import re

import pytest

from services.game_story import _display_name, build_game_story

# Subtype string literals scraped from the two classifiers, minus the
# non-subtype returns that share their shape (phase names, time flags, the
# register verdicts). Scraping rather than listing is deliberate: a subtype
# added in code tomorrow is caught without anyone remembering this file.
_NOT_SUBTYPES = {
    "opening", "middlegame", "endgame",          # phase names
    # Time flags. These live in the observation's `time_flag` field, not its
    # `subtype`, so a story never carries one as a moment. They are graded in
    # the quality registry alongside the gap subtypes, which is the only
    # reason they turn up in this scrape.
    "snap_decision", "time_pressure_blunder", "slow_paralysis",
    "chronic_timeout", "impulsive_critical",
    "wrong_register",                            # a register verdict
}


def _scraped_subtypes():
    """Every subtype a story can carry, from both places that mint one.

    The classifiers are scraped for their return literals, and the detector
    quality registry for the `gap:<pattern>:<subtype>` identities it grades.
    Both are needed: `trapped_piece_exact` is graded in the registry, has 150
    documents behind it, and appears in neither classifier's return literals,
    so a scrape alone said it was fine while a real story could not name it.
    """
    import services.cognitive_gap_subtypes as cgs
    import services.detector_quality as dq
    import services.move_observation_deriver as mod
    found = set()
    for module, pattern in (
        (cgs, r'return \(\s*"([a-z0-9_]+)"'),
        (mod, r'return "([a-z0-9_]+)"'),
        (dq, r'"gap:[a-z_]+:([a-z0-9_]+)"'),
    ):
        with open(module.__file__, encoding="utf-8") as fh:
            found |= set(re.findall(pattern, fh.read()))
    return sorted(found - _NOT_SUBTYPES)


def _shape_ids():
    from services.shape_patterns import PATTERNS_BY_ID
    return sorted(PATTERNS_BY_ID)


# The three fields on an observation that mark a success. Kept in step with
# services.game_story._POSITIVE_FLAGS by the test below.
_FLAGS = ["found_best_in_critical", "punished_opponent_blunder",
          "responded_to_threat"]


@pytest.mark.parametrize("subtype", _scraped_subtypes())
def test_every_classifier_subtype_has_an_english_name(subtype):
    assert _display_name(subtype, "negative"), (
        f"{subtype!r} can be returned by a classifier but has no human_name "
        f"in pattern_catalog.json, so a story would drop it silently"
    )


@pytest.mark.parametrize("motif", _shape_ids())
def test_every_executed_motif_has_an_english_name(motif):
    assert _display_name(motif, "positive"), (
        f"{motif!r} is an executed-motif id with no name in shape_patterns"
    )


@pytest.mark.parametrize("flag", _FLAGS)
def test_every_positive_flag_has_an_english_name(flag):
    assert _display_name(flag, "positive")


def test_the_flag_list_here_matches_the_one_that_ships():
    from services.game_story import _POSITIVE_FLAGS
    assert sorted(_POSITIVE_FLAGS) == sorted(_FLAGS)


class TestNothingTaggyReachesTheScreen:
    def _story(self, observations):
        return build_game_story(observations=observations, move_evaluations=[],
                                user_color="white")

    def test_a_shown_moment_always_carries_its_english(self):
        shown = self._story([
            {"move_number": 12, "color": "white", "severity": "critical",
             "cp_loss": 400, "eval_before": 100, "eval_after": -300,
             "missed_pattern": "piece_safety", "subtype": "simple_hang"},
            {"move_number": 20, "color": "white", "cp_loss": 0,
             "eval_before": 10, "eval_after": 10, "found_best_in_critical": True},
        ])["moments_showable"]
        assert shown
        for moment in shown:
            assert moment["display_name"], moment
            # The tag itself must never be what a caller would print.
            assert moment["display_name"] != moment["id"]

    def test_an_unnameable_moment_is_recorded_but_not_shown(self):
        """The gate, stated as behaviour rather than as an implementation.

        An id with no entry is a hole in the authoring, and the right
        response is to record it and stay quiet -- not to print the id.
        """
        story = self._story([
            {"move_number": 9, "color": "white", "severity": "moderate",
             "cp_loss": 200, "eval_before": 0, "eval_after": -200,
             "missed_pattern": "piece_safety",
             "subtype": "a_subtype_nobody_has_authored"},
        ])
        assert story["moments"], "the detection should still be on the record"
        assert story["moments_showable"] == []

    def test_an_executed_motif_is_named_from_the_shapes_registry(self):
        """Not from pattern_catalog, which does not own motif language."""
        shown = self._story([
            {"move_number": 14, "color": "white", "cp_loss": 0,
             "eval_before": 50, "eval_after": 50,
             "tactical_pattern_executed": "knight_fork"},
        ])["moments_showable"]
        assert shown and shown[0]["display_name"] == "Knight Fork"

    def test_a_span_carries_the_same_key_as_a_moment(self):
        """One render contract, so a caller does not special-case spans."""
        import chess
        board = chess.Board()
        rows = []
        for san in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"):
            before = board.fen()
            board.push_san(san)
            rows.append({"fen_before": before, "fen_after": board.fen(),
                         "move_number": len(rows) // 2 + 1})
        spans = build_game_story(observations=[], move_evaluations=rows,
                                 user_color="white")["spans"]
        for span in spans:
            assert span["display_name"] == span["label"]
