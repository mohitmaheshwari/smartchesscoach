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
    uci_elo: Optional[int] = None,
) -> Iterator[chess.engine.SimpleEngine]:
    """Acquire the warm engine under a lock. Configures strength for this call.

    Args:
        skill_level: Stockfish Skill Level (0-20). Legacy throttle — adds
            randomness to move selection. Use this for users below 1320
            (UCI_Elo's lower bound).
        uci_elo: Stockfish UCI_Elo target (1320-3190). When set, enables
            UCI_LimitStrength=true + UCI_Elo=<value>. Calibrated against
            CCRL data — coach plays human-like at the chosen rating.
            Takes precedence over skill_level when both are provided.

    Yields:
        A live chess.engine.SimpleEngine.

    Raises:
        chess.engine.EngineTerminatedError: engine was restarted; caller should retry.
    """
    with _POOL_LOCK:
        engine = _ensure_engine()
        configured = False
        configured_strength_path = None  # "uci_elo" | "skill" — what we set, for cleanup
        try:
            if uci_elo is not None:
                try:
                    engine.configure({
                        "UCI_LimitStrength": True,
                        "UCI_Elo": int(uci_elo),
                    })
                    configured = True
                    configured_strength_path = "uci_elo"
                except Exception as e:
                    logger.debug(f"engine_pool: UCI_Elo configure failed, falling back to Skill Level: {e}")
                    # Fall through to skill_level path if also provided.
            if not configured and skill_level is not None:
                try:
                    engine.configure({"Skill Level": int(skill_level)})
                    configured = True
                    configured_strength_path = "skill"
                except Exception as e:
                    logger.debug(f"engine_pool: Skill Level configure failed: {e}")
            yield engine
        except chess.engine.EngineTerminatedError:
            logger.warning("engine_pool: engine terminated during use — restarting")
            _restart_engine()
            raise
        finally:
            # Reset to full strength so the next borrower starts clean.
            if configured:
                try:
                    if configured_strength_path == "uci_elo":
                        # Disable UCI_LimitStrength AND reset Skill Level to max.
                        engine.configure({"UCI_LimitStrength": False})
                        engine.configure({"Skill Level": 20})
                    else:
                        engine.configure({"Skill Level": 20})
                except Exception:
                    pass
