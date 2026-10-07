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


def test_no_user_facing_string_contains_a_typists_dash():
    """A literal `--` renders as two hyphens on screen and reads as a typo.

    Two slipped through and shipped: "moves that happened to work -- moves you
    had to see" and "about yourself -- it is a habit". Both are now two short
    sentences, which is the house style anyway. Every published string, not
    just the one I happened to notice.
    """
    offenders = []
    for name, text in words.STRENGTH_WORDS.items():
        if "--" in text:
            offenders.append(("strength", name, text))
    for n in range(0, 8):
        note = today.repeat_note(n)
        if note and "--" in note:
            offenders.append(("repeat_note", n, note))
    for topic in today.ASKABLE_TOPICS:
        spec = spec_mod.get_spec(topic)
        for option in spec.reason_options:
            for field in ("label", "belief_lead", "correction"):
                value = getattr(option, field, "") or ""
                if "--" in value:
                    offenders.append((topic, option.id + "." + field, value))
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

    def _matching(self, query):
        def matches(row):
            return all(row.get(k) == v for k, v in query.items())
        return [r for r in self._rows if matches(r)]

    def find(self, query, projection=None):
        return _Cursor(self._matching(query))

    async def find_one(self, query, projection=None, sort=None):
        rows = self._matching(query)
        if sort:
            key, direction = sort[0]
            rows.sort(key=lambda r: r.get(key) or "", reverse=direction < 0)
        return rows[0] if rows else None


class _DB:
    def __init__(self, puzzles=(), positions=()):
        self.community_puzzles = _Coll(list(puzzles))
        self.community_training_positions = _Coll(list(positions))
        self.home_today_answers = _Coll([])

    # `db[ANSWERS]` is a subscript on the real motor database object.
    def __getitem__(self, name):
        return getattr(self, name)


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


# ------------------------------------------------- does the page move at all?

def test_answering_writes_the_row_that_retires_the_board():
    """Mohit, 2026-10-07: *"it won't change over time, or would it?"*

    It would not. The first version of the answer endpoint wrote only
    `user_misconceptions`, keyed by misconception, while the supply function's
    `already_solved` filter reads `puzzle_attempts` -- a collection nothing on
    this path writes. The same position at move 49 came back every day.

    This is a source contract because the failure is that two collections
    disagree, which no unit of either one can see.
    """
    import inspect

    from services import coach_today_position as mod

    # The reader and the writer must name the same collection.
    reader = inspect.getsource(mod._answered_position_ids)
    writer = inspect.getsource(mod.record_answer)
    assert "db[ANSWERS]" in reader, reader
    assert "db[ANSWERS]" in writer, writer

    # And the position filter must actually consult it.
    picker = inspect.getsource(mod.todays_position)
    assert "_answered_position_ids" in picker
    assert "not in answered" in picker

    # It must NOT fake a solve: solve_rate orders every other pool.
    assert "puzzle_attempts" not in writer
    assert '"correct": True' not in writer


def test_the_endpoint_records_the_answer():
    """The route has to call it. The endpoint existed and recorded nothing
    that moved the page, which is the whole bug."""
    import inspect

    from routes import home

    source = inspect.getsource(home.answer_todays_question)
    assert "record_answer(" in source
    assert "position_id" in source


@pytest.mark.asyncio
async def test_the_board_advances_once_a_position_is_answered():
    """The behaviour, not just the wiring."""
    rows = [{"user_id": "u", "position_id": "p1", "topic": "piece_safety",
             "reason_id": "checked_landing_square", "expected": True}]
    db = _DB()
    db.home_today_answers = _Coll(rows)
    answered = await today._answered_position_ids(db, "u")
    assert answered == {"p1"}
    # and a different player's answer must not retire this player's board
    assert await today._answered_position_ids(db, "someone_else") == set()


def test_the_coach_does_not_repeat_itself():
    """Three sessions on real data gave the identical correction three times.

    Saying the same paragraph again is what a worksheet does. The first answer
    gets no note; a repeat gets noticed; a third gets something mechanical.
    """
    assert today.repeat_note(0) is None
    assert today.repeat_note(1) is None, "the first time is not a repeat"
    second = today.repeat_note(2)
    third = today.repeat_note(5)
    assert second and third and second != third


def test_a_right_answer_pays_the_count_back_down():
    """A counter that only rises can never resolve.

    That is the same disease as the finding that counts every timeout loss
    ever: "this keeps being your answer" would follow someone around for a
    habit they fixed months ago. One credit per right answer, not a reset --
    the shape pattern_decay_service already uses.
    """
    import inspect

    from services import coach_today_position as mod

    source = inspect.getsource(mod.record_answer)
    # The credit is applied on the path where there is no misconception, i.e.
    # they gave the expected reason.
    assert '"times_held": -1' in source, source
    assert "update_many" in source
    # And it must not drop below zero, or a diligent player banks credit
    # against a habit they have not shown yet.
    assert '"times_held": {"$gt": 0}' in source


def test_the_repeat_note_is_never_a_scoreboard():
    """No "that is your third time". The standing rule, and it matters most
    here because the counter makes the number so easy to reach for."""
    for n in range(0, 12):
        text = today.repeat_note(n)
        if text:
            assert not DIGIT.search(text), (n, text)
            for word in ("third", "fourth", "fifth", "times", "again and"):
                assert word not in text.lower(), (n, word, text)


@pytest.mark.asyncio
async def test_the_coach_remembers_what_they_said_last_time():
    rows = [{"user_id": "u", "position_id": "p1", "topic": "piece_safety",
             "reason_id": "moved_the_attacked_piece", "expected": False,
             "answered_at": "2026-10-06T10:00:00+00:00"}]
    db = _DB()
    db.home_today_answers = _Coll(rows)
    last = await today.last_answer(db, "u", "piece_safety")
    assert last["said"] == "I moved the piece that was already under attack."
    assert last["was_expected"] is False
    # Nothing to remember on a topic they have never answered, and no
    # invented continuity.
    assert await today.last_answer(db, "u", "calculation_depth") is None


@pytest.mark.asyncio
async def test_a_topic_we_have_no_question_for_is_never_chosen():
    db = _DB(puzzles=[
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "pawn_structure"},
        {"shared_by": "u", "approved": True, "issue_type": "piece_safety"},
    ])
    assert await today.choose_topic(db, "u", "pawn_structure") == "piece_safety"
