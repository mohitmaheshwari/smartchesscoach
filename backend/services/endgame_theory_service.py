"""Canonical, truth-gated endgame lesson service.

The only authored source is data/coaching/endgame_theory_tree.json. Public
catalogs and lesson routes return only lessons that pass the offline curriculum
validator. Correct moves remain server-side until the player attempts.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Dict, Optional

import chess

from services.curriculum_content_validator import is_content_publishable


TREE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "coaching"
    / "endgame_theory_tree.json"
)
CANONICAL_SOURCE = "backend/data/coaching/endgame_theory_tree.json"

_CONTENT_REF_INDEX = {
    "opposition": ("king_and_pawn", "opposition"),
    "rule_of_square": ("king_and_pawn", "square_rule"),
    "lucena_position": ("rook_endgames", "lucena"),
    "philidor_position": ("rook_endgames", "philidor"),
}

_endgame_tree: Optional[Dict[str, Any]] = None


def _load_tree() -> Dict[str, Any]:
    global _endgame_tree
    if _endgame_tree is None:
        with TREE_PATH.open("r", encoding="utf-8") as handle:
            _endgame_tree = json.load(handle)
    return _endgame_tree


def reset_endgame_cache() -> None:
    global _endgame_tree
    _endgame_tree = None


def _lesson_id(category_key: str, lesson_key: str) -> str:
    return f"{category_key}/{lesson_key}"


def _raw_lesson(category_key: str, lesson_key: str) -> Optional[Dict[str, Any]]:
    category = _load_tree().get(category_key)
    if not isinstance(category, dict):
        return None
    lesson = (category.get("lessons") or {}).get(lesson_key)
    return lesson if isinstance(lesson, dict) else None


def get_verified_lesson_data(
    category_key: str,
    lesson_key: str,
) -> Optional[Dict[str, Any]]:
    """Return a defensive copy with answers for server-side teaching only."""
    if not is_content_publishable(
        "endgames",
        _lesson_id(category_key, lesson_key),
    ):
        return None
    lesson = _raw_lesson(category_key, lesson_key)
    return deepcopy(lesson) if lesson else None


def _stage_for(index: int, total: int) -> str:
    return "independent_proof" if index == total - 1 else "guided_try"


def get_all_categories() -> list[Dict[str, Any]]:
    categories = []
    for category_key, category in _load_tree().items():
        if category_key.startswith("_") or not isinstance(category, dict):
            continue
        lessons = []
        for lesson_key, lesson in (category.get("lessons") or {}).items():
            content_id = _lesson_id(category_key, lesson_key)
            if not is_content_publishable("endgames", content_id):
                continue
            lessons.append(
                {
                    "key": lesson_key,
                    "name": lesson["name"],
                    "rule": lesson["rule"],
                    "description": lesson["description"],
                    "position_count": len(lesson.get("positions", [])),
                    "lesson_id": content_id,
                    "canonical_source": CANONICAL_SOURCE,
                }
            )
        if lessons:
            categories.append(
                {
                    "key": category_key,
                    "name": category["name"],
                    "icon": category.get("icon", ""),
                    "description": category.get("description", ""),
                    "lessons": lessons,
                }
            )
    return categories


def get_lesson(category_key: str, lesson_key: str) -> Optional[Dict[str, Any]]:
    lesson = get_verified_lesson_data(category_key, lesson_key)
    category = _load_tree().get(category_key)
    if not lesson or not isinstance(category, dict):
        return None

    raw_positions = lesson.get("positions", [])
    positions = []
    for index, position in enumerate(raw_positions):
        entry = {
            "index": index,
            "fen": position["fen"],
            "side_to_move": position["side_to_move"],
            "prompt": position["prompt"],
            "stage": _stage_for(index, len(raw_positions)),
            "answer_hidden": True,
        }
        for optional in ("square_corners", "concept"):
            if position.get(optional):
                entry[optional] = position[optional]
        positions.append(entry)

    return {
        "category_key": category_key,
        "category_name": category["name"],
        "lesson_key": lesson_key,
        "lesson_id": _lesson_id(category_key, lesson_key),
        "name": lesson["name"],
        "rule": lesson["rule"],
        "description": lesson["description"],
        "intro": lesson.get("intro"),
        "positions": positions,
        "total_positions": len(positions),
        "canonical_source": CANONICAL_SOURCE,
    }


def resolve_content_ref(content_ref: str) -> Optional[Dict[str, str]]:
    identity = _CONTENT_REF_INDEX.get(str(content_ref or ""))
    if not identity:
        return None
    category_key, lesson_key = identity
    if get_lesson(category_key, lesson_key) is None:
        return None
    lesson_id = _lesson_id(category_key, lesson_key)
    return {
        "content_ref": str(content_ref),
        "category_key": category_key,
        "lesson_key": lesson_key,
        "lesson_id": lesson_id,
        "href": f"/endgames/{lesson_id}",
        "canonical_source": CANONICAL_SOURCE,
    }


def get_lesson_by_content_ref(content_ref: str):
    resolved = resolve_content_ref(content_ref)
    if not resolved:
        return None
    return get_lesson(resolved["category_key"], resolved["lesson_key"])


def check_move(
    category_key: str,
    lesson_key: str,
    position_index: int,
    user_move_uci: str,
) -> Dict[str, Any]:
    lesson = get_verified_lesson_data(category_key, lesson_key)
    if not lesson:
        return {"error": "Verified lesson not found"}
    positions = lesson.get("positions", [])
    if position_index < 0 or position_index >= len(positions):
        return {"error": "Position not found"}

    position = positions[position_index]
    board = chess.Board(position["fen"])
    supplied = str(user_move_uci or "").strip()
    user_move = None
    try:
        user_move = chess.Move.from_uci(supplied.lower())
    except ValueError:
        try:
            user_move = board.parse_san(supplied)
        except (ValueError, AssertionError):
            pass

    correct_uci = position["correct_move_uci"].lower()
    correct = bool(user_move and user_move.uci() == correct_uci)
    stage = _stage_for(position_index, len(positions))
    is_last = position_index == len(positions) - 1

    if correct:
        return {
            "correct": True,
            "move_san": position["correct_move_san"],
            "move_uci": correct_uci,
            "idea": position["idea"],
            "on_correct": position["on_correct"],
            "rule_reminder": position.get("rule_reminder", lesson["rule"]),
            "is_last": is_last,
            "stage": stage,
            "demonstrated": is_last,
        }

    response = {
        "correct": False,
        "on_wrong": position["on_wrong"],
        "rule_reminder": position.get("rule_reminder", lesson["rule"]),
        "is_last": is_last,
        "stage": stage,
        "demonstrated": False,
    }
    if stage == "guided_try":
        response.update(
            {
                "correct_move_san": position["correct_move_san"],
                "correct_move_uci": correct_uci,
                "idea": position["idea"],
            }
        )
    return response
