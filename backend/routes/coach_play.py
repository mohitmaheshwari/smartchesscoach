"""
Coach Play Routes — ALL coach/play endpoints live here.
=========================================================

Handles the "Play with Coach" feature including:
- Starting/ending sessions (start, end)
- Making moves (move, move/confirm, undo)
- Real-time feedback (messages, state, feedback, behaviors)
- Coaching (reflect, chat, evaluate, analysis)
- Opening curriculum (opening-guide, opening-assessment, pregame-intro)
- Candidate moves + position reader
- Endgame lessons
- Teaching mode

Fully extracted from server.py (April 2026).
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime, timezone
import logging
import chess

logger = logging.getLogger(__name__)

def _detect_opening_from_moves(moves: list, user_color: str) -> str:
    """Detect which curriculum opening matches these moves."""
    from services.opening_curriculum_engine import _load_curriculum
    curriculum = _load_curriculum()

    best_match = None
    best_depth = 0

    for key, opening in curriculum.items():
        if opening.get("color") != user_color:
            continue
        tree = opening.get("tree", {})
        if not tree:
            continue

        # Try to walk the tree with these moves
        first_key = list(tree.keys())[0]
        if not moves or moves[0] != first_key:
            continue

        # Walk as deep as possible
        depth = 1
        node = tree[first_key]
        for i in range(1, len(moves)):
            move = moves[i]
            is_user = (i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black")

            if not is_user:
                responses = node.get("responses", {})
                if move in responses:
                    node = responses[move]
                    depth += 1
                else:
                    break
            else:
                expected = node.get("next")
                if expected and move == expected:
                    depth += 1
                else:
                    break

        if depth > best_depth:
            best_depth = depth
            best_match = key

    return best_match



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
                    from services.pattern_memory_service import get_pattern_for_mistake
                    
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


@router.post("/candidates")
async def get_candidate_moves(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get 3 best candidate moves for the current position with simple explanations.
    
    This is the CORE of smart coaching — shows the player what to think about
    BEFORE they move. Each candidate has a plain-English explanation of its idea.
    
    Body:
    - session_id: Current game session
    
    Returns:
    - candidates: [{move, idea, move_type, is_best}]
    - position_hint: A simple hint about what to look for in this position
    """
    global db
    import chess
    from services.shared_coaching_v5 import get_stockfish_candidates

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

    current_fen = session_doc.get("current_fen")
    if not current_fen:
        raise HTTPException(status_code=400, detail="No position available")

    try:
        board = chess.Board(current_fen)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid position")

    # Get top 3 moves from Stockfish with ideas
    candidates = await get_stockfish_candidates(board, num_moves=3, depth=10)

    result = []
    for c in candidates:
        result.append({
            "move": c.move,
            "idea": c.idea,
            "move_type": c.move_type,
            "is_best": c.is_best,
        })

    # Generate a simple position hint
    hint = _generate_position_hint(board)

    return {
        "candidates": result,
        "position_hint": hint,
        "fen": current_fen,
    }


def _generate_position_hint(board: chess.Board) -> str:
    """Simple hint about what to focus on in this position."""
    import chess

    move_count = board.fullmove_number

    # Opening
    if move_count <= 5:
        undeveloped = 0
        back_rank = 0 if board.turn == chess.WHITE else 7
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                if chess.square_rank(sq) == back_rank:
                    undeveloped += 1

        if undeveloped >= 2:
            return "Get your pieces out! Develop knights and bishops toward the center."
        if not board.has_castling_rights(board.turn):
            return "Good — you've castled. Now think about what your pieces are aiming at."
        if board.has_castling_rights(board.turn):
            return "Think about castling soon. Get your king safe."
        return "Control the center. Develop your pieces."

    # Check if in check
    if board.is_check():
        return "You're in check. Deal with it first."

    # Middlegame
    if move_count <= 25:
        # Check for hanging pieces
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color != board.turn and piece.piece_type != chess.KING:
                if board.is_attacked_by(board.turn, sq) and not board.is_attacked_by(not board.turn, sq):
                    return "Look carefully — your opponent has an undefended piece. Can you take it?"

        return "Look for captures, checks, and threats. What's the most active move?"

    # Endgame
    return "Endgame time. Push your passed pawns and activate your king."


@router.post("/opening-guide")
async def get_opening_guide(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Get curriculum-based opening guidance for the current game position.
    
    Reads from the opening curriculum tree and tells the player:
    - What to play next (and why)
    - The plan going forward
    - Any trap warnings
    - A golden rule to remember
    
    Body:
    - session_id: Current game session
    - opening_key: Which opening curriculum to use (default: auto-detect)
    """
    global db
    from services.opening_curriculum_engine import get_opening_guidance

    session_id = request.get("session_id")
    opening_key = request.get("opening_key") or session_doc.get("teaching_opening") if session_id else None

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    user_color = session_doc.get("user_color", "white")

    # Get move history as SAN list
    move_history = session_doc.get("move_history", [])
    moves_san = []
    for m in move_history:
        if isinstance(m, dict):
            moves_san.append(m.get("san", m.get("move", "")))
        elif isinstance(m, str):
            moves_san.append(m)

    # Auto-detect opening from moves (after 3+ moves)
    if not opening_key and len(moves_san) >= 3:
        opening_key = _detect_opening_from_moves(moves_san, user_color)
        if opening_key:
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"teaching_opening": opening_key}}
            )
    
    # Still no opening detected — too early or unknown
    if not opening_key:
        opening_key = session_doc.get("teaching_opening")

    # Get user's assessment of this opening (cached per session)
    assessment = session_doc.get("opening_assessment")
    if not assessment:
        from services.opening_assessment_service import assess_opening_knowledge
        assessment = await assess_opening_knowledge(db, user.user_id, opening_key)
        # Cache it on the session so we don't re-compute every move
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"opening_assessment": assessment}}
        )

    guidance = get_opening_guidance(opening_key, moves_san, user_color, assessment=assessment)

    # Detect opening + user's performance after 2+ moves
    opening_info = None
    if len(moves_san) >= 3 and opening_key:
        from services.opening_curriculum_engine import _load_curriculum
        curriculum = _load_curriculum()
        opening_data = curriculum.get(opening_key, {})
        opening_name = opening_data.get("name", "")
        
        # Get user's stats for this opening from their games
        games_played = assessment.get("games_played", 0) if assessment else 0
        score = assessment.get("overall_score", 0) if assessment else 0
        
        if games_played == 0:
            status = "new"
            message = f"New opening! Let's learn the {opening_name} together."
        elif score >= 80:
            status = "strong"
            message = f"You know this well — {score}% accuracy from {games_played} games. Let's sharpen it."
        elif score >= 50:
            status = "learning"
            message = f"Getting there — {score}% accuracy from {games_played} games. Let's improve."
        else:
            status = "weak"
            message = f"Needs work — {score}% accuracy from {games_played} games. Focus time."
        
        opening_info = {
            "name": opening_name,
            "games_played": games_played,
            "score": score,
            "status": status,
            "message": message,
        }

    # ALWAYS include commentary about the coach's last move
    coach_move_commentary = None
    # Track the last coach move SAN for frontend display
    last_opponent_move_san = None
    if move_history:
        last_move = move_history[-1]
        if isinstance(last_move, dict) and last_move.get("by") == "coach":
            last_san = last_move.get("san", last_move.get("move", ""))
            last_fen = last_move.get("fen_before", "")
            last_opponent_move_san = last_san
            
            # Use curriculum commentary if available
            if guidance and guidance.get("opponent_commentary"):
                coach_move_commentary = guidance["opponent_commentary"]
            elif last_san and last_fen:
                try:
                    from services.move_intent_analyzer import analyze_move_intent
                    intent = analyze_move_intent(last_fen, last_san)
                    # Fix perspective — analyzer says "You" but this is the opponent
                    desc = intent.description.replace("You ", "Opponent ").replace("Your ", "Their ")
                    coach_move_commentary = desc
                except Exception:
                    coach_move_commentary = f"Opponent played {last_san}."
            elif last_san:
                coach_move_commentary = f"Opponent played {last_san}."

    if not guidance:
        result = {
            "has_guidance": coach_move_commentary is not None,
            "message": "Past the opening — play your best.",
            "opponent_commentary": coach_move_commentary,
            "last_opponent_move": last_opponent_move_san,
            "mode": "free",
        }
        if opening_info:
            result["opening_info"] = opening_info
        return result

    if coach_move_commentary:
        guidance["opponent_commentary"] = coach_move_commentary
    guidance["last_opponent_move"] = last_opponent_move_san

    result = {"has_guidance": True, **guidance}
    if opening_info:
        result["opening_info"] = opening_info
    return result


@router.get("/curriculum/openings")
async def get_curriculum_openings(user: User = Depends(get_current_user)):
    """Get available opening curriculums."""
    from services.opening_curriculum_engine import get_available_openings, get_opening_summary

    openings = get_available_openings()
    result = []
    for o in openings:
        summary = get_opening_summary(o["key"])
        result.append({**o, **(summary or {})})

    return {"openings": result}


@router.post("/smart-feedback")
async def get_smart_move_feedback(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Smart coaching feedback — analyzes WHAT the player was trying to do,
    acknowledges their intent, then explains if there's something better.
    
    Rating-filtered: doesn't comment on minor inaccuracies for low-rated players.
    
    Body:
    - session_id: Current game session
    - move_san: The move the player just made
    - fen_before: Position before the move
    """
    global db
    import chess
    from services.smart_coach_feedback import generate_smart_feedback
    from stockfish_service import StockfishEngine

    session_id = request.get("session_id")
    move_san = request.get("move_san")
    fen_before = request.get("fen_before")

    if not all([session_id, move_san, fen_before]):
        raise HTTPException(status_code=400, detail="session_id, move_san, and fen_before required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    # Get user rating
    user_rating = session_doc.get("user_rating", 1200)

    # Get Stockfish evaluation
    best_move_san = ""
    cp_loss = 0
    eval_before = 0
    eval_after = 0
    is_best = False
    is_candidate = False

    try:
        engine = StockfishEngine()
        engine.start()
        try:
            board = chess.Board(fen_before)
            eval_before_cp, _ = engine.evaluate_position(board, depth=14)
            eval_before = eval_before_cp / 100.0

            # Get best move
            best_info = engine.get_best_move(board, depth=14)
            if best_info:
                best_move_obj = best_info.get("move")
                if best_move_obj:
                    best_move_san = board.san(best_move_obj)

            # Check top 3 for candidate
            result = engine.analyze_multipv(board, depth=12, num_moves=3)
            top_moves = [board.san(r["move"]) for r in (result or []) if "move" in r]
            is_best = move_san == best_move_san
            is_candidate = move_san in top_moves

            # Eval after
            user_move = board.parse_san(move_san)
            board.push(user_move)
            eval_after_cp, _ = engine.evaluate_position(board, depth=14)
            eval_after = eval_after_cp / 100.0

            # Calculate cp_loss from user's perspective
            user_color = session_doc.get("user_color", "white")
            if user_color == "white":
                cp_loss = max(0, int(eval_before_cp - eval_after_cp))
            else:
                cp_loss = max(0, int(eval_after_cp - eval_before_cp))

        finally:
            engine.stop()
    except Exception as e:
        logger.warning(f"Stockfish eval failed: {e}")

    feedback = generate_smart_feedback(
        fen=fen_before,
        move_san=move_san,
        best_move_san=best_move_san,
        cp_loss=cp_loss,
        user_rating=user_rating,
        eval_before=eval_before,
        eval_after=eval_after,
        is_best=is_best,
        is_candidate=is_candidate,
    )

    if feedback is None:
        return {"has_feedback": False, "message": ""}

    return {"has_feedback": True, **feedback}


@router.get("/opening-assessment")
async def get_opening_assessment(
    opening: str = "london_system",
    user: User = Depends(get_current_user)
):
    """
    Assess user's knowledge of a specific opening from their game history.
    
    Returns what they know, what they don't, and what to train next.
    """
    global db
    from services.opening_assessment_service import assess_opening_knowledge

    result = await assess_opening_knowledge(db, user.user_id, opening)
    return result


@router.get("/pregame-intro")
async def get_pregame_intro_endpoint(
    opening: str = "london_system",
    user: User = Depends(get_current_user)
):
    """
    Get the pre-game introduction for structured training.
    
    Shows before "Start Game":
    - What opening we're learning
    - What the user already knows
    - What we'll focus on today
    """
    global db
    from services.opening_assessment_service import get_pregame_intro

    return await get_pregame_intro(db, user.user_id, opening)


@router.post("/read-position")
async def read_position_endpoint(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Read a position — what should the player NOTICE?
    Returns top 2-3 features adapted to rating.
    """
    global db
    from services.position_reader import read_position

    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    fen = session_doc.get("current_fen")
    user_color = session_doc.get("user_color", "white")
    user_rating = session_doc.get("user_rating", 1200)

    return read_position(fen, user_color, user_rating)


@router.get("/opening-suggestions")
async def get_opening_suggestions(user: User = Depends(get_current_user)):
    """
    Get personalized opening suggestions for Play with Coach.
    Shows what the user plays, how well, and what to learn next.
    """
    global db
    from services.opening_curriculum_engine import get_available_openings

    # Get user's actual opening stats from their games
    white_openings = []
    black_openings = []

    games = await db.games.find(
        {"user_id": user.user_id, "opening_name": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "game_id": 1, "opening_name": 1, "opening": 1, "result": 1, "user_color": 1}
    ).sort("imported_at", -1).limit(100).to_list(100)

    # Group by color and opening
    for color_label, color_list in [("white", white_openings), ("black", black_openings)]:
        color_games = [g for g in games if g.get("user_color") == color_label]
        opening_map = {}

        for g in color_games:
            name = g.get("opening_name") or g.get("opening") or "Unknown"
            short = " ".join(name.split()[:3])
            if short not in opening_map:
                opening_map[short] = {"name": name, "games": 0, "wins": 0, "losses": 0, "draws": 0}

            opening_map[short]["games"] += 1
            result = g.get("result", "")
            user_won = (result == "1-0" and color_label == "white") or (result == "0-1" and color_label == "black")
            user_lost = (result == "0-1" and color_label == "white") or (result == "1-0" and color_label == "black")
            if user_won:
                opening_map[short]["wins"] += 1
            elif user_lost:
                opening_map[short]["losses"] += 1
            else:
                opening_map[short]["draws"] += 1

        sorted_openings = sorted(opening_map.values(), key=lambda x: x["games"], reverse=True)

        for o in sorted_openings[:5]:
            total = o["games"]
            win_rate = round(o["wins"] / total * 100) if total > 0 else 0
            
            # Determine status
            if total >= 5 and win_rate >= 60:
                status = "strong"
                status_label = "You play this well"
            elif total >= 3 and win_rate >= 40:
                status = "learning"
                status_label = "Getting there"
            elif total >= 3 and win_rate < 40:
                status = "weak"
                status_label = "Needs work"
            else:
                status = "new"
                status_label = "Just started"

            color_list.append({
                "name": o["name"],
                "games": total,
                "wins": o["wins"],
                "losses": o["losses"],
                "win_rate": win_rate,
                "status": status,
                "status_label": status_label,
            })

    # Available curriculums
    available = get_available_openings()

    # Suggest what to learn
    suggestion = None
    if not white_openings:
        suggestion = {"message": "You haven't played many games yet. Start with the London System — it's solid and easy to learn.", "opening_key": "london_system"}
    else:
        weak = [o for o in white_openings if o["status"] == "weak"]
        if weak:
            suggestion = {"message": f"Your {weak[0]['name']} needs work ({weak[0]['win_rate']}% win rate). Let's fix that.", "opening_key": None}
        elif len(white_openings) <= 2:
            suggestion = {"message": "You only play 1-2 openings. Adding the London System gives you a backup.", "opening_key": "london_system"}

    return {
        "white": white_openings,
        "black": black_openings,
        "available_curriculums": [{"key": a["key"], "name": a["name"], "color": a["color"]} for a in available],
        "suggestion": suggestion,
        "total_games": len(games),
    }


# ══════════════════════════════════════════════════════════════════════
# MIGRATED FROM server.py — Start, Move, and Process Move
# ══════════════════════════════════════════════════════════════════════

@router.post("/start")
async def start_play_with_coach(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Start a new Play With Coach session.
    
    Body:
    - user_color: "white" or "black" (default: "white")
    - time_control: Time format like "15+10" (default: "15+10" rapid)
    - starting_fen: Custom starting position (optional, for practice mode)
    - practice_mode: Whether this is practice mode (optional)
    - source_game_id: Game ID this practice is from (optional)
    
    Returns:
    - session_id: Unique session ID
    - session: Full session state
    - current_fen: Current board position
    - is_player_turn: Whether it's the player's turn
    - evaluation: Position evaluation for eval bar
    """
    from coach_play import start_coach_session
    from coach_play.coach_opponent import CoachOpponent
    global db, call_llm
    
    user_color = request.get("user_color", "white")
    time_control = request.get("time_control", "15+10")
    starting_fen = request.get("starting_fen", None)
    practice_mode = request.get("practice_mode", False)
    source_game_id = request.get("source_game_id", None)
    opening_key = request.get("opening_key", None)  # Curriculum opening to teach
    
    # Validate user_color
    if user_color not in ["white", "black"]:
        raise HTTPException(status_code=400, detail="user_color must be 'white' or 'black'")
    
    try:
        session = await start_coach_session(
            db=db,
            user_id=user.user_id,
            user_color=user_color,
            time_control=time_control,
            starting_fen=starting_fen,
            practice_mode=practice_mode,
            source_game_id=source_game_id
        )
        
        # Get initial evaluation
        opponent = CoachOpponent(user_rating=session.user_rating)
        eval_score, mate_in = await opponent.get_evaluation(session.current_fen)
        
        # Determine whose turn it is based on FEN
        fen_parts = session.current_fen.split(' ')
        to_move = fen_parts[1] if len(fen_parts) > 1 else 'w'
        is_player_turn = (to_move == 'w' and user_color == 'white') or (to_move == 'b' and user_color == 'black')
        
        message = f"Game started! You are playing {user_color}."
        if practice_mode:
            message = f"Practice mode! Playing from a position in your game. You are {user_color}."
        
        # Get memory-aware welcome message from Coach Memory + Human Coach
        welcome_message = message
        coaching_context = {}
        opening_guidance = None
        
        try:
            # Get coaching context from memory
            from services.coach_memory import get_coaching_context, get_personalized_greeting
            from services.opening_mastery import suggest_opening_for_session
            
            coaching_context = await get_coaching_context(db, user.user_id)
            try:
                personalized_greeting = await get_personalized_greeting(db, user.user_id)
            except Exception as greet_err:
                logger.warning(f"Coach memory greeting failed: {greet_err}")
                personalized_greeting = "Let's play!"
            
            # OPENING SELECTION: Use curriculum if specified, else old system
            if not practice_mode:
                if opening_key:
                    # Use our structured curriculum system
                    from services.opening_assessment_service import get_pregame_intro
                    pregame = await get_pregame_intro(db, user.user_id, opening_key)
                    
                    welcome_message = pregame.get("intro", personalized_greeting)
                    
                    # Update both MongoDB AND in-memory session
                    session.curriculum_active = True
                    session.teaching_opening = opening_key
                    session.opening_assessment = pregame.get("assessment")
                    
                    await db.coach_sessions.update_one(
                        {"session_id": session.session_id},
                        {"$set": {
                            "teaching_opening": opening_key,
                            "opening_assessment": pregame.get("assessment"),
                            "curriculum_active": True,
                            "opening_teaching_active": False,
                        }}
                    )
                else:
                    # Fallback: old system picks an opening
                    opening_guidance = await suggest_opening_for_session(
                        db, user.user_id, user_color, session.user_rating
                    )
                    
                    if opening_guidance:
                        await db.coach_sessions.update_one(
                            {"session_id": session.session_id},
                            {"$set": {
                                "opening_to_teach": opening_guidance["opening_key"],
                                "opening_teaching_moves": opening_guidance["full_moves"],
                                "opening_teaching_index": 0,
                                "opening_teaching_active": True,
                                "suggested_trap": opening_guidance.get("suggested_trap"),
                                "available_traps": opening_guidance.get("traps", [])
                            }}
                        )
                        welcome_message = f"{personalized_greeting}\n\n{opening_guidance['teaching_message']}"
                        if is_player_turn:
                            first_move = opening_guidance["first_moves"][0] if opening_guidance["first_moves"] else None
                            if first_move:
                                welcome_message += f"\n\nYour first move: Play **{first_move}** to start."
                    else:
                        welcome_message = personalized_greeting
                        if coaching_context.get("focus_suggestion"):
                            welcome_message += f" {coaching_context['focus_suggestion']}."
            else:
                # Practice mode - use standard personalized greeting
                welcome_message = personalized_greeting
                
                # Add focus suggestion if available
                if coaching_context.get("focus_suggestion"):
                    welcome_message += f" {coaching_context['focus_suggestion']}."
            
            # Surface any recurring patterns
            if coaching_context.get("watch_for"):
                top_weakness = coaching_context["watch_for"][0] if coaching_context["watch_for"] else None
                if top_weakness and top_weakness["count"] >= 3:
                    welcome_message += f"\n\nRemember: Watch out for {top_weakness['name']} - let's work on that today!"
            
            # Try Human Coach as fallback/enhancement — but NOT when curriculum is active
            if not opening_key:
                try:
                    from services.human_coach_service import create_human_coach
                    coach = await create_human_coach(db, user.user_id, session.user_rating)
                    human_welcome = await coach.get_welcome_message()
                    
                    # Use human coach message if it's more personal
                    if len(human_welcome) > len(welcome_message):
                        welcome_message = human_welcome
                        
                    if starting_fen:
                        memory_note = await coach.surface_relevant_memory(current_fen=starting_fen)
                        if memory_note:
                            welcome_message = f"{welcome_message}\n\n{memory_note}"
                except Exception as e:
                    logger.warning(f"Human coach welcome failed: {e}")
                
        except Exception as e:
            logger.warning(f"Coach memory greeting failed: {e}")
            welcome_message = message
        
        return {
            "success": True,
            "session_id": session.session_id,
            "session": session.to_dict(),
            "current_fen": session.current_fen,
            "is_player_turn": is_player_turn,
            "message": welcome_message,
            "opening_key": opening_key,
            "evaluation": {
                "score": eval_score,
                "mate_in": mate_in
            },
            "practice_mode": practice_mode
        }
    except Exception as e:
        logger.error(f"Error starting coach session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move")
async def make_coach_play_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Make a move in the Play With Coach session.
    
    Flow:
    1. User's move is validated and recorded (FAST)
    2. Returns immediately - coach will respond async
    3. Background: Analyze → Generate message → Make coach move
    4. Frontend polls for messages and coach move
    
    Body:
    - session_id: Session ID
    - move: Move in SAN notation (e.g., "e4", "Nf3", "O-O")
    - time_spent: Time spent on this move in seconds (optional)
    
    Returns:
    - success: bool
    global db
    - user_move_recorded: True if move was valid
    - current_fen: Position after user's move
    - awaiting_coach: True (coach will respond async)
    """
    import asyncio
    import chess
    from datetime import datetime, timezone
    
    session_id = request.get("session_id")
    move = request.get("move")
    time_spent = request.get("time_spent", 0.0)
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not move:
        raise HTTPException(status_code=400, detail="move is required")
    
    # Get session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    # Store context - ensure FEN is never null
    fen_before = session_doc.get("current_fen")
    if not fen_before:
        fen_history = session_doc.get("fen_history", [])
        if fen_history:
            fen_before = fen_history[-1]
        else:
            fen_before = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    user_rating = session_doc.get("user_rating", 1200)
    user_color = session_doc.get("user_color", "white")
    
    # CURRICULUM ENFORCEMENT: Check if move matches the curriculum's expected move
    curriculum_active = session_doc.get("curriculum_active", False)
    curriculum_feedback = None
    if curriculum_active:
        teaching_opening = session_doc.get("teaching_opening")
        if teaching_opening:
            from services.opening_curriculum_engine import get_opening_guidance
            assessment = session_doc.get("opening_assessment")
            move_history_san = [m.get("move", "") for m in session_doc.get("move_history", [])]
            guidance = get_opening_guidance(teaching_opening, move_history_san, user_color, assessment=assessment)
            
            # Only compare to curriculum when we're IN the book
            if guidance and guidance.get("is_in_book") and guidance.get("mode") == "think" and guidance.get("expected_move"):
                expected = guidance["expected_move"]
                moves_match = False
                try:
                    check_board = chess.Board(fen_before)
                    user_uci = check_board.parse_san(move).uci()
                    expected_uci = check_board.parse_san(expected).uci()
                    moves_match = (user_uci == expected_uci)
                except Exception:
                    moves_match = (move == expected)
                
                if moves_match:
                    curriculum_feedback = guidance.get("right_feedback", "Good move.")
                else:
                    # First time off-book — explain what the curriculum wanted, then let it go
                    wrong_fb = guidance.get("wrong_feedback", "")
                    curriculum_feedback = f"{wrong_fb}" if wrong_fb else f"The curriculum move was {expected} here. But that's OK."
            
            # If already off-book, don't nag. Use move intent analyzer instead.
            elif guidance and not guidance.get("is_in_book"):
                try:
                    from services.move_intent_analyzer import analyze_move_intent
                    intent = analyze_move_intent(fen_before, move)
                    if intent.is_reasonable:
                        curriculum_feedback = intent.feedback
                    else:
                        curriculum_feedback = f"{intent.description} {intent.feedback}"
                except Exception:
                    pass  # No feedback is better than bad feedback
    
    # Validate and record user's move ONLY (fast)
    try:
        board = chess.Board(fen_before)
        chess_move = board.parse_san(move)
        
        # Record user's move
        board.push(chess_move)
        fen_after_user = board.fen()
        
        move_history = session_doc.get("move_history", [])
        move_number = len([m for m in move_history if m.get("by") == "player"]) + 1
        
        # Add user's move to history
        move_history.append({
            "move": move,
            "uci": chess_move.uci(),
            "by": "player",
            "fen_before": fen_before,
            "fen_after": fen_after_user,
            "time_spent": time_spent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        action_revision = session_doc.get("action_revision", 0) + 1

        # Update session with user's move (coach move pending)
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "current_fen": fen_after_user,
                "move_history": move_history,
                "coach_move_pending": True,
                "action_revision": action_revision
            }}
        )
        
        # Check if game is over after user's move
        game_over = board.is_game_over()
        result = None
        if game_over:
            if board.is_checkmate():
                result = "win"  # User checkmated opponent
            elif board.is_stalemate() or board.is_insufficient_material():
                result = "draw"
        
        # Fire background task: analyze → message → coach move
        asyncio.create_task(
            _process_move_and_respond(
                session_id=session_id,
                user_move=move,
                fen_before=fen_before,
                fen_after_user=fen_after_user,
                user_rating=user_rating,
                user_color=user_color,
                move_number=move_number,
                game_over=game_over,
                expected_action_revision=action_revision
            )
        )
        
        return {
            "success": True,
            "user_move_recorded": True,
            "move": move,
            "current_fen": fen_after_user,
            "awaiting_coach": not game_over,
            "game_over": game_over,
            "result": result,
            "curriculum_feedback": curriculum_feedback,
        }
        
    except chess.InvalidMoveError:
        raise HTTPException(status_code=400, detail="Invalid move")
    except chess.AmbiguousMoveError:
        raise HTTPException(status_code=400, detail="Ambiguous move - please be more specific")
    except Exception as e:
        logger.error(f"Error processing move: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _classify_move(eval_before: float, eval_after: float, user_color: str) -> str:
    """Classify a move as blunder, mistake, inaccuracy, or good based on centipawn loss."""
    # Calculate centipawn loss from user's perspective
    if user_color == "white":
        cp_loss = (eval_before - eval_after) * 100  # Positive means user lost eval
    else:
        cp_loss = (eval_after - eval_before) * 100  # For black, eval going down is good
    
    if cp_loss >= 300:
        return "blunder"
    elif cp_loss >= 100:
        return "mistake"
    elif cp_loss >= 50:
        return "inaccuracy"
    else:
        return "good"


async def _apply_coach_move(db, session_id: str, fen: str, coach_move_san: str, move_history: list) -> bool:
    """
    ONE function to apply a coach move. ALL paths use this.
    Sets: current_fen, move_history, coach_move_pending, last_coach_move, status.
    Returns True if successful.
    """
    import chess as _chess
    try:
        board = _chess.Board(fen)
        chess_move = board.parse_san(coach_move_san)
        board.push(chess_move)
        fen_after = board.fen()

        move_history.append({
            "move": coach_move_san,
            "san": coach_move_san,
            "uci": chess_move.uci(),
            "by": "coach",
            "fen_before": fen,
            "fen_after": fen_after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        update = {
            "current_fen": fen_after,
            "move_history": move_history,
            "coach_move_pending": False,
            "last_coach_move": {
                "move": coach_move_san,
                "san": coach_move_san,
                "uci": chess_move.uci(),
            },
        }

        # Check game over
        if board.is_game_over():
            if board.is_checkmate():
                update["status"] = "completed"
                update["result"] = "loss"
            elif board.is_stalemate() or board.is_insufficient_material():
                update["status"] = "completed"
                update["result"] = "draw"

        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": update}
        )
        logger.info(f"[COACH MOVE] {coach_move_san} applied to {session_id}")
        return True

    except Exception as e:
        logger.error(f"[COACH MOVE] Failed to apply {coach_move_san}: {e}")
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"coach_move_pending": False}}
        )
        return False



async def _process_move_and_respond(
    session_id: str,
    user_move: str,
    fen_before: str,
    fen_after_user: str,
    user_rating: int,
    user_color: str,
    move_number: int,
    game_over: bool,
    expected_action_revision: int,
):
    """
    Background task: Analyze user's move, generate message, then make coach's move.
    
    Order:
    1. Analyze user's move with Stockfish
    2. Generate coach message if triggered
    3. Make coach's responding move
    4. Store everything for frontend to poll
    """
    from coach_play.coach_commentary import get_quick_analysis
    from coach_play.coaching_triggers import should_coach_speak
    from coach_play.coach_opponent import CoachOpponent
    from datetime import datetime, timezone
    import chess

    async def _is_current_revision() -> bool:
        current_doc = await db.coach_sessions.find_one(
            {"session_id": session_id},
            {"_id": 0, "action_revision": 1},
        )
        return bool(current_doc) and current_doc.get("action_revision", 0) == expected_action_revision
    
    try:
        # FAST PATH: When curriculum is active, skip heavy analysis
        session_doc_check = await db.coach_sessions.find_one({"session_id": session_id})
        if session_doc_check and session_doc_check.get("curriculum_active") and not game_over:
            from services.coach_move_pipeline import get_curriculum_coach_move, get_simple_coach_move
            import asyncio as _asyncio
            
            move_history = session_doc_check.get("move_history", [])
            
            # Try curriculum first (instant)
            coach_move_san = await get_curriculum_coach_move(db, session_doc_check, user_color)
            
            # Fallback to simple Stockfish
            if not coach_move_san:
                coach_move_san = await get_simple_coach_move(db, fen_after_user, user_rating)
            
            if coach_move_san:
                await _asyncio.sleep(1.5)  # Brief pause for UX
                success = await _apply_coach_move(db, session_id, fen_after_user, coach_move_san, move_history)
                if success:
                    return
            
            # Both failed — don't fall through to heavy path
            logger.warning(f"Curriculum: no move found for {session_id}")
            await db.coach_sessions.update_one(
                {"session_id": session_id}, {"$set": {"coach_move_pending": False}})
            return
        
        # NORMAL PATH: Full analysis + coaching
        # Step 1: Quick analysis of user's move
        analysis = await get_quick_analysis(
            fen_before=fen_before,
            move_san=user_move,
            fen_after=fen_after_user,
            user_color=user_color,
            move_number=move_number
        )
        
        # Step 2: Check if coach should comment
        trigger = should_coach_speak(
            user_rating=user_rating,
            move_san=user_move,
            eval_before=analysis["eval_before"],
            eval_after=analysis["eval_after"],
            is_best_move=analysis["is_best_move"],
            is_candidate=analysis["is_candidate"],
            best_move_san=analysis["best_move"],
            phase=analysis["phase"],
            move_number=move_number,
            opening_name=analysis.get("opening_name")
        )
        
        # === CRITICAL: Store evaluations in move_history for post-game analysis ===
        if not await _is_current_revision():
            logger.info(f"Skipping stale coach task for session {session_id}")
            return

        session_doc = await db.coach_sessions.find_one({"session_id": session_id})
        if session_doc:
            move_history = session_doc.get("move_history", [])
            # Find and update the last user move with evaluations
            for i in range(len(move_history) - 1, -1, -1):
                if move_history[i].get("move") == user_move and move_history[i].get("by") == "player":
                    move_history[i]["eval_before"] = analysis.get("eval_before", 0)
                    move_history[i]["eval_after"] = analysis.get("eval_after", 0)
                    move_history[i]["is_best_move"] = analysis.get("is_best_move", False)
                    move_history[i]["best_move"] = analysis.get("best_move")
                    move_history[i]["evaluation"] = _classify_move(
                        analysis.get("eval_before", 0),
                        analysis.get("eval_after", 0),
                        user_color
                    )
                    break
            
            # Store evaluations list for post-game analysis
            evaluations = session_doc.get("evaluations", [])
            evaluations.append({
                "move_number": move_number,
                "move": user_move,
                "by": "player",
                "score": analysis.get("eval_after", 0),
                "eval_before": analysis.get("eval_before", 0),
                "eval_after": analysis.get("eval_after", 0),
                "best_move": analysis.get("best_move")
            })
            
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "move_history": move_history,
                    "evaluations": evaluations
                }}
            )
            
            # === OPENING TEACHING: Advance teaching index if correct move played ===
            if session_doc.get("opening_teaching_active"):
                teaching_moves = session_doc.get("opening_teaching_moves", [])
                teaching_index = session_doc.get("opening_teaching_index", 0)
                
                if teaching_index < len(teaching_moves):
                    expected_move = teaching_moves[teaching_index]
                    # Check if user played the expected opening move
                    if user_move.lower().replace("+", "").replace("#", "") == expected_move.lower().replace("+", "").replace("#", ""):
                        # Correct move! Advance the teaching index by 2 (user move + upcoming coach move)
                        new_index = teaching_index + 2
                        
                        if new_index >= len(teaching_moves):
                            # Opening identifying sequence complete
                            # But DON'T say "completed" if we have deep variations to teach
                            opening_obj = None
                            try:
                                from coach_engine.opening_plans import get_opening_by_moves
                                session_d = await db.coach_sessions.find_one({"session_id": session_id})
                                mh = session_d.get("move_history", []) if session_d else []
                                all_m = [m.get("move", "") for m in mh if m.get("move")]
                                opening_obj = get_opening_by_moves(all_m)
                            except Exception:
                                pass
                            
                            has_deep_variations = opening_obj and getattr(opening_obj, 'variations', None)
                            
                            await db.coach_sessions.update_one(
                                {"session_id": session_id},
                                {"$set": {
                                    "opening_teaching_active": False,
                                    "opening_teaching_complete": True,
                                    "opening_teaching_index": new_index
                                }}
                            )
                            
                            # Only show completion if no deep variations exist
                            if not has_deep_variations:
                                await db.coach_messages.insert_one({
                                    "session_id": session_id,
                                    "type": "coach",
                                    "message": f"Excellent! You've completed the opening! Now let's play freely. Remember the key ideas we learned!",
                                    "trigger": "opening_complete",
                                    "created_at": datetime.now(timezone.utc),
                                    "read": False
                                })
                        else:
                            await db.coach_sessions.update_one(
                                {"session_id": session_id},
                                {"$set": {"opening_teaching_index": new_index}}
                            )
        
        # Step 3: MOVE-BY-MOVE COACHING for opening phase
        # During opening, ALWAYS generate a commentary message (not trigger-dependent)
        opening_commentary_sent = False
        if move_number <= 15:
            try:
                if not await _is_current_revision():
                    logger.info(f"Skipping stale opening commentary for session {session_id}")
                    return
                from services.move_by_move_coach import generate_move_commentary
                from coach_engine.opening_plans import build_opening_coaching_context
                
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                move_history = session_doc.get("move_history", []) if session_doc else []
                all_moves_san = [m.get("move", "") for m in move_history if m.get("move")]
                
                opening_plan = build_opening_coaching_context(all_moves_san)
                
                commentary = generate_move_commentary(
                    fen_before=fen_before,
                    fen_after=fen_after_user,
                    move_san=user_move,
                    move_by="user",
                    all_moves=all_moves_san,
                    user_color=user_color,
                    user_rating=user_rating,
                    opening_plan=opening_plan,
                    eval_before=analysis.get("eval_before", 0),
                    eval_after=analysis.get("eval_after", 0),
                    is_best_move=analysis.get("is_best_move", True),
                    best_move_san=analysis.get("best_move", ""),
                )
                
                if commentary.message:
                    msg_doc = {
                        "session_id": session_id,
                        "type": "coach",
                        "message": commentary.message,
                        "trigger": "opening_teaching",
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "move_quality": commentary.move_quality,
                        "teaching_type": commentary.teaching_type,
                    }
                    if commentary.question:
                        msg_doc["question"] = {"prompt": commentary.question}
                    if commentary.trap_warning:
                        msg_doc["trap_warning"] = commentary.trap_warning
                    if commentary.next_hint:
                        msg_doc["next_hint"] = commentary.next_hint
                    if commentary.pattern_note:
                        msg_doc["pattern_note"] = commentary.pattern_note
                    
                    await db.coach_messages.insert_one(msg_doc)
                    opening_commentary_sent = True
            except Exception as e:
                logger.warning(f"Move-by-move coaching failed: {e}")
        
        # Step 4: Generate and store message if triggered (skip if opening commentary already sent)
        if trigger.should_speak and not opening_commentary_sent:
            if not await _is_current_revision():
                logger.info(f"Skipping stale triggered coaching for session {session_id}")
                return
            # First, try to get wisdom-based explanation
            from coach_play.teaching_integration import enhance_coaching_message
            
            wisdom_enhanced = None
            try:
                # Get session to find user_id
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                user_id = session_doc.get("user_id", "unknown") if session_doc else "unknown"
                
                # Parse user move to UCI
                import chess
                board = chess.Board(fen_before)
                chess_move = board.parse_san(user_move)
                
                wisdom_enhanced = enhance_coaching_message(
                    fen=fen_before,
                    user_move_uci=chess_move.uci(),
                    user_color=user_color,
                    eval_before=analysis["eval_before"],
                    eval_after=analysis["eval_after"],
                    best_move_uci=analysis.get("best_move_uci", ""),
                    best_move_eval=analysis.get("best_move_eval", analysis["eval_before"]),
                    move_number=move_number,
                    user_id=user_id,
                    user_rating=user_rating,
                )
            except Exception as e:
                logger.warning(f"Wisdom enhancement failed: {e}")
            
            # Use wisdom-based message if available, otherwise fall back to LLM
            if wisdom_enhanced and wisdom_enhanced.get("rule_id"):
                # Wisdom-based coaching message
                coach_message = wisdom_enhanced.get("chat_message", "")
                rule_id = wisdom_enhanced.get("rule_id")
                memorable_rule = wisdom_enhanced.get("memorable_rule", "")
                highlights = wisdom_enhanced.get("highlights", {})
                question = wisdom_enhanced.get("question")
                teaching_level = wisdom_enhanced.get("level", "teach")
                
                await db.coach_messages.insert_one({
                    "session_id": session_id,
                    "type": "coach",
                    "message": coach_message,
                    "trigger": trigger.trigger_type.value,
                    "move": user_move,
                    "move_number": move_number,
                    "created_at": datetime.now(timezone.utc),
                    "read": False,
                    # Wisdom-based enhancements
                    "rule_id": rule_id,
                    "memorable_rule": memorable_rule,
                    "highlights": highlights,
                    "question": question,
                    "teaching_level": teaching_level,
                    "is_wisdom_based": True,
                })
            else:
                # Use SOCRATIC ENGINE for human-like coaching
                # Never give the answer first - guide them to discover
                from services.human_coach_service import get_socratic_response
                
                eval_before = analysis.get("eval_before", 0)
                eval_after = analysis.get("eval_after", 0)
                best_move = analysis.get("best_move", "")
                delta = int((eval_after - eval_before) * 100)
                
                # Determine position type for Socratic engine
                if abs(delta) >= 200:
                    pass
                elif abs(delta) >= 100:
                    pass
                elif analysis.get("missed_tactic"):
                    pass
                else:
                    pass
                
                # Get Socratic response with emotional adaptation
                try:
                    # Get session for emotional context
                    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                    
                    # Build emotional context from session
                    emotional_context = None
                    if session_doc:
                        move_history = session_doc.get("move_history", [])
                        blunders_count = sum(1 for m in move_history if m.get("classification") == "BLUNDER")
                        emotional_context = {
                            "blunders_this_game": blunders_count
                        }
                    
                    socratic_response = await get_socratic_response(
                        db=db,
                        user_id=session_doc.get("user_id") if session_doc else "unknown",
                        user_rating=user_rating,
                        fen=fen_before,
                        move_played=user_move,
                        best_move=best_move,
                        eval_loss=abs(delta),
                        emotional_context=emotional_context
                    )
                    
                    coach_message = socratic_response.get("message", "")
                    
                    # Store Socratic dialogue context for continuing the conversation
                    dialogue_context = {
                        "dialogue_id": socratic_response.get("dialogue_id"),
                        "fen": fen_before,
                        "move_played": user_move,
                        "best_move": best_move,
                        "hints_given": 0
                    }
                    
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": coach_message,
                        "trigger": trigger.trigger_type.value,
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_socratic": True,
                        "socratic_dialogue": dialogue_context,
                        "emotional_state": socratic_response.get("emotional_state"),
                        "expects_response": socratic_response.get("expects_response", True),
                        "pattern_connection": socratic_response.get("pattern_connection"),
                        # MEMORY INSIGHTS - makes coach feel human
                        "memory_insight": socratic_response.get("memory_insight"),
                        "focus_note": socratic_response.get("focus_note"),
                        "games_together": socratic_response.get("games_together", 0),
                    })
                    
                except Exception as e:
                    logger.warning(f"Socratic engine failed, using fallback: {e}")
                    # Fallback to simple Socratic-style message
                    if abs(delta) >= 200:
                        coach_message = f"Interesting choice with {user_move}. What were you trying to achieve?"
                    elif abs(delta) >= 100:
                        coach_message = f"Let me ask about {user_move} - what was your thinking there?"
                    else:
                        coach_message = f"Good thinking with {user_move}! What's your plan from here?"
                    
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": coach_message,
                        "trigger": trigger.trigger_type.value,
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_wisdom_based": False,
                        "is_factual_fallback": True,
                    })
        
        # Step 3.5: Proactive teaching for GOOD moves and consequence detection
        # Even if trigger didn't fire, we can praise good moves or warn about consequences
        if not trigger.should_speak:
            try:
                if not await _is_current_revision():
                    logger.info(f"Skipping stale proactive teaching for session {session_id}")
                    return
                from coach_engine.question_system import (
                    generate_move_praise_question,
                    detect_long_term_consequences
                )
                import chess
                
                board = chess.Board(fen_after_user)
                
                # Check if it was a best/candidate move - praise it!
                if analysis.get("is_best_move") and move_number >= 4:
                    question = generate_move_praise_question(user_move, is_best=True)
                    await db.coach_messages.insert_one({
                        "session_id": session_id,
                        "type": "coach",
                        "message": question.text,
                        "trigger": "praise",
                        "move": user_move,
                        "move_number": move_number,
                        "created_at": datetime.now(timezone.utc),
                        "read": False,
                        "is_praise": True,
                        "question": question.to_dict() if question.options else None,
                    })
                
                # Check for long-term consequences (pawn structure, castling rights)
                elif move_number >= 6:
                    board_before = chess.Board(fen_before)
                    chess_move = board_before.parse_san(user_move)
                    board_before.push(chess_move)
                    
                    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                    consequence = detect_long_term_consequences(
                        board_before, user_chess_color, chess_move
                    )
                    
                    if consequence:
                        await db.coach_messages.insert_one({
                            "session_id": session_id,
                            "type": "coach",
                            "message": consequence,
                            "trigger": "consequence",
                            "move": user_move,
                            "move_number": move_number,
                            "created_at": datetime.now(timezone.utc),
                            "read": False,
                            "is_consequence_warning": True,
                        })
            except Exception as e:
                logger.warning(f"Proactive teaching failed: {e}")
        
        # Step 4: Make coach's responding move (if game not over)
        if not game_over:
            if not await _is_current_revision():
                logger.info(f"Skipping stale coach reply for session {session_id}")
                return
            session_doc = await db.coach_sessions.find_one({"session_id": session_id})
            if session_doc:
                board = chess.Board(fen_after_user)
                
                # === NEW: Check for opening and offer interactive teaching ===
                move_history = session_doc.get("move_history", [])
                user_id = session_doc.get("user_id", "unknown")
                
                # Only check in opening phase (first 12 moves per side)
                if len(move_history) <= 24 and not session_doc.get("opening_offer_shown"):
                    try:
                        from services.opening_teaching_integration import check_opening_and_offer_teaching
                        
                        opening_offer = await check_opening_and_offer_teaching(
                            db=db,
                            session_id=session_id,
                            move_history=move_history,
                            user_color=user_color,
                            user_id=user_id
                        )
                        
                        if opening_offer:
                            # Store the teaching offer as a coach message
                            await db.coach_messages.insert_one({
                                "session_id": session_id,
                                "type": "opening_teaching_offer",
                                "message": opening_offer["message"],
                                "trigger": "opening_detected",
                                "opening_name": opening_offer["opening_name"],
                                "opening_key": opening_offer["opening_key"],
                                "options": opening_offer["options"],
                                "trap_name": opening_offer.get("trap_name"),
                                "created_at": datetime.now(timezone.utc),
                                "read": False,
                            })
                            logger.info(f"Opening detected: {opening_offer['opening_name']} - offered teaching")
                    except Exception as e:
                        logger.warning(f"Opening detection failed: {e}")
                
                # === ENDGAME DETECTION ===
                # Check if we've entered an endgame and offer teaching
                if len(move_history) > 24 and not session_doc.get("endgame_offer_shown"):
                    try:
                        from services.endgame_teaching import check_endgame_and_offer_teaching
                        
                        endgame_offer = await check_endgame_and_offer_teaching(
                            db=db,
                            session_id=session_id,
                            current_fen=fen_after_user,
                            user_id=user_id,
                            user_color=user_color
                        )
                        
                        if endgame_offer:
                            await db.coach_messages.insert_one({
                                "session_id": session_id,
                                "type": "endgame_teaching_offer",
                                "message": endgame_offer["message"],
                                "trigger": "endgame_detected",
                                "endgame_type": endgame_offer["endgame_type"],
                                "lesson_name": endgame_offer["lesson_name"],
                                "key_concepts": endgame_offer["key_concepts"],
                                "options": endgame_offer["options"],
                                "created_at": datetime.now(timezone.utc),
                                "read": False,
                            })
                            logger.info(f"Endgame detected: {endgame_offer['lesson_name']} - offered teaching")
                    except Exception as e:
                        logger.warning(f"Endgame detection failed: {e}")
                
                # Get student weaknesses from their profile (if available)
                student_weaknesses = session_doc.get("student_weaknesses", [])
                teaching_focus = session_doc.get("teaching_focus", None)
                
                # Get move history for opening guidance
                move_history = session_doc.get("move_history", [])
                move_history_san = [m.get("move") for m in move_history if m.get("move")]
                
                # Get user's color (coach plays opposite)
                user_color = session_doc.get("user_color", "white")
                
                # Use Pedagogical Opponent with Teaching Move Selector
                from coach_play.coach_opponent import PedagogicalOpponent
                opponent = PedagogicalOpponent(
                    user_rating=user_rating,
                    teaching_mode="balanced",
                    student_weaknesses=student_weaknesses,
                    teaching_focus=teaching_focus,
                    move_history=move_history_san,  # Pass move history for opening guidance
                    user_color=user_color  # Pass user's color for correct opening guidance
                )
                coach_move = await opponent.get_move(fen_after_user)
                teaching_context = opponent.get_teaching_context()
                
                if coach_move:
                    chess_move = board.parse_san(coach_move)
                    board.push(chess_move)
                    fen_after_coach = board.fen()
                    
                    # CRITICAL: Fetch FRESH move_history that includes evaluations we just stored
                    if not await _is_current_revision():
                        logger.info(f"Skipping stale coach move application for session {session_id}")
                        return
                    fresh_session = await db.coach_sessions.find_one({"session_id": session_id})
                    move_history = fresh_session.get("move_history", []) if fresh_session else []
                    move_history.append({
                        "move": coach_move,
                        "uci": chess_move.uci(),
                        "by": "coach",
                        "fen_before": fen_after_user,
                        "fen_after": fen_after_coach,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "teaching_goal": teaching_context.get("teaching_goal"),
                        "is_best_move": teaching_context.get("is_best_move", True)
                    })
                    
                    # Check if game over after coach move
                    coach_game_over = board.is_game_over()
                    coach_result = None
                    status = "active"
                    if coach_game_over:
                        status = "completed"
                        if board.is_checkmate():
                            coach_result = "loss"  # Coach checkmated user
                        else:
                            coach_result = "draw"
                    
                    # Get new evaluation
                    eval_score, mate_in = await opponent.get_evaluation(fen_after_coach)
                    
                    # === OPENING DETECTION AFTER COACH'S MOVE ===
                    # This enables immediate detection for openings where the coach makes the defining move
                    # (e.g., 1.e4 for French Defense: coach plays e4, user will play e6)
                    if not coach_game_over and len(move_history) <= 24 and not session_doc.get("opening_offer_shown"):
                        try:
                            from services.opening_teaching_integration import check_opening_and_offer_teaching
                            
                            # Get updated move history (including coach's move)
                            all_moves_for_detection = [m.get("move", "") for m in move_history]
                            
                            opening_offer = await check_opening_and_offer_teaching(
                                db=db,
                                session_id=session_id,
                                move_history=all_moves_for_detection,
                                user_color=user_color,
                                user_id=session_doc.get("user_id", "unknown")
                            )
                            
                            if opening_offer:
                                # Store the teaching offer as a coach message
                                await db.coach_messages.insert_one({
                                    "session_id": session_id,
                                    "type": "opening_teaching_offer",
                                    "message": opening_offer["message"],
                                    "trigger": "opening_detected",
                                    "opening_name": opening_offer["opening_name"],
                                    "opening_key": opening_offer["opening_key"],
                                    "options": opening_offer["options"],
                                    "trap_name": opening_offer.get("trap_name"),
                                    "created_at": datetime.now(timezone.utc),
                                    "read": False,
                                })
                                logger.info(f"Opening detected after coach move: {opening_offer['opening_name']}")
                                
                                # Mark as shown so we don't show again
                                await db.coach_sessions.update_one(
                                    {"session_id": session_id},
                                    {"$set": {"opening_offer_shown": True}}
                                )
                        except Exception as e:
                            logger.warning(f"Opening detection after coach move failed: {e}")
                    
                    # === TEACHING: Generate coach's teaching message ===
                    coach_move_number = len(move_history) // 2
                    if not coach_game_over:
                        try:
                            from services.move_by_move_coach import generate_move_commentary
                            from coach_engine.opening_plans import build_opening_coaching_context
                            
                            all_moves = [m.get("move", "") for m in move_history]
                            opening_plan = build_opening_coaching_context(all_moves)
                            
                            # Use move-by-move coach for opening moves
                            if coach_move_number <= 15:
                                commentary = generate_move_commentary(
                                    fen_before=fen_after_user,
                                    fen_after=fen_after_coach,
                                    move_san=coach_move,
                                    move_by="coach",
                                    all_moves=all_moves,
                                    user_color=user_color,
                                    user_rating=user_rating,
                                    opening_plan=opening_plan,
                                )
                                
                                msg_text = commentary.message
                                trigger_type = "opening_teaching"
                                
                                if msg_text:
                                    msg_doc = {
                                        "session_id": session_id,
                                        "type": "coach",
                                        "message": msg_text,
                                        "trigger": trigger_type,
                                        "move": coach_move,
                                        "move_number": coach_move_number,
                                        "is_coach_move": True,
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                        "teaching_type": commentary.teaching_type,
                                    }
                                    if commentary.question:
                                        msg_doc["question"] = {"prompt": commentary.question}
                                    if commentary.trap_warning:
                                        msg_doc["trap_warning"] = commentary.trap_warning
                                    if commentary.next_hint:
                                        msg_doc["next_hint"] = commentary.next_hint
                                    
                                    # Include opening info
                                    if opening_plan:
                                        msg_doc["opening_key"] = opening_plan.get("key")
                                        msg_doc["opening_name"] = opening_plan.get("name")
                                    
                                    await db.coach_messages.insert_one(msg_doc)
                            else:
                                # Fall back to Active Teaching Engine for middlegame+
                                from services.active_teaching_engine import generate_teaching_feedback
                                
                                feedback = generate_teaching_feedback(
                                    fen=fen_after_coach,
                                    last_move_uci=chess_move.uci(),
                                    student_rating=user_rating,
                                    phase="after_coach_move",
                                    student_color=user_color,
                                    move_context={
                                        "teaching_goal": teaching_context.get("teaching_goal", "natural_play"),
                                        "why_instructive": teaching_context.get("why_instructive", ""),
                                        "concept_taught": teaching_context.get("concept_taught", ""),
                                        "student_challenge": teaching_context.get("student_challenge", ""),
                                        "move_san": coach_move,
                                        "game_phase": teaching_context.get("teaching_content", {}).get("game_phase", "middlegame")
                                    }
                                )
                                
                                if not feedback.get("error") and feedback.get("message"):
                                    await db.coach_messages.insert_one({
                                        "session_id": session_id,
                                        "type": "coach",
                                        "message": feedback["message"],
                                        "trigger": "teaching",
                                        "move": coach_move,
                                        "move_number": coach_move_number,
                                        "is_coach_move": True,
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                        "concept": feedback.get("concept"),
                                        "hints": feedback.get("hints", []),
                                    })
                        except Exception as e:
                            logger.warning(f"Opening teaching generation failed: {e}")
                    
                    # === NEW: INTELLIGENT POSITION COACHING ===
                    # Offer position-based coaching when not in opening/endgame teaching
                    # This connects all our analysis systems to provide contextual suggestions
                    if not coach_game_over:
                        try:
                            # Only offer if no opening/endgame teaching was triggered this session
                            should_offer_position_coaching = (
                                not session_doc.get("opening_teaching_active") and
                                not session_doc.get("position_coaching_offered") and
                                len(move_history) >= 12  # After ~6 moves per side
                            )
                            
                            if should_offer_position_coaching:
                                from services.intelligent_position_coach import analyze_position_and_suggest
                                
                                # Analyze the current position
                                position_coaching = await analyze_position_and_suggest(
                                    board=board,  # Board after coach's move
                                    move_history=move_history_san + [coach_move],
                                    user_color=user_color,
                                    user_id=session_doc.get("user_id", "unknown"),
                                    db=db
                                )
                                
                                if position_coaching:
                                    # Store the position coaching offer as a message
                                    await db.coach_messages.insert_one({
                                        "session_id": session_id,
                                        "type": "position_coaching",
                                        "message": position_coaching.get("main_idea", ""),
                                        "trigger": "position_analysis",
                                        "structure_name": position_coaching.get("structure_name"),
                                        "structure_type": position_coaching.get("structure_type"),
                                        "game_phase": position_coaching.get("game_phase"),
                                        "key_characteristics": position_coaching.get("key_characteristics", []),
                                        "strategic_plans": position_coaching.get("strategic_plans", []),
                                        "tactical_features": position_coaching.get("tactical_features", {}),
                                        "tactical_insights": position_coaching.get("tactical_insights", []),
                                        "teaching_points": position_coaching.get("teaching_points", []),
                                        "critical_squares": position_coaching.get("critical_squares", []),
                                        "options": position_coaching.get("options", []),
                                        "created_at": datetime.now(timezone.utc),
                                        "read": False,
                                    })
                                    
                                    # Mark that we've offered position coaching
                                    await db.coach_sessions.update_one(
                                        {"session_id": session_id},
                                        {"$set": {"position_coaching_offered": True}}
                                    )
                                    
                                    logger.info(f"Position coaching offered: {position_coaching.get('structure_name')} ({position_coaching.get('game_phase')})")
                        except Exception as e:
                            logger.warning(f"Intelligent position coaching failed: {e}")
                    
                    # Update session
                    await db.coach_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "current_fen": fen_after_coach,
                            "move_history": move_history,
                            "coach_move_pending": False,
                            "last_coach_move": {
                                "move": coach_move,
                                "uci": chess_move.uci(),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            "status": status,
                            "result": coach_result,
                            "evaluation": {"score": eval_score, "mate_in": mate_in}
                        }}
                    )
                else:
                    # No valid move (shouldn't happen)
                    await db.coach_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {"coach_move_pending": False}}
                    )
        else:
            # Game was over after user's move
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"coach_move_pending": False}}
            )
            
            # === UPDATE COACH MEMORY AFTER GAME ===
            try:
                from services.coach_memory import update_memory_after_game
                from phase_theory_service import detect_game_phase
                
                session_doc = await db.coach_sessions.find_one({"session_id": session_id})
                if session_doc:
                    # Determine result from user's perspective
                    result = "draw"
                    loss_phase = None
                    if game_over:
                        import chess
                        board = chess.Board(fen_after_user)
                        if board.is_checkmate():
                            # User delivered checkmate
                            result = "win"
                        else:
                            # User lost - determine phase
                            result = "loss"
                            # Get move count to determine phase
                            move_count = len(session_doc.get("move_history", []))
                            move_number = (move_count // 2) + 1
                            loss_phase = detect_game_phase(board, move_number)
                            logger.info(f"Game lost in {loss_phase} phase (move {move_number})")
                    
                    await update_memory_after_game(
                        db=db,
                        user_id=session_doc.get("user_id"),
                        game_result=result,
                        accuracy=0,  # Would need move-by-move analysis
                        blunders=0,
                        mistakes=0,
                        habits_violated=[],
                        habits_improved=[],
                        opening_played=session_doc.get("detected_opening"),
                        endgame_reached=session_doc.get("endgame_offer_shown", False),
                        performance_rating=session_doc.get("user_rating", 1200),
                        loss_phase=loss_phase
                    )
                    logger.info(f"Updated coach memory after game {session_id}")
            except Exception as e:
                logger.warning(f"Failed to update coach memory: {e}")
            
    except Exception as e:
        logger.error(f"Background move processing failed: {e}")
        # Mark as no longer pending even on error
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"coach_move_pending": False}}
        )




