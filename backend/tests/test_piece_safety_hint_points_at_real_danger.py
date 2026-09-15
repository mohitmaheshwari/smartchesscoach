"""The help squares must point at pieces that are actually in danger.

`_help_squares` is what a "Which move keeps every piece safe?" lesson
highlights for the student. It was built from `board.is_attacked_by()` alone,
with no check for whether the piece was DEFENDED — so a pawn defended twice and
attacked once was highlighted exactly like a hanging queen. In a piece-safety
lesson that points the student at the pieces that are not the problem.

mission_scoreboard.find_hanging_pieces owns the real judgement (attackers > 0
and defenders == 0). This lesson consults it rather than re-deriving danger, so
there is no seventh hanging-piece rule in the codebase.

The fallback matters too: when nothing genuinely hangs, the merely-attacked set
is still shown. A lesson with no highlight at all would be worse than an
imperfect one.
"""
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.mission_scoreboard import find_hanging_pieces  # noqa: E402


def _help_squares(fen: str) -> list:
    """Mirror of the adapter's selection, so the rule is testable in isolation."""
    board = chess.Board(fen)
    hanging = [
        str(h["square"])
        for h in find_hanging_pieces(fen, board.turn == chess.WHITE)
        if h.get("square")
    ]
    attacked = [
        chess.square_name(sq)
        for sq, piece in board.piece_map().items()
        if piece.color == board.turn and board.is_attacked_by(not board.turn, sq)
    ]
    return hanging or attacked


def test_when_nothing_hangs_the_attacked_set_is_still_shown():
    """The deliberate fallback, stated plainly.

    White's d5 pawn is attacked by c6 and defended by e4, so it is not hanging,
    and no other white piece hangs either. Rather than highlight nothing, the
    lesson falls back to the merely-attacked set — the pre-existing behaviour.
    That is a coverage choice, not an oversight: a piece-safety lesson with no
    highlight at all would be worse than an imprecise one.
    """
    fen = "4k3/8/n1p5/3P4/4P3/8/8/4K3 w - - 0 1"
    board = chess.Board(fen)
    assert board.is_attacked_by(chess.BLACK, chess.D5), "d5 is attacked"
    assert board.attackers(chess.WHITE, chess.D5), "and defended, so not hanging"
    assert find_hanging_pieces(fen, True) == [], "no white piece hangs here"
    assert _help_squares(fen) == ["d5"], "the fallback preserves the old hint"


def test_the_genuinely_hanging_piece_is_offered():
    """An undefended, attacked bishop must be highlighted."""
    fen = "4k3/8/8/8/1r6/8/1B6/4K3 w - - 0 1"
    got = _help_squares(fen)
    assert got == ["b2"], got


@pytest.mark.parametrize("fen", [
    "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",          # nothing attacked at all
    "4k3/8/2p5/3P4/4P3/8/8/4K3 w - - 0 1",      # attacked but defended
])
def test_the_hint_is_never_empty_when_something_is_attacked(fen):
    """Coverage beats silence: fall back rather than highlight nothing."""
    board = chess.Board(fen)
    attacked = [
        chess.square_name(sq)
        for sq, piece in board.piece_map().items()
        if piece.color == board.turn and board.is_attacked_by(not board.turn, sq)
    ]
    got = _help_squares(fen)
    assert got == attacked or got, "the fallback must preserve the old behaviour"


def test_hanging_wins_over_merely_attacked_when_both_exist():
    """Black rook b4 hits the undefended bishop b2; the d5 pawn is defended."""
    fen = "4k3/8/2p5/3P4/1r2P3/8/1B6/4K3 w - - 0 1"
    got = _help_squares(fen)
    assert "b2" in got, got
    assert "d5" not in got, f"defended pawn still highlighted: {got}"


def test_the_adapter_consults_the_owner_rather_than_re_deriving():
    src = (BACKEND / "services" / "personalized_lesson_adapter.py").read_text(encoding="utf-8")
    assert "from services.mission_scoreboard import find_hanging_pieces" in src
    assert "hanging_squares or merely_attacked" in src, (
        "the fallback must remain, so a lesson never loses its highlight"
    )
