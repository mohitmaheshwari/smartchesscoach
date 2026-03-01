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
    result: GameResult = GameResult.ONGOING
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
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        data['status'] = self.status.value
        data['result'] = self.result.value
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
        data['result'] = GameResult(data['result'])
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
    time_control: str = "15+10"
) -> CoachGameSession:
    """
    Start a new Play With Coach session.
    
    Args:
        db: MongoDB database
        user_id: User's ID
        user_color: "white" or "black"
        time_control: Time format (default 15+10 rapid)
    
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
    
    session = CoachGameSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        status=SessionStatus.ACTIVE,
        user_color=user_color,
        time_control=time_control,
        user_time_remaining=base_time,
        coach_time_remaining=base_time,
        increment=increment,
        fen_history=["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"],
        current_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    
    # Save to database
    await db.coach_sessions.insert_one(session.to_dict())
    
    # If user is black, coach (white) plays first
    if user_color == "black":
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
            "termination_reason": reason
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
    
    return {
        "success": True,
        "session": session.to_dict(),
        "coach_move": session.move_history[-1] if session.move_history and session.move_history[-1]["by"] == "coach" else None,
        "game_over": game_over,
        "result": result.value if game_over else None,
        "termination_reason": reason if game_over else None
    }


async def get_session_state(
    db: AsyncIOMotorDatabase,
    session_id: str
) -> Optional[Dict]:
    """Get current state of a session"""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return None
    
    session = CoachGameSession.from_dict(session_doc)
    
    # Determine whose turn it is
    board = chess.Board(session.current_fen)
    is_white_turn = board.turn == chess.WHITE
    is_player_turn = (is_white_turn and session.user_color == "white") or \
                     (not is_white_turn and session.user_color == "black")
    
    return {
        "session": session.to_dict(),
        "current_fen": session.current_fen,
        "is_player_turn": is_player_turn,
        "legal_moves": [board.san(m) for m in board.legal_moves],
        "move_count": len(session.move_history),
        "game_over": session.status != SessionStatus.ACTIVE
    }


async def end_coach_session(
    db: AsyncIOMotorDatabase,
    session_id: str,
    reason: str = "resigned"
) -> Dict[str, Any]:
    """
    End a session (resign, abort, etc.)
    
    Args:
        db: MongoDB database
        session_id: Session ID
        reason: Reason for ending (resigned, abandoned, timeout)
    
    Returns:
        Dict with session summary
    """
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
    
    await _save_session(db, session)
    
    # Generate summary
    summary = _generate_session_summary(session)
    
    return {
        "success": True,
        "session": session.to_dict(),
        "summary": summary
    }


async def _make_coach_move(
    db: AsyncIOMotorDatabase,
    session: CoachGameSession
) -> CoachGameSession:
    """
    Coach makes a move using Stockfish.
    
    For Step 1, coach just plays the strongest move.
    Later phases will add pedagogical opponent logic.
    """
    from .coach_opponent import CoachOpponent
    
    opponent = CoachOpponent()
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
