"""Server-owned evidence helpers for personalized opening practice.

This module deliberately contains no opening theory. The unified curriculum
remains the only source for authored moves; this code only verifies whether a
legal alternative is engine-sound from the mover's perspective.
"""

import asyncio
import logging
from typing import Dict, Optional

import chess

from stockfish_service import StockfishEngine


logger = logging.getLogger(__name__)


async def evaluate_practice_alternative(
    board: chess.Board,
    move: chess.Move,
) -> Optional[Dict]:
    """Return mover-POV engine loss for a legal non-authored move.

    Engine failure returns None so the practice route fails closed to the
    verified authored line.
    """

    def _run() -> Dict:
        mover_is_white = board.turn == chess.WHITE
        with StockfishEngine() as engine:
            before_cp, best_move, _ = engine.analyse_full(board)
            after = board.copy()
            after.push(move)
            after_cp, _, reply_line = engine.analyse_full(after, pv_length=2)
        cp_loss = max(
            0,
            int(before_cp - after_cp)
            if mover_is_white
            else int(after_cp - before_cp),
        )
        return {
            "cp_loss": cp_loss,
            "best_move_san": board.san(best_move) if best_move else None,
            "reply_line": reply_line,
        }

    try:
        return await asyncio.to_thread(_run)
    except Exception:
        logger.exception("[OPENING_PRACTICE] Alternative verification failed")
        return None
