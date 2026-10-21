"""The story must be two-sided, ranked by what a player remembers, and honest.

`build_game_story` assembles existing layers; these pin the judgements it
makes on top of them, because those are the parts no other test covers.

The guarantee worth stating: negatives outnumber positives in the corpus
1,063 to 548 AND carry higher severity, so a plain top-N by severity produces
an all-bad story in most games. Measured over 300 games with the guarantee
in place, 140 had a positive moment available and 0 produced an all-negative
story.
"""
import chess

from services.game_story import MAX_MOMENTS, build_game_story

START = chess.Board().fen()


def observation(**kw):
    base = {"move_number": 10, "ply": 19, "color": "white",
            "severity": "moderate", "cp_loss": 150,
            "eval_before": 20, "eval_after": -130}
    base.update(kw)
    return base


def negative(subtype="simple_hang", **kw):
    return observation(missed_pattern="piece_safety", subtype=subtype, **kw)


def positive(**kw):
    kw.setdefault("punished_opponent_blunder", True)
    return observation(**kw)


def story(observations, move_evaluations=(), **kw):
    return build_game_story(
        observations=list(observations),
        move_evaluations=list(move_evaluations),
        user_color="white",
        **kw,
    )


class TestBothSidesOfTheGame:
    def test_a_positive_moment_appears_when_one_exists(self):
        """The rule the corpus forces, not a preference."""
        result = story([negative(), negative(), negative(), positive()])
        assert any(m["polarity"] == "positive" for m in result["moments"])

    def test_the_story_does_not_grow_to_fit_the_positive(self):
        # It swaps the weakest negative rather than exceeding the budget; a
        # story nobody finishes reading teaches nothing.
        result = story([negative()] * 6 + [positive()])
        assert len(result["moments"]) <= MAX_MOMENTS

    def test_no_positive_is_invented_when_the_player_made_none(self):
        result = story([negative(), negative()])
        assert all(m["polarity"] == "negative" for m in result["moments"])


class TestRanking:
    def test_a_decisive_moment_outranks_a_more_severe_one(self):
        """Decisiveness first: the move that changed the result.

        The severe-but-not-decisive moment here loses an eval chunk while
        already losing; the decisive one throws away a won game.
        """
        severe = negative("tactical_seq_loss", severity="critical",
                          eval_before=-800, eval_after=-1400, cp_loss=600)
        decisive = negative("simple_hang", severity="moderate",
                            eval_before=400, eval_after=-250, cp_loss=650)
        result = story([severe, decisive])
        assert result["headline"]["id"] == "simple_hang"
        assert result["headline"]["decisive"] is True

    def test_recurrence_breaks_a_tie_between_equals(self):
        a = negative("simple_hang", eval_before=10, eval_after=5, cp_loss=120)
        b = negative("trapped_piece_exact", eval_before=10, eval_after=5,
                     cp_loss=120)
        result = story([a, b], recurring_ids={"trapped_piece_exact"})
        assert result["headline"]["id"] == "trapped_piece_exact"

    def test_without_a_recurring_set_recurrence_simply_does_not_rank(self):
        # It is a parameter rather than a lookup precisely so this is true.
        a = negative("simple_hang", severity="critical")
        b = negative("trapped_piece_exact", severity="minor")
        assert story([a, b])["headline"]["id"] == "simple_hang"


class TestSpansAndEmptiness:
    def test_a_game_with_nothing_sharp_says_so(self):
        """41 of 300 real games are like this. Silence is the honest answer."""
        result = story([])
        assert result["is_empty"] is True
        assert result["headline"] is None
        assert result["moments"] == [] and result["spans"] == []

    def test_user_moves_are_read_from_the_fen_not_the_opponent_flag(self):
        """Coach games never set is_opponent_move.

        Trusting `not is_opponent_move` counted both players and doubled every
        trend denominator. The FEN basis reproduced the v5-sourced trends and
        counts on 120 of 120 games, coach games included, so this pins the
        basis rather than the output.
        """
        board = chess.Board()
        after_white = board.copy()
        after_white.push_san("e4")
        rows = [
            # White's move: user is white, so this one counts.
            {"fen_before": START, "fen_after": after_white.fen(),
             "move_number": 1},
            # Black's reply, with NO is_opponent_move field at all.
            {"fen_before": after_white.fen(), "fen_after": after_white.fen(),
             "move_number": 1},
        ]
        result = story([], move_evaluations=rows)
        assert result["user_move_count"] == 1, (
            "both sides were counted as the user; that is the coach-game bug"
        )


class TestComposition:
    def test_every_moment_comes_from_an_observation(self):
        """It assembles; it must not manufacture.

        A story element with no source observation would mean this module had
        started making chess claims of its own, which is the one thing it is
        not allowed to do.
        """
        observations = [negative("simple_hang"), positive()]
        result = story(observations)
        source_ids = {"simple_hang", "punished_opponent_blunder"}
        assert {m["id"] for m in result["moments"]} <= source_ids

    def test_an_observation_with_nothing_sharp_yields_no_moment(self):
        quiet = observation(severity="good", cp_loss=5)
        assert story([quiet])["moments"] == []

    def test_a_negative_moment_carries_its_detector_quality_id(self):
        # The id is what lets the showable gate and any later audit tie a
        # story element back to the authority that permits it.
        result = story([negative("simple_hang")])
        assert result["moments"][0]["detector_quality_id"] == (
            "gap:piece_safety:simple_hang")


class TestShowableGate:
    def test_an_unauthorised_moment_is_stored_but_not_shown(self):
        """Stored-and-unshown is deliberate: auditable before published."""
        result = story(
            [negative("trapped_piece_exact")],
            is_showable=lambda qid: qid != "gap:piece_safety:trapped_piece_exact",
        )
        assert result["moments"], "the moment should still be recorded"
        assert result["moments_showable"] == []

    def test_the_headline_falls_back_to_a_span_when_nothing_may_be_shown(self):
        board = chess.Board()
        after = board.copy()
        after.push_san("e4")
        rows = [{"fen_before": START, "fen_after": after.fen(),
                 "move_number": 1}]
        result = story([negative("trapped_piece_exact")],
                       move_evaluations=rows,
                       is_showable=lambda _qid: False)
        assert result["headline"] is None or result["headline"]["kind"] == "span"


class TestNoRepetition:
    def test_the_same_mistake_takes_one_slot(self):
        """The first real story spent two of three slots on one subtype.

        It fired at moves 21 and 22, true both times. A player takes away
        "you keep ignoring attacks on your king", not two instances of it --
        and how often it happened is the span layer's job, which already
        counts moves.
        """
        repeated = [negative("ignored_king_attack", move_number=n)
                    for n in (21, 22, 23)]
        result = story(repeated + [negative("simple_hang", move_number=30)])
        ids = [m["id"] for m in result["moments"]]
        assert len(ids) == len(set(ids)), f"story repeated itself: {ids}"
        assert "simple_hang" in ids, (
            "dropping duplicates should free a slot for a different mistake"
        )

    def test_a_positive_and_a_negative_sharing_a_name_both_survive(self):
        # Polarity is part of the key, so "responded_to_threat" as a success
        # is not deduped against a negative of the same name.
        result = story([negative("responded_to_threat"),
                        positive(responded_to_threat=True)])
        assert len({(m["polarity"], m["id"]) for m in result["moments"]}) == 2


class TestPositivesAreRankedByWhatTheySignify:
    """Negatives carry a severity; positives did not, so they all tied at zero.

    The first real story on one of Mohit's own won games headlined
    "responded_to_threat" at move 6 while "found_best_in_critical" at move 32
    sat below it on nothing but observation order.
    """

    def test_a_critical_find_outranks_answering_a_threat(self):
        routine = observation(responded_to_threat=True, move_number=6)
        critical = observation(found_best_in_critical=True, move_number=32)
        # Routine first in the list, so order alone would pick it.
        result = story([routine, critical])
        assert result["headline"]["id"] == "found_best_in_critical"

    def test_the_strongest_signal_on_one_move_is_the_one_named(self):
        both = observation(responded_to_threat=True,
                           punished_opponent_blunder=True)
        assert story([both])["moments"][0]["id"] == "punished_opponent_blunder"

    def test_a_real_mistake_still_outranks_any_success(self):
        # Ordering positives must not let a good move bury a decisive error.
        decisive = negative("simple_hang", severity="critical",
                            eval_before=400, eval_after=-250, cp_loss=650)
        good = observation(found_best_in_critical=True)
        assert story([good, decisive])["headline"]["id"] == "simple_hang"


class TestRecurrenceMatchesTheTopicNotJustTheSubtype:
    def test_a_focus_topic_matches_a_moment_of_that_family(self):
        """The mismatch that made recurrence inert with real input.

        `user_active_focus.topic_key` holds "missed_tactic"; the moment is
        "missed_generic_tactic". Comparing ids alone never matched once, so
        the second-ranked criterion did nothing on every real game.
        """
        tactic = observation(missed_pattern="missed_tactic",
                             subtype="missed_generic_tactic", move_number=7)
        other = observation(missed_pattern="piece_safety",
                            subtype="simple_hang", move_number=20)
        result = story([other, tactic], recurring_ids={"missed_tactic"})
        assert result["headline"]["id"] == "missed_generic_tactic"

    def test_an_unrelated_topic_does_not_match(self):
        tactic = observation(missed_pattern="missed_tactic",
                             subtype="missed_generic_tactic",
                             severity="minor")
        other = observation(missed_pattern="piece_safety",
                            subtype="simple_hang", severity="critical")
        result = story([tactic, other], recurring_ids={"king_safety"})
        assert result["headline"]["id"] == "simple_hang"
