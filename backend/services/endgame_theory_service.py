"""
Endgame Theory Service
======================

Serves structured endgame lessons from endgame_theory_tree.json.
Each lesson = one idea, multiple positions, Position → Try → Teach format.
"""

import json
import os
import logging
import chess

logger = logging.getLogger(__name__)

_endgame_tree = None


def _load_tree():
    global _endgame_tree
    if _endgame_tree is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "coaching", "endgame_theory_tree.json")
        with open(path, "r") as f:
            _endgame_tree = json.load(f)
    return _endgame_tree


def get_all_categories():
    """Return all endgame categories with their lessons (names only, no positions)."""
    tree = _load_tree()
    categories = []
    for cat_key, cat_data in tree.items():
        if cat_key.startswith("_"):
            continue
        lessons = []
        for lesson_key, lesson_data in cat_data.get("lessons", {}).items():
            lessons.append({
                "key": lesson_key,
                "name": lesson_data["name"],
                "rule": lesson_data["rule"],
                "description": lesson_data["description"],
                "position_count": len(lesson_data.get("positions", []))
            })
        categories.append({
            "key": cat_key,
            "name": cat_data["name"],
            "icon": cat_data.get("icon", ""),
            "description": cat_data.get("description", ""),
            "lessons": lessons
        })
    return categories


def get_lesson(category_key: str, lesson_key: str):
    """Return a specific lesson with all positions (but without correct moves — those are checked server-side)."""
    tree = _load_tree()
    cat = tree.get(category_key)
    if not cat:
        return None
    lesson = cat.get("lessons", {}).get(lesson_key)
    if not lesson:
        return None

    positions = []
    for i, pos in enumerate(lesson.get("positions", [])):
        positions.append({
            "index": i,
            "fen": pos["fen"],
            "side_to_move": pos["side_to_move"],
            "prompt": pos["prompt"],
        })

    return {
        "category_key": category_key,
        "category_name": cat["name"],
        "lesson_key": lesson_key,
        "name": lesson["name"],
        "rule": lesson["rule"],
        "description": lesson["description"],
        "positions": positions,
        "total_positions": len(positions)
    }


def check_move(category_key: str, lesson_key: str, position_index: int, user_move_uci: str):
    """Check if the user's move matches the correct move for the position."""
    tree = _load_tree()
    cat = tree.get(category_key)
    if not cat:
        return {"error": "Category not found"}
    lesson = cat.get("lessons", {}).get(lesson_key)
    if not lesson:
        return {"error": "Lesson not found"}
    positions = lesson.get("positions", [])
    if position_index < 0 or position_index >= len(positions):
        return {"error": "Position not found"}

    pos = positions[position_index]
    correct_uci = pos["correct_move_uci"]
    correct_san = pos["correct_move_san"]

    # Normalize UCI (strip whitespace)
    user_uci = user_move_uci.strip().lower()
    correct_uci_norm = correct_uci.strip().lower()

    # Also try to parse user's SAN move in case frontend sends SAN
    is_correct = user_uci == correct_uci_norm

    # Additional check: try to parse the user's UCI move and see if it matches
    if not is_correct:
        try:
            chess.Board(pos["fen"])
            user_chess_move = chess.Move.from_uci(user_uci)
            correct_chess_move = chess.Move.from_uci(correct_uci_norm)
            is_correct = user_chess_move == correct_chess_move
        except Exception:
            pass

    if is_correct:
        return {
            "correct": True,
            "move_san": correct_san,
            "move_uci": correct_uci,
            "idea": pos["idea"],
            "on_correct": pos["on_correct"],
            "rule_reminder": pos.get("rule_reminder", lesson["rule"]),
            "is_last": position_index >= len(positions) - 1
        }
    else:
        return {
            "correct": False,
            "correct_move_san": correct_san,
            "correct_move_uci": correct_uci,
            "on_wrong": pos["on_wrong"],
            "idea": pos["idea"],
            "rule_reminder": pos.get("rule_reminder", lesson["rule"]),
            "is_last": position_index >= len(positions) - 1
        }
