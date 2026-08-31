"""Exact transfer checks derived from every verified endgame lesson position.

These detectors do not copy or re-index the endgame catalogue. They adapt the
single exact matcher and independent verifier in
``canonical_curriculum_puzzle_proof``. Broader real-game generalization remains
the job of the geometry detectors (opposition, Lucena, active rook, and so on).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, Mapping, Optional

import chess

from services.concept_detectors.evidence import stored_best_move
from services.canonical_curriculum_puzzle_proof import (
    exact_endgame_lesson_ids,
    match_exact_endgame_transfer,
)


def detector_id_for_lesson(lesson_id: str) -> str:
    category_key, lesson_key = lesson_id.split("/", 1)
    return f"endgame_curriculum__{category_key}__{lesson_key}"


def curriculum_endgame_lesson_ids() -> tuple[str, ...]:
    return exact_endgame_lesson_ids()


def _make_detector(
    lesson_id: str,
) -> Callable:
    def detect_curriculum_endgame_application(
        board_before: chess.Board,
        move: chess.Move,
        user_color: chess.Color,
        best_move_san: Optional[str] = None,
        best_move_uci: Optional[str] = None,
    ) -> Optional[str]:
        if board_before.turn != user_color:
            return None
        stored_best = stored_best_move(
            board_before, best_move_san, best_move_uci
        )
        if stored_best is None:
            return None
        transfer = match_exact_endgame_transfer(
            board_before, stored_best.uci()
        )
        if transfer is None or transfer.content_id != lesson_id:
            return None
        expected = chess.Move.from_uci(transfer.expected_uci)
        return "applied" if move == expected else "missed"

    detect_curriculum_endgame_application.__name__ = (
        "detect_" + detector_id_for_lesson(lesson_id) + "_application"
    )
    detect_curriculum_endgame_application.__doc__ = (
        f"Exact canonical-position transfer detector for {lesson_id}."
    )
    return detect_curriculum_endgame_application


@lru_cache(maxsize=1)
def curriculum_endgame_detectors() -> Mapping[str, Callable]:
    return {
        detector_id_for_lesson(lesson_id): _make_detector(lesson_id)
        for lesson_id in exact_endgame_lesson_ids()
    }
