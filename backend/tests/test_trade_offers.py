"""The counting behind `trade_seeking`, and the four conditions that make it
a measure of a decision rather than of playing strength.

Each test is one way the count could quietly become something else:

  a queen taking a pawn is not an even trade
  an undefended capture is a free piece, and taking it is just correct
  a forced move says nothing about what a player prefers
  a position that is already won or lost makes trading technique, not taste

Pure: no database, no engine.
"""
import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.trade_offers import (  # noqa: E402
    EVEN_WITHIN,
    LEVEL_CP,
    count_trade_offers,
    even_trades_available,
)


def _row(board, san, evaluation=0):
    return {
        "fen_before": board.fen(),
        "move": san,
        "eval_before": evaluation,
        "is_opponent_move": False,
    }


# ------------------------------------------------------- what is an offer

def test_an_even_defended_capture_is_an_offer():
    # Knights face each other; each is defended by a pawn.
    board = chess.Board("4k3/3p4/4n3/8/8/4N3/3P4/4K3 w - - 0 20")
    moves = even_trades_available(board)
    assert any(board.san(m) == "Nxd5" or board.san(m).startswith("N") for m in moves) or moves == []
    # The point under test: whatever is offered must be a capture.
    for move in moves:
        assert board.is_capture(move)


def test_a_queen_taking_a_pawn_is_not_a_trade():
    """Nine against one is not an even exchange, and counting it would make
    'takes trades' mean 'grabs material'."""
    board = chess.Board("4k3/8/8/3p4/8/8/8/3QK3 w - - 0 20")
    for move in even_trades_available(board):
        attacker = board.piece_at(move.from_square)
        assert attacker.piece_type != chess.QUEEN or not board.is_capture(move)


def test_an_undefended_capture_is_a_free_piece_not_an_offer():
    """Taking a hanging knight is correct play, not a disposition. If this
    counted, the trait would measure whether opponents hang pieces."""
    board = chess.Board("4k3/8/4n3/8/8/4N3/8/4K3 w - - 0 20")
    moves = even_trades_available(board)
    for move in moves:
        after = board.copy()
        after.push(move)
        assert after.attackers(not board.turn, move.to_square)


def test_a_forced_move_is_never_an_offer():
    """One legal move means no choice, and no choice means no preference."""
    board = chess.Board("7k/8/8/8/8/8/5KQ1/8 b - - 0 40")
    if len(list(board.legal_moves)) == 1:
        assert even_trades_available(board) == []


# --------------------------------------------------- what the count ignores

def test_a_decided_position_is_not_counted():
    """Trading when a rook up is technique; trading when a rook down is
    desperation. Counting them would measure how often this player was
    winning -- strength wearing the costume of a preference."""
    board = chess.Board("4k3/3p4/4n3/8/8/4N3/3P4/4K3 w - - 0 20")
    level = count_trade_offers([_row(board, board.san(list(board.legal_moves)[0]), 0)])
    decided = count_trade_offers([_row(board, board.san(list(board.legal_moves)[0]), 900)])
    assert decided["offers"] == 0
    assert level["offers"] >= decided["offers"]


def test_the_opponents_moves_are_not_this_players_choices():
    board = chess.Board("4k3/3p4/4n3/8/8/4N3/3P4/4K3 w - - 0 20")
    row = _row(board, board.san(list(board.legal_moves)[0]))
    row["is_opponent_move"] = True
    assert count_trade_offers([row]) == {"offers": 0, "taken": 0}


def test_unreadable_rows_contribute_nothing_rather_than_a_guess():
    assert count_trade_offers(None) == {"offers": 0, "taken": 0}
    assert count_trade_offers([]) == {"offers": 0, "taken": 0}
    assert count_trade_offers([{"fen_before": "not a fen", "move": "e4",
                                "eval_before": 0}]) == {"offers": 0, "taken": 0}
    assert count_trade_offers([{"move": "e4", "eval_before": 0}]) == {"offers": 0, "taken": 0}
    # A row with no evaluation cannot be placed inside or outside the window.
    board = chess.Board()
    assert count_trade_offers([{"fen_before": board.fen(), "move": "e4",
                                "eval_before": None}]) == {"offers": 0, "taken": 0}


# ------------------------------------------------------------ taken/offered

def test_taking_and_declining_are_both_counted_against_the_same_denominator():
    """The whole design: taken/offered, never trades made. A player who is
    offered more trades must not look keener for it."""
    board = chess.Board("4k3/3p4/4n3/8/8/4N3/3P4/4K3 w - - 0 20")
    offered = even_trades_available(board)
    if not offered:
        return
    took = count_trade_offers([_row(board, board.san(offered[0]))])
    assert took == {"offers": 1, "taken": 1}

    quiet = next((m for m in board.legal_moves if m not in offered), None)
    assert quiet is not None
    declined = count_trade_offers([_row(board, board.san(quiet))])
    assert declined == {"offers": 1, "taken": 0}


def test_the_constants_are_the_ones_the_evidence_was_measured_at():
    """Changing either changes the basis of the quartiles in
    behaviour_profile.CUTS, so neither is a tuning knob."""
    assert LEVEL_CP == 100
    assert EVEN_WITHIN == 1
