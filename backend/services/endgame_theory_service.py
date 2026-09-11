"""Canonical, truth-gated endgame lesson service.

The only authored source is data/coaching/endgame_theory_tree.json. Public
catalogs and lesson routes return only lessons that pass the offline curriculum
validator. Correct moves remain server-side until the player attempts.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

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
    "queen_checkmate": ("basic_mates", "queen_mate"),
    "rook_checkmate": ("basic_mates", "rook_mate"),
    "opposition": ("king_and_pawn", "opposition"),
    "rule_of_square": ("king_and_pawn", "square_rule"),
    "lucena_position": ("rook_endgames", "lucena"),
    "philidor_position": ("rook_endgames", "philidor"),
    "key_squares": ("king_and_pawn", "key_squares"),
    "pawn_breakthrough": ("king_and_pawn", "breakthrough"),
    "king_centralization": ("king_and_pawn", "king_centralization"),
    "active_rook": ("rook_endgames", "active_rook"),
    "stop_promotion": ("queen_vs_pawn", "stop_promotion"),
    "creating_passed_pawn": ("practical_endgames", "creating_passed_pawn"),
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
    raw_ref = str(content_ref or "")
    identity = _CONTENT_REF_INDEX.get(raw_ref)
    if identity is None and "/" in raw_ref:
        category_key, lesson_key = raw_ref.split("/", 1)
        if get_lesson(category_key, lesson_key) is not None:
            identity = (category_key, lesson_key)
    if not identity:
        return None
    category_key, lesson_key = identity
    if get_lesson(category_key, lesson_key) is None:
        return None
    lesson_id = _lesson_id(category_key, lesson_key)
    return {
        "content_ref": raw_ref,
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


def _parse_legal_move(board: chess.Board, supplied: str) -> Optional[chess.Move]:
    text = str(supplied or "").strip()
    try:
        move = chess.Move.from_uci(text.lower())
        return move if move in board.legal_moves else None
    except ValueError:
        try:
            return board.parse_san(text)
        except (ValueError, AssertionError):
            return None


def _authored_moves(position: Mapping[str, Any]) -> list[Dict[str, Any]]:
    primary = {
        "move_san": position["correct_move_san"],
        "move_uci": position["correct_move_uci"],
        "idea": position["idea"],
        "on_correct": position["on_correct"],
        "reason_contract": position.get("reason_contract"),
    }
    return [primary, *deepcopy(position.get("accepted_alternatives") or [])]


def _matched_authored_move(
    position: Mapping[str, Any],
    move_uci: str,
) -> Optional[Dict[str, Any]]:
    target = str(move_uci or "").lower()
    return next(
        (
            authored
            for authored in _authored_moves(position)
            if str(authored.get("move_uci") or "").lower() == target
        ),
        None,
    )


def build_endgame_reason_bundle(
    category_key: str,
    lesson_key: str,
    position_index: int,
    user_move: str,
):
    """Convert one canonical move-specific reason into the shared contract.

    The lesson JSON remains the only chess-knowledge owner. This function only
    validates the submitted legal move, selects its authored contract, and
    projects that contract into the surface-neutral reason schema.
    """
    lesson = get_verified_lesson_data(category_key, lesson_key)
    positions = (lesson or {}).get("positions") or []
    if position_index < 0 or position_index >= len(positions):
        return None
    position = positions[position_index]
    board = chess.Board(position["fen"])
    parsed = _parse_legal_move(board, user_move)
    if parsed is None:
        return None
    authored = _matched_authored_move(position, parsed.uci())
    contract = (authored or {}).get("reason_contract")
    if not isinstance(contract, dict):
        return None

    from services.teaching_reason_contracts import (
        ReasonChoice,
        ReasonComponent,
        ReasonProof,
        TeachingReasonBundle,
    )

    fingerprint_source = json.dumps(
        {
            "content_id": _lesson_id(category_key, lesson_key),
            "position_index": position_index,
            "fen": board.fen(),
            "move_uci": parsed.uci(),
            "reason_contract": contract,
        },
        sort_keys=True,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(fingerprint_source).hexdigest()
    return TeachingReasonBundle(
        semantic_version="endgame.authored_reason.v1",
        position_fingerprint=hashlib.sha256(board.fen().encode("utf-8")).hexdigest(),
        move_uci=parsed.uci(),
        move_san=board.san(parsed),
        target_result="pass",
        safety_kind="tablebase_result_preserving_lesson_move",
        components=(
            ReasonComponent(
                question_id=f"endgame:{position_index}:{parsed.uci()}:idea",
                kind="endgame_idea",
                prompt=str(contract.get("prompt") or ""),
                choices=tuple(
                    ReasonChoice.from_dict(choice)
                    for choice in (contract.get("choices") or [])
                ),
                accepted_choice_ids=tuple(
                    contract.get("accepted_choice_ids") or ()
                ),
                facts={
                    "content_id": _lesson_id(category_key, lesson_key),
                    "position_index": position_index,
                    "move_uci": parsed.uci(),
                },
                success_text=str(contract.get("success_text") or ""),
                correction_text=str(contract.get("correction_text") or ""),
            ),
        ),
        proof=ReasonProof(
            authority="canonical_endgame_curriculum",
            quality_id=(
                f"concept:endgame_curriculum__{category_key}__{lesson_key}"
            ),
            detector_version="endgame_theory_tree.v1",
            verifier_version="curriculum_content_validator.v2",
            fingerprint=fingerprint,
        ),
    )


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
    user_move = _parse_legal_move(board, supplied)

    correct_uci = position["correct_move_uci"].lower()
    matched = (
        _matched_authored_move(position, user_move.uci())
        if user_move is not None
        else None
    )
    correct = matched is not None
    stage = _stage_for(position_index, len(positions))
    is_last = position_index == len(positions) - 1

    if correct:
        return {
            "correct": True,
            "move_san": str(matched["move_san"]),
            "move_uci": str(matched["move_uci"]).lower(),
            "idea": str(matched["idea"]),
            "on_correct": str(matched["on_correct"]),
            "reason_contract": deepcopy(matched.get("reason_contract")),
            "rule_reminder": position.get("rule_reminder", lesson["rule"]),
            "is_last": is_last,
            "stage": stage,
            "demonstrated": is_last,
        }

    submitted_san = board.san(user_move) if user_move is not None else ""
    wrong_example = str(position.get("wrong_example_san") or "").strip()
    response = {
        "correct": False,
        "on_wrong": (
            position["on_wrong"]
            if submitted_san == wrong_example
            else (
                "That legal move does not practise this position's idea yet. "
                + str(position.get("rule_reminder") or lesson["rule"])
            )
        ),
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
