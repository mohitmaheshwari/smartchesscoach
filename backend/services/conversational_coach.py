"""
Conversational Teaching Coach
=============================

Integrates all teaching systems into natural, conversational chat messages
that feel like talking to a human coach.

The coach should:
1. Explain moves in plain language (not computer speak)
2. Ask Socratic questions to make the student think
3. Connect concepts to what was taught before
4. Celebrate good decisions, gently correct mistakes
5. Use the student's name and maintain a warm tone

This service combines:
- Active Teaching Engine (Socratic feedback)
- Teaching Move Selector (instructive move selection)
- Structure & Plan Database (strategic guidance)
- Game Phase Calculator (phase-appropriate advice)
- Opening Teaching Database (opening-specific explanations)

Usage:
    coach = ConversationalCoach(user_id, user_rating)
    message = coach.get_message_for_coach_move(fen, coach_move, context)
    message = coach.get_message_for_student_move(fen, student_move, eval_data)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)


@dataclass
class GameContext:
    """Tracks context across the game for coherent coaching."""
    concepts_taught: List[str] = field(default_factory=list)
    mistakes_made: List[Dict] = field(default_factory=list)
    good_moves: List[Dict] = field(default_factory=list)
    current_phase: str = "opening"
    current_structure: str = ""
    opening_name: str = ""
    move_count: int = 0
    student_color: str = "white"
    session_start: str = ""
    last_teaching_goal: str = ""


class ConversationalCoach:
    """
    Generates natural, conversational coaching messages.
    Feels like talking to a human coach, not a computer.
    """
    
    # Conversation starters for different situations
    COACH_MOVE_INTROS = {
        "opening": [
            "In this opening, {move} is important because",
            "I'm playing {move} here.",
            "Watch this - {move}.",
            "Here's a key move: {move}.",
        ],
        "middlegame": [
            "I'm going to play {move}.",
            "Here's my plan: {move}.",
            "{move} - let me explain why.",
            "This is instructive: {move}.",
        ],
        "endgame": [
            "In this endgame, {move} is the technique.",
            "{move} - endgame precision.",
            "Watch this endgame idea: {move}.",
            "{move} demonstrates the key principle.",
        ]
    }
    
    STUDENT_MOVE_RESPONSES = {
        "excellent": [
            "Excellent! {move} is exactly right!",
            "Well done! {move} shows you understand.",
            "Great move! {move} is what I would play.",
            "Yes! {move} is the best move here.",
        ],
        "good": [
            "Good thinking with {move}.",
            "{move} is solid.",
            "That works! {move} keeps you in the game.",
            "{move} - sensible choice.",
        ],
        "okay": [
            "{move} is okay, but let me show you something.",
            "Hmm, {move} is playable.",
            "{move} isn't bad, but there was something better.",
            "I see {move}. Let's continue.",
        ],
        "mistake": [
            "Careful! {move} has a problem.",
            "{move}... do you see what happens now?",
            "That's a learning moment! {move} allows something.",
            "{move} - let's talk about this.",
        ],
        "blunder": [
            "Oops! {move} loses something important.",
            "{move} is a mistake. But that's how we learn!",
            "Ah, {move} overlooks something. Let me show you.",
            "{move} - this is exactly the kind of thing we need to fix.",
        ]
    }
    
    SOCRATIC_QUESTIONS = {
        "tactics": [
            "Can you see what I'm threatening?",
            "What happens if I play my next move?",
            "Look at the board - what's undefended?",
            "Do you see a tactical pattern here?",
        ],
        "strategy": [
            "What's my plan in this position?",
            "Which piece is my best piece right now?",
            "What should you be thinking about here?",
            "What's the weakness in your position?",
        ],
        "endgame": [
            "What's the key principle in this endgame?",
            "How should you use your king here?",
            "Do you know this endgame technique?",
            "What's the winning plan?",
        ]
    }
    
    def __init__(self, user_id: str, user_rating: int = 1200, user_name: str = ""):
        """Initialize the conversational coach."""
        self.user_id = user_id
        self.user_rating = user_rating
        self.user_name = user_name
        self.context = GameContext(session_start=datetime.utcnow().isoformat())
        self._determine_tone()
    
    def _determine_tone(self):
        """Set tone based on rating level."""
        if self.user_rating < 1000:
            self.tone = "encouraging"
            self.complexity = "simple"
        elif self.user_rating < 1400:
            self.tone = "supportive"
            self.complexity = "moderate"
        elif self.user_rating < 1800:
            self.tone = "challenging"
            self.complexity = "detailed"
        else:
            self.tone = "collegial"
            self.complexity = "advanced"
    
    def start_game(self, student_color: str) -> str:
        """Generate welcome message at game start."""
        self.context.student_color = student_color
        self.context.move_count = 0
        
        color_name = "White" if student_color == "white" else "Black"
        
        if self.complexity == "simple":
            messages = [
                f"Let's play! You're {color_name}. Have fun and learn!",
                f"Ready? You have {color_name}. Remember to develop your pieces!",
                f"Game on! As {color_name}, try to control the center.",
            ]
        else:
            messages = [
                f"Welcome! You're playing {color_name}. I'll help you think through each move.",
                f"Let's begin. As {color_name}, what's your opening plan?",
                f"You have {color_name}. Remember: develop, control the center, castle. Let's see how you do!",
            ]
        
        return random.choice(messages)
    
    def get_message_for_coach_move(
        self,
        fen: str,
        coach_move: str,
        teaching_context: Dict = None
    ) -> str:
        """
        Generate a conversational message explaining the coach's move.
        
        Args:
            fen: Position AFTER coach's move
            coach_move: The move in SAN (e.g., "Nf3")
            teaching_context: Context from TeachingMoveSelector
        """
        if teaching_context is None:
            teaching_context = {}
        
        self.context.move_count += 1
        
        # Get phase for appropriate intro
        phase = self._get_phase_category(teaching_context.get("game_phase", "middlegame"))
        
        # Build the message
        parts = []
        
        # 1. Move announcement with intro
        intros = self.COACH_MOVE_INTROS.get(phase, self.COACH_MOVE_INTROS["middlegame"])
        intro = random.choice(intros).format(move=coach_move)
        parts.append(intro)
        
        # 2. Teaching explanation (if available)
        teaching_goal = teaching_context.get("teaching_goal", "")
        why_instructive = teaching_context.get("why_instructive", "")
        concept = teaching_context.get("concept_taught", "")
        
        if why_instructive:
            parts.append(why_instructive)
            if concept and concept not in self.context.concepts_taught:
                self.context.concepts_taught.append(concept)
                self.context.last_teaching_goal = teaching_goal
        
        # 3. Add Socratic question
        challenge = teaching_context.get("student_challenge", "")
        if challenge:
            parts.append(challenge)
        else:
            # Generate a question based on context
            q_type = "tactics" if teaching_goal == "tactics" else ("endgame" if phase == "endgame" else "strategy")
            question = random.choice(self.SOCRATIC_QUESTIONS.get(q_type, self.SOCRATIC_QUESTIONS["strategy"]))
            parts.append(question)
        
        # Join and clean up
        message = " ".join(parts)
        return self._clean_message(message)
    
    def get_message_for_student_move(
        self,
        fen_before: str,
        fen_after: str,
        student_move: str,
        eval_data: Dict = None
    ) -> Optional[str]:
        """
        Generate feedback message for student's move.
        
        Args:
            fen_before: Position before student's move
            fen_after: Position after student's move
            student_move: The move in SAN
            eval_data: Evaluation data (was_best, eval_change, better_move, etc.)
        """
        if eval_data is None:
            eval_data = {}
        
        # Determine move quality
        was_best = eval_data.get("was_best", False)
        was_blunder = eval_data.get("was_blunder", False)
        eval_change = eval_data.get("eval_change", 0)
        better_move = eval_data.get("better_move", "")
        
        # Categorize the move
        if was_blunder or eval_change < -150:
            quality = "blunder"
        elif eval_change < -50:
            quality = "mistake"
        elif was_best:
            quality = "excellent"
        elif eval_change > -20:
            quality = "good"
        else:
            quality = "okay"
        
        # Track for end-of-game review
        if quality in ["blunder", "mistake"]:
            self.context.mistakes_made.append({
                "move": student_move,
                "better": better_move,
                "eval_change": eval_change,
                "fen": fen_before
            })
        elif quality == "excellent":
            self.context.good_moves.append({
                "move": student_move,
                "fen": fen_before
            })
        
        # Generate response
        responses = self.STUDENT_MOVE_RESPONSES.get(quality, self.STUDENT_MOVE_RESPONSES["okay"])
        base_response = random.choice(responses).format(move=student_move)
        
        # Add explanation for mistakes
        if quality in ["blunder", "mistake"] and better_move:
            if self.complexity == "simple":
                explanation = f"{better_move} was better here."
            else:
                explanation = f"Consider {better_move} instead - do you see why it's stronger?"
            return f"{base_response} {explanation}"
        
        return base_response
    
    def get_opening_teaching(self, fen: str, move: str, opening_name: str = "") -> Optional[str]:
        """Get opening-specific teaching message."""
        if opening_name:
            self.context.opening_name = opening_name
        
        # Will be enhanced with opening database
        if not opening_name:
            return None
        
        if self.complexity == "simple":
            return f"In the {opening_name}, {move} is a main move."
        else:
            return f"We're playing the {opening_name}. {move} is a key move in this opening."
    
    def get_structure_teaching(self, structure_name: str, structure_plans: Dict) -> Optional[str]:
        """Generate teaching message about pawn structure."""
        if not structure_name or structure_name == "Complex Structure":
            return None
        
        self.context.current_structure = structure_name
        
        plans = structure_plans.get("plans", [])
        if not plans:
            return None
        
        main_plan = plans[0]
        plan_name = main_plan.get("name", "")
        
        if self.complexity == "simple":
            return f"This is a {structure_name}. The main idea is {plan_name}."
        else:
            return f"We've reached a {structure_name} position. The typical plan here is {plan_name}. Keep this in mind as you play."
    
    def get_phase_transition_message(self, new_phase: str, phase_percent: int) -> Optional[str]:
        """Generate message when game phase changes."""
        old_phase = self.context.current_phase
        self.context.current_phase = new_phase
        
        # Only announce significant transitions
        if old_phase == new_phase:
            return None
        
        phase_messages = {
            "early_middlegame": "We're moving into the middlegame now. Development is mostly done - time to make plans!",
            "middlegame": "The middlegame is where the real battle happens. Look for tactics and strategic plans.",
            "late_middlegame": "We're heading towards an endgame. Start thinking about pawn structure and king activity.",
            "early_endgame": "This is turning into an endgame. Your king becomes a fighting piece now!",
            "endgame": "Endgame time! Precision is key. Every move matters.",
            "deep_endgame": "We're in a pure endgame. This is where technique wins games."
        }
        
        return phase_messages.get(new_phase)
    
    def get_endgame_teaching(self, endgame_type: str, endgame_concepts: List[str]) -> Optional[str]:
        """Generate endgame-specific teaching."""
        if not endgame_type:
            return None
        
        if self.complexity == "simple":
            return f"This is a {endgame_type}. Do you know the winning technique?"
        else:
            concepts = endgame_concepts[:2] if endgame_concepts else []
            if concepts:
                return f"This is a {endgame_type}. Key concepts: {', '.join(concepts)}. Let me show you how to play this."
            return f"This is a {endgame_type}. Let me demonstrate the correct technique."
    
    def get_game_end_summary(self, result: str) -> str:
        """
        Generate end-of-game teaching summary.
        
        This is the post-game lesson!
        """
        student_won = (
            (result == "1-0" and self.context.student_color == "white") or
            (result == "0-1" and self.context.student_color == "black")
        )
        is_draw = result == "1/2-1/2"
        
        parts = []
        
        # 1. Result acknowledgment
        if student_won:
            parts.append("Congratulations on the win!")
        elif is_draw:
            parts.append("A draw - well fought!")
        else:
            parts.append("I won this time, but let's learn from it.")
        
        # 2. Concepts taught
        if self.context.concepts_taught:
            unique_concepts = list(set(self.context.concepts_taught))[:3]
            parts.append(f"Today we covered: {', '.join(unique_concepts)}.")
        
        # 3. Highlight good moves
        if self.context.good_moves:
            good_count = len(self.context.good_moves)
            if good_count >= 3:
                parts.append(f"You made {good_count} excellent moves - great job!")
            elif good_count > 0:
                parts.append(f"Nice moves like {self.context.good_moves[0]['move']} showed good understanding.")
        
        # 4. Review mistakes
        if self.context.mistakes_made:
            mistake_count = len(self.context.mistakes_made)
            if mistake_count > 2:
                parts.append(f"We found {mistake_count} learning opportunities. Let's focus on checking for tactics before each move.")
            elif mistake_count > 0:
                parts.append(f"One area to work on: {self.context.mistakes_made[0]['move']} was a mistake. Remember to ask 'what can my opponent do?' before every move.")
        
        # 5. Structure/Opening mention
        if self.context.opening_name:
            parts.append(f"We played the {self.context.opening_name} - good to get experience in this opening.")
        
        if self.context.current_structure and self.context.current_structure != "Complex Structure":
            parts.append(f"The {self.context.current_structure} structure is important to understand.")
        
        # 6. Closing encouragement
        closing = [
            "Keep practicing!",
            "Every game makes you stronger.",
            "See you next time!",
            "Well played - let's do it again!",
        ]
        parts.append(random.choice(closing))
        
        return " ".join(parts)
    
    def _get_phase_category(self, phase: str) -> str:
        """Map detailed phase to category."""
        if phase in ["opening", "early_middlegame"]:
            return "opening"
        elif phase in ["endgame", "deep_endgame", "early_endgame"]:
            return "endgame"
        return "middlegame"
    
    def _clean_message(self, message: str) -> str:
        """Clean up message formatting."""
        # Remove double spaces
        while "  " in message:
            message = message.replace("  ", " ")
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]
        return message.strip()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_coach_for_session(
    user_id: str,
    user_rating: int = 1200,
    user_name: str = ""
) -> ConversationalCoach:
    """Create a new conversational coach for a game session."""
    return ConversationalCoach(user_id, user_rating, user_name)


def generate_coach_move_message(
    coach: ConversationalCoach,
    fen: str,
    coach_move: str,
    teaching_context: Dict = None
) -> str:
    """Generate message for coach's move."""
    return coach.get_message_for_coach_move(fen, coach_move, teaching_context)


def generate_student_feedback(
    coach: ConversationalCoach,
    fen_before: str,
    fen_after: str,
    student_move: str,
    eval_data: Dict = None
) -> Optional[str]:
    """Generate feedback for student's move."""
    return coach.get_message_for_student_move(fen_before, fen_after, student_move, eval_data)


def generate_game_summary(
    coach: ConversationalCoach,
    result: str
) -> str:
    """Generate end-of-game teaching summary."""
    return coach.get_game_end_summary(result)
