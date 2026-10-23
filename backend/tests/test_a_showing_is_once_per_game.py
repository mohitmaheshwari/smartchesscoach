"""A lesson shown twice in one game, or re-rendered, counts once.

`shown_count` is incremented in the RENDERER, and the two paths were
exactly inverted:

    background re-analysis / batch re-render  ->  counted (default True)
    the user opening the review page          ->  NOT counted (False)

So the number measured how often a job had rendered the card, not how
often a human had been told the lesson. Measured 2026-10-23: 34.5% of
5,313 concept-user pairs stood at 10 or more, and re-analysing five games
four times in one afternoon added four to every acknowledgment-bearing
card in them. Acknowledgment, mastery, and any future "which lesson next"
were all reading that noise.

Two things are asserted here, and the second is a bug this nearly shipped
with.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SRC = (Path(__file__).resolve().parents[1]
       / "services" / "game_decryption_v5_service.py").read_text(
    encoding="utf-8")


def _block():
    i = SRC.index("user_concept_understanding.update_one")
    return SRC[max(0, i - 2600):i + 2600]


class TestAShowingIsIdentifiedByItsGame:
    def test_the_game_is_part_of_what_a_showing_means(self):
        b = _block()
        assert '"shown_games"' in b, (
            "without the game in the identity, every re-render counts "
            "again")
        assert '"$addToSet": {"shown_games": game_id}' in b

    def test_the_increment_is_guarded_by_the_game_not_being_recorded(self):
        b = _block()
        assert '"shown_games": {"$ne": game_id}' in b


class TestItCannotCreateADuplicateRow:
    """The trap: ONE upsert whose filter says `shown_games: {$ne: game_id}`
    inserts a SECOND row for the same user and concept whenever the game is
    already recorded -- the existing document fails the filter, nothing
    matches, and upsert creates. The ensure and the increment must be
    separate operations."""

    def test_the_negative_filter_never_appears_with_upsert(self):
        b = _block()
        # find each update_one call and check: if it has the $ne guard, it
        # must NOT also have upsert=True
        parts = b.split("update_one(")
        for p in parts[1:]:
            call = p[:p.index(")\n") + 1] if ")\n" in p else p[:800]
            if '"shown_games": {"$ne": game_id}' in call:
                assert "upsert=True" not in call, (
                    "an upsert with the $ne guard duplicates the row")

    def test_the_identity_upsert_sets_the_count_to_zero_not_one(self):
        """The row is created by the ensure step, so the count starts at 0
        and the guarded increment is what takes it to 1. Starting at 1
        would double-count the first game."""
        b = _block()
        assert '"shown_count": 0' in b

    def test_a_missing_game_id_does_not_increment_anything(self):
        """game_id is optional on this path -- an ad-hoc render without one
        must not be counted as a showing."""
        b = _block()
        assert "if game_id:" in b
