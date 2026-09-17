"""Search counts, evidence checks, and event-loop responsiveness (no engine)."""
import asyncio
import threading
from types import SimpleNamespace

import chess
import chess.engine
import pytest

from services.puzzle_move_evaluator import evaluate_puzzle_move


def install_engine(monkeypatch, *, loss=40, incomplete=False, entered=None, release=None):
    calls = []

    class Engine:
        def __enter__(self):
            self.engine = self
            return self

        def __exit__(self, *args):
            pass

        def analyse(self, board, limit, root_moves=None):
            calls.append((board.fen(), root_moves))
            if entered:
                entered.set()
                assert release.wait(2)
            move = root_moves[0] if root_moves else chess.Move.from_uci("e2e4")
            return {
                "pv": [move],
                "score": chess.engine.PovScore(chess.engine.Cp(-loss if root_moves else 0), chess.WHITE),
                "depth": 0 if incomplete else limit.depth,
            }

    monkeypatch.setitem(__import__("sys").modules, "stockfish_service", SimpleNamespace(StockfishEngine=Engine))
    return calls


@pytest.mark.parametrize("move,count", [("e2e4", 1), ("d2d4", 2)])
def test_one_root_search_and_only_needed_candidate_search(monkeypatch, move, count):
    calls = install_engine(monkeypatch)
    result = asyncio.run(evaluate_puzzle_move(chess.STARTING_FEN, move))
    assert result["is_acceptable"] is True
    assert result["best_move_uci"] == "e2e4"
    assert len(calls) == count
    assert all(fen == chess.STARTING_FEN for fen, _ in calls)


def test_stored_best_label_cannot_override_measured_loss(monkeypatch):
    install_engine(monkeypatch, loss=450)
    result = asyncio.run(evaluate_puzzle_move(chess.STARTING_FEN, "d2d4", known_best_san="d4"))
    assert result["quality"] == "blunder"
    assert result["is_acceptable"] is False


def test_incomplete_engine_evidence_is_not_a_verdict(monkeypatch):
    install_engine(monkeypatch, incomplete=True)
    result = asyncio.run(evaluate_puzzle_move(chess.STARTING_FEN, "e2e4"))
    assert result["quality"] == "invalid"


def test_synchronous_engine_does_not_block_timeout(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    install_engine(monkeypatch, entered=entered, release=release)

    async def run():
        task = asyncio.create_task(evaluate_puzzle_move(chess.STARTING_FEN, "e2e4"))
        try:
            await asyncio.wait_for(asyncio.to_thread(entered.wait, 1), timeout=1.5)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), timeout=0.01)
        finally:
            release.set()
        assert (await task)["is_acceptable"] is True

    asyncio.run(run())
