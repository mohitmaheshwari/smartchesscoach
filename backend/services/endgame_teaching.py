"""Compatibility adapter for proactive endgame coaching.

Endgame content is authored only in the canonical theory tree and filtered by
the shared truth gate. This module preserves the older detection and dataclass
interfaces used by postgame analysis while forwarding interactive teaching to
the canonical teaching engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Dict, List, Optional

import chess

from services.endgame_theory_service import (
    get_all_categories,
    get_lesson,
    get_verified_lesson_data,
)


logger = logging.getLogger(__name__)


class EndgameType(str, Enum):
    KING_PAWN = "king_pawn"
    KING_QUEEN = "king_queen"
    KING_ROOK = "king_rook"
    KING_TWO_ROOKS = "king_two_rooks"
    ROOK_ENDGAME = "rook_endgame"
    QUEEN_ENDGAME = "queen_endgame"
    BISHOP_ENDGAME = "bishop_endgame"
    KNIGHT_ENDGAME = "knight_endgame"
    OPPOSITE_BISHOPS = "opposite_bishops"
    BASIC_CHECKMATE = "basic_checkmate"


@dataclass
class EndgameLesson:
    name: str
    endgame_type: EndgameType
    description: str
    key_concepts: List[str]
    setup_fen: str
    solution_moves: List[str]
    explanations: Dict[int, str]
    common_mistakes: List[str]
    practice_positions: List[str] = field(default_factory=list)
    category_key: str = ""
    lesson_key: str = ""
    canonical_source: str = (
        "backend/data/coaching/endgame_theory_tree.json"
    )


_LEGACY_KEY_ROUTES = {
    "opposition": ("king_and_pawn", "opposition", EndgameType.KING_PAWN),
    "key_squares": ("king_and_pawn", "key_squares", EndgameType.KING_PAWN),
    "rule_of_square": ("king_and_pawn", "square_rule", EndgameType.KING_PAWN),
    "lucena_position": ("rook_endgames", "lucena", EndgameType.ROOK_ENDGAME),
    "zugzwang": ("practical_endgames", "zugzwang", EndgameType.KING_PAWN),
}


def _adapt_lesson(
    category_key: str,
    lesson_key: str,
    endgame_type: EndgameType,
) -> Optional[EndgameLesson]:
    lesson = get_verified_lesson_data(category_key, lesson_key)
    if not lesson:
        return None
    positions = lesson.get("positions", [])
    first = positions[0]
    return EndgameLesson(
        name=lesson["name"],
        endgame_type=endgame_type,
        description=lesson["description"],
        key_concepts=[lesson["rule"]],
        setup_fen=first["fen"],
        solution_moves=[first["correct_move_san"]],
        explanations={0: first.get("idea", lesson["rule"])},
        common_mistakes=[
            position.get("on_wrong", "")
            for position in positions
            if position.get("on_wrong")
        ],
        practice_positions=[position["fen"] for position in positions],
        category_key=category_key,
        lesson_key=lesson_key,
    )


def _load_lessons() -> Dict[str, EndgameLesson]:
    result = {}
    for legacy_key, (category, lesson, endgame_type) in _LEGACY_KEY_ROUTES.items():
        adapted = _adapt_lesson(category, lesson, endgame_type)
        if adapted:
            result[legacy_key] = adapted
    return result


ENDGAME_LESSONS: Dict[str, EndgameLesson] = _load_lessons()


def reload_lessons() -> None:
    global ENDGAME_LESSONS
    ENDGAME_LESSONS = _load_lessons()


def get_endgame_principles() -> List[Dict[str, str]]:
    return [
        {
            "rule": lesson["rule"],
            "lesson_id": lesson["lesson_id"],
            "source": "backend/data/coaching/endgame_theory_tree.json",
        }
        for category in get_all_categories()
        for lesson in category.get("lessons", [])
    ]


def detect_endgame_type(board: chess.Board) -> Optional[EndgameType]:
    pieces = {
        color: {
            piece_type: len(board.pieces(piece_type, color))
            for piece_type in (
                chess.QUEEN,
                chess.ROOK,
                chess.BISHOP,
                chess.KNIGHT,
                chess.PAWN,
            )
        }
        for color in (chess.WHITE, chess.BLACK)
    }
    total = sum(sum(counts.values()) for counts in pieces.values())
    if total > 6:
        return None

    white = pieces[chess.WHITE]
    black = pieces[chess.BLACK]
    white_total = sum(white.values())
    black_total = sum(black.values())

    if (
        white[chess.QUEEN] == 1
        and white_total == 1
        and black_total == 0
    ) or (
        black[chess.QUEEN] == 1
        and black_total == 1
        and white_total == 0
    ):
        return EndgameType.KING_QUEEN
    if (
        white[chess.ROOK] == 1
        and white_total == 1
        and black_total == 0
    ) or (
        black[chess.ROOK] == 1
        and black_total == 1
        and white_total == 0
    ):
        return EndgameType.KING_ROOK
    if total <= 2 and (
        white[chess.PAWN] > 0 or black[chess.PAWN] > 0
    ):
        return EndgameType.KING_PAWN
    if (
        white[chess.ROOK] >= 1
        and black[chess.ROOK] >= 1
        and white[chess.QUEEN] == 0
        and black[chess.QUEEN] == 0
    ):
        return EndgameType.ROOK_ENDGAME
    if white[chess.QUEEN] >= 1 and black[chess.QUEEN] >= 1:
        return EndgameType.QUEEN_ENDGAME
    return None


def get_relevant_lesson(
    endgame_type: EndgameType,
    board: chess.Board,
) -> Optional[EndgameLesson]:
    if endgame_type == EndgameType.KING_PAWN:
        return ENDGAME_LESSONS.get("opposition")
    if endgame_type == EndgameType.ROOK_ENDGAME:
        white_pawns = len(board.pieces(chess.PAWN, chess.WHITE))
        black_pawns = len(board.pieces(chess.PAWN, chess.BLACK))
        if white_pawns != black_pawns:
            return ENDGAME_LESSONS.get("lucena_position")
    # Basic queen/rook mates remain unoffered until canonical verified lessons
    # exist. The legacy source contained invalid positions.
    return None


async def check_endgame_and_offer_teaching(
    db,
    session_id: str,
    current_fen: str,
    user_id: str,
    user_color: str,
) -> Optional[Dict]:
    board = chess.Board(current_fen)
    session = await db.coach_sessions.find_one({"session_id": session_id})
    if not session or session.get("endgame_offer_shown"):
        return None

    endgame_type = detect_endgame_type(board)
    lesson = (
        get_relevant_lesson(endgame_type, board)
        if endgame_type
        else None
    )
    if not lesson:
        return None

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "endgame_offer_shown": True,
                "detected_endgame": endgame_type.value,
            }
        },
    )
    return {
        "type": "endgame_teaching_offer",
        "endgame_type": endgame_type.value,
        "lesson_name": lesson.name,
        "lesson_key": lesson.lesson_key,
        "category": lesson.category_key,
        "message": (
            f"This position uses {lesson.name}. Want to practise the idea "
            "before you continue?"
        ),
        "description": lesson.description,
        "key_concepts": lesson.key_concepts,
        "options": [
            {
                "id": "learn_technique",
                "label": f"Learn {lesson.name}",
                "description": "Try guided positions, then solve one alone.",
            },
            {
                "id": "show_key_concepts",
                "label": "Show the main rule",
                "description": lesson.key_concepts[0],
            },
            {
                "id": "just_play",
                "label": "Let me try",
                "description": "Continue this game.",
            },
        ],
        "canonical_source": lesson.canonical_source,
    }


async def start_endgame_lesson(db, session_id: str, lesson_key: str) -> Dict:
    lesson = ENDGAME_LESSONS.get(lesson_key)
    if not lesson:
        return {"error": "Verified lesson not found"}
    from services.teaching_engine import start_endgame_lesson as start_canonical

    return await start_canonical(
        db,
        session_id,
        "",
        {
            "category": lesson.category_key,
            "lesson_key": lesson.lesson_key,
        },
    )


async def process_endgame_teaching_move(
    db,
    session_id: str,
    user_move: str,
) -> Dict:
    from services.teaching_engine import process_endgame_move

    return await process_endgame_move(db, session_id, user_move)
