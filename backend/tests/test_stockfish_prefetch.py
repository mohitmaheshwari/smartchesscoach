"""The prefetched table must answer exactly as StockfishEngine would, and fall
back to the real engine for anything it does not hold."""
import chess
import chess.engine

from stockfish_service import _PrefetchedEngine


class FakeEngine:
    def __init__(self):
        self.calls = []

    def evaluate_position(self, board, depth=18):
        self.calls.append(("eval", depth)); return 1, None

    def evaluate_position_with_line(self, board, depth=18, pv_length=12):
        self.calls.append(("line", depth)); return 2, None, []

    def get_best_move(self, board, depth=18):
        self.calls.append(("best", depth)); return chess.Move.from_uci("a2a3"), 3, None

    def classify_move(self, *a, **k):
        return "delegated"


START = chess.Board()


def table(score, pv=("e2e4", "e7e5")):
    return {(START.fen(), 18, 1): {"score": chess.engine.PovScore(score, chess.WHITE),
                                   "pv": [chess.Move.from_uci(m) for m in pv]}}


def test_centipawn_answers_match_the_engine_shapes():
    e = _PrefetchedEngine(FakeEngine(), table(chess.engine.Cp(35)))
    assert e.evaluate_position(START, 18) == (35, None)
    assert e.evaluate_position_with_line(START, 18) == (35, None, ["e4", "e5"])
    assert e.get_best_move(START, 18) == (chess.Move.from_uci("e2e4"), 35, None)


def test_each_method_keeps_its_own_mate_convention():
    e = _PrefetchedEngine(FakeEngine(), table(chess.engine.Mate(-3)))
    assert e.evaluate_position(START, 18) == (-(10000 - 30), -3)
    assert e.evaluate_position_with_line(START, 18)[:2] == (-(10000 - 30), -3)
    assert e.get_best_move(START, 18)[1:] == (-10000, -3)


def test_score_is_white_relative_when_black_is_to_move():
    b = chess.Board(); b.push_uci("e2e4")
    t = {(b.fen(), 18, 1): {"score": chess.engine.PovScore(chess.engine.Cp(50), chess.BLACK), "pv": [chess.Move.from_uci("e7e5")]}}
    e = _PrefetchedEngine(FakeEngine(), t)
    assert e.evaluate_position(b, 18) == (-50, None)


def test_misses_and_other_depths_go_to_the_real_engine():
    fake = FakeEngine()
    e = _PrefetchedEngine(fake, table(chess.engine.Cp(35)))
    other = chess.Board(); other.push_uci("d2d4")
    assert e.evaluate_position(other, 18) == (1, None)
    assert e.get_best_move(START, 12) == (chess.Move.from_uci("a2a3"), 3, None)
    assert fake.calls == [("eval", 18), ("best", 12)]
    assert e.classify_move() == "delegated"


def test_an_entry_without_a_line_asks_the_engine_for_the_best_move():
    fake = FakeEngine()
    e = _PrefetchedEngine(fake, table(chess.engine.Cp(10), pv=()))
    assert e.get_best_move(START, 18)[0] == chess.Move.from_uci("a2a3")


def test_line_threat_and_multipv_answers():
    t = table(chess.engine.Cp(20))
    t[(START.fen(), 18, 3)] = [
        {"score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE), "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]},
        {"score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE), "pv": [chess.Move.from_uci("d2d4")]},
    ]
    e = _PrefetchedEngine(FakeEngine(), t)
    assert e.get_principal_variation(START, 18, 1) == ["e4"]
    assert e.get_threat(START, 18) == "e4"
    assert e.get_top_replies(START, 3, 18) == [
        {"move_san": "e4", "move_uci": "e2e4", "eval_cp": 20},
        {"move_san": "d4", "move_uci": "d2d4", "eval_cp": 15}]
    cands = e.get_candidate_lines(START, num=3, depth=18, pv_length=2)
    assert [c["line_san"] for c in cands] == [["e4", "e5"], ["d4"]]
