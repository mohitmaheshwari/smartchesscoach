"""Failure and concurrency contracts, without engine/model/network calls."""
from concurrent.futures import ThreadPoolExecutor
import time
from contextlib import contextmanager

import chess
import chess.engine
import pytest

from services import fast_eval_service as fast


class Engine:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure
        self.active = 0
        self.overlap = False

    @contextmanager
    def analysis(self, board, limit, **kwargs):
        yield iter([self.analyse(board, limit, **kwargs)])

    def analyse(self, board, limit, **kwargs):
        self.active += 1
        self.overlap |= self.active > 1
        try:
            time.sleep(0.005)
            self.calls.append((board.fen(), kwargs))
            if self.failure == "exception":
                raise RuntimeError("search unavailable")
            forced = kwargs.get("root_moves")
            move = forced[0] if forced else next(iter(board.legal_moves))
            score = 50 if not forced else -400
            result = {
                "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                "pv": [move], "depth": 13 if not forced else 11, "nodes": 2345,
            }
            if self.failure == "missing_score":
                result.pop("score")
            if self.failure == "zero_depth":
                result["depth"] = 0
            if self.failure == "bound":
                result["lowerbound"] = True
            return result
        finally:
            self.active -= 1


@pytest.mark.parametrize("failure", ["exception", "missing_score", "zero_depth", "bound"])
def test_failed_search_never_becomes_a_valid_zero(monkeypatch, failure):
    monkeypatch.setattr(fast, "_get_engine", lambda: Engine(failure))
    result = fast.fast_eval(chess.STARTING_FEN, "e2e4", 0.0)
    assert result["depth"] == 0
    assert result["move_quality"] == "unknown"


@pytest.mark.parametrize("black", [False, True])
def test_compares_same_root_for_both_colors_and_ignores_unbound_cache(monkeypatch, black):
    board = chess.Board()
    if black:
        board.push_uci("e2e4")
    move = "e7e5" if black else "e2e4"
    engine = Engine()
    monkeypatch.setattr(fast, "_get_engine", lambda: engine)
    result = fast.fast_eval(board.fen(), move, 999.0)
    assert result["cp_loss"] == 450
    assert result["depth"] == 11
    assert result["nodes"] == 4690
    assert len(engine.calls) == 2
    assert all(fen == board.fen() for fen, _ in engine.calls)
    assert engine.calls[1][1]["root_moves"] == [chess.Move.from_uci(move)]


def test_shared_engine_searches_cannot_overlap(monkeypatch):
    engine = Engine()
    monkeypatch.setattr(fast, "_get_engine", lambda: engine)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: fast.fast_eval(chess.STARTING_FEN, "e2e4"), range(4)))
    assert not engine.overlap
    assert all(r["cp_loss"] == 450 for r in results)


def test_exact_iteration_survives_later_bound_update():
    board = chess.Board()
    exact = Engine().analyse(board, None)
    class Streaming:
        @contextmanager
        def analysis(self, *_args, **_kwargs):
            yield iter([exact, {**exact, "depth": 14, "upperbound": True}])
    assert fast._search(Streaming(), board, None) == exact


def test_forced_search_cannot_return_another_move(monkeypatch):
    class WrongMove(Engine):
        def analyse(self, board, limit, **kwargs):
            return super().analyse(board, limit)
    monkeypatch.setattr(fast, "_get_engine", lambda: WrongMove())
    result = fast.fast_eval(chess.STARTING_FEN, "e2e4")
    assert result["move_quality"] == "unknown"


def test_deployment_runs_canary_before_replacing_backend():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[2] / "scripts" / "deploy.sh").read_text()
    canary = script.index("backend python3 -m pytest tests/test_unified_pwc_real_engine_canary.py")
    assert script.index("docker compose build backend") < canary
    assert canary < script.index("docker compose up -d backend")
    assert '|| die "PWC losing-game canary failed' in script


def test_recommended_move_cannot_become_a_blunder_from_search_noise(monkeypatch):
    engine = Engine()
    monkeypatch.setattr(fast, "_get_engine", lambda: engine)
    move = next(iter(chess.Board().legal_moves))
    result = fast.fast_eval(chess.STARTING_FEN, move.uci())
    assert result["cp_loss"] == 0
    assert len(engine.calls) == 1


def test_queue_timeout_is_unknown_and_never_starts_engine(monkeypatch):
    class Busy:
        def acquire(self, **kwargs):
            return False
    monkeypatch.setattr(fast, "_engine_lock", Busy())
    monkeypatch.setattr(fast, "_get_engine", lambda: pytest.fail("Must not search"))
    result = fast.fast_eval(chess.STARTING_FEN, "e2e4")
    assert result["failure_reason"] == "engine_busy"
    assert result["move_quality"] == "unknown"
