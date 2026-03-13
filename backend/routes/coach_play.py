"""
Coach Play Routes
=================

Handles the "Play with Coach" feature including:
- Starting/ending coach play sessions
- Making moves and getting coach responses
- Real-time feedback and evaluation
- Endgame lessons
- Opening teaching integration

NOTE: This is the first phase of refactoring. The main routes are still in server.py
but will be progressively moved here.

Routes to be migrated from server.py:
- POST /coach/play/start (line ~8778)
- POST /coach/play/move (line ~8935)
- GET /coach/play/messages/{session_id} (line ~9696)
- POST /coach/play/reflect (line ~9767)
- POST /coach/play/chat (line ~9855)
- POST /coach/play/evaluate (line ~9969)
- POST /coach/play/move/confirm (line ~10080)
- GET /coach/play/state/{session_id} (line ~10228)
- GET /coach/play/feedback/{session_id} (line ~10260)
- POST /coach/play/end (line ~10291)
- POST /coach/play/analysis (line ~10341)
- GET /coach/play/active (line ~10466)
- GET /coach/play/history (line ~10486)
- GET /coach/play/identity (line ~10520)
- GET /coach/play/cpr/history (line ~10555)
- GET /coach/play/behaviors/{session_id} (line ~10582)
- POST /coach/play/feedback (line ~10624)
- POST /coach/play/endgame/start (line ~10701)
- POST /coach/play/endgame/move (line ~10740)
- GET /coach/play/opening-plan (line ~11072)
- POST /coach/play/teaching/start (line ~11154)
- POST /coach/play/teaching/move (line ~11197)
- POST /coach/play/teaching/exit (line ~11242)
- POST /coach/play/teaching/skip (line ~11281)

Helper functions to migrate:
- _is_common_opening_move (line ~8559)
- _get_coach_move_explanation (line ~8588)
- _get_teaching_explanation (line ~8677)
- _classify_move (line ~9061)
- _process_move_and_respond (line ~9079)

Total: ~2500 lines to migrate from server.py
"""

from fastapi import APIRouter, HTTPException, Depends, Body, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import uuid
import chess

logger = logging.getLogger(__name__)

# Create router for coach play endpoints
router = APIRouter(prefix="/coach/play", tags=["Coach Play"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm = None


def set_db(database):
    """Set the database reference for coach play routes"""
    global db
    db = database


def set_llm(llm_func):
    """Set the LLM function reference"""
    global call_llm
    call_llm = llm_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== HELPER FUNCTIONS ====================

def is_common_opening_move(move_san: str) -> bool:
    """
    Check if a move is a common mainline opening move.
    We don't want to say "This is part of the Italian Game" for h6!
    """
    mainline_moves = {
        "e4", "d4", "c4", "Nf3", "g3", "e3", "d3", "c3",
        "e5", "d5", "c5", "c6", "e6", "d6",
        "Nc3", "Nc6", "Nf6",
        "Bc4", "Bb5", "Be2", "Bd3", "Bg2", "Bc5", "Bb4", "Be7", "Bf5", "Bg4",
        "O-O", "O-O-O",
        "Qd2",
    }
    
    if move_san in ["h3", "h4", "h6", "a3", "a4", "a6", "Rh3", "Ra3"]:
        return False
    
    return move_san in mainline_moves


def get_coach_move_explanation(move_san: str, fen_before: str, fen_after: str, move_number: int) -> str:
    """
    Generate POSITION-SPECIFIC explanation for coach's move.
    """
    try:
        board_before = chess.Board(fen_before)
        chess_move = board_before.parse_san(move_san)
        from_sq = chess_move.from_square
        to_sq = chess_move.to_square
        piece = board_before.piece_at(from_sq)
        
        if piece is None:
            return f"I played {move_san}."
        
        if piece.piece_type == chess.PAWN:
            file = chess.square_file(to_sq)
            rank = chess.square_rank(to_sq)
            
            if file in [0, 7]:
                if rank in [2, 5]:
                    return f"I played {move_san}. This prepares a potential retreat square for my bishop or prevents your pieces from using that square."
                else:
                    return f"I played {move_san}. A flank pawn move."
            elif file in [3, 4]:
                return f"I played {move_san}. Fighting for the center."
            elif file in [2, 5]:
                return f"I played {move_san}. Supporting my central control."
            else:
                return f"I played {move_san}."
        
        if board_before.is_castling(chess_move):
            if board_before.is_kingside_castling(chess_move):
                return f"I played {move_san}. Castling kingside - my king is now safe and my rook is ready for action."
            else:
                return f"I played {move_san}. Castling queenside - my king is tucked away and my rook eyes the center."
        
        if piece.piece_type == chess.KNIGHT:
            central_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5]
            development_squares = [chess.F3, chess.C3, chess.F6, chess.C6]
            if to_sq in central_squares:
                return f"I played {move_san}. The knight is powerful in the center - it controls many squares from here."
            elif to_sq in development_squares:
                return f"I played {move_san}. Developing the knight to its natural square - knights should be developed early."
            else:
                return f"I played {move_san}. Repositioning my knight."
        
        if piece.piece_type == chess.BISHOP:
            if to_sq in [chess.G2, chess.B2, chess.G7, chess.B7]:
                return f"I played {move_san}. Fianchettoing my bishop - it will be powerful on this diagonal."
            elif to_sq in [chess.C4, chess.F4, chess.C5, chess.F5]:
                return f"I played {move_san}. Active bishop pointing at your position."
            else:
                return f"I played {move_san}. Developing my bishop."
        
        if piece.piece_type == chess.QUEEN:
            if move_number <= 5:
                return f"I played {move_san}. An early queen move - can you punish it?"
            else:
                return f"I played {move_san}. The queen enters the game."
        
        if piece.piece_type == chess.ROOK:
            file = chess.square_file(to_sq)
            if file in [3, 4]:
                return f"I played {move_san}. Centralizing my rook on an open file."
            else:
                return f"I played {move_san}."
        
        return f"I played {move_san}."
        
    except Exception as e:
        logger.warning(f"Error generating coach move explanation: {e}")
        return f"I played {move_san}."


def get_teaching_explanation(move_san: str, fen_before: str, fen_after: str, move_number: int) -> str:
    """
    Generate TEACHING-FOCUSED explanation for coach's move.
    """
    try:
        board_before = chess.Board(fen_before)
        chess_move = board_before.parse_san(move_san)
        from_sq = chess_move.from_square
        to_sq = chess_move.to_square
        piece = board_before.piece_at(from_sq)
        
        if piece is None:
            return f"See this {move_san}? Think about what it's preparing."
        
        if piece.piece_type == chess.PAWN:
            file = chess.square_file(to_sq)
            rank = chess.square_rank(to_sq)
            
            if file in [3, 4]:
                return f"Watch this {move_san} - fighting for the center. What squares does this pawn control now?"
            elif file in [2, 5]:
                return f"This {move_san} supports the center. Can you see how it helps control d4/e4?"
            elif rank in [2, 5]:
                return f"This {move_san} is a useful waiting move. What do you think it prevents?"
            else:
                return f"See this pawn move {move_san}? Every pawn move changes the structure permanently."
        
        if board_before.is_castling(chess_move):
            if board_before.is_kingside_castling(chess_move):
                return "Castling kingside! The king is now safe, and the rook is ready to join the fight. Have you castled yet?"
            else:
                return "Castling queenside! This is aggressive - the rook immediately eyes the center. Be ready for action!"
        
        if piece.piece_type == chess.KNIGHT:
            central_squares = [chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5]
            development_squares = [chess.F3, chess.C3, chess.F6, chess.C6]
            
            if to_sq in central_squares:
                return f"Look at this knight on {chess.square_name(to_sq)}! From the center, a knight controls up to 8 squares. What does it threaten?"
            elif to_sq in development_squares:
                return f"Knight to {chess.square_name(to_sq)} - this is a natural developing move. Notice it's heading toward the center?"
            else:
                return f"Watch this knight maneuver to {chess.square_name(to_sq)}. Knights need good outposts - squares where they can't be chased away."
        
        if piece.piece_type == chess.BISHOP:
            if to_sq in [chess.G2, chess.B2, chess.G7, chess.B7]:
                return "Fianchetto! The bishop on this diagonal is a long-range sniper. See how it controls the whole diagonal?"
            elif to_sq in [chess.C4, chess.F4, chess.C5, chess.F5]:
                return "Active bishop! It's pointing right at your position. What targets can you see?"
            else:
                return "Developing the bishop. Bishops are strongest on long, open diagonals."
        
        if piece.piece_type == chess.QUEEN:
            if move_number <= 5:
                return "Early queen move! Usually risky - can you think of ways to attack it and gain time?"
            else:
                return "The queen joins the attack. This is the most powerful piece - watch where it points!"
        
        if piece.piece_type == chess.ROOK:
            file = chess.square_file(to_sq)
            if file in [3, 4]:
                return "Rook to the center! Rooks love open files. Is there an open file for your rook too?"
            else:
                return "The rook is repositioning. Rooks are most powerful on open files and the 7th rank."
        
        return f"See this {move_san}? Think about what it accomplishes. What's the idea?"
        
    except Exception as e:
        logger.warning(f"Error generating teaching explanation: {e}")
        return f"Watch this move - {move_san}. What do you think it's preparing?"


def classify_move(eval_before: float, eval_after: float, user_color: str) -> str:
    """Classify a move as blunder, mistake, inaccuracy, or good based on centipawn loss."""
    if user_color == "white":
        cp_loss = (eval_before - eval_after) * 100
    else:
        cp_loss = (eval_after - eval_before) * 100
    
    if cp_loss >= 300:
        return "blunder"
    elif cp_loss >= 100:
        return "mistake"
    elif cp_loss >= 50:
        return "inaccuracy"
    else:
        return "good"


# ==================== MODELS ====================

class CoachPlayStartRequest(BaseModel):
    user_color: str = "white"
    time_control: str = "15+10"
    starting_fen: Optional[str] = None
    practice_mode: bool = False
    source_game_id: Optional[str] = None


class CoachPlayMoveRequest(BaseModel):
    session_id: str
    move: str
    thinking_time_ms: Optional[int] = None


class CoachPlayReflectRequest(BaseModel):
    session_id: str
    move_number: int
    user_reasoning: str


class CoachPlayChatRequest(BaseModel):
    session_id: str
    message: str


class CoachPlayFeedbackRequest(BaseModel):
    session_id: str
    move_number: int
    feedback_type: str  # helpful, not_helpful, wrong
    comment: Optional[str] = ""


# ==================== PLACEHOLDER ENDPOINTS ====================
# These are placeholders - the actual implementations are still in server.py
# They will be migrated in subsequent refactoring phases

# NOTE: The following endpoints are currently handled in server.py:
# - POST /coach/play/start
# - POST /coach/play/move  
# - GET /coach/play/messages/{session_id}
# - POST /coach/play/reflect
# - POST /coach/play/chat
# - POST /coach/play/evaluate
# - POST /coach/play/move/confirm
# - GET /coach/play/state/{session_id}
# - GET /coach/play/feedback/{session_id}
# - POST /coach/play/end
# - POST /coach/play/analysis
# - GET /coach/play/active
# - GET /coach/play/history
# - GET /coach/play/identity
# - GET /coach/play/cpr/history
# - GET /coach/play/behaviors/{session_id}
# - POST /coach/play/feedback
# - POST /coach/play/endgame/start
# - POST /coach/play/endgame/move
# - GET /coach/play/opening-plan
# - POST /coach/play/teaching/start
# - POST /coach/play/teaching/move
# - POST /coach/play/teaching/exit
# - POST /coach/play/teaching/skip


@router.get("/stats")
async def get_coach_play_stats(user: User = Depends(get_current_user)):
    """
    Get statistics about user's coach play sessions.
    
    This is a new endpoint added as part of the refactoring.
    """
    global db
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Get session count
    total_sessions = await db.coach_sessions.count_documents({
        "user_id": user.user_id
    })
    
    # Get completed sessions
    completed_sessions = await db.coach_sessions.count_documents({
        "user_id": user.user_id,
        "status": "completed"
    })
    
    # Get recent sessions
    recent_sessions = await db.coach_sessions.find({
        "user_id": user.user_id
    }).sort("created_at", -1).limit(5).to_list(5)
    
    # Calculate stats
    wins = 0
    losses = 0
    draws = 0
    
    for session in recent_sessions:
        result = session.get("result")
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "draw":
            draws += 1
    
    return {
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "recent_results": {
            "wins": wins,
            "losses": losses,
            "draws": draws
        },
        "recent_sessions": [
            {
                "session_id": s.get("session_id"),
                "created_at": s.get("created_at"),
                "user_color": s.get("user_color"),
                "result": s.get("result"),
                "status": s.get("status")
            }
            for s in recent_sessions
        ]
    }


@router.get("/active")
async def get_active_coach_sessions(
    user: User = Depends(get_current_user)
):
    """
    Get user's active Play With Coach sessions.
    
    Returns list of active sessions (usually just one).
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    sessions = await db.coach_sessions.find(
        {"user_id": user.user_id, "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    return {
        "active_sessions": sessions,
        "count": len(sessions)
    }


@router.get("/history")
async def get_coach_play_history(
    user: User = Depends(get_current_user),
    limit: int = 10
):
    """
    Get user's Play With Coach history.
    
    Returns completed and resigned sessions.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    sessions = await db.coach_sessions.find(
        {
            "user_id": user.user_id,
            "status": {"$in": ["completed", "resigned", "abandoned"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Add summary stats
    wins = sum(1 for s in sessions if s.get("result") == "win")
    losses = sum(1 for s in sessions if s.get("result") == "loss")
    draws = sum(1 for s in sessions if s.get("result") == "draw")
    
    return {
        "sessions": sessions,
        "stats": {
            "total": len(sessions),
            "wins": wins,
            "losses": losses,
            "draws": draws
        }
    }


@router.get("/identity")
async def get_player_identity(
    user: User = Depends(get_current_user)
):
    """
    Get user's cognitive identity profile (Step 5).
    
    Identity is built from behavioral patterns across multiple sessions.
    Requires minimum 3 sessions for meaningful identity.
    
    Returns:
    - identity_label: e.g., "The Calculator", "The Warrior"
    - identity_description: Narrative description
    - trait_snapshot: Current trait values
    - confidence: How confident we are (0-1)
    - narrative_timeline: Recent session narratives
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    identity = await db.player_identity.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    
    if not identity:
        return {
            "has_identity": False,
            "message": "Play more games with coach to build your identity profile.",
            "sessions_needed": 3
        }
    
    return {
        "has_identity": True,
        "identity": identity
    }


@router.get("/cpr/history")
async def get_cpr_history(
    user: User = Depends(get_current_user),
    limit: int = 10
):
    """
    Get user's CPR (Cognitive Performance Rating) history.
    
    Returns CPR scores from recent sessions.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    sessions = await db.coach_sessions.find(
        {
            "user_id": user.user_id,
            "cpr_after": {"$exists": True, "$ne": None}
        },
        {"_id": 0, "session_id": 1, "cpr_after": 1, "created_at": 1, "result": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    cpr_scores = [s.get("cpr_after") for s in sessions if s.get("cpr_after")]
    
    return {
        "history": sessions,
        "average_cpr": sum(cpr_scores) / len(cpr_scores) if cpr_scores else None,
        "sessions_count": len(sessions)
    }


@router.get("/behaviors/{session_id}")
async def get_session_behaviors(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get behavioral events from a specific session.
    
    Returns detailed behavior analysis for review.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    behavior_events = session_doc.get("behavior_events", [])
    
    # Categorize events
    positive = [e for e in behavior_events if e.get("behavior_type") in [
        "calculated_sacrifice", "positional_patience", "tactical_alertness",
        "threat_addressed", "accurate_under_pressure"
    ]]
    negative = [e for e in behavior_events if e.get("behavior_type") in [
        "impulse_move", "threat_ignored", "panic_defense",
        "rapid_streak", "time_pressure_mistake", "repeated_mistake"
    ]]
    
    return {
        "session_id": session_id,
        "total_events": len(behavior_events),
        "positive_behaviors": len(positive),
        "negative_behaviors": len(negative),
        "events": behavior_events,
        "summary": {
            "positive": positive,
            "negative": negative
        }
    }


@router.post("/feedback")
async def submit_coach_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Submit feedback on a coach message (for beta users).
    
    Body:
    - session_id: The game session ID
    - message_id: The coach message ID
    - feedback_type: "confusing" | "wrong" | "obvious" | "not_relevant" | "other"
    - comment: Optional user comment
    
    Returns:
    - success: True if feedback was recorded
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_id = request.get("session_id")
    message_id = request.get("message_id")
    feedback_type = request.get("feedback_type", "other")
    comment = request.get("comment", "")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message_id:
        raise HTTPException(status_code=400, detail="message_id is required")
    
    # Validate feedback_type
    valid_types = ["confusing", "wrong", "obvious", "not_relevant", "helpful", "other"]
    if feedback_type not in valid_types:
        feedback_type = "other"
    
    # Get session to verify ownership and get context
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get the message for context
    message_doc = await db.coach_messages.find_one({"_id": message_id})
    message_context = {}
    if message_doc:
        message_context = {
            "message": message_doc.get("message", ""),
            "trigger": message_doc.get("trigger", ""),
            "move": message_doc.get("move", ""),
            "rule_id": message_doc.get("rule_id", ""),
            "is_wisdom_based": message_doc.get("is_wisdom_based", False),
        }
    
    # Store feedback
    await db.coach_feedback.insert_one({
        "user_id": user.user_id,
        "session_id": session_id,
        "message_id": message_id,
        "feedback_type": feedback_type,
        "comment": comment,
        "current_fen": session_doc.get("current_fen", ""),
        "message_context": message_context,
        "user_rating": session_doc.get("user_rating", 1200),
        "created_at": datetime.now(timezone.utc),
    })
    
    logger.info(f"Coach feedback recorded: type={feedback_type}, session={session_id}, message={message_id}")
    
    return {
        "success": True,
        "message": "Thank you for your feedback! It helps us improve the coach."
    }



@router.get("/state/{session_id}")
async def get_coach_play_state(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get current state of a Play With Coach session.
    
    Returns:
    - session: Full session state
    - current_fen: Current board position
    - is_player_turn: Whether it's the player's turn
    - legal_moves: List of legal moves in SAN notation
    - move_count: Number of moves played
    - game_over: Whether the game has ended
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from coach_play import get_session_state
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    state = await get_session_state(db, session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return state


@router.get("/move-feedback/{session_id}")
async def get_coach_play_move_feedback(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get comprehensive coaching feedback for the last move made.
    
    This is the key endpoint for real-time teaching - returns:
    - Assessment of user's move quality
    - Best move explanation
    - Coach's response explanation
    - Personalized coaching message
    
    Returns:
    - feedback: Complete MoveFeedback object
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.realtime_coaching_feedback import get_last_move_feedback
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    feedback = await get_last_move_feedback(db, session_id, user.user_id)
    
    return {"feedback": feedback}


@router.post("/end")
async def end_coach_play_session(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    End a Play With Coach session (resign, abort).
    
    Body:
    - session_id: Session ID
    - reason: Reason for ending ("resigned", "abandoned")
    
    Returns:
    - success: bool
    - session: Final session state
    - summary: Game summary
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from coach_play import end_coach_session
    
    session_id = request.get("session_id")
    reason = request.get("reason", "resigned")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        result = await end_coach_session(
            db=db,
            session_id=session_id,
            reason=reason
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "End failed"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis")
async def get_postgame_analysis(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get comprehensive post-game analysis.
    
    Includes:
    - Performance rating (estimated rating based on move quality)
    - Mistake breakdown with explanations
    - Habit check (comparing to known weaknesses)
    - Personalized recommendations
    - Coach summary and encouragement
    
    Body:
    - session_id: Session ID
    
    Returns:
    - PostGameAnalysis object with all components
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.postgame_analysis import analyze_postgame
    
    session_id = request.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session data
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        # Get evaluations from stored data
        evaluations = session_doc.get("evaluations", [])
        
        # Perform analysis
        analysis = await analyze_postgame(
            db=db,
            session_id=session_id,
            user_id=user.user_id,
            move_history=session_doc.get("move_history", []),
            evaluations=evaluations,
            game_result=session_doc.get("result", "draw"),
            user_rating=session_doc.get("user_rating", 1200),
            user_color=session_doc.get("user_color", "white"),
            time_controls=session_doc.get("time_controls")
        )
        
        # Convert to dict for JSON response - includes MEMORY INSIGHTS
        result = {
            "session_id": analysis.session_id,
            "game_result": analysis.game_result,
            "performance_rating": {
                "estimated": analysis.performance_rating.estimated_rating,
                "confidence": analysis.performance_rating.confidence,
                "vs_actual": analysis.performance_rating.comparison_to_actual,
                "factors": analysis.performance_rating.key_factors
            },
            "accuracy": analysis.accuracy_percentage,
            "mistakes": {
                "blunders": analysis.total_blunders,
                "mistakes": analysis.total_mistakes,
                "inaccuracies": analysis.total_inaccuracies,
                "details": [
                    {
                        "move_number": m.move_number,
                        "move": m.move_played,
                        "type": m.mistake_type.value,
                        "severity": m.severity,
                        "explanation": m.explanation,
                        "better_move": m.better_move
                    }
                    for m in analysis.mistakes[:5]
                ]
            },
            "habits": {
                "violations": [
                    {
                        "habit": v.habit_type.value,
                        "move_number": v.move_number,
                        "description": v.description
                    }
                    for v in analysis.habit_violations
                ],
                "improved": analysis.habits_improved,
                "still_weak": analysis.habits_still_weak
            },
            # MEMORY INSIGHTS - This is what makes the coach feel human
            "memory": {
                "games_together": analysis.games_together,
                "coach_knows_you": analysis.coach_knows_you,
                "insights": [
                    {
                        "type": insight.insight_type,
                        "message": insight.message,
                        "pattern": insight.pattern_name,
                        "count": insight.occurrence_count,
                        "improving": insight.is_improving
                    }
                    for insight in analysis.memory_insights
                ]
            },
            "recommendations": {
                "priority": analysis.priority_focus,
                "suggestions": analysis.training_suggestions,
                "opening_to_learn": analysis.opening_to_learn
            },
            "coach_summary": analysis.coach_summary,
            "encouragement": analysis.encouragement
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating post-game analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
