"""
Opening play detector — did the user stay in curriculum book, where
curriculum coverage actually exists?

Rewritten 2026-08-03. The original imported `get_opening_for_game`,
`is_in_book`, `is_known_bad_deviation` from `opening_curriculum_engine.py`
— none of the three exist anywhere in that file (confirmed: the module
only exports `get_available_openings`, `get_opening_guidance`,
`get_opening_summary`), so the import always raised and the broad
`except Exception` swallowed it silently every time.

Real, honest scope of what's gradable with the data that actually
exists:
  - `get_opening_guidance(opening_key, moves_played, user_color,
    assessment)` walks `opening_curriculum.json`'s move tree following
    `moves_played` and returns `is_in_book=True` only if every move in
    the sequence matched the tree. Passing the FULL history (including
    this move) and checking `is_in_book` tells us whether THIS move
    specifically stayed in book — "applied".
  - There is NO "known bad deviation" concept anywhere in this data
    model. `_off_book_guidance()` (the function that runs the moment a
    move leaves the tree) treats every deviation identically and
    neutrally ("That's off the main line — but that's OK") — there is
    no field distinguishing a sound deviation from a losing one. The
    original docstring's "missed — known losing line" case was always
    aspirational, not backed by real data. Grading it would be a guess,
    not a fact, so this now returns None (no grade) on any deviation,
    same honest-silence choice as trap_detection.py's un-gradable cases.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import chess
import logging

logger = logging.getLogger(__name__)


def _raw_opening_name(opening_name: Optional[object]) -> str:
    if isinstance(opening_name, dict):
        return str(opening_name.get("opening_key") or opening_name.get("name") or "")
    return str(opening_name or "")


def resolve_opening_curriculum_key(
    opening_name: Optional[object],
    user_color: chess.Color,
) -> Optional[str]:
    """Resolve provider labels to one publishable lesson for this side."""
    from services.curriculum_content_validator import is_content_publishable
    from services.opening_library_service import (
        get_opening_data,
        match_opening_to_library,
    )
    from services.opening_normalizer import (
        curriculum_key_for_opening,
        normalize_opening,
    )
    from services.opening_theory_json_service import (
        get_opening_theory,
        resolve_opening_key,
    )

    raw = _raw_opening_name(opening_name).strip()
    if not raw:
        return None
    color_word = "white" if user_color == chess.WHITE else "black"

    candidates = []
    direct = resolve_opening_key(raw)
    if direct:
        candidates.append(direct)
    normalized_name = normalize_opening(raw.replace("_", " ").replace("-", " "))
    normalized_key = curriculum_key_for_opening(normalized_name, color_word)
    if normalized_key:
        candidates.append(normalized_key)
    public_key = match_opening_to_library(raw)
    public_record = get_opening_data(public_key) if public_key else None
    if public_record:
        candidates.append(str(public_record.get("canonical_key") or ""))

    for candidate in dict.fromkeys(candidates):
        theory = get_opening_theory(candidate) or {}
        if (
            candidate
            and is_content_publishable("openings", candidate)
            and str(theory.get("color") or "white").lower() == color_word
        ):
            return candidate
    return None


def _uci_history(move_history_san: List[str]) -> Optional[List[str]]:
    board = chess.Board()
    result = []
    try:
        for san in move_history_san:
            parsed = board.parse_san(str(san))
            result.append(parsed.uci())
            board.push(parsed)
    except (ValueError, AssertionError):
        return None
    return result


def _path_uci(steps: List[Dict]) -> Optional[List[str]]:
    board = chess.Board()
    result = []
    try:
        for step in steps:
            parsed = board.parse_san(str(step.get("move") or ""))
            result.append(parsed.uci())
            board.push(parsed)
    except (ValueError, AssertionError):
        return None
    return result


def _stored_best_uci(
    board: chess.Board,
    best_move_san: Optional[str],
    best_move_uci: Optional[str],
) -> Optional[str]:
    for raw in (best_move_uci, best_move_san):
        if not raw:
            continue
        try:
            parsed = chess.Move.from_uci(str(raw).lower())
            if parsed in board.legal_moves:
                return parsed.uci()
        except ValueError:
            pass
        try:
            return board.parse_san(str(raw)).uci()
        except (ValueError, AssertionError):
            continue
    return None


def detect_opening_play_detail(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[object] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Grade an exact authored decision, including a proven deviation miss."""
    context = _opening_decision_context(
        board_before,
        move,
        user_color,
        move_number=move_number,
        opening_name=opening_name,
        move_history_san=move_history_san,
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
    )
    if not context:
        return None
    expected = context["expected"]
    lesson_key = str(context["content_ref"])
    if move.uci() in expected:
        return {
            "outcome": "applied",
            "content_ref": lesson_key,
        }
    stored_best = context.get("stored_best")
    if stored_best and stored_best in expected:
        return {
            "outcome": "missed",
            "content_ref": lesson_key,
        }
    return None


def _opening_decision_context(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[object] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """Return one exact authored decision without judging the deviation."""
    if move_number is None or move_number > 15 or not move_history_san:
        return None
    if board_before.turn != user_color or move not in board_before.legal_moves:
        return None
    lesson_key = resolve_opening_curriculum_key(opening_name, user_color)
    if not lesson_key:
        return None

    history_uci = _uci_history(move_history_san)
    if not history_uci or history_uci[-1] != move.uci():
        return None
    current_index = len(history_uci) - 1
    user_parity = 0 if user_color == chess.WHITE else 1
    if sum(1 for index in range(len(history_uci)) if index % 2 == user_parity) < 2:
        return None

    from services.opening_theory_json_service import get_all_lesson_move_paths

    expected = set()
    for steps in get_all_lesson_move_paths(lesson_key):
        line = _path_uci(steps)
        if not line or current_index >= len(line):
            continue
        if line[:current_index] != history_uci[:current_index]:
            continue
        if current_index < len(steps):
            step_side = str(steps[current_index].get("side") or "").lower()
            if step_side and step_side != ("white" if user_color else "black"):
                continue
        expected.add(line[current_index])
    if not expected:
        return None
    stored_best = _stored_best_uci(board_before, best_move_san, best_move_uci)
    return {
        "content_ref": lesson_key,
        "expected": frozenset(expected),
        "stored_best": stored_best,
    }


def detect_sound_opening_deviation_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[object] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    """Recognize an off-curriculum move that is the stored engine best.

    This is positive evidence that the deviation was sound, not evidence that
    the player mastered the authored line. It also identifies a curriculum
    expansion opportunity without calling a good move a mistake.
    """
    context = _opening_decision_context(
        board_before,
        move,
        user_color,
        move_number=move_number,
        opening_name=opening_name,
        move_history_san=move_history_san,
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
    )
    if not context:
        return None
    if move.uci() in context["expected"]:
        return None
    return "applied" if context.get("stored_best") == move.uci() else None


def detect_opening_play_application(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
    opening_name: Optional[object] = None,
    move_history_san: Optional[List[str]] = None,
    best_move_san: Optional[str] = None,
    best_move_uci: Optional[str] = None,
) -> Optional[str]:
    """
    Detect if the user's move stayed in the curriculum's book line.

    `opening_name` is whatever `recognize_opening_from_history` returns
    — a dict with a `"name"` key (e.g. `{"name": "italian_game", ...}`),
    the same shape caption_pipeline.py already consumes elsewhere. This
    accepts a plain string too, for callers that already resolved it.

    `move_history_san` must be the FULL SAN history including this move
    — `board_before` is built fresh from a stored FEN by the caller
    (coach_memory.py) and has no move_stack to derive it from.

    Returns:
      "applied" — the move matched the curriculum's book line
      None — no curriculum coverage for this opening, or the move
             deviated (deviation is not gradable good/bad with the
             data that exists — see module docstring)
    """
    detail = detect_opening_play_detail(
        board_before,
        move,
        user_color,
        move_number=move_number,
        opening_name=opening_name,
        move_history_san=move_history_san,
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
    )
    return str(detail.get("outcome")) if detail else None


def detect_preparation_for_opening(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    move_number: Optional[int] = None,
) -> Optional[str]:
    """
    Simplified: detect if user played a preparatory move (like 1.d4 when they
    use Queen's Gambit, or 1.e4 for Italian openings).

    This is a lighter version that just checks if the opening move matches
    the user's repertoire.

    Returns:
      "applied" — Correct opening move
      None — Not evaluating this
    """
    if move_number != 1:  # Only grade white's first move
        return None

    if user_color != chess.WHITE:
        return None

    user_move_san = board_before.san(move)

    # Common opening moves that indicate preparation
    if user_move_san in ["e4", "d4", "c4", "Nf3"]:
        return "applied"  # Standard opening preparations

    return None
