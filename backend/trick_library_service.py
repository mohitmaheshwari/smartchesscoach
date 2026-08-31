"""Play-with-Coach trap adapter over the canonical trap curriculum.

Trap content is authored only in backend/data/traps.json. This module keeps
the legacy service/API shape used by training and Play with Coach, but its
database is a derived compatibility index rather than a second inventory.
Only records that pass the offline curriculum truth gate are returned.
"""

from __future__ import annotations

from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional

import chess
import httpx

from services.curriculum_content_validator import (
    get_publishable_content_ids,
    trap_content_id,
)
from services.trap_library import (
    get_all_opening_plans as get_canonical_opening_plans,
    get_all_traps as get_canonical_traps,
)


logger = logging.getLogger(__name__)

START_FEN = chess.STARTING_FEN
LICHESS_API_BASE = "https://lichess.org/api"


class PracticeMode(str, Enum):
    EXECUTION = "execution"
    AVOIDANCE = "avoidance"
    RECOGNITION = "recognition"


def _practice_key(name: str) -> str:
    clean = str(name or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "_", clean).strip("_")


def _opening_name(opening_key: str) -> str:
    return str(opening_key or "").replace("-", " ").replace("_", " ").title()


def _line_moves(trap: Dict[str, Any]) -> List[str]:
    return [
        str(step.get("move") or "")
        for step in trap.get("trap_line", [])
        if isinstance(step, dict) and step.get("move")
    ]


def _line_explanations(trap: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {
            "move": str(step.get("move") or ""),
            "explanation": str(step.get("explanation") or ""),
        }
        for step in trap.get("trap_line", [])
        if isinstance(step, dict) and step.get("move")
    ]


def _fen_after(moves: List[str]) -> Optional[str]:
    board = chess.Board()
    try:
        for san in moves:
            board.push_san(san)
    except (ValueError, AssertionError):
        return None
    return board.fen()


def _split_roles(full_sequence: List[str], user_color: str) -> tuple[List[Dict], List[Dict]]:
    user_moves: List[Dict] = []
    engine_moves: List[Dict] = []
    user_is_white = user_color == "white"
    for index, move in enumerate(full_sequence):
        actor_is_white = index % 2 == 0
        item = {"index": index, "move": move}
        if actor_is_white == user_is_white:
            user_moves.append(item)
        else:
            engine_moves.append(item)
    return user_moves, engine_moves


def _adapt_trap(opening_key: str, trap: Dict[str, Any]) -> Dict[str, Any]:
    name = str(trap.get("name") or "")
    key = str(trap.get("practice_key") or _practice_key(name))
    setup_moves = [str(move) for move in trap.get("setup_moves", [])]
    winning_line = _line_moves(trap)
    full_sequence = setup_moves + winning_line
    trap_for = str(trap.get("trap_color") or "")
    victim_color = "black" if trap_for == "white" else "white"

    trap_side_moves = [
        move
        for index, move in enumerate(winning_line, start=len(setup_moves))
        if (index % 2 == 0) == (trap_for == "white")
    ]
    winning_move = trap_side_moves[-1] if trap_side_moves else ""

    defense_steps = trap.get("defense_line") or []
    defense_line = [
        str(step.get("move") if isinstance(step, dict) else step)
        for step in defense_steps
        if (step.get("move") if isinstance(step, dict) else step)
    ]
    defense_setup = [
        str(move)
        for move in trap.get("defense_setup_moves", setup_moves)
    ]

    return {
        "key": key,
        "content_id": trap_content_id(opening_key, name),
        "name": name,
        "opening_key": opening_key,
        "opening": _opening_name(opening_key),
        "difficulty": trap.get("difficulty", "intermediate"),
        "description": trap.get("description", ""),
        "explanation": trap.get("description", ""),
        "why_it_works": trap.get("success_message", ""),
        "success_message": trap.get("success_message", ""),
        "result_type": trap.get("result_type", ""),
        "lesson_kind": trap.get("lesson_kind", "forced_trap"),
        "learning_goal": trap.get("learning_goal", ""),
        "trap_for": trap_for,
        "victim_color": victim_color,
        "setup_moves": setup_moves,
        "trap_line": _line_explanations(trap),
        "winning_line": winning_line,
        "winning_move": winning_move,
        "full_sequence": full_sequence,
        "trap_position_fen": _fen_after(setup_moves),
        "practice_fen": {
            "execution": START_FEN,
            "recognition": _fen_after(setup_moves),
            "avoidance": _fen_after(defense_setup) if defense_line else None,
        },
        "danger": trap.get("danger", ""),
        "how_to_avoid": trap.get("how_to_avoid", ""),
        "defense_setup_moves": defense_setup,
        "defense_line": defense_line,
        "safe_moves": list(trap.get("safe_moves") or []),
        "key_squares": list(trap.get("key_squares") or []),
        "tactical_theme": trap.get("tactical_theme", ""),
        "canonical_source": "backend/data/traps.json",
    }


def _build_database() -> Dict[str, Dict[str, Any]]:
    publishable = get_publishable_content_ids("traps")
    database: Dict[str, Dict[str, Any]] = {}
    for opening_key, traps in get_canonical_traps().items():
        if str(opening_key).startswith("_") or not isinstance(traps, list):
            continue
        for raw in traps:
            if not isinstance(raw, dict):
                continue
            content_id = trap_content_id(opening_key, raw.get("name", ""))
            if content_id not in publishable:
                continue
            adapted = _adapt_trap(opening_key, raw)
            key = adapted["key"]
            if key in database:
                key = f"{key}_{_practice_key(opening_key)}"
                adapted["key"] = key
            database[key] = adapted
    return database


TRAPS_DATABASE: Dict[str, Dict[str, Any]] = _build_database()


def _build_opening_ideas_database() -> Dict[str, Dict[str, Any]]:
    """Verified plans/gambits derived from the same canonical JSON source."""
    publishable = get_publishable_content_ids("opening_ideas")
    database: Dict[str, Dict[str, Any]] = {}
    for opening_key, lessons in get_canonical_opening_plans().items():
        if str(opening_key).startswith("_") or not isinstance(lessons, list):
            continue
        for raw in lessons:
            if not isinstance(raw, dict):
                continue
            content_id = trap_content_id(opening_key, raw.get("name", ""))
            if content_id not in publishable:
                continue
            adapted = _adapt_trap(opening_key, raw)
            key = adapted["key"]
            if key in database:
                key = f"{key}_{_practice_key(opening_key)}"
                adapted["key"] = key
            database[key] = adapted
    return database


OPENING_IDEAS_DATABASE: Dict[str, Dict[str, Any]] = (
    _build_opening_ideas_database()
)


def _build_categories() -> Dict[str, Dict[str, Any]]:
    beginner = [
        key for key, trap in TRAPS_DATABASE.items()
        if trap.get("difficulty") == "beginner"
    ]
    mate = [
        key for key, trap in TRAPS_DATABASE.items()
        if trap.get("result_type") in {"mate", "checkmate"}
    ]
    material = [
        key for key, trap in TRAPS_DATABASE.items()
        if trap.get("result_type") in {"wins_material", "wins_piece"}
    ]
    queens = [
        key for key, trap in TRAPS_DATABASE.items()
        if trap.get("result_type") == "wins_queen"
    ]
    return {
        "beginner": {
            "name": "Beginner trap dangers",
            "description": "Common early threats to recognise and defend.",
            "traps": beginner,
        },
        "mate": {
            "name": "King-safety traps",
            "description": "Threats that can end the game if they are ignored.",
            "traps": mate,
        },
        "material": {
            "name": "Piece-winning traps",
            "description": "Sequences where one loose or overloaded piece is lost.",
            "traps": material,
        },
        "queen_traps": {
            "name": "Queen traps",
            "description": "Positions where the queen runs out of safe squares.",
            "traps": queens,
        },
    }


TRAP_CATEGORIES = _build_categories()


def reload_canonical_traps() -> None:
    global TRAPS_DATABASE, OPENING_IDEAS_DATABASE, TRAP_CATEGORIES
    from services.curriculum_content_validator import reset_validation_cache
    from services.trap_library import reload_traps

    reload_traps()
    reset_validation_cache()
    TRAPS_DATABASE = _build_database()
    OPENING_IDEAS_DATABASE = _build_opening_ideas_database()
    TRAP_CATEGORIES = _build_categories()


def get_all_traps() -> List[Dict[str, Any]]:
    return [dict(trap) for trap in TRAPS_DATABASE.values()]


_PUBLIC_TRAP_FIELDS = (
    "key",
    "content_id",
    "name",
    "opening_key",
    "opening",
    "difficulty",
    "description",
    "result_type",
    "lesson_kind",
    "learning_goal",
    "trap_for",
    "victim_color",
    "trap_position_fen",
    "danger",
    "how_to_avoid",
    "key_squares",
    "tactical_theme",
    "canonical_source",
)


def public_trap_metadata(trap: Dict[str, Any]) -> Dict[str, Any]:
    """Browseable trap identity with every move/answer field removed."""
    return {
        field: trap[field]
        for field in _PUBLIC_TRAP_FIELDS
        if field in trap
    } | {
        "practice_href": (
            "/training?personalized=1&kind=trap&lesson="
            + str(trap.get("key") or "")
        ),
        "answer_hidden": True,
    }


def get_public_traps() -> List[Dict[str, Any]]:
    return [public_trap_metadata(trap) for trap in TRAPS_DATABASE.values()]


def get_all_opening_ideas() -> List[Dict[str, Any]]:
    return [dict(lesson) for lesson in OPENING_IDEAS_DATABASE.values()]


def get_trap_by_key(trap_key: str) -> Optional[Dict[str, Any]]:
    trap = TRAPS_DATABASE.get(str(trap_key or ""))
    return dict(trap) if trap else None


def get_public_trap_by_key(trap_key: str) -> Optional[Dict[str, Any]]:
    trap = TRAPS_DATABASE.get(str(trap_key or ""))
    return public_trap_metadata(trap) if trap else None


def get_traps_by_opening(opening_name: str) -> List[Dict[str, Any]]:
    needle = str(opening_name or "").lower().replace("-", " ").replace("_", " ")
    return [
        dict(trap)
        for trap in TRAPS_DATABASE.values()
        if needle in trap.get("opening", "").lower()
        or needle in trap.get("opening_key", "").replace("-", " ").lower()
    ]


def get_traps_by_category(category: str) -> List[Dict[str, Any]]:
    category_data = TRAP_CATEGORIES.get(category)
    if not category_data:
        return []
    return [
        dict(TRAPS_DATABASE[key])
        for key in category_data.get("traps", [])
        if key in TRAPS_DATABASE
    ]


def get_traps_by_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    return [
        dict(trap)
        for trap in TRAPS_DATABASE.values()
        if trap.get("difficulty") == difficulty
    ]


def _execution_practice(trap: Dict[str, Any]) -> Dict[str, Any]:
    full_sequence = list(trap["full_sequence"])
    user_moves, engine_moves = _split_roles(full_sequence, trap["trap_for"])
    final_user_index = user_moves[-1]["index"] if user_moves else -1
    user_moves = [
        {**item, "is_winning": item["index"] == final_user_index}
        for item in user_moves
    ]
    return {
        **trap,
        "mode": "execution",
        "start_fen": START_FEN,
        "user_color": trap["trap_for"],
        "full_sequence": full_sequence,
        "user_moves": user_moves,
        "engine_moves": engine_moves,
        "total_moves": len(full_sequence),
        "hints": (
            (
                f"Play as {trap['trap_for'].title()}. Follow the model line "
                "and notice what each move prepares. This is a plan, not a "
                "forced sequence."
            )
            if trap.get("lesson_kind") == "opening_plan"
            else (
                f"Play as {trap['trap_for'].title()}. Follow the whole line "
                "and notice which defensive mistake makes the tactic possible."
            )
        ),
    }


def _avoidance_practice(trap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    defense_line = list(trap.get("defense_line") or [])
    if not defense_line:
        return None
    full_sequence = list(trap["defense_setup_moves"]) + defense_line
    user_color = trap["victim_color"]
    setup_count = len(trap["defense_setup_moves"])
    user_moves = [
        {"index": index, "move": move}
        for index, move in enumerate(full_sequence)
        if index >= setup_count
        and (index % 2 == 0) == (user_color == "white")
    ]
    user_indexes = {item["index"] for item in user_moves}
    engine_moves = [
        {"index": index, "move": move}
        for index, move in enumerate(full_sequence)
        if index not in user_indexes
    ]
    return {
        **trap,
        "mode": "avoidance",
        "start_fen": START_FEN,
        "fen": trap["practice_fen"]["avoidance"],
        "user_color": user_color,
        "full_sequence": full_sequence,
        "user_moves": user_moves,
        "engine_moves": engine_moves,
        "total_moves": len(full_sequence),
        "dangerous_moves": list(trap.get("winning_line") or [])[:1],
        "hints": (
            f"Play as {user_color.title()}. Answer the threat before starting "
            "your own plan."
        ),
    }


def _recognition_practice(trap: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **trap,
        "mode": "recognition",
        "fen": trap["trap_position_fen"],
        "user_color": trap["victim_color"],
        "has_trap": True,
        "hints": "What is threatened here, and which piece or square needs help?",
    }


def get_trap_for_practice(trap_key: str, mode: str) -> Optional[Dict[str, Any]]:
    trap = TRAPS_DATABASE.get(str(trap_key or ""))
    if not trap:
        return None
    if mode == PracticeMode.EXECUTION.value:
        return _execution_practice(trap)
    if mode == PracticeMode.AVOIDANCE.value:
        return _avoidance_practice(trap)
    if mode == PracticeMode.RECOGNITION.value:
        return _recognition_practice(trap)
    return None


def get_opening_idea_for_practice(
    lesson_key: str,
    mode: str = PracticeMode.EXECUTION.value,
) -> Optional[Dict[str, Any]]:
    lesson = OPENING_IDEAS_DATABASE.get(str(lesson_key or ""))
    if not lesson or mode != PracticeMode.EXECUTION.value:
        return None
    return _execution_practice(lesson)


OPENING_TO_LICHESS_THEME = {
    "italian": "Italian_Game",
    "sicilian": "Sicilian_Defense",
    "french": "French_Defense",
    "caro-kann": "Caro-Kann_Defense",
    "scandinavian": "Scandinavian_Defense",
    "ruy lopez": "Ruy_Lopez",
    "queens gambit": "Queens_Gambit",
    "kings indian": "Kings_Indian_Defense",
    "english": "English_Opening",
    "london": "London_System",
}


async def fetch_lichess_puzzles_by_opening(
    opening: str,
    count: int = 10,
) -> List[Dict]:
    opening_lower = opening.lower().replace("'", "").replace("-", " ")
    lichess_theme = next(
        (
            theme
            for key, theme in OPENING_TO_LICHESS_THEME.items()
            if key in opening_lower
        ),
        None,
    )
    if not lichess_theme:
        return []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LICHESS_API_BASE}/puzzle/daily",
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
        if response.status_code != 200:
            return []
        puzzle = response.json().get("puzzle", {})
        themes = puzzle.get("themes", [])
        if themes and lichess_theme not in themes:
            return []
        return [{
            "id": puzzle.get("id"),
            "solution": puzzle.get("solution", []),
            "rating": puzzle.get("rating"),
            "themes": themes,
            "source": "lichess",
        }]
    except Exception as exc:
        logger.error("Error fetching Lichess puzzle: %s", exc)
        return []


async def fetch_tactical_puzzles(
    theme: str,
    rating_range: tuple = (1000, 1600),
    count: int = 5,
) -> List[Dict]:
    return []


def get_recommended_traps_for_opening(opening_name: str) -> List[Dict[str, Any]]:
    return [
        {
            "key": trap["key"],
            "name": trap["name"],
            "opening": trap["opening"],
            "relevance": "direct",
            "difficulty": trap["difficulty"],
            "description": trap["description"],
        }
        for trap in get_traps_by_opening(opening_name)[:5]
    ]


def get_trap_statistics() -> Dict[str, Any]:
    by_difficulty: Dict[str, int] = {}
    by_opening: Dict[str, int] = {}
    for trap in TRAPS_DATABASE.values():
        difficulty = trap.get("difficulty", "unknown")
        opening = trap.get("opening", "Unknown")
        by_difficulty[difficulty] = by_difficulty.get(difficulty, 0) + 1
        by_opening[opening] = by_opening.get(opening, 0) + 1
    return {
        "total_traps": len(TRAPS_DATABASE),
        "by_difficulty": by_difficulty,
        "by_opening": by_opening,
        "categories": list(TRAP_CATEGORIES),
        "canonical_source": "backend/data/traps.json",
    }
