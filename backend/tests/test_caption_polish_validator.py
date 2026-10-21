"""The validator is the guarantee, so it gets the tests.

Mohit set the boundary: the LLM "should never reason on chess position, it
will just take up the english from template that our engine would create and
would beautify that, nothing else", on gpt-6-luna.

Every case below is a real failure, either measured from that model or
produced by my own first version of this check:

  "moved" for "pushed"           gpt-6-luna, head to head, 3 of 3 captions
  "their c-pawn" for "their own" lost the word that IS the lesson
  an empty answer                gpt-5-mini spent its whole budget thinking
                                 and returned nothing -- and my first check
                                 PASSED it, because an empty string adds no
                                 chess tokens

No network here. The validator is a pure function and that is the point: the
guarantee must not depend on a model being available or well behaved.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_polish import PROTECTED, validate  # noqa: E402

ORIGINAL = ("Their knight on c3 blocks their own c-pawn. "
            "The better line plays c4.")


class TestItAcceptsAnHonestRewrite:
    def test_a_clean_rephrase_passes(self):
        assert validate(
            ORIGINAL,
            "Their knight on c3 blocks their own c-pawn. "
            "The better line is c4.") is None

    def test_reordering_is_allowed(self):
        assert validate(
            ORIGINAL,
            "The better line plays c4. Their knight on c3 blocks their own "
            "c-pawn.") is None


class TestItRefusesInventedChess:
    def test_a_move_that_was_not_there(self):
        why = validate(ORIGINAL,
                       "Their knight on c3 blocks their own c-pawn. "
                       "The better line plays c4 and then Nbd2.")
        assert why and "invented" in why, why

    def test_a_square_that_was_not_there(self):
        why = validate(ORIGINAL,
                       "Their knight on c3 blocks their own c-pawn, so d4 "
                       "is weak. The better line plays c4.")
        assert why and "invented" in why, why

    def test_losing_the_move_it_was_meant_to_name(self):
        why = validate(ORIGINAL,
                       "Their knight on c3 blocks their own c-pawn. "
                       "There was a better line.")
        assert why and "dropped chess" in why, why


class TestItRefusesMeaningDrift:
    """The token check cannot see these: none of them is a chess token."""

    def test_dropping_own(self):
        why = validate(ORIGINAL,
                       "Their knight on c3 blocks their c-pawn. "
                       "The better line is c4.")
        assert why and "dropped meaning" in why and "own" in why, why

    def test_pushed_becoming_moved(self):
        original = ("e5 is a mistake - you pushed the pawn that was guarding "
                    "your pawn on d5, and Nxd5 wins it. a6 was better.")
        why = validate(original,
                       "e5 is a mistake. You moved the pawn that guarded your "
                       "pawn on d5. Nxd5 wins it. a6 was better.")
        assert why and "dropped meaning" in why, why

    def test_dropping_a_negation(self):
        original = "Bd6 is not safe here. Nf6 was better."
        why = validate(original, "Bd6 is safe here. Nf6 was better.")
        assert why and "not" in why, why

    def test_every_protected_word_is_actually_enforced(self):
        """A word on the list that nothing checks is decoration."""
        for word in PROTECTED:
            original = f"The rook is {word} active on d4 right now."
            polished = "The rook is active on d4 right now."
            why = validate(original, polished)
            assert why and "dropped meaning" in why, (word, why)


class TestItRefusesNonAnswers:
    def test_empty(self):
        assert validate(ORIGINAL, "") == "empty"
        assert validate(ORIGINAL, "   ") == "empty"

    def test_truncated(self):
        """gpt-5-mini returned nothing after spending its budget on thinking,
        and the first version of this check called that a pass."""
        assert validate(ORIGINAL, "Their knight") == "truncated"

    def test_an_essay(self):
        why = validate(ORIGINAL, " ".join(["word"] * 200))
        assert why in ("grew too long", "dropped chess: ['c3', 'c4']"), why

    def test_an_introduced_number(self):
        why = validate("The rook is active on the open file.",
                       "The rook is 2 times active on the open file.")
        assert why == "introduced a number", why


class TestSquaresAreNotNumbers:
    def test_square_names_do_not_trip_the_digit_rule(self):
        assert validate("The knight on c3 is fine where it stands.",
                        "The knight on c3 is okay where it stands.") is None

    def test_san_does_not_trip_it_either(self):
        """Real caption length -- a three-word fixture trips the truncation
        rule, which is the rule working rather than a bug."""
        assert validate(
            "Play Nxd5 here and the knight is yours.",
            "Play Nxd5 now and the knight is yours.") is None
