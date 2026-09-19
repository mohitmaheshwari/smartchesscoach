"""A dropped knight is not an opening-theory lesson.

Mohit, reviewing a `left_book` card: "I feel like this is more of a blunder,
hanging piece or something, not left your book."

The move was Nxe5 in the Italian (1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5). It takes a
pawn, Nxe5 takes the knight straight back, net -200 -- and the engine line
stored with the claim literally begins with the recapture. The card told a
900-rated player that c3 is the move and they had left theory.

`played_hangs_detector` already fires on the same move and says "it leaves
your knight on e5 hanging -- no defender after the move", which is what the
player actually needs. So left_book stands down and lets that speak, the same
way the hang detector stands down for the mate path.

Measured on 18 live claims: 2 (11%) are this shape; the other 16 are genuine
book deviations and must keep firing.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess  # noqa: E402

from services.cognitive_gap_subtypes import (  # noqa: E402
    LEFT_BOOK_SUBTYPE,
    _classify_left_book,
)
from services.played_hangs_detector import detect_played_hangs  # noqa: E402

ITALIAN = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


def _move(fen, uci, san, best, cp_loss, move_number=4):
    return {"fen_before": fen, "move_uci": uci, "move": san,
            "best_move": best, "cp_loss": cp_loss, "move_number": move_number}


def _context(expected_san, move_number=4):
    return {"opening_deviation": {"deviation": {
        "user_move_number": move_number, "expected_san": expected_san}}}


def test_the_premise_nxe5_really_does_drop_a_knight():
    """Assert the position, so this cannot silently stop testing anything."""
    board = chess.Board(ITALIAN)
    nxe5 = board.parse_san("Nxe5")
    assert board.piece_at(nxe5.to_square).piece_type == chess.PAWN
    after = board.copy()
    after.push(nxe5)
    assert chess.C6 in after.attackers(chess.BLACK, chess.E5), (
        "the c6 knight must be able to recapture"
    )


def test_the_hang_detector_already_says_the_right_thing():
    """The reason left_book can stand down: a better caption exists."""
    board = chess.Board(ITALIAN)
    hang = detect_played_hangs(board.copy(), board.parse_san("Nxe5"), cp_loss=354)
    assert hang is not None
    assert hang["square"] == "e5"
    assert hang["piece"] == "knight"


def test_left_book_stands_down_when_the_move_hangs_material():
    board = chess.Board(ITALIAN)
    uci = board.parse_san("Nxe5").uci()
    subtype, _ = _classify_left_book(
        _move(ITALIAN, uci, "Nxe5", "c3", 354), _context("c3"))
    assert subtype is None, "a dropped knight is not a book question"


def test_a_real_book_deviation_still_fires():
    """16 of 18 live claims are these; muting them would be the wrong fix."""
    # A quiet deviation that loses ground without hanging anything: a3 in the
    # Italian, where the book and the engine both want c3.
    board = chess.Board(ITALIAN)
    uci = board.parse_san("a3").uci()
    subtype, severity = _classify_left_book(
        _move(ITALIAN, uci, "a3", "c3", 150), _context("c3"))
    assert subtype == LEFT_BOOK_SUBTYPE
    assert severity == "moderate"


def test_an_unreadable_board_does_not_suppress_a_claim():
    """Failing open: we cannot price it, so we do not silence it."""
    subtype, _ = _classify_left_book(
        _move("not a fen", "e2e4", "e4", "c3", 200), _context("c3"))
    assert subtype == LEFT_BOOK_SUBTYPE
