"""Exact positive application detector for canonical opening-plan lessons.

Opening-plan content remains owned by ``backend/data/traps.json`` and exposed
through ``trick_library_service.OPENING_IDEAS_DATABASE``.  This detector builds
only a derived exact-position index.  It fires when:

* the board is exactly one authored opening-plan position;
* the user's legal move is the plan move authored for that side;
* that same move is the already-stored Stockfish best move; and
* the position/move pair identifies one lesson, not two ambiguous lessons.

It is positive-only and Shadow: it can measure likely application offline, but
cannot call an off-line move a mistake or write mastery until blind review.
No engine, LLM, database, or network call occurs here.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional, Tuple

import chess

from services.concept_detectors.evidence import stored_best_matches


def _position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


@lru_cache(maxsize=1)
def _exact_plan_index() -> Dict[Tuple[str, str, chess.Color], Tuple[str, ...]]:
    from trick_library_service import OPENING_IDEAS_DATABASE

    grouped: Dict[Tuple[str, str, chess.Color], set[str]] = {}
    for lesson in OPENING_IDEAS_DATABASE.values():
        learner = (
            chess.WHITE
            if str(lesson.get("trap_for") or "").lower() == "white"
            else chess.BLACK
        )
        content_id = str(lesson.get("content_id") or "")
        if not content_id:
            continue
        board = chess.Board()
        for raw_san in lesson.get("full_sequence") or ():
            try:
                move = board.parse_san(str(raw_san))
            except ValueError:
                break
            if board.turn == learner:
                key = (_position_key(board), move.uci(), learner)
                grouped.setdefault(key, set()).add(content_id)
            board.push(move)
    return {key: tuple(sorted(values)) for key, values in grouped.items()}


def detect_opening_plan_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    """Return applied only for an unambiguous exact authored plan move."""
    if (
        board_before.turn != user_color
        or move not in board_before.legal_moves
        or (move_number is not None and move_number > 25)
        or not stored_best_matches(
            board_before, move, best_move_san, best_move_uci
        )
    ):
        return None
    lessons = _exact_plan_index().get(
        (_position_key(board_before), move.uci(), user_color),
        (),
    )
    return "applied" if len(lessons) == 1 else None


def exact_opening_plan_content_ids() -> Tuple[str, ...]:
    """Canonical opening-plan identities covered by the exact index."""
    return tuple(sorted({
        content_id
        for content_ids in _exact_plan_index().values()
        for content_id in content_ids
    }))
