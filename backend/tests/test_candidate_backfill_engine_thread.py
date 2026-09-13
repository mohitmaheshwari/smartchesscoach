"""The candidate backfill must drive Stockfish off the event-loop thread.

`candidate_builder` is called synchronously from inside the awaited
generate_game_decryption_v5, so its body used to execute ON the event loop
thread. python-chess SimpleEngine drives its UCI transport from its own loop and
expects to be called from a thread with no loop running; from the loop thread it
hung forever rather than erroring.

Measured on production 2026-09-12: a user with ONE analysed game, capped at two
games, timed out after 540 seconds. The backend sat at 0.4% CPU with no
stockfish process alive -- stuck, not slow. That blocked bulk enrichment for all
69 users with analysed games.

The guardian path (_coach_evaluate_sync) already had the same class of bug and
was fixed the same way: keep blocking engine work off the loop.
"""
import asyncio
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SCRIPT = BACKEND / "scripts" / "backfill_candidate_caption_evidence.py"


def _src() -> str:
    return io.open(SCRIPT, encoding="utf-8").read()


def test_the_engine_call_is_dispatched_to_a_worker_thread():
    src = _src()
    assert "_engine_pool.submit(_candidate_builder_blocking, row).result()" in src, (
        "candidate_builder must hand the engine work to a thread, not run it "
        "on the event loop"
    )
    assert "ThreadPoolExecutor(max_workers=1" in src, (
        "one worker keeps every call on the same thread so the engine started "
        "on the first call stays usable"
    )


def test_the_pool_is_shut_down_and_the_engine_stopped_on_its_own_thread():
    src = _src()
    assert "_engine_pool.submit(engine.stop).result(timeout=30)" in src
    assert "_engine_pool.shutdown(wait=True)" in src, (
        "a leaked worker thread would keep the process alive after the run"
    )


@pytest.mark.asyncio
async def test_a_pool_worker_has_no_running_loop_but_the_caller_does():
    """The property that actually prevents the hang.

    Inside the async caller a loop IS running. Inside the pool worker it must
    not be -- that is exactly what SimpleEngine requires.
    """
    assert asyncio.get_running_loop() is not None

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        def probe():
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return "no running loop"
            return "loop is running"

        # Called the same way candidate_builder calls its blocking body.
        assert pool.submit(probe).result() == "no running loop"
    finally:
        pool.shutdown(wait=True)


@pytest.mark.asyncio
async def test_the_same_worker_thread_serves_every_call():
    """The engine is created lazily on first use, so it must be reused."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        import threading
        seen = {pool.submit(threading.get_ident).result() for _ in range(8)}
        assert len(seen) == 1, f"engine work spread across {len(seen)} threads"
    finally:
        pool.shutdown(wait=True)


def test_the_blocking_body_still_creates_and_reuses_one_engine():
    src = _src()
    assert "def _candidate_builder_blocking(row):" in src
    assert "if engine is None:" in src, (
        "the engine must still be created lazily and reused across rows"
    )
