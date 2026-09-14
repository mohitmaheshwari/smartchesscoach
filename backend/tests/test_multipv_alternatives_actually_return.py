"""Asking the engine for alternatives has to return alternatives.

`get_best_moves_for_position` called `engine.configure({"MultiPV": n})` and
then passed `multipv=n` to `analyse()`. python-chess manages that option
itself and raises

    cannot set MultiPV which is automatically managed

on the configure call -- so the function raised on EVERY invocation, caught
its own exception, and returned {"success": False} with no moves. From
2026-02-04 until this fix.

Nothing alerted, because the caller checks `if top_raw.get("success")` and
quietly moves on. The visible cost was in Play with Coach: `pv_top_moves`
feeds `punishment_puzzle.evaluate_for_puzzle`, the feature that turns the
opponent's blunder into a "can you punish this?" moment mid-game. With an
empty list it can never confirm a concrete win, so that puzzle never fired
in a coached game for seven months. `/api/analysis` alternatives were dead
the same way.

Found by playing games against the live server and reading the log: the
error repeated once per move, every move.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SERVICE = BACKEND / "stockfish_service.py"

# A quiet Italian position: several reasonable moves, no forced tactic, so a
# healthy MultiPV must return more than one distinct line.
ITALIAN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"


def test_multipv_is_never_configured_directly():
    """The regression lock. This one line cost seven months of silence."""
    src = io.open(SERVICE, encoding="utf-8").read()
    assert 'configure({"MultiPV"' not in src, (
        "python-chess manages MultiPV; setting it directly makes analyse() "
        "raise on every call"
    )
    assert "multipv=num_moves" in src, (
        "MultiPV must still be requested -- via the analyse() argument"
    )


def _engine_available():
    try:
        from stockfish_service import StockfishEngine
        with StockfishEngine():
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _engine_available(), reason="no Stockfish binary here")
def test_it_returns_several_distinct_moves_with_evaluations():
    from stockfish_service import get_best_moves_for_position

    result = get_best_moves_for_position(ITALIAN, num_moves=3, depth=10)

    assert result.get("success") is True, result.get("error")
    moves = result.get("top_moves") or []
    assert len(moves) >= 2, f"MultiPV returned {len(moves)} line(s): {moves}"

    sans = [m.get("move_san") for m in moves]
    assert len(set(sans)) == len(sans), f"duplicate lines: {sans}"
    for m in moves:
        assert m.get("move_san") and m.get("move_uci")
        # Every line needs a usable number, or the caller cannot rank them.
        assert (m.get("evaluation") is not None) or (m.get("mate_in") is not None), m


@pytest.mark.skipif(not _engine_available(), reason="no Stockfish binary here")
def test_the_punish_puzzle_can_build_its_input_again():
    """The shape coach_play actually consumes: [(san, cp), ...].

    It skips any entry with neither an evaluation nor a mate, so a result
    that "succeeds" with unusable numbers would still leave the list empty.
    """
    from stockfish_service import get_best_moves_for_position

    result = get_best_moves_for_position(ITALIAN, num_moves=3, depth=10)
    pv_top_moves = []
    for entry in result.get("top_moves", []):
        mate, ev = entry.get("mate_in"), entry.get("evaluation")
        if mate is not None:
            cp = 30000 if mate > 0 else -30000
        elif ev is not None:
            cp = ev
        else:
            continue
        if entry.get("move_san"):
            pv_top_moves.append((entry["move_san"], int(cp)))

    assert pv_top_moves, "this list was empty on every coached move since Feb"
    assert len(pv_top_moves) >= 2
