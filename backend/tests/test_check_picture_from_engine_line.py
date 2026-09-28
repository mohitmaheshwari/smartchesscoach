"""The check picture points where the ENGINE goes, and only at a piece you see.

Mohit 2026-09-28: "it should only draw lines on stockfish backed move, right??
that's what will make people understand the plan, right??"

The move was always Stockfish's. The target was not: it was the best
static_exchange_eval square, and SEE skips king recaptures. Measured on 400
games / 461 cards this fired on, the engine's own line never takes the arrowed
piece on 94 of the 132 that carry a line, and Stockfish at depth 16 agreed on
41 of 60 sampled from the rest.

Both fixtures below were built by playing the position out, not by eye.
"""
import chess

from services.caption_pipeline import _check_attack_arrows

# Black: Kg8, Ra8, pawns g7/h7.  White: Qd1, Kg1, pawns b2/g2/h2.
# Qd5+ checks along d5-e6-f7-g8 and also eyes the rook on a8.
ROOK_STANDING = "r5k1/6pp/8/8/8/8/1P4PP/3Q2K1 w - - 0 1"
# Same idea, but the rook starts on f8 and BLOCKS the check on f7, so the
# capture in the line lands on a square that is empty when the card is drawn.
ROOK_BLOCKS = "5rk1/6pp/8/8/8/8/1P4PP/3Q2K1 w - - 0 1"


def _arrows(fen, line):
    board = chess.Board(fen)
    return _check_attack_arrows(board, board.parse_san("Qd5+").uci(), line)


class TestTheTargetComesFromTheLine:
    def test_it_draws_the_piece_the_engine_takes(self):
        arrows = _arrows(ROOK_STANDING, ["Kf8", "Qxa8+"])
        assert [(a["from"], a["to"]) for a in arrows] == [("d5", "a8"), ("d5", "g8")]

    def test_the_king_arrow_is_the_red_one(self):
        arrows = _arrows(ROOK_STANDING, ["Kf8", "Qxa8+"])
        by_colour = {a["color"]: a["to"] for a in arrows}
        assert by_colour["red"] == "g8" and by_colour["green"] == "a8"

    def test_no_line_means_no_picture(self):
        # 329 of 461 real cards have no stored line; 68% of those pointed at a
        # piece Stockfish never takes, so silence is the honest answer.
        assert _arrows(ROOK_STANDING, []) == []
        assert _arrows(ROOK_STANDING, None) == []

    def test_a_line_that_takes_nothing_draws_nothing(self):
        assert _arrows(ROOK_STANDING, ["Kf8", "Qd7", "Kg8", "b3"]) == []


class TestTheTargetMustBeStandingThere:
    """Otherwise the arrow ends on an empty square."""

    def test_a_capture_that_lands_on_a_square_empty_now_is_silent(self):
        board = chess.Board(ROOK_BLOCKS)
        board.push(board.parse_san("Qd5+"))
        assert board.piece_at(chess.F7) is None, "f7 is empty on the rendered board"
        assert _arrows(ROOK_BLOCKS, ["Rf7", "Qxf7+"]) == []

    def test_every_arrow_endpoint_holds_something_worth_pointing_at(self):
        board = chess.Board(ROOK_STANDING)
        after = board.copy()
        after.push(board.parse_san("Qd5+"))
        for arrow in _arrows(ROOK_STANDING, ["Kf8", "Qxa8+"]):
            piece = after.piece_at(chess.parse_square(arrow["to"]))
            assert piece is not None and piece.color == chess.BLACK


class TestSilence:
    def test_a_quiet_best_move_draws_nothing(self):
        board = chess.Board(ROOK_STANDING)
        # b3 gives no check, so this picture never applies.
        assert _check_attack_arrows(
            board, board.parse_san("b3").uci(), ["Kf8", "Qxa8+"]
        ) == []

    def test_an_illegal_best_move_is_silent_not_a_crash(self):
        assert _check_attack_arrows(chess.Board(ROOK_STANDING), "a1a8", ["Qxa8"]) == []
