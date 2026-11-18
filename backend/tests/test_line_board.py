"""Play any line on the review board: the words (services/line_board.py).

Board facts are checked on real positions; the one engine-shaped test uses a
fake engine that answers from a fixed table, so the suite needs no Stockfish.
"""
import chess
import chess.engine
import pytest

from services.line_board import (
    LineError,
    describe,
    game_positions,
    material_sentence,
    position_in_game,
    replay,
    step,
    verdict,
)

QF3 = "rn1qkbnr/p1pppp1p/b7/1B4p1/8/4P3/PPPP1PPP/RNBQK1NR w KQkq - 1 4"


def _after(fen, sans):
    b = chess.Board(fen)
    moves = []
    for s in sans:
        m = b.parse_san(s)
        b.push(m)
        moves.append(m)
    return b, moves


def test_bc6_names_the_queen_and_the_line_the_queen_opened():
    # 4.Qf3 Bxb5 5.Qxa8 Bc6: the student's real question, answered.
    board, moves = _after(QF3, ["Qf3", "Bxb5", "Qxa8"])
    prev_board = board.copy()
    prev_board.pop()
    text = " ".join(describe(board, board.parse_san("Bc6"), chess.WHITE,
                             previous=moves[-1], previous_board=prev_board))
    assert text == ("Bc6 attacks your queen. Now that your queen has left f3, it also hits "
                    "your pawn on g2, with your rook on h1 behind it.")


def test_capture_of_the_attacker_says_so():
    board = chess.Board(QF3)
    text = " ".join(describe(board, board.parse_san("Bxa6"), chess.WHITE))
    assert text == "Bxa6 takes their bishop on a6. That bishop was attacking it."


def test_check_reads_after_the_capture():
    fen = "r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6"
    board, _ = _after(fen, ["d5"])
    text = " ".join(describe(board, board.parse_san("Bxd5+"), chess.BLACK))
    assert text == "Bxd5+ takes your pawn on d5 with check. That pawn was attacking it."


def test_fork_names_check_and_the_rook():
    fen = "3Q2k1/2n2pp1/7p/P7/8/6PP/2r2PK1/4r3 b - - 1 31"
    board, _ = _after(fen, ["Kh7"])
    text = " ".join(describe(board, board.parse_san("Qd3+"), chess.BLACK))
    assert text == "Qd3+ gives check. It also attacks your rook on c2."


def test_a_guarded_equal_target_is_not_named():
    # 1.e4 e5 2.Nf3: the knight hits a pawn guarded by nothing? e5 is unguarded,
    # so it IS named; 2...Nc6 then guards it and 3.Bb5 hitting the guarded
    # knight with a bishop (equal value) is not named.
    board, _ = _after(chess.STARTING_FEN, ["e4", "e5", "Nf3", "Nc6"])
    assert describe(board, board.parse_san("Bb5"), chess.WHITE) == []


def test_without_notation_no_square_is_named():
    board, moves = _after(QF3, ["Qf3", "Bxb5", "Qxa8"])
    prev_board = board.copy()
    prev_board.pop()
    text = " ".join(describe(board, board.parse_san("Bc6"), chess.WHITE,
                             previous=moves[-1], previous_board=prev_board, notation=False))
    assert " on " not in text and "f3" not in text
    assert "has left its square" in text


def test_count_waits_for_a_quiet_point():
    start = chess.Board(QF3)
    _, moves = _after(QF3, ["Qf3", "Bxb5", "Qxa8", "Bc6", "Qxa7", "Bxg2"])
    b, _ = _after(QF3, ["Qf3", "Bxb5", "Qxa8", "Bc6", "Qxa7", "Bxg2"])
    nc3 = b.parse_san("Nc3")
    b.push(nc3)
    bxh1 = b.parse_san("Bxh1")
    assert material_sentence(start, moves, chess.WHITE, [nc3, bxh1]) is None


def test_count_is_read_from_the_board_overall():
    # White starts this line a pawn up (1...b5 was taken earlier in the game).
    start = chess.Board(QF3)
    _, moves = _after(QF3, ["Qf3", "Bxb5"])
    text = material_sentence(start, moves, chess.WHITE, [])
    assert text == "In this line they won a bishop. Overall you are two pawns down."


def test_small_even_trade_has_no_count():
    start = chess.Board(QF3)
    _, moves = _after(QF3, ["Bxa6", "Nxa6"])
    assert material_sentence(start, moves, chess.WHITE, []) is None


def test_verdict_uses_the_shared_rating_table():
    assert verdict(10, 1200) == "good"
    assert verdict(50, 1200) == "inaccuracy"
    assert verdict(100, 1200) == "mistake"
    assert verdict(250, 1200) == "blunder"
    # The same drop is only an inaccuracy under 1000.
    assert verdict(140, 800) == "inaccuracy"


def test_line_must_start_from_a_game_position():
    pgn = "1. e4 e5 2. Nf3 Nc6 *"
    pos = game_positions(pgn)
    b, _ = _after(chess.STARTING_FEN, ["e4", "e5"])
    assert position_in_game(b.fen(), pos)
    assert not position_in_game(QF3, pos)


def test_bad_line_is_refused():
    with pytest.raises(LineError):
        replay(QF3, ["Qf3", "Qxa8"])


class _FakeEngine:
    """Answers analyse() from a table keyed by the position's first four fields."""

    def __init__(self, table):
        self.table = table

    def analyse(self, board, limit):
        cp, pv = self.table[" ".join(board.fen().split()[:4])]
        return {"score": chess.engine.PovScore(chess.engine.Cp(cp), board.turn),
                "pv": [board.parse_san(s) if i == 0 else None for i, s in enumerate(pv)][:1]}


def test_step_calls_qf3_a_mistake_and_names_the_reply():
    b0 = chess.Board(QF3)
    b1, _ = _after(QF3, ["Qf3"])
    key = lambda b: " ".join(b.fen().split()[:4])  # noqa: E731
    eng = _FakeEngine({key(b0): (245, ["Bxa6"]), key(b1): (276, ["Bxb5"])})
    out = step(eng, QF3, [], "Qf3", user_color=chess.WHITE, rating=1200, depth=1).to_dict()
    assert out["student"]["class"] == "blunder"
    assert out["student"]["text"] == "Qf3 is a mistake: Bxa6 was better. It attacks their rook on a8."
    assert out["needs_why"] is True
    assert out["reply"]["san"] == "Bxb5"
    assert out["reply"]["text"] == "Bxb5 takes your bishop on b5."
