"""
Opening Teaching Integration for Play with Coach
=================================================

This module integrates the Opening Mastery System with the live coaching game.

Flow:
1. After each move, check if we're in a known opening
2. If opening detected AND user hasn't seen the offer yet, send teaching offer
3. User can choose: Learn trap / Learn main line / Just play
4. If user chooses to learn, enter teaching mode
5. In teaching mode, guide user through moves one by one
6. After teaching complete, continue normal game or offer to restart
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

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
    
    Returns:
        Dict with teaching offer if applicable, None otherwise
    """
    from services.opening_mastery import (
        detect_opening_from_moves,
        OpeningTeacher,
        get_user_opening_progress,
        OPENING_DATABASE
    )
    
    logger.info(f"Checking opening for session {session_id}, move_history length: {len(move_history)}")
    
    # Get session to check if we've already offered teaching
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        logger.info("No session found")
        return None
    
    # Skip if already in teaching mode or offer was shown
    if session_doc.get("teaching_mode"):
        logger.info("Already in teaching mode, skipping")
        return None
    if session_doc.get("opening_offer_shown"):
        logger.info("Opening offer already shown, skipping")
        return None
    
    # Only check in first 12 moves (opening phase)
    if len(move_history) > 24:  # 12 moves per side
        logger.info("Past opening phase, skipping")
        return None
    
    # Need at least 2 moves to detect an opening
    if len(move_history) < 2:
        logger.info("Not enough moves yet")
        return None
    
    # Get moves as SAN strings
    moves = [m.get("move", "") for m in move_history if m.get("move")]
    logger.info(f"Checking moves for opening: {moves}")
    
    # Detect opening
    opening_info = detect_opening_from_moves(moves)
    if not opening_info:
        logger.info("No opening detected")
        return None
    
    logger.info(f"Opening detected: {opening_info['opening_name']}")
    
    opening_key = opening_info["opening_key"]
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        logger.info(f"Opening {opening_key} not in database")
        return None
    
    # Check user's progress with this opening
    progress = await get_user_opening_progress(db, user_id, opening.name)
    
    # Build teaching offer
    teacher = OpeningTeacher(opening_key, progress)
    intro = teacher.get_introduction()
    
    # Build interactive options
    options = []
    
    # Get trap names if available
    all_traps = []
    for var in opening.variations:
        all_traps.extend(var.traps)
    
    if all_traps:
        trap_name = all_traps[0].name
        options.append({
            "id": "learn_trap",
            "label": f"🎯 Learn the {trap_name}",
            "description": "Interactive trap lesson - I'll show you the moves"
        })
    
    options.append({
        "id": "learn_main_line",
        "label": "📚 Learn the main line",
        "description": "Step-by-step opening theory"
    })
    
    options.append({
        "id": "just_play",
        "label": "⚔️ Just play - I'll figure it out",
        "description": "Continue the game without lesson"
    })
    
    # Mark that we've shown the offer
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
        "opening_name": opening.name,
        "message": intro["message"],
        "description": opening.description,
        "character": opening.character,
        "options": options,
        "has_learned_before": intro.get("has_learned_before", False),
        "trap_available": len(all_traps) > 0,
        "trap_name": all_traps[0].name if all_traps else None
    }


async def start_opening_lesson(
    db,
    session_id: str,
    user_id: str,
    lesson_type: str  # "learn_trap" or "learn_main_line"
) -> Dict:
    """
    Start an interactive opening lesson.
    
    This pauses the normal game and enters teaching mode.
    
    Args:
        db: Database
        session_id: Current game session
        user_id: User ID
        lesson_type: What to teach
    
    Returns:
        Dict with first teaching instruction
    """
    from services.opening_mastery import (
        OpeningTeacher,
        get_user_opening_progress,
        OPENING_DATABASE
    )
    import chess
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}
    
    # Check for opening - either detected during play OR proactively set at game start
    opening_key = session_doc.get("detected_opening") or session_doc.get("opening_to_teach")
    if not opening_key:
        return {"error": "No opening detected"}
    
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return {"error": "Opening not found"}
    
    # Get user's color - critical for knowing which moves are user's vs coach's
    user_color = session_doc.get("user_color", "white")
    user_plays_white = user_color == "white"
    
    # Get user's progress
    progress = await get_user_opening_progress(db, user_id, opening.name)
    teacher = OpeningTeacher(opening_key, progress)
    
    if lesson_type == "learn_trap":
        result = teacher.start_trap_teaching()
        mode = "trap"
        
        # For trap teaching, use suggested_trap if available, else pick first trap
        suggested_trap = session_doc.get("suggested_trap")
        trap = None
        
        if suggested_trap and suggested_trap.get("name"):
            # Find the trap by name from the opening
            trap_name = suggested_trap.get("name")
            for var in opening.variations:
                for t in var.traps:
                    if t.name == trap_name:
                        trap = t
                        break
                if trap:
                    break
        
        # Fallback to first trap if suggested not found
        if not trap:
            all_traps = []
            for var in opening.variations:
                all_traps.extend(var.traps)
            
            if not all_traps:
                return {"error": "No traps available"}
            
            trap = all_traps[0]
        
        # Get current position and move history
        current_fen = session_doc.get("current_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        move_history = session_doc.get("move_history", [])
        moves_played = len(move_history)
        
        # Figure out where we are in the trap sequence
        # Compare moves played to trap moves to find current index
        trap_moves = trap.moves
        current_move_index = 0
        on_trap_line = True
        
        # Match moves played to trap moves
        for i, trap_move in enumerate(trap_moves):
            if i < moves_played:
                # Move history uses 'move' key, not 'san'
                played_move = move_history[i].get("move", "") or move_history[i].get("san", "")
                # Normalize moves for comparison (remove check/mate symbols)
                played_normalized = played_move.replace("+", "").replace("#", "").strip()
                trap_normalized = trap_move.replace("+", "").replace("#", "").strip()
                if played_normalized == trap_normalized:
                    current_move_index = i + 1
                else:
                    # Moves diverged from trap line
                    on_trap_line = False
                    logger.info(f"Moves diverged at index {i}: played={played_normalized}, expected={trap_normalized}")
                    break
            else:
                break
        
        # If moves don't match trap line at all (even first move), this trap doesn't apply
        if not on_trap_line and current_move_index == 0:
            return {
                "error": f"This trap requires starting with {trap_moves[0]}, but you played {move_history[0].get('move', '?')}. Start a new game to learn this trap, or continue playing!"
            }
        
        logger.info(f"Starting trap lesson at move index {current_move_index} (moves played: {moves_played}, on_trap_line: {on_trap_line})")
        
        # Build teaching state - continue from current position, not reset
        teaching_data = {
            "trap_name": trap.name,
            "trap_moves": trap.moves,
            "current_move_index": current_move_index,
            "explanation": trap.explanation,
            "refutation": trap.refutation,
            "victim_color": trap.victim_color,
            "user_plays_white": user_plays_white,
            "teaching_fen": current_fen,  # Keep current position!
            "lesson_start_fen": current_fen,
            "original_fen": current_fen,
            "original_move_history": move_history
        }
        
    else:  # learn_main_line
        teacher.start_main_line_teaching()  # Initialize teacher state
        mode = "main_line"
        
        var = opening.variations[0] if opening.variations else None
        if not var:
            return {"error": "No variations available"}
        
        teaching_data = {
            "variation_name": var.name,
            "main_line_moves": var.moves,
            "current_move_index": 0,
            "key_ideas": var.key_ideas,
            "plans_white": var.plans_for_white,
            "plans_black": var.plans_for_black,
            "user_plays_white": user_plays_white,  # Critical: know which moves are user's
            "teaching_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "lesson_start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "original_fen": session_doc.get("current_fen"),
            "original_move_history": session_doc.get("move_history", [])
        }
    
    # Update session to teaching mode - DON'T reset FEN, keep current position
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_mode": mode,
            "teaching_opening": opening_key,
            "teaching_data": teaching_data
            # Note: current_fen is NOT reset - we continue from current position
        }}
    )
    
    # Get teaching instruction for current position
    current_idx = teaching_data.get("current_move_index", 0)
    first_instruction = _get_teaching_instruction(teaching_data, mode, current_idx)
    
    result = {
        "success": True,
        "mode": mode,
        "opening_name": opening.name,
        "lesson_name": teaching_data.get("trap_name") or teaching_data.get("variation_name"),
        "total_moves": len(teaching_data.get("trap_moves", teaching_data.get("main_line_moves", []))),
        "current_move_index": current_idx,
        "instruction": first_instruction,
        "teaching_fen": teaching_data["teaching_fen"],
        "key_ideas": teaching_data.get("key_ideas", []),
        "user_plays_white": user_plays_white
    }
    
    # If current move is coach's move, auto-play it
    if not first_instruction.get("is_user_move") and not first_instruction.get("complete"):
        # Auto-play the coach's move
        auto_result = await _auto_play_teaching_move(db, session_id, teaching_data, mode, current_idx)
        if auto_result.get("auto_played"):
            result["auto_played_move"] = auto_result.get("move_played")
            result["instruction"] = auto_result.get("next_instruction")
            result["teaching_fen"] = auto_result.get("teaching_fen")
            result["current_move_index"] = auto_result.get("new_move_index", current_idx + 1)
    
    return result


def _get_teaching_instruction(teaching_data: Dict, mode: str, move_index: int) -> Dict:
    """Get teaching instruction for current move."""
    if mode == "trap":
        moves = teaching_data.get("trap_moves", [])
    else:
        moves = teaching_data.get("main_line_moves", [])
    
    if move_index >= len(moves):
        return {
            "complete": True,
            "message": "Excellent! You've completed the lesson!",
            "summary": teaching_data.get("explanation", "")
        }
    
    move = moves[move_index]
    is_white = move_index % 2 == 0
    move_number = (move_index // 2) + 1
    user_plays_white = teaching_data.get("user_plays_white", True)
    
    # Determine if this move is by the user or the coach
    is_user_move = (is_white and user_plays_white) or (not is_white and not user_plays_white)
    
    # Determine who plays this move and provide appropriate instruction
    if is_white:
        side = "White"
    else:
        side = "Black"
    
    if is_user_move:
        # User's turn - tell them to play
        instruction_text = f"Your turn! Play {move}."
        if move_index == 0:
            instruction_text += " This is how the opening begins."
        elif mode == "trap" and move_index == len(moves) - 1:
            instruction_text = f"Now the trap! Play {move}! " + teaching_data.get("explanation", "")
    else:
        # Coach's turn - this move will be auto-played
        instruction_text = f"I'll play {move} as {side}."
        if move_index == 0:
            instruction_text += " Watch the opening begin."
    
    return {
        "complete": False,
        "move": move,
        "move_number": move_number,
        "is_white": is_white,
        "side": side,
        "message": instruction_text,
        "remaining": len(moves) - move_index - 1,
        "should_user_play": is_user_move,  # True only if it's user's turn
        "is_user_move": is_user_move  # Clear flag for frontend
    }


async def process_teaching_move(
    db,
    session_id: str,
    user_move: str
) -> Dict:
    """
    Process a move during teaching mode.
    
    Checks if user played the correct move, provides feedback,
    and advances to the next teaching step.
    """
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
    
    # Check if user played the correct move (case-insensitive)
    if user_move.lower().replace("+", "").replace("#", "") != expected_move.lower().replace("+", "").replace("#", ""):
        # Wrong move - give hint
        return {
            "correct": False,
            "expected_move": expected_move,
            "message": f"Not quite! The correct move is {expected_move}. Try again!",
            "hint": f"Play {expected_move} to continue the lesson.",
            "teaching_fen": teaching_data.get("teaching_fen")
        }
    
    # Correct move! Update board and advance
    current_fen = teaching_data.get("teaching_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    board = chess.Board(current_fen)
    
    try:
        chess_move = board.parse_san(expected_move)
        board.push(chess_move)
        new_fen = board.fen()
    except Exception as e:
        logger.error(f"Error applying teaching move: {e}")
        return {"error": f"Move error: {e}"}
    
    # Update teaching state
    new_index = current_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_data": teaching_data,
            "current_fen": new_fen
        }}
    )
    
    # Check if lesson complete
    if new_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)
    
    # Get next instruction
    next_instruction = _get_teaching_instruction(teaching_data, mode, new_index)
    
    # If it's the opponent's move in the lesson, auto-play it
    is_white = new_index % 2 == 0
    user_plays_white = teaching_data.get("user_plays_white", True)  # Assume white for now
    
    # Auto-play opponent moves
    if (is_white and not user_plays_white) or (not is_white and user_plays_white):
        # This is opponent's move - auto-play it
        logger.info(f"[TeachingMove] Next move at index {new_index} is opponent's - auto-playing")
        return await _auto_play_teaching_move(db, session_id, teaching_data, mode, new_index)
    
    logger.info(f"[TeachingMove] User's turn next at index {new_index}, returning instruction")
    return {
        "correct": True,
        "message": "Correct! Great job!",
        "next_instruction": next_instruction,
        "teaching_fen": new_fen,
        "progress": f"{new_index}/{len(moves)}"
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
    
    # Get current FEN from database (most up-to-date)
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
    
    # Update teaching state
    new_index = move_index + 1
    teaching_data["current_move_index"] = new_index
    teaching_data["teaching_fen"] = new_fen
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "teaching_data": teaching_data,
            "current_fen": new_fen
        }}
    )
    
    # Check if complete
    if new_index >= len(moves):
        return await _complete_teaching(db, session_id, teaching_data)
    
    # Get next instruction for user
    next_instruction = _get_teaching_instruction(teaching_data, mode, new_index)
    
    logger.info(f"[AutoPlay] Auto-played {move}, new FEN: {new_fen[:30]}..., next instruction: {next_instruction.get('message', '')[:50]}")
    
    return {
        "correct": True,  # Mark as correct so frontend processes it
        "auto_played": True,
        "move_played": move,
        "new_move_index": new_index,
        "message": f"I played {move}. Now your turn!",
        "next_instruction": next_instruction,
        "teaching_fen": new_fen,
        "progress": f"{new_index}/{len(moves)}"
    }


async def _complete_teaching(db, session_id: str, teaching_data: Dict) -> Dict:
    """Complete a teaching lesson and return to normal game or offer options."""
    from services.opening_mastery import update_user_opening_progress, UserOpeningProgress, MasteryLevel
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}
    
    user_id = session_doc.get("user_id")
    opening_key = session_doc.get("teaching_opening")
    mode = session_doc.get("teaching_mode")
    
    # Update user's opening progress
    if user_id and opening_key:
        from services.opening_mastery import OPENING_DATABASE, get_user_opening_progress
        
        opening = OPENING_DATABASE.get(opening_key)
        if opening:
            progress = await get_user_opening_progress(db, user_id, opening.name)
            
            if not progress:
                # Create new progress
                progress = UserOpeningProgress(
                    user_id=user_id,
                    opening_name=opening.name,
                    mastery_level=MasteryLevel.INTRODUCED,
                    introduced_at=datetime.now(timezone.utc),
                    last_practiced_at=datetime.now(timezone.utc),
                    times_practiced=1,
                    times_applied_in_games=0,
                    correct_applications=0,
                    traps_learned=[],
                    variations_learned=[],
                    quiz_scores=[],
                    notes=""
                )
            else:
                progress.last_practiced_at = datetime.now(timezone.utc)
                progress.times_practiced += 1
                if progress.mastery_level == MasteryLevel.UNKNOWN:
                    progress.mastery_level = MasteryLevel.INTRODUCED
                elif progress.mastery_level == MasteryLevel.INTRODUCED:
                    progress.mastery_level = MasteryLevel.LEARNING
            
            # Record what was learned
            if mode == "trap":
                trap_name = teaching_data.get("trap_name", "")
                if trap_name and trap_name not in progress.traps_learned:
                    progress.traps_learned.append(trap_name)
            else:
                var_name = teaching_data.get("variation_name", "")
                if var_name and var_name not in progress.variations_learned:
                    progress.variations_learned.append(var_name)
            
            await update_user_opening_progress(db, progress)
    
    # Build completion response with options
    lesson_name = teaching_data.get("trap_name") or teaching_data.get("variation_name", "opening")
    
    return {
        "complete": True,
        "message": f"🎉 Excellent! You've learned the {lesson_name}!",
        "summary": teaching_data.get("explanation", "You've mastered this opening concept."),
        "key_ideas": teaching_data.get("key_ideas", []),
        "options": [
            {
                "id": "continue_game",
                "label": "⚔️ Continue the game",
                "description": "Return to your game from where you left off"
            },
            {
                "id": "new_game",
                "label": "🔄 Start a new game",
                "description": "Practice what you learned in a fresh game"
            },
            {
                "id": "try_another",
                "label": "📚 Learn something else",
                "description": "Explore more opening lessons"
            }
        ],
        "progress_updated": True,
        "new_mastery_level": "learning"
    }


async def exit_teaching_mode(db, session_id: str, choice: str) -> Dict:
    """
    Exit teaching mode based on user's choice.
    
    Args:
        choice: "continue_game" | "new_game" | "try_another"
    """
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}
    
    teaching_data = session_doc.get("teaching_data", {})
    
    if choice == "continue_game":
        # Restore original game state
        original_fen = teaching_data.get("original_fen")
        original_history = teaching_data.get("original_move_history", [])
        
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "teaching_data": {},
                "current_fen": original_fen,
                "move_history": original_history
            }}
        )
        
        return {
            "action": "continue_game",
            "restored_fen": original_fen,
            "message": "Game restored! Your turn to continue."
        }
    
    elif choice == "new_game":
        # Mark current session as ended, signal frontend to start new
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "status": "completed",
                "termination_reason": "new_game_after_lesson"
            }}
        )
        
        return {
            "action": "new_game",
            "message": "Starting a fresh game to practice what you learned!"
        }
    
    else:  # try_another
        # Stay in teaching mode but reset
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "teaching_mode": None,
                "teaching_data": {},
                "opening_offer_shown": False,  # Allow new offers
                "detected_opening": None
            }}
        )
        
        return {
            "action": "try_another",
            "message": "Ready for another lesson! Make some moves to enter an opening."
        }


async def undo_teaching_move(db, session_id: str) -> Dict:
    """Undo the student's last move inside an active lesson.

    If the lesson auto-played the coach/opponent reply after the student's move,
    both plies are rewound so the same prompt can be attempted again.
    """
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

    candidate_base_fens = []
    for fen in [
        teaching_data.get("lesson_start_fen"),
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" if mode == "main_line" else None,
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
            for move in moves[:rewind_index]:
                candidate_board.push_san(move)
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
        "message": f"Undid your last lesson move: {moves[rewind_index]}"
    }
