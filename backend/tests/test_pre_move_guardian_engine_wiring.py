"""The pre-move guardian must actually reach Stockfish.

On 2026-09-10 a HAR from a real game showed /coach/play/evaluate returning
`should_intervene: false` with `processing_time_ms: 0.64` for every move --
including the one that hung a queen. Two depth-12 analyses cannot run in 0.6ms.

The cause: 455b1a60 (2026-06-24) moved the engine call out of
`evaluate_coach_play_move` into the module-level helper `_coach_evaluate_sync`
so it could run in a thread executor, but left
`from stockfish_service import StockfishEngine` behind in the caller's local
scope. The helper therefore raised NameError on every call. The caller catches
Exception and only logs a warning, so the guardian silently fell back to
heuristics with no engine data and never intervened -- for 78 days, for every
user, in every game.

Production logged `Stockfish evaluation failed: name 'StockfishEngine' is not
defined` 44 times in 24 hours before the fix.

These tests fail if the import is ever removed again, and if any other
module-level helper in this file grows the same scope hole.
"""
import ast
import io
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

ROUTE = BACKEND / "routes" / "coach_play.py"


class _FakeEngine:
    """Minimal stand-in with the surface _coach_evaluate_sync actually uses."""

    started = False
    stopped = False

    def start(self):
        self.started = True

    def analyse_full(self, board, depth=12, pv_length=6):
        best = next(iter(board.legal_moves))
        return 35, best, ["e4", "e5"][:pv_length]

    def stop(self):
        self.stopped = True


def test_coach_evaluate_sync_reaches_the_engine(monkeypatch):
    """The regression itself: this raised NameError for 78 days."""
    import stockfish_service

    monkeypatch.setattr(stockfish_service, "StockfishEngine", _FakeEngine)
    from routes.coach_play import _coach_evaluate_sync

    eval_before, eval_after, best_san, best_line, punish = _coach_evaluate_sync(
        chess.STARTING_FEN, "e4"
    )
    assert eval_before is not None, (
        "engine never ran -- _coach_evaluate_sync lost StockfishEngine from scope"
    )
    assert eval_after is not None
    assert best_san, "no best move returned; the guardian has nothing to offer"


def test_the_helper_imports_what_it_uses():
    """Static guard: a thread-executor helper cannot borrow a caller's import."""
    tree = ast.parse(io.open(ROUTE, encoding="utf-8").read())
    offenders = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        uses = {
            n.id for n in ast.walk(node)
            if isinstance(n, ast.Name) and n.id == "StockfishEngine"
        }
        if not uses:
            continue
        imported = any(
            isinstance(n, (ast.Import, ast.ImportFrom))
            and any(a.name == "StockfishEngine" or a.asname == "StockfishEngine"
                    for a in n.names)
            for n in ast.walk(node)
        )
        if not imported:
            offenders.append(node.name)
    assert not offenders, (
        "these functions use StockfishEngine without importing it in their own "
        f"scope: {offenders}. A function that runs in a thread executor does not "
        "inherit the caller's function-local imports."
    )


def test_guardian_failure_is_not_silent():
    """A blind guardian must be loud, not a warning nobody reads.

    The original bug survived 78 days because the only signal was
    logger.warning inside a broad `except Exception`.
    """
    source = io.open(ROUTE, encoding="utf-8").read()
    marker = "Stockfish evaluation failed"
    assert marker in source, "the failure log line was removed"
    idx = source.index(marker)
    window = source[max(0, idx - 700):idx + 300]
    assert "guardian_engine_available" in window or "logger.error" in window, (
        "an engine failure here blinds the pre-move guardian for that move; it "
        "must be logged at error level or surfaced in the response so it cannot "
        "rot silently again"
    )
