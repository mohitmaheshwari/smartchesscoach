"""A king walk in the opening is never "Good", whatever the number says.

Mohit 2026-09-28, on a card badged GOOD with a green tick: "coach shouldn't
really appreciate this, king out in the open in the second or third move you
know, this should be criticised."

The move was 2...Kf7 at cp_loss 71 -- four points under the 75 the rating
band needs to call anything an inaccuracy, because the position was already
poor after 1...f6 so the engine saw little ADDITIONAL loss. Centipawns
measure the position. They do not measure having given up castling on move
two.

The first version of this rule was WRONG and the corpus said so. Over 600
games, 38 early king moves forfeit castling and 25 have cp_loss 0, because
they are recaptures -- Kxe2, Kxf7, Kxd8 -- usually forced and correct.
Criticising those would be worse than the bug being fixed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import is_quiet_opening_king_walk  # noqa: E402


def _walk(fen, san, move_number=3):
    board = chess.Board(fen)
    return is_quiet_opening_king_walk(board, board.parse_san(san), move_number)


class TestItFires:
    def test_the_reported_card(self):
        # 1.e4 f6 2.d4 Kf7 -- castling gone on move two, for nothing.
        assert _walk(
            "rnbqkbnr/ppppp1pp/5p2/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2",
            "Kf7", 2,
        ) is True

    def test_it_is_about_losing_castling_not_about_the_square(self):
        board = chess.Board(
            "rnbqkbnr/ppppp1pp/5p2/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
        )
        after = board.copy()
        after.push(board.parse_san("Kf7"))
        assert board.has_kingside_castling_rights(chess.BLACK)
        assert not after.has_kingside_castling_rights(chess.BLACK)
        assert not after.has_queenside_castling_rights(chess.BLACK)


class TestItDoesNotFire:
    def test_a_recapture_is_usually_forced_and_fine(self):
        # 25 of the 38 early king moves in 600 games are this shape. The
        # bishop must really be ON f7 -- an earlier version of this test put
        # it on g7, so "Kxf7" was not a capture at all and the fixture
        # proved nothing.
        fen = "rnbqkbnr/pppppBpp/8/8/8/8/PPPPPPPP/RNBQK1NR b KQkq - 0 3"
        board = chess.Board(fen)
        assert board.piece_at(chess.F7) is not None      # guard the fixture
        assert board.is_capture(board.parse_san("Kxf7"))
        assert _walk(fen, "Kxf7") is False

    def test_castling_itself_is_the_thing_we_want(self):
        assert _walk(
            "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
            "O-O", 4,
        ) is False

    def test_a_king_that_already_lost_its_rights(self):
        # Nothing left to give up, so nothing to criticise here. The FEN must
        # give the SIDE TO MOVE no rights -- the first version left White
        # holding "KQ" and then moved White's king, so it fired correctly and
        # the test was simply wrong.
        fen = "rnbq1bnr/pppp1ppp/4k3/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQ - 2 3"
        board = chess.Board(fen)
        assert board.turn is chess.BLACK
        assert not board.has_kingside_castling_rights(chess.BLACK)
        assert not board.has_queenside_castling_rights(chess.BLACK)
        assert _walk(fen, "Kd6", 3) is False

    def test_the_opening_window_ends(self):
        assert _walk(
            "rnbqkbnr/ppppp1pp/5p2/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2",
            "Kf7", 20,
        ) is False

    def test_a_non_king_move(self):
        assert _walk(
            "rnbqkbnr/ppppp1pp/5p2/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2",
            "e6", 2,
        ) is False

    def test_missing_inputs_do_not_raise(self):
        board = chess.Board()
        assert is_quiet_opening_king_walk(None, None, 2) is False
        assert is_quiet_opening_king_walk(board, None, 2) is False
        assert is_quiet_opening_king_walk(board, chess.Move.null(), 2) is False
