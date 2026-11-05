"""A game that begins from a FEN (lichess "From Position", Chess960) is replayed
from THAT position, not from the standard start.

Mohit 2026-11-05 on 10c92688, a "Benoni Defense Rapid Arena" game: every card
good, no caption, no why button, move names "hxh4" and "Qxc2" he never played.
The replay began from chess.Board() while the PGN carried [FEN ...] [SetUp "1"].
"""
from __future__ import annotations

import io
import os
import sys

import chess
import chess.pgn

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.game_decryption_v5_service import _san_history, is_book_opening_move  # noqa: E402

# The real headers and first moves of 10c92688 (clock comments dropped).
BENONI_PGN = """[Event "Benoni Defense Rapid Arena"]
[Site "https://lichess.org/game/6ykdzyRg"]
[Variant "From Position"]
[FEN "rnbqkb1r/pp1p1ppp/4pn2/2pP4/2P5/8/PP2PPPP/RNBQKBNR w KQkq - 0 1"]
[SetUp "1"]
[Result "0-1"]

1. Nc3 d6 2. Bg5 Be7 3. Nf3 Nbd7 4. dxe6 fxe6 5. Qc2 O-O 6. h4 0-1
"""

STORED_SANS = ["Nc3", "d6", "Bg5", "Be7", "Nf3", "Nbd7", "dxe6", "fxe6", "Qc2", "O-O", "h4"]


def _game():
    return chess.pgn.read_game(io.StringIO(BENONI_PGN))


class TestTheReplayStart:
    def test_the_pgn_board_is_the_benoni_position_not_the_standard_start(self):
        game = _game()
        assert game.board().fen() == "rnbqkb1r/pp1p1ppp/4pn2/2pP4/2P5/8/PP2PPPP/RNBQKBNR w KQkq - 0 1"
        assert game.board().fen() != chess.Board().fen()

    def test_sans_taken_on_the_pgn_board_are_the_moves_played(self):
        # This is what the engine side stores (stockfish_service replays from
        # game.board()); the cards must name the same moves.
        game = _game()
        board = game.board()
        sans = []
        for mv in game.mainline_moves():
            sans.append(board.san(mv))
            board.push(mv)
        assert sans == STORED_SANS

    def test_the_standard_start_produces_the_garbage_the_cards_carried(self):
        # The negative control: from chess.Board() the fourth move dxe6 is not
        # even legal (no pawn on d5), which is the "PGN-replay drift" the log
        # showed, and the moves before it are read on the wrong board.
        game = _game()
        board = chess.Board()
        moves = list(game.mainline_moves())
        for mv in moves[:6]:
            board.push(mv)
        assert not board.is_legal(moves[6])


class TestSanHistory:
    def test_history_is_replayed_from_the_boards_own_start(self):
        game = _game()
        board = game.board()
        moves = list(game.mainline_moves())
        for mv in moves[:8]:
            board.push(mv)
        assert _san_history(board) == STORED_SANS[:8]
        assert board.san(moves[8]) == "Qc2"

    def test_a_standard_game_is_unchanged(self):
        board = chess.Board()
        for san in ("e4", "e5", "Nf3", "Nc6"):
            board.push_san(san)
        assert _san_history(board) == ["e4", "e5", "Nf3", "Nc6"]

    def test_the_book_gate_survives_a_from_position_board_without_a_history(self):
        # Before: the fallback replayed board.move_stack from chess.Board() and
        # raised inside a bare except, so the gate's answer came from the later
        # checks on a wrong premise. Now the sequence is read from the real
        # start and simply matches no opening.
        game = _game()
        board = game.board()
        moves = list(game.mainline_moves())
        for mv in moves[:2]:
            board.push(mv)
        assert is_book_opening_move(board, "Bg5", 2, None, 68) is False
