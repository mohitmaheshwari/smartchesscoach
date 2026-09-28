"""Same missed tactics, two players, opposite prescriptions.

That is the whole point of splitting knowledge from behaviour. If both ever
produce the same drill, the split has bought nothing.

Measured 2026-09-28 across 49 players:
    knowledge rate     q1 0.58  median 0.66  q3 0.70
    thinks-long share  q1 0.12  median 0.14  q3 0.17
    fast-miss share    min 0.00 median 0.15  max 0.28   <- too flat to diagnose
"""
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.opportunity_gate import MIN_CHANCES_TO_JUDGE, pooled_knowledge  # noqa: E402
from services.two_layer_diagnosis import (  # noqa: E402
    ATTENTION_GAP,
    KNOWLEDGE_GAP,
    KNOWLEDGE_MEDIAN,
    NO_TACTICAL_GAP,
    NOT_ENOUGH_EVIDENCE,
    PRESCRIPTION,
    THINKS_LONG_MEDIAN,
    card,
    diagnose,
)


def _pooled(rate, chances=MIN_CHANCES_TO_JUDGE * 2):
    took = int(round(rate * chances))
    return pooled_knowledge(
        [{"pattern": "fork", "took": True}] * took
        + [{"pattern": "fork", "took": False}] * (chances - took))


def test_misses_them_while_taking_his_time_is_a_knowledge_gap():
    d = diagnose(_pooled(KNOWLEDGE_MEDIAN - 0.15), THINKS_LONG_MEDIAN + 0.05)
    assert d["layer"] == KNOWLEDGE_GAP
    assert "teach the shape" in d["prescription"]


def test_misses_them_without_taking_time_is_an_attention_gap():
    d = diagnose(_pooled(KNOWLEDGE_MEDIAN - 0.15), THINKS_LONG_MEDIAN - 0.05)
    assert d["layer"] == ATTENTION_GAP
    assert "NOT more puzzles" in d["prescription"]


def test_the_two_gaps_never_prescribe_the_same_thing():
    """If they did, separating the layers would have bought nothing."""
    a = diagnose(_pooled(0.50), THINKS_LONG_MEDIAN + 0.05)["prescription"]
    b = diagnose(_pooled(0.50), THINKS_LONG_MEDIAN - 0.05)["prescription"]
    assert a != b


def test_a_player_who_finds_them_gets_no_diagnosis_at_all():
    """Not a softened one. A diagnosis nobody needs is noise in the coaching."""
    d = diagnose(_pooled(KNOWLEDGE_MEDIAN + 0.10), THINKS_LONG_MEDIAN - 0.05)
    assert d["layer"] == NO_TACTICAL_GAP
    assert card(d, "fork") is None


def test_too_few_chances_means_no_verdict():
    """Below the gate's bar a rate is noise with a decimal point."""
    thin = pooled_knowledge([{"pattern": "fork", "took": False}]
                            * (MIN_CHANCES_TO_JUDGE - 1))
    assert diagnose(thin, 0.05)["layer"] == NOT_ENOUGH_EVIDENCE
    assert diagnose({}, 0.05)["layer"] == NOT_ENOUGH_EVIDENCE


def test_unknown_tempo_falls_back_to_the_half_that_helps_either_way():
    """With no clock data we know he misses them and nothing about his time.
    Teaching the shape helps both kinds of player; a looking-habit drill helps
    only one, so guessing that way would be the costly guess."""
    d = diagnose(_pooled(0.50), None)
    assert d["layer"] == KNOWLEDGE_GAP
    assert d["because"] is None


def test_every_verdict_carries_a_prescription():
    for layer in (KNOWLEDGE_GAP, ATTENTION_GAP, NO_TACTICAL_GAP,
                  NOT_ENOUGH_EVIDENCE):
        assert PRESCRIPTION.get(layer), layer


# ---- the card ----------------------------------------------------------

def test_the_card_never_shows_a_number():
    for tempo in (THINKS_LONG_MEDIAN + 0.05, THINKS_LONG_MEDIAN - 0.05):
        text = card(diagnose(_pooled(0.50), tempo), "fork")
        for key, value in text.items():
            assert not re.search(r"\d", value), (key, value)
            assert "%" not in value


def test_the_card_never_compares_him_to_other_players():
    """The cut is population-relative, so the wording must not be. Missing a
    third of available tactics is ordinary at this rating; being told you are
    below average is not coaching."""
    banned = ("average", "than other", "most players", "below", "worse than",
              "percentile", "rank")
    for tempo in (THINKS_LONG_MEDIAN + 0.05, THINKS_LONG_MEDIAN - 0.05):
        text = " ".join(card(diagnose(_pooled(0.50), tempo), "fork").values())
        for word in banned:
            assert word not in text.lower(), word


def test_the_card_names_the_pattern_for_the_drill():
    text = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN + 0.05), "fork")
    assert "forks" in text["next"]
    other = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN + 0.05), "free_piece")
    assert "free material" in other["next"]


def test_an_unknown_pattern_still_produces_a_card():
    """A missing drill name must not cost the player the diagnosis."""
    text = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN + 0.05), None)
    assert "tactics" in text["next"]


def test_the_two_cards_say_opposite_things_about_time():
    knowledge = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN + 0.05), "fork")
    attention = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN - 0.05), "fork")
    assert "not rushing" in knowledge["body"]
    assert "fast mover" in attention["body"]
    assert knowledge["headline"] != attention["headline"]


def test_the_attention_card_offers_a_hypothesis_not_a_cause():
    """The verdict comes from the player's GENERAL tempo, not from the speed of
    these misses -- and the miss speed refuses a causal claim: fast-miss share
    runs 0.00 to 0.28, median 0.15, and mistakes are LESS rushed than ordinary
    moves (13.2% against 23.5%). So the card must not say his speed caused
    this."""
    text = card(diagnose(_pooled(0.50), THINKS_LONG_MEDIAN - 0.05), "fork")
    joined = " ".join(text.values()).lower()
    assert "we do not know yet" in joined, "must be offered as a question"
    for asserted in ("stopping to check is", "because you", "that is why",
                     "the idea is not the problem"):
        assert asserted not in joined, asserted


def test_the_cut_is_stamped_with_the_gate_it_was_measured_against():
    """The bug this catches, which already happened once.

    KNOWLEDGE_MEDIAN was measured on a two-pattern gate with a 67% take rate.
    Adding pin, skewer and hidden_attack moved the rate to 53%, and the constant
    -- untouched, still 0.66 -- went from splitting the population in half to
    sitting above nearly all of it. Every player got diagnosed and nothing
    failed. A relative cut is only meaningful against the distribution it came
    from.
    """
    from services.opportunity_gate import GATE_VERSION
    from services.two_layer_diagnosis import CALIBRATED_FOR_GATE

    assert CALIBRATED_FOR_GATE == GATE_VERSION, (
        "the gate's pattern set changed; re-measure KNOWLEDGE_MEDIAN against "
        "the new distribution before shipping, then update this stamp"
    )


def test_somebody_must_come_out_with_no_gap():
    """A cut that diagnoses everyone is not a diagnosis. Guards the shape of the
    failure rather than the exact number: if a future cut puts every player on
    the wrong side again, this fails."""
    from services.two_layer_diagnosis import KNOWLEDGE_MEDIAN

    healthy = diagnose(_pooled(min(KNOWLEDGE_MEDIAN + 0.05, 0.99)), 0.20)
    assert healthy["layer"] == NO_TACTICAL_GAP
