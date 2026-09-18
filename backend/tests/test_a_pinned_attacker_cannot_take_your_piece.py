"""A piece is not hanging if nothing can legally take it.

`board.attackers()` is PSEUDO-legal: it lists pieces whose move pattern
reaches a square, not pieces that may actually capture there. `_winnable` used
it directly, so a pinned attacker -- or one belonging to a side that is in
check and must answer the check first -- made a perfectly safe piece read as
hanging.

Measured on 120 production fires, 2026-09-18: 13 were provably false (11%),
and 9 of the 13 were exactly this. At the 95% promotion bar that disqualifies
the detector on its own, so a review session spent on it would have failed
after the fact -- which is the expensive way to find this out.

Found by building a mechanical pre-filter for the review queue. The filter
turned out to be worth ~2% as a time-saver and worth much more as this.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.played_hangs_detector import (  # noqa: E402
    _winnable,
    detect_played_hangs,
)

# Black king a7, black pawn a6, white queen a4: the pawn is pinned down the
# a-file, so axb5 is illegal and the knight that just landed on b5 is safe.
# This is a real production position, verified move-by-move.
PINNED = "3r4/kpp1qpp1/p3bn1p/1N6/Q2P4/P2B1P2/1PP3PP/2K4R b - - 3 25"


def test_the_position_really_does_pin_the_attacker():
    """Assert the premise, so the test cannot silently stop testing anything."""
    board = chess.Board(PINNED)
    assert board.piece_at(chess.B5) == chess.Piece(chess.KNIGHT, chess.WHITE)
    # The pawn attacks b5 by move pattern...
    assert chess.A6 in board.attackers(chess.BLACK, chess.B5)
    # ...and cannot actually take.
    assert chess.Move.from_uci("a6b5") in board.pseudo_legal_moves
    assert chess.Move.from_uci("a6b5") not in board.legal_moves


def test_a_pinned_attacker_does_not_make_a_piece_hang():
    board = chess.Board(PINNED)
    assert _winnable(board, chess.B5, chess.WHITE) is True, (
        "the pseudo-legal answer, kept for the before-snapshot"
    )
    assert _winnable(board, chess.B5, chess.WHITE,
                     require_legal_capture=True) is False, (
        "nothing can legally take on b5, so the knight is not hanging"
    )


def test_the_before_snapshot_stays_pseudo_legal_on_purpose():
    """Over-counting what was ALREADY hanging can only suppress a fire.

    Under-counting it would invent new ones, which is the wrong direction, so
    the default must remain the looser test.
    """
    import inspect

    sig = inspect.signature(_winnable)
    assert sig.parameters["require_legal_capture"].default is False

    source = (BACKEND / "services" / "played_hangs_detector.py").read_text(
        encoding="utf-8")
    assert "before = _winnable_squares(board_before, mover)\n" in source
    assert "require_legal_capture=True)" in source


def test_a_genuine_hang_still_fires():
    """The gate must not mute the detector's real job."""
    # White plays Qh5??; the queen lands where the g6 pawn simply takes it.
    board = chess.Board(
        "rnbqkbnr/pppp1pp1/7p/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 3")
    hang = detect_played_hangs(board, board.parse_san("Qxh6"), cp_loss=900)
    assert hang is not None, "a queen taken for free must still be reported"
    assert hang["square"] == "h6"
    assert hang["piece"] == "queen"


def test_nothing_hanging_reports_nothing():
    board = chess.Board()
    assert detect_played_hangs(board, board.parse_san("e4"), cp_loss=150) is None
