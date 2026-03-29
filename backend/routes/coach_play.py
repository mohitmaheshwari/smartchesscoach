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
    
    from coach_play.coach_game_session import get_session_state
    
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
    
    from coach_play.coach_game_session import end_coach_session
    
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



@router.get("/messages/{session_id}")
async def get_coach_messages(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Poll for new coach messages.
    Frontend calls this periodically to get coach commentary.
    
    Returns unread messages and marks them as read.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get unread messages
    cursor = db.coach_messages.find({
        "session_id": session_id,
        "read": False
    }).sort("created_at", 1)
    
    messages = []
    message_ids = []
    
    async for msg in cursor:
        msg_data = {
            "id": str(msg["_id"]),
            "type": msg.get("type", "coach"),
            "message": msg.get("message", ""),
            "trigger": msg.get("trigger"),
            "move": msg.get("move"),
            "move_number": msg.get("move_number"),
            "timestamp": msg.get("created_at").isoformat() if msg.get("created_at") else None,
            # Always include opening info if present (for "Learn Opening" button)
            "opening_key": msg.get("opening_key"),
            "opening_name": msg.get("opening_name"),
        }
        
        # Include opening teaching offer fields
        if msg.get("type") == "opening_teaching_offer":
            msg_data["options"] = msg.get("options")
            msg_data["trap_name"] = msg.get("trap_name")
        
        # Include endgame teaching offer fields
        if msg.get("type") == "endgame_teaching_offer":
            msg_data["endgame_type"] = msg.get("endgame_type")
            msg_data["lesson_name"] = msg.get("lesson_name")
            msg_data["key_concepts"] = msg.get("key_concepts")
            msg_data["options"] = msg.get("options")
        
        messages.append(msg_data)
        message_ids.append(msg["_id"])
    
    # Mark as read
    if message_ids:
        await db.coach_messages.update_many(
            {"_id": {"$in": message_ids}},
            {"$set": {"read": True}}
        )
    
    return {
        "success": True,
        "messages": messages,
        "count": len(messages)
    }


@router.post("/reflect")
async def get_coach_reflection_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get Socratic coaching feedback after a move.
    
    User explains WHY they played a move, coach compares to reality.
    
    Body:
    - session_id: Session ID
    - move_index: Index of the move to reflect on
    - user_reasoning: User's explanation for why they played the move
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from coach_play.coach_commentary import get_coach_feedback
    
    session_id = request.get("session_id")
    move_index = request.get("move_index")
    user_reasoning = request.get("user_reasoning", "")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if move_index is None:
        raise HTTPException(status_code=400, detail="move_index is required")
    if not user_reasoning:
        raise HTTPException(status_code=400, detail="user_reasoning is required")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Get the move from history
    move_history = session_doc.get("move_history", [])
    if move_index < 0 or move_index >= len(move_history):
        raise HTTPException(status_code=400, detail="Invalid move_index")
    
    move_data = move_history[move_index]
    
    if move_data.get("by") != "player":
        raise HTTPException(status_code=400, detail="Can only reflect on your own moves")
    
    fen_before = move_data.get("fen_before")
    move_san = move_data.get("move")
    fen_after = move_data.get("fen_after")
    move_number = (move_index // 2) + 1
    
    try:
        feedback = await get_coach_feedback(
            fen_before=fen_before,
            move_san=move_san,
            fen_after=fen_after,
            user_reasoning=user_reasoning,
            user_color=session_doc.get("user_color", "white"),
            move_number=move_number
        )
        
        return {
            "success": True,
            "move": move_san,
            "move_index": move_index,
            **feedback
        }
        
    except Exception as e:
        logger.error(f"Error getting coach feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def coach_chat_message(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Send a message to the coach and get a PERSONALIZED response.
    
    Our coach knows your past games and mistakes.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from coach_play.coach_commentary import generate_response_to_user, CoachCommentary
    from coach_play.personalized_coach import get_personalized_coaching
    
    session_id = request.get("session_id")
    message = request.get("message", "").strip()
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        current_fen = session_doc.get("current_fen")
        move_history = session_doc.get("move_history", [])
        user_color = session_doc.get("user_color", "white")
        user_rating = session_doc.get("user_rating", 1200)
        
        user_moves = [m for m in move_history if m.get("by") == "player"]
        last_user_move = user_moves[-1] if user_moves else None
        last_move = last_user_move.get("move", "") if last_user_move else ""
        
        move_analysis = None
        if last_user_move and last_user_move.get("fen_before"):
            coach = CoachCommentary()
            try:
                analysis = await coach.analyze_move(
                    last_user_move.get("fen_before"),
                    last_user_move.get("move"),
                    last_user_move.get("fen_after", current_fen)
                )
                move_analysis = {
                    "cp_loss": int(analysis.eval_loss * 100),
                    "best_move": analysis.best_move_san,
                    "quality": analysis.quality.value
                }
            except Exception:
                pass
        
        coach = CoachCommentary()
        position = await coach.analyze_position(current_fen)
        phase = position.phase
        
        personal_data = await get_personalized_coaching(
            db=db,
            user_id=user.user_id,
            current_fen=current_fen,
            last_move=last_move,
            phase=phase,
            user_color=user_color,
            move_analysis=move_analysis
        )
        
        result = await generate_response_to_user(
            user_message=message,
            current_fen=current_fen,
            move_history=move_history,
            user_color=user_color,
            user_rating=user_rating,
            personal_context=personal_data.get("personal_context"),
            position_plan=personal_data.get("position_plan")
        )
        
        return {
            "success": True,
            "response": result.get("response", ""),
            "suggestion_arrow": result.get("suggestion_arrow"),
            "move_quality": result.get("move_quality"),
            "best_move": result.get("best_move"),
            "missed_tactic": result.get("missed_tactic"),
            "position_plan": personal_data.get("position_plan"),
            "personal_insight": personal_data.get("personal_context", {}).get("similar_mistake"),
            "pattern_match": personal_data.get("pattern_match")
        }
        
    except Exception as e:
        logger.error(f"Error in coach chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_coach_play_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Evaluate a move BEFORE making it - Pre-Move Guardian.
    
    Stop bad moves before they happen.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    import chess
    from stockfish_service import StockfishEngine
    
    session_id = request.get("session_id")
    move = request.get("move")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        session_doc = await db.play_sessions.find_one({"session_id": session_id})
    
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session_doc.get("status") != "active":
        raise HTTPException(status_code=400, detail="Session not active")
    
    current_fen = session_doc.get("current_fen")
    user_color = session_doc.get("user_color")
    
    eval_before = None
    eval_after = None
    
    try:
        engine = StockfishEngine()
        engine.start()
        
        try:
            board_before = chess.Board(current_fen)
            eval_before_cp, _ = engine.evaluate_position(board_before, depth=12)
            eval_before = eval_before_cp / 100.0
            
            chess_move = board_before.parse_san(move)
            board_before.push(chess_move)
            
            eval_after_cp, _ = engine.evaluate_position(board_before, depth=12)
            eval_after = eval_after_cp / 100.0
            
        finally:
            engine.stop()
            
    except Exception as e:
        logger.warning(f"Stockfish evaluation failed: {e}")
    
    from coach_play.pre_move_guardian import PreMoveGuardian
    
    guardian = PreMoveGuardian(session_doc.get("remaining_interventions", 3))
    guardian_result = guardian.evaluate_move(
        fen=current_fen,
        move_san=move,
        user_color=user_color,
        stockfish_eval_before=eval_before,
        stockfish_eval_after=eval_after
    )
    
    result = guardian_result.to_dict()
    result["remaining_interventions"] = session_doc.get("remaining_interventions", 3)
    
    details = result.get("details", {})
    if details.get("good_trade"):
        result["good_trade"] = True
    elif details.get("stockfish_approved"):
        result["stockfish_approved"] = True
    
    return result


@router.post("/move/confirm")
async def confirm_risky_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Confirm a risky move after user acknowledges the warning.
    
    Decrements intervention count for this session.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_id = request.get("session_id")
    move = request.get("move")
    risk_level = request.get("risk_level", "medium")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Decrement intervention count
    remaining = session_doc.get("remaining_interventions", 3)
    if remaining > 0:
        remaining -= 1
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"remaining_interventions": remaining}}
        )
    
    # Log the override
    guardian_overrides = session_doc.get("guardian_overrides", [])
    guardian_overrides.append({
        "move": move,
        "risk_level": risk_level,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"guardian_overrides": guardian_overrides}}
    )
    
    return {
        "success": True,
        "remaining_interventions": remaining,
        "message": "Okay, I'll let you learn from this one!"
    }




# ========================================
# OPENING TEACHING ENDPOINTS
# ========================================

@router.post("/teaching/start")
async def start_opening_teaching(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Start an interactive opening lesson during the game.
    
    Called when user clicks a teaching option (e.g., "Learn the Fried Liver").
    
    Body:
    - session_id: Current game session
    - lesson_type: "learn_trap" | "learn_main_line"
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.opening_teaching_integration import start_opening_lesson
    
    session_id = request.get("session_id")
    lesson_type = request.get("lesson_type", "learn_trap")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await start_opening_lesson(db, session_id, user.user_id, lesson_type)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/teaching/move")
async def process_teaching_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Process a move during opening teaching mode.
    
    Validates the move, provides feedback, and advances the lesson.
    
    Body:
    - session_id: Current game session
    - move: Move played by user (SAN notation)
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.opening_teaching_integration import process_teaching_move as process_move
    
    session_id = request.get("session_id")
    move = request.get("move")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await process_move(db, session_id, move)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/teaching/exit")
async def exit_teaching_mode(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Exit teaching mode after lesson completion.
    
    Body:
    - session_id: Current game session
    - choice: "continue_game" | "new_game" | "try_another"
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.opening_teaching_integration import exit_teaching_mode as exit_mode
    
    session_id = request.get("session_id")
    choice = request.get("choice", "continue_game")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await exit_mode(db, session_id, choice)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/teaching/skip")
async def skip_opening_offer(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Skip the opening teaching offer (user chose "Just play").
    
    Body:
    - session_id: Current game session
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_id = request.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"opening_offer_shown": True}}
    )
    
    return {"success": True, "message": "Got it! Let's play on."}


@router.get("/opening-plan")
async def get_opening_plan(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get opening guidance for the current position.
    
    Returns opening name, main ideas, and suggestions.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.opening_library_service import get_opening_for_position, get_opening_name
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    current_fen = session_doc.get("current_fen")
    
    opening = get_opening_for_position(current_fen)
    
    lichess_name = ""
    try:
        lichess_name = await get_opening_name(current_fen)
    except Exception:
        pass
    
    if opening:
        return {
            "success": True,
            "opening_name": opening.name,
            "lichess_name": lichess_name,
            "main_ideas": opening.main_ideas,
            "key_squares": opening.key_squares,
            "typical_mistakes": opening.typical_mistakes,
            "simple_explanation": opening.simple_explanation,
            "eco_codes": opening.eco_codes,
        }
    elif lichess_name:
        return {
            "success": True,
            "opening_name": lichess_name,
            "lichess_name": lichess_name,
            "main_ideas": [
                "Develop your knights and bishops",
                "Control the center",
                "Castle to protect your king"
            ],
            "key_squares": [],
            "typical_mistakes": [],
            "simple_explanation": f"This is the {lichess_name}. Focus on development and king safety.",
            "eco_codes": [],
        }
    else:
        return {
            "success": True,
            "opening_name": None,
            "lichess_name": None,
            "main_ideas": [
                "Develop your pieces",
                "Control the center",
                "Keep your king safe"
            ],
            "key_squares": [],
            "typical_mistakes": [],
            "simple_explanation": "Focus on basic opening principles.",
            "eco_codes": [],
        }



@router.post("/trigger-coach-move")
async def trigger_coach_move_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Trigger the coach to make a move when it's their turn.
    
    Used when resuming a game that was interrupted during coach's turn.
    
    Body:
    - session_id: Current game session
    
    Returns:
    - success: bool
    - coach_move: The move played by coach (if successful)
    - current_fen: Updated position
    - is_player_turn: Should now be True
    """
    global db
    import chess
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_id = request.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session_doc.get("status") != "active":
        raise HTTPException(status_code=400, detail="Session not active")
    
    # Check if it's actually coach's turn
    current_fen = session_doc.get("current_fen")
    user_color = session_doc.get("user_color")
    
    try:
        board = chess.Board(current_fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid board position")
    
    is_white_turn = board.turn == chess.WHITE
    is_player_turn = (is_white_turn and user_color == "white") or (not is_white_turn and user_color == "black")
    
    if is_player_turn:
        return {
            "success": True,
            "message": "It's already your turn!",
            "current_fen": current_fen,
            "is_player_turn": True
        }
    
    # It's coach's turn - make a move
    from coach_play.coach_opponent import CoachOpponent
    
    try:
        user_rating = session_doc.get("user_rating", 1200)
        coach = CoachOpponent(user_rating=user_rating)
        
        # Get coach's move using FEN - returns SAN notation
        coach_move = await coach.get_move(current_fen)
        
        if not coach_move:
            raise HTTPException(status_code=500, detail="Coach couldn't find a move")
        
        # Parse move - could be SAN or UCI
        try:
            # Try parsing as SAN first (most likely)
            chess_move = board.parse_san(coach_move)
            coach_move_san = coach_move
            coach_move_uci = chess_move.uci()
        except ValueError:
            # Try parsing as UCI
            try:
                chess_move = board.parse_uci(coach_move)
                coach_move_san = board.san(chess_move)
                coach_move_uci = coach_move
            except ValueError:
                raise HTTPException(status_code=500, detail=f"Invalid move format: {coach_move}")
        
        # Make the move
        board.push(chess_move)
        new_fen = board.fen()
        
        # Update session
        move_history = session_doc.get("move_history", [])
        move_number = len(move_history) + 1
        
        move_history.append({
            "move": coach_move_san,
            "uci": coach_move_uci,
            "by": "coach",
            "move_number": move_number,
            "fen_before": current_fen,
            "fen_after": new_fen,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "current_fen": new_fen,
                    "move_history": move_history,
                    "coach_move_pending": False,
                    "last_coach_move": coach_move_san
                }
            }
        )
        
        # Add a coach message
        await db.coach_messages.insert_one({
            "session_id": session_id,
            "type": "coach",
            "message": f"I played {coach_move_san}. Your turn!",
            "trigger": "resume_coach_move",
            "move": coach_move_san,
            "move_number": move_number,
            "created_at": datetime.now(timezone.utc),
            "read": False
        })
        
        return {
            "success": True,
            "coach_move": coach_move_san,
            "current_fen": new_fen,
            "is_player_turn": True,
            "message": f"Coach played {coach_move_san}. Your turn!"
        }
        
    except Exception as e:
        logger.error(f"Error triggering coach move: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ==================== V5 COACHING INTEGRATION ====================

@router.post("/v5/feedback")
async def get_v5_coaching_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get V5 "Thinking Simulator" coaching feedback for a move.
    
    This uses the SAME coaching logic as Lab (Game Decryption), ensuring
    consistent coaching tone and quality across both pages.
    
    Body:
    - session_id: Coach play session ID
    - move_san: The move just played (SAN notation)
    - fen_before: Position before the move
    - fen_after: Position after the move
    - is_user_move: Whether this was the user's move (vs coach's move)
    - best_move: Best move according to engine (optional)
    - pv_after_played: PV after the played move (optional)
    - pv_after_best: PV after the best move (optional)
    - cp_loss: Centipawn loss (optional)
    
    Returns:
    - V5Coaching object with narrative, consequence, candidates, learning, etc.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    
    session_id = request.get("session_id")
    move_san = request.get("move_san")
    fen_before = request.get("fen_before")
    is_user_move = request.get("is_user_move", True)
    best_move = request.get("best_move")
    pv_after_played = request.get("pv_after_played", [])
    pv_after_best = request.get("pv_after_best", [])
    cp_loss = request.get("cp_loss", 0)
    
    if not move_san or not fen_before:
        raise HTTPException(status_code=400, detail="move_san and fen_before are required")
    
    # Verify session belongs to user
    if session_id:
        session_doc = await db.coach_sessions.find_one({"session_id": session_id})
        if session_doc and session_doc.get("user_id") != user.user_id:
            raise HTTPException(status_code=403, detail="Not your session")
    
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(move_san)
        
        # Get user's color from session
        user_color = "white"
        if session_id:
            session_doc = await db.coach_sessions.find_one({"session_id": session_id})
            if session_doc:
                user_color = session_doc.get("user_color", "white")
        
        # Determine game phase based on move count
        fullmove = board.fullmove_number
        if fullmove <= 10:
            phase = "opening"
        elif fullmove <= 30:
            phase = "middlegame"
        else:
            phase = "endgame"
        
        # Determine coaching context
        context = CoachingContext.LIVE_AFTER_USER if is_user_move else CoachingContext.LIVE_AFTER_COACH
        
        # Generate V5 coaching
        coaching = await generate_move_coaching(
            board_before=board,
            move=move,
            best_move_san=best_move,
            pv_after_played=pv_after_played,
            pv_after_best=pv_after_best,
            cp_loss=cp_loss,
            phase=phase,
            is_user_move=is_user_move,
            context=context,
            user_color=user_color
        )
        
        return coaching.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid move or FEN: {e}")
    except Exception as e:
        logger.error(f"Error generating V5 coaching: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/v5/interactive-feedback")
async def get_interactive_coaching(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get INTERACTIVE coaching for Play with Coach.
    
    Supports phased calls:
    - phase="user_move" → Return only user move V5 coaching (call RIGHT after user moves)
    - phase="coach_move" → Return only coach move explanation (call after coach responds)
    - phase=None → Return both (default, backward compat)
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.shared_coaching_v5 import generate_move_coaching, generate_coach_move_explanation, CoachingContext, quick_stockfish_eval
    from services.player_habits_service import generate_behavioral_coaching, get_player_profile
    
    session_id = request.get("session_id")
    phase = request.get("phase")  # "user_move", "coach_move", or None (both)
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    user_color = session_doc.get("user_color", "white")
    move_history = session_doc.get("move_history", [])
    evaluations = session_doc.get("evaluations", [])
    
    result = {
        "user_move_coaching": None,
        "coach_move_coaching": None,
        "behavioral_coaching": None,
        "is_user_turn": True
    }
    
    if not move_history:
        return result
    
    # Find last user move and last coach move
    last_user_move = None
    last_coach_move = None
    
    for m in reversed(move_history):
        if m.get("by") == "player" and not last_user_move:
            last_user_move = m
        elif m.get("by") == "coach" and not last_coach_move:
            last_coach_move = m
        if last_user_move and last_coach_move:
            break
    
    # Determine whose turn
    if move_history:
        result["is_user_turn"] = move_history[-1].get("by") == "coach"
    
    # === USER MOVE COACHING (phase="user_move" or both) ===
    if phase in (None, "user_move") and last_user_move and last_user_move.get("fen_before"):
        try:
            fen_before = last_user_move["fen_before"]
            move_san = last_user_move["move"]
            board = chess.Board(fen_before)
            move = board.parse_san(move_san)
            
            # Try stored analysis data first
            best_move = last_user_move.get("best_move")
            eval_before = last_user_move.get("eval_before", 0)
            eval_after = last_user_move.get("eval_after", 0)
            pv_after_played = last_user_move.get("pv_after_played", [])
            pv_after_best = last_user_move.get("pv_after_best", [])
            
            # Fallback: check evaluations list
            if not best_move and evaluations:
                for ev in reversed(evaluations):
                    if ev.get("move") == move_san and ev.get("by") == "player":
                        best_move = ev.get("best_move")
                        eval_before = ev.get("eval_before", eval_before)
                        eval_after = ev.get("eval_after", eval_after)
                        break
            
            # If STILL no analysis data, run quick Stockfish eval inline
            if not best_move:
                sf_eval = await quick_stockfish_eval(fen_before, move_san, user_color)
                best_move = sf_eval["best_move"]
                eval_before = sf_eval["eval_before"]
                eval_after = sf_eval["eval_after"]
                pv_after_played = sf_eval["pv_after_played"]
                pv_after_best = sf_eval["pv_after_best"]
            
            # Calculate cp_loss
            if user_color == "white":
                cp_loss = max(0, int((eval_before - eval_after) * 100))
            else:
                cp_loss = max(0, int((eval_after - eval_before) * 100))
            
            # Determine game phase
            fullmove = board.fullmove_number
            phase_str = "opening" if fullmove <= 10 else ("middlegame" if fullmove <= 30 else "endgame")
            
            # Run V5 coaching — SAME function Lab uses!
            coaching = await generate_move_coaching(
                board_before=board,
                move=move,
                best_move_san=best_move,
                pv_after_played=pv_after_played,
                pv_after_best=pv_after_best,
                cp_loss=cp_loss,
                phase=phase_str,
                is_user_move=True,
                context=CoachingContext.LIVE_AFTER_USER,
                user_color=user_color
            )
            
            coaching_dict = coaching.to_dict()
            coaching_dict["move_san"] = move_san
            coaching_dict["fen_before"] = fen_before  # Needed for board preview of alternatives
            
            # === PATTERN MEMORY INJECTION ===
            # "You've missed forks 3 times this week" — makes the coach feel like it remembers
            if coaching.severity in ("mistake", "blunder", "inaccuracy") and cp_loss >= 100:
                try:
                    from services.pattern_memory_service import get_pattern_for_mistake, normalize_pattern
                    
                    # Map coaching concept_id or severity to a cognitive gap
                    cognitive_gap = coaching.concept_id or coaching.severity
                    pattern_data = await get_pattern_for_mistake(db, user.user_id, cognitive_gap)
                    
                    if pattern_data and pattern_data.get("confrontation_message"):
                        coaching_dict["pattern_memory"] = pattern_data["confrontation_message"]
                except Exception as pm_err:
                    logger.warning(f"Pattern memory injection failed (non-critical): {pm_err}")
            
            # === THEORY APPLIED TRACKING ===
            # Check if this move matches an opening theory the user was taught
            if len(move_history) <= 24 and coaching.severity in ("good", "excellent", "book"):
                try:
                    from services.opening_mastery import detect_opening_from_moves, get_user_opening_progress, update_user_opening_progress
                    from services.opening_theory_json_service import get_opening_theory
                    
                    moves_san = [m.get("move", "") for m in move_history if m.get("move")]
                    opening_info = detect_opening_from_moves(moves_san)
                    
                    if opening_info:
                        opening_key = opening_info["opening_key"]
                        theory = get_opening_theory(opening_key)
                        
                        if theory:
                            opening_name = theory.get("name", opening_key)
                            progress = await get_user_opening_progress(db, user.user_id, opening_name)
                            
                            # Only if user was previously taught this opening
                            if progress and progress.times_practiced > 0:
                                main_line = theory.get("main_line", [])
                                move_idx = len(moves_san) - 1
                                
                                # Check if current move matches theory
                                if move_idx < len(main_line) and move_san == main_line[move_idx]:
                                    progress.times_applied_in_games += 1
                                    progress.correct_applications += 1
                                    await update_user_opening_progress(db, progress)
                                    
                                    coaching_dict["theory_applied"] = f"You played the book move in the {opening_name}. The theory is sticking."
                except Exception as ta_err:
                    logger.warning(f"Theory applied tracking failed (non-critical): {ta_err}")
            
            result["user_move_coaching"] = coaching_dict
            
            # === BEHAVIORAL COACHING (Smart Coach) ===
            try:
                behavior_events = session_doc.get("behavior_events", [])
                player_profile = await get_player_profile(db, user.user_id)
                
                behavioral = generate_behavioral_coaching(
                    move_san=move_san,
                    time_spent=last_user_move.get("time_spent", 0),
                    move_quality=coaching.severity,
                    game_phase=phase_str,
                    behavior_events=behavior_events,
                    move_history=move_history,
                    player_profile=player_profile
                )
                
                if behavioral:
                    result["behavioral_coaching"] = behavioral
            except Exception as e:
                logger.warning(f"Behavioral coaching failed (non-critical): {e}")
            
        except Exception as e:
            logger.error(f"Error generating V5 user move coaching: {e}")
    
    # === COACH MOVE COACHING (phase="coach_move" or both) ===
    if phase in (None, "coach_move") and last_coach_move and last_coach_move.get("fen_before"):
        try:
            board = chess.Board(last_coach_move["fen_before"])
            move = board.parse_san(last_coach_move["move"])
            
            coach_explanation = generate_coach_move_explanation(
                board, move, user_color
            )
            result["coach_move_coaching"] = coach_explanation
        except Exception as e:
            logger.warning(f"Error generating coach move explanation: {e}")
    
    return result


def _transform_to_fun_language(feedback: Dict, severity: str, move_san: str) -> str:
    """Transform feedback to fun V5 language."""
    piece = feedback.get("piece_moved", "")
    
    if severity in ["good", "best", "great"]:
        return feedback.get("coaching_message") or f"Nice! {move_san} is a solid choice!"
    
    if "knight" in piece.lower() or (move_san and move_san[0] == "N"):
        if severity in ["blunder", "mistake"]:
            return f"Naughty Knight! {move_san} gets your Horsey in trouble!"
        return f"Hmm, {move_san} - what's your Horsey doing there?"
    
    if "bishop" in piece.lower() or (move_san and move_san[0] == "B"):
        return f"Your Slicey Boi looks sad after {move_san}!"
    
    if "pawn" in piece.lower():
        return f"Careful with {move_san} - Little Soldiers can't go backwards!"
    
    if severity == "blunder":
        return f"Oops! {move_san} is a blunder - let's see why."
    if severity == "mistake":
        return f"{move_san} is a mistake - there was something better."
    if severity == "inaccuracy":
        return f"{move_san} is okay, but there's a stronger idea."
    
    return feedback.get("coaching_message") or f"Let's look at {move_san}."



@router.get("/v5/session/{session_id}/moves")
async def get_v5_session_moves_coaching(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get V5 coaching for all moves in a session.
    
    This allows the frontend to display a full game review with V5 coaching
    after a Play with Coach session ends.
    
    Returns:
    - moves: List of moves with V5 coaching for each
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Verify session belongs to user
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Check if V5 analysis already exists
    v5_data = session_doc.get("v5_coaching_data")
    if v5_data:
        return {"moves": v5_data, "cached": True}
    
    # If not, generate it now (for completed sessions)
    if session_doc.get("status") == "ended":
        from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
        
        moves_data = []
        pgn = session_doc.get("pgn", "")
        user_color = session_doc.get("user_color", "white")
        is_user_white = user_color.lower() == "white"
        
        # Parse PGN and generate coaching for each move
        try:
            import chess.pgn
            import io
            
            game = chess.pgn.read_game(io.StringIO(pgn))
            if game:
                board = game.board()
                move_number = 0
                
                for move in game.mainline_moves():
                    move_number += 1
                    is_user_move = (board.turn == chess.WHITE) == is_user_white
                    fen_before = board.fen()
                    move_san = board.san(move)
                    
                    # Determine phase
                    fullmove = board.fullmove_number
                    if fullmove <= 10:
                        phase = "opening"
                    elif fullmove <= 30:
                        phase = "middlegame"
                    else:
                        phase = "endgame"
                    
                    # Get evaluation data if available
                    move_evals = session_doc.get("move_evaluations", [])
                    eval_data = next((e for e in move_evals if e.get("move_number") == move_number), {})
                    
                    context = CoachingContext.LIVE_AFTER_USER if is_user_move else CoachingContext.LIVE_AFTER_COACH
                    
                    coaching = await generate_move_coaching(
                        board_before=board,
                        move=move,
                        best_move_san=eval_data.get("best_move"),
                        pv_after_played=eval_data.get("pv_after_played", []),
                        pv_after_best=eval_data.get("pv_after_best", []),
                        cp_loss=eval_data.get("cp_loss", 0),
                        phase=phase,
                        is_user_move=is_user_move,
                        context=context,
                        user_color=user_color
                    )
                    
                    board.push(move)
                    
                    moves_data.append({
                        "move_number": move_number,
                        "move_san": move_san,
                        "fen_before": fen_before,
                        "fen_after": board.fen(),
                        "is_user_move": is_user_move,
                        **coaching.to_dict()
                    })
                
                # Cache the V5 data
                await db.coach_sessions.update_one(
                    {"session_id": session_id},
                    {"$set": {"v5_coaching_data": moves_data}}
                )
                
                return {"moves": moves_data, "cached": False}
        except Exception as e:
            logger.error(f"Error generating V5 session coaching: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return {"moves": [], "message": "Session still in progress"}
