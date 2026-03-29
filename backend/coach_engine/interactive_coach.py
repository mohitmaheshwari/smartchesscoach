"""
Interactive Coach Service

The main brain for "Play with Coach" mode.
Handles:
- Coach playing moves (from opening book or engine)
- Understanding user messages
- Generating teaching moments
- Managing conversation state
- Feedback collection
- Coach personality (varied phrases, memory)
"""

import chess
import chess.engine
import uuid
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum

from .opening_plans import (
    OpeningPlan, OPENING_PLANS, get_opening_by_moves, get_teaching_for_move
)
from .lichess_explorer import (
    get_opening_info, get_popular_moves, get_opening_name, is_opening_phase
)
from .piece_metrics import PieceMetricsAnalyzer, PositionMetrics
from .coach_personality import get_coach_personality, get_coach_phrase, get_memory_comment


class CoachState(Enum):
    """What the coach is currently doing"""
    WAITING_FOR_USER = "waiting_for_user"
    ASKING_QUESTION = "asking_question"
    EXPLAINING = "explaining"
    THINKING = "thinking"


class MessageType(Enum):
    """Types of coach messages"""
    GREETING = "greeting"
    MOVE_COMMENT = "move_comment"
    QUESTION = "question"
    ANSWER_FEEDBACK = "answer_feedback"
    PLAN_EXPLANATION = "plan_explanation"
    POSITION_INSIGHT = "position_insight"
    ENCOURAGEMENT = "encouragement"
    WARNING = "warning"


@dataclass
class CoachMessage:
    """A message from the coach"""
    id: str
    type: MessageType
    text: str
    highlights: List[str] = field(default_factory=list)  # Squares to highlight
    arrows: List[Tuple[str, str, str]] = field(default_factory=list)  # (from, to, color)
    question: Optional[Dict] = None  # For questions: {text, options, correct_idx}
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "highlights": self.highlights,
            "arrows": [(a[0], a[1], a[2]) for a in self.arrows],
            "question": self.question,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class GameSession:
    """Tracks the current game session"""
    session_id: str
    user_id: str
    user_color: str  # "white" or "black"
    moves: List[str] = field(default_factory=list)  # SAN moves
    fens: List[str] = field(default_factory=list)  # Position after each move
    messages: List[CoachMessage] = field(default_factory=list)
    current_opening: Optional[OpeningPlan] = None
    opening_name_from_lichess: str = ""
    state: CoachState = CoachState.WAITING_FOR_USER
    pending_question: Optional[Dict] = None
    feedback: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ==================== INDIAN COACH PERSONALITY ====================

COACH_PERSONALITY = {
    "greeting_white": [
        "You're playing White. Let's start with e4 or d4 - which do you prefer?",
        "White to move. Take your time and think about what you want to do.",
        "Okay, you have White. Remember - develop your pieces and control the center.",
    ],
    "greeting_black": [
        "I'll play first as White. Watch what I do and think about why.",
        "You're Black. Let's see what opening I choose, then you respond.",
        "Okay, I'm White. Pay attention to the plans - I'll explain as we go.",
    ],
    "good_move": [
        "Good move. You're developing nicely.",
        "Yes, that's the right idea.",
        "Good. Keep going.",
        "Correct! You're following the plan.",
    ],
    "explain_my_move": [
        "See why I played this?",
        "Notice what this move does?",
        "This is important - watch this diagonal.",
        "I'm preparing something. Can you guess what?",
    ],
    "ask_plan": [
        "What's your plan here?",
        "Why this move? Tell me your thinking.",
        "What are you trying to do?",
        "Explain your idea to me.",
    ],
    "encourage": [
        "Good thinking!",
        "Yes, you're getting it.",
        "Exactly right.",
        "Now you're playing like a chess player!",
    ],
    "gentle_correction": [
        "Hmm, think again. What did we say about developing?",
        "Wait - is this the best square for this piece?",
        "Before you play that, check: what's your opponent threatening?",
        "Slow down. What's your plan with this move?",
    ],
}


def get_coach_phrase(category: str) -> str:
    """Get a random phrase from a category"""
    import random
    phrases = COACH_PERSONALITY.get(category, [""])
    return random.choice(phrases)


# ==================== MAIN INTERACTIVE COACH ====================

class InteractiveCoach:
    """
    The main interactive coach for "Play with Coach" mode.
    """
    
    def __init__(self, user_id: str, user_rating: int = 1200):
        self.user_id = user_id
        self.user_rating = user_rating
        self.session: Optional[GameSession] = None
        self.board = chess.Board()
        self.stockfish_path = "/usr/games/stockfish"
    
    def start_game(self, user_color: str) -> GameSession:
        """Start a new coaching game"""
        self.session = GameSession(
            session_id=str(uuid.uuid4()),
            user_id=self.user_id,
            user_color=user_color.lower(),
        )
        self.board = chess.Board()
        self.session.fens.append(self.board.fen())
        
        # Send greeting
        if user_color.lower() == "white":
            greeting = get_coach_phrase("greeting_white")
        else:
            greeting = get_coach_phrase("greeting_black")
        
        msg = CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.GREETING,
            text=greeting,
        )
        self.session.messages.append(msg)
        
        return self.session
    
    async def process_user_move(self, move_san: str) -> List[CoachMessage]:
        """
        Process a move made by the user.
        Returns list of coach messages in response.
        """
        if not self.session:
            raise ValueError("No active session")
        
        messages = []
        
        # Try to make the move
        try:
            move = self.board.parse_san(move_san)
            self.board.push(move)
            self.session.moves.append(move_san)
            self.session.fens.append(self.board.fen())
        except Exception as e:
            # Invalid move
            msg = CoachMessage(
                id=str(uuid.uuid4()),
                type=MessageType.WARNING,
                text=f"That move doesn't seem legal. Try again.",
            )
            return [msg]
        
        # Check opening
        move_number = len(self.session.moves)
        
        # Try to identify opening
        if move_number <= 10 and not self.session.current_opening:
            opening = get_opening_by_moves(self.session.moves)
            if opening:
                self.session.current_opening = opening
        
        # Also check Lichess for opening name
        if move_number <= 12 and is_opening_phase(move_number):
            lichess_name = await get_opening_name(self.board.fen())
            if lichess_name:
                self.session.opening_name_from_lichess = lichess_name
        
        # Generate coaching response
        messages = await self._generate_response_to_user_move(move_san, move_number)
        
        self.session.messages.extend(messages)
        return messages
    
    async def _generate_response_to_user_move(
        self, move_san: str, move_number: int
    ) -> List[CoachMessage]:
        """Generate coaching response to user's move using personality system"""
        messages = []
        personality = get_coach_personality()
        
        # Check if move matches opening plan
        if self.session.current_opening:
            teaching = get_teaching_for_move(self.session.current_opening, move_san)
            if teaching:
                msg = CoachMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.MOVE_COMMENT,
                    text=teaching,
                )
                messages.append(msg)
                return messages
        
        # Analyze position for teaching moments
        analyzer = PieceMetricsAnalyzer(self.board)
        metrics = analyzer.analyze()
        
        # Check for common issues
        user_color = chess.WHITE if self.session.user_color == "white" else chess.BLACK
        
        # Check development in opening - varied phrasing
        if move_number <= 10:
            dev_count = (
                metrics.white_developed_count 
                if user_color == chess.WHITE 
                else metrics.black_developed_count
            )
            if dev_count < 2 and move_number >= 5:
                development_tips = [
                    "Remember: develop your knights and bishops before making other moves. They need to get into the game!",
                    "Your minor pieces are still at home. Let's get them into the action!",
                    "Development first! Knights and bishops are waiting to join the battle.",
                    "In the opening, piece development is key. Those knights and bishops want to play!",
                ]
                msg = CoachMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.POSITION_INSIGHT,
                    text=personality._pick_phrase(development_tips, "development"),
                )
                messages.append(msg)
                return messages
        
        # Check castling - varied phrasing
        is_castled = (
            metrics.white_castled if user_color == chess.WHITE else metrics.black_castled
        )
        if move_number >= 8 and not is_castled:
            king_safety = (
                metrics.white_king_safety 
                if user_color == chess.WHITE 
                else metrics.black_king_safety
            )
            if king_safety < 60:
                castle_tips = [
                    "Your king is still in the center. Think about castling soon - a safe king lets you attack freely!",
                    "The center isn't safe for your king much longer. Castle when you can!",
                    "King safety first! Consider tucking your king away before complications arise.",
                    "Your king looks exposed. Castling would give you peace of mind.",
                ]
                msg = CoachMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.WARNING,
                    text=personality._pick_phrase(castle_tips, "castling"),
                    highlights=[chess.square_name(self.board.king(user_color))],
                )
                messages.append(msg)
                return messages
        
        # Check for endgame transition
        total_pieces = len(self.board.piece_map())
        if total_pieces <= 12 and move_number > 20:
            if not hasattr(self.session, '_endgame_announced'):
                self.session._endgame_announced = True
                msg = CoachMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.POSITION_INSIGHT,
                    text=personality.get_endgame_transition(),
                )
                messages.append(msg)
                return messages
        
        # Default: good move comment with variety
        msg = CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.MOVE_COMMENT,
            text=personality.get_good_move_comment(),
        )
        messages.append(msg)
        
        return messages
    
    async def get_coach_move(self) -> Tuple[str, List[CoachMessage]]:
        """
        Get the coach's move and explanation.
        Uses opening book if in opening, otherwise Stockfish.
        """
        if not self.session:
            raise ValueError("No active session")
        
        messages = []
        move_san = ""
        
        move_number = len(self.session.moves) + 1
        
        # Try opening book first
        if is_opening_phase(move_number):
            popular_moves = await get_popular_moves(self.board.fen(), top_n=3)
            if popular_moves and popular_moves[0].total >= 100:
                # Use most popular book move
                move_san = popular_moves[0].san
        
        # If no book move, use Stockfish
        if not move_san:
            move_san = await self._get_stockfish_move()
        
        # Make the move
        try:
            move = self.board.parse_san(move_san)
            self.board.push(move)
            self.session.moves.append(move_san)
            self.session.fens.append(self.board.fen())
        except Exception as e:
            # Fallback
            legal_moves = list(self.board.legal_moves)
            if legal_moves:
                move = legal_moves[0]
                move_san = self.board.san(move)
                self.board.push(move)
                self.session.moves.append(move_san)
                self.session.fens.append(self.board.fen())
        
        # Generate explanation
        messages = await self._generate_explanation_for_coach_move(move_san, move_number)
        
        self.session.messages.extend(messages)
        return move_san, messages
    
    async def _generate_explanation_for_coach_move(
        self, move_san: str, move_number: int
    ) -> List[CoachMessage]:
        """Generate teaching explanation for coach's move"""
        messages = []
        
        # Check if this is an opening move
        if self.session.current_opening:
            teaching = get_teaching_for_move(self.session.current_opening, move_san)
            if teaching:
                msg = CoachMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.PLAN_EXPLANATION,
                    text=f"I played {move_san}. {teaching}",
                )
                messages.append(msg)
                
                # Sometimes ask if user understands
                if move_number in [3, 5, 7]:
                    question_msg = CoachMessage(
                        id=str(uuid.uuid4()),
                        type=MessageType.QUESTION,
                        text="Do you see what I'm planning?",
                        question={
                            "text": "What's the idea behind this move?",
                            "options": [
                                "Developing a piece",
                                "Controlling the center",
                                "Preparing to castle",
                                "I'm not sure"
                            ],
                            "correct_idx": None,  # No single correct answer
                            "free_response": True,
                        }
                    )
                    messages.append(question_msg)
                    self.session.pending_question = question_msg.question
                
                return messages
        
        # Check Lichess opening name
        if self.session.opening_name_from_lichess and move_number <= 6:
            msg = CoachMessage(
                id=str(uuid.uuid4()),
                type=MessageType.PLAN_EXPLANATION,
                text=f"I played {move_san}. This is part of the {self.session.opening_name_from_lichess}.",
            )
            messages.append(msg)
            return messages
        
        # Generic explanation based on position
        msg = CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.MOVE_COMMENT,
            text=f"I played {move_san}. {get_coach_phrase('explain_my_move')}",
        )
        messages.append(msg)
        
        return messages
    
    async def _get_stockfish_move(self, depth: int = 12) -> str:
        """Get a move from Stockfish"""
        try:
            transport, engine = await chess.engine.popen_uci(self.stockfish_path)
            result = await engine.play(
                self.board,
                chess.engine.Limit(depth=depth)
            )
            await engine.quit()
            
            if result.move:
                return self.board.san(result.move)
        except Exception as e:
            print(f"Stockfish error: {e}")
        
        # Fallback: random legal move
        legal = list(self.board.legal_moves)
        if legal:
            return self.board.san(legal[0])
        return ""
    
    async def process_user_message(self, message: str) -> List[CoachMessage]:
        """
        Process a chat message from the user.
        Uses simple pattern matching + context to understand intent.
        """
        if not self.session:
            raise ValueError("No active session")
        
        messages = []
        msg_lower = message.lower().strip()
        
        # Check if user is answering a pending question
        if self.session.pending_question:
            response = self._handle_question_answer(message)
            self.session.pending_question = None
            return [response]
        
        # Pattern matching for common questions
        if any(w in msg_lower for w in ["why", "what", "how", "explain"]):
            # User is asking for explanation
            response = await self._explain_current_position()
            messages.append(response)
        
        elif any(w in msg_lower for w in ["plan", "idea", "goal", "strategy"]):
            # User asking about plan
            response = self._explain_current_plan()
            messages.append(response)
        
        elif any(w in msg_lower for w in ["don't understand", "confused", "lost", "help"]):
            # User needs help
            response = self._provide_help()
            messages.append(response)
        
        elif any(w in msg_lower for w in ["yes", "yeah", "okay", "ok", "got it", "understand"]):
            # User confirms understanding
            response = CoachMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ENCOURAGEMENT,
                text=get_coach_phrase("encourage") + " Your move!",
            )
            messages.append(response)
        
        elif any(w in msg_lower for w in ["no", "nope", "not sure", "idk"]):
            # User doesn't understand
            response = self._provide_help()
            messages.append(response)
        
        else:
            # Default: acknowledge and continue
            response = CoachMessage(
                id=str(uuid.uuid4()),
                type=MessageType.MOVE_COMMENT,
                text="I see. It's your turn - make your move when ready.",
            )
            messages.append(response)
        
        self.session.messages.extend(messages)
        return messages
    
    def _handle_question_answer(self, answer: str) -> CoachMessage:
        """Handle user's answer to a coach question"""
        # For now, just acknowledge any answer positively
        return CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.ANSWER_FEEDBACK,
            text=f"{get_coach_phrase('encourage')} Good thinking. Let's continue - your move!",
        )
    
    async def _explain_current_position(self) -> CoachMessage:
        """Explain what's happening in the current position"""
        analyzer = PieceMetricsAnalyzer(self.board)
        metrics = analyzer.analyze()
        
        explanations = []
        
        # Opening context
        if self.session.current_opening:
            explanations.append(
                f"We're in the {self.session.current_opening.name}. "
                f"{self.session.current_opening.simple_explanation}"
            )
        elif self.session.opening_name_from_lichess:
            explanations.append(
                f"This opening is called the {self.session.opening_name_from_lichess}."
            )
        
        # Development
        move_number = len(self.session.moves)
        if move_number <= 10:
            if metrics.development_lead > 0:
                explanations.append("White has developed more pieces.")
            elif metrics.development_lead < 0:
                explanations.append("Black has developed more pieces.")
        
        # King safety
        if not metrics.white_castled or not metrics.black_castled:
            if not metrics.white_castled:
                explanations.append("White hasn't castled yet.")
            if not metrics.black_castled:
                explanations.append("Black hasn't castled yet.")
        
        text = " ".join(explanations) if explanations else "The position is roughly equal. Focus on developing your pieces and controlling the center."
        
        return CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.POSITION_INSIGHT,
            text=text,
        )
    
    def _explain_current_plan(self) -> CoachMessage:
        """Explain the current plan"""
        if self.session.current_opening:
            ideas = self.session.current_opening.main_ideas
            text = f"In the {self.session.current_opening.name}, the main ideas are:\n"
            for i, idea in enumerate(ideas, 1):
                text += f"{i}. {idea}\n"
            return CoachMessage(
                id=str(uuid.uuid4()),
                type=MessageType.PLAN_EXPLANATION,
                text=text.strip(),
            )
        
        return CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.PLAN_EXPLANATION,
            text="Right now, focus on: 1) Develop your pieces, 2) Control the center, 3) Castle your king to safety.",
        )
    
    def _provide_help(self) -> CoachMessage:
        """Provide help when user is confused"""
        move_number = len(self.session.moves)
        
        if move_number <= 6:
            text = "No problem! In the opening, remember three things:\n"
            text += "1. Develop knights and bishops\n"
            text += "2. Control the center (d4, d5, e4, e5)\n"
            text += "3. Castle early to protect your king"
        else:
            text = "Let me help. Look at the position and ask:\n"
            text += "1. Is my king safe?\n"
            text += "2. Are any pieces not doing anything?\n"
            text += "3. What's my opponent threatening?"
        
        return CoachMessage(
            id=str(uuid.uuid4()),
            type=MessageType.POSITION_INSIGHT,
            text=text,
        )
    
    def submit_feedback(
        self, message_id: str, feedback_type: str, comment: str = ""
    ) -> bool:
        """Record feedback for a coach message"""
        if not self.session:
            return False
        
        self.session.feedback.append({
            "message_id": message_id,
            "feedback_type": feedback_type,
            "comment": comment,
            "fen": self.board.fen(),
            "move_number": len(self.session.moves),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True
    
    def get_session_data(self) -> Dict:
        """Get serializable session data"""
        if not self.session:
            return {}
        
        return {
            "session_id": self.session.session_id,
            "user_id": self.session.user_id,
            "user_color": self.session.user_color,
            "moves": self.session.moves,
            "current_fen": self.board.fen(),
            "opening_name": (
                self.session.current_opening.name 
                if self.session.current_opening 
                else self.session.opening_name_from_lichess
            ),
            "messages": [m.to_dict() for m in self.session.messages],
            "feedback": self.session.feedback,
        }


# ==================== FACTORY ====================

_coaches: Dict[str, InteractiveCoach] = {}


def get_or_create_coach(user_id: str, user_rating: int = 1200) -> InteractiveCoach:
    """Get or create an interactive coach for a user"""
    if user_id not in _coaches:
        _coaches[user_id] = InteractiveCoach(user_id, user_rating)
    return _coaches[user_id]


def clear_coach(user_id: str):
    """Clear coach instance for a user"""
    if user_id in _coaches:
        del _coaches[user_id]
