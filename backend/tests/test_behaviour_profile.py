"""The behavioural traits, described rather than graded.

Six traits survived the stability test — stable within a player across time AND
spread across players. Ten candidates did not, and this file holds the line
against the ones that would be tempting to add back.

Cuts are quartiles of 48 measured players, 2026-09-28.
"""
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.behaviour_profile import (  # noqa: E402
    CUTS,
    MIN_MOVES,
    MIN_TIMED_MOVES,
    SENTENCES,
    SILENT_TRAITS,
    build_profile,
    describe,
)

ENOUGH = {"moves": MIN_MOVES, "timed_moves": MIN_TIMED_MOVES}


def _at(trait, end):
    low, high = CUTS[trait]
    return {trait: (high + 0.05) if end == "high" else (low - 0.02)}


def test_a_trait_at_the_top_end_speaks():
    lines = describe(_at("thinks_long", "high"))
    assert [l["trait"] for l in lines] == ["thinks_long"]
    assert lines[0]["end"] == "high"


def test_a_trait_at_the_bottom_end_speaks_differently():
    high = describe(_at("thinks_long", "high"))[0]["sentence"]
    low = describe(_at("thinks_long", "low"))[0]["sentence"]
    assert high != low


def test_a_player_in_the_middle_is_told_nothing_about_that_trait():
    """"You are about average at this" is not worth a line on a page, and it is
    the answer for half the population on every trait."""
    low, high = CUTS["thinks_long"]
    middle = (low + high) / 2
    assert describe({"thinks_long": middle}) == []


def test_error_rate_is_carried_but_never_spoken():
    """It is the most stable trait after the clock and it is not a diagnosis --
    it is how strong the player is. Saying it would be telling someone their
    rating back."""
    assert "error_rate" in SILENT_TRAITS
    assert "error_rate" in CUTS, "still used for ranking"
    assert describe({"error_rate": 0.9}) == []
    assert "error_rate" not in SENTENCES


def test_no_sentence_carries_a_number_or_a_grade():
    """Traits are described, not scored. `area_grades` grades board skills
    Excellent to Needs work; a disposition has no such axis -- measured per
    player, thinking longer goes with FEWER errors, not more."""
    banned = ("excellent", "good", "fair", "needs work", "poor", "average",
              "better than", "worse than", "most players", "percentile")
    for trait, ends in SENTENCES.items():
        for end, sentence in ends.items():
            assert not re.search(r"\d", sentence), (trait, end, sentence)
            for word in banned:
                assert word not in sentence.lower(), (trait, end, word)


def test_every_spoken_trait_has_both_ends_written():
    """A trait with only one end written would speak for half the players who
    qualify and silently drop the other half."""
    for trait in CUTS:
        if trait in SILENT_TRAITS:
            continue
        assert set(SENTENCES.get(trait, {})) == {"high", "low"}, trait


def test_a_thin_history_gets_no_profile_at_all():
    """A profile built on a handful of games describes the games, not the
    person."""
    thin = build_profile(_at("thinks_long", "high"), moves=10, timed_moves=5)
    assert thin["measured"] is False
    assert thin["lines"] == []
    assert "not enough" in thin["reason"]


def test_a_full_history_produces_the_lines():
    profile = build_profile(_at("thinks_long", "high"), **ENOUGH)
    assert profile["measured"] is True
    assert profile["lines"]
    assert profile["reason"] is None


def test_rates_stay_internal():
    profile = build_profile(_at("thinks_long", "high"), **ENOUGH)
    for key, value in profile.items():
        if isinstance(value, float):
            assert key.startswith("_"), key


def test_the_rejected_candidates_are_not_quietly_added_back():
    """Each of these was measured and is not a property of the player. tilt is
    0.18 -- one blunder does not cause the next. Aggression failed twice, at
    0.23 and 0.06. too_passive is stable at 0.58 with a spread of 0.009, so it
    separates nobody."""
    for rejected in ("tilt", "aggression", "too_forcing", "too_passive",
                     "errs_when_forcing", "opportunism", "notices_threats"):
        assert rejected not in CUTS, rejected
        assert rejected not in SENTENCES, rejected


def test_several_traits_can_speak_at_once():
    """This is a profile, not a single verdict -- unlike the focus, which names
    exactly one thing."""
    traits = {}
    traits.update(_at("thinks_long", "high"))
    traits.update(_at("clock_front_loaded", "high"))
    traits.update(_at("plays_on_when_lost", "low"))
    lines = describe(traits)
    assert len(lines) == 3


def test_throwing_away_won_games_needs_more_history_before_it_speaks():
    """Conversion is a GAME-level event, so each game is one binary observation
    and the estimate is noise-limited at small samples. Measured half-half as
    the bar rose: 0.41 at 10 winning positions, 0.43 at 30, 0.44 at 60, 0.59 at
    100, 0.72 at 150 -- climbing exactly as Spearman-Brown predicts for
    attenuation. So it is a real trait that an early reading calls weak, and it
    must stay silent until there is enough of it.
    """
    from services.behaviour_profile import MIN_SAMPLE

    traits = _at("throws_away_won_games", "high")
    need = MIN_SAMPLE["throws_away_won_games"]
    assert describe(traits, {"throws_away_won_games": need - 1}) == []
    spoken = describe(traits, {"throws_away_won_games": need})
    assert [l["trait"] for l in spoken] == ["throws_away_won_games"]


def test_a_trait_without_a_sample_rule_is_unaffected():
    """Only conversion carries the extra gate; the per-move traits already have
    enough observations by the time the profile is built at all."""
    assert describe(_at("thinks_long", "high"), {}) != []


def test_the_conversion_sentence_does_not_blame_luck_or_the_opponent():
    """It is the player's own conversion, so the wording has to own it without
    being cruel -- and without a number, like every other line."""
    from services.behaviour_profile import SENTENCES

    high = SENTENCES["throws_away_won_games"]["high"].lower()
    assert "unlucky" not in high and "opponent" not in high
    assert not re.search(r"\d", high)
