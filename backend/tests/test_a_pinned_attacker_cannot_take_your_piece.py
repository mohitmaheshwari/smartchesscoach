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


def test_a_piece_that_just_captured_is_trading_not_hanging():
    """Mohit found this on his second review card, from the raw evidence.

    Bxf3 takes a knight (300cp); gxf3 takes the bishop back (300cp). Net zero
    -- a trade. The detector reported "it leaves your bishop on f3 hanging".

    The cp_loss >= 100 gate does not catch it, because the move IS bad for an
    unrelated reason: Nxf3+ comes with check and the line ends Qxa1, winning a
    rook. 180cp of mistake, none of it a hang.

    Measured on 890 production fires: 193 (21.7%) were an even trade reported
    as a hang -- in a detector already at CAPTION grade, i.e. already saying
    this to players.
    """
    board = chess.Board(
        "r3kb1r/pp3ppp/2p1pq2/4n2b/1P6/P4N1P/2PPBPP1/R1BQR1K1 b kq - 1 13")
    bxf3 = board.parse_san("Bxf3")
    assert board.piece_at(bxf3.to_square).piece_type == chess.KNIGHT, (
        "premise: Bxf3 must be a capture of a knight"
    )
    assert detect_played_hangs(board, bxf3, cp_loss=180) is None, (
        "a bishop that just took a knight and gets recaptured is trading"
    )


def test_a_capture_that_really_does_lose_material_still_fires():
    """The gate must price the trade, not mute every capture.

    19.9% of fires are captures that genuinely lose material; those are real
    hangs and have to survive.
    """
    # Qxa7?? grabs a pawn and the rook on a8 takes the queen.
    board = chess.Board("r3k3/p7/8/8/8/8/8/Q3K3 w - - 0 1")
    qxa7 = board.parse_san("Qxa7")
    hang = detect_played_hangs(board, qxa7, cp_loss=800)
    assert hang is not None, "queen for a pawn is a hang, not a trade"
    assert hang["square"] == "a7"
    assert hang["piece"] == "queen"


def test_a_player_being_mated_is_not_told_a_piece_is_hanging():
    """Mohit's rule, and the hole testing it opened.

    His rule: a bigger engine loss means a PIECE went, not a pawn. Measured
    over 9,000 user mistakes it holds cleanly -- piece:pawn runs 1.1x, 1.5x,
    2.2x, 4.0x, 8.1x as the loss grows -- and then REVERSES above 900, where
    47.9% of moves lose no material at all. Those are mate swings.

    41 cards said "your queen on e3 is hanging" to a player being mated in 6.

    The gate cannot be the size of the loss: a player who is ALREADY lost
    walks into mate and the SWING is small while the position is mate (one
    real case at cp_loss 3,449). So the caller states whether a mate is on
    the board, and this abstains so the mate path can speak.
    """
    # White queen grabs a pawn while Black has mate on the board.
    board = chess.Board("6k1/5ppp/8/8/8/7q/5PPP/6K1 w - - 0 1")
    mv = board.parse_san("Kh1")
    assert detect_played_hangs(board, mv, cp_loss=9500, mate_in_play=True) is None
    # ...and a huge swing alone is enough even without the flag.
    assert detect_played_hangs(board, mv, cp_loss=9500) is None


def test_a_real_hang_in_a_lost_position_still_fires():
    """The gate must not mute material loss just because things are grim."""
    board = chess.Board("r3k3/p7/8/8/8/8/8/Q3K3 w - - 0 1")
    hang = detect_played_hangs(board, board.parse_san("Qxa7"), cp_loss=800,
                               mate_in_play=False)
    assert hang is not None and hang["piece"] == "queen"
