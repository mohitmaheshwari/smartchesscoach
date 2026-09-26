"""A printed question must be one some move can satisfy.

This lesson prints "play a move that leaves nothing of yours hanging", and
correctness is exactly

    grade_destination_safety_candidate(fen, move).status == "pass"

That grader returns `piece_not_eligible` for every pawn and king move. So a
position whose only legal replies are pawn or king moves cannot be answered
correctly by anybody -- most often when the side to move is in check.

Measured on production 2026-09-26: 92 of 3,000 positions in the served pool
(3.1%). A session holds its current item until it is answered correctly, so
this is not a bad question, it is a dead end. The deploy gate found it by
getting pinned on one and serving the same position three runs running.
"""
import sys
from pathlib import Path

import chess

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.destination_safety_detector import (  # noqa: E402
    grade_destination_safety_candidate,
)
from services.lesson_question_spec import ANY_SAFE  # noqa: E402
from services.personalized_lesson_adapter import (  # noqa: E402
    _question_is_answerable,
)

# The exact position the gate pinned on. White is in check from the rook on
# e3; every escape is a king move, a pawn capture, or Be2 losing to Rxe2+.
DEAD_END = "rn3k2/ppp4p/6p1/2P5/2Q3bq/2P1r2N/PP3PPP/RN2KB1R w KQ - 0 14"

# An ordinary Italian position with plenty of safe developing moves.
ORDINARY = "r1bqkbnr/pppp1pp1/2n4p/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"


class _Spec:
    def __init__(self, accepts):
        self.accepts = accepts


def _passing_moves(fen):
    board = chess.Board(fen)
    return [
        move.uci() for move in board.legal_moves
        if str(grade_destination_safety_candidate(fen, move.uci())
               .get("status")) == "pass"
    ]


def test_the_dead_end_really_has_no_answer():
    """The premise, computed rather than asserted. Without this the test
    below could pass because the filter rejects everything."""
    assert chess.Board(DEAD_END).is_check(), "fixture should be a check"
    assert _passing_moves(DEAD_END) == []


def test_an_ordinary_position_has_many_answers():
    """The positive control. A filter that refuses everything would look
    identical to a working one without this."""
    assert len(_passing_moves(ORDINARY)) > 1


def test_an_unanswerable_position_is_not_served():
    assert _question_is_answerable(DEAD_END, _Spec(ANY_SAFE)) is False


def test_an_answerable_position_is_served():
    assert _question_is_answerable(ORDINARY, _Spec(ANY_SAFE)) is True


def test_a_question_family_we_cannot_judge_is_left_alone():
    """Refusing to serve content because this function has not learned to
    judge it would be worse than serving it."""
    assert _question_is_answerable(DEAD_END, _Spec("single_best")) is True


def test_an_unparseable_position_is_left_alone():
    assert _question_is_answerable("not a fen", _Spec(ANY_SAFE)) is True
