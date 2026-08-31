"""Shared stored-analysis evidence helpers for concept detectors."""

from __future__ import annotations

import math
from typing import Optional

import chess


def require_nonnegative_cp_loss(raw: object) -> float:
    """Return one finite stored loss or fail closed.

    ``cp_loss`` is already expressed as a non-negative loss by the analysis
    pipeline. Taking its absolute value would turn corrupt negative evidence,
    NaN or infinity into a publishable mistake.
    """
    try:
        loss = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("cp_loss must be numeric") from exc
    if not math.isfinite(loss) or loss < 0:
        raise ValueError("cp_loss must be finite and non-negative")
    return loss


def stored_best_matches(
    board: chess.Board,
    move: chess.Move,
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
) -> bool:
    """True only when a legal stored best move is exactly ``move``."""
    for raw in (best_move_uci, best_move_san):
        if not raw:
            continue
        try:
            candidate = chess.Move.from_uci(str(raw).lower())
            if candidate in board.legal_moves:
                return candidate == move
        except ValueError:
            pass
        try:
            return board.parse_san(str(raw)) == move
        except (ValueError, AssertionError):
            continue
    return False


def stored_best_move(
    board: chess.Board,
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
) -> Optional[chess.Move]:
    """Return a legal stored best move without evaluating the position."""
    for raw in (best_move_uci, best_move_san):
        if not raw:
            continue
        try:
            candidate = chess.Move.from_uci(str(raw).lower())
            if candidate in board.legal_moves:
                return candidate
        except ValueError:
            pass
        try:
            return board.parse_san(str(raw))
        except (ValueError, AssertionError):
            continue
    return None
