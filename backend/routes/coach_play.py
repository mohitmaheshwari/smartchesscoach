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
from typing import Optional, Dict, List
from datetime import datetime, timezone
import logging
import json
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


def get_coach_move_explanation(move_san: str, fen_before: str, fen_after: str = "", move_number: int = 0) -> str:
    """
    Generate position-aware explanation for coach's move.
    Analyzes what the move actually DOES: captures, threats, development, etc.
    """
    try:
        board_before = chess.Board(fen_before)
        chess_move = board_before.parse_san(move_san)
        from_sq = chess_move.from_square
        to_sq = chess_move.to_square
        piece = board_before.piece_at(from_sq)
        captured = board_before.piece_at(to_sq)
        coach_color = piece.color if piece else chess.WHITE
        user_color = not coach_color

        if piece is None:
            return f"I played {move_san}."

        # Castling
        if board_before.is_castling(chess_move):
            side = "kingside" if board_before.is_kingside_castling(chess_move) else "queenside"
            return f"Castling {side} — king is safe, rook joins the fight."

        # Capture — explain what was taken and why
        if captured:
            cap_name = chess.piece_name(captured.piece_type)
            piece_name = chess.piece_name(piece.piece_type)
            if captured.piece_type > piece.piece_type:
                return f"Took your {cap_name} with my {piece_name} — winning material."
            elif captured.piece_type == piece.piece_type:
                return f"Traded {piece_name}s — simplifying the position."
            else:
                return f"Captured your {cap_name} on {chess.square_name(to_sq)}."

        # Make the move to check what it creates
        board_after = board_before.copy()
        board_after.push(chess_move)

        # Check
        if board_after.is_check():
            return f"{move_san} — check! Your king must respond."

        # New threats: does this move attack an undefended piece?
        new_threat = None
        for sq in chess.SQUARES:
            target = board_after.piece_at(sq)
            if target and target.color == user_color and target.piece_type != chess.KING:
                if to_sq in board_after.attacks(to_sq) or sq in board_after.attacks(to_sq):
                    # Check if newly attacked
                    attackers_after = board_after.attackers(coach_color, sq)
                    defenders = board_after.attackers(user_color, sq)
                    if to_sq in attackers_after and not defenders:
                        new_threat = (chess.piece_name(target.piece_type), chess.square_name(sq))
                        break
                    elif to_sq in attackers_after and len(defenders) < len(attackers_after):
                        target_val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(target.piece_type, 0)
                        piece_val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(piece.piece_type, 0)
                        if piece_val <= target_val:
                            new_threat = (chess.piece_name(target.piece_type), chess.square_name(sq))
                            break

        if new_threat:
            return f"{move_san} — now attacking your {new_threat[0]} on {new_threat[1]}. How will you respond?"

        # Piece-specific explanations
        if piece.piece_type == chess.PAWN:
            file = chess.square_file(to_sq)
            if file in (3, 4):
                return f"{move_san} — fighting for the center."
            elif file in (2, 5):
                return f"{move_san} — supporting central control."
            return f"{move_san} — advancing on the flank."

        if piece.piece_type == chess.KNIGHT:
            central = {chess.C3, chess.C6, chess.F3, chess.F6, chess.D4, chess.D5, chess.E4, chess.E5}
            if to_sq in central:
                return f"{move_san} — knight to an active central square."
            return f"{move_san} — repositioning the knight."

        if piece.piece_type == chess.BISHOP:
            # Count squares the bishop controls on its new diagonal
            mobility = len(list(board_after.attacks(to_sq)))
            if mobility >= 7:
                return f"{move_san} — bishop on a long diagonal, controlling {mobility} squares."
            return f"{move_san} — developing the bishop."

        if piece.piece_type == chess.ROOK:
            # Check if on an open/semi-open file
            file = chess.square_file(to_sq)
            own_pawns = any(board_after.piece_at(chess.square(file, r)) == chess.Piece(chess.PAWN, coach_color) for r in range(8))
            if not own_pawns:
                return f"{move_san} — rook on an open file. It controls the whole column."
            return f"{move_san} — activating the rook."

        if piece.piece_type == chess.QUEEN:
            return f"{move_san} — the queen enters play."

        return f"{move_san}."

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
        # Save behavior summary before ending
        try:
            _behavior_cache = getattr(evaluate_pending_move, '_behavior_cache', {})
            if session_id in _behavior_cache:
                from services.player_behavior_tracker import save_session_behavior
                await save_session_behavior(db, session_id, _behavior_cache[session_id])
                del _behavior_cache[session_id]
        except Exception as e:
            logger.warning(f"Behavior save at end failed: {e}")

        # Extract puzzles from this coach session
        try:
            from services.coach_puzzle_extractor import extract_puzzles_from_coach_session
            puzzles = await extract_puzzles_from_coach_session(db, session_id, user.user_id)
            if puzzles:
                logger.info(f"[COACH] Extracted {len(puzzles)} puzzles from session {session_id[:8]}")
        except Exception as e:
            logger.warning(f"Coach puzzle extraction failed: {e}")

        # Update opening mastery after game
        try:
            session_for_mastery = await db.coach_sessions.find_one({"session_id": session_id})
            if session_for_mastery:
                teaching_opening = session_for_mastery.get("opening_to_teach") or session_for_mastery.get("opening_key")
                if teaching_opening:
                    from services.opening_mastery_tracker import update_mastery_after_game
                    mh = session_for_mastery.get("move_history", [])
                    teaching_moves = session_for_mastery.get("opening_teaching_moves", [])

                    # Count how many teaching moves the user played correctly
                    correct = 0
                    total_teaching = 0
                    for i, tm in enumerate(teaching_moves):
                        if i >= len(mh):
                            break
                        move_entry = mh[i]
                        played = move_entry.get("move", "") if isinstance(move_entry, dict) else str(move_entry)
                        # Only count user's moves
                        is_user = move_entry.get("by") == "player" if isinstance(move_entry, dict) else (i % 2 == 0)
                        if is_user:
                            total_teaching += 1
                            if played.replace("+", "").replace("#", "").lower() == tm.replace("+", "").replace("#", "").lower():
                                correct += 1

                    if total_teaching > 0:
                        await update_mastery_after_game(
                            db, user.user_id, teaching_opening,
                            moves_correct=correct,
                            moves_total=total_teaching,
                        )
                        logger.info(f"[MASTERY] Updated {teaching_opening}: {correct}/{total_teaching} correct")
        except Exception as e:
            logger.warning(f"Opening mastery update failed: {e}")

        # Update focus after game (detect root problem, set/update focus)
        try:
            from services.focus_engine import update_focus_after_game
            from services.root_behavior_engine import get_root_problem_for_session

            session_for_focus = await db.coach_sessions.find_one({"session_id": session_id})
            if session_for_focus:
                beh_summary = session_for_focus.get("behavior_summary", {})
                _thinking = await db.thinking_scores.find(
                    {"user_id": user.user_id}, {"_id": 0, "habit_scores": 1}
                ).sort("calculated_at", -1).limit(5).to_list(5)
                _problems = await db.problem_lifecycle.find(
                    {"user_id": user.user_id}, {"_id": 0, "category": 1, "count": 1}
                ).to_list(10)
                root = get_root_problem_for_session(beh_summary, _thinking, _problems)
                await update_focus_after_game(db, user.user_id, beh_summary, root)
        except Exception as e:
            logger.warning(f"Focus update at end failed: {e}")

        result = await end_coach_session(
            db=db,
            session_id=session_id,
            reason=reason
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "End failed"))

        # Promote AFTER end_coach_session so result/status are set
        try:
            await _promote_session_to_game(db, session_id, user.user_id)
        except Exception as e:
            logger.warning(f"[COACH] Session-to-game promotion failed (non-fatal): {e}")

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
    best_move_san = None
    best_line_san = []
    punishment_line = []

    try:
        engine = StockfishEngine()
        engine.start()

        try:
            board_before = chess.Board(current_fen)
            eval_before_cp, _ = engine.evaluate_position(board_before, depth=12)
            eval_before = eval_before_cp / 100.0

            # Best move + principal variation from BEFORE position
            best_move_obj, _, _ = engine.get_best_move(board_before, depth=14)
            if best_move_obj:
                best_move_san = board_before.san(best_move_obj)
            best_line_san = engine.get_principal_variation(board_before, depth=14, pv_length=6)

            # Evaluate AFTER user's move
            chess_move = board_before.parse_san(move)
            board_after = board_before.copy()
            board_after.push(chess_move)

            eval_after_cp, _ = engine.evaluate_position(board_after, depth=12)
            eval_after = eval_after_cp / 100.0

            # Punishment line: opponent's best response after user's bad move
            punishment_line = engine.get_principal_variation(board_after, depth=12, pv_length=4)

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

    # Add engine analysis for the "Think Again" popup
    if result.get("should_intervene"):
        cp_loss = round((eval_before - eval_after) * 100) if eval_before is not None and eval_after is not None else 0
        # Flip for black
        if user_color == "black":
            cp_loss = -cp_loss

        # Categorize the mistake
        risk_type = result.get("risk_type", "")
        if risk_type in ("hanging_piece", "material_loss"):
            mistake_category = "one_move_blunder"
        elif risk_type in ("blunder_into_tactic",):
            mistake_category = "tactical_miss"
        elif risk_type in ("ignore_threat",):
            mistake_category = "threat_blindness"
        elif cp_loss > 200:
            mistake_category = "calculation_error"
        else:
            mistake_category = "positional_mistake"

        result["analysis"] = {
            "best_move": best_move_san,
            "best_line": best_line_san,  # e.g. ["Bc4", "Nf6", "d3", "Bc5"]
            "punishment_line": punishment_line,  # What opponent does after your bad move
            "cp_loss": cp_loss,
            "eval_before": round(eval_before, 1) if eval_before is not None else None,
            "eval_after": round(eval_after, 1) if eval_after is not None else None,
            "mistake_category": mistake_category,
        }

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
    
    # Now actually execute the move (same as /move endpoint)
    time_spent = request.get("time_spent", 0)
    try:
        current_fen = session_doc.get("current_fen")
        board = chess.Board(current_fen)
        chess_move = board.parse_san(move)
        board.push(chess_move)
        fen_after_user = board.fen()

        move_history = session_doc.get("move_history", [])
        move_number = len([m for m in move_history if m.get("by") == "player"]) + 1

        move_history.append({
            "move": move,
            "uci": chess_move.uci(),
            "by": "player",
            "fen_before": current_fen,
            "fen_after": fen_after_user,
            "time_spent": time_spent,
            "risk_acknowledged": risk_level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "current_fen": fen_after_user,
                "move_history": move_history,
                "coach_move_pending": True,
            }}
        )

        # Check if game is over
        game_over = board.is_game_over()
        if game_over:
            result = "draw"
            if board.is_checkmate():
                result = "win"
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"status": "completed", "result": result}}
            )
            return {
                "success": True,
                "remaining_interventions": remaining,
                "current_fen": fen_after_user,
                "game_over": True,
                "result": result,
            }

        return {
            "success": True,
            "remaining_interventions": remaining,
            "current_fen": fen_after_user,
            "awaiting_coach": True,
        }
    except Exception as e:
        logger.error(f"[GUARDIAN] Move execution after confirm failed: {e}")
        return {
            "success": True,
            "remaining_interventions": remaining,
            "message": "Move confirmed but execution failed. Try again.",
        }




# ========================================
# OPENING TEACHING ENDPOINTS
# ========================================

@router.post("/teaching/start")
async def start_teaching(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Start an interactive lesson during the game.
    
    Body:
    - session_id: Current game session
    - lesson_type: "learn_trap" | "learn_main_line" | "trap" | "endgame"
    - trap_key: (for lesson_type=trap) Key of the trap to practice
    - category: (for lesson_type=endgame) Endgame category
    - lesson_key: (for lesson_type=endgame) Specific lesson
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.teaching_engine import start_lesson
    
    session_id = request.get("session_id")
    lesson_type = request.get("lesson_type", "learn_trap")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await start_lesson(db, session_id, user.user_id, lesson_type, request)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/teaching/move")
async def process_teaching_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Process a move during any teaching mode (opening, trap, endgame).
    Dispatches to the correct handler based on session's lesson_type.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.teaching_engine import process_lesson_move
    
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
    
    result = await process_lesson_move(db, session_id, move)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/teaching/exit")
async def exit_teaching_mode(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Exit any teaching mode and optionally restore the game.
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    from services.teaching_engine import exit_lesson
    
    session_id = request.get("session_id")
    choice = request.get("choice", "continue_game")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")
    
    result = await exit_lesson(db, session_id, choice)
    
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


@router.get("/teaching/catalog")
async def get_teaching_catalog(
    user: User = Depends(get_current_user)
):
    """Return all available lesson types for the lesson picker UI."""
    from services.teaching_engine import get_lesson_catalog
    return get_lesson_catalog()


@router.post("/escape-squares/check")
async def check_escape_squares(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Check if the current position is a good moment for escape squares quiz.

    Body:
    - session_id: Current game session
    - fen: (optional) Override FEN. If not provided, uses session's current_fen.

    Returns:
    - has_quiz: bool
    - quiz: Quiz data if has_quiz is True
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from services.escape_squares_service import is_escape_squares_teaching_moment

    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    fen = request.get("fen") or session_doc.get("current_fen")
    user_color = session_doc.get("user_color", "white")

    if not fen:
        return {"has_quiz": False}

    quiz = is_escape_squares_teaching_moment(fen, user_color)
    if quiz:
        return {"has_quiz": True, "quiz": quiz}
    return {"has_quiz": False}


@router.post("/escape-squares/answer")
async def answer_escape_squares(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Validate user's answer to the escape squares quiz.

    Body:
    - session_id: Current game session
    - answer: int (user's count of escape squares)
    - quiz_data: The quiz object returned from /escape-squares/check

    Returns:
    - result: Validation result with feedback message
    """
    global db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from services.escape_squares_service import validate_escape_squares_answer

    session_id = request.get("session_id")
    answer = request.get("answer")
    quiz_data = request.get("quiz_data")

    if session_id is None or answer is None or quiz_data is None:
        raise HTTPException(status_code=400, detail="session_id, answer, and quiz_data are required")

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_doc.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    result = validate_escape_squares_answer(quiz_data, int(answer))

    # Track quiz results in session for stats
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$push": {"escape_square_quizzes": {
            "correct": result["correct"],
            "user_answer": int(answer),
            "correct_answer": result["correct_answer"],
            "fen": session_doc.get("current_fen"),
        }}}
    )

    return {"result": result}


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
                    "last_coach_move": {
                        "move": coach_move_san,
                        "san": coach_move_san,
                        "uci": coach_move_uci,
                        "explanation": get_coach_move_explanation(coach_move_san, current_fen),
                    }
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
            
            # Get opponent's last move for fundamentals checking
            opp_last_move = None
            if board.move_stack:
                opp_last_move = board.move_stack[-1]

            # Try to match opening for opening ideas
            opening_match = None
            try:
                from services.opening_theory_tree_service import match_opening_by_moves
                # Reconstruct move list from board
                temp = board.copy()
                move_list_san = []
                moves_to_pop = list(temp.move_stack)
                temp.reset()
                for m in moves_to_pop:
                    move_list_san.append(temp.san(m))
                    temp.push(m)
                opening_match = match_opening_by_moves(move_list_san)
            except Exception:
                pass

            # Get coach's teaching intent from last coach move (v2 data)
            _coach_intent = None
            if last_coach_move and last_coach_move.get("v2"):
                _coach_intent = last_coach_move.get("teaching_intent")

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
                user_color=user_color,
                opponent_last_move=opp_last_move,
                opening_match=opening_match,
                coach_intent=_coach_intent,
            )

            coaching_dict = coaching.to_dict()
            coaching_dict["move_san"] = move_san
            coaching_dict["fen_before"] = fen_before  # Needed for board preview of alternatives

            # Track fundamental violations for post-game summary
            if coaching_dict.get("fundamental_violated"):
                try:
                    await db.coach_sessions.update_one(
                        {"session_id": session_id},
                        {"$push": {"fundamental_violations": {
                            "move_number": board.fullmove_number,
                            "fundamental": coaching_dict["fundamental_violated"],
                            "move": move_san,
                        }}}
                    )
                except Exception:
                    pass

            # Enhance Socratic question with LLM for mistakes/blunders
            if coaching.severity in ("mistake", "blunder"):
                try:
                    from services.smart_coaching import generate_smart_user_feedback
                    smart_fb = await generate_smart_user_feedback(
                        board_before=board,
                        user_move=move,
                        best_move_san=best_move,
                        cp_loss=cp_loss,
                        severity=coaching.severity,
                        fundamental_violated=coaching_dict.get("fundamental_violated"),
                        coach_intent=_coach_intent,
                        user_rating=session_doc.get("user_rating", 1200),
                        phase=phase_str,
                        db=db,
                    )
                    if smart_fb:
                        if smart_fb.get("question"):
                            coaching_dict["socratic_question"] = smart_fb["question"]
                        if smart_fb.get("hint"):
                            coaching_dict["socratic_hint"] = smart_fb["hint"]
                except Exception as smart_err:
                    logger.debug(f"Smart user feedback failed (using template): {smart_err}")

            # Compute best_move_uci for board arrow drawing
            if best_move and best_move != move_san:
                try:
                    best_move_obj = board.parse_san(best_move)
                    coaching_dict["best_move_uci"] = best_move_obj.uci()
                except Exception:
                    coaching_dict["best_move_uci"] = ""
            else:
                coaching_dict["best_move_uci"] = ""
            
            # === MID-GAME ADAPTATION ===
            # Detect tempo, tilt, hot/cold streaks — adjust coaching in real-time
            try:
                from services.midgame_adaptation import compute_game_adaptation
                adaptation = compute_game_adaptation(move_history, user_color, evaluations)

                if adaptation.get("nudge") and coaching.severity in ("mistake", "blunder"):
                    coaching_dict["narrative"] = f"{adaptation['nudge']} {coaching_dict.get('narrative', '')}"

                if adaptation.get("nudge") and adaptation.get("tilt_risk"):
                    coaching_dict["narrative"] = f"{adaptation['nudge']} {coaching_dict.get('narrative', '')}"

                if adaptation.get("momentum") == "hot_streak" and coaching.severity in ("good", "brilliant"):
                    streak = adaptation.get("good_moves_streak", 0)
                    if streak >= 3:
                        coaching_dict["encouragement"] = f"{streak} good moves in a row. You're locked in."

                coaching_dict["adaptation"] = {
                    "tempo": adaptation.get("tempo", "unknown"),
                    "momentum": adaptation.get("momentum", "neutral"),
                    "tilt_risk": adaptation.get("tilt_risk", False),
                }
            except Exception as adapt_err:
                logger.debug(f"Mid-game adaptation failed (non-fatal): {adapt_err}")

            # === PATTERN MEMORY + STRENGTH AWARENESS ===
            # Adapts coaching based on what user knows vs doesn't know
            if coaching.severity in ("mistake", "blunder", "inaccuracy") and cp_loss >= 100:
                try:
                    from services.pattern_memory_service import get_pattern_for_mistake

                    cognitive_gap = coaching.concept_id or coaching.severity
                    pattern_data = await get_pattern_for_mistake(db, user.user_id, cognitive_gap)

                    if pattern_data and pattern_data.get("confrontation_message"):
                        # Check if user has been TRAINING this pattern and doing well
                        try:
                            from services.community_training_service import get_user_pattern_stats
                            puzzle_stats = await get_user_pattern_stats(db, user.user_id)
                            puzzle_map = {s["pattern"]: s for s in puzzle_stats}
                            gap_stats = puzzle_map.get(cognitive_gap)

                            if gap_stats and gap_stats.get("total_attempts", 0) >= 3:
                                solve_rate = gap_stats.get("solve_rate", 0)
                                if solve_rate >= 70:
                                    # They KNOW this pattern but still missed it in-game
                                    coaching_dict["pattern_memory"] = (
                                        f"You know this pattern — you solve it in training. "
                                        f"This was a focus lapse, not a knowledge gap. Slow down."
                                    )
                                else:
                                    # They're still learning this pattern
                                    coaching_dict["pattern_memory"] = pattern_data["confrontation_message"]
                            else:
                                coaching_dict["pattern_memory"] = pattern_data["confrontation_message"]
                        except Exception:
                            coaching_dict["pattern_memory"] = pattern_data["confrontation_message"]
                except Exception as pm_err:
                    logger.warning(f"Pattern memory injection failed (non-critical): {pm_err}")
            
            # === CONVERSATION THREAD ===
            # "I told you this on move 10. Same thing happening again."
            try:
                from services.game_conversation_thread import get_thread

                thread = get_thread(session_id)
                move_num = board.fullmove_number

                if coaching.severity in ("mistake", "blunder", "inaccuracy"):
                    # Check if we coached this behavior before in this game
                    behavior_key = coaching.concept_id or coaching.concept_type or coaching.severity
                    callback = thread.get_callback(move_num, behavior_key)

                    if callback:
                        # Prepend the callback to the narrative
                        coaching_dict["narrative"] = f"{callback} {coaching_dict.get('narrative', '')}"
                        coaching_dict["conversation_callback"] = callback

                    # Record this coaching moment
                    rule = coaching.transferable_learning or coaching_dict.get("better_approach", "")
                    thread.record(move_num, behavior_key, coaching.severity, rule)
                else:
                    # Good move — track it for "you listened for X moves then stopped"
                    thread.record_good_move()

            except Exception as thread_err:
                logger.debug(f"Conversation thread failed (non-fatal): {thread_err}")

            # === TRAP DETECTION (Escape Square Awareness) ===
            # Detect opponent pieces with limited escape squares
            try:
                from services.trap_detection_service import detect_trap_opportunities, generate_trap_coaching_message, track_trap_opportunity

                # Analyze AFTER user's move — what traps exist now?
                board_after = chess.Board(fen_before)
                board_after.push(board_after.parse_san(move_san))

                trap_opps = detect_trap_opportunities(board_after, chess.WHITE if user_color == "white" else chess.BLACK)
                if trap_opps:
                    # Pick the best trap (highest value * urgency)
                    best_trap = trap_opps[0]
                    trap_msg = generate_trap_coaching_message(best_trap)

                    coaching_dict["trap_opportunity"] = {
                        "target_square": best_trap.target_square,
                        "target_piece": best_trap.target_piece,
                        "escape_count": best_trap.escape_count,
                        "escape_squares": best_trap.escape_squares,
                        "blocked_squares": best_trap.blocked_squares,
                        "reduction_moves": [
                            {"move_san": r["move_san"], "move_uci": r["move_uci"],
                             "from": r["from"], "to": r["to"],
                             "blocks": r["blocks_squares"], "new_escapes": r["new_escape_count"]}
                            for r in best_trap.reduction_moves[:2]
                        ],
                        "trap_level": best_trap.trap_level,
                        "message": trap_msg,
                        "is_attacked": best_trap.is_attacked,
                        "is_trappable_in_2": best_trap.is_trappable_in_2,
                        "trap_sequence": best_trap.trap_sequence,
                    }

                    # Track the trap opportunity for conversion rate
                    await track_trap_opportunity(db, user.user_id, session_id, best_trap)
            except Exception as trap_err:
                logger.debug(f"Trap detection failed (non-fatal): {trap_err}")

            # === POSITION EVAL LABEL ===
            # "Are you winning, losing, or equal?"
            try:
                from services.position_eval_label import get_eval_label
                # eval_after is from white's perspective in centipawns
                eval_cp_for_label = int(eval_after * 100) if isinstance(eval_after, float) else int(eval_after)
                coaching_dict["eval_label"] = get_eval_label(eval_cp_for_label, user_color)
            except Exception:
                pass

            # === POSITION INTELLIGENCE ===
            # Use deterministic reading for every move (no LLM cost)
            # LLM board reading was being called on EVERY move — 30+ calls per game
            try:
                from services.position_intelligence import read_board_like_a_coach

                board_after_user = chess.Board(fen_before)
                board_after_user.push(board_after_user.parse_san(move_san))

                board_read = read_board_like_a_coach(
                    board_after_user.fen(),
                    user_color=user_color,
                    user_rating=1200
                )

                if board_read.get("plan_id") != "neutral":
                    coaching_dict["position_read"] = {
                        "summary": board_read.get("summary", ""),
                        "plan": board_read.get("plan", ""),
                        "focus": board_read.get("focus", ""),
                        "phase": board_read.get("phase", ""),
                        "material": board_read.get("material", ""),
                        "priority": board_read.get("priority", ""),
                        "observations": board_read.get("observations", [])[:2],
                    }
            except Exception as pi_err:
                logger.debug(f"Position intelligence failed (non-fatal): {pi_err}")

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
            result["best_move_uci"] = coaching_dict.get("best_move_uci", "")

            # === MOVE SNAPSHOT: Capture everything for testing/review ===
            # === MOVE SNAPSHOT: Dump EVERYTHING for review ===
            try:
                snapshot = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "move_number": board.fullmove_number,
                    "move": move_san,
                    "by": "player",
                    "fen_before": fen_before,
                    # The entire coaching dict — everything the frontend receives
                    "coaching": coaching_dict,
                    # Coach's teaching intent for the PREVIOUS coach move
                    "coach_intent": _coach_intent,
                }
                await db.coach_sessions.update_one(
                    {"session_id": session_id},
                    {"$push": {"move_snapshots": snapshot}}
                )
                logger.info(f"[SNAPSHOT] User {move_san}: severity={coaching.severity} "
                           f"fundamental={coaching_dict.get('fundamental_violated')} "
                           f"cp_loss={cp_loss} coach_intent={_coach_intent}")
            except Exception as snap_err:
                logger.warning(f"Move snapshot failed: {snap_err}")

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

            # Try LLM-powered smart coaching first
            v2_ctx = None
            if last_coach_move.get("v2"):
                v2_ctx = {
                    "v2": True,
                    "teaching_goal": last_coach_move.get("teaching_intent"),
                    "why_instructive": last_coach_move.get("why_instructive"),
                    "v2_breakdown": last_coach_move.get("v2_breakdown", {}),
                }

            coach_explanation = None
            try:
                logger.info(f"[COACH-EXPLAIN] Attempting smart coaching for {last_coach_move.get('move')}")
                from services.smart_coaching import generate_smart_coach_explanation
                # Get player weaknesses for context
                _player_weaknesses = []
                try:
                    _pp = await db.player_profiles.find_one(
                        {"user_id": user_id}, {"top_weaknesses": 1, "_id": 0})
                    if _pp:
                        _player_weaknesses = [w.get("subcategory", w.get("category", ""))
                                              for w in _pp.get("top_weaknesses", [])[:3]]
                except Exception:
                    pass

                _opening = session_doc.get("detected_opening") or session_doc.get("opening_to_teach")

                coach_explanation = await generate_smart_coach_explanation(
                    board_before=board,
                    move=move,
                    user_color=user_color,
                    v2_context=v2_ctx,
                    player_weaknesses=_player_weaknesses,
                    user_rating=session_doc.get("user_rating", 1200),
                    opening_name=_opening,
                    db=db,
                    move_history=move_history,
                )
            except Exception as llm_err:
                logger.error(f"[COACH-EXPLAIN] Smart coaching FAILED: {llm_err}", exc_info=True)

            # Fallback to template-based explanation
            if not coach_explanation:
                coach_explanation = generate_coach_move_explanation(
                    board, move, user_color, v2_context=v2_ctx
                )

            # Add intent badge data for frontend
            # Don't show intent badge during opening (misleading — "Creating Threats" for Nf6)
            intent_labels = {
                "fork_opportunity": "Double Attack",
                "hanging_piece_punishment": "Piece Safety",
                "threat_awareness": "Creating Threats",
            }
            move_count = len(move_history)
            in_opening = move_count <= 20  # ~10 moves per side
            if last_coach_move.get("v2"):
                v2_intent = last_coach_move.get("teaching_intent", "")
                # Only show intent badge after the opening
                if not in_opening or v2_intent in ("fork_opportunity", "hanging_piece_punishment"):
                    coach_explanation["v2_intent"] = v2_intent
                coach_explanation["v2_label"] = intent_labels.get(v2_intent, "")

            result["coach_move_coaching"] = coach_explanation
        except Exception as e:
            logger.warning(f"Error generating coach move explanation: {e}")

    # === PRE-MOVE TRAP PROMPT ===
    # After coach plays, check if the CURRENT position has a trap opportunity
    # for the user. Show it BEFORE they make their next move.
    if phase in (None, "coach_move"):
        try:
            from services.trap_detection_service import detect_trap_opportunities, generate_trap_coaching_message

            # Get current FEN (after coach's move)
            current_fen = session_doc.get("current_fen", "")
            if current_fen:
                current_board = chess.Board(current_fen)
                uc = chess.WHITE if user_color == "white" else chess.BLACK

                pre_traps = detect_trap_opportunities(current_board, uc)
                if pre_traps:
                    best = pre_traps[0]
                    if best.escape_count <= 2:  # Only prompt for serious traps
                        result["pre_move_trap"] = {
                            "target_square": best.target_square,
                            "target_piece": best.target_piece,
                            "escape_count": best.escape_count,
                            "escape_squares": best.escape_squares,
                            "message": f"Before you move — their {best.target_piece} on {best.target_square} has only {best.escape_count} escape square{'s' if best.escape_count != 1 else ''}. Can you restrict it?",
                            "trap_level": best.trap_level,
                            "is_trappable_in_2": best.is_trappable_in_2,
                            "trap_sequence": best.trap_sequence,
                            "reduction_moves": [
                                {"move_san": r["move_san"], "from": r["from"], "to": r["to"]}
                                for r in best.reduction_moves[:2]
                            ],
                        }
        except Exception as pre_trap_err:
            logger.debug(f"Pre-move trap detection failed (non-fatal): {pre_trap_err}")

    # === SNAPSHOT: Save the complete interactive-feedback response ===
    # This is the FULL payload the frontend receives — everything shown in the sidebar
    try:
        feedback_snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "by": "feedback_response",
            "phase": phase,
            "full_response": {
                k: v for k, v in result.items()
                if k not in ("_id",)  # exclude mongo internals
            },
        }
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$push": {"move_snapshots": feedback_snapshot}}
        )
    except Exception:
        pass

    return result


def _transform_to_fun_language(feedback: Dict, severity: str, move_san: str) -> str:
    """Transform feedback to fun V5 language."""
    piece = feedback.get("piece_moved", "")
    
    if severity in ["good", "best", "great"]:
        return feedback.get("coaching_message") or f"Nice! {move_san} is a solid choice!"
    
    if "knight" in piece.lower() or (move_san and move_san[0] == "N"):
        if severity in ["blunder", "mistake"]:
            return f"{move_san} gets your knight in trouble!"
        return f"Hmm, {move_san} — is that the best square for your knight?"

    if "bishop" in piece.lower() or (move_san and move_san[0] == "B"):
        return f"Your bishop looks passive after {move_san}."

    if "pawn" in piece.lower():
        return f"Careful with {move_san} — pawns can't go backwards!"
    
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


@router.post("/position/read")
async def read_position_general(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Read a position — what's happening on the board? General endpoint (no session needed)."""
    fen = request.get("fen", "")
    user_color = request.get("user_color", "white")

    if not fen:
        raise HTTPException(status_code=400, detail="fen required")

    try:
        from services.position_intelligence import read_board_deep
        result = await read_board_deep(fen, user_color=user_color, user_rating=1200)
        return result
    except Exception as e:
        # Fallback to deterministic
        from services.position_intelligence import read_board_like_a_coach
        result = read_board_like_a_coach(fen, user_color=user_color, user_rating=1200)
        return result


@router.post("/position/explore-lines")
async def explore_lines(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Explore branching lines from a position.

    Given a FEN + best move, returns:
    1. Main line (best play for both sides)
    2. "But what if...?" branches (opponent's alternatives + why they fail)

    This teaches WHY a move is good, not just THAT it's good.
    """
    fen = request.get("fen", "")
    best_move_san = request.get("best_move", "")

    if not fen or not best_move_san:
        raise HTTPException(status_code=400, detail="fen and best_move required")

    try:
        import chess as chess_mod
        import chess.engine

        board = chess_mod.Board(fen)
        best_move = board.parse_san(best_move_san)

        STOCKFISH_PATH = "/usr/games/stockfish"
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)

        try:
            PIECE_NAMES = {chess_mod.PAWN: "pawn", chess_mod.KNIGHT: "knight", chess_mod.BISHOP: "bishop",
                           chess_mod.ROOK: "rook", chess_mod.QUEEN: "queen", chess_mod.KING: "king"}

            # 1. Play the best move
            board_after = board.copy()
            board_after.push(best_move)

            # 2. Get opponent's top 3 responses (MultiPV)
            opp_responses = await engine.analyse(
                board_after,
                chess.engine.Limit(depth=14),
                multipv=3
            )

            branches = []
            for i, info in enumerate(opp_responses):
                if "pv" not in info or not info["pv"]:
                    continue

                opp_move = info["pv"][0]
                opp_san = board_after.san(opp_move)

                # Get eval after opponent's response
                score = info.get("score")
                if score:
                    opp_eval = score.relative.score(mate_score=10000) if not score.is_mate() else (10000 if score.relative.mate() > 0 else -10000)
                else:
                    opp_eval = 0

                # Play opponent's move
                board_after_opp = board_after.copy()
                board_after_opp.push(opp_move)

                # Get user's best reply to this opponent response
                user_reply_info = await engine.analyse(
                    board_after_opp,
                    chess.engine.Limit(depth=12),
                    multipv=1
                )

                user_reply_san = ""
                user_reply_fen = board_after_opp.fen()
                final_eval = opp_eval
                continuation = []

                if user_reply_info and user_reply_info[0].get("pv"):
                    # Play the FULL Stockfish PV — let the engine decide when position is quiet
                    # Don't try to detect "exchange settled" ourselves — Stockfish already did
                    full_pv = user_reply_info[0]["pv"]

                    temp = board_after.copy()
                    continuation.append({"move": opp_san, "by": "opponent"})
                    temp.push(opp_move)

                    user_turn = True
                    PIECE_VALUES = {chess_mod.PAWN: 1, chess_mod.KNIGHT: 3, chess_mod.BISHOP: 3,
                                    chess_mod.ROOK: 5, chess_mod.QUEEN: 9, chess_mod.KING: 0}

                    # Material BEFORE the line starts
                    w_mat_before = sum(PIECE_VALUES.get(p.piece_type, 0) for p in temp.piece_map().values() if p.color == chess_mod.WHITE)
                    b_mat_before = sum(PIECE_VALUES.get(p.piece_type, 0) for p in temp.piece_map().values() if p.color == chess_mod.BLACK)

                    for pv_idx, pv_move in enumerate(full_pv[:10]):
                        try:
                            pv_san = temp.san(pv_move)
                            is_cap = temp.is_capture(pv_move)
                            gives_check = temp.gives_check(pv_move)
                            who = "you" if user_turn else "opponent"

                            # Describe what this move does
                            move_desc = None
                            if gives_check:
                                temp.push(pv_move)
                                if temp.is_checkmate():
                                    move_desc = "Checkmate"
                                else:
                                    move_desc = "Check"
                                temp.pop()
                            if is_cap:
                                captured = temp.piece_at(pv_move.to_square)
                                if captured:
                                    cap_name = PIECE_NAMES.get(captured.piece_type, "piece")
                                    move_desc = f"Takes {cap_name}" if not move_desc else f"{move_desc} and takes {cap_name}"

                            continuation.append({
                                "move": pv_san,
                                "by": who,
                                "is_impact": False,
                                "impact": move_desc,
                            })

                            temp.push(pv_move)
                            user_turn = not user_turn

                            if move_desc == "Checkmate":
                                continuation[-1]["is_impact"] = True
                                break

                        except Exception:
                            break

                    # Evaluate the FINAL position after the full line
                    final_score = user_reply_info[0].get("score")
                    if final_score:
                        final_eval = final_score.relative.score(mate_score=10000) if not final_score.is_mate() else 10000

                    # Material at the end
                    user_is_white = board.turn == chess_mod.WHITE
                    w_mat_after = sum(PIECE_VALUES.get(p.piece_type, 0) for p in temp.piece_map().values() if p.color == chess_mod.WHITE)
                    b_mat_after = sum(PIECE_VALUES.get(p.piece_type, 0) for p in temp.piece_map().values() if p.color == chess_mod.BLACK)

                    # Net material change from user's perspective
                    user_mat_change = (w_mat_after - b_mat_after) - (w_mat_before - b_mat_before)
                    if not user_is_white:
                        user_mat_change = -user_mat_change

                    # Add final outcome
                    outcome = ""
                    if user_mat_change >= 8:
                        outcome = "You win the queen"
                    elif user_mat_change >= 4:
                        outcome = "You win major material"
                    elif user_mat_change >= 2:
                        outcome = "You win a piece"
                    elif user_mat_change >= 1:
                        outcome = "You win a pawn"
                    elif user_mat_change <= -4:
                        outcome = "You lose material"
                    elif user_mat_change <= -1:
                        outcome = "You lose a pawn"
                    elif final_eval and final_eval > 200:
                        outcome = "You have a winning position"
                    elif final_eval and final_eval < -200:
                        outcome = "You're in trouble"
                    else:
                        outcome = "Position is roughly equal"

                    # Mark outcome on last move
                    if continuation:
                        continuation.append({
                            "move": "",
                            "by": "result",
                            "is_impact": True,
                            "impact": outcome,
                        })

                    if final_eval is None and final_score:
                        final_eval = final_score.relative.score(mate_score=10000) if not final_score.is_mate() else 10000

                    _ = final_eval  # Suppress unused warning
                    if False:  # Dead code guard — was "if not impact_found"
                        # Describe outcome based on eval
                        if abs(final_eval) >= 300:
                            continuation.append({
                                "move": "",
                                "by": "result",
                                "is_impact": True,
                                "impact": "Winning position" if final_eval > 0 else "Lost position",
                            })

                # Describe what opponent's move does
                opp_piece = board_after.piece_at(opp_move.from_square)
                opp_piece_name = PIECE_NAMES.get(opp_piece.piece_type, "piece") if opp_piece else "piece"
                is_capture = board_after.is_capture(opp_move)

                if is_capture:
                    captured = board_after.piece_at(opp_move.to_square)
                    cap_name = PIECE_NAMES.get(captured.piece_type, "piece") if captured else "piece"
                    opp_desc = f"Takes your {cap_name}"
                elif board_after.gives_check(opp_move):
                    opp_desc = "Gives check"
                else:
                    to_sq = chess_mod.square_name(opp_move.to_square)
                    opp_desc = f"Moves {opp_piece_name} to {to_sq}"

                # Is this the main line or an alternative?
                is_main = i == 0

                branches.append({
                    "opponent_move": opp_san,
                    "opponent_description": opp_desc,
                    "your_reply": user_reply_san,
                    "continuation": continuation,
                    "is_main_line": is_main,
                    "label": "What actually happens" if is_main else f"What if {opp_desc.lower()}?",
                    "outcome_eval": final_eval,
                    "fen_after_opponent": board_after_opp.fen(),
                })

            return {
                "fen": fen,
                "best_move": best_move_san,
                "fen_after_best": board_after.fen(),
                "branches": branches,
            }

        finally:
            await engine.quit()

    except Exception as e:
        logger.error(f"Explore lines failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ─── EVALUATE PENDING MOVE (Fast Path) ────────────────────────────

@router.post("/evaluate-pending")
async def evaluate_pending_move(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """
    Ultra-fast pending move evaluation.
    Target: P95 < 400ms.

    Returns shouldAutoCommit + optional coachingMoment.
    No LLM. No deep search. Warm Stockfish only.
    """
    import time as _time
    start = _time.monotonic()

    session_id = request.get("sessionId")
    fen_before = request.get("fenBefore")
    uci = request.get("uci")
    move_index_preview = request.get("moveIndexPreview", 0)
    user_rating = request.get("userRating", 1200)

    if not session_id or not fen_before or not uci:
        return {"shouldAutoCommit": True, "coachingMoment": None, "coachingDecision": {"layer": "silent"}, "checklist": {}, "weaknesses": [], "playerProfile": None, "commentary": None}

    try:
        from services.fast_eval_service import fast_eval, detect_signals_fast
        from services.message_decision_engine import (
            ENABLE_DECISION_ENGINE, SessionMemory, MoveSignals,
            generate_candidates, score_candidates, select_winner, THRESHOLDS,
        )

        # Get session for cached eval and user patterns
        session_doc = await db.coach_sessions.find_one(
            {"session_id": session_id},
            {"_id": 0, "evaluations": 1, "user_color": 1, "user_id": 1, "move_history": 1,
             "coaching_decisions": 1, "last_coaching_move_index": 1,
             "opening_to_teach": 1, "opening_key": 1, "opening_teaching_active": 1,
             "opening_teaching_moves": 1, "opening_teaching_index": 1,
             "behavior_summary": 1}
        )
        if not session_doc:
            return {"shouldAutoCommit": True, "coachingMoment": None, "coachingDecision": {"layer": "silent"}, "checklist": {}, "weaknesses": [], "playerProfile": None, "commentary": None}

        user_color = session_doc.get("user_color", "white")
        user_id = session_doc.get("user_id", "")

        # Load player weaknesses, strengths, and focus concept
        top_weaknesses = []
        player_profile_data = None
        focus_concept = None
        try:
            from services.player_behavior_tracker import (
                compute_top_weaknesses, get_focus_concept,
                get_weakness_score_boost, get_escalation_level,
                get_escalated_message, get_adaptive_hold_boost,
                SessionBehaviorTracker,
            )
            top_weaknesses = await compute_top_weaknesses(db, user_id, recent_games=10)
            focus_concept = await get_focus_concept(db, user_id)
        except Exception as e:
            logger.warning(f"[FAST-EVAL] Behavior tracker load failed: {e}")

        # Load player strength profile (domains, strongest, weakest)
        try:
            strength_doc = await db.player_strength_profiles.find_one(
                {"user_id": user_id},
                {"_id": 0, "domains": 1, "strongest": 1, "weakest": 1, "overall_score": 1, "overall_label": 1}
            )
            if strength_doc:
                domains = strength_doc.get("domains", {})
                player_profile_data = {
                    "strongest": strength_doc.get("strongest"),
                    "weakest": strength_doc.get("weakest"),
                    "overall_label": strength_doc.get("overall_label"),
                    "overall_score": strength_doc.get("overall_score"),
                    "domains": {
                        k: {"score": v.get("score", 0) if isinstance(v, dict) else 0,
                            "label": v.get("label", "") if isinstance(v, dict) else ""}
                        for k, v in domains.items()
                    } if domains else {},
                }
            if player_profile_data:
                logger.info(f"[FAST-EVAL] Profile loaded: strongest={player_profile_data.get('strongest')}")
            else:
                logger.warning(f"[FAST-EVAL] No strength profile found for user {user_id}")
        except Exception as e:
            logger.error(f"[FAST-EVAL] Strength profile load failed: {e}", exc_info=True)

        # Compute root behavioral problem (collapsed clusters)
        root_problem = None
        try:
            from services.root_behavior_engine import get_root_problem_for_session
            # Get recent thinking scores and active problems
            _thinking = await db.thinking_scores.find(
                {"user_id": user_id}, {"_id": 0, "habit_scores": 1}
            ).sort("calculated_at", -1).limit(5).to_list(5)
            _problems = await db.problem_lifecycle.find(
                {"user_id": user_id}, {"_id": 0, "category": 1, "count": 1}
            ).to_list(10)

            # Get current session behavior counts
            _session_behavior = session_doc.get("behavior_summary", {})
            root_problem = get_root_problem_for_session(_session_behavior, _thinking, _problems)
        except Exception as e:
            logger.warning(f"[FAST-EVAL] Root problem detection failed: {e}")

        # Load user's persistent focus
        user_focus = None
        try:
            from services.focus_engine import get_user_focus, get_enforcement_message
            user_focus = await get_user_focus(db, user_id)
        except Exception as e:
            logger.warning(f"[FAST-EVAL] Focus load failed: {e}")

        # Get or create session behavior tracker (cached on function)
        _behavior_cache = getattr(evaluate_pending_move, '_behavior_cache', {})
        if session_id not in _behavior_cache:
            _behavior_cache[session_id] = SessionBehaviorTracker()
            evaluate_pending_move._behavior_cache = _behavior_cache
        session_tracker = _behavior_cache[session_id]

        # ─── OPENING GUIDANCE + TRAP (compute BEFORE eval — instant, <1ms) ─────
        opening_guidance_data = None
        trap_warning_data = None
        _guidance_debug = {}
        try:
            teaching_opening = session_doc.get("opening_to_teach") or session_doc.get("opening_key")
            _ota = session_doc.get("opening_teaching_active")
            _guidance_debug = {"teaching_opening": teaching_opening, "active": _ota}
            logger.info(f"[FAST-EVAL] Opening check: teaching_opening={teaching_opening}, active={_ota}")
            if teaching_opening and _ota:
                from services.opening_mastery_tracker import (
                    get_opening_mastery, get_move_guidance, get_trap_warning, get_phase_label
                )
                _mh = session_doc.get("move_history", [])
                mastery = await get_opening_mastery(db, user_id, teaching_opening)
                raw_phase = mastery.get("phase", "introduction")
                # Always use introduction phase during active teaching — guidance should always show
                phase = "introduction" if _ota else raw_phase
                # _mh does NOT include the pending move yet (it's not committed)
                # So the pending user move is at ply len(_mh)
                pending_ply = len(_mh)  # index of the move the user just played

                # Guidance for the move the user JUST played (was it correct?)
                current_guidance = get_move_guidance(teaching_opening, pending_ply, phase)
                # Coach's upcoming move idea (the response to user's move)
                coach_move_guidance = get_move_guidance(teaching_opening, pending_ply + 1, phase)
                # Guidance for the NEXT user move (after coach responds)
                next_guidance = get_move_guidance(teaching_opening, pending_ply + 2, phase)
                _guidance_debug.update({"ply": pending_ply, "raw_phase": raw_phase, "phase": phase, "mh_len": len(_mh), "has_current": current_guidance is not None, "has_coach": coach_move_guidance is not None, "has_next": next_guidance is not None, "next_arrow": next_guidance.get("arrow") if next_guidance else None})
                logger.info(f"[FAST-EVAL] Guidance: {_guidance_debug}")

                if next_guidance or coach_move_guidance:
                    opening_guidance_data = {
                        "opening_key": teaching_opening,
                        "phase": phase,
                        "phase_label": get_phase_label(phase),
                        "games_played": mastery.get("games_played", 0),
                    }
                    # Next user move guidance (with arrow)
                    if next_guidance:
                        opening_guidance_data["move_idea"] = next_guidance.get("idea")
                        opening_guidance_data["expected_move"] = next_guidance.get("move")
                        opening_guidance_data["arrow"] = next_guidance.get("arrow")
                    # Coach's move explanation (no arrow, just idea)
                    if coach_move_guidance:
                        opening_guidance_data["coach_move_idea"] = coach_move_guidance.get("idea")
                        opening_guidance_data["coach_move"] = coach_move_guidance.get("move")

                    # Check if user played the WRONG move for the opening
                    if current_guidance:
                        expected = current_guidance.get("move", "")
                        played_san = ""
                        try:
                            board_check = chess.Board(fen_before)
                            played_san = board_check.san(chess.Move.from_uci(uci))
                        except Exception:
                            pass
                        if expected and played_san and played_san.replace("+", "").replace("#", "").lower() != expected.replace("+", "").replace("#", "").lower():
                            # User deviated — tell them
                            opening_guidance_data["deviation"] = {
                                "played": played_san,
                                "expected": expected,
                                "idea": current_guidance.get("idea", ""),
                            }

                # Trap warning
                moves_played = [m.get("move", "") for m in _mh if isinstance(m, dict)]
                trap_warn = get_trap_warning(teaching_opening, moves_played)
                if trap_warn:
                    trap_warning_data = trap_warn
        except Exception as e:
            logger.warning(f"[FAST-EVAL] Pre-eval guidance failed: {e}")

        # Cache eval_before from last evaluation
        cached_eval = None
        evals = session_doc.get("evaluations", [])
        if evals:
            last_eval = evals[-1]
            cached_eval = last_eval.get("eval_after") or last_eval.get("score")

        # ─── FAST STOCKFISH EVAL ─────
        eval_result = fast_eval(fen_before, uci, cached_eval)

        # If fast_eval failed (all zeros), log it
        if eval_result.get("depth", 0) == 0 and eval_result.get("elapsed_ms", 0) > 500:
            logger.warning(f"[FAST-EVAL] Engine returned empty result, depth=0")

        # If fast_eval returned no useful data (cp_loss=0, no best_move),
        # we still proceed — the heuristic signals will decide.
        # But we should NOT trigger critical based on cp_loss alone if eval is broken.
        eval_is_valid = eval_result.get("depth", 0) > 0

        elapsed_eval = (_time.monotonic() - start) * 1000

        # Hard timeout check — still return checklist/commentary even on timeout
        if elapsed_eval > 1000:
            logger.warning(f"[FAST-EVAL] Hard timeout at {elapsed_eval:.0f}ms")
            # Board reading even on timeout
            _timeout_commentary = None
            if not _timeout_commentary:
                try:
                    from services.position_intelligence import read_board_like_a_coach
                    _timeout_commentary = read_board_like_a_coach(fen_before, user_color, user_rating)
                except Exception:
                    pass
            return {
                "shouldAutoCommit": True,
                "coachingDecision": {"layer": "silent", "gamePhase": "opening" if move_index_preview < 24 else "middlegame"},
                "checklist": {},
                "weaknesses": [{"signal": w["signal"], "label": w["label"], "severity": w["severity"]} for w in top_weaknesses[:3]],
                "playerProfile": player_profile_data,
                "rootProblem": root_problem,
                "focusEnforcement": None,
                "userFocus": user_focus,
                "commentary": _timeout_commentary,
                "openingGuidance": opening_guidance_data,
                "trapWarning": trap_warning_data,
                "coachingMoment": None,
                "moveEvaluation": {
                    "moveQuality": eval_result.get("move_quality", "good"),
                    "cpLoss": eval_result.get("cp_loss", 0),
                    "bestMove": eval_result.get("best_move"),
                },
                "debug": {"elapsedMs": round(elapsed_eval), "depth": 0, "nodes": 0, "guidance": _guidance_debug},
            }

        # ─── SIGNAL DETECTION (< 5ms) ─────
        board_before = chess.Board(fen_before)
        move = chess.Move.from_uci(uci)
        board_after = board_before.copy()
        board_after.push(move)
        color = chess.WHITE if user_color == "white" else chess.BLACK

        fast_signals = detect_signals_fast(
            board_before, board_after, color, eval_result, evals
        )

        # Record signals in session behavior tracker
        try:
            session_tracker.record_signals(move_index_preview, fast_signals)
        except Exception:
            pass

        # ─── 4-LAYER COACHING DECISION ─────
        # Layer: silent / ambient / advisory / critical_interrupt
        # Critical = hold. Everything else = auto-commit with coaching strip.
        move_quality = eval_result.get("move_quality", "good")
        cp_loss_val = eval_result.get("cp_loss", 0)

        # If eval is invalid (engine failed), DON'T trust move_quality for critical decisions.
        # Only trigger critical from heuristics if a real non-pawn piece is hanging.
        if not eval_is_valid:
            # Override: don't classify as mistake/blunder without real eval
            if move_quality in ("mistake", "blunder"):
                move_quality = "good"  # Downgrade — we can't trust this
                logger.info(f"[FAST-EVAL] Downgraded {eval_result.get('move_quality')} to good (eval invalid)")
        move_history = session_doc.get("move_history", [])
        move_number = len(move_history) // 2 + 1
        move_idx = len(move_history) - 1

        # Track last message move for "no silent gap" rule
        last_msg_move = session_doc.get("last_coaching_move_index", -10)
        moves_since_last_msg = move_idx - last_msg_move

        layer = "silent"
        category = None
        text = None
        question = None
        severity = None
        concept_key = None

        from services.coaching_templates import pick_template

        # ─── MISTAKE/BLUNDER HANDLING ─────
        # With the v2 Socratic coaching system, mistakes are teaching moments
        # that happen AFTER the move. Only hold for catastrophic blunders (4+ pawns).
        # Everything else auto-commits so the Socratic question can fire after.
        if move_quality == "blunder" and cp_loss_val >= 400:
            layer = "critical_interrupt"
            severity = "high"
        elif move_quality in ("mistake", "blunder"):
            layer = "advisory"
            severity = "medium"

            if fast_signals.get("hung_piece"):
                hp = fast_signals["hung_piece"]
                concept_key = "hung_piece"
                category = "critical_tactic"
                tmpl = pick_template("critical_interrupt", "hung_piece",
                    {"piece": hp["piece"], "square": hp["square"]}, session_id)
            elif fast_signals.get("missed_threat"):
                mt = fast_signals["missed_threat"]
                concept_key = "ignored_threat"
                category = "critical_tactic"
                tmpl = pick_template("critical_interrupt", "ignored_threat",
                    {"piece": mt["piece"]}, session_id)
            elif fast_signals.get("ignored_capture"):
                ic = fast_signals["ignored_capture"]
                concept_key = "ignored_capture"
                category = "critical_tactic"
                tmpl = pick_template("critical_interrupt", "ignored_capture",
                    {"piece": ic["piece"], "square": ic["square"]}, session_id)
            elif fast_signals.get("lost_winning_position"):
                concept_key = "conversion_failure"
                category = "critical_tactic"
                tmpl = pick_template("critical_interrupt", "conversion_failure", {}, session_id)
            else:
                concept_key = "blunder" if move_quality == "blunder" else "mistake"
                category = "critical_tactic"
                # Generate position-specific detail
                detail = _get_move_detail(board_before, board_after, user_color, cp_loss_val)
                tmpl = pick_template("critical_interrupt", concept_key, {"detail": detail}, session_id)

            text = tmpl.get("text") or "This move needs another look."
            # Clean up empty {detail} placeholders
            if text and "{detail}" in text:
                text = text.replace("{detail}", "").strip()
            question = tmpl.get("question")

        # ─── ADVISORY (drift detection — BEFORE blunders happen) ─────
        # Advisory = "you should adjust". Identifies live issues.
        # Also catches heuristic issues when eval is invalid.
        elif move_quality == "inaccuracy" or (
            move_quality == "good" and (
                fast_signals.get("premature_attack") or
                fast_signals.get("loose_pieces_present") or
                (fast_signals.get("king_unsafe") and fast_signals.get("development_incomplete")) or
                (not eval_is_valid and fast_signals.get("hung_piece")) or
                (not eval_is_valid and fast_signals.get("missed_threat"))
            )
        ):
            # Priority order: heuristic warnings > drift > fundamentals > generic
            if not eval_is_valid and fast_signals.get("hung_piece"):
                hp = fast_signals["hung_piece"]
                layer = "advisory"
                concept_key = "hung_pieces"
                category = "fundamental_warning"
                severity = "medium"
                text = f"Check — your {hp['piece']} on {hp['square']} might be vulnerable."
            elif not eval_is_valid and fast_signals.get("missed_threat"):
                mt = fast_signals["missed_threat"]
                layer = "advisory"
                concept_key = "ignored_threat"
                category = "fundamental_warning"
                severity = "medium"
                text = f"Your {mt['piece']} might be under pressure. Check your opponent's threats."
            elif fast_signals.get("premature_attack"):
                layer = "advisory"
                concept_key = "premature_attack"
                category = "drift_warning"
                severity = "medium"
                tmpl = pick_template("advisory", "premature_attack", {}, session_id)
                text = tmpl["text"]
            elif fast_signals.get("loose_pieces_present"):
                layer = "advisory"
                concept_key = "loose_pieces"
                category = "fundamental_warning"
                severity = "medium"
                tmpl = pick_template("advisory", "loose_pieces", {}, session_id)
                text = tmpl["text"]
            elif fast_signals.get("king_unsafe") and move_number >= 8:
                layer = "advisory"
                concept_key = "king_safety"
                category = "fundamental_warning"
                severity = "medium"
                tmpl = pick_template("advisory", "king_safety", {}, session_id)
                text = tmpl["text"]
            elif fast_signals.get("development_incomplete") and fast_signals.get("is_opening_phase"):
                layer = "advisory"
                concept_key = "development"
                category = "opening_orientation"
                severity = "medium"
                tmpl = pick_template("advisory", "development", {}, session_id)
                text = tmpl["text"]
            elif move_quality == "inaccuracy":
                layer = "advisory"
                concept_key = "inaccuracy"
                category = "plan_guidance"
                severity = "low"
                tmpl = pick_template("advisory", "inaccuracy", {}, session_id)
                text = tmpl["text"]
            # else: fall through to ambient

        # ─── AMBIENT (orientation — describe what's happening) ─────
        # Don't show ambient when position is already lost — not useful
        # Ambient = "this is happening". Objective, position-specific.
        # NOT praise. NOT generic. Must be tied to actual board state.
        position_reasonable = _position_is_reasonable(eval_result, user_color)
        if layer == "silent" and move_quality in ("good", "inaccuracy") and position_reasonable:
            opp_threat = fast_signals.get("opponent_created_threat")

            # PRIORITY 1: Opponent idea (most important ambient signal)
            if opp_threat:
                layer = "ambient"
                concept_key = "opponent_threat"
                category = "opponent_idea"
                severity = "low"
                tmpl = pick_template("ambient", "opponent_threat", {
                    "attacker": opp_threat["attacker"],
                    "target": opp_threat["target"],
                    "square": opp_threat["target_square"],
                }, session_id)
                text = tmpl["text"]

            # PRIORITY 2: Opponent improved activity
            elif fast_signals.get("opponent_improved_activity"):
                layer = "ambient"
                concept_key = "opponent_activity"
                category = "opponent_idea"
                severity = "low"
                tmpl = pick_template("ambient", "opponent_activity", {}, session_id)
                text = tmpl["text"]

            # PRIORITY 3: Center tension
            elif fast_signals.get("center_under_pressure"):
                layer = "ambient"
                concept_key = "center_pressure"
                category = "opponent_idea"
                severity = "low"
                tmpl = pick_template("ambient", "opponent_center_pressure", {}, session_id)
                text = tmpl["text"]

            # PRIORITY 4: King still uncommitted
            elif fast_signals.get("king_unsafe") and move_number >= 10:
                layer = "ambient"
                concept_key = "king_safety_ambient"
                category = "opening_orientation"
                severity = "low"
                tmpl = pick_template("ambient", "king_uncommitted", {}, session_id)
                text = tmpl["text"]

            # PRIORITY 5: Opening phase orientation
            elif fast_signals.get("development_incomplete") and fast_signals.get("is_opening_phase") and move_number >= 5:
                layer = "ambient"
                concept_key = "opening_phase"
                category = "opening_orientation"
                severity = "low"
                tmpl = pick_template("ambient", "development_phase", {}, session_id)
                text = tmpl["text"]

            # PRIORITY 6: Reinforcement (ONLY non-obvious strong moves WITH valid eval)
            # NEVER praise when position is already bad (losing by 1.5+ pawns)
            elif (fast_signals.get("is_strong_move") and fast_signals.get("is_non_obvious")
                  and eval_is_valid and cp_loss_val <= 30
                  and _position_is_reasonable(eval_result, user_color)):
                layer = "ambient"
                concept_key = "reinforcement"
                category = "reinforcement"
                severity = "low"
                tmpl = pick_template("ambient", "strong_move", {}, session_id)
                text = tmpl["text"]

            # else: stay silent — nothing position-specific to say

        # ─── ANTI-SILENCE RULES ─────
        # Rule 1: Force ambient in opening if nothing else triggered
        if layer == "silent" and fast_signals.get("is_opening_phase") and move_number >= 3:
            if move_number <= 6:
                layer = "ambient"
                concept_key = "opening_phase"
                category = "opening_orientation"
                severity = "low"
                tmpl = pick_template("ambient", "development_phase", {}, session_id)
                text = tmpl["text"]
            elif fast_signals.get("king_unsafe"):
                layer = "ambient"
                concept_key = "king_safety_ambient"
                category = "opening_orientation"
                severity = "low"
                tmpl = pick_template("ambient", "king_uncommitted", {}, session_id)
                text = tmpl["text"]

        # Rule 2: No silent gap > 2 moves — force ambient if coach has been quiet
        if layer == "silent" and moves_since_last_msg >= 3:
            # Generate a position-awareness message
            board_for_ambient = board_after if board_after else chess.Board(fen_before)
            _ambient = _generate_gap_filler(board_for_ambient, user_color, move_number, fast_signals, session_id)
            if _ambient:
                layer = _ambient["layer"]
                text = _ambient["text"]
                concept_key = _ambient["concept_key"]
                category = _ambient["category"]
                severity = _ambient["severity"]

        # ─── DUPLICATE SUPPRESSION ─────
        # Same concept within last 8 moves → downgrade to silent (except critical)
        if layer in ("ambient", "advisory") and concept_key:
            recent_decisions = session_doc.get("coaching_decisions", [])
            recent_concepts = [
                d.get("concept_key") for d in recent_decisions[-8:]
                if d.get("concept_key") and d.get("layer") != "silent"
            ]
            if concept_key in recent_concepts:
                # Same concept recently shown — suppress
                layer = "silent"
                text = None
                concept_key = None

        # Also suppress if same TEXT was used recently
        if layer in ("ambient", "advisory") and text:
            recent_decisions = session_doc.get("coaching_decisions", [])
            recent_texts = [d.get("text", "") for d in recent_decisions[-6:] if d.get("text")]
            if text in recent_texts:
                layer = "silent"
                text = None

        # ─── FOCUS ENFORCEMENT ─────
        # If user has a focus and this move violates it, add enforcement
        focus_enforcement = None
        if user_focus and layer in ("critical_interrupt", "advisory"):
            try:
                from services.root_behavior_engine import ROOT_CLUSTERS
                focus_cluster = user_focus.get("cluster")
                focus_signals = ROOT_CLUSTERS.get(focus_cluster, {}).get("signals", [])
                # Check if this concept maps to the focus cluster
                is_focus_violation = concept_key in focus_signals
                if is_focus_violation:
                    # Count violations this game
                    past_decisions = session_doc.get("coaching_decisions", [])
                    focus_violations = sum(
                        1 for d in past_decisions
                        if d.get("concept_key") in focus_signals and d.get("layer") in ("critical_interrupt", "advisory")
                    )
                    focus_enforcement = get_enforcement_message(user_focus, focus_violations + 1)
            except Exception as e:
                logger.warning(f"[FAST-EVAL] Focus enforcement failed: {e}")

        # ─── PATTERN ESCALATION + ADAPTIVE FRICTION ─────
        # Apply player weakness bias, escalate tone, adjust hold time
        extra_hold_ms = 0
        if layer != "silent" and concept_key and text:
            try:
                # Escalation: first → repeated → pattern
                count_this_game = session_tracker.get_concept_count_this_game(concept_key)
                escalation = get_escalation_level(concept_key, count_this_game, top_weaknesses)

                # Modify text tone based on escalation
                if escalation in ("repeated", "pattern"):
                    text = get_escalated_message(concept_key, escalation, text)

                # Upgrade layer if pattern is severe
                if escalation == "pattern" and layer == "advisory":
                    layer = "critical_interrupt"
                    severity = "high"

                # Adaptive friction: more hold time for known weaknesses
                if layer == "critical_interrupt":
                    extra_hold_ms = get_adaptive_hold_boost(concept_key, count_this_game, top_weaknesses)

            except Exception as e:
                logger.warning(f"[FAST-EVAL] Escalation failed: {e}")

        # (Opening guidance + trap warning already computed before eval)

        # ─── BUILD RESPONSE ─────
        elapsed_total = (_time.monotonic() - start) * 1000

        # Track last coaching move index for gap detection
        if layer != "silent":
            try:
                await db.coach_sessions.update_one(
                    {"session_id": session_id},
                    {"$set": {"last_coaching_move_index": move_idx}}
                )
            except Exception:
                pass

        # Save behavior summary periodically (every 10 moves)
        if move_index_preview > 0 and move_index_preview % 10 == 0:
            try:
                from services.player_behavior_tracker import save_session_behavior
                await save_session_behavior(db, session_id, session_tracker)
            except Exception:
                pass

        # ─── FUNDAMENTALS (cheap, pure python-chess, < 5ms) ─────
        # Must run BEFORE commentary (which is expensive)
        game_phase = "opening" if move_number <= 12 else ("middlegame" if move_number <= 30 else "endgame")
        try:
            from services.fundamentals_evaluator import evaluate_fundamentals as _eval_fund
            _fund_board = chess.Board(board_after.fen()) if board_after else chess.Board(fen_before)
            fundamentals_data = _eval_fund(_fund_board, move_history, user_color,
                                           {"cp_loss": cp_loss_val, "move_quality": move_quality})
            logger.info(f"[FAST-EVAL] Fundamentals: phase={fundamentals_data.get('phase')}, count={len(fundamentals_data.get('fundamentals', []))}")
        except Exception as _fe:
            logger.error(f"[FAST-EVAL] Fundamentals eval failed: {_fe}", exc_info=True)
            fundamentals_data = {"phase": game_phase, "fundamentals": []}

        # ─── POSITION COMMENTARY ─────
        # Don't override commentary when opening guidance is active —
        # the CommentaryPanel shows the guidance card separately.
        # Always use real position reading so the board analysis is genuine.
        commentary = None

        if not commentary:
            try:
                from services.position_intelligence import read_board_like_a_coach
                fen_after = board_after.fen() if board_after else fen_before
                commentary = read_board_like_a_coach(fen_after, user_color, user_rating)
                if commentary:
                    logger.info(f"[FAST-EVAL] Commentary generated: {commentary.get('summary', '')[:50]}")
            except Exception as e:
                logger.warning(f"[FAST-EVAL] Board reading failed: {e}")

        # Store decision in session for export/debugging
        try:
            decision_log = {
                "move_index": move_index_preview,
                "move_quality": move_quality,
                "cp_loss": cp_loss_val,
                "layer": layer,
                "category": category,
                "concept_key": concept_key,
                "text": text[:80] if text else None,
                "eval_valid": eval_is_valid,
                "elapsed_ms": round(elapsed_total),
            }
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$push": {"coaching_decisions": decision_log}}
            )
        except Exception:
            pass

        # Silent — no coaching text, but still return fundamentals
        if layer == "silent":
            logger.info(f"[FAST-EVAL] {move_quality}, silent, {elapsed_total:.0f}ms")
            return {
                "shouldAutoCommit": True,
                "coachingDecision": {"layer": "silent", "gamePhase": game_phase},
                "checklist": fundamentals_data,
                "weaknesses": [{"signal": w["signal"], "label": w["label"], "severity": w["severity"]} for w in top_weaknesses[:3]],
                "playerProfile": player_profile_data,
                "rootProblem": root_problem,
                "focusEnforcement": focus_enforcement,
                "userFocus": user_focus,
                "commentary": commentary,
                "openingGuidance": opening_guidance_data,
                "trapWarning": trap_warning_data,
                "moveEvaluation": {
                    "moveQuality": move_quality,
                    "cpLoss": cp_loss_val,
                    "bestMove": eval_result.get("best_move"),
                },
                "debug": {
                    "elapsedMs": round(elapsed_total),
                    "depth": eval_result.get("depth", 0),
                    "nodes": eval_result.get("nodes", 0),
                    "guidance": _guidance_debug,
                },
            }

        # Snapshot: evaluate-pending decision
        try:
            ep_snapshot = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "by": "evaluate_pending",
                "move": uci,
                "move_quality": move_quality,
                "cp_loss": cp_loss_val,
                "layer": layer,
                "category": category,
                "severity": severity,
                "text": text,
                "concept_key": concept_key,
                "commentary": commentary.get("text") if isinstance(commentary, dict) else str(commentary)[:100] if commentary else None,
            }
            await db.coach_sessions.update_one(
                {"session_id": session_id},
                {"$push": {"move_snapshots": ep_snapshot}}
            )
        except Exception:
            pass

        # Compute hold time (only for critical)
        requires_hold = layer == "critical_interrupt"
        min_hold_ms = (_get_hold_ms(layer, severity or "low") + extra_hold_ms) if requires_hold else 0
        should_auto_commit = not requires_hold

        logger.info(
            f"[FAST-EVAL] {move_quality}, layer={layer}, cat={category}, "
            f"hold={requires_hold}, {elapsed_total:.0f}ms"
        )

        # Fundamentals already computed above (fundamentals_data)

        return {
            "shouldAutoCommit": should_auto_commit,
            "coachingDecision": {
                "layer": layer,
                "category": category,
                "severity": severity,
                "text": text,
                "question": {"prompt": question} if question else None,
                "conceptKey": concept_key,
                "requiresHold": requires_hold,
                "minHoldMs": min_hold_ms,
                "showInTimeline": layer in ("critical_interrupt", "advisory"),
                "showInActiveStrip": layer in ("ambient", "advisory"),
                "gamePhase": game_phase,
            },
            "checklist": fundamentals_data,
            "weaknesses": [{"signal": w["signal"], "label": w["label"], "severity": w["severity"]} for w in top_weaknesses[:3]],
            "playerProfile": player_profile_data,
            "commentary": commentary,
            "moveEvaluation": {
                "moveQuality": move_quality,
                "cpLoss": eval_result.get("cp_loss", 0),
                "bestMove": eval_result.get("best_move"),
            },
            "coachingMoment": {
                "messageType": layer,
                "severity": severity,
                "text": text,
                "question": {"prompt": question} if question else None,
                "conceptKey": concept_key,
                "minHoldMs": min_hold_ms,
            } if requires_hold else None,
            "debug": {
                "elapsedMs": round(elapsed_total),
                "depth": eval_result.get("depth", 0),
                "nodes": eval_result.get("nodes", 0),
                "guidance": _guidance_debug,
            },
        }

    except Exception as e:
        elapsed_total = (_time.monotonic() - start) * 1000
        logger.error(f"[FAST-EVAL] Error after {elapsed_total:.0f}ms: {e}")
        try:
            _og = opening_guidance_data
        except NameError:
            _og = None
        try:
            _tw = trap_warning_data
        except NameError:
            _tw = None
        return {"shouldAutoCommit": True, "coachingMoment": None, "coachingDecision": {"layer": "silent"}, "checklist": {}, "weaknesses": [], "playerProfile": None, "commentary": None, "openingGuidance": _og, "trapWarning": _tw}


def _generate_gap_filler(board: chess.Board, user_color: str, move_number: int, signals: dict, session_id: str) -> Optional[Dict]:
    """Generate a position-aware ambient message when coach has been quiet too long."""
    from services.coaching_templates import pick_template

    color = chess.WHITE if user_color == "white" else chess.BLACK
    opponent = not color

    # Priority 1: Describe opponent's activity/pressure
    if signals.get("opponent_created_threat"):
        opp = signals["opponent_created_threat"]
        tmpl = pick_template("ambient", "opponent_threat", {
            "attacker": opp["attacker"], "target": opp["target"], "square": opp["target_square"]
        }, session_id)
        return {"layer": "ambient", "text": tmpl["text"], "concept_key": "opponent_idea",
                "category": "opponent_idea", "severity": "low"}

    if signals.get("opponent_improved_activity"):
        tmpl = pick_template("ambient", "opponent_activity", {}, session_id)
        return {"layer": "ambient", "text": tmpl["text"], "concept_key": "opponent_activity",
                "category": "opponent_idea", "severity": "low"}

    # Priority 2: Describe game phase
    if move_number <= 12:
        # Opening: what's the current state?
        king_sq = board.king(color)
        castled = king_sq in ((chess.G1, chess.C1) if color == chess.WHITE else (chess.G8, chess.C8)) if king_sq else False

        if castled and move_number >= 6:
            return {"layer": "ambient", "text": "King safety is handled. Now focus shifts to piece coordination.",
                    "concept_key": "phase_shift", "category": "opening_orientation", "severity": "low"}

        if not castled and move_number >= 8:
            tmpl = pick_template("ambient", "king_uncommitted", {}, session_id)
            return {"layer": "ambient", "text": tmpl["text"], "concept_key": "king_safety_ambient",
                    "category": "opening_orientation", "severity": "low"}

        tmpl = pick_template("ambient", "development_phase", {}, session_id)
        return {"layer": "ambient", "text": tmpl["text"], "concept_key": "opening_phase",
                "category": "opening_orientation", "severity": "low"}

    elif move_number <= 25:
        # Middlegame: describe tension
        center_sqs = [chess.E4, chess.D4, chess.E5, chess.D5]
        our_center = sum(1 for sq in center_sqs if board.attackers(color, sq))
        opp_center = sum(1 for sq in center_sqs if board.attackers(opponent, sq))

        if opp_center > our_center + 1:
            tmpl = pick_template("ambient", "opponent_center_pressure", {}, session_id)
            return {"layer": "ambient", "text": tmpl["text"], "concept_key": "center_pressure",
                    "category": "opponent_idea", "severity": "low"}

        # Count material for phase awareness
        our_pieces = sum(1 for sq in chess.SQUARES
                         if board.piece_at(sq) and board.piece_at(sq).color == color
                         and board.piece_at(sq).piece_type not in (chess.PAWN, chess.KING))
        opp_pieces = sum(1 for sq in chess.SQUARES
                          if board.piece_at(sq) and board.piece_at(sq).color == opponent
                          and board.piece_at(sq).piece_type not in (chess.PAWN, chess.KING))

        if our_pieces > opp_pieces:
            return {"layer": "ambient", "text": "You have more active pieces. Use the advantage.",
                    "concept_key": "activity_advantage", "category": "plan_guidance", "severity": "low"}

        return {"layer": "ambient", "text": "The middlegame is about coordination and targets.",
                "concept_key": "middlegame_phase", "category": "opening_orientation", "severity": "low"}

    else:
        # Endgame
        return {"layer": "ambient", "text": "In the endgame, king activity and passed pawns matter most.",
                "concept_key": "endgame_phase", "category": "opening_orientation", "severity": "low"}


def _get_move_detail(board_before, board_after, user_color: str, cp_loss: int) -> str:
    """Generate a short position-specific detail for why a move is bad."""
    if not board_before or not board_after:
        return ""
    try:
        color = chess.WHITE if user_color == "white" else chess.BLACK
        opponent = not color

        # Check what opponent can now do
        if board_after.is_check():
            return "Your king is now in check."

        # Check for newly hanging pieces
        for sq in chess.SQUARES:
            p = board_after.piece_at(sq)
            if p and p.color == color and p.piece_type not in (chess.KING, chess.PAWN):
                atts = board_after.attackers(opponent, sq)
                defs = board_after.attackers(color, sq)
                real_atts = [a for a in atts if not board_after.is_pinned(opponent, a)]
                if real_atts and not defs:
                    pn = {2: "knight", 3: "bishop", 4: "rook", 5: "queen"}.get(p.piece_type, "piece")
                    return f"Your {pn} on {chess.square_name(sq)} is now undefended."

        # Check for opponent fork opportunity
        for sq in chess.SQUARES:
            p = board_after.piece_at(sq)
            if p and p.color == opponent and p.piece_type == chess.KNIGHT:
                targets = []
                for t_sq in board_after.attacks(sq):
                    t = board_after.piece_at(t_sq)
                    if t and t.color == color and t.piece_type in (chess.ROOK, chess.QUEEN, chess.KING):
                        targets.append(t)
                if len(targets) >= 2:
                    return "Your opponent has a fork opportunity."

        if cp_loss >= 300:
            return "You lost significant material."
        elif cp_loss >= 150:
            return "Your position weakened considerably."
        return ""
    except Exception:
        return ""


def _position_is_reasonable(eval_result: dict, user_color: str) -> bool:
    """Is the position not already lost? Don't praise or orient when losing badly."""
    eval_after = eval_result.get("eval_after", 0)
    if user_color == "white":
        return eval_after > -1.5  # Not losing by more than 1.5 pawns
    else:
        return eval_after < 1.5  # Not losing by more than 1.5 pawns (as black, positive = losing)


def _build_checklist(signals: dict, move_quality: str, eval_valid: bool, phase: str) -> dict:
    """
    Build pass/fail checklist from fast_eval signals.
    Returns: {"opponent_threats": "passed"|"failed"|"neutral", ...}
    """
    cl = {}

    # 1. Opponent threats: failed if missed_threat or ignored capture
    if signals.get("missed_threat") or signals.get("ignored_capture"):
        cl["opponent_threats"] = "failed"
    elif signals.get("opponent_created_threat"):
        # There was a threat and we didn't miss it
        cl["opponent_threats"] = "passed"
    else:
        cl["opponent_threats"] = "neutral"

    # 2. Piece safety: failed if hung piece
    if signals.get("hung_piece"):
        cl["piece_safety"] = "failed"
    elif move_quality in ("good",) and eval_valid:
        cl["piece_safety"] = "passed"
    else:
        cl["piece_safety"] = "neutral"

    # 3. King safety
    if signals.get("king_unsafe"):
        cl["king_safety"] = "failed"
    else:
        cl["king_safety"] = "passed" if phase != "endgame" else "neutral"

    # 4. Development
    if signals.get("development_incomplete") and phase == "opening":
        cl["development"] = "failed"
    elif phase == "opening":
        cl["development"] = "passed"
    else:
        cl["development"] = "neutral"

    # 5. Center control
    if signals.get("center_under_pressure"):
        cl["center_control"] = "failed"
    else:
        cl["center_control"] = "neutral"

    # 6. Has plan (move purpose)
    if move_quality == "blunder":
        cl["has_plan"] = "failed"
    elif move_quality == "good" and eval_valid:
        cl["has_plan"] = "passed"
    elif signals.get("premature_attack"):
        cl["has_plan"] = "failed"
    else:
        cl["has_plan"] = "neutral"

    # Also add weakness signal mappings for the weakness section
    if signals.get("missed_threat") or signals.get("ignored_capture"):
        cl["ignored_threat"] = "failed"
    elif signals.get("opponent_created_threat"):
        cl["ignored_threat"] = "passed"

    if signals.get("hung_piece"):
        cl["hung_pieces"] = "failed"
    elif move_quality == "good" and eval_valid:
        cl["hung_pieces"] = "passed"

    if signals.get("premature_attack"):
        cl["premature_attack"] = "failed"
    elif move_quality == "good":
        cl["premature_attack"] = "passed"

    if signals.get("king_unsafe"):
        cl["king_safety_weakness"] = "failed"
    else:
        cl["king_safety_weakness"] = "passed" if phase != "endgame" else "neutral"

    if signals.get("development_incomplete") and phase == "opening":
        cl["weak_development"] = "failed"
    elif phase == "opening":
        cl["weak_development"] = "passed"

    return cl


def _get_hold_ms(message_type: str, severity: str) -> int:
    """Compute adaptive hold duration."""
    if message_type == "critical_interrupt":
        return 4000
    if message_type == "pattern_repeat":
        return 5000
    if severity == "medium":
        return 2500
    if message_type == "opening_principle":
        return 2000
    if message_type == "reinforcement":
        return 1500
    return 2000


# ─── TRAINING LOCK ────────────────────────────────────────────────

@router.get("/training-lock")
async def get_training_lock_status(user: User = Depends(get_current_user)):
    """Check if user is training-locked (must complete puzzles before playing)."""
    global db
    try:
        from services.focus_engine import get_user_focus, FOCUS_RULES
        focus = await get_user_focus(db, user.user_id)

        if not focus:
            return {"locked": False, "focus": None}

        locked = focus.get("training_locked", False)
        puzzles_done = focus.get("puzzles_completed", 0)
        puzzles_needed = focus.get("puzzles_required", 5)

        return {
            "locked": locked,
            "focus": {
                "name": focus.get("name"),
                "rule": focus.get("rule"),
                "short_rule": focus.get("short_rule"),
                "cluster": focus.get("cluster"),
                "enforcement_level": focus.get("enforcement_level"),
                "puzzles_completed": puzzles_done,
                "puzzles_required": puzzles_needed,
            },
        }
    except Exception as e:
        logger.warning(f"Training lock check failed: {e}")
        return {"locked": False, "focus": None}


@router.get("/training-lock/puzzles")
async def get_focus_puzzles(user: User = Depends(get_current_user)):
    """Get puzzles matched to the user's focus area."""
    global db
    try:
        from services.focus_engine import get_user_focus, FOCUS_RULES

        focus = await get_user_focus(db, user.user_id)
        if not focus:
            return {"puzzles": [], "focus": None}

        cluster = focus.get("cluster")
        rule_config = FOCUS_RULES.get(cluster, {})
        puzzle_query = rule_config.get("puzzle_query", {})

        # Get puzzles matching the focus pattern types
        query = {
            "source_user_id": user.user_id,
            **puzzle_query,
        }

        puzzles = await db.community_training_positions.find(
            query,
            {"_id": 0, "position_id": 1, "fen": 1, "best_move_san": 1, "best_move_uci": 1,
             "user_move_san": 1, "cp_loss": 1, "pattern_type": 1, "difficulty": 1,
             "move_number": 1, "opening_name": 1}
        ).sort("cp_loss", -1).limit(20).to_list(20)

        # If not enough user puzzles, get community ones
        if len(puzzles) < 10:
            community_query = {**puzzle_query}
            community_query.pop("source_user_id", None)
            extra = await db.community_training_positions.find(
                community_query,
                {"_id": 0, "position_id": 1, "fen": 1, "best_move_san": 1, "best_move_uci": 1,
                 "cp_loss": 1, "pattern_type": 1, "difficulty": 1}
            ).sort("cp_loss", -1).limit(20 - len(puzzles)).to_list(20 - len(puzzles))
            puzzles.extend(extra)

        puzzles_needed = focus.get("puzzles_required", 5)
        puzzles_done = focus.get("puzzles_completed", 0)

        return {
            "puzzles": puzzles,
            "focus": {
                "name": focus.get("name"),
                "rule": focus.get("rule"),
                "cluster": cluster,
                "puzzles_completed": puzzles_done,
                "puzzles_required": puzzles_needed,
            },
        }
    except Exception as e:
        logger.warning(f"Focus puzzles failed: {e}")
        return {"puzzles": [], "focus": None}


@router.post("/training-lock/complete-puzzle")
async def complete_focus_puzzle(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Record that user completed a focus puzzle."""
    global db
    try:
        from services.focus_engine import record_puzzle_completion
        result = await record_puzzle_completion(db, user.user_id)
        return result or {"puzzles_completed": 0, "puzzles_required": 5, "training_locked": True}
    except Exception as e:
        logger.warning(f"Puzzle completion failed: {e}")
        return {"puzzles_completed": 0, "puzzles_required": 5, "training_locked": True}


@router.post("/opening-line-complete")
async def opening_line_complete(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Track when a user completes an opening teaching line."""
    session_id = request.get("session_id")
    opening_key = request.get("opening_key")
    branch_key = request.get("branch_key")
    guided_mode = request.get("guided_mode", True)
    moves_total = request.get("moves_total", 0)
    played_perfectly = request.get("played_perfectly", False)

    if not opening_key:
        return {"ok": True}

    try:
        # Update mastery with this completion
        from services.opening_mastery_tracker import update_mastery_after_game
        mastery = await update_mastery_after_game(
            db, user.user_id, opening_key,
            moves_correct=moves_total if played_perfectly else max(0, moves_total - 2),
            moves_total=moves_total,
            branch_played=branch_key,
        )

        # Store play record for progress tracking
        await db.opening_play_history.insert_one({
            "user_id": user.user_id,
            "session_id": session_id,
            "opening_key": opening_key,
            "branch_key": branch_key,
            "guided_mode": guided_mode,
            "played_perfectly": played_perfectly,
            "moves_total": moves_total,
            "phase": mastery.get("phase", "introduction"),
            "games_played": mastery.get("games_played", 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"[OPENING] Line complete: {opening_key}/{branch_key} guided={guided_mode} perfect={played_perfectly} phase={mastery.get('phase')}")
        return {
            "ok": True,
            "phase": mastery.get("phase"),
            "games_played": mastery.get("games_played"),
            "branches_seen": mastery.get("branches_seen", []),
        }
    except Exception as e:
        logger.warning(f"[OPENING] Line complete tracking failed: {e}")
        return {"ok": True}


def _get_initial_opening_guidance(update_fields: dict, log=None) -> Optional[Dict]:
    """Get opening guidance for the FIRST move + ALL move ideas for client-side guidance."""
    teaching_key = update_fields.get("opening_to_teach") or update_fields.get("opening_key")
    if log:
        log.info(f"[COACH-GUIDANCE] update_fields keys: {list(update_fields.keys())}, teaching_key: {teaching_key}")
    if not teaching_key:
        return None
    try:
        from services.opening_mastery_tracker import (
            get_teaching_line, get_phase_label, INTRODUCTION, OPENING_BRANCH_DATA,
        )
        branch_key = update_fields.get("opening_branch")
        guided_mode = update_fields.get("opening_guided_mode", True)

        # Get the full teaching line for this branch
        all_ideas, branch_info = get_teaching_line(teaching_key, branch_key)
        if log:
            log.info(f"[COACH-GUIDANCE] {teaching_key}: {len(all_ideas)} ideas, branch={branch_info}")

        if all_ideas:
            first = all_ideas[0]
            result = {
                "opening_key": teaching_key,
                "phase": INTRODUCTION,
                "phase_label": get_phase_label(INTRODUCTION),
                "move_idea": first.get("idea"),
                "expected_move": first.get("move"),
                "arrow": first.get("arrow") if guided_mode else None,
                "games_played": 0,
                "all_ideas": all_ideas if guided_mode else [],
                "guided_mode": guided_mode,
            }
            # Include branch info so frontend knows about the variation
            if branch_info:
                result["branch"] = branch_info
            # Include all available branches for this opening
            if teaching_key in OPENING_BRANCH_DATA:
                bd = OPENING_BRANCH_DATA[teaching_key]
                result["has_branches"] = True
                result["branch_point"] = bd["branch_point"]
                # Send all branches so frontend can detect variation switches
                result["all_branches"] = {
                    k: {
                        "name": v["name"],
                        "branch_move": v["branch_move"],
                        "ideas": v.get("ideas", []),
                        "intro": v.get("intro", ""),
                    }
                    for k, v in bd["branches"].items()
                }

            # Include relevant traps for this opening (for client-side awareness)
            try:
                from services.verified_opening_traps import get_all_for_opening
                traps = get_all_for_opening(teaching_key)
                if traps:
                    result["traps"] = [{
                        "trap_id": t.trap_id,
                        "name": t.name,
                        "trap_move": t.trap_move,
                        "setup_moves": t.setup_moves,
                        "explanation": t.explanation,
                        "refutation": t.refutation,
                        "victim_color": t.victim_color,
                        "difficulty": t.difficulty,
                    } for t in traps]
            except Exception:
                pass

            return result
    except Exception as e:
        if log:
            log.error(f"[COACH-GUIDANCE] Failed: {e}")
    return None


def _build_full_opening_line(opening_key: str) -> List[str]:
    """
    Build the full teaching line for an opening by combining:
    main_line + first variation's continuation + sub-variation if exists.

    e.g., Italian Game:
    main_line: e4 e5 Nf3 Nc6 Bc4
    + Giuoco Piano: Bc5 c3 Nf6 d4 exd4 cxd4 Bb4+ Bd2 Bxd2+ Nbxd2
    = 15 moves total
    """
    try:
        from services.opening_theory_tree_service import load_theory_tree
        tree = load_theory_tree()
        opening = tree.get(opening_key, {})

        main_line = list(opening.get("main_line", []))
        if not main_line:
            return []

        # Walk into the first/main variation
        variations = opening.get("variations", {})
        if variations:
            # Pick the first variation (usually the main one)
            first_var_key = list(variations.keys())[0]
            first_var = variations[first_var_key]

            # Add the branching move
            moves_from_parent = first_var.get("moves_from_parent", [])
            if moves_from_parent:
                main_line.extend(moves_from_parent)

            # Add the continuation
            continuation = first_var.get("continuation", [])
            if continuation:
                main_line.extend(continuation)

            # Check for sub-variations
            sub_vars = first_var.get("subvariations", first_var.get("sub_variations", {}))
            if sub_vars and isinstance(sub_vars, dict):
                first_sub_key = list(sub_vars.keys())[0]
                first_sub = sub_vars[first_sub_key]
                sub_moves = first_sub.get("moves", first_sub.get("continuation", []))
                # Don't add sub-variation by default — it's a branch, not the main line

        return main_line
    except Exception:
        return []


def _get_opening_family(name: str) -> str:
    """
    Extract the main opening family from a full opening name.
    'Queens Pawn Opening Chigorin Variation 2...c6' → "Queen's Pawn"
    'Sicilian Defense Old Sicilian Variation 3.Bc4' → "Sicilian Defense"
    'Kings Indian Defense Normal Variation' → "King's Indian"
    """
    if not name or name == "Unknown":
        return "Unknown"

    # Normalize common patterns
    n = name.strip()

    # Known opening families — check longest match first
    FAMILIES = [
        "Queen's Gambit Declined", "Queen's Gambit Accepted", "Queen's Gambit",
        "King's Indian Defense", "King's Indian Attack",
        "Queen's Indian Defense",
        "Nimzo-Indian Defense", "Nimzo-Indian",
        "Grunfeld Defense",
        "Sicilian Defense", "Sicilian Najdorf", "Sicilian Dragon",
        "French Defense",
        "Caro-Kann Defense", "Caro-Kann",
        "Italian Game",
        "Ruy Lopez", "Spanish Opening",
        "Scotch Game",
        "Petrov Defense", "Petrov's Defense",
        "Philidor Defense",
        "Vienna Game",
        "London System",
        "English Opening",
        "Catalan Opening",
        "Dutch Defense",
        "Benoni Defense",
        "Scandinavian Defense",
        "Pirc Defense",
        "Modern Defense",
        "Alekhine Defense",
        "Budapest Gambit",
        "Slav Defense",
        "Reti Opening",
    ]

    # Normalize for matching (remove apostrophes, lowercase)
    n_lower = n.lower().replace("'", "").replace("\u2019", "")

    for family in FAMILIES:
        f_lower = family.lower().replace("'", "").replace("\u2019", "")
        if n_lower.startswith(f_lower):
            return family

    # Fallback: use first 2 words, but clean up
    parts = n.split()
    if len(parts) >= 2:
        # Skip if it's just "Undefined" or numbers
        short = " ".join(parts[:2])
        # Add "Defense/Opening/Game" if the 3rd word is one of those
        if len(parts) >= 3 and parts[2].lower() in ("defense", "opening", "game", "gambit", "system", "attack"):
            short = " ".join(parts[:3])
        return short

    return n


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

    # Query using `opening` field (the one that actually exists on game documents)
    games = await db.games.find(
        {"user_id": user.user_id, "$or": [
            {"opening": {"$exists": True, "$nin": [None, ""]}},
            {"opening_name": {"$exists": True, "$nin": [None, ""]}},
        ]},
        {"_id": 0, "game_id": 1, "opening_name": 1, "opening": 1, "result": 1, "user_color": 1}
    ).sort("imported_at", -1).limit(100).to_list(100)

    # Group by color and opening
    for color_label, color_list in [("white", white_openings), ("black", black_openings)]:
        color_games = [g for g in games if g.get("user_color") == color_label]
        opening_map = {}

        for g in color_games:
            name = g.get("opening") or g.get("opening_name") or "Unknown"
            short = _get_opening_family(name)
            if not short or short == "Unknown":
                continue
            if short not in opening_map:
                opening_map[short] = {"name": short, "games": 0, "wins": 0, "losses": 0, "draws": 0}

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
    opening_name = request.get("opening_name", None)  # Opening name from user's repertoire
    guided_mode = request.get("guided_mode", True)  # True = arrows+ideas, False = test mode
    teaching_focus = request.get("teaching_focus", None)  # e.g. "tactics", "king_safety", "endgame_technique"

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

        # Store opening preference and activate opening teaching if selected
        logger.info(f"[COACH-START] opening_key={opening_key}, opening_name={opening_name}")
        if opening_key or opening_name:
            # Try to match opening_name to an opening_key for the teaching system
            matched_key = opening_key
            if not matched_key and opening_name:
                try:
                    from services.opening_theory_tree_service import load_theory_tree
                    tree = load_theory_tree()
                    # Match opening name — prefer longest/most specific match
                    best_match = None
                    best_match_len = 0
                    for key, data in tree.items():
                        if key == "_meta":
                            continue
                        name = data.get("name", "")
                        if opening_name.lower() in name.lower() or name.lower() in opening_name.lower():
                            match_len = len(name)
                            if match_len > best_match_len:
                                best_match = key
                                best_match_len = match_len
                    matched_key = best_match
                    logger.info(f"[COACH-START] Matched '{opening_name}' -> {matched_key}")
                except Exception as e:
                    logger.warning(f"[COACH-START] Opening match failed: {e}")

            update_fields = {
                "opening_key": matched_key or opening_key,
                "opening_name": opening_name,
            }

            # If we matched to a curriculum opening, activate teaching
            if matched_key:
                try:
                    from services.opening_mastery_tracker import (
                        get_teaching_line, select_branch_for_game, get_opening_mastery,
                        OPENING_BRANCH_DATA,
                    )
                    # Pick which branch to teach based on what user has seen
                    selected_branch = None
                    mastery_doc = await get_opening_mastery(db, user.user_id, matched_key)
                    branches_seen = mastery_doc.get("branches_seen", [])
                    if matched_key in OPENING_BRANCH_DATA:
                        selected_branch = select_branch_for_game(matched_key, branches_seen)
                        logger.info(f"[COACH] Branch selected: {selected_branch} (seen: {branches_seen})")

                    # Build teaching line for the selected branch
                    teaching_ideas, branch_info = get_teaching_line(matched_key, selected_branch)
                    full_line = [idea["move"] for idea in teaching_ideas]

                    if full_line:
                        update_fields.update({
                            "opening_to_teach": matched_key,
                            "opening_teaching_moves": full_line,
                            "opening_teaching_index": 0,
                            "opening_teaching_active": True,
                            "opening_guided_mode": guided_mode,
                            "opening_branch": selected_branch,
                        })
                        logger.info(f"[COACH] Opening teaching activated: {matched_key}, branch={selected_branch}, guided={guided_mode}, {len(full_line)} moves")
                except Exception as e:
                    logger.warning(f"Opening teaching setup failed: {e}")
                    # Fallback to old method
                    try:
                        full_line = _build_full_opening_line(matched_key)
                        if full_line:
                            update_fields.update({
                                "opening_to_teach": matched_key,
                                "opening_teaching_moves": full_line,
                                "opening_teaching_index": 0,
                                "opening_teaching_active": True,
                                "opening_guided_mode": guided_mode,
                            })
                    except Exception:
                        pass

            await db.coach_sessions.update_one(
                {"session_id": session.session_id},
                {"$set": update_fields}
            )

        # Store teaching focus and student weaknesses on session
        focus_update = {}
        if teaching_focus:
            # Map weakness categories to TeachingGoal values
            WEAKNESS_TO_FOCUS = {
                "piece_safety": "tactics",
                "tactical_miss": "tactics",
                "tactical_oversight": "tactics",
                "calculation_depth": "tactics",
                "ignore_threat": "prophylaxis",
                "threat_awareness": "prophylaxis",
                "king_safety": "king_safety",
                "threw_winning": "endgame_technique",
                "endgame_collapse": "endgame_technique",
                "opening_disaster": "development",
                "time_collapse": "natural_play",
                "positional": "piece_activity",
            }
            focus_update["teaching_focus"] = WEAKNESS_TO_FOCUS.get(teaching_focus, teaching_focus)
            logger.info(f"[COACH-START] Teaching focus: {teaching_focus} → {focus_update['teaching_focus']}")

        # Auto-detect student weaknesses from focus engine
        try:
            from services.focus_engine import get_user_focus
            user_focus = await get_user_focus(db, user.user_id)
            if user_focus:
                focus_update["student_weaknesses"] = [user_focus.get("cluster", "")]
                if not teaching_focus:
                    focus_update["teaching_focus"] = WEAKNESS_TO_FOCUS.get(
                        user_focus.get("cluster", ""), "natural_play"
                    )
        except Exception:
            pass

        if focus_update:
            await db.coach_sessions.update_one(
                {"session_id": session.session_id},
                {"$set": focus_update}
            )

        # Clear conversation thread for new game
        try:
            from services.game_conversation_thread import clear_thread
            clear_thread(session.session_id)
        except Exception:
            pass

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

        # Add opening instruction if teaching is active
        if opening_name and update_fields.get("opening_teaching_moves"):
            first_move = update_fields["opening_teaching_moves"][0]
            tree_name = opening_name
            try:
                from services.opening_theory_tree_service import load_theory_tree
                tree = load_theory_tree()
                matched = update_fields.get("opening_key") or update_fields.get("opening_to_teach")
                if matched and matched in tree:
                    tree_name = tree[matched].get("name", opening_name)
                    plan = tree[matched].get("white_plan" if user_color == "white" else "black_plan", "")
                    message = f"Let's practice the {tree_name}. Play {first_move} to begin."
                    if plan:
                        message += f"\n\nYour plan: {plan}"
            except Exception:
                message = f"Let's practice the {tree_name}. Play {first_move} to begin."
        
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
                elif not opening_name:
                    # Fallback: old system picks an opening ONLY if user didn't select one
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
            
            # Surface focus concept from behavior tracker (replaces old watch_for)
            try:
                from services.player_behavior_tracker import get_focus_concept, get_session_focus_message
                focus = await get_focus_concept(db, user.user_id)
                if focus:
                    focus_msg = get_session_focus_message(focus)
                    if focus_msg:
                        welcome_message += f"\n\n{focus_msg}"
                    # Store focus concept in session for reference
                    await db.coach_sessions.update_one(
                        {"session_id": session.session_id},
                        {"$set": {"focus_concept": focus}}
                    )
            except Exception as e:
                logger.warning(f"Focus concept injection failed: {e}")
                # Fallback to old watch_for system
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
            "practice_mode": practice_mode,
            "openingGuidance": _get_initial_opening_guidance(update_fields if (opening_key or opening_name) else {}, logger),
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


async def _promote_session_to_game(db, session_id: str, user_id: str):
    """
    Convert a completed coach session into a games + game_analyses document
    so it appears in the Lab for review and decryption.

    Uses the move history (which already has evals from the live session)
    to build the analysis without needing another Stockfish pass.
    """
    import chess

    session = await db.coach_sessions.find_one({"session_id": session_id})
    if not session:
        return

    # Don't duplicate — check if already promoted
    existing = await db.games.find_one({"coach_session_id": session_id})
    if existing:
        return

    move_history = session.get("move_history", [])
    if len(move_history) < 4:
        return  # Too short to be useful

    user_color = session.get("user_color", "white")

    # Build PGN from move history
    board = chess.Board()
    pgn_moves = []
    for entry in move_history:
        move_san = entry.get("move") if isinstance(entry, dict) else str(entry)
        if not move_san:
            continue
        try:
            move = board.parse_san(move_san)
            pgn_moves.append(board.san(move))
            board.push(move)
        except Exception:
            break

    # Build PGN string
    result_map = {"win": "1-0" if user_color == "white" else "0-1",
                  "loss": "0-1" if user_color == "white" else "1-0",
                  "draw": "1/2-1/2"}
    game_result = result_map.get(session.get("result", ""), "*")

    pgn_parts = []
    for i, san in enumerate(pgn_moves):
        if i % 2 == 0:
            pgn_parts.append(f"{i // 2 + 1}.")
        pgn_parts.append(san)
    pgn_str = " ".join(pgn_parts) + f" {game_result}"

    # Create game document
    game_id = f"coach_{session_id[:12]}"
    opening_name = session.get("opening_name") or session.get("opening_to_teach", "")

    game_doc = {
        "game_id": game_id,
        "user_id": user_id,
        "platform": "coach",
        "pgn": pgn_str,
        "user_color": user_color,
        "result": game_result,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "is_analyzed": True,  # We already have evals
        "coach_session_id": session_id,
        "opponent_name": "Coach",
        "time_control": "untimed",
        "opening": opening_name.replace("_", " ").title() if opening_name else "",
        "white_player": "You" if user_color == "white" else "Coach",
        "black_player": "Coach" if user_color == "white" else "You",
    }

    # Build move evaluations from session data
    move_evaluations = []
    user_moves_only = [m for m in move_history if isinstance(m, dict) and m.get("by") == "player"]

    blunders = 0
    mistakes = 0
    total_cp_loss = 0

    for m in user_moves_only:
        eb = m.get("eval_before")
        ea = m.get("eval_after")
        if eb is None or ea is None:
            continue

        if user_color == "white":
            cp_loss = max(0, int((eb - ea) * 100))
        else:
            cp_loss = max(0, int((ea - eb) * 100))

        total_cp_loss += cp_loss
        if cp_loss >= 300:
            blunders += 1
        elif cp_loss >= 100:
            mistakes += 1

        move_evaluations.append({
            "move": m.get("move"),
            "move_number": move_history.index(m) // 2 + 1,
            "eval_before": eb,
            "eval_after": ea,
            "cp_loss": cp_loss,
            "best_move": m.get("best_move"),
            "fen_before": m.get("fen_before", ""),
            "cognitive_gap": m.get("cognitive_gap"),
            "threat": m.get("threat"),
        })

    total_user_moves = len(user_moves_only)
    accuracy = round((1 - total_cp_loss / max(total_user_moves * 100, 1)) * 100)
    accuracy = max(0, min(100, accuracy))

    analysis_doc = {
        "game_id": game_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stockfish_analysis": {
            "accuracy": accuracy,
            "blunders": blunders,
            "mistakes": mistakes,
            "move_evaluations": move_evaluations,
        },
    }

    await db.games.insert_one(game_doc)
    await db.game_analyses.insert_one(analysis_doc)
    logger.info(f"[COACH] Promoted session {session_id[:8]} → game {game_id} "
                f"({len(pgn_moves)} moves, {blunders}B {mistakes}M, acc={accuracy}%)")


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
                "explanation": get_coach_move_explanation(coach_move_san, fen),
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
        
        # NORMAL PATH: Reuse eval from evaluate-pending (no duplicate Stockfish!)
        # evaluate-pending already ran Stockfish and stored the result in coaching_decisions.
        # We just need to read it and store in move_history for post-game analysis.
        if not await _is_current_revision():
            logger.info(f"Skipping stale coach task for session {session_id}")
            return

        session_doc = await db.coach_sessions.find_one({"session_id": session_id})
        if not session_doc:
            return

        # Get eval data from the coaching_decision that evaluate-pending just stored
        analysis = {"eval_before": 0, "eval_after": 0, "best_move": None,
                    "is_best_move": False, "is_candidate": False, "phase": "middlegame"}
        decisions = session_doc.get("coaching_decisions", [])
        if decisions:
            last_decision = decisions[-1]
            # Use eval from evaluate-pending's fast_eval
            analysis["best_move"] = last_decision.get("best_move")
            cp_loss_from_ep = last_decision.get("cp_loss", 0)
            # Reconstruct rough evals from cp_loss (evaluate-pending stores this)
            analysis["eval_before"] = 0  # Will be overwritten below if available
            analysis["eval_after"] = 0

        # Check if the move_history entry already has eval (from evaluate-pending's fast path)
        move_history = session_doc.get("move_history", [])
        for i in range(len(move_history) - 1, -1, -1):
            if move_history[i].get("move") == user_move and move_history[i].get("by") == "player":
                # If evaluate-pending already stored evals, use them
                if move_history[i].get("eval_before") is not None:
                    analysis["eval_before"] = move_history[i]["eval_before"]
                    analysis["eval_after"] = move_history[i]["eval_after"]
                    analysis["best_move"] = move_history[i].get("best_move", analysis["best_move"])
                    analysis["is_best_move"] = move_history[i].get("is_best_move", False)
                else:
                    # Fallback: run quick analysis only if we have NO eval data at all
                    try:
                        quick = await get_quick_analysis(
                            fen_before=fen_before, move_san=user_move,
                            fen_after=fen_after_user, user_color=user_color,
                            move_number=move_number
                        )
                        analysis = quick
                        move_history[i]["eval_before"] = quick.get("eval_before", 0)
                        move_history[i]["eval_after"] = quick.get("eval_after", 0)
                        move_history[i]["is_best_move"] = quick.get("is_best_move", False)
                        move_history[i]["best_move"] = quick.get("best_move")
                    except Exception:
                        pass

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

        # Generate trigger from cached analysis (no extra Stockfish call)
        trigger = should_coach_speak(
            user_rating=user_rating,
            move_san=user_move,
            eval_before=analysis.get("eval_before", 0),
            eval_after=analysis.get("eval_after", 0),
            is_best_move=analysis.get("is_best_move", False),
            is_candidate=analysis.get("is_candidate", False),
            best_move_san=analysis.get("best_move"),
            phase=analysis.get("phase", "middlegame"),
            move_number=move_number,
            opening_name=analysis.get("opening_name")
        )

        # === FALLBACK DECISION: If evaluate-pending missed this move ===
        try:
            existing_decisions = session_doc.get("coaching_decisions", [])
            move_idx = len(move_history) - 1
            already_has = any(d.get("move_index") == move_idx for d in existing_decisions)

            if not already_has:
                bg_eval_before = analysis.get("eval_before", 0)
                bg_eval_after = analysis.get("eval_after", 0)
                if user_color == "white":
                    bg_cp_loss = max(0, int((bg_eval_before - bg_eval_after) * 100))
                else:
                    bg_cp_loss = max(0, int((bg_eval_after - bg_eval_before) * 100))

                if bg_cp_loss >= 300:
                    bg_quality = "blunder"
                elif bg_cp_loss >= 120:
                    bg_quality = "mistake"
                elif bg_cp_loss >= 60:
                    bg_quality = "inaccuracy"
                else:
                    bg_quality = "good"

                bg_layer = "silent"
                bg_text = None
                bg_category = None

                if bg_quality in ("blunder", "mistake"):
                    bg_layer = "critical_interrupt"
                    _bg_detail = _get_move_detail(
                        chess.Board(fen_before) if fen_before else None,
                        chess.Board(fen_after_user) if fen_after_user else None,
                        user_color, bg_cp_loss)
                    bg_text = f"This move loses ground. {_bg_detail}".strip()
                    bg_category = "critical_tactic"
                elif bg_quality == "inaccuracy":
                    bg_layer = "advisory"
                    bg_text = "There was something more accurate here."
                    bg_category = "plan_guidance"

                fallback_decision = {
                    "move_index": move_idx,
                    "move_quality": bg_quality,
                    "cp_loss": bg_cp_loss,
                    "layer": bg_layer,
                    "category": bg_category,
                    "text": bg_text,
                    "eval_valid": True,
                    "elapsed_ms": 0,
                    "source": "background_fallback",
                }
                await db.coach_sessions.update_one(
                    {"session_id": session_id},
                    {"$push": {"coaching_decisions": fallback_decision}}
                )
        except Exception as e:
            logger.warning(f"Fallback decision failed: {e}")

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
        
        # ═══════════════════════════════════════════════════════════
        # NEW: Message Decision Engine (Step 2.5)
        # Replaces ALL old emitters when enabled.
        # ═══════════════════════════════════════════════════════════
        # The new evaluate-pending endpoint handles all coaching decisions.
        # Skip ALL coaching message emission in this background task.
        engine_handled = True
        try:
            from services.message_decision_engine import ENABLE_DECISION_ENGINE
            engine_handled = ENABLE_DECISION_ENGINE
        except ImportError:
            engine_handled = False

        # ═══════════════════════════════════════════════════════════
        # LEGACY COACHING (skipped when engine handles the move)
        # ═══════════════════════════════════════════════════════════

        # Step 3: MOVE-BY-MOVE COACHING for opening phase
        # During opening, ALWAYS generate a commentary message (not trigger-dependent)
        opening_commentary_sent = False
        if not engine_handled and move_number <= 15:
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
        if not engine_handled and trigger.should_speak and not opening_commentary_sent:
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
        if not engine_handled and not trigger.should_speak:
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

                # Learning loop: get violations from the user's PREVIOUS session
                last_game_violations = []
                try:
                    prev_session = await db.coach_sessions.find_one(
                        {"user_id": user.user_id, "session_id": {"$ne": session_id}},
                        {"fundamental_violations": 1},
                        sort=[("created_at", -1)],
                    )
                    if prev_session and prev_session.get("fundamental_violations"):
                        last_game_violations = list({
                            v.get("fundamental") for v in prev_session["fundamental_violations"]
                            if v.get("fundamental")
                        })
                except Exception:
                    pass  # Non-critical

                # Use Pedagogical Opponent with Teaching Move Selector v2
                from coach_play.coach_opponent import PedagogicalOpponent
                opponent = PedagogicalOpponent(
                    user_rating=user_rating,
                    teaching_mode="balanced",
                    student_weaknesses=student_weaknesses,
                    teaching_focus=teaching_focus,
                    move_history=move_history_san,
                    user_color=user_color,
                    last_game_violations=last_game_violations,
                )
                # If opening teaching is active, use the teaching moves
                coach_move = None
                if session_doc.get("opening_teaching_active"):
                    # Re-fetch session to get latest teaching_index (may have been updated)
                    _fresh_session = await db.coach_sessions.find_one(
                        {"session_id": session_id},
                        {"opening_teaching_moves": 1, "opening_teaching_index": 1, "opening_teaching_active": 1}
                    )
                    if _fresh_session and _fresh_session.get("opening_teaching_active"):
                        teaching_moves = _fresh_session.get("opening_teaching_moves", [])
                        teaching_index = _fresh_session.get("opening_teaching_index", 0)

                        # Find the coach's next move in the teaching line
                        # Verify the user has been following the line — if they deviated, stop teaching
                        current_ply = len(move_history)
                        coach_move_idx = current_ply

                        # Check: did user follow the line up to this point?
                        user_deviated = False
                        for i, entry in enumerate(move_history):
                            if i >= len(teaching_moves):
                                break
                            played = entry.get("move", "") if isinstance(entry, dict) else str(entry)
                            expected = teaching_moves[i]
                            if played.replace("+", "").replace("#", "").lower() != expected.replace("+", "").replace("#", "").lower():
                                user_deviated = True
                                logger.info(f"[COACH] User deviated at move {i}: played {played}, expected {expected}")
                                break

                        if user_deviated:
                            # Stop teaching — user went off-book
                            logger.info(f"[COACH] User deviated from opening line, switching to normal play")
                            await db.coach_sessions.update_one(
                                {"session_id": session_id},
                                {"$set": {"opening_teaching_active": False}}
                            )
                        elif coach_move_idx < len(teaching_moves):
                            expected_move = teaching_moves[coach_move_idx]
                            try:
                                board_check = chess.Board(fen_after_user)
                                board_check.parse_san(expected_move)
                                coach_move = expected_move
                                logger.info(f"[COACH] Teaching move: {expected_move} (index {coach_move_idx}/{len(teaching_moves)})")
                            except Exception:
                                logger.warning(f"[COACH] Teaching move '{expected_move}' illegal at index {coach_move_idx}, stopping teaching")
                                await db.coach_sessions.update_one(
                                    {"session_id": session_id},
                                    {"$set": {"opening_teaching_active": False}}
                                )

                if not coach_move:
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
                        "is_best_move": teaching_context.get("is_best_move", True),
                        # V2 teaching data
                        "teaching_intent": teaching_context.get("teaching_goal"),
                        "intent_reason": teaching_context.get("intent_reason"),
                        "why_instructive": teaching_context.get("why_instructive"),
                        "v2": teaching_context.get("v2", False),
                    })
                    
                    # === COACH MOVE SNAPSHOT: Dump everything ===
                    try:
                        coach_snapshot = {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "move_number": board.fullmove_number,
                            "move": coach_move,
                            "by": "coach",
                            "fen_before": fen_after_user,
                            "fen_after": fen_after_coach,
                            # The entire teaching context — everything about why this move was chosen
                            "teaching_context": teaching_context,
                        }
                        await db.coach_sessions.update_one(
                            {"session_id": session_id},
                            {"$push": {"move_snapshots": coach_snapshot}}
                        )
                        logger.info(f"[SNAPSHOT] Coach {coach_move}: "
                                   f"intent={teaching_context.get('teaching_goal')} "
                                   f"rank={teaching_context.get('eval_rank')}")
                    except Exception as e:
                        logger.warning(f"Coach snapshot failed: {e}")

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
                    if not coach_game_over and len(move_history) <= 24 and not session_doc.get("opening_offer_shown") and not session_doc.get("opening_teaching_active"):
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
                    # When decision engine is active, run coach move through it too
                    coach_move_number = len(move_history) // 2
                    # Coach move coaching is now handled by evaluate-pending on the NEXT user move
                    # (opponent idea signals). No separate coach move message emission needed.
                    if engine_handled and not coach_game_over:
                        pass  # Silent — evaluate-pending handles opponent awareness

                    if not engine_handled and not coach_game_over:
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
                                        "game_phase": teaching_context.get("teaching_content", {}).get("game_phase", "middlegame"),
                                        # V2 enriched data
                                        "v2": teaching_context.get("v2", False),
                                        "intent_reason": teaching_context.get("intent_reason", ""),
                                        "v2_breakdown": teaching_context.get("v2_breakdown", {}),
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
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "explanation": get_coach_move_explanation(coach_move, fen_after_user, fen_after_coach, len(move_history) // 2),
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

                    # Promote to games collection for Lab review
                    try:
                        user_id = session_doc.get("user_id")
                        await _promote_session_to_game(db, session_id, user_id)
                    except Exception as promo_err:
                        logger.warning(f"Session promotion failed (non-fatal): {promo_err}")

                    # P1-2: Auto-trigger full postgame analysis immediately
                    # This attaches detailed review data to the user's profile
                    # right when the game ends, not when the user clicks "Review"
                    try:
                        from services.postgame_analysis import analyze_postgame
                        user_id = session_doc.get("user_id")
                        move_history = session_doc.get("move_history", [])
                        evaluations = session_doc.get("evaluations", [])

                        if move_history and len(move_history) >= 4:
                            await analyze_postgame(
                                db=db,
                                session_id=session_id,
                                user_id=user_id,
                                move_history=move_history,
                                evaluations=evaluations,
                                game_result=result,
                                user_rating=session_doc.get("user_rating", 1200),
                                user_color=session_doc.get("user_color", "white"),
                                time_controls=session_doc.get("time_controls"),
                            )
                            logger.info(f"Auto-analysis completed for session {session_id}")
                    except Exception as analysis_err:
                        logger.warning(f"Auto-analysis failed for {session_id}: {analysis_err}")

            except Exception as e:
                logger.warning(f"Failed to update coach memory: {e}")
            
    except Exception as e:
        logger.error(f"Background move processing failed: {e}")
        # Mark as no longer pending even on error
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"coach_move_pending": False}}
        )


# =============================================================================
# POST-GAME REFLECTION
# =============================================================================

@router.get("/postgame/{session_id}")
async def get_postgame_reflection(session_id: str, user: User = Depends(get_current_user)):
    """
    Post-game reflection — called after game ends.
    Returns: accuracy, top 2 mistakes, pattern check, what to do next.
    Uses postgame_analysis.py which is already fully implemented.
    """
    global db

    # Get session
    session = await db.coach_sessions.find_one(
        {"session_id": session_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    move_history = session.get("move_history", [])
    user_color = session.get("user_color", "white")
    user_rating = session.get("user_rating", 1200)
    game_result = session.get("result", "unknown")

    # Get evaluations from session feedback
    evaluations = []
    feedback_cursor = db.coach_messages.find(
        {"session_id": session_id, "type": "move_feedback"},
        {"_id": 0}
    ).sort("move_number", 1)
    async for msg in feedback_cursor:
        fb = msg.get("feedback", {})
        if fb:
            evaluations.append({
                "move_number": msg.get("move_number", 0),
                "user_move": fb.get("user_move", ""),
                "quality": fb.get("user_move_quality", ""),
                "eval_change": fb.get("user_move_eval_change", 0),
                "best_move": fb.get("best_move", ""),
                "fen_before": fb.get("fen_before", ""),
                "is_sacrifice": fb.get("is_sacrifice", False),
                "is_brilliant": fb.get("is_brilliant", False),
            })

    try:
        from services.postgame_analysis import analyze_postgame
        analysis = await analyze_postgame(
            db=db,
            session_id=session_id,
            user_id=user.user_id,
            move_history=move_history,
            evaluations=evaluations,
            game_result=game_result,
            user_rating=user_rating,
            user_color=user_color,
        )

        # ── ACTIVE PATTERN CHECK ──
        # Did the user repeat the pattern that the coaching system identified?
        pattern_verdict = None
        try:
            # Get the user's active coaching pattern from lab-coach-pick logic
            from services.pattern_memory_service import get_top_patterns
            top_patterns = await get_top_patterns(db, user.user_id, limit=1)
            active_pattern = top_patterns[0].get("pattern_type", "") if top_patterns else ""

            if active_pattern:
                # Check if this game had the active pattern
                pattern_occurrences = 0
                for ev in evaluations:
                    quality = ev.get("quality", "")
                    if quality in ("blunder", "mistake"):
                        # Check cognitive gap from feedback
                        fb_msg = await db.coach_messages.find_one(
                            {"session_id": session_id, "move_number": ev.get("move_number"), "type": "move_feedback"},
                            {"_id": 0, "feedback.cognitive_gap": 1, "feedback.concept_id": 1}
                        )
                        if fb_msg:
                            gap = fb_msg.get("feedback", {}).get("cognitive_gap", "") or fb_msg.get("feedback", {}).get("concept_id", "")
                            if gap == active_pattern:
                                pattern_occurrences += 1

                # Also check V5 coaching data for the pattern
                v5_cursor = db.coach_messages.find(
                    {"session_id": session_id},
                    {"_id": 0, "feedback.concept_id": 1, "feedback.cognitive_gap": 1}
                )
                async for msg in v5_cursor:
                    fb = msg.get("feedback", {})
                    if fb.get("concept_id") == active_pattern or fb.get("cognitive_gap") == active_pattern:
                        pattern_occurrences += 1

                pattern_occurrences = min(pattern_occurrences, 10)  # Cap

                from routes.training_advanced import COACHING_DIAGNOSIS, COACHING_RULES

                diag = COACHING_DIAGNOSIS.get(active_pattern, {})
                rule = COACHING_RULES.get(active_pattern, {})
                pattern_label = active_pattern.replace("_", " ").title()

                if pattern_occurrences == 0:
                    # CASE C: SUCCESS
                    pattern_verdict = {
                        "case": "success",
                        "pattern": active_pattern,
                        "label": pattern_label,
                        "message": f"This time, no {pattern_label.lower()} mistakes.",
                        "detail": f"You checked your opponent before moving. This is real progress.",
                        "cta_label": "Play Again",
                        "cta_href": "/play-with-coach",
                    }
                elif pattern_occurrences == 1:
                    # CASE B: PARTIAL
                    pattern_verdict = {
                        "case": "partial",
                        "pattern": active_pattern,
                        "label": pattern_label,
                        "occurrences": pattern_occurrences,
                        "message": "Better.",
                        "detail": f"You avoided {pattern_label.lower()} in most positions, but missed it once under pressure.",
                        "rule": rule.get("rule", ""),
                        "rule_name": rule.get("name", ""),
                        "cta_label": "Review Game",
                        "cta_href": f"/lab",
                    }
                else:
                    # CASE A: FAILED
                    # Find the worst moment
                    worst_move = None
                    for m in (analysis.mistakes or []):
                        if m.category and active_pattern in m.category.lower().replace(" ", "_"):
                            worst_move = m
                            break
                    if not worst_move and analysis.mistakes:
                        worst_move = analysis.mistakes[0]

                    detail = f"Again, {diag.get('short', pattern_label.lower())}."
                    if worst_move:
                        detail += f" On move {worst_move.move_number}, you played {worst_move.user_move} instead of {worst_move.best_move}."

                    pattern_verdict = {
                        "case": "failed",
                        "pattern": active_pattern,
                        "label": pattern_label,
                        "occurrences": pattern_occurrences,
                        "message": detail,
                        "detail": diag.get("detail", ""),
                        "rule": rule.get("rule", ""),
                        "rule_name": rule.get("name", ""),
                        "cta_label": "Fix This Again",
                        "cta_href": f"/training?focus={active_pattern}",
                    }
        except Exception as pv_err:
            logger.debug(f"Pattern verdict failed (non-fatal): {pv_err}")

        # Extract the key fields for the reflection UI
        return {
            "has_data": True,
            "session_id": session_id,
            "result": game_result,

            # How you played
            "accuracy": analysis.accuracy_percentage,
            "total_blunders": analysis.total_blunders,
            "total_mistakes": analysis.total_mistakes,
            "coach_summary": analysis.coach_summary,
            "encouragement": analysis.encouragement,

            # Two moments that mattered (top 2 mistakes)
            "key_moments": [
                {
                    "move_number": m.move_number,
                    "user_move": m.user_move,
                    "best_move": m.best_move,
                    "position_fen": m.position_fen,
                    "explanation": m.explanation,
                    "category": m.category,
                }
                for m in (analysis.mistakes[:2] if analysis.mistakes else [])
            ],

            # Active pattern verdict (Case A/B/C)
            "pattern_verdict": pattern_verdict,

            # Legacy memory insights
            "memory_insights": [
                {
                    "type": mi.type,
                    "message": mi.message,
                    "pattern": mi.pattern,
                }
                for mi in (analysis.memory_insights or [])
            ],

            # Phase-by-phase breakdown
            "phase_analysis": analysis.phase_analysis,

            # What to do next
            "priority_focus": analysis.priority_focus,
            "training_suggestions": analysis.training_suggestions[:2] if analysis.training_suggestions else [],
            "games_together": analysis.games_together,
        }

    except Exception as e:
        logger.error(f"Postgame analysis failed: {e}")
        # Return minimal reflection even if full analysis fails
        total_moves = len([m for m in move_history if m.get("by") == "player"])
        return {
            "has_data": True,
            "session_id": session_id,
            "result": game_result,
            "accuracy": 0,
            "total_blunders": 0,
            "total_mistakes": 0,
            "coach_summary": f"Good game! You played {total_moves} moves.",
            "encouragement": "Every game is a chance to learn.",
            "key_moments": [],
            "memory_insights": [],
            "priority_focus": "Keep playing and reviewing.",
            "training_suggestions": [],
            "games_together": 0,
        }


# ─── FUNDAMENTALS SUMMARY ─────────────────────────────────────────

@router.get("/fundamentals-summary/{session_id}")
async def get_fundamentals_summary(session_id: str, user=Depends(get_current_user)):
    """Get which fundamentals the player violated during this session."""
    session_doc = await db.coach_sessions.find_one(
        {"session_id": session_id},
        {"fundamental_violations": 1}
    )
    if not session_doc:
        return {"violations": [], "summary": {}}

    violations = session_doc.get("fundamental_violations", [])
    counts = {}
    for v in violations:
        f = v.get("fundamental", "unknown")
        counts[f] = counts.get(f, 0) + 1

    return {"violations": violations, "summary": counts}


# ─── SESSION EXPORT (Debug) ──────────────────────────────────────

@router.get("/export-session/{session_id}")
async def export_session(session_id: str, user=Depends(get_current_user)):
    """Export full session data for debugging — includes all coaching system data."""
    global db
    from datetime import datetime, timezone

    session = await db.coach_sessions.find_one(
        {"session_id": session_id},
        {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = session.get("user_id", "")

    # Messages (match by move_index first, fallback to SAN)
    messages = await db.coach_messages.find(
        {"session_id": session_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    # Postgame
    postgame = await db.postgame_analyses.find_one(
        {"session_id": session_id}, {"_id": 0}
    )

    # Player data
    player_strength = await db.player_strength_profiles.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    player_profile = await db.player_profiles.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    thinking_recent = await db.thinking_scores.find(
        {"user_id": user_id}, {"_id": 0, "habit_scores": 1, "overall_score": 1}
    ).sort("calculated_at", -1).limit(5).to_list(5)
    problems = await db.problem_lifecycle.find(
        {"user_id": user_id}, {"_id": 0}
    ).to_list(10)

    # Build move timeline
    move_history = session.get("move_history", [])
    fen_history = session.get("fen_history", [])
    evaluations = session.get("evaluations", [])

    moves = []
    for i, entry in enumerate(move_history):
        move_data = {
            "index": i,
            "move": entry.get("move") if isinstance(entry, dict) else entry,
            "by": entry.get("by") if isinstance(entry, dict) else None,
        }
        if i < len(fen_history):
            move_data["fen_before"] = fen_history[i]
        if i + 1 < len(fen_history):
            move_data["fen_after"] = fen_history[i + 1]
        if i < len(evaluations):
            move_data["eval"] = evaluations[i]

        # Messages by move_index (preferred) or SAN (fallback)
        move_san = move_data["move"]
        move_msgs = [
            m for m in messages
            if m.get("move_index") == i or
               (m.get("move") == move_san and m.get("move_index") is None)
        ]
        if move_msgs:
            move_data["coaching"] = move_msgs
        moves.append(move_data)

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "summary": {
            "user_id": user_id,
            "user_color": session.get("user_color"),
            "result": session.get("result"),
            "termination": session.get("termination_reason"),
            "total_moves": len(move_history),
            "user_rating": session.get("user_rating"),
            "detected_opening": session.get("detected_opening"),
            "opening_teaching_active": session.get("opening_teaching_active"),
            "focus_concept": session.get("focus_concept"),
            "created_at": session.get("created_at"),
            "ended_at": session.get("ended_at"),
        },
        "moves": moves,
        "messages": messages,
        "evaluations": evaluations,

        # Per-move snapshots — complete coaching data per move
        "move_snapshots": session.get("move_snapshots", []),

        # Decision engine data
        "coaching_decisions": session.get("coaching_decisions", []),
        "mde_debug_logs": session.get("mde_debug_logs", []),
        "behavior_summary": session.get("behavior_summary"),
        "fundamental_violations": session.get("fundamental_violations", []),
        "last_coaching_move_index": session.get("last_coaching_move_index"),

        # Player data — what the system knows about this player
        "player_data": {
            "strength_profile": {
                "strongest": player_strength.get("strongest") if player_strength else None,
                "weakest": player_strength.get("weakest") if player_strength else None,
                "overall_score": player_strength.get("overall_score") if player_strength else None,
                "overall_label": player_strength.get("overall_label") if player_strength else None,
                "domains": player_strength.get("domains") if player_strength else None,
            } if player_strength else None,
            "profile": {
                "average_accuracy": player_profile.get("average_accuracy") if player_profile else None,
                "top_weaknesses": player_profile.get("top_weaknesses") if player_profile else None,
                "phase_accuracy": player_profile.get("phase_accuracy") if player_profile else None,
            } if player_profile else None,
            "recent_habit_scores": thinking_recent,
            "active_problems": problems,
        },

        "postgame": postgame,
        "raw_session": {
            k: v for k, v in session.items()
            if k not in ("fen_history", "move_history", "evaluations", "pgn", "mde_debug_logs")
        },
    }

    return export

