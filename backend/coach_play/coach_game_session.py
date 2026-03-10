"""
Coach Game Session - Core session management for Play With Coach

Step 1: Bare Session Infrastructure
- Session persistence in MongoDB
- Legal move validation via python-chess
- Board state tracking
- Coach responding with engine move
- Session lifecycle: start → move → coach move → end → summary

No interception, no CPR, no identity yet.
"""

import chess
import chess.engine
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

STOCKFISH_PATH = "/usr/games/stockfish"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    RESIGNED = "resigned"


class GameResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    ONGOING = "ongoing"


@dataclass
class CoachGameSession:
    """Represents a single Play With Coach game session"""
    session_id: str
    user_id: str
    status: SessionStatus
    user_color: str  # "white" or "black"
    
    # Game state
    fen_history: List[str] = field(default_factory=list)
    move_history: List[Dict] = field(default_factory=list)  # [{move, by, timestamp, fen_before}]
    current_fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    # Time control (15+10 rapid)
    time_control: str = "15+10"
    user_time_remaining: float = 900.0  # 15 minutes in seconds
    coach_time_remaining: float = 900.0
    increment: float = 10.0
    
    # Result
    result: Optional[GameResult] = None
    termination_reason: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_move_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # For later phases (empty for now)
    coach_interventions: List[Dict] = field(default_factory=list)
    behavior_events: List[Dict] = field(default_factory=list)
    cpr_before: Optional[float] = None
    cpr_after: Optional[float] = None
    
    # Guardian state (Step 2)
    remaining_interventions: int = 3  # How many times guardian can interrupt
    guardian_overrides: List[Dict] = field(default_factory=list)  # Moves user made despite warnings
    
    # Coach difficulty (based on user rating)
    user_rating: int = 1200  # User's rating for difficulty matching
    coach_skill_level: int = 5  # Stockfish skill level (0-20)
    
    # Async coaching state
    coach_move_pending: bool = False  # Whether coach is still thinking
    last_coach_move: Optional[Dict] = None  # Last move made by coach
    evaluation: Optional[Dict] = None  # Current position evaluation
    
    # Opening Teaching State (Interactive Learning)
    teaching_mode: Optional[str] = None  # "main_line", "trap", or None
    teaching_opening: Optional[str] = None  # Opening key being taught
    teaching_data: Optional[Dict] = field(default_factory=dict)  # Current teaching state
    detected_opening: Optional[str] = None  # Opening detected in this game
    opening_offer_shown: bool = False  # Whether we've offered teaching for this opening
    
    # Learning Progress (per game)
    openings_taught_this_game: List[str] = field(default_factory=list)
    habits_checked: List[str] = field(default_factory=list)  # Which habits were monitored
    habit_violations: List[Dict] = field(default_factory=list)  # Habit violations detected
    
    # Move evaluations for post-game analysis
    evaluations: List[Dict] = field(default_factory=list)  # [{move_number, move, score, eval_before, eval_after}]
    
    # Proactive Opening Teaching State
    opening_to_teach: Optional[str] = None  # Opening key to teach this game
    opening_teaching_moves: List[str] = field(default_factory=list)  # Moves to guide player through
    opening_teaching_index: int = 0  # Current teaching move index
    opening_teaching_active: bool = False  # Whether we're actively teaching
    suggested_trap: Optional[Dict] = field(default_factory=dict)  # Trap suggestion for this opening
    available_traps: List[Dict] = field(default_factory=list)  # All traps available in this opening
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        data['status'] = self.status.value
        data['result'] = self.result.value if self.result else None
        data['created_at'] = self.created_at.isoformat()
        if self.last_move_at:
            data['last_move_at'] = self.last_move_at.isoformat()
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CoachGameSession':
        """Create from MongoDB document"""
        data['status'] = SessionStatus(data['status'])
        # Handle None result (game in progress)
        if data.get('result') is not None:
            data['result'] = GameResult(data['result'])
        else:
            data['result'] = None
        data['created_at'] = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        if data.get('last_move_at'):
            data['last_move_at'] = datetime.fromisoformat(data['last_move_at']) if isinstance(data['last_move_at'], str) else data['last_move_at']
        if data.get('ended_at'):
            data['ended_at'] = datetime.fromisoformat(data['ended_at']) if isinstance(data['ended_at'], str) else data['ended_at']
        # Remove MongoDB _id if present
        data.pop('_id', None)
        return cls(**data)


async def start_coach_session(
    db: AsyncIOMotorDatabase,
    user_id: str,
    user_color: str = "white",
    time_control: str = "15+10",
    starting_fen: str = None,
    practice_mode: bool = False,
    source_game_id: str = None
) -> CoachGameSession:
    """
    Start a new Play With Coach session.
    
    Args:
        db: MongoDB database
        user_id: User's ID
        user_color: "white" or "black"
        time_control: Time format (default 15+10 rapid)
        starting_fen: Custom starting position (optional, for practice mode)
        practice_mode: Whether this is practice mode
        source_game_id: Game ID this practice is from
    
    Returns:
        New CoachGameSession
    """
    # Parse time control
    base_time, increment = 900.0, 10.0  # Default 15+10
    if time_control:
        parts = time_control.split("+")
        if len(parts) == 2:
            base_time = float(parts[0]) * 60  # Convert minutes to seconds
            increment = float(parts[1])
    
    # Get user's rating from player_profiles
    from .coach_opponent import rating_to_skill_level
    user_rating = 1200  # Default
    player_profile = await db.player_profiles.find_one({"user_id": user_id})
    if player_profile:
        # Use their highest rating from any platform
        lichess_rating = player_profile.get("lichess_stats", {}).get("rating", 0)
        chesscom_rating = player_profile.get("chesscom_stats", {}).get("rating", 0)
        user_rating = max(lichess_rating, chesscom_rating, 1200)
    
    skill_level = rating_to_skill_level(user_rating)
    
    # Use custom starting position or default
    initial_fen = starting_fen if starting_fen else "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    session = CoachGameSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        status=SessionStatus.ACTIVE,
        user_color=user_color,
        time_control=time_control,
        user_time_remaining=base_time,
        coach_time_remaining=base_time,
        increment=increment,
        fen_history=[initial_fen],
        current_fen=initial_fen,
        user_rating=user_rating,
        coach_skill_level=skill_level
    )
    
    # Add practice mode metadata
    if practice_mode:
        session_dict = session.to_dict()
        session_dict['practice_mode'] = True
        session_dict['source_game_id'] = source_game_id
        await db.coach_sessions.insert_one(session_dict)
    else:
        # Save to database
        await db.coach_sessions.insert_one(session.to_dict())
    
    # Determine whose turn based on FEN
    fen_parts = initial_fen.split(' ')
    to_move = fen_parts[1] if len(fen_parts) > 1 else 'w'
    coach_color = "black" if user_color == "white" else "white"
    coach_to_move = (to_move == 'w' and coach_color == "white") or (to_move == 'b' and coach_color == "black")
    
    # If it's coach's turn, coach plays first
    if coach_to_move:
        session = await _make_coach_move(db, session)
    
    return session


async def make_player_move(
    db: AsyncIOMotorDatabase,
    session_id: str,
    move_san: str,
    time_spent: float = 0.0
) -> Dict[str, Any]:
    """
    Process a player's move in the session.
    
    Args:
        db: MongoDB database
        session_id: Session ID
        move_san: Move in SAN notation (e.g., "e4", "Nf3", "O-O")
        time_spent: Time spent on this move in seconds
    
    Returns:
        Dict with:
        - success: bool
        - session: Updated session state
        - coach_move: Coach's response move (if game continues)
        - game_over: bool
        - result: Game result if over
        - error: Error message if failed
    """
    # Load session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"success": False, "error": "Session not found"}
    
    session = CoachGameSession.from_dict(session_doc)
    
    if session.status != SessionStatus.ACTIVE:
        return {"success": False, "error": f"Session is {session.status.value}"}
    
    # Validate it's player's turn
    board = chess.Board(session.current_fen)
    is_white_turn = board.turn == chess.WHITE
    is_player_turn = (is_white_turn and session.user_color == "white") or \
                     (not is_white_turn and session.user_color == "black")
    
    if not is_player_turn:
        return {"success": False, "error": "Not your turn"}
    
    # Validate and make move
    try:
        move = board.parse_san(move_san)
    except ValueError:
        return {"success": False, "error": f"Invalid move: {move_san}"}
    
    if move not in board.legal_moves:
        return {"success": False, "error": f"Illegal move: {move_san}"}
    
    # Record move
    fen_before = session.current_fen
    board.push(move)
    new_fen = board.fen()
    
    # Extract behaviors for this move (Step 3)
    from .live_behavior_extractor import extract_behaviors_from_move
    
    behavior_events = extract_behaviors_from_move(
        fen_before=fen_before,
        move_san=move_san,
        fen_after=new_fen,
        time_spent=time_spent,
        time_remaining=session.user_time_remaining,
        move_quality="accurate",  # Simplified - would need engine eval for real classification
        session_behavior_history=session.behavior_events
    )
    
    # Add new behavior events to session
    session.behavior_events.extend(behavior_events)
    
    session.move_history.append({
        "move": move_san,
        "uci": move.uci(),
        "by": "player",
        "fen_before": fen_before,
        "fen_after": new_fen,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "time_spent": time_spent,
        "behavior_events": behavior_events  # Attach behaviors to move
    })
    session.fen_history.append(new_fen)
    session.current_fen = new_fen
    session.last_move_at = datetime.now(timezone.utc)
    
    # Deduct time (add increment)
    session.user_time_remaining = max(0, session.user_time_remaining - time_spent + session.increment)
    
    # Check if game is over after player move
    game_over, result, reason = _check_game_over(board, session)
    if game_over:
        session.status = SessionStatus.COMPLETED
        session.result = result
        session.termination_reason = reason
        session.ended_at = datetime.now(timezone.utc)
        await _save_session(db, session)
        return {
            "success": True,
            "session": session.to_dict(),
            "game_over": True,
            "result": result.value,
            "termination_reason": reason,
            "evaluation": {"score": 0.0, "mate_in": None}  # Game over, eval not meaningful
        }
    
    # Coach responds
    session = await _make_coach_move(db, session)
    
    # Check if game is over after coach move
    board = chess.Board(session.current_fen)
    game_over, result, reason = _check_game_over(board, session)
    if game_over:
        session.status = SessionStatus.COMPLETED
        session.result = result
        session.termination_reason = reason
        session.ended_at = datetime.now(timezone.utc)
    
    await _save_session(db, session)
    
    # Get evaluation for the eval bar
    from .coach_opponent import CoachOpponent
    eval_score, mate_in = 0.0, None
    if not game_over:
        opponent = CoachOpponent(user_rating=session.user_rating)
        eval_score, mate_in = await opponent.get_evaluation(session.current_fen)
    
    return {
        "success": True,
        "session": session.to_dict(),
        "coach_move": session.move_history[-1] if session.move_history and session.move_history[-1]["by"] == "coach" else None,
        "game_over": game_over,
        "result": result.value if game_over else None,
        "termination_reason": reason if game_over else None,
        "evaluation": {
            "score": eval_score,
            "mate_in": mate_in
        }
    }


async def get_session_state(
    db: AsyncIOMotorDatabase,
    session_id: str
) -> Optional[Dict]:
    """Get current state of a session"""
    from .coach_opponent import CoachOpponent
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return None
    
    session = CoachGameSession.from_dict(session_doc)
    
    # Determine whose turn it is
    board = chess.Board(session.current_fen)
    is_white_turn = board.turn == chess.WHITE
    is_player_turn = (is_white_turn and session.user_color == "white") or \
                     (not is_white_turn and session.user_color == "black")
    
    # Get position evaluation for the eval bar
    opponent = CoachOpponent(user_rating=session.user_rating)
    eval_score, mate_in = await opponent.get_evaluation(session.current_fen)
    
    # Check for opening teaching guidance
    opening_guidance = None
    if session_doc.get("opening_teaching_active"):
        from services.opening_mastery import get_move_guidance
        
        opening_key = session_doc.get("opening_to_teach")
        teaching_index = session_doc.get("opening_teaching_index", 0)
        suggested_trap = session_doc.get("suggested_trap")
        available_traps = session_doc.get("available_traps", [])
        
        if opening_key:
            guidance = get_move_guidance(opening_key, teaching_index, session.user_color)
            if guidance:
                opening_guidance = {
                    "opening_key": opening_key,
                    "teaching_active": True,
                    "move_index": teaching_index,
                    "guidance": guidance,
                    "suggested_trap": suggested_trap,
                    "available_traps": available_traps
                }
    
    return {
        "session": session.to_dict(),
        "current_fen": session.current_fen,
        "is_player_turn": is_player_turn,
        "legal_moves": [board.san(m) for m in board.legal_moves],
        "move_count": len(session.move_history),
        "game_over": session.status != SessionStatus.ACTIVE,
        "evaluation": {
            "score": eval_score,  # From white's perspective
            "mate_in": mate_in    # None or number of moves to mate
        },
        "opening_teaching": opening_guidance
    }


async def end_coach_session(
    db: AsyncIOMotorDatabase,
    session_id: str,
    reason: str = "resigned"
) -> Dict[str, Any]:
    """
    End a session (resign, abort, etc.)
    
    Computes CPR (Step 4) and updates Identity (Step 5) on session end.
    
    Args:
        db: MongoDB database
        session_id: Session ID
        reason: Reason for ending (resigned, abandoned, timeout)
    
    Returns:
        Dict with session summary, CPR, and identity
    """
    from .cpr_engine import compute_session_cpr
    from .identity_engine import update_player_identity
    
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"success": False, "error": "Session not found"}
    
    session = CoachGameSession.from_dict(session_doc)
    
    if session.status != SessionStatus.ACTIVE:
        return {"success": False, "error": f"Session already {session.status.value}"}
    
    # End the session
    session.status = SessionStatus.RESIGNED if reason == "resigned" else SessionStatus.ABANDONED
    session.result = GameResult.LOSS  # User loses if they resign/abandon
    session.termination_reason = reason
    session.ended_at = datetime.now(timezone.utc)
    
    # Generate basic summary
    summary = _generate_session_summary(session)
    
    # Compute CPR (Step 4)
    player_moves = [m for m in session.move_history if m.get("by") == "player"]
    avg_time = sum(m.get("time_spent", 0) for m in player_moves) / len(player_moves) if player_moves else 10.0
    
    session_stats = {
        "move_count": len(player_moves),
        "accuracy": 70.0,  # Default - would need engine analysis for real value
        "avg_time_per_move": avg_time,
        "time_control_base": session.user_time_remaining + sum(m.get("time_spent", 0) for m in player_moves),
        "blunders": 0,
        "mistakes": 0,
        "guardian_overrides": len(session.guardian_overrides)
    }
    
    cpr_result = compute_session_cpr(session.behavior_events, session_stats)
    session.cpr_after = cpr_result["overall_cpr"]
    
    # Update player identity (Step 5)
    existing_identity = await db.player_identity.find_one({"user_id": session.user_id})
    identity_dict = existing_identity if existing_identity else None
    if identity_dict:
        identity_dict.pop("_id", None)
    
    updated_identity = update_player_identity(
        user_id=session.user_id,
        existing_identity=identity_dict,
        behavior_events=session.behavior_events,
        session_result=session.result.value,
        cpr_score=cpr_result["overall_cpr"]
    )
    
    # Save updated identity
    await db.player_identity.replace_one(
        {"user_id": session.user_id},
        updated_identity,
        upsert=True
    )
    
    await _save_session(db, session)
    
    return {
        "success": True,
        "session": session.to_dict(),
        "summary": summary,
        "cpr": cpr_result,
        "identity": updated_identity
    }


async def _make_coach_move(
    db: AsyncIOMotorDatabase,
    session: CoachGameSession
) -> CoachGameSession:
    """
    Coach makes a move using Stockfish.
    
    Uses skill level matched to user's rating.
    """
    from .coach_opponent import CoachOpponent
    
    # Create opponent with user's rating for difficulty matching
    opponent = CoachOpponent(user_rating=session.user_rating)
    coach_move = await opponent.get_move(session.current_fen)
    
    if not coach_move:
        # Fallback: if no move found, game might be over
        return session
    
    # Apply the move
    board = chess.Board(session.current_fen)
    try:
        move = board.parse_san(coach_move)
        fen_before = session.current_fen
        board.push(move)
        new_fen = board.fen()
        
        session.move_history.append({
            "move": coach_move,
            "uci": move.uci(),
            "by": "coach",
            "fen_before": fen_before,
            "fen_after": new_fen,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time_spent": 0  # Coach doesn't spend "real" time
        })
        session.fen_history.append(new_fen)
        session.current_fen = new_fen
        session.last_move_at = datetime.now(timezone.utc)
        
    except Exception as e:
        print(f"Error making coach move: {e}")
    
    return session


async def _save_session(db: AsyncIOMotorDatabase, session: CoachGameSession):
    """Save session to database"""
    await db.coach_sessions.replace_one(
        {"session_id": session.session_id},
        session.to_dict()
    )


def _check_game_over(board: chess.Board, session: CoachGameSession) -> tuple:
    """
    Check if game is over.
    
    Returns:
        (game_over: bool, result: GameResult, reason: str)
    """
    if board.is_checkmate():
        # Who got checkmated?
        loser_is_white = board.turn == chess.WHITE
        user_lost = (loser_is_white and session.user_color == "white") or \
                    (not loser_is_white and session.user_color == "black")
        return (True, GameResult.LOSS if user_lost else GameResult.WIN, "checkmate")
    
    if board.is_stalemate():
        return (True, GameResult.DRAW, "stalemate")
    
    if board.is_insufficient_material():
        return (True, GameResult.DRAW, "insufficient_material")
    
    if board.can_claim_fifty_moves():
        return (True, GameResult.DRAW, "fifty_moves")
    
    if board.can_claim_threefold_repetition():
        return (True, GameResult.DRAW, "threefold_repetition")
    
    # Check time (simplified - would need real clock tracking)
    if session.user_time_remaining <= 0:
        return (True, GameResult.LOSS, "timeout")
    
    return (False, GameResult.ONGOING, "")


def _generate_session_summary(session: CoachGameSession) -> Dict:
    """Generate a summary of the completed session"""
    total_moves = len(session.move_history)
    player_moves = [m for m in session.move_history if m["by"] == "player"]
    coach_moves = [m for m in session.move_history if m["by"] == "coach"]
    
    # Calculate average time per move
    player_times = [m.get("time_spent", 0) for m in player_moves]
    avg_time = sum(player_times) / len(player_times) if player_times else 0
    
    return {
        "session_id": session.session_id,
        "result": session.result.value,
        "termination_reason": session.termination_reason,
        "total_moves": total_moves,
        "player_moves": len(player_moves),
        "coach_moves": len(coach_moves),
        "avg_time_per_move": round(avg_time, 2),
        "duration_seconds": (session.ended_at - session.created_at).total_seconds() if session.ended_at else 0,
        "user_color": session.user_color,
        # Placeholders for later phases
        "interventions_count": len(session.coach_interventions),
        "behavior_events_count": len(session.behavior_events),
        "cpr_change": None  # Will be implemented in Phase 4
    }
