"""Compatibility adapters for the canonical rule-of-square truth."""
from __future__ import annotations

from typing import Optional

import chess

from services.concept_detectors.rule_of_the_square import (
    detect_rule_of_the_square_application,
    is_rule_of_square_relevant,
)


def detect_rule_of_square(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    result = detect_rule_of_the_square_application(board, move, user_color)
    return {"applied": "applies", "missed": "violates"}.get(result)


__all__ = ["detect_rule_of_square", "is_rule_of_square_relevant"]
