"""The home page's first two movements, tested where they can actually break.

docs/home_as_a_coach_scope.md

These are not coverage tests. Each one here is a failure this session already
made somewhere else and paid for:

  * the strength narrative that renders percentages, a cohort comparison and a
    sigma to a 1200 player
  * a question whose right answer is always the first option on screen
  * a board keyed to a focus topic that half the players have no positions for
  * a surface that opens with the fault and mentions the good thing last
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import coach_opening_words as words  # noqa: E402
from services import coach_today_position as today  # noqa: E402
from services import lesson_question_spec as spec_mod  # noqa: E402

DIGIT = re.compile(r"\d")


# ---------------------------------------------------------------- movement 1

def test_no_strength_sentence_contains_a_number():
    """The reason this module exists at all.

    The stored narrative says "you land at 4.6%, vs the cohort average of 6.7%
    ... that's +0.9 sigma". Every one of the 39 reads like that.
    """
    offenders = [label for label, text in words.STRENGTH_WORDS.items()
                 if DIGIT.search(text)]
    assert offenders == [], offenders


def test_no_strength_sentence_compares_to_other_players():
    """No cross-player comparison. Profiles are for the player themselves."""
    banned = ("cohort", "average", "other players", "than most",
              "percentile", "sigma", "σ", "compared")
    offenders = [(label, word)
                 for label, text in words.STRENGTH_WORDS.items()
                 for word in banned if word in text.lower()]
    assert offenders == [], offenders


def test_every_strength_the_picker_can_produce_has_words():
    """The gap this test exists for was invisible and was the biggest one.

    "Brilliant moves" is the most common strength of the thirty-nine stored,
    and it was the single label with nothing authored -- so the most common
    good thing about our players reached none of them. Nothing failed; the
    lookup simply returned None and the line was dropped.

    Locking the authored set to the picker's own two label tables means a new
    metric cannot be added without someone writing the sentence for it.
    """
    from services.primary_strength_picker import _METRIC_LABEL, _PATTERN_LABEL

    producible = set(_METRIC_LABEL.values()) | set(_PATTERN_LABEL.values())
    assert producible - set(words.STRENGTH_WORDS) == set(), \
        "picker can produce these, nobody wrote for them"


def test_no_strength_sentence_uses_a_word_a_1200_player_lacks():
    """Two of the picker's own labels are jargon ("Zwischenzug",
    "Fianchetto-hole play"). The sentence says the idea instead of repeating
    the label, so the jargon stops at the label."""
    banned = ("zwischenzug", "fianchetto", "prophyla", "outpost",
              "tempo", "zugzwang")
    offenders = [(label, word)
                 for label, text in words.STRENGTH_WORDS.items()
                 for word in banned if word in text.lower()]
    assert offenders == [], offenders


def test_an_unauthored_strength_label_stays_silent():
    """Silence beats dressing up the unshippable narrative as a fallback."""
    assert words.strength_words({"label": "Some new metric nobody wrote for"}) is None
    assert words.strength_words({"label": ""}) is None
    assert words.strength_words(None) is None


def test_the_good_thing_is_said_before_the_costly_one():
    """A coach who only names faults loses the client in three sessions."""
    out = words.opening_words(
        {"label": "Low blunder rate"},
        {"headline": "You have lost seventy-one games you were already "
                      "winning, on the clock.", "line": "Not to a better move."},
        "Most of it is one thing.")
    kinds = [line["kind"] for line in out["lines"]]
    assert kinds[0] == "strength", kinds
    assert "cost" in kinds, kinds
    assert out["lead"] == "I have been through your games."


def test_a_finding_outranks_the_focus_explanation():
    """A finding is the thing they could not have worked out alone."""
    out = words.opening_words(
        None, {"headline": "Headline."}, "Most of it is one thing.")
    texts = [line["text"] for line in out["lines"]]
    assert texts == ["Headline."], texts


def test_the_focus_explanation_is_used_when_there_is_no_finding():
    out = words.opening_words(None, None, "Most of it is one thing.")
    assert [l["text"] for l in out["lines"]] == ["Most of it is one thing."]


def test_nothing_measured_means_nothing_said():
    """No lead sentence promising a read we do not have."""
    out = words.opening_words(None, None, None)
    assert out["measured"] is False
    assert out["lead"] is None
    assert out["lines"] == []


# ---------------------------------------------------------------- movement 2

def test_every_askable_topic_has_an_authored_question():
    """A topic we would show a board for but have no question for is a board
    with a made-up question on it."""
    missing = []
    for topic in today.ASKABLE_TOPICS:
        spec = spec_mod.get_spec(topic)
        if spec is None or len(spec.reason_options) < 2 or not spec.reason_prompt:
            missing.append(topic)
    assert missing == [], missing


def test_no_belief_option_or_correction_contains_a_number():
    """Published text, simple English, no numbers -- all of it, not captions."""
    offenders = []
    for topic in today.ASKABLE_TOPICS:
        spec = spec_mod.get_spec(topic)
        for option in spec.reason_options:
            for field in ("label", "belief_lead", "correction"):
                text = getattr(option, field, "") or ""
                if DIGIT.search(text):
                    offenders.append((topic, option.id, field, text))
    assert offenders == [], offenders


def test_the_expected_answer_is_not_always_first_on_screen():
    """The spec stores the right answer at index 0. Shipping that order makes
    the question answerable without looking at the board."""
    spec = spec_mod.get_spec("piece_safety")
    seen_first = set()
    for _ in range(200):
        seen_first.add(today._options_for(spec)[0]["id"])
    assert len(seen_first) > 1, seen_first


def test_options_are_never_dropped_or_duplicated_by_the_shuffle():
    for topic in today.ASKABLE_TOPICS:
        spec = spec_mod.get_spec(topic)
        ids = sorted(o.id for o in spec.reason_options)
        got = sorted(o["id"] for o in today._options_for(spec))
        assert got == ids, (topic, got, ids)


def test_the_right_answer_is_confirmed_rather_than_corrected():
    out = today.answer_for("piece_safety", "checked_landing_square")
    assert out["ok"] is True
    assert out["expected"] is True
    assert out["belief"], "the right answer still gets a sentence"
    assert out["correction"] == ""


def test_a_wrong_belief_is_named_back_and_then_corrected():
    out = today.answer_for("piece_safety", "moved_the_attacked_piece")
    assert out["expected"] is False
    assert out["belief"], out
    assert out["correction"], out
    assert out["misconception_id"] == "attacked_is_not_the_same_as_hanging"


def test_an_unknown_option_is_refused_rather_than_guessed():
    assert today.answer_for("piece_safety", "made_up")["ok"] is False
    assert today.answer_for("piece_safety", None)["ok"] is False
    assert today.answer_for("no_such_topic", "checked_landing_square")["ok"] is False


# ------------------------------------------------------------ what is a finding

def test_the_retired_finding_is_not_in_the_chooser():
    """A finding every player gets is a fact about chess in a finding's clothes.

    `one_family_dominates` fired for 42 of 42 evaluable players with the same
    sentence, because alignment_share runs 0.550-0.764 and the bar was 0.4 --
    picked from one player's value before anyone looked at the spread. Three
    consecutive players on screen got it word for word.

    The function is kept so the numbers stay findable. This test is what stops
    it being wired back in.
    """
    import inspect

    from services import home_session

    source = inspect.getsource(home_session._finding_for)
    assert "one_family_dominates(" not in source, \
        "it fires for every player; see its docstring for the distribution"


def test_a_finding_still_reaches_the_players_it_is_true_of():
    """Removing the broken one must not leave the mechanism dead.

    A positive control for the deletion above: the clock finding still fires on
    the real worst case (96 winning games of 205 analysed timeouts) and still
    refuses a player with too little evidence.
    """
    from services.striking_finding import won_games_lost_on_time

    assert won_games_lost_on_time(96, 205) is not None
    assert won_games_lost_on_time(2, 20) is None, "below the event floor"
    assert won_games_lost_on_time(5, 100) is None, "below the share floor"


# ------------------------------------------------- the topic rule, on a fake db

class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        async def gen():
            for row in self._rows:
                yield row
        return gen()


class _Coll:
    def __init__(self, rows):
        self._rows = rows

    def find(self, query, projection=None):
        def matches(row):
            return all(row.get(k) == v for k, v in query.items())
        return _Cursor([r for r in self._rows if matches(r)])


class _DB:
    def __init__(self, puzzles=(), positions=()):
        self.community_puzzles = _Coll(list(puzzles))
        self.community_training_positions = _Coll(list(positions))


@pytest.mark.asyncio
async def test_the_focus_topic_wins_when_their_games_can_show_it():
    db = _DB(puzzles=[
        {"shared_by": "u", "approved": True, "issue_type": "king_safety"},
        {"shared_by": "u", "approved": True, "issue_type": "calculation_depth"},
        {"shared_by": "u", "approved": True, "issue_type": "calculation_depth"},
    ])
    assert await today.choose_topic(db, "u", "king_safety") == "king_safety"


@pytest.mark.asyncio
async def test_a_focus_with_no_board_falls_back_to_their_largest_topic():
    """Measured 2026-10-07: eight of the forty-nine focused players are on
    time_management, which has no positions by construction, and Mohit is one
    of them. The strict rule shows the person looking at the page nothing."""
    db = _DB(puzzles=[
        {"shared_by": "u", "approved": True, "issue_type": "piece_safety"},
        {"shared_by": "u", "approved": True, "issue_type": "calculation_depth"},
        {"shared_by": "u", "approved": True, "issue_type": "calculation_depth"},
    ])
    assert await today.choose_topic(db, "u", "time_management") == "calculation_depth"
    assert await today.choose_topic(db, "u", None) == "calculation_depth"


@pytest.mark.asyncio
async def test_a_player_with_no_positions_of_their_own_gets_no_board():
    """Rather than somebody else's game narrated as theirs."""
    assert await today.choose_topic(_DB(), "u", "piece_safety") is None


@pytest.mark.asyncio
async def test_positions_from_the_coach_pool_count_towards_the_topic():
    """A positive control for the second pool: the same probe that returns
    None above has to return a topic when only this pool has rows."""
    db = _DB(positions=[
        {"source_user_id": "u", "pattern_type": "hanging_piece"},
        {"source_user_id": "u", "pattern_type": "hanging_piece"},
    ])
    assert await today.choose_topic(db, "u", None) == "piece_safety"


@pytest.mark.asyncio
async def test_a_topic_we_have_no_question_for_is_never_chosen():
    db = _DB(puzzles=[
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "piece_safety"},
    ])
    assert await today.choose_topic(db, "u", "pawn_structure") == "piece_safety"
