"""The lesson plays out after the correct move, and talks through it.

A player answered Re4 on the Lucena lesson and the app jumped to the next
puzzle. The move they had just been asked for meant nothing, because they
never saw the pawn promote.

Beat detection is pure board geometry and is tested without an engine. The
line generation needs Stockfish and is skipped where there is none.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.lesson_continuation import (  # noqa: E402
    BEAT_CAPTURED_CHECKER,
    BEAT_CHECK,
    BEAT_MATE,
    BEAT_PROMOTION,
    BEAT_PROMOTION_MATE,
    BEAT_ROOK_TO_SHIELD_RANK,
    _beat_coaching,
    shield_rank_for,
    _stockfish_path,
    build_continuation,
    detect_beat,
)

LUCENA = "3K4/3P1k2/8/8/8/8/r7/4R3 w - - 0 1"


def _apply(fen, san, learner=None):
    before = chess.Board(fen)
    if learner is None:
        learner = before.turn
    move = before.parse_san(san)
    after = before.copy(stack=False)
    after.push(move)
    return before, move, after, learner


# --- beats are board facts -------------------------------------------------

def test_rook_reaching_the_fourth_rank_is_a_beat():
    before, move, after, learner = _apply(LUCENA, "Re4")
    assert detect_beat(before, move, after, learner) == BEAT_ROOK_TO_SHIELD_RANK


def test_a_rook_move_along_the_fourth_rank_is_not_a_fresh_beat():
    """It only fires on ARRIVING. Otherwise every shuffle re-announces it."""
    fen = "3K4/3P1k2/8/8/4R3/8/r7/8 w - - 0 1"
    before, move, after, learner = _apply(fen, "Rd4")
    assert detect_beat(before, move, after, learner) is None


def test_the_shield_rank_comes_from_the_pawn_not_a_constant():
    """"The fourth rank" is Lucena's rule and only holds because Lucena has a
    pawn one square from promoting with its own king in front."""
    board = chess.Board(LUCENA)
    assert shield_rank_for(board, chess.WHITE) == 3   # 0-indexed rank 4

    # Mirrored: Black pawn on the 2nd, own king in front -> rank 5.
    mirrored = chess.Board("4r3/8/8/8/8/8/3p1K2/3k4 b - - 0 1")
    assert shield_rank_for(mirrored, chess.BLACK) == 4


def test_no_shield_rank_without_a_pawn_near_promotion():
    """Philidor has no advanced pawn, and the rule does not apply there."""
    philidor = chess.Board("8/8/8/3k4/8/8/r7/3K1R2 w - - 0 1")
    assert shield_rank_for(philidor, chess.WHITE) is None


def test_no_shield_rank_when_the_king_is_not_in_front_of_the_pawn():
    board = chess.Board("8/3P4/8/8/8/8/r7/3K1R2 w - - 0 1")
    assert shield_rank_for(board, chess.WHITE) is None


def test_the_shield_beat_does_not_fire_on_philidor():
    """It did. Ra5+ on philidor[0] was captioned "it is not attacking
    anything yet" -- on a move that gives check, in a lesson about a
    different technique entirely."""
    fen = "8/8/8/3k4/8/8/r7/3K1R2 w - - 0 1"
    before, move, after, learner = _apply(fen, "Rf5+")
    assert detect_beat(before, move, after, learner) != BEAT_ROOK_TO_SHIELD_RANK


def test_the_shield_beat_does_not_fire_on_a_checking_move():
    """Preparing and attacking are different claims."""
    board = chess.Board(LUCENA)
    assert shield_rank_for(board, chess.WHITE) == 3
    before, move, after, learner = _apply(LUCENA, "Re4")
    assert detect_beat(before, move, after, learner) == BEAT_ROOK_TO_SHIELD_RANK
    assert not after.is_check()


def test_a_defender_check_is_a_beat():
    fen = "3K4/3P1k2/8/8/4R3/8/r7/8 b - - 0 1"
    before, move, after, learner = _apply(fen, "Ra8+", learner=chess.WHITE)
    assert detect_beat(before, move, after, learner) == BEAT_CHECK


def test_the_learner_giving_check_is_not_the_check_beat():
    """The beat is about being checked -- that is the problem the plan solves."""
    fen = "3K4/3P1k2/8/8/4R3/8/r7/8 w - - 0 1"
    before, move, after, learner = _apply(fen, "Re7+")
    assert detect_beat(before, move, after, learner) != BEAT_CHECK


def test_king_capturing_the_checker_is_a_beat():
    fen = "8/rK6/8/8/8/8/8/6k1 w - - 0 1"
    board = chess.Board(fen)
    assert board.is_check()
    before, move, after, learner = _apply(fen, "Kxa7")
    assert detect_beat(before, move, after, learner) == BEAT_CAPTURED_CHECKER


def test_an_ordinary_capture_while_not_in_check_is_not_that_beat():
    fen = "8/r7/1K6/8/8/8/8/6k1 w - - 0 1"
    board = chess.Board(fen)
    assert not board.is_check()
    before, move, after, learner = _apply(fen, "Kxa7")
    assert detect_beat(before, move, after, learner) != BEAT_CAPTURED_CHECKER


def test_promotion_and_promotion_with_mate_are_distinguished():
    before, move, after, learner = _apply("8/3P4/8/8/8/8/8/K5k1 w - - 0 1", "d8=Q")
    assert detect_beat(before, move, after, learner) == BEAT_PROMOTION

    before, move, after, learner = _apply("6k1/1P3ppp/8/8/8/8/8/K7 w - - 0 1", "b8=Q#")
    assert detect_beat(before, move, after, learner) == BEAT_PROMOTION_MATE


def test_mate_without_promotion_is_its_own_beat():
    before, move, after, learner = _apply("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Ra8#")
    assert detect_beat(before, move, after, learner) == BEAT_MATE


# --- what the beats say ----------------------------------------------------

def test_the_first_check_explains_and_later_ones_do_not_repeat_it():
    """Six identical sentences in one line reads as a broken record."""
    fen = "3K4/3P1k2/8/8/4R3/8/r7/8 b - - 0 1"
    before, move, after, learner = _apply(fen, "Ra8+", learner=chess.WHITE)
    first = _beat_coaching(BEAT_CHECK, before, move, after, check_index=0)
    later = _beat_coaching(BEAT_CHECK, before, move, after, check_index=3)
    last = _beat_coaching(BEAT_CHECK, before, move, after, check_index=3,
                          is_last_check=True)
    assert first != later != last
    assert first != last
    for text in (first, later, last):
        assert text and text[0].isupper() and text.endswith(".")


def test_the_promotion_line_points_back_at_the_plan():
    before, move, after, learner = _apply("6k1/1P3ppp/8/8/8/8/8/K7 w - - 0 1", "b8=Q#")
    text = _beat_coaching(BEAT_PROMOTION_MATE, before, move, after)
    assert "queen" in text.lower()
    assert "checkmate" in text.lower()
    assert "plan" in text.lower()


def test_no_beat_line_names_a_centipawn_or_a_detector():
    fen = "3K4/3P1k2/8/8/4R3/8/r7/8 b - - 0 1"
    before, move, after, learner = _apply(fen, "Ra8+", learner=chess.WHITE)
    for beat in (BEAT_CHECK, BEAT_PROMOTION, BEAT_MATE):
        text = _beat_coaching(beat, before, move, after).lower()
        assert "cp" not in text.split()
        assert "_" not in text


# --- the line itself (needs an engine) -------------------------------------

needs_engine = pytest.mark.skipif(
    _stockfish_path() is None, reason="no Stockfish on this machine"
)


@needs_engine
def test_the_lucena_line_reaches_a_promotion():
    c = build_continuation(LUCENA, "Re4")
    assert c.unavailable_reason is None
    assert c.reached_promotion is True
    assert c.moves
    assert c.moves[0].san == "Re4"


@needs_engine
def test_every_move_carries_coaching_and_no_dataclass_repr():
    """Both halves of this shipped broken in one sitting: reading
    decision.caption rendered "TextSurface(caption='...', rule_name='...')"
    into the lesson, and reading surface.caption on the wrong object returned
    empty strings for every connecting move."""
    c = build_continuation(LUCENA, "Re4")
    assert c.moves
    for m in c.moves:
        assert "TextSurface" not in m.coaching
        assert "rule_name" not in m.coaching
    # Every BEAT speaks. Connective moves after the last decisive beat are
    # deliberately silent -- the central pipeline is a review captioner and
    # produced "Look at what it attacks now" three times running there.
    for m in c.moves:
        if m.beat:
            assert m.coaching, f"beat ply {m.ply} ({m.san}) has no coaching"
    assert c.moves[0].coaching
    assert c.moves[-1].coaching, "the finish must always speak"


@needs_engine
def test_the_shuffling_moves_before_the_finish_stay_quiet():
    """Filler reads worse than silence, and the board still moves."""
    c = build_continuation(LUCENA, "Re4")
    beats = [m.ply for m in c.moves if m.beat]
    assert len(beats) >= 2
    last_decisive = beats[-2]
    quiet = [m for m in c.moves if not m.beat and m.ply > last_decisive]
    assert quiet, "this line should have connective moves after the last beat"
    for m in quiet:
        assert m.coaching == ""


@needs_engine
def test_the_line_is_legal_from_the_starting_position():
    c = build_continuation(LUCENA, "Re4")
    board = chess.Board(c.start_fen)
    for m in c.moves:
        assert board.fen() == m.fen_before
        move = board.parse_san(m.san)
        board.push(move)
        assert board.fen() == m.fen_after


@needs_engine
def test_an_illegal_first_move_is_reported_not_raised():
    c = build_continuation(LUCENA, "Rxh8")
    assert c.moves == []
    assert c.unavailable_reason


def test_a_missing_engine_degrades_instead_of_failing(monkeypatch):
    """With no engine the lesson behaves exactly as it does today."""
    import services.lesson_continuation as mod

    monkeypatch.setattr(mod, "_stockfish_path", lambda: None)
    c = mod.build_continuation(LUCENA, "Re4")
    assert c.moves == []
    assert c.unavailable_reason == "no engine available"
