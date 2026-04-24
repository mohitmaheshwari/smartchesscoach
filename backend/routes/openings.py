"""
Opening Training Routes
=======================

Handles the Opening Training Lab functionality:
- Opening repertoire management
- Opening lessons
- Interactive practice mode
- Progress tracking
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging
import chess
import random

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Openings"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm = None


def set_db(database):
    """Set the database reference for opening routes"""
    global db
    db = database


def set_llm(llm_func):
    """Set the LLM function reference for opening routes"""
    global call_llm
    call_llm = llm_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class PracticeStartRequest(BaseModel):
    """Request to start interactive practice session"""
    opening_key: str


class PracticeMoveRequest(BaseModel):
    """Request to make a move in practice mode"""
    session_id: str
    move: str  # UCI format (e.g., "e2e4") or SAN format (e.g., "e4")


class ProgressUpdateRequest(BaseModel):
    """Request to update learning progress"""
    main_line_progress: Optional[int] = None
    trap_learned: Optional[str] = None
    practiced: Optional[bool] = False


class OpeningCorrectionRequest(BaseModel):
    source_context: str
    opening_key: str
    opening_name: Optional[str] = None
    variation_name: Optional[str] = None
    trap_name: Optional[str] = None
    correction_type: str
    current_moves: List[str] = []
    current_fen: Optional[str] = None
    corrected_pgn: Optional[str] = None
    corrected_san_text: Optional[str] = None
    corrected_name: Optional[str] = None
    corrected_explanation: Optional[str] = None
    notes: Optional[str] = None


# ==================== ENDPOINTS ====================

@router.get("/openings/repertoire")
async def get_opening_repertoire(user: User = Depends(get_current_user)):
    """
    Get user's opening repertoire - openings they've played + recommendations.
    """
    from services.opening_library_service import get_user_opening_repertoire
    
    repertoire = await get_user_opening_repertoire(db, user.user_id)
    return repertoire


@router.get("/openings/library")
async def get_opening_library():
    """
    Get all openings in the teaching library (includes code + admin overrides).
    """
    from services.opening_feedback_admin_service import list_effective_openings
    
    openings = await list_effective_openings(db)
    # Convert to simpler format for library listing
    library_list = [
        {
            "key": opening["opening_key"],
            "name": opening["opening_name"],
            "has_admin_override": opening.get("updated_at") is not None
        }
        for opening in openings
    ]
    return {"openings": library_list}


@router.get("/openings/match")
async def match_opening_to_library_endpoint(opening_name: str, eco: str = None):
    """
    Match an opening name to our library using intelligent aliasing.
    
    This handles variations like "Giuoco Piano Game" -> "italian-game".
    
    Args:
        opening_name: The opening name from a game (e.g., "Giuoco Piano Game")
        eco: Optional ECO code (e.g., "C54")
    
    Returns:
        library_key: The key in our library, or null if not found
    """
    from services.opening_library_service import match_opening_to_library, get_opening_data
    
    library_key = match_opening_to_library(opening_name, eco)
    
    if library_key:
        opening_data = get_opening_data(library_key)
        return {
            "found": True,
            "library_key": library_key,
            "library_name": opening_data["name"] if opening_data else None
        }
    
    return {
        "found": False,
        "library_key": None,
        "library_name": None
    }


@router.get("/openings/{opening_key}")
async def get_opening_lesson(
    opening_key: str, 
    variation: str = None,
    user: User = Depends(get_current_user)
):
    """
    Get full opening lesson data from the JSON theory tree.
    Optional: ?variation=french_advance to get a specific variation.
    """
    from services.opening_theory_json_service import get_opening_theory, get_available_variations, get_variation_lesson_moves
    from services.verified_opening_traps import get_verified_traps_for_opening
    
    theory = get_opening_theory(opening_key)
    if not theory:
        raise HTTPException(status_code=404, detail="Opening not found in theory database")
    
    variations = get_available_variations(opening_key)
    traps = get_verified_traps_for_opening(opening_key)
    
    # Pick the requested variation or default to first
    target_variation_key = variation or (variations[0]["key"] if variations else None)
    lesson = get_variation_lesson_moves(opening_key, target_variation_key) if target_variation_key else None
    main_line = []
    if lesson:
        for i, move in enumerate(lesson["moves"]):
            main_line.append({"move": move, "explanation": ""})
    
    # Build trap details
    trap_details = []
    for trap in traps:
        trap_details.append({
            "name": trap.name,
            "description": trap.explanation,
            "setup_moves": trap.setup_moves,
            "trap_line": [{"move": m, "explanation": trap.explanation if m == trap.trap_move else ""} for m in trap.full_line],
            "difficulty": trap.difficulty,
            "result_type": "verified_trap",
        })
    
    lesson_data = {
        "name": theory.get("name", opening_key.replace("_", " ").title()),
        "eco": ", ".join(theory.get("eco_prefix", [])),
        "description": theory.get("white_plan", "") + " / " + theory.get("black_plan", ""),
        "color": "black" if "defense" in theory.get("name", "").lower() or "indian" in theory.get("name", "").lower() else "white",
        "first_moves": theory.get("main_line", [])[:5],
        "main_line": main_line,
        "key_ideas": theory.get("common_learnings", []),
        "common_mistakes": [],
        "traps": trap_details,
        "what_if": [],
        "identity": "open" if any(m in theory.get("main_line", []) for m in ["e4", "e5"]) else "closed",
        "variations": [{
            "key": v["key"],
            "name": v["name"],
            "total_moves": v["total_moves"],
        } for v in variations],
        "active_variation": target_variation_key,
    }
    
    # Add user-specific progress data
    progress_doc = await db.user_opening_progress.find_one({
        "user_id": user.user_id,
        "opening_key": opening_key
    })

    user_progress = {}
    if progress_doc:
        user_progress = {
            "main_line_progress": progress_doc.get("main_line_progress", 0),
            "traps_learned": progress_doc.get("traps_learned", []),
            "times_practiced": progress_doc.get("times_practiced", 0),
            "last_practiced": progress_doc.get("last_practiced")
        }

    user_mistakes = await _compute_opening_mistakes(user.user_id, opening_key)

    return {
        "opening": lesson_data,
        "user_progress": user_progress,
        "user_mistakes": user_mistakes,
        "learning_progress": user_progress,
    }


async def _compute_opening_mistakes(user_id: str, opening_key: str) -> List[Dict]:
    """Pull this user's mistakes inside the opening phase for games that
    actually belong to this opening family. Returns up to 5 worst mistakes
    (by cp_loss) in descending order. Facts-only — empty when nothing
    qualifies. No invention, no fallbacks.
    """
    from services.opening_normalizer import (
        normalize_opening,
        canonical_name_for_curriculum_key,
        color_for_curriculum_key,
    )

    canonical = canonical_name_for_curriculum_key(opening_key)
    if not canonical:
        return []

    color_filter = color_for_curriculum_key(opening_key)

    query = {"user_id": user_id, "is_analyzed": True}
    if color_filter:
        query["user_color"] = color_filter

    games = await db.games.find(
        query,
        {"_id": 0, "game_id": 1, "opening": 1, "user_color": 1},
    ).to_list(500)

    matching = [
        g for g in games
        if normalize_opening(g.get("opening")) == canonical
    ]
    if not matching:
        return []

    game_by_id = {g["game_id"]: g for g in matching if g.get("game_id")}
    game_ids = list(game_by_id.keys())
    if not game_ids:
        return []

    # Opening phase = first 10 full moves. move_number is full-move count
    # in python-chess, so 10 covers the typical book depth while keeping
    # us out of the middlegame where mistakes are not opening issues.
    OPENING_MOVE_LIMIT = 10
    # Inaccuracy-or-worse. Below this isn't really a mistake for a 1200.
    MISTAKE_CP_MIN = 50
    # Above this is mate-detection sentinel, not a real cp loss — those
    # are tactical/mate failures, not opening misplays.
    MISTAKE_CP_MAX = 3000

    mistakes: List[Dict] = []
    async for analysis in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    ):  # noqa: E501
        game_id = analysis.get("game_id")
        game = game_by_id.get(game_id)
        if not game:
            continue
        user_color = (game.get("user_color") or "white").lower()
        moves = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        for m in moves:
            move_num = m.get("move_number") or 0
            if move_num <= 0 or move_num > OPENING_MOVE_LIMIT:
                continue
            # Filter to user's moves via FEN active color before the move.
            fen_before = m.get("fen_before") or ""
            if fen_before:
                parts = fen_before.split()
                if len(parts) >= 2:
                    active = "white" if parts[1] == "w" else "black"
                    if active != user_color:
                        continue
            cp_loss = m.get("cp_loss")
            if cp_loss is None:
                continue
            cp_abs = abs(cp_loss)
            if cp_abs < MISTAKE_CP_MIN or cp_abs > MISTAKE_CP_MAX:
                continue
            played = (m.get("move") or "").strip()
            best = (m.get("best_move") or "").strip()
            if not played or not best:
                continue
            # Skip false positives where classifier says "mistake" but the
            # played and best move are the same SAN (punctuation aside).
            def _norm_san(s: str) -> str:
                return s.replace("+", "").replace("#", "").replace("!", "").replace("?", "").lower()
            if _norm_san(played) == _norm_san(best):
                continue
            mistakes.append({
                "game_id": game_id,
                "move_number": move_num,
                "your_move": played,
                "your_move_uci": m.get("move_uci"),
                "best_move": best,
                "best_move_uci": m.get("best_move_uci"),
                "cp_loss": cp_abs,
                "fen_before": fen_before,
            })

    mistakes.sort(key=lambda x: -x["cp_loss"])
    return mistakes[:5]


@router.post("/openings/corrections")
async def submit_opening_correction(
    correction: OpeningCorrectionRequest,
    user: User = Depends(get_current_user)
):
    """Save an opening/trap correction and apply it immediately as a live override."""
    from services.opening_correction_service import save_opening_correction

    if not correction.corrected_pgn and not correction.corrected_san_text and not correction.corrected_name and not correction.corrected_explanation:
        raise HTTPException(status_code=400, detail="Please provide corrected PGN, SAN moves, name, or explanation")

    saved = await save_opening_correction(db, user.user_id, correction.model_dump())
    return {
        "success": True,
        "correction": saved,
        "message": "Opening correction saved and applied immediately."
    }


@router.get("/openings/{opening_key}/corrections")
async def get_opening_corrections_endpoint(
    opening_key: str,
    user: User = Depends(get_current_user)
):
    from services.opening_correction_service import get_opening_corrections

    corrections = await get_opening_corrections(db, opening_key)
    return {
        "opening_key": opening_key,
        "corrections": corrections,
        "count": len(corrections)
    }


@router.post("/openings/{opening_key}/progress")
async def update_opening_progress(
    opening_key: str,
    progress_data: ProgressUpdateRequest,
    user: User = Depends(get_current_user)
):
    """
    Update user's learning progress on an opening.
    """
    from services.opening_library_service import update_learning_progress
    
    result = await update_learning_progress(
        db,
        user.user_id,
        opening_key,
        main_line_progress=progress_data.main_line_progress,
        trap_learned=progress_data.trap_learned,
        practiced=progress_data.practiced
    )
    
    return result


# ==================== INTERACTIVE PRACTICE MODE ====================

@router.post("/openings/{opening_key}/practice/start")
async def start_practice_session(
    opening_key: str,
    user: User = Depends(get_current_user)
):
    """
    Start an interactive practice session for an opening.
    
    The coach plays the opponent's moves and provides Socratic feedback
    when the user makes mistakes.
    """
    from services.opening_library_service import get_opening_data
    import uuid
    from datetime import datetime, timezone
    
    opening = get_opening_data(opening_key)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")
    
    session_id = str(uuid.uuid4())
    
    # Initialize the board
    board = chess.Board()
    
    # Determine who moves first
    user_color = opening["color"]  # The color the user will play
    
    # Create session
    session = {
        "session_id": session_id,
        "user_id": user.user_id,
        "opening_key": opening_key,
        "opening_name": opening["name"],
        "user_color": user_color,
        "fen": board.fen(),
        "move_history": [],
        "main_line": opening["main_line"],
        "current_main_line_index": 0,
        "status": "active",
        "mistakes_made": [],
        "created_at": datetime.now(timezone.utc)
    }
    
    # If user plays black, play white's first move automatically
    coach_move = None
    coach_explanation = None
    
    if user_color == "black" and len(opening["main_line"]) > 0:
        first_move_data = opening["main_line"][0]
        move = board.push_san(first_move_data["move"])
        session["fen"] = board.fen()
        session["move_history"].append({
            "move": first_move_data["move"],
            "uci": move.uci(),
            "by": "coach"
        })
        session["current_main_line_index"] = 1
        coach_move = first_move_data["move"]
        coach_explanation = first_move_data["explanation"]
    
    # Store session
    await db.opening_practice_sessions.insert_one(session)
    
    # Get expected move for user
    expected_idx = session["current_main_line_index"]
    expected_explanation = None
    if expected_idx < len(opening["main_line"]):
        opening["main_line"][expected_idx]["move"]
        expected_explanation = opening["main_line"][expected_idx]["explanation"]
    
    return {
        "session_id": session_id,
        "opening_name": opening["name"],
        "user_color": user_color,
        "fen": session["fen"],
        "coach_move": coach_move,
        "coach_explanation": coach_explanation,
        "hint": "Your move. Think about what move controls the center or develops a piece." if not expected_explanation else None,
        "move_number": (expected_idx // 2) + 1,
        "is_user_turn": True
    }


@router.post("/openings/practice/move")
async def make_practice_move(
    request: PracticeMoveRequest,
    user: User = Depends(get_current_user)
):
    """
    Make a move in the practice session.
    
    Returns Socratic feedback if the move is incorrect,
    or plays the opponent's response if correct.
    """
    
    # Get session
    session = await db.opening_practice_sessions.find_one({
        "session_id": request.session_id,
        "user_id": user.user_id,
        "status": "active"
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or already completed")
    
    # Set up board
    board = chess.Board(session["fen"])
    main_line = session["main_line"]
    current_idx = session["current_main_line_index"]
    
    # Try to parse user's move
    try:
        # Try UCI first
        if len(request.move) >= 4:
            try:
                move = chess.Move.from_uci(request.move)
                if move in board.legal_moves:
                    user_san = board.san(move)
                else:
                    move = board.parse_san(request.move)
                    user_san = request.move
            except:
                move = board.parse_san(request.move)
                user_san = request.move
        else:
            move = board.parse_san(request.move)
            user_san = request.move
    except Exception:
        return {
            "valid": False,
            "error": f"Invalid move: {request.move}",
            "fen": session["fen"]
        }
    
    # Check if it's the expected move from main line
    expected_move_data = main_line[current_idx] if current_idx < len(main_line) else None
    
    if not expected_move_data:
        # Practice complete
        return {
            "valid": True,
            "complete": True,
            "message": "You've completed the main line! Great job!",
            "fen": session["fen"]
        }
    
    expected_san = expected_move_data["move"]
    is_correct = user_san.replace("+", "").replace("#", "") == expected_san.replace("+", "").replace("#", "")
    
    if is_correct:
        # Correct move!
        board.push(move)
        
        # Update session
        new_history = session["move_history"] + [{
            "move": user_san,
            "uci": move.uci(),
            "by": "user"
        }]
        
        next_idx = current_idx + 1
        
        # Check if practice is complete
        if next_idx >= len(main_line):
            await db.opening_practice_sessions.update_one(
                {"session_id": request.session_id},
                {"$set": {
                    "fen": board.fen(),
                    "move_history": new_history,
                    "current_main_line_index": next_idx,
                    "status": "completed"
                }}
            )
            
            return {
                "valid": True,
                "correct": True,
                "complete": True,
                "fen": board.fen(),
                "message": "Excellent! You've mastered this opening line!",
                "explanation": expected_move_data["explanation"]
            }
        
        # Play coach's response
        coach_move_data = main_line[next_idx]
        coach_move = board.push_san(coach_move_data["move"])
        
        new_history.append({
            "move": coach_move_data["move"],
            "uci": coach_move.uci(),
            "by": "coach"
        })
        
        final_idx = next_idx + 1
        
        # Update session
        await db.opening_practice_sessions.update_one(
            {"session_id": request.session_id},
            {"$set": {
                "fen": board.fen(),
                "move_history": new_history,
                "current_main_line_index": final_idx
            }}
        )
        
        # Check if complete after coach move
        if final_idx >= len(main_line):
            await db.opening_practice_sessions.update_one(
                {"session_id": request.session_id},
                {"$set": {"status": "completed"}}
            )
            
            return {
                "valid": True,
                "correct": True,
                "complete": True,
                "fen": board.fen(),
                "your_move_explanation": expected_move_data["explanation"],
                "coach_move": coach_move_data["move"],
                "coach_explanation": coach_move_data["explanation"],
                "message": "Perfect! You've completed the opening!"
            }
        
        # Get hint for next move
        main_line[final_idx]
        
        return {
            "valid": True,
            "correct": True,
            "fen": board.fen(),
            "your_move_explanation": expected_move_data["explanation"],
            "coach_move": coach_move_data["move"],
            "coach_explanation": coach_move_data["explanation"],
            "move_number": (final_idx // 2) + 1,
            "is_user_turn": True,
            # Add dynamic coaching if available
            "dynamic_coaching": await _get_dynamic_coaching_for_practice(
                board=board,
                move_history=new_history,
                user_id=user.user_id,
                opening_name=session["opening_name"]
            )
        }
    
    else:
        # Incorrect move - provide Socratic feedback
        # Don't update the board, give the user another chance
        
        # Record the mistake
        mistake = {
            "expected": expected_san,
            "played": user_san,
            "move_number": current_idx
        }
        
        await db.opening_practice_sessions.update_one(
            {"session_id": request.session_id},
            {"$push": {"mistakes_made": mistake}}
        )
        
        # Generate Socratic feedback
        socratic_feedback = await generate_socratic_feedback(
            expected_san,
            user_san,
            expected_move_data["explanation"],
            board,
            session["opening_name"]
        )
        
        return {
            "valid": True,
            "correct": False,
            "fen": session["fen"],  # Return original FEN, move not made
            "feedback": socratic_feedback,
            "hint": expected_move_data["explanation"],
            "try_again": True
        }


@router.get("/openings/practice/{session_id}/hint")
async def get_practice_hint(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get a hint for the current position in practice mode.
    """
    session = await db.opening_practice_sessions.find_one({
        "session_id": session_id,
        "user_id": user.user_id,
        "status": "active"
    })
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    main_line = session["main_line"]
    current_idx = session["current_main_line_index"]
    
    if current_idx >= len(main_line):
        return {"hint": "You've completed the main line!"}
    
    expected_move = main_line[current_idx]
    
    # Provide progressively more specific hints based on number of mistakes
    mistakes_count = len([m for m in session.get("mistakes_made", []) if m.get("move_number") == current_idx])
    
    if mistakes_count == 0:
        # Generic hint
        hint = f"Think about: {expected_move['explanation'][:50]}..."
    elif mistakes_count == 1:
        # More specific hint
        move_san = expected_move["move"]
        piece = move_san[0] if move_san[0].isupper() else "Pawn"
        if piece == "N":
            piece = "Knight"
        elif piece == "B":
            piece = "Bishop"
        elif piece == "R":
            piece = "Rook"
        elif piece == "Q":
            piece = "Queen"
        elif piece == "K":
            piece = "King"
        elif piece == "O":
            piece = "Castling"
        hint = f"Consider moving your {piece}. {expected_move['explanation']}"
    else:
        # Give the answer
        hint = f"The correct move is {expected_move['move']}. {expected_move['explanation']}"
    
    return {
        "hint": hint,
        "hint_level": min(mistakes_count + 1, 3)
    }


@router.post("/openings/practice/{session_id}/resign")
async def resign_practice_session(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    End a practice session early.
    """
    result = await db.opening_practice_sessions.update_one(
        {
            "session_id": session_id,
            "user_id": user.user_id,
            "status": "active"
        },
        {"$set": {"status": "resigned"}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Session not found or already completed")
    
    return {"message": "Practice session ended"}


async def _get_dynamic_coaching_for_practice(
    board: chess.Board,
    move_history: list,
    user_id: str,
    opening_name: str
) -> dict:
    """
    Generate dynamic coaching suggestions for practice mode.
    
    Connects the Behavioral Coaching Layer and Active Teaching Engine
    to provide personalized feedback during opening practice.
    """
    try:
        global db
        
        # 1. Try to get behavioral coaching
        behavioral_feedback = None
        try:
            from services.behavioral_coaching_layer import get_behavioral_coaching_feedback
            behavioral_feedback = await get_behavioral_coaching_feedback(
                db=db,
                user_id=user_id,
                current_position=board.fen(),
                move_history=[m.get("move", "") for m in move_history],
                context={
                    "mode": "opening_practice",
                    "opening_name": opening_name
                }
            )
        except Exception as e:
            logger.debug(f"Behavioral coaching not available: {e}")
        
        # 2. Try to get position analysis
        position_insights = None
        try:
            from services.intelligent_position_coach import analyze_position_and_suggest
            position_insights = await analyze_position_and_suggest(
                board=board,
                move_history=[m.get("move", "") for m in move_history],
                user_color="white" if len(move_history) % 2 == 0 else "black",
                user_id=user_id,
                db=db
            )
        except Exception as e:
            logger.debug(f"Position insights not available: {e}")
        
        # Build combined coaching response
        coaching = {}
        
        if behavioral_feedback and behavioral_feedback.get("feedback"):
            coaching["behavioral_tip"] = behavioral_feedback["feedback"]
            coaching["behavioral_type"] = behavioral_feedback.get("pattern_type")
        
        if position_insights:
            coaching["structure_name"] = position_insights.get("structure_name")
            coaching["game_phase"] = position_insights.get("game_phase")
            coaching["main_idea"] = position_insights.get("main_idea")
            coaching["key_characteristics"] = position_insights.get("key_characteristics", [])[:2]
        
        return coaching if coaching else None
        
    except Exception as e:
        logger.warning(f"Dynamic coaching generation failed: {e}")
        return None


async def generate_socratic_feedback(
    expected_move: str,
    played_move: str,
    explanation: str,
    board: chess.Board,
    opening_name: str
) -> Dict:
    """
    Generate Socratic feedback for an incorrect move.
    
    Instead of just saying "wrong", ask questions that guide
    the student to understand why the expected move is better.
    """
    global call_llm
    
    # Build context
    fen = board.fen()
    
    # Try to use LLM for personalized Socratic feedback
    if call_llm:
        try:
            prompt = f"""You are a friendly chess coach teaching the {opening_name}.

The student is at this position (FEN): {fen}

They played: {played_move}
The correct move is: {expected_move}
Why the correct move is good: {explanation}

Generate a SHORT Socratic response (2-3 sentences max) that:
1. Acknowledges their move without being harsh
2. Asks ONE guiding question that helps them discover the right move
3. Keep it simple and encouraging

Example good responses:
- "Interesting idea! But what square is really weak in Black's position right now? What piece could target it?"
- "That develops a piece, good instinct! But look at the center - is there a way to control it more directly?"

Don't reveal the answer directly. Just guide them to think.
Be warm and use simple language.
"""
            response = await call_llm(prompt)
            if response:
                return {
                    "type": "socratic",
                    "message": response,
                    "encouragement": True
                }
        except Exception as e:
            logger.error(f"Error generating Socratic feedback: {e}")
    
    # Fallback to template-based feedback
    questions = [
        f"Good try! But think about this - {explanation.split('.')[0]}. What move accomplishes that?",
        f"That's a reasonable idea. But in the {opening_name}, we want to {explanation.split('.')[0].lower()}. Can you find that move?",
        f"Not quite! Ask yourself: what's the key idea in this opening? {explanation}",
        f"Think about what square or piece we're targeting here. {explanation.split('.')[0]}.",
    ]
    
    return {
        "type": "socratic",
        "message": random.choice(questions),
        "encouragement": True
    }


# ==================== TRAP LIBRARY ENDPOINTS ====================

@router.get("/traps/statistics")
async def get_trap_statistics():
    """
    Get statistics about the trap library.
    """
    from services.trap_library import get_all_trap_statistics
    return get_all_trap_statistics()


@router.get("/traps/checkmates")
async def get_checkmate_traps():
    """
    Get all traps that end in checkmate.
    """
    from services.trap_library import get_checkmate_traps
    return {"traps": get_checkmate_traps()}


@router.get("/traps/difficulty/{difficulty}")
async def get_traps_by_difficulty_level(difficulty: str):
    """
    Get traps filtered by difficulty level.
    
    Args:
        difficulty: "beginner", "intermediate", or "advanced"
    """
    from services.trap_library import get_traps_by_difficulty
    
    if difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(status_code=400, detail="Invalid difficulty. Use: beginner, intermediate, advanced")
    
    return {"traps": get_traps_by_difficulty(difficulty)}


@router.post("/traps/suggest")
async def suggest_trap_for_position(moves: List[str]):
    """
    Check if a trap is available from the current position.
    
    Args:
        moves: List of moves played so far (SAN format)
    
    Returns:
        Trap suggestion if available, or null
    """
    from services.trap_library import get_trap_for_position
    
    trap_data = get_trap_for_position(moves)
    
    if trap_data:
        return {
            "trap_available": True,
            "trap": {
                "name": trap_data.get("name"),
                "description": trap_data.get("description"),
                "setup_remaining": trap_data.get("setup_remaining", []),
                "trap_line": trap_data.get("trap_line", []),
                "moves_until_trap": trap_data.get("moves_until_trap", 0),
                "result_type": trap_data.get("result_type"),
                "difficulty": trap_data.get("difficulty"),
                "opening_key": trap_data.get("opening_key")
            }
        }
    
    return {"trap_available": False, "trap": None}


@router.post("/traps/analyze-game")
async def analyze_game_traps(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Analyze a specific game for trap patterns.
    
    Returns:
    - traps_executed: Traps successfully played by the user
    - traps_fallen_into: Traps the user fell into
    - trap_opportunities_missed: Traps that could have been played
    """
    from services.trap_library import analyze_game_for_traps
    
    # Get game data
    game = await db.games.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get analysis for moves
    analysis = await db.game_analyses.find_one({
        "game_id": game_id,
        "user_id": user.user_id
    }, {"_id": 0})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")
    
    # Extract moves
    sf = analysis.get("stockfish_analysis", {})
    move_evaluations = sf.get("move_evaluations", [])
    game_moves = [m.get("move", "") for m in move_evaluations if m.get("move")]
    
    user_color = game.get("user_color", "white")
    
    trap_analysis = analyze_game_for_traps(game_moves, user_color)
    
    return {
        "game_id": game_id,
        "user_color": user_color,
        "opening": game.get("opening_name") or game.get("opening"),
        **trap_analysis
    }

