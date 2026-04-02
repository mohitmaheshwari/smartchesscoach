"""
Teaching Engine — Generic lesson dispatcher for Play with Coach
================================================================

Supports multiple lesson types:
  - "opening" → Opening curriculum moves (existing flow via opening_teaching_integration)
  - "trap"    → Walk through a trap sequence step-by-step (trick_library_service)
  - "endgame" → Solve endgame positions from theory tree

Each lesson type implements:
  - start(db, session_id, user_id, params) → lesson data
  - process_move(db, session_id, move) → feedback + next instruction
  - exit(db, session_id, choice) → restored state or cleanup
"""

import logging
import json
import os
import chess
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENDGAME_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "coaching", "endgame_theory_tree.json"
)

_ENDGAME_TREE = None

def _load_endgame_tree() -> Dict:
    global _ENDGAME_TREE
    if _ENDGAME_TREE is None:
        try:
            with open(ENDGAME_TREE_PATH, "r") as f:
                _ENDGAME_TREE = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load endgame tree: {e}")
            _ENDGAME_TREE = {}
    return _ENDGAME_TREE


# ─────────────────────────────────────────────
# TRAP LESSONS
# ─────────────────────────────────────────────

async def start_trap_lesson(db, session_id: str, user_id: str, params: Dict) -> Dict:
    """Start a trap practice lesson inside a coach session."""
    from trick_library_service import get_trap_for_practice

    trap_key = params.get("trap_key")
    if not trap_key:
        return {"error": "trap_key is required"}

    trap = get_trap_for_practice(trap_key, "execution")
    if not trap:
        return {"error": f"Trap '{trap_key}' not found or has no practice data"}

    # Build the lesson move sequence the user needs to play
    user_moves = trap.get("user_moves", [])
    engine_moves = trap.get("engine_moves", [])
    full_sequence = trap.get("full_sequence", [])

    if not full_sequence:
        return {"error": "Trap has no move sequence"}

    # First instruction: first move of the sequence
    first_move_idx = 0
    first_move = full_sequence[first_move_idx]
    is_user_move = any(um["index"] == first_move_idx for um in user_moves)

    # Store teaching state in session
    teaching_state = {
        "teaching_mode": True,
        "lesson_type": "trap",
        "lesson_key": trap_key,
        "lesson_name": trap["name"],
        "trap_data": {
            "full_sequence": full_sequence,
            "user_moves": user_moves,
            "engine_moves": engine_moves,
            "user_color": trap.get("user_color", "white"),
            "explanation": trap.get("explanation", ""),
            "why_it_works": trap.get("why_it_works", ""),
            "hints": trap.get("hints", ""),
        },
        "current_move_index": 0,
        "pre_teaching_fen": None,  # Will be set from session
    }

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if session_doc:
        teaching_state["pre_teaching_fen"] = session_doc.get("current_fen")

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": teaching_state}
    )

    # Auto-play engine moves at the start if engine goes first
    teaching_fen = trap.get("start_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    auto_played = []

    board = chess.Board(teaching_fen)
    move_idx = 0
    while move_idx < len(full_sequence):
        is_engine = any(em["index"] == move_idx for em in engine_moves)
        if is_engine:
            move_san = full_sequence[move_idx]
            try:
                board.push_san(move_san)
                auto_played.append(move_san)
                move_idx += 1
            except Exception:
                break
        else:
            break

    current_move_index = move_idx
    teaching_fen = board.fen()

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_move_index": current_move_index}}
    )

    next_user_move = full_sequence[current_move_index] if current_move_index < len(full_sequence) else None
    remaining = len([um for um in user_moves if um["index"] >= current_move_index])

    return {
        "success": True,
        "lesson_type": "trap",
        "lesson_name": trap["name"],
        "lesson_key": trap_key,
        "teaching_fen": teaching_fen,
        "instruction": {
            "move": next_user_move,
            "is_user_move": True,
            "message": f"Play {next_user_move} to set up the trap",
            "remaining": remaining,
        },
        "auto_played_moves": auto_played,
        "trap_info": {
            "description": trap.get("explanation", ""),
            "why_it_works": trap.get("why_it_works", ""),
        },
    }


async def process_trap_move(db, session_id: str, move: str) -> Dict:
    """Validate a move during trap practice."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    trap_data = session_doc.get("trap_data", {})
    full_sequence = trap_data.get("full_sequence", [])
    user_moves = trap_data.get("user_moves", [])
    engine_moves = trap_data.get("engine_moves", [])
    current_idx = session_doc.get("current_move_index", 0)

    if current_idx >= len(full_sequence):
        return {"complete": True, "message": "Trap complete!"}

    expected_move = full_sequence[current_idx]

    # Normalize move comparison
    move_clean = move.replace("+", "").replace("#", "").strip()
    expected_clean = expected_move.replace("+", "").replace("#", "").strip()

    if move_clean != expected_clean:
        # Check if it's the same move with different notation
        hint = f"Expected {expected_move}."
        um = next((u for u in user_moves if u["index"] == current_idx), None)
        return {
            "correct": False,
            "message": f"Not quite! The trap needs {expected_move} here.",
            "hint": hint,
            "expected_move": expected_move,
        }

    # Correct move! Advance and auto-play engine responses
    next_idx = current_idx + 1
    board = chess.Board(session_doc.get("current_fen", chess.STARTING_FEN))

    # Play the user's move
    try:
        board.push_san(expected_move)
    except Exception:
        board = chess.Board(chess.STARTING_FEN)
        for m in full_sequence[:next_idx]:
            try:
                board.push_san(m)
            except Exception:
                pass

    auto_played = []
    # Auto-play engine moves
    while next_idx < len(full_sequence):
        is_engine = any(em["index"] == next_idx for em in engine_moves)
        if is_engine:
            eng_move = full_sequence[next_idx]
            try:
                board.push_san(eng_move)
                auto_played.append(eng_move)
                next_idx += 1
            except Exception:
                break
        else:
            break

    teaching_fen = board.fen()

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_move_index": next_idx, "current_fen": teaching_fen}}
    )

    # Check if lesson complete
    if next_idx >= len(full_sequence):
        is_winning = any(um.get("is_winning") and um["move"] == expected_move for um in user_moves)
        return {
            "correct": True,
            "complete": True,
            "teaching_fen": teaching_fen,
            "auto_played": bool(auto_played),
            "auto_played_moves": auto_played,
            "message": f"Trap complete! {trap_data.get('explanation', 'Well done!')}",
            "why_it_works": trap_data.get("why_it_works", ""),
        }

    # More moves to go
    next_move = full_sequence[next_idx]
    remaining_user = len([um for um in user_moves if um["index"] >= next_idx])

    msg = f"Good! Now play {next_move}."
    if auto_played:
        msg = f"Opponent played {', '.join(auto_played)}. Now play {next_move}."

    return {
        "correct": True,
        "complete": False,
        "teaching_fen": teaching_fen,
        "auto_played": bool(auto_played),
        "auto_played_moves": auto_played,
        "message": msg,
        "next_instruction": {
            "move": next_move,
            "is_user_move": True,
            "message": msg,
            "remaining": remaining_user,
        },
    }


# ─────────────────────────────────────────────
# ENDGAME LESSONS
# ─────────────────────────────────────────────

async def start_endgame_lesson(db, session_id: str, user_id: str, params: Dict) -> Dict:
    """Start an endgame lesson inside a coach session."""
    tree = _load_endgame_tree()
    category = params.get("category")
    lesson_key = params.get("lesson_key")

    if not category or not lesson_key:
        return {"error": "category and lesson_key are required"}

    cat_data = tree.get(category)
    if not cat_data:
        return {"error": f"Category '{category}' not found"}

    lesson = cat_data.get("lessons", {}).get(lesson_key)
    if not lesson:
        return {"error": f"Lesson '{lesson_key}' not found in {category}"}

    positions = lesson.get("positions", [])
    if not positions:
        return {"error": "Lesson has no positions"}

    first_pos = positions[0]

    # Store in session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    teaching_state = {
        "teaching_mode": True,
        "lesson_type": "endgame",
        "lesson_key": f"{category}/{lesson_key}",
        "lesson_name": lesson["name"],
        "endgame_data": {
            "category": category,
            "category_name": cat_data.get("name", category),
            "rule": lesson.get("rule", ""),
            "description": lesson.get("description", ""),
            "positions": positions,
        },
        "current_position_index": 0,
        "pre_teaching_fen": session_doc.get("current_fen") if session_doc else None,
    }

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": teaching_state}
    )

    return {
        "success": True,
        "lesson_type": "endgame",
        "lesson_name": lesson["name"],
        "lesson_key": f"{category}/{lesson_key}",
        "teaching_fen": first_pos["fen"],
        "instruction": {
            "move": first_pos["correct_move_san"],
            "is_user_move": True,
            "message": first_pos.get("prompt", "Find the best move."),
            "remaining": len(positions),
        },
        "endgame_info": {
            "rule": lesson.get("rule", ""),
            "description": lesson.get("description", ""),
        },
    }


async def process_endgame_move(db, session_id: str, move: str) -> Dict:
    """Validate a move during endgame lesson."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    eg_data = session_doc.get("endgame_data", {})
    positions = eg_data.get("positions", [])
    current_idx = session_doc.get("current_position_index", 0)

    if current_idx >= len(positions):
        return {"complete": True, "message": "Endgame lesson complete!"}

    pos = positions[current_idx]
    correct_san = pos.get("correct_move_san", "")
    correct_uci = pos.get("correct_move_uci", "")

    # Normalize comparison
    move_clean = move.replace("+", "").replace("#", "").strip()
    correct_clean = correct_san.replace("+", "").replace("#", "").strip()

    is_correct = move_clean == correct_clean

    # Also check UCI match
    if not is_correct and correct_uci:
        try:
            board = chess.Board(pos["fen"])
            user_move = board.parse_san(move)
            if user_move.uci() == correct_uci:
                is_correct = True
        except Exception:
            pass

    if not is_correct:
        return {
            "correct": False,
            "message": pos.get("on_wrong", f"Not quite. The correct move is {correct_san}."),
            "hint": pos.get("rule_reminder", pos.get("idea", "")),
            "expected_move": correct_san,
        }

    # Correct! Apply the move to get new FEN
    try:
        board = chess.Board(pos["fen"])
        board.push_san(correct_san)
        new_fen = board.fen()
    except Exception:
        new_fen = pos["fen"]

    next_idx = current_idx + 1

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_position_index": next_idx}}
    )

    # Check if lesson complete
    if next_idx >= len(positions):
        return {
            "correct": True,
            "complete": True,
            "teaching_fen": new_fen,
            "message": f"Excellent! You've completed the {session_doc.get('lesson_name', 'endgame')} lesson. Rule: {eg_data.get('rule', '')}",
        }

    # Next position
    next_pos = positions[next_idx]
    return {
        "correct": True,
        "complete": False,
        "teaching_fen": next_pos["fen"],
        "message": pos.get("on_correct", "Correct!"),
        "next_instruction": {
            "move": next_pos["correct_move_san"],
            "is_user_move": True,
            "message": next_pos.get("prompt", "Find the best move."),
            "remaining": len(positions) - next_idx,
        },
        "endgame_info": {
            "rule_reminder": pos.get("rule_reminder", ""),
            "idea": pos.get("idea", ""),
        },
    }


# ─────────────────────────────────────────────
# GENERIC DISPATCH
# ─────────────────────────────────────────────

async def start_lesson(db, session_id: str, user_id: str, lesson_type: str, params: Dict) -> Dict:
    """Start a lesson of any type."""
    if lesson_type == "trap":
        return await start_trap_lesson(db, session_id, user_id, params)
    elif lesson_type == "endgame":
        return await start_endgame_lesson(db, session_id, user_id, params)
    elif lesson_type in ("learn_trap", "learn_main_line", "opening"):
        # Delegate to existing opening teaching
        from services.opening_teaching_integration import start_opening_lesson
        return await start_opening_lesson(db, session_id, user_id, lesson_type)
    else:
        return {"error": f"Unknown lesson type: {lesson_type}"}


async def process_lesson_move(db, session_id: str, move: str) -> Dict:
    """Process a move — dispatches based on current lesson type in session."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    lesson_type = session_doc.get("lesson_type", "opening")

    if lesson_type == "trap":
        return await process_trap_move(db, session_id, move)
    elif lesson_type == "endgame":
        return await process_endgame_move(db, session_id, move)
    else:
        # Default: opening teaching
        from services.opening_teaching_integration import process_teaching_move
        return await process_teaching_move(db, session_id, move)


async def exit_lesson(db, session_id: str, choice: str) -> Dict:
    """Exit any lesson type and restore game state."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    restored_fen = session_doc.get("pre_teaching_fen")

    # Clean up teaching state
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$unset": {
            "teaching_mode": "",
            "lesson_type": "",
            "lesson_key": "",
            "lesson_name": "",
            "trap_data": "",
            "endgame_data": "",
            "current_move_index": "",
            "current_position_index": "",
            "pre_teaching_fen": "",
        }}
    )

    if choice == "continue_game" and restored_fen:
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"current_fen": restored_fen}}
        )
        return {"success": True, "restored_fen": restored_fen}

    return {"success": True}


# ─────────────────────────────────────────────
# LESSON CATALOG (for frontend lesson picker)
# ─────────────────────────────────────────────

def get_lesson_catalog() -> Dict:
    """Return available lessons organized by type for the lesson picker UI."""
    from trick_library_service import get_all_traps

    # Traps
    traps = get_all_traps()
    trap_lessons = []
    for trap in traps:
        trap_lessons.append({
            "key": trap["key"],
            "name": trap["name"],
            "opening": trap.get("opening", ""),
            "difficulty": trap.get("difficulty", "intermediate"),
            "description": trap.get("description", ""),
            "trap_for": trap.get("trap_for", ""),
            "tactical_theme": trap.get("tactical_theme", ""),
        })

    # Endgames
    tree = _load_endgame_tree()
    endgame_lessons = []
    for cat_key, cat_data in tree.items():
        if cat_key == "_meta":
            continue
        lessons = cat_data.get("lessons", {})
        for lesson_key, lesson in lessons.items():
            positions = lesson.get("positions", [])
            endgame_lessons.append({
                "category": cat_key,
                "category_name": cat_data.get("name", cat_key),
                "lesson_key": lesson_key,
                "name": lesson.get("name", lesson_key),
                "rule": lesson.get("rule", ""),
                "description": lesson.get("description", ""),
                "positions_count": len(positions),
                "icon": cat_data.get("icon", "book"),
            })

    return {
        "traps": trap_lessons,
        "endgames": endgame_lessons,
    }
