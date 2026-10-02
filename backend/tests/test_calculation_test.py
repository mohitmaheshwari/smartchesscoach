"""Grading a calculated line, against the real engine.

These run Stockfish rather than a stub. The whole point of the exercise is that
the engine is the authority on whether a line holds, and a stub would only test
that the code agrees with my own chess -- which is exactly the thing that was
wrong when the Ruy Lopez "pin" turned out to be a skewer.
"""
from __future__ import annotations

import chess
import pytest

from services.calculation_test import (
    FOUND, MISSED, SOUND, TOO_EASY, UNSOUND,
    grade_line, required_depth,
)
from stockfish_service import StockfishEngine


@pytest.fixture(scope="module")
def engine():
    with StockfishEngine() as wrapper:
        yield wrapper.engine


# A forced mate in one: Qh5xf7 is mate. Nothing to calculate past it.
MATE_IN_ONE = "rnbqkbnr/pppp1ppp/8/4p3/5PPQ/8/PPPPP2P/RNB1KBNR b KQkq - 1 3"
# Scholar's-mate shape, white to move: Qxf7 is mate.
SCHOLARS = "r1bqkbnr/pppp1ppp/2n5/2b1p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


def test_the_first_move_decides_whether_they_found_the_idea(engine):
    r = grade_line(SCHOLARS, ["Qxf7#"], engine)
    assert r["found_the_idea"] == FOUND
    assert r["sound_through"] == 1


def test_a_move_that_throws_the_position_away_is_not_the_idea(engine):
    r = grade_line(SCHOLARS, ["Qd1"], engine)
    assert r["found_the_idea"] == MISSED
    assert r["sound_through"] == 0
    assert r["plies"][0]["verdict"] == UNSOUND


def test_grading_stops_at_the_first_unsound_half_move(engine):
    """Everything after a wrong move is a line from a position that would not
    have arisen, so it is not graded and not counted."""
    r = grade_line(SCHOLARS, ["Qd1", "Nf6", "Qxf7#"], engine)
    assert r["sound_through"] == 0
    assert len(r["plies"]) == 1, "it kept grading past the break"


def test_an_unreadable_move_is_reported_not_guessed(engine):
    r = grade_line(SCHOLARS, ["Qxz9"], engine)
    assert r["plies"][0]["verdict"] == "could not read that move"
    assert r["sound_through"] == 0


def test_an_illegal_move_is_not_accepted_as_a_calculation(engine):
    r = grade_line(SCHOLARS, ["Qxf8"], engine)
    assert r["sound_through"] == 0


# ── the opponent is held to a different standard ──────────────────────

def test_a_feeble_reply_for_the_opponent_is_called_out(engine):
    """A player who answers their own best move with a gift for the opponent
    has calculated nothing. This is the trap the exercise exists to catch."""
    # 1...exf4 is fine for black; white then has a strong answer. Giving white
    # a weak one instead should not count as having seen the defence.
    start = "rnbqkbnr/pppp1ppp/8/4p3/5P2/8/PPPPP1PP/RNBQKBNR b KQkq - 0 2"
    r = grade_line(start, ["exf4", "a3"], engine)
    assert r["plies"][1]["by"] == "opponent"
    assert r["plies"][1]["verdict"] == TOO_EASY
    assert r["sound_through"] == 1, "the feeble reply was counted as sound"


def test_the_player_and_the_opponent_alternate(engine):
    """A quiet position on purpose. In SCHOLARS mate is on the board, so ANY
    other first move is correctly unsound and grading stops at ply 1 -- which
    is right, and makes it useless for testing alternation."""
    r = grade_line(chess.STARTING_FEN, ["e4", "e5"], engine)
    assert [p["by"] for p in r["plies"]][:2] == ["you", "opponent"]
    assert r["sound_through"] == 2


# ── depth ─────────────────────────────────────────────────────────────

def test_a_position_that_ends_at_once_needs_no_depth(engine):
    board = chess.Board(SCHOLARS)
    assert required_depth(board, engine) <= 2


def test_stopping_short_is_recorded_separately_from_going_wrong(engine):
    """Two different failures, two different things to tell a player."""
    r = grade_line(SCHOLARS, ["Qxf7#"], engine)
    # A sound line that ran to the end of the position is not "stopped early".
    assert r["stopped_early"] in (False, None)


def test_the_line_may_be_any_length(engine):
    one = grade_line(SCHOLARS, ["Qxf7#"], engine)
    assert one["sound_through"] == 1
    longer = grade_line(
        "rnbqkbnr/pppp1ppp/8/4p3/5P2/8/PPPPP1PP/RNBQKBNR b KQkq - 0 2",
        ["exf4", "Nf3", "g5", "h4"], engine)
    assert len(longer["plies"]) >= 2


# ── judging the end ───────────────────────────────────────────────────

def test_calling_a_won_position_won_is_right(engine):
    r = grade_line(SCHOLARS, ["Qxf7#"], engine, verdict="winning")
    assert r["judged_the_end"]["right"] is True


def test_seeing_the_line_but_misjudging_the_end_is_recorded(engine):
    """A player can calculate correctly and still be wrong about the result.
    Folding that into one score would hide it."""
    r = grade_line(SCHOLARS, ["Qxf7#"], engine, verdict="level")
    assert r["judged_the_end"]["right"] is False
    assert r["judged_the_end"]["actually"] == "winning"
    assert r["sound_through"] == 1, "the misjudgement wrongly cost them the line"


def test_no_verdict_asked_means_none_reported(engine):
    r = grade_line(SCHOLARS, ["Qxf7#"], engine)
    assert r["judged_the_end"] is None


# ── the sound line must start with the best move ─────────────────────
#
# pv_after_best is the continuation AFTER the best move and does not contain
# it. Handing that to the grader starts the line one half-move in, and its
# first move is not even legal from the test position. The symptom was the
# engine's OWN line grading as unsound at ply 1, which is the control that
# caught it.

def test_the_engine_own_line_grades_as_fully_sound(engine):
    """If the sound line is not sound, the grader is wrong. This is the
    control, and it is the one that found the off-by-one."""
    fen = "5N1k/1p4p1/7p/2p1P3/1pP5/4q3/6PP/5K2 b - - 0 37"
    best, continuation = "Kg8", ["Nd7", "Qd3+", "Kf2"]
    r = grade_line(fen, [best] + continuation, engine)
    assert r["sound_through"] == 4, r["plies"]
    assert r["found_the_idea"] == FOUND


def test_the_continuation_alone_is_not_playable_from_the_position(engine):
    """Proves the off-by-one is real and not a quirk of one grader run."""
    fen = "5N1k/1p4p1/7p/2p1P3/1pP5/4q3/6PP/5K2 b - - 0 37"
    r = grade_line(fen, ["Nd7"], engine)
    assert r["sound_through"] == 0
    assert r["plies"][0]["verdict"] == "could not read that move"


# ── being told the right move is not teaching ────────────────────────

def test_a_wrong_move_comes_back_with_the_line_that_works(engine):
    """"c6 was the move" and nothing else is the empty card this product has
    been criticised for all week. The continuation is what makes it a lesson."""
    r = grade_line(SCHOLARS, ["Qd1"], engine)
    assert r["sound_through"] == 0
    assert len(r["sound_continuation"]) >= 1, r
    assert r["sound_continuation"][0] == "Qxf7#"


def test_a_line_that_holds_needs_no_correction(engine):
    r = grade_line(SCHOLARS, ["Qxf7#"], engine)
    assert r["sound_continuation"] == []
