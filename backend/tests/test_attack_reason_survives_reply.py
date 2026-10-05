"""An "attacks the X" reason has to survive the opponent's best reply.

Mohit 2026-10-03, on "Qb5 was better -- it wins the knight on e8": "the question
is what is the best move for opponent after Qb5, because that will solve the
real caption of why Qb5, as knight can be moved right?" Then: "that's why
stockfish lines matter so much in teaching captions, and you always miss those."

Measured over 400 games: of 1,432 "attacks the X" reasons on recommended moves,
663 (46%) are answered in the stored line by simply moving X. Playing 60 of
those out at depth 18 and judging them with the engine rather than a piece
count: 27% already decided, 30% nothing measurable, 14% material later, 14% a
trade, 12% a genuine retreat. 52 of the 60 were still the engine's top move --
good moves with a wrong explanation.

Everything below is computed from squares and the stored line.
"""
import chess

from services.caption_facts import _attack_outcome, _recommended_move_why

# The card Mohit questioned.
QB5_FEN = "1k2n2r/p1p5/1p5p/8/3q4/1Q3B2/PP3PP1/4R1K1 w - - 0 30"
# The card that said nothing: Re1 hits the bishop on e3.
RE1_FEN = "2kr3r/ppp1nppp/6b1/4P3/P1B3P1/2N1bN1P/1PP5/RK5R w - - 3 16"
# Minimal board for the trade / retreat split, built by playing it out rather
# than by eye: the king is on d8 so the e3 bishop is not pinned to it.
TRADE_FEN = "3k4/8/8/8/8/4b3/5P2/4R1K1 w - - 0 1"


class TestTheKnightCanJustMove:
    def test_the_stored_shallow_line_keeps_the_claim(self):
        # Depth-14-era line: Black plays Kc8 and loses the knight.
        board = chess.Board(QB5_FEN)
        why = _recommended_move_why(board, board.parse_san("Qb5"),
                                    line=["Kc8", "Rxe8+", "Qd8", "Qf5+"])
        assert why and "knight on e8" in why

    def test_the_real_line_drops_it(self):
        # Deeper: the knight runs and White wins by other means (Qc6).
        board = chess.Board(QB5_FEN)
        why = _recommended_move_why(board, board.parse_san("Qb5"),
                                    line=["Nf6", "Qc6", "Nd5", "Bxd5"])
        assert why is None, why

    def test_the_knight_really_can_run(self):
        board = chess.Board(QB5_FEN)
        board.push(board.parse_san("Qb5"))
        assert [m for m in board.legal_moves if m.from_square == chess.E8]


class TestRetreatIsMeasuredFromTheirSide:
    """A black piece retreats toward rank 8, not rank 1.

    The first version measured it from the mover's side, so on RE1_FEN the
    black bishop stepping e3 -> d2, further INTO White's position, was called
    "drives the bishop back to d2".
    """

    def test_a_black_piece_coming_forward_is_not_a_retreat(self):
        board = chess.Board(RE1_FEN)
        verdict, _square = _attack_outcome(
            board, board.parse_san("Re1"), chess.E3, ["Bd2", "Re2", "Bf4", "Ka2"])
        assert verdict != "retreats", "e3->d2 moves toward White, that is not a retreat"

    def test_a_black_piece_going_home_is_a_retreat(self):
        board = chess.Board(RE1_FEN)
        verdict, square = _attack_outcome(
            board, board.parse_san("Re1"), chess.E3, ["Bf4", "a5", "Nc6", "a6"])
        assert (verdict, square) == ("retreats", "f4")

    def test_the_card_that_said_nothing_now_teaches(self):
        board = chess.Board(RE1_FEN)
        why = _recommended_move_why(board, board.parse_san("Re1"),
                                    line=["Bf4", "a5", "Nc6", "a6"])
        assert why == "drives the bishop back to f4"


class TestTheOtherOutcomes:
    def test_no_line_keeps_todays_behaviour(self):
        board = chess.Board(QB5_FEN)
        assert _attack_outcome(board, board.parse_san("Qb5"), chess.E8, None)[0] == "unknown"
        assert _attack_outcome(board, board.parse_san("Qb5"), chess.E8, [])[0] == "unknown"

    def test_a_piece_that_stays_put_keeps_the_claim(self):
        board = chess.Board(QB5_FEN)
        assert _attack_outcome(board, board.parse_san("Qb5"), chess.E8,
                               ["Kc8", "Rxe8+"])[0] == "survives"

    def test_a_reply_that_captures_is_a_trade(self):
        # Black bishop on e3, White rook on e1 and pawn on f2 both eye it; the
        # king sits on d8 so the bishop is NOT pinned and can answer either way.
        board = chess.Board(TRADE_FEN)
        verdict, _ = _attack_outcome(board, board.parse_san("Kh2"), chess.E3,
                                     ["Bxf2", "Kg3"])
        assert verdict == "trades"

    def test_the_same_position_read_as_a_retreat(self):
        board = chess.Board(TRADE_FEN)
        assert _attack_outcome(board, board.parse_san("Kh2"), chess.E3,
                               ["Ba7", "Kg3"]) == ("retreats", "a7")

    def test_an_unparseable_line_does_not_crash(self):
        board = chess.Board(QB5_FEN)
        assert _attack_outcome(board, board.parse_san("Qb5"), chess.E8, ["Zz9"])[0] == "unknown"
