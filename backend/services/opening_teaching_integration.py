"""
Opening Teaching Integration for Play with Coach
=================================================

This module integrates the Opening Theory System with the live coaching game.
ALL opening theory data comes from the JSON file via opening_theory_json_service.

Flow:
1. After each move, check if we're in a known opening
2. If opening detected AND user hasn't seen the offer yet, send teaching offer
3. User can choose: Learn trap / Learn main line / Just play
4. If user chooses to learn, enter teaching mode
5. In teaching mode, guide user through moves one by one (10-15+ moves deep)
6. After teaching complete, continue normal game or offer to restart
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from services.verified_opening_traps import (
    get_applicable_traps_for_moves,
    get_verified_trap_by_name,
    get_verified_traps_for_opening,
    select_preferred_trap,
)
from services.opening_correction_service import select_corrected_trap_for_current_line
from services.opening_theory_json_service import (
    get_opening_theory,
    get_available_variations,
    get_variation_lesson_moves,
    get_move_teaching_context,
)

logger = logging.getLogger(__name__)


async def check_opening_and_offer_teaching(
    db,
    session_id: str,
    move_history: List[Dict],
    user_color: str,
    user_id: str
) -> Optional[Dict]:
    """
    Check if we're in a known opening and offer interactive teaching.
    Called after each move to see if we should offer opening teaching.
    """
    from services.opening_mastery import detect_opening_from_moves, get_user_opening_progress

    logger.info(f"Checking opening for session {session_id}, move_history length: {len(move_history)}")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return None

    if session_doc.get("teaching_mode"):
        return None
    if session_doc.get("opening_offer_shown"):
        return None
    if len(move_history) > 24:
        return None
    if len(move_history) < 2:
        return None

    moves = [m.get("move", "") for m in move_history if m.get("move")]
    opening_info = detect_opening_from_moves(moves)
    if not opening_info:
        return None

    logger.info(f"Opening detected: {opening_info['opening_name']}")
    opening_key = opening_info["opening_key"]
    opening_name = opening_info["opening_name"]

    # Get theory data from JSON
    theory = get_opening_theory(opening_key)
    if theory:
        opening_name = theory.get("name", opening_name)
        opening_description = theory.get("white_plan", "") + " / " + theory.get("black_plan", "")
        opening_character = "open" if any(m in theory.get("main_line", []) for m in ["e4", "e5"]) else "closed"
    else:
        opening_description = opening_info.get("description", "")
        opening_character = opening_info.get("character", "strategic")

    progress = await get_user_opening_progress(db, user_id, opening_name)

    has_learned_before = progress and progress.mastery_level.value not in ("unknown", "introduced")
    if has_learned_before:
        intro_message = f"Welcome back! Ready to continue learning the {opening_name}?"
    else:
        intro_message = f"Let's learn the {opening_name}! {opening_description}"

    # Build interactive options
    options = []

    # Check for available traps
    suggested_trap = select_preferred_trap(opening_key, moves)
    corrected_trap = await select_corrected_trap_for_current_line(db, opening_key, moves)

    trap_name = None
    if corrected_trap:
        trap_name = corrected_trap.get("corrected_name") or corrected_trap.get("trap_name") or "Corrected trap"
        options.append({
            "id": "learn_trap",
            "label": f"Learn the {trap_name}",
            "description": "Interactive trap lesson - I'll show you the corrected moves"
        })
    elif suggested_trap:
        trap_name = suggested_trap.name
        options.append({
            "id": "learn_trap",
            "label": f"Learn the {trap_name}",
            "description": "Interactive trap lesson - I'll show you the moves"
        })

    # Show available variations from JSON (only if deep theory exists)
    variations = get_available_variations(opening_key)
    has_deep_theory = len(variations) > 0
    
    if has_deep_theory:
        first_var = variations[0]
        options.append({
            "id": "learn_main_line",
            "label": f"Learn the {first_var['name']} ({first_var['total_moves']} moves deep)",
            "description": "Step-by-step opening theory"
        })

    options.append({
        "id": "just_play",
        "label": "Just play - I'll figure it out",
        "description": "Continue the game without lesson"
    })

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "detected_opening": opening_key,
            "opening_offer_shown": True
        }}
    )

    return {
        "type": "opening_teaching_offer",
        "opening_key": opening_key,
        "opening_name": opening_name,
        "message": intro_message,
        "description": opening_description,
        "character": opening_character,
        "options": options,
        "has_learned_before": has_learned_before,
        "trap_available": suggested_trap is not None or corrected_trap is not None,
        "trap_name": trap_name,
    }


async def start_opening_lesson(
    db,
    session_id: str,
    user_id: str,
    lesson_type: str  # "learn_trap" or "learn_main_line"
) -> Dict:
    """
    Start an interactive opening lesson.
    Pauses the normal game and enters teaching mode.
    All lesson data comes from the JSON theory file.
    """
    from services.opening_mastery import get_user_opening_progress
    import chess

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    opening_key = session_doc.get("detected_opening") or session_doc.get("opening_to_teach")
    if not opening_key:
        return {"error": "No opening detected"}

    # Get opening name from JSON
    theory = get_opening_theory(opening_key)
    opening_name = theory.get("name", opening_key.replace("_", " ").title()) if theory else opening_key.replace("_", " ").title()

    user_color = session_doc.get("user_color", "white")
    user_plays_white = user_color == "white"
    progress = await get_user_opening_progress(db, user_id, opening_name)

    if lesson_type == "learn_trap":
        return await _start_trap_lesson(db, session_id, session_doc, opening_key, opening_name, user_plays_white, progress)
    else:
        # Check if deep theory exists before starting
        variations = get_available_variations(opening_key)
        if not variations:
            return {"error": f"No deep theory available yet for the {opening_name}. We're adding more openings soon! Try playing and the coach will guide you."}
        return await _start_main_line_lesson(db, session_id, session_doc, opening_key, opening_name, user_plays_white, progress)


async def _start_main_line_lesson(db, session_id, session_doc, opening_key, opening_name, user_plays_white, progress):
    """Start a main line lesson using the JSON theory data.
    
    Resumes from the current board position — matches moves already played
    against the lesson line and picks up from there.
    """
    import chess

    # Get available variations from JSON
    variations = get_available_variations(opening_key)
    if not variations:
        return {"error": f"No theory data available for {opening_name}"}

    # Use the first (default) variation
    var_key = variations[0]["key"]
    lesson = get_variation_lesson_moves(opening_key, var_key)
    if not lesson or not lesson.get("moves"):
        return {"error": f"No lesson moves available for {opening_name}"}

    main_line_moves = lesson["moves"]
    variation_name = lesson["variation_name"]
    white_plan = lesson.get("white_plan", "")
    black_plan = lesson.get("black_plan", "")
    common_learnings = lesson.get("common_learnings", [])
    critical_positions = lesson.get("critical_positions", {})

    # --- Match moves already played on the board against the lesson line ---
    move_history = session_doc.get("move_history", [])
    played_sans = [m.get("move", "") or m.get("san", "") for m in move_history if m.get("move") or m.get("san")]

    def normalize(m):
        return m.replace("+", "").replace("#", "").replace("!", "").replace("?", "").strip().lower()

    resume_index = 0
    for i, lesson_move in enumerate(main_line_moves):
        if i < len(played_sans) and normalize(played_sans[i]) == normalize(lesson_move):
            resume_index = i + 1
        else:
            break

    # Build the FEN at the resume point by replaying lesson moves up to resume_index
    board = chess.Board()
    for i in range(resume_index):
        try:
            board.push_san(main_line_moves[i])
        except Exception as e:
            logger.error(f"Error replaying lesson move {i} ({main_line_moves[i]}): {e}")
            resume_index = i
            break

    current_fen = board.fen()
    logger.info(f"Starting main line lesson: {variation_name} with {len(main_line_moves)} moves, resuming from move {resume_index}")

    teaching_data = {
        "variation_name": variation_name,
        "variation_key": var_key,
        "main_line_moves": main_line_moves,
        "current_move_index": resume_index,
        "key_ideas": common_learnings[:5],
        "plans_white": [white_plan] if white_plan else [],
        "plans_black": [black_plan] if black_plan else [],
        "critical_positions": {str(k): v for k, v in critical_positions.items()},
        "user_plays_white": user_plays_white,
        "teaching_fen": current_fen,
        "lesson_start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "original_fen": session_doc.get("current_fen"),
        "original_move_history": move_history,
    }

    mode = "main_line"

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_mode": mode,
            "teaching_opening": opening_key,
            "teaching_data": teaching_data,
            "current_fen": current_fen,
        }}
    )

    remaining = len(main_line_moves) - resume_index
    first_instruction = _get_teaching_instruction(teaching_data, mode, resume_index)

    result = {
        "success": True,
        "mode": mode,
        "opening_name": opening_name,
        "lesson_name": variation_name,
        "total_moves": len(main_line_moves),
        "current_move_index": resume_index,
        "moves_already_played": resume_index,
        "remaining_moves": remaining,
        "instruction": first_instruction,
        "teaching_fen": current_fen,
        "key_ideas": teaching_data.get("key_ideas", []),
        "user_plays_white": user_plays_white,
    }

    # Auto-play if next move is coach's (not user's turn)
    if not first_instruction.get("is_user_move") and not first_instruction.get("complete"):
        auto_result = await _auto_play_teaching_move(db, session_id, teaching_data, mode, resume_index)
        if auto_result.get("auto_played"):
            result["auto_played_move"] = auto_result.get("move_played")
            result["instruction"] = auto_result.get("next_instruction")
            result["teaching_fen"] = auto_result.get("teaching_fen")
            result["current_move_index"] = auto_result.get("new_move_index", resume_index + 1)

    return result


async def _start_trap_lesson(db, session_id, session_doc, opening_key, opening_name, user_plays_white, progress):
    """Start a trap lesson (unchanged logic, uses verified_opening_traps)."""
    from services.opening_correction_service import get_trap_override
    import chess

    move_history = session_doc.get("move_history", [])
    moves_played_san = [m.get("move", "") for m in move_history if m.get("move")]
    corrected_trap = await select_corrected_trap_for_current_line(db, opening_key, moves_played_san)
    corrected_trap_name = corrected_trap.get("corrected_name") or corrected_trap.get("trap_name") if corrected_trap else None

    trap = None
    suggested_trap = session_doc.get("suggested_trap")

    if corrected_trap:
        trap = corrected_trap
    elif suggested_trap and suggested_trap.get("name"):
        trap = get_verified_trap_by_name(opening_key, suggested_trap.get("name"))

    if not trap:
        trap = select_preferred_trap(opening_key, moves_played_san)

    if not trap and not moves_played_san:
        opening_traps = get_verified_traps_for_opening(opening_key)
        trap = opening_traps[0] if opening_traps else None

    if not trap:
        return {"error": "No verified trap available for this exact opening line yet"}

    current_fen = session_doc.get("current_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    moves_played = len(move_history)

    if isinstance(trap, dict):
        trap_name = corrected_trap_name or trap.get("trap_name") or trap.get("corrected_name") or "Corrected trap"
        trap_explanation = trap.get("corrected_explanation") or trap.get("notes") or "Corrected trap line"
        trap_moves_source = trap.get("corrected_moves") or trap.get("current_moves") or []
        trap_refutation = trap.get("notes") or "Follow the corrected line."
        trap_victim_color = trap.get("victim_color") or "unknown"
    else:
        trap_override = await get_trap_override(db, opening_key, trap.name)
        trap_name = trap_override.get("corrected_name") if trap_override and trap_override.get("corrected_name") else trap.name
        trap_explanation = trap_override.get("corrected_explanation") if trap_override and trap_override.get("corrected_explanation") else trap.explanation
        trap_moves_source = trap_override.get("corrected_moves") if trap_override and trap_override.get("corrected_moves") else trap.full_line
        trap_refutation = trap.refutation
        trap_victim_color = trap.victim_color

    trap_moves = trap_moves_source
    current_move_index = 0
    on_trap_line = True

    for i, trap_move in enumerate(trap_moves):
        if i < moves_played:
            played_move = move_history[i].get("move", "") or move_history[i].get("san", "")
            played_normalized = played_move.replace("+", "").replace("#", "").strip()
            trap_normalized = trap_move.replace("+", "").replace("#", "").strip()
            if played_normalized == trap_normalized:
                current_move_index = i + 1
            else:
                on_trap_line = False
                break
        else:
            break

    if not on_trap_line and moves_played > 0:
        return {"error": f"The current game has deviated from the {trap_name} line. Start a new game to learn this trap."}

    teaching_data = {
        "trap_name": trap_name,
        "trap_moves": trap_moves,
        "current_move_index": current_move_index,
        "explanation": trap_explanation,
        "refutation": trap_refutation,
        "victim_color": trap_victim_color,
        "user_plays_white": user_plays_white,
        "teaching_fen": current_fen,
        "lesson_start_fen": current_fen,
        "original_fen": current_fen,
        "original_move_history": move_history,
    }

    mode = "trap"

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_mode": mode,
            "teaching_opening": opening_key,
            "teaching_data": teaching_data,
        }}
    )

    first_instruction = _get_teaching_instruction(teaching_data, mode, current_move_index)

    result = {
        "success": True,
        "mode": mode,
        "opening_name": opening_name,
        "lesson_name": trap_name,
        "total_moves": len(trap_moves),
        "current_move_index": current_move_index,
        "instruction": first_instruction,
        "teaching_fen": teaching_data["teaching_fen"],
        "key_ideas": [],
        "user_plays_white": user_plays_white,
    }

    if not first_instruction.get("is_user_move") and not first_instruction.get("complete"):
        auto_result = await _auto_play_teaching_move(db, session_id, teaching_data, mode, current_move_index)
        if auto_result.get("auto_played"):
            result["auto_played_move"] = auto_result.get("move_played")
            result["instruction"] = auto_result.get("next_instruction")
            result["teaching_fen"] = auto_result.get("teaching_fen")
            result["current_move_index"] = auto_result.get("new_move_index", current_move_index + 1)

    return result


def _get_teaching_instruction(teaching_data: Dict, mode: str, move_index: int) -> Dict:
    """
    Get teaching instruction for current move.
    Enriched with critical position data from JSON when available.
    """
    if mode == "trap":
        moves = teaching_data.get("trap_moves", [])
    else:
        moves = teaching_data.get("main_line_moves", [])

    if move_index >= len(moves):
        return {
            "complete": True,
            "message": "Excellent! You've completed the lesson!",
            "summary": teaching_data.get("explanation", ""),
        }

    move = moves[move_index]
    is_white = move_index % 2 == 0
    move_number = (move_index // 2) + 1
    user_plays_white = teaching_data.get("user_plays_white", True)
    is_user_move = (is_white and user_plays_white) or (not is_white and not user_plays_white)
    side = "White" if is_white else "Black"

    # Try to get rich context from critical positions data
    critical_positions = teaching_data.get("critical_positions", {})
    context = critical_positions.get(str(move_index)) or critical_positions.get(move_index)

    if is_user_move:
        instruction_text = f"Your turn! Play {move}."

        # Enrich with critical position context
        if context:
            key_decision = context.get("key_decision", "")
            best_info = context.get("best_moves", {}).get(move, {})
            idea = best_info.get("idea", "") or best_info.get("why_good", "")
            if key_decision:
                instruction_text = f"{key_decision} Play {move}!"
            if idea:
                instruction_text += f" {idea}"
        elif move_index == 0:
            instruction_text += " This is how the opening begins."
        elif mode == "trap" and move_index == len(moves) - 1:
            instruction_text = f"Now the trap! Play {move}! " + teaching_data.get("explanation", "")
    else:
        instruction_text = f"I'll play {move} as {side}."

        if context:
            key_decision = context.get("key_decision", "")
            if key_decision:
                instruction_text += f" {key_decision}"
        elif move_index == 0:
            instruction_text += " Watch the opening begin."

    return {
        "complete": False,
        "move": move,
        "move_number": move_number,
        "is_white": is_white,
        "side": side,
        "message": instruction_text,
        "remaining": len(moves) - move_index - 1,
        "should_user_play": is_user_move,
        "is_user_move": is_user_move,
    }


async def process_teaching_move(
    db,
    session_id: str,
    user_move: str
) -> Dict:
    """Process a move during teaching mode."""
    import chess

    logger.info(f"[TeachingMove] Processing move: {user_move} for session {session_id}")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    if not session_doc.get("teaching_mode"):
        return {"error": "Not in teaching mode"}

    mode = session_doc["teaching_mode"]
    teaching_data = session_doc.get("teaching_data", {})
    current_index = teaching_data.get("current_move_index", 0)

    if mode == "trap":
        moves = teaching_data.get("trap_moves", [])
    else:
        moves = teaching_data.get("main_line_moves", [])

    if current_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)

    expected_move = moves[current_index]

    if user_move.lower().replace("+", "").replace("#", "") != expected_move.lower().replace("+", "").replace("#", ""):
        # Wrong move - give hint, enriched with mistake data if available
        hint_msg = f"Not quite! The correct move is {expected_move}. Try again!"

        # Check if the wrong move is a known mistake
        critical_positions = teaching_data.get("critical_positions", {})
        context = critical_positions.get(str(current_index)) or critical_positions.get(current_index)
        if context:
            mistake_info = context.get("mistake_moves", {}).get(user_move.replace("+", "").replace("#", ""))
            if mistake_info:
                why_bad = mistake_info.get("why_bad", "")
                learning = mistake_info.get("learning", "")
                if why_bad:
                    hint_msg = f"{why_bad} The correct move is {expected_move}."
                if learning:
                    hint_msg += f" Remember: {learning}"

        return {
            "correct": False,
            "expected_move": expected_move,
            "message": hint_msg,
            "hint": f"Play {expected_move} to continue the lesson.",
            "teaching_fen": teaching_data.get("teaching_fen"),
        }

    # Correct move
    current_fen = teaching_data.get("teaching_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    board = chess.Board(current_fen)

    try:
        chess_move = board.parse_san(expected_move)
        board.push(chess_move)
        new_fen = board.fen()
    except Exception as e:
        logger.error(f"Error applying teaching move: {e}")
        return {"error": f"Move error: {e}"}

    new_index = current_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_data": teaching_data,
            "current_fen": new_fen,
        }}
    )

    if new_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)

    next_instruction = _get_teaching_instruction(teaching_data, mode, new_index)

    is_white = new_index % 2 == 0
    user_plays_white = teaching_data.get("user_plays_white", True)

    if (is_white and not user_plays_white) or (not is_white and user_plays_white):
        return await _auto_play_teaching_move(db, session_id, teaching_data, mode, new_index)

    return {
        "correct": True,
        "message": "Correct! Great job!",
        "next_instruction": next_instruction,
        "teaching_fen": new_fen,
        "progress": f"{new_index}/{len(moves)}",
    }


async def _auto_play_teaching_move(db, session_id: str, teaching_data: Dict, mode: str, move_index: int) -> Dict:
    """Auto-play a teaching move (for opponent's moves in the lesson)."""
    import chess

    logger.info(f"[AutoPlay] Auto-playing move at index {move_index}")

    if mode == "trap":
        moves = teaching_data.get("trap_moves", [])
    else:
        moves = teaching_data.get("main_line_moves", [])

    if move_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)

    move = moves[move_index]

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    current_fen = session_doc.get("current_fen") if session_doc else teaching_data.get("teaching_fen")

    board = chess.Board(current_fen)

    try:
        chess_move = board.parse_san(move)
        board.push(chess_move)
        new_fen = board.fen()
    except Exception as e:
        logger.error(f"Error in auto-play: {e}")
        return {"error": str(e)}

    new_index = move_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_data": teaching_data,
            "current_fen": new_fen,
        }}
    )

    if new_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)

    next_instruction = _get_teaching_instruction(teaching_data, mode, new_index)

    return {
        "correct": True,
        "auto_played": True,
        "move_played": move,
        "new_move_index": new_index,
        "message": f"I played {move}. Now your turn!",
        "next_instruction": next_instruction,
        "teaching_fen": new_fen,
        "progress": f"{new_index}/{len(moves)}",
    }


async def _complete_teaching(db, session_id: str, teaching_data: Dict) -> Dict:
    """Complete a teaching lesson and return to normal game or offer options."""
    from services.opening_mastery import update_user_opening_progress, UserOpeningProgress, MasteryLevel, get_user_opening_progress

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    user_id = session_doc.get("user_id")
    opening_key = session_doc.get("teaching_opening")
    mode = session_doc.get("teaching_mode")

    # Update user's opening progress
    if user_id and opening_key:
        theory = get_opening_theory(opening_key)
        opening_name = theory.get("name", opening_key.replace("_", " ").title()) if theory else opening_key.replace("_", " ").title()

        progress = await get_user_opening_progress(db, user_id, opening_name)

        if not progress:
            progress = UserOpeningProgress(
                user_id=user_id,
                opening_name=opening_name,
                mastery_level=MasteryLevel.INTRODUCED,
                introduced_at=datetime.now(timezone.utc),
                last_practiced_at=datetime.now(timezone.utc),
                times_practiced=1,
                times_applied_in_games=0,
                correct_applications=0,
                traps_learned=[],
                variations_learned=[],
                quiz_scores=[],
                notes="",
            )
        else:
            progress.last_practiced_at = datetime.now(timezone.utc)
            progress.times_practiced += 1
            if progress.mastery_level == MasteryLevel.UNKNOWN:
                progress.mastery_level = MasteryLevel.INTRODUCED
            elif progress.mastery_level == MasteryLevel.INTRODUCED:
                progress.mastery_level = MasteryLevel.LEARNING

        if mode == "trap":
            trap_name = teaching_data.get("trap_name", "")
            if trap_name and trap_name not in progress.traps_learned:
                progress.traps_learned.append(trap_name)
        else:
            var_name = teaching_data.get("variation_name", "")
            if var_name and var_name not in progress.variations_learned:
                progress.variations_learned.append(var_name)

        await update_user_opening_progress(db, progress)

    lesson_name = teaching_data.get("trap_name") or teaching_data.get("variation_name", "opening")

    return {
        "complete": True,
        "message": f"Excellent! You've learned the {lesson_name}!",
        "summary": teaching_data.get("explanation", "You've mastered this opening concept."),
        "key_ideas": teaching_data.get("key_ideas", []),
        "options": [
            {
                "id": "continue_game",
                "label": "Continue the game",
                "description": "Return to your game from where you left off"
            },
            {
                "id": "new_game",
                "label": "Start a new game",
                "description": "Practice what you learned in a fresh game"
            },
            {
                "id": "try_another",
                "label": "Learn something else",
                "description": "Explore more opening lessons"
            }
        ],
        "progress_updated": True,
        "new_mastery_level": "learning",
    }


async def exit_teaching_mode(db, session_id: str, choice: str) -> Dict:
    """Exit teaching mode based on user's choice."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    teaching_data = session_doc.get("teaching_data", {})

    if choice == "continue_game":
        original_fen = teaching_data.get("original_fen")
        original_history = teaching_data.get("original_move_history", [])

        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "teaching_data": {},
                "current_fen": original_fen,
                "move_history": original_history,
            }}
        )

        return {
            "action": "continue_game",
            "restored_fen": original_fen,
            "message": "Game restored! Your turn to continue."
        }

    elif choice == "new_game":
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "status": "completed",
                "termination_reason": "new_game_after_lesson",
            }}
        )

        return {
            "action": "new_game",
            "message": "Starting a fresh game to practice what you learned!"
        }

    else:
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "teaching_data": {},
                "opening_offer_shown": False,
                "detected_opening": None,
            }}
        )

        return {
            "action": "try_another",
            "message": "Ready for another lesson! Make some moves to enter an opening."
        }


async def undo_teaching_move(db, session_id: str) -> Dict:
    """Undo the student's last move inside an active lesson."""
    import chess

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    if not session_doc.get("teaching_mode"):
        return {"error": "Not in teaching mode"}

    teaching_data = session_doc.get("teaching_data", {})
    current_index = teaching_data.get("current_move_index", 0)
    user_plays_white = teaching_data.get("user_plays_white", True)
    mode = session_doc.get("teaching_mode")

    moves = teaching_data.get("trap_moves", []) if mode == "trap" else teaching_data.get("main_line_moves", [])
    if current_index <= 0 or not moves:
        return {"error": "No lesson move available to undo"}

    def is_user_index(index: int) -> bool:
        is_white = index % 2 == 0
        return (is_white and user_plays_white) or (not is_white and not user_plays_white)

    played_user_indices = [index for index in range(current_index) if is_user_index(index)]
    if not played_user_indices:
        return {"error": "No lesson move available to undo"}

    rewind_index = played_user_indices[-1]

    preferred_main_line_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" if mode == "main_line" else None
    candidate_base_fens = []
    for fen in [
        preferred_main_line_fen,
        teaching_data.get("lesson_start_fen"),
        teaching_data.get("original_fen"),
        session_doc.get("current_fen"),
    ]:
        if fen and fen not in candidate_base_fens:
            candidate_base_fens.append(fen)

    board = None
    last_error = None
    for base_fen in candidate_base_fens:
        try:
            candidate_board = chess.Board(base_fen)
            for m in moves[:rewind_index]:
                candidate_board.push_san(m)
            board = candidate_board
            break
        except Exception as exc:
            last_error = exc

    if board is None:
        logger.error(f"Error rebuilding lesson board for undo: {last_error}")
        return {"error": f"Could not undo the lesson move: {last_error}"}

    teaching_data["current_move_index"] = rewind_index
    teaching_data["teaching_fen"] = board.fen()

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "teaching_data": teaching_data,
                "current_fen": board.fen(),
                "action_revision": session_doc.get("action_revision", 0) + 1,
            }
        },
    )

    instruction = _get_teaching_instruction(teaching_data, mode, rewind_index)
    return {
        "success": True,
        "mode": "teaching",
        "undone_move": moves[rewind_index],
        "current_move_index": rewind_index,
        "teaching_fen": board.fen(),
        "instruction": instruction,
        "message": f"Undid your last lesson move: {moves[rewind_index]}",
    }
