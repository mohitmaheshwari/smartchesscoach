"""
Puzzle Move Evaluator
=====================

Grade a user's move in a training puzzle against Stockfish, not against
string-match. Returns:

  - is_best: exact-match best move
  - is_acceptable: close enough (cp_loss <= 100) — advance, but note a sharper line
  - quality label: best / excellent / good / inaccuracy / mistake / blunder
  - coach-voice feedback that names both moves

Why this exists:
  Previous grader compared the played SAN to the stored solution_san. That's
  binary — play anything other than the exact best move and the puzzle says
  "wrong" even if the user's move was perfectly reasonable (say, a +1.5
  position vs the engine's +1.8). Users feel punished for solid chess.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import chess
import chess.engine

logger = logging.getLogger(__name__)

# Centipawn thresholds for quality buckets. Chosen to match Stockfish's
# standard classifications (see stockfish_service CP_THRESHOLDS) so that
# "mistake" in a puzzle means the same thing as "mistake" in a game.
BEST_EPSILON = 5      # <= this → effectively the top move
EXCELLENT_CP = 50     # <= this → very strong, minor eval diff
GOOD_CP = 100         # <= this → solid but not sharpest (still advance)
INACCURACY_CP = 200   # <= this → noticeable error, retry
MISTAKE_CP = 400      # <= this → real mistake


def _classify(cp_loss: int, is_best_match: bool) -> str:
    if is_best_match or cp_loss <= BEST_EPSILON:
        return "best"
    if cp_loss <= EXCELLENT_CP:
        return "excellent"
    if cp_loss <= GOOD_CP:
        return "good"
    if cp_loss <= INACCURACY_CP:
        return "inaccuracy"
    if cp_loss <= MISTAKE_CP:
        return "mistake"
    return "blunder"


def _build_feedback(quality: str, played_san: str, best_san: str) -> str:
    """Coach-voice feedback, one short line."""
    if quality == "best":
        return f"You found it — {played_san}."
    if quality == "excellent":
        return f"Strong move. {best_san} was the sharpest option."
    if quality == "good":
        return f"Solid. {best_san} was sharper — worth seeing why."
    if quality == "inaccuracy":
        return f"Not quite. {best_san} was better here."
    if quality == "mistake":
        return f"{played_san} loses ground. {best_san} was the move."
    if quality == "blunder":
        return f"{played_san} loses ground. {best_san} was stronger."
    return ""


async def evaluate_puzzle_move(
    fen: str,
    played_uci: str,
    depth: int = 12,
    known_best_san: Optional[str] = None,
) -> Dict:
    # python-chess and engine startup are synchronous. Keeping them inside
    # the event loop prevented the caller's wait_for budget from firing.
    return await asyncio.to_thread(
        _evaluate_puzzle_move_sync, fen, played_uci, depth, known_best_san
    )


def _evaluate_puzzle_move_sync(
    fen: str,
    played_uci: str,
    depth: int = 12,
    known_best_san: Optional[str] = None,
) -> Dict:
    """
    Evaluate the quality of a single user move against Stockfish.

    Args:
      fen: position before the user's move (from puzzle.fen)
      played_uci: user's move in UCI (source + target, optionally promotion)
      depth: Stockfish search depth. 12 is ~100-200ms and accurate enough
             for classification (best / acceptable / wrong).
      known_best_san: optional — if the puzzle already has a stored solution,
             we avoid a round-trip to Stockfish for the best move. Still
             verify by evaluating position.

    Returns dict with keys:
      quality, cp_loss, is_best, is_acceptable,
      best_move_san, user_move_san, feedback
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {
            "error": f"invalid fen: {e}",
            "quality": "invalid",
            "is_best": False,
            "is_acceptable": False,
        }

    # Parse the user's move — accept UCI or SAN for flexibility.
    played_move = None
    for parser in (
        lambda: chess.Move.from_uci(played_uci),
        lambda: board.parse_san(played_uci),
    ):
        try:
            candidate = parser()
            if candidate in board.legal_moves:
                played_move = candidate
                break
        except Exception:
            continue
    if played_move is None:
        return {
            "error": "illegal or unparseable move",
            "quality": "invalid",
            "is_best": False,
            "is_acceptable": False,
        }

    mover_is_white = board.turn == chess.WHITE
    sign = 1 if mover_is_white else -1

    try:
        from stockfish_service import StockfishEngine

        with StockfishEngine() as engine:
            # Step 1: baseline = engine eval of the current position (this
            # IS the best-play eval by definition — Stockfish assumes top
            # play for the side to move).
            # One search yields both the baseline and best move. Do not run
            # the identical root search again just to get the move.
            info = engine.engine.analyse(board, chess.engine.Limit(depth=depth))
            pv = info.get("pv") or []
            if not pv or pv[0] not in board.legal_moves or "score" not in info:
                raise ValueError("Missing scored legal principal variation")
            if info.get("depth", 0) < depth or info.get("lowerbound") or info.get("upperbound"):
                raise ValueError("Incomplete or bounded engine result")
            baseline_eval = info["score"].white().score(mate_score=10000)
            best_move = pv[0]
            best_san = board.san(best_move)
            played_san = board.san(played_move)

            # Only a different candidate needs a second search.
            if played_move == best_move:
                user_after_eval = baseline_eval
            else:
                # Compare from the same root and point of view. Restricting
                # the root move also avoids granting the played line an
                # extra ply relative to the unrestricted search.
                played_info = engine.engine.analyse(
                    board, chess.engine.Limit(depth=depth), root_moves=[played_move]
                )
                played_pv = played_info.get("pv") or []
                if (not played_pv or played_pv[0] != played_move
                        or "score" not in played_info
                        or played_info.get("depth", 0) < depth
                        or played_info.get("lowerbound") or played_info.get("upperbound")):
                    raise ValueError("Incomplete played-move evidence")
                user_after_eval = played_info["score"].white().score(mate_score=10000)
    except Exception as e:
        logger.warning(f"puzzle move eval failed: {e}")
        return {
            "error": f"engine_error: {e}",
            "quality": "invalid",
            "is_best": False,
            "is_acceptable": False,
        }

    # cp_loss from the mover's POV. Stockfish evals are always white-POV,
    # so for black movers we flip the sign.
    delta = (baseline_eval - user_after_eval) * sign
    cp_loss = max(0, int(delta))

    # Stored notation is context, not permission to override fresh evidence.
    is_best_match = played_move == best_move
    quality = _classify(cp_loss, is_best_match)
    is_best = quality == "best"
    is_acceptable = cp_loss <= GOOD_CP  # best / excellent / good all advance

    return {
        "quality": quality,
        "cp_loss": cp_loss,
        "is_best": is_best,
        "is_acceptable": is_acceptable,
        "best_move_san": best_san,
        "best_move_uci": best_move.uci(),
        "user_move_san": played_san,
        "feedback": _build_feedback(quality, played_san, best_san),
    }
