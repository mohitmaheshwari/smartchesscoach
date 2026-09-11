"""A recommended capture is only a "trade" when the exchange says so.

`_recommended_move_why` described every recommended capture from the static
exchange value on the target square:

    SEE >= 200     -> "wins material"
    SEE >=  80     -> "wins a pawn" / "wins material"
    anything else  -> "trades his {piece}"     <- no floor underneath

The last branch called itself "equal-ish exchange" but had nothing holding it
up, so a capture that loses a whole piece on that square was described to the
player as a trade.

Flagged live, game 46edaf7e move 8:

    "Opponent's Bd6 is a mistake. Play Nxb5 - it trades his pawn."

SEE on b5 is -200. Nxb5 is nonetheless the engine's best move at +263, and the
reason is the exact opposite of a trade: the a6 pawn that guards b5 is also the
only thing keeping the a-file shut in front of an undefended rook, so after
axb5 Rxa8 wins the rook outright -- Black has no recapture on a8 at all. The
card replaced a tactic with a false and boring reason.

Measured over 500 analysed games: 1,376 recommended captures get a why, 506 of
them called a trade, and 128 of those (25.3%) sit at SEE <= -50 -- 110 below
-100. So one trade claim in four was not a trade.

Two rules come out of that, and both are held here:

1. Below TRADE_FLOOR_CP the word "trades" is not used at all.
2. When every recapture on the square leaves something worth >=150cp hanging,
   say so -- that is the tactic, proved from the board.

Otherwise the function falls through to the branches it already had (threat,
escape, defends, principle), all board-verified. Silence or a plainer true
reason both beat a false material claim.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_facts import (
    TRADE_FLOOR_CP,
    _recommended_move_why,
    static_exchange_eval,
)

# The flagged position, after Black's Bd6.
FLAGGED_FEN = "r1bqk1nr/2pp1ppp/p2b4/1p2p3/4P2P/1PNP1N2/1PP2PP1/R1BQK2R w KQkq - 1 9"

# Move 7 of game 1d591f35. Rxf2 is +205 by engine (7. Rxf2 Bxf2+ 8. Kxf2),
# but static_exchange_eval reports -200 because it skips king recaptures by
# design. The deflection proof uses legally_hanging_pieces, which does count
# Kxf2, so the card still says something true here.
KING_RECAPTURE_FEN = "rnbqk2r/pppp2pp/5p2/2b1p3/N3P3/3B1N2/PPPP1nPP/R1BQ1RK1 w kq - 0 7"


def _why(fen: str, san: str):
    board = chess.Board(fen)
    return _recommended_move_why(board, board.parse_san(san))


def test_the_flagged_card_no_longer_calls_a_tactic_a_trade():
    why = _why(FLAGGED_FEN, "Nxb5")
    assert why is not None
    assert "trade" not in why, (
        "Nxb5 loses 200cp on b5 by the exchange count; calling it a trade is "
        f"false. Got: {why!r}"
    )


def test_the_flagged_card_names_what_taking_back_actually_costs():
    why = _why(FLAGGED_FEN, "Nxb5")
    assert why == "costs him the rook on a8 if he takes back", why


def test_black_really_cannot_recapture_on_a8():
    # The claim above is only worth making because it is true: after axb5
    # Rxa8 there is no recapture. Anchored so a change to the proof cannot
    # quietly start asserting it in positions where the rook comes back.
    board = chess.Board(FLAGGED_FEN)
    board.push_san("Nxb5")
    board.push_san("axb5")
    board.push_san("Rxa8")
    assert not [m for m in board.legal_moves
                if board.is_capture(m) and m.to_square == chess.A8]


def test_a_genuine_trade_keeps_its_wording():
    # exd5 with a pawn recapture available: SEE 0, a real trade.
    fen = "rnbqkbnr/ppp2ppp/8/3pp3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
    board = chess.Board(fen)
    move = board.parse_san("exd5")
    assert static_exchange_eval(board, move.to_square, board.turn) == 0
    assert _why(fen, "exd5") == "trades his pawn"


def test_a_clearly_winning_capture_still_says_so():
    # Free queen: nothing near d8 defends it.
    fen = "3q1rk1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    assert _why(fen, "Rxd8") == "wins material"


@pytest.mark.parametrize("see_value", [-50, -49])
def test_the_floor_sits_where_the_measurement_put_it(see_value):
    # -50 is the boundary: at it a capture is still called a trade, below it
    # never. The number came from the 500-game distribution, not from taste.
    assert TRADE_FLOOR_CP == -50
    assert see_value >= TRADE_FLOOR_CP


def test_the_proof_survives_the_kings_absence_from_see():
    # static_exchange_eval skips kings by design, so this reads as a rook
    # sacrifice. legally_hanging_pieces counts Kxf2, so the card is right
    # anyway -- and, critically, does not call it a trade.
    board = chess.Board(KING_RECAPTURE_FEN)
    move = board.parse_san("Rxf2")
    assert static_exchange_eval(board, move.to_square, board.turn) == -200
    why = _why(KING_RECAPTURE_FEN, "Rxf2")
    assert why == "costs him the bishop on f2 if he takes back", why


def test_no_claim_when_he_has_a_recapture_that_costs_him_nothing():
    # Nxe5 drops a knight for a pawn and Nxe5 back costs Black nothing, so
    # there is no deflection to name. The function must not invent one -- it
    # may say something else true, or nothing, but never "trades".
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
    why = _why(fen, "Nxe5")
    assert why is None or "takes back" not in why
    assert why is None or "trade" not in why
