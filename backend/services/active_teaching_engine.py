"""
Active Teaching Engine
======================

Provides real-time, conversational, Socratic coaching during play.
This is the "human coach" experience - guiding the student through each move.

Philosophy:
- Ask questions, don't just give answers
- Guide the student's thinking process
- Celebrate good decisions, gently correct mistakes
- Adapt tone and complexity to student level
- Use plain, simple Indian-English

Teaching Moments:
1. BEFORE opponent moves: "What do you think I'm planning?"
2. AFTER opponent moves: "Why do you think I played that?"
3. BEFORE student moves: "What are you considering? What's your plan?"
4. AFTER student moves: "Let's think about what this move does..."

Socratic Method:
- Don't tell them the answer
- Ask questions that lead to understanding
- Make them think, not just memorize
- Connect concepts to their experience

Usage:
    engine = ActiveTeachingEngine()
    feedback = engine.generate_feedback(
        board=board,
        last_move=move,
        student_rating=1200,
        phase="before_student_move"
    )
"""

import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import random
import logging

logger = logging.getLogger(__name__)


class TeachingPhase(str, Enum):
    """When in the move cycle are we teaching?"""
    BEFORE_COACH_MOVE = "before_coach_move"    # Coach is about to play
    AFTER_COACH_MOVE = "after_coach_move"      # Coach just played
    BEFORE_STUDENT_MOVE = "before_student_move" # Student is thinking
    AFTER_STUDENT_MOVE = "after_student_move"   # Student just played
    GAME_START = "game_start"                  # Beginning of game
    GAME_END = "game_end"                      # Game is over


class FeedbackType(str, Enum):
    """Type of feedback to give."""
    QUESTION = "question"           # Ask the student something
    EXPLANATION = "explanation"     # Explain a concept
    ENCOURAGEMENT = "encouragement" # Positive reinforcement
    GENTLE_CORRECTION = "gentle_correction"  # Point out mistake kindly
    CHALLENGE = "challenge"         # Challenge them to think deeper
    HINT = "hint"                  # Give a subtle hint
    CELEBRATION = "celebration"    # Celebrate good play


@dataclass
class TeachingFeedback:
    """Complete teaching feedback for a moment."""
    message: str
    feedback_type: FeedbackType
    concept: Optional[str] = None
    follow_up_question: Optional[str] = None
    hints: List[str] = None
    difficulty: str = "appropriate"
    tone: str = "encouraging"


class ActiveTeachingEngine:
    """
    Generates real-time teaching feedback during play.
    Uses Socratic questioning to guide student thinking.
    """
    
    # Rating bands for tone calibration
    RATING_BANDS = {
        "beginner": (0, 1000),
        "intermediate": (1000, 1400),
        "club": (1400, 1800),
        "advanced": (1800, 2200)
    }
    
    # Tone templates by band
    TONE_BY_BAND = {
        "beginner": {
            "warm": True,
            "simple": True,
            "encouraging": True,
            "use_emojis": False,
            "complexity": "basic"
        },
        "intermediate": {
            "warm": True,
            "simple": True,
            "encouraging": True,
            "use_emojis": False,
            "complexity": "moderate"
        },
        "club": {
            "warm": True,
            "simple": False,
            "encouraging": True,
            "use_emojis": False,
            "complexity": "detailed"
        },
        "advanced": {
            "warm": False,
            "simple": False,
            "encouraging": False,
            "use_emojis": False,
            "complexity": "advanced"
        }
    }
    
    def __init__(self):
        """Initialize the teaching engine."""
        pass
    
    def get_student_band(self, rating: int) -> str:
        """Get rating band for a student."""
        for band, (low, high) in self.RATING_BANDS.items():
            if low <= rating < high:
                return band
        return "intermediate"
    
    def generate_feedback(
        self,
        board: chess.Board,
        last_move: Optional[chess.Move] = None,
        student_rating: int = 1200,
        phase: TeachingPhase = TeachingPhase.BEFORE_STUDENT_MOVE,
        student_color: chess.Color = chess.WHITE,
        move_context: Dict = None
    ) -> TeachingFeedback:
        """
        Generate appropriate teaching feedback for the current moment.
        
        Args:
            board: Current position (AFTER the last move if any)
            last_move: The move that was just played (if any)
            student_rating: Student's rating for calibration
            phase: Which phase of the move cycle we're in
            student_color: Which color the student is playing
            move_context: Additional context about the move/position
            
        Returns:
            TeachingFeedback with message and metadata
        """
        band = self.get_student_band(student_rating)
        tone = self.TONE_BY_BAND.get(band, self.TONE_BY_BAND["intermediate"])
        
        if move_context is None:
            move_context = {}
        
        # Generate feedback based on phase
        if phase == TeachingPhase.GAME_START:
            return self._generate_game_start_feedback(board, student_color, tone)
        
        elif phase == TeachingPhase.BEFORE_COACH_MOVE:
            return self._generate_before_coach_move_feedback(board, tone, move_context)
        
        elif phase == TeachingPhase.AFTER_COACH_MOVE:
            return self._generate_after_coach_move_feedback(
                board, last_move, tone, move_context
            )
        
        elif phase == TeachingPhase.BEFORE_STUDENT_MOVE:
            return self._generate_before_student_move_feedback(board, tone, move_context)
        
        elif phase == TeachingPhase.AFTER_STUDENT_MOVE:
            return self._generate_after_student_move_feedback(
                board, last_move, tone, move_context
            )
        
        elif phase == TeachingPhase.GAME_END:
            return self._generate_game_end_feedback(board, student_color, tone)
        
        # Default
        return TeachingFeedback(
            message="Your move!",
            feedback_type=FeedbackType.ENCOURAGEMENT
        )
    
    def _generate_game_start_feedback(
        self,
        board: chess.Board,
        student_color: chess.Color,
        tone: Dict
    ) -> TeachingFeedback:
        """Generate feedback at game start."""
        
        color_name = "White" if student_color == chess.WHITE else "Black"
        
        messages = [
            f"Welcome! You're playing {color_name}. Let's learn together.",
            f"Good to have you! As {color_name}, what's your opening plan?",
            f"Let's begin! You have {color_name}. Remember: develop pieces, control the center, castle early.",
            f"Ready to play? You're {color_name}. I'll help you think through each move."
        ]
        
        if tone["simple"]:
            messages = [
                f"Let's start! You are {color_name}. Have fun and learn!",
                f"You play {color_name}. Remember to bring your pieces out!"
            ]
        
        return TeachingFeedback(
            message=random.choice(messages),
            feedback_type=FeedbackType.ENCOURAGEMENT,
            concept="Opening principles",
            follow_up_question="What are your first few move ideas?",
            hints=["Control the center", "Develop knights before bishops", "Castle for king safety"],
            tone="warm"
        )
    
    def _generate_before_coach_move_feedback(
        self,
        board: chess.Board,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Generate feedback before the coach plays."""
        
        # Analyze the position to give relevant hints
        questions = [
            "What do you think I'm planning?",
            "Can you guess my next move?",
            "What would you play in my position?",
            "Look at the board - where am I strong? Where are you vulnerable?"
        ]
        
        if tone["simple"]:
            questions = [
                "What do you think I'll play?",
                "Look at my pieces. What might I do?"
            ]
        
        # Check for specific position features
        position_hints = self._analyze_position_for_teaching(board)
        
        message = random.choice(questions)
        hints = []
        
        if position_hints.get("has_tactics"):
            hints.append("There might be a tactical idea here...")
        if position_hints.get("has_weakness"):
            hints.append("One side has a weakness to exploit")
        if position_hints.get("development_advantage"):
            hints.append("Development matters - count the pieces in play")
        
        return TeachingFeedback(
            message=message,
            feedback_type=FeedbackType.QUESTION,
            concept="Anticipating opponent's moves",
            follow_up_question="Try to predict before I play",
            hints=hints if hints else ["Think about what I want to achieve"],
            tone="challenging"
        )
    
    def _generate_after_coach_move_feedback(
        self,
        board: chess.Board,
        move: chess.Move,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Generate feedback after the coach plays."""
        
        if move is None:
            return TeachingFeedback(
                message="Your turn to move!",
                feedback_type=FeedbackType.ENCOURAGEMENT
            )
        
        # Get move details from context (from TeachingMoveSelector)
        teaching_goal = context.get("teaching_goal", "natural_play")
        why_instructive = context.get("why_instructive", "This is a reasonable move")
        concept = context.get("concept_taught", "")
        challenge = context.get("student_challenge", "What would you play now?")
        
        # Build the teaching message
        move_san = context.get("move_san", board.san(move) if move in board.legal_moves else str(move))
        
        # Get previous position to generate proper SAN
        board_before = board.copy()
        board_before.pop()  # Go back one move
        try:
            move_san = board_before.san(move)
        except ValueError:
            move_san = str(move)
        
        messages = {
            "tactics": f"I played {move_san}. This creates some tactical pressure. {challenge}",
            "piece_activity": f"I played {move_san}. Notice how this improves my piece. {challenge}",
            "development": f"I played {move_san}. Bringing another piece into the game. {challenge}",
            "pawn_structure": f"I played {move_san}. This shapes the pawn structure. {challenge}",
            "king_safety": f"I played {move_san}. Safety first! {challenge}",
            "endgame_technique": f"I played {move_san}. In endgames, technique is key. {challenge}",
            "prophylaxis": f"I played {move_san}. This prevents something you might want to do. Can you see what?",
            "attack": f"I played {move_san}. The pressure is building. How will you defend?",
            "natural_play": f"I played {move_san}. {why_instructive}. {challenge}"
        }
        
        message = messages.get(teaching_goal, messages["natural_play"])
        
        if tone["simple"]:
            message = f"I played {move_san}. {challenge}"
        
        return TeachingFeedback(
            message=message,
            feedback_type=FeedbackType.EXPLANATION,
            concept=concept,
            follow_up_question=challenge,
            hints=[why_instructive] if why_instructive else [],
            tone="teaching"
        )
    
    def _generate_before_student_move_feedback(
        self,
        board: chess.Board,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Generate guidance before student moves."""
        
        # Analyze position
        position = self._analyze_position_for_teaching(board)
        
        # Socratic questions based on position
        if position.get("in_check"):
            return TeachingFeedback(
                message="You're in check! How can you get out of it? Think of all the options: block, capture, or move the king.",
                feedback_type=FeedbackType.HINT,
                concept="Getting out of check",
                hints=["Block the check", "Capture the attacker", "Move the king"]
            )
        
        if position.get("has_hanging_piece"):
            return TeachingFeedback(
                message="Take a moment to check: are all your pieces safe?",
                feedback_type=FeedbackType.HINT,
                concept="Piece safety",
                hints=["Look at each of your pieces", "Is anything undefended?"]
            )
        
        # General guidance based on game phase
        game_phase = context.get("game_phase", "middlegame")
        
        phase_questions = {
            "opening": [
                "Which piece should you develop next?",
                "Is your king safe? Have you castled?",
                "Are you fighting for the center?"
            ],
            "early_middlegame": [
                "What's your plan for the next few moves?",
                "Which of your pieces is your worst piece?",
                "What is my last move threatening?"
            ],
            "middlegame": [
                "Look for tactics! Are there any captures or checks?",
                "What's the weak point in my position?",
                "How can you improve your pieces?"
            ],
            "late_middlegame": [
                "Are we heading to an endgame? Think about pawn structure.",
                "Should you trade pieces or keep them on?",
                "Where should your king go if pieces get traded?"
            ],
            "endgame": [
                "Activate your king! It's a fighting piece now.",
                "Do you have any passed pawns to push?",
                "Calculate carefully - every move counts."
            ]
        }
        
        questions = phase_questions.get(game_phase, phase_questions["middlegame"])
        
        return TeachingFeedback(
            message=random.choice(questions),
            feedback_type=FeedbackType.QUESTION,
            concept=f"{game_phase} thinking",
            follow_up_question="Take your time and think it through",
            hints=["Look at the whole board", "What did my last move do?"],
            tone="encouraging"
        )
    
    def _generate_after_student_move_feedback(
        self,
        board: chess.Board,
        move: chess.Move,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Generate feedback after student moves."""
        
        if move is None:
            return TeachingFeedback(
                message="Let's see what you've played!",
                feedback_type=FeedbackType.ENCOURAGEMENT
            )
        
        # Get evaluation context
        was_best_move = context.get("was_best_move", False)
        was_blunder = context.get("was_blunder", False)
        was_good = context.get("was_good", False)
        
        # Get move SAN from context or calculate
        move_san = context.get("move_san", str(move))
        
        # Generate appropriate response
        if was_blunder:
            return self._generate_gentle_correction(board, move, move_san, tone, context)
        
        elif was_best_move:
            return self._generate_celebration(move_san, tone)
        
        elif was_good:
            return self._generate_encouragement(move_san, tone)
        
        else:
            return self._generate_neutral_response(move_san, tone, context)
    
    def _generate_gentle_correction(
        self,
        board: chess.Board,
        move: chess.Move,
        move_san: str,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Gently point out a mistake."""
        
        mistake_type = context.get("mistake_type", "tactical")
        better_move = context.get("better_move", "")
        
        messages = {
            "tactical": [
                f"Hmm, {move_san} might have a problem. Did you check if all your pieces are safe?",
                "That's an interesting choice. But wait - is there a tactical issue here?",
                f"Let me ask: before playing {move_san}, did you check what I can do now?"
            ],
            "positional": [
                f"{move_san} is playable, but there might be a better square for that piece.",
                f"Think about this: does {move_san} improve your position or make it harder?",
                "That's one option. But ask yourself: is this piece now doing more or less?"
            ],
            "strategic": [
                f"Interesting. {move_san} changes the nature of the game. Is that what you wanted?",
                f"That's a committal choice. What was your plan behind {move_san}?",
                f"{move_san} is a decision. Let's think about the consequences together."
            ]
        }
        
        hints = []
        if better_move:
            hints.append("There might have been something better...")
        hints.append("Remember to always check for tactics before moving")
        
        message_list = messages.get(mistake_type, messages["tactical"])
        
        if tone["simple"]:
            message_list = [
                "That move might cause problems. Did you see what I can do now?",
                "Careful! Check if your pieces are all safe."
            ]
        
        return TeachingFeedback(
            message=random.choice(message_list),
            feedback_type=FeedbackType.GENTLE_CORRECTION,
            concept="Checking your moves",
            follow_up_question="What do you think I'll play now?",
            hints=hints,
            tone="supportive"
        )
    
    def _generate_celebration(self, move_san: str, tone: Dict) -> TeachingFeedback:
        """Celebrate a great move."""
        
        messages = [
            f"Excellent! {move_san} is the best move! You saw it!",
            f"Well done! {move_san} is exactly right. Strong play!",
            f"Great move! {move_san} shows good understanding.",
            f"Yes! {move_san} is what I would have played. Impressive!"
        ]
        
        if tone["simple"]:
            messages = [
                f"Very good! {move_san} is great!",
                f"Nice! {move_san} is the best move!"
            ]
        
        return TeachingFeedback(
            message=random.choice(messages),
            feedback_type=FeedbackType.CELEBRATION,
            concept="Finding the best move",
            hints=["Keep up the good work!"],
            tone="excited"
        )
    
    def _generate_encouragement(self, move_san: str, tone: Dict) -> TeachingFeedback:
        """Encourage a good but not perfect move."""
        
        messages = [
            f"Good thinking! {move_san} is a solid choice.",
            f"{move_san} makes sense. You're on the right track.",
            f"That's reasonable. {move_san} is a practical move.",
            f"I like the idea behind {move_san}. Let's see how it goes."
        ]
        
        if tone["simple"]:
            messages = [
                f"Good! {move_san} is okay.",
                f"That works! {move_san} is a fine move."
            ]
        
        return TeachingFeedback(
            message=random.choice(messages),
            feedback_type=FeedbackType.ENCOURAGEMENT,
            concept="Making solid moves",
            hints=["Keep thinking practically"],
            tone="supportive"
        )
    
    def _generate_neutral_response(
        self,
        move_san: str,
        tone: Dict,
        context: Dict
    ) -> TeachingFeedback:
        """Neutral response for an okay move."""
        
        messages = [
            f"Okay, you played {move_san}. Let's continue.",
            f"{move_san} is one option. Let me respond.",
            f"I see {move_san}. Interesting choice.",
            f"Noted. {move_san}. My turn to think."
        ]
        
        return TeachingFeedback(
            message=random.choice(messages),
            feedback_type=FeedbackType.EXPLANATION,
            tone="neutral"
        )
    
    def _generate_game_end_feedback(
        self,
        board: chess.Board,
        student_color: chess.Color,
        tone: Dict
    ) -> TeachingFeedback:
        """Generate feedback at game end."""
        
        result = board.result()
        
        # Determine outcome for student
        student_won = (result == "1-0" and student_color == chess.WHITE) or \
                     (result == "0-1" and student_color == chess.BLACK)
        student_lost = (result == "1-0" and student_color == chess.BLACK) or \
                      (result == "0-1" and student_color == chess.WHITE)
        
        if student_won:
            messages = [
                "Congratulations! You won! Great game - what did you learn?",
                "Well played! You outplayed me. What was your best moment?",
                "Victory! You showed good understanding. Keep it up!",
                "You won! Let's review: what were the key turning points?"
            ]
            feedback_type = FeedbackType.CELEBRATION
            
        elif student_lost:
            messages = [
                "Game over. Don't worry - every loss is a lesson. What do you think went wrong?",
                "I won this time, but you played some good moves. Let's learn from this.",
                "This game didn't go your way, but that's how we improve. What would you do differently?",
                "A tough game. The key is to understand WHY it went wrong. Any ideas?"
            ]
            feedback_type = FeedbackType.GENTLE_CORRECTION
            
        else:  # Draw
            messages = [
                "It's a draw! Neither of us could break through. Good defensive play!",
                "Draw! Sometimes that's the correct result. What did you learn?",
                "We split the point. A hard-fought game! Any lessons?",
                "A draw - which is a fair result. Let's review the key moments."
            ]
            feedback_type = FeedbackType.ENCOURAGEMENT
        
        if tone["simple"]:
            if student_won:
                messages = ["You won! Great job!"]
            elif student_lost:
                messages = ["I won, but you played well. Let's see what we can learn!"]
            else:
                messages = ["It's a draw! Good game!"]
        
        return TeachingFeedback(
            message=random.choice(messages),
            feedback_type=feedback_type,
            concept="Game review",
            follow_up_question="What was the most important moment in this game?",
            hints=["Think about your critical decisions", "What would you change?"],
            tone="reflective"
        )
    
    def _analyze_position_for_teaching(self, board: chess.Board) -> Dict:
        """Analyze position to identify teaching opportunities."""
        
        analysis = {
            "in_check": board.is_check(),
            "has_hanging_piece": False,
            "has_tactics": False,
            "development_advantage": False,
            "has_weakness": False,
            "king_exposed": False
        }
        
        # Check for hanging pieces (simple heuristic)
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == board.turn:
                attackers = board.attackers(not board.turn, square)
                defenders = board.attackers(board.turn, square)
                if len(attackers) > len(defenders) and piece.piece_type != chess.PAWN:
                    analysis["has_hanging_piece"] = True
                    break
        
        # Check for tactical opportunities (captures, checks)
        for move in board.legal_moves:
            if board.is_capture(move):
                analysis["has_tactics"] = True
                break
            board.push(move)
            if board.is_check():
                analysis["has_tactics"] = True
            board.pop()
            if analysis["has_tactics"]:
                break
        
        # Simple development count
        white_developed = 0
        black_developed = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                rank = chess.square_rank(square)
                if piece.color == chess.WHITE and rank > 1:
                    white_developed += 1
                elif piece.color == chess.BLACK and rank < 6:
                    black_developed += 1
        
        if abs(white_developed - black_developed) >= 2:
            analysis["development_advantage"] = True
        
        return analysis


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def generate_teaching_feedback(
    fen: str,
    last_move_uci: Optional[str] = None,
    student_rating: int = 1200,
    phase: str = "before_student_move",
    student_color: str = "white",
    move_context: Dict = None
) -> Dict:
    """
    Generate teaching feedback for a position.
    
    Args:
        fen: Position in FEN
        last_move_uci: Last move played (UCI format)
        student_rating: Student's rating
        phase: Teaching phase
        student_color: Which color student plays
        move_context: Additional context
        
    Returns:
        Dict with teaching feedback
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}
    
    last_move = None
    if last_move_uci:
        try:
            last_move = chess.Move.from_uci(last_move_uci)
        except ValueError:
            pass
    
    try:
        teaching_phase = TeachingPhase(phase)
    except ValueError:
        teaching_phase = TeachingPhase.BEFORE_STUDENT_MOVE
    
    student_chess_color = chess.WHITE if student_color.lower() == "white" else chess.BLACK
    
    engine = ActiveTeachingEngine()
    feedback = engine.generate_feedback(
        board=board,
        last_move=last_move,
        student_rating=student_rating,
        phase=teaching_phase,
        student_color=student_chess_color,
        move_context=move_context or {}
    )
    
    return {
        "message": feedback.message,
        "feedback_type": feedback.feedback_type.value,
        "concept": feedback.concept,
        "follow_up_question": feedback.follow_up_question,
        "hints": feedback.hints or [],
        "tone": feedback.tone
    }
