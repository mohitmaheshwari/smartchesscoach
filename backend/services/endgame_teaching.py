"""
Endgame Teaching — loader + detectors + lesson flow.

Lesson data lives in data/endgames.json (admin-editable). This module
loads it at import time and rehydrates each entry into an EndgameLesson
dataclass so existing callers' attribute access (lesson.name,
lesson.solution_moves, etc.) keeps working unchanged.

Callers unchanged:
  - detect_endgame_type(board)
  - get_relevant_lesson(endgame_type, board)
  - check_endgame_and_offer_teaching(...)
  - start_endgame_lesson(...)
  - process_endgame_teaching_move(...)
  - ENDGAME_LESSONS dict (public)
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


class EndgameType(str, Enum):
    """Types of endgames"""
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
    """An endgame lesson with interactive teaching"""
    name: str
    endgame_type: EndgameType
    description: str
    key_concepts: List[str]
    setup_fen: str
    solution_moves: List[str]
    explanations: Dict[int, str]
    common_mistakes: List[str]
    practice_positions: List[str] = field(default_factory=list)


# ── Data load ─────────────────────────────────────────────────────────

_ENDGAMES_PATH = Path(__file__).resolve().parent.parent / "data" / "endgames.json"


def _rehydrate_lesson(d: Dict) -> EndgameLesson:
    """Rebuild an EndgameLesson from a raw JSON dict. Handles the enum +
    int-keyed explanations (JSON only allows string keys)."""
    return EndgameLesson(
        name=d.get("name", ""),
        endgame_type=EndgameType(d.get("endgame_type", "basic_checkmate")),
        description=d.get("description", ""),
        key_concepts=d.get("key_concepts", []) or [],
        setup_fen=d.get("setup_fen", ""),
        solution_moves=d.get("solution_moves", []) or [],
        explanations={int(k): v for k, v in (d.get("explanations", {}) or {}).items()},
        common_mistakes=d.get("common_mistakes", []) or [],
        practice_positions=d.get("practice_positions", []) or [],
    )


def _load_lessons() -> Dict[str, EndgameLesson]:
    try:
        with open(_ENDGAMES_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: _rehydrate_lesson(v) for k, v in raw.items()}
    except Exception as e:
        logger.error(f"Failed to load {_ENDGAMES_PATH}: {e}")
        return {}


ENDGAME_LESSONS: Dict[str, EndgameLesson] = _load_lessons()


def reload_lessons() -> None:
    """Force-reload from disk (for admin edits without restart)."""
    global ENDGAME_LESSONS
    ENDGAME_LESSONS = _load_lessons()


# ── Detection ─────────────────────────────────────────────────────────


def detect_endgame_type(board: chess.Board) -> Optional[EndgameType]:
    """Detect the endgame type from board material. Returns None if not an endgame."""
    white_pieces = {
        "Q": len(board.pieces(chess.QUEEN, chess.WHITE)),
        "R": len(board.pieces(chess.ROOK, chess.WHITE)),
        "B": len(board.pieces(chess.BISHOP, chess.WHITE)),
        "N": len(board.pieces(chess.KNIGHT, chess.WHITE)),
        "P": len(board.pieces(chess.PAWN, chess.WHITE)),
    }
    black_pieces = {
        "Q": len(board.pieces(chess.QUEEN, chess.BLACK)),
        "R": len(board.pieces(chess.ROOK, chess.BLACK)),
        "B": len(board.pieces(chess.BISHOP, chess.BLACK)),
        "N": len(board.pieces(chess.KNIGHT, chess.BLACK)),
        "P": len(board.pieces(chess.PAWN, chess.BLACK)),
    }
    total_white = sum(white_pieces.values())
    total_black = sum(black_pieces.values())
    total_pieces = total_white + total_black

    if total_pieces > 6:
        return None

    if (white_pieces["Q"] == 1 and total_white == 1 and total_black == 0) or \
       (black_pieces["Q"] == 1 and total_black == 1 and total_white == 0):
        return EndgameType.KING_QUEEN

    if (white_pieces["R"] == 1 and total_white == 1 and total_black == 0) or \
       (black_pieces["R"] == 1 and total_black == 1 and total_white == 0):
        return EndgameType.KING_ROOK

    if total_pieces <= 2 and (white_pieces["P"] > 0 or black_pieces["P"] > 0):
        return EndgameType.KING_PAWN

    if white_pieces["R"] >= 1 and black_pieces["R"] >= 1 and \
       white_pieces["Q"] == 0 and black_pieces["Q"] == 0:
        return EndgameType.ROOK_ENDGAME

    if white_pieces["Q"] >= 1 and black_pieces["Q"] >= 1:
        return EndgameType.QUEEN_ENDGAME

    return None


def get_relevant_lesson(endgame_type: EndgameType, board: chess.Board) -> Optional[EndgameLesson]:
    """Pick the most relevant lesson for a detected endgame."""
    if endgame_type == EndgameType.KING_QUEEN:
        return ENDGAME_LESSONS.get("queen_checkmate")
    if endgame_type == EndgameType.KING_ROOK:
        return ENDGAME_LESSONS.get("rook_checkmate")
    if endgame_type == EndgameType.KING_PAWN:
        return ENDGAME_LESSONS.get("opposition")
    if endgame_type == EndgameType.ROOK_ENDGAME:
        white_pawns = len(board.pieces(chess.PAWN, chess.WHITE))
        black_pawns = len(board.pieces(chess.PAWN, chess.BLACK))
        if white_pawns != black_pawns:
            return ENDGAME_LESSONS.get("lucena_position")
    return None


# ── Teaching-flow endpoints ───────────────────────────────────────────


async def check_endgame_and_offer_teaching(
    db, session_id: str, current_fen: str, user_id: str, user_color: str,
) -> Optional[Dict]:
    """Detect if we're in a teachable endgame and offer a lesson."""
    board = chess.Board(current_fen)

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return None
    if session_doc.get("endgame_offer_shown"):
        return None

    endgame_type = detect_endgame_type(board)
    if not endgame_type:
        return None

    lesson = get_relevant_lesson(endgame_type, board)
    if not lesson:
        return None

    logger.info(f"Endgame detected: {endgame_type.value}, suggesting lesson: {lesson.name}")

    options = [
        {
            "id": "learn_technique",
            "label": f"Learn {lesson.name}",
            "description": "Interactive lesson on this endgame technique",
        },
        {
            "id": "show_key_concepts",
            "label": "Show me the key ideas",
            "description": "Quick summary of what to know",
        },
        {
            "id": "just_play",
            "label": "Let me try myself",
            "description": "Continue playing without lesson",
        },
    ]

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"endgame_offer_shown": True, "detected_endgame": endgame_type.value}},
    )

    return {
        "type": "endgame_teaching_offer",
        "endgame_type": endgame_type.value,
        "lesson_name": lesson.name,
        "message": (
            f"We're in a {lesson.name.lower()} position! This is a crucial "
            "endgame technique. Would you like to learn it?"
        ),
        "description": lesson.description,
        "key_concepts": lesson.key_concepts,
        "options": options,
    }


async def start_endgame_lesson(db, session_id: str, lesson_key: str) -> Dict:
    """Start an interactive endgame lesson."""
    lesson = ENDGAME_LESSONS.get(lesson_key)
    if not lesson:
        return {"error": "Lesson not found"}

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    teaching_data = {
        "lesson_key": lesson_key,
        "lesson_name": lesson.name,
        "current_move_index": 0,
        "solution_moves": lesson.solution_moves,
        "explanations": lesson.explanations,
        "setup_fen": lesson.setup_fen,
        "teaching_fen": lesson.setup_fen,
        "original_fen": session_doc.get("current_fen"),
        "original_move_history": session_doc.get("move_history", []),
    }

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_mode": "endgame",
            "teaching_data": teaching_data,
            "current_fen": lesson.setup_fen,
        }},
    )

    first_explanation = lesson.explanations.get(0, "Let's begin the lesson.")

    return {
        "success": True,
        "mode": "endgame",
        "lesson_name": lesson.name,
        "description": lesson.description,
        "key_concepts": lesson.key_concepts,
        "common_mistakes": lesson.common_mistakes,
        "teaching_fen": lesson.setup_fen,
        "instruction": {
            "message": first_explanation,
            "expected_move": lesson.solution_moves[0] if lesson.solution_moves else None,
            "total_moves": len(lesson.solution_moves),
        },
    }


async def process_endgame_teaching_move(db, session_id: str, user_move: str) -> Dict:
    """Process a move during endgame teaching mode."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    teaching_data = session_doc.get("teaching_data", {})
    current_index = teaching_data.get("current_move_index", 0)
    solution_moves = teaching_data.get("solution_moves", [])
    explanations = teaching_data.get("explanations", {})
    # explanations from the DB come back as str-keyed (JSON semantics);
    # normalise for downstream .get(int) calls.
    if explanations and isinstance(next(iter(explanations.keys())), str):
        explanations = {int(k): v for k, v in explanations.items()}

    if current_index >= len(solution_moves):
        return {"complete": True, "message": "Lesson complete!"}

    expected_move = solution_moves[current_index]

    user_clean = user_move.lower().replace("+", "").replace("#", "").replace("x", "")
    expected_clean = expected_move.lower().replace("+", "").replace("#", "").replace("x", "")

    if user_clean != expected_clean:
        return {
            "correct": False,
            "expected_move": expected_move,
            "message": f"Not quite! The correct move is {expected_move}.",
            "hint": explanations.get(current_index, "Think about the key concepts."),
        }

    current_fen = teaching_data.get("teaching_fen")
    board = chess.Board(current_fen)
    try:
        move = board.parse_san(expected_move)
        board.push(move)
        new_fen = board.fen()
    except Exception as e:
        logger.error(f"Error applying move: {e}")
        return {"error": str(e)}

    new_index = current_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"teaching_data": teaching_data, "current_fen": new_fen}},
    )

    if new_index >= len(solution_moves):
        lesson = ENDGAME_LESSONS.get(teaching_data.get("lesson_key"))
        return {
            "complete": True,
            "message": "Excellent! You've completed the lesson!",
            "summary": lesson.description if lesson else "",
            "key_concepts": lesson.key_concepts if lesson else [],
        }

    next_explanation = explanations.get(new_index, "Continue with the technique.")
    next_move = solution_moves[new_index]

    return {
        "correct": True,
        "message": "Correct!",
        "explanation": next_explanation,
        "next_instruction": {
            "message": next_explanation,
            "expected_move": next_move,
            "progress": f"{new_index}/{len(solution_moves)}",
        },
        "teaching_fen": new_fen,
    }
