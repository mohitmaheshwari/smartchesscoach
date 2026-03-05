"""
Interactive Question System for Play with Coach

Handles:
- Generating questions for the user
- Understanding user responses (fuzzy matching)
- Tracking question state in session
- Providing feedback on answers
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import chess

from .opening_plans import OpeningPlan, get_opening_by_moves


class QuestionType(Enum):
    """Types of questions the coach can ask"""
    PLAN_CHECK = "plan_check"           # "What's my plan here?"
    MOVE_CHOICE = "move_choice"         # "What move would you play?"
    CONCEPT_CHECK = "concept_check"     # "Why is this move good?"
    THREAT_CHECK = "threat_check"       # "What am I threatening?"
    UNDERSTANDING = "understanding"      # "Do you understand?"


@dataclass
class CoachQuestion:
    """A question from the coach"""
    question_type: QuestionType
    text: str
    options: Optional[List[str]] = None  # For multiple choice
    correct_option_idx: Optional[int] = None  # Index of correct answer
    accepts_free_response: bool = True
    context: Dict = None  # Position context
    
    def to_dict(self) -> Dict:
        return {
            "type": self.question_type.value,
            "text": self.text,
            "options": self.options,
            "correct_idx": self.correct_option_idx,
            "free_response": self.accepts_free_response,
        }


# ==================== QUESTION GENERATORS ====================

def generate_opening_plan_question(opening: OpeningPlan, move_number: int) -> CoachQuestion:
    """Generate a question about the opening plan"""
    if move_number <= 4:
        return CoachQuestion(
            question_type=QuestionType.PLAN_CHECK,
            text=f"This is the {opening.name}. What do you think the main idea is?",
            options=[
                opening.main_ideas[0] if opening.main_ideas else "Control the center",
                "Attack the king immediately",
                "Trade all the pieces",
                "I'm not sure"
            ],
            correct_option_idx=0,
            accepts_free_response=True,
        )
    else:
        return CoachQuestion(
            question_type=QuestionType.UNDERSTANDING,
            text="Do you see what I'm planning with this move?",
            options=["Yes, I see it", "I think so", "Not really", "Please explain"],
            correct_option_idx=None,  # No wrong answer
            accepts_free_response=True,
        )


def generate_threat_question(board: chess.Board, last_move: str) -> Optional[CoachQuestion]:
    """Generate a question about threats in the position"""
    # Check if the last move creates obvious threats
    if board.is_check():
        return CoachQuestion(
            question_type=QuestionType.THREAT_CHECK,
            text="I just gave check. What must you do?",
            options=["Block the check", "Move my king", "Capture the piece", "I need to think"],
            correct_option_idx=None,
            accepts_free_response=True,
        )
    
    # Check for attacked pieces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color != board.turn:
            if board.is_attacked_by(board.turn, square):
                piece_name = chess.piece_name(piece.piece_type)
                return CoachQuestion(
                    question_type=QuestionType.THREAT_CHECK,
                    text=f"Notice anything about your {piece_name}?",
                    options=[
                        "It's under attack",
                        "It's well placed",
                        "Nothing special",
                        "I'm not sure"
                    ],
                    correct_option_idx=0,
                    accepts_free_response=True,
                )
    
    return None


def generate_move_praise_question(move_san: str, is_best: bool) -> CoachQuestion:
    """Generate a question when user plays a good move"""
    if is_best:
        return CoachQuestion(
            question_type=QuestionType.CONCEPT_CHECK,
            text=f"Good move with {move_san}! Why do you think this is strong?",
            options=[
                "It develops a piece",
                "It controls the center",
                "It creates a threat",
                "I just felt it was good"
            ],
            correct_option_idx=None,  # Accept any thinking
            accepts_free_response=True,
        )
    else:
        return CoachQuestion(
            question_type=QuestionType.UNDERSTANDING,
            text=f"Solid choice with {move_san}. What's your plan from here?",
            options=None,
            accepts_free_response=True,
        )


# ==================== RESPONSE UNDERSTANDING ====================

class ResponseUnderstanding:
    """
    Understand fuzzy user responses without hallucinating.
    Uses pattern matching, not LLM.
    """
    
    # Patterns for different intents
    PATTERNS = {
        "confused": [
            r"don't understand",
            r"not sure",
            r"confused",
            r"lost",
            r"help",
            r"what\s*(do|should)",
            r"explain",
            r"idk",
            r"i don't know",
            r"\?{2,}",  # Multiple question marks
        ],
        "affirmative": [
            r"^yes",
            r"^yeah",
            r"^yep",
            r"^ok",
            r"^okay",
            r"got it",
            r"understand",
            r"makes sense",
            r"i see",
            r"right",
            r"correct",
        ],
        "negative": [
            r"^no\b",
            r"^nope",
            r"^nah",
            r"not really",
            r"don't think so",
        ],
        "asking_plan": [
            r"what.*(plan|idea|goal|strategy)",
            r"why.*(move|play)",
            r"what.*(do|should).*(i|me)",
            r"suggest",
            r"hint",
            r"help me",
        ],
        "asking_about_move": [
            r"what about",
            r"how about",
            r"is .* good",
            r"should i.*(play|move)",
            r"can i",
        ],
        "thinking_out_loud": [
            r"i think",
            r"maybe",
            r"perhaps",
            r"probably",
            r"because",
            r"since",
            r"so that",
        ],
    }
    
    @classmethod
    def understand(cls, message: str) -> Tuple[str, float]:
        """
        Understand user's intent from their message.
        
        Returns:
            (intent, confidence)
        """
        msg = message.lower().strip()
        
        # Check each pattern category
        for intent, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, msg, re.IGNORECASE):
                    return (intent, 0.8)
        
        # If message is very short, likely an answer attempt
        if len(msg.split()) <= 3:
            return ("short_answer", 0.6)
        
        # Default: treat as thinking/explanation
        return ("thinking_out_loud", 0.5)
    
    @classmethod
    def extract_chess_concepts(cls, message: str) -> List[str]:
        """Extract chess concepts mentioned in the message"""
        msg = message.lower()
        concepts = []
        
        concept_keywords = {
            "center": ["center", "central", "d4", "d5", "e4", "e5"],
            "development": ["develop", "piece out", "get out", "bring out"],
            "castling": ["castle", "castling", "king safety", "safe king"],
            "attack": ["attack", "threat", "threatening", "pressure"],
            "defense": ["defend", "protect", "guard", "block"],
            "tactic": ["tactic", "fork", "pin", "skewer", "discovered"],
            "pawn_structure": ["pawn", "structure", "doubled", "isolated"],
            "piece_activity": ["active", "passive", "stuck", "trapped"],
        }
        
        for concept, keywords in concept_keywords.items():
            for kw in keywords:
                if kw in msg:
                    concepts.append(concept)
                    break
        
        return concepts


# ==================== RESPONSE GENERATORS ====================

def generate_response_to_answer(
    user_message: str,
    question: Optional[CoachQuestion],
    opening: Optional[OpeningPlan] = None,
    board: Optional[chess.Board] = None,
) -> str:
    """
    Generate a coach response to user's answer.
    No LLM - uses templates and pattern matching.
    """
    intent, confidence = ResponseUnderstanding.understand(user_message)
    concepts = ResponseUnderstanding.extract_chess_concepts(user_message)
    
    # Handle different intents
    if intent == "confused":
        if opening:
            return (
                f"No problem! In the {opening.name}, the main idea is: "
                f"{opening.main_ideas[0] if opening.main_ideas else 'control the center and develop pieces'}. "
                f"Take your time with your move."
            )
        else:
            return (
                "No worries! Focus on these basics:\n"
                "1. Develop your knights and bishops\n"
                "2. Control the center\n"
                "3. Castle to protect your king\n"
                "Your move when ready."
            )
    
    elif intent == "affirmative":
        if question and question.question_type == QuestionType.UNDERSTANDING:
            return "Good! Let's continue. Your move."
        elif concepts:
            return f"Yes, you're thinking about {concepts[0].replace('_', ' ')}. That's the right idea! Your move."
        else:
            return "Good! Keep that in mind. Your move."
    
    elif intent == "negative":
        if opening:
            return (
                f"Let me explain. In the {opening.name}, {opening.simple_explanation} "
                f"Does that make more sense?"
            )
        else:
            return "Let me help. What specifically are you unsure about?"
    
    elif intent == "asking_plan":
        if opening:
            ideas = "\n".join(f"• {idea}" for idea in opening.main_ideas[:3])
            return f"In this position, your main ideas are:\n{ideas}\nWhich one appeals to you?"
        else:
            return (
                "Good question! At this stage, focus on:\n"
                "• Developing pieces that haven't moved\n"
                "• Controlling the center squares\n"
                "• Getting your king to safety"
            )
    
    elif intent == "asking_about_move":
        return (
            "I can't tell you exactly what to play - that's for you to figure out! "
            "But think about: what piece hasn't moved yet? Is your king safe?"
        )
    
    elif intent == "thinking_out_loud":
        if concepts:
            concept_feedback = {
                "center": "Yes, the center is key in the opening!",
                "development": "Exactly - get your pieces into the game!",
                "castling": "Right, king safety is crucial.",
                "attack": "Good thinking, but make sure you're ready first.",
                "defense": "Good awareness of threats!",
            }
            for concept in concepts:
                if concept in concept_feedback:
                    return f"{concept_feedback[concept]} Your move when ready."
        
        return "Good thinking! Trust your instincts and make your move."
    
    else:
        # Default response
        return "I see. Take your time and make your move when ready."


def should_ask_question(
    move_number: int,
    is_opening: bool,
    eval_diff: float,
    last_question_move: int,
) -> bool:
    """
    Decide if coach should ask a question.
    
    Don't ask too often - space out questions.
    """
    # Don't ask on every move
    if move_number - last_question_move < 3:
        return False
    
    # More questions in opening
    if is_opening and move_number in [2, 4, 6, 8]:
        return True
    
    # Ask after significant position changes
    if abs(eval_diff) > 1.0:
        return True
    
    return False


# ==================== CONSEQUENCE DETECTION ====================

def detect_long_term_consequences(
    board: chess.Board,
    user_color: chess.Color,
    last_move: chess.Move,
) -> Optional[str]:
    """
    Detect if a move creates long-term positional consequences.
    Only detects what we can verify - no speculation.
    """
    from .piece_metrics import PieceMetricsAnalyzer
    
    consequences = []
    analyzer = PieceMetricsAnalyzer(board)
    
    # Check if it was a pawn move (permanent!)
    moved_piece = board.piece_at(last_move.to_square)
    if moved_piece and moved_piece.piece_type == chess.PAWN:
        # Check if this pawn blocks a bishop
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.BISHOP and piece.color == user_color:
                blocking_info = analyzer.get_bishop_blocking_info(sq)
                if blocking_info and blocking_info.get("blocked_by_own_pawn"):
                    consequences.append(
                        f"That pawn move restricts your bishop on {chess.square_name(sq)}. "
                        f"In closed positions, bishops behind pawns become less active."
                    )
                    break
    
    # Check if king moved (can't castle anymore)
    if moved_piece and moved_piece.piece_type == chess.KING:
        # Check if castling rights were lost
        if not board.has_castling_rights(user_color):
            if not (board.is_castled(user_color) if hasattr(board, 'is_castled') else False):
                consequences.append(
                    "Moving your king means you can't castle anymore. "
                    "Make sure your king is safe in the center!"
                )
    
    # Return first consequence (don't overwhelm)
    if consequences:
        return consequences[0]
    
    return None
