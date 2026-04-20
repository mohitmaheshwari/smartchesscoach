"""
Engine Pool — shared warm Stockfish instance for the hot coaching path.

`fast_eval_service` already keeps one Stockfish process warm for
`/evaluate-pending`. This module exposes that same pool to other hot-path
callers so they don't each pay the ~200ms popen_uci spawn cost per move.

Usage:
    from services.engine_pool import warm_engine_scope

    with warm_engine_scope(skill_level=8) as engine:
        result = engine.play(board, chess.engine.Limit(depth=6))

The context manager handles:
  - Locking (the engine is shared across threads; only one analysis at a time)
  - Optional skill-level configuration (reset to max after the call)
  - Engine restart on EngineTerminatedError

Do NOT call `engine.quit()` inside the scope — the engine is meant to stay warm.
"""

import chess
import chess.engine
import logging
import threading
from contextlib import contextmanager
from typing import Optional, Iterator

logger = logging.getLogger(__name__)

_POOL_LOCK = threading.Lock()


def _ensure_engine():
    """Import lazily so this module stays importable without fast_eval_service."""
    from services import fast_eval_service
    return fast_eval_service._get_engine()


def _restart_engine():
    from services import fast_eval_service
    return fast_eval_service._restart_engine()


@contextmanager
def warm_engine_scope(
    skill_level: Optional[int] = None,
) -> Iterator[chess.engine.SimpleEngine]:
    """Acquire the warm engine under a lock. Configures skill level for this call.

    Args:
        skill_level: Stockfish skill level 0-20. If provided, engine is
            configured on entry and reset to 20 (max) on exit so the next
            caller doesn't inherit a weaker strength by accident.

    Yields:
        A live chess.engine.SimpleEngine.

    Raises:
        chess.engine.EngineTerminatedError: engine was restarted; caller should retry.
    """
    with _POOL_LOCK:
        engine = _ensure_engine()
        configured = False
        try:
            if skill_level is not None:
                try:
                    engine.configure({"Skill Level": int(skill_level)})
                    configured = True
                except Exception as e:
                    logger.debug(f"engine_pool: configure failed: {e}")
            yield engine
        except chess.engine.EngineTerminatedError:
            logger.warning("engine_pool: engine terminated during use — restarting")
            _restart_engine()
            raise
        finally:
            # Reset skill to max so the next borrower starts clean.
            if configured:
                try:
                    engine.configure({"Skill Level": 20})
                except Exception:
                    pass
