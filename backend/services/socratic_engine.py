"""
Socratic Teaching Engine
========================

The SOUL of human-like coaching.

Core Philosophy:
- NEVER give the answer first
- ASK what they think
- GUIDE with progressive hints
- Let them DISCOVER
- Only REVEAL after engagement

This transforms:
  "You blundered. Best move was Qxd4." 
Into:
  "Interesting position. What were you trying to achieve with Nf3?"
  → (student responds)
  "Good thinking! But did you notice what Black can do now?"
  → (student guesses)
  "You're close! Look at the h2 square..."
  → (student discovers)
  "Exactly! You found it. This is called a Greek Gift sacrifice."

Usage:
    engine = SocraticEngine(user_rating=1200)
    
    # Start a dialogue about a position
    dialogue = engine.start_position_dialogue(fen, move_played, best_move)
    
    # Get the opening question (never the answer)
    question = dialogue.get_opening_question()
    
    # Process student's response
    next_step = dialogue.process_response(student_answer)
    
    # Get progressive hints if needed
    hint = dialogue.get_next_hint()
    
    # Finally reveal (only after engagement)
    reveal = dialogue.get_reveal()
"""

import chess
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import re


class DialogueState(str, Enum):
    """State of the Socratic dialogue."""
    OPENING_QUESTION = "opening_question"  # Ask what they think
    AWAITING_RESPONSE = "awaiting_response"  # Waiting for student
    HINT_PHASE = "hint_phase"  # Giving progressive hints
    GUIDED_DISCOVERY = "guided_discovery"  # They're close
    REVEAL = "reveal"  # Show the answer (only after effort)
    CELEBRATION = "celebration"  # They got it!
    COMPLETE = "complete"


class HintLevel(str, Enum):
    """Progressive hint levels."""
    SUBTLE = "subtle"  # Very vague direction
    DIRECTIONAL = "directional"  # Points to the area
    SPECIFIC = "specific"  # Points to the piece/square
    ALMOST_ANSWER = "almost_answer"  # One step from answer


@dataclass
class DialogueContext:
    """Tracks the state of a Socratic dialogue."""
    dialogue_id: str
    fen: str
    move_played: str  # What they played
    best_move: str  # What was better
    eval_loss: float  # How much they lost
    position_type: str  # "tactic", "strategic", "endgame"
    
    # State tracking
    state: DialogueState = DialogueState.OPENING_QUESTION
    hints_given: int = 0
    max_hints: int = 3
    student_responses: List[str] = field(default_factory=list)
    student_guesses: List[str] = field(default_factory=list)
    
    # What we want them to discover
    key_insight: str = ""
    discovery_elements: List[str] = field(default_factory=list)
    
    # Rating calibration
    student_rating: int = 1200


@dataclass
class SocraticResponse:
    """A response from the Socratic engine."""
    message: str
    state: DialogueState
    expects_response: bool
    response_type: str  # "text", "move", "choice"
    choices: List[str] = field(default_factory=list)
    hint_level: Optional[HintLevel] = None
    celebration: bool = False


class SocraticEngine:
    """
    Transforms chess teaching from "telling" to "guiding discovery".
    """
    
    # Opening questions - NEVER reveal the answer here
    OPENING_QUESTIONS = {
        "blunder": [
            "This move changed the game. What were you trying to achieve with {move}?",
            "Interesting choice with {move}. Walk me through your thinking.",
            "{move} - what was your plan here?",
            "Tell me about {move}. What did you see?",
        ],
        "mistake": [
            "Let's look at {move}. What were you considering?",
            "{move} is interesting. What made you choose this?",
            "What was your idea behind {move}?",
            "Walk me through {move} - what were you hoping for?",
        ],
        "missed_tactic": [
            "There was something special in this position. Did you feel it?",
            "This position had a hidden opportunity. What do you notice?",
            "Something powerful was possible here. Can you sense it?",
            "The position was screaming for something. What do you see?",
        ],
        "strategic": [
            "What do you think about the pawn structure here?",
            "How would you evaluate this position?",
            "What's the most important factor in this position?",
            "Where should the pieces be heading?",
        ],
        "endgame": [
            "What's the key to this endgame?",
            "How would you approach this ending?",
            "What principle applies here?",
            "What's the winning/drawing idea?",
        ]
    }
    
    # Progressive hints - from subtle to specific
    HINT_TEMPLATES = {
        HintLevel.SUBTLE: [
            "Hmm, think about piece activity...",
            "Consider the balance of forces...",
            "What pieces aren't doing much right now?",
            "Something's not quite safe...",
            "There might be a forcing sequence...",
        ],
        HintLevel.DIRECTIONAL: [
            "Look at the {area} of the board.",
            "Pay attention to the {piece} positions.",
            "Something's happening on the {file_or_rank}.",
            "The {color} king seems relevant here.",
            "There's tension around {square_area}.",
        ],
        HintLevel.SPECIFIC: [
            "What about the {square} square?",
            "Notice what happens if the {piece} moves.",
            "Can you see a check or capture involving {piece}?",
            "The {square} square is key here.",
            "Think about {piece} to {square}...",
        ],
        HintLevel.ALMOST_ANSWER: [
            "You're so close! What if {piece} went to {square}?",
            "Almost there! The key is {piece} attacking {target}.",
            "One more step - after {piece} moves, what happens to {target}?",
            "Think about {move_hint}...",
        ]
    }
    
    # Celebration messages - when they discover it
    CELEBRATION_MESSAGES = [
        "Yes! You found it! That's exactly right.",
        "Brilliant! You discovered it yourself.",
        "Exactly! You've got great chess intuition.",
        "Perfect! That's the move. You saw it!",
        "You got it! This is how strong players think.",
        "Wonderful! You worked it out yourself.",
    ]
    
    # Reveal messages - gentle, not condescending
    REVEAL_MESSAGES = [
        "Let me show you - {explanation}",
        "Here's the idea: {explanation}",
        "The key was {explanation}",
        "What makes this special: {explanation}",
    ]
    
    def __init__(self, user_rating: int = 1200):
        """Initialize with user's rating for calibration."""
        self.user_rating = user_rating
        self.dialogues: Dict[str, DialogueContext] = {}
    
    def start_position_dialogue(
        self,
        fen: str,
        move_played: str,
        best_move: str,
        eval_loss: float = 0,
        position_type: str = "blunder"
    ) -> DialogueContext:
        """
        Start a Socratic dialogue about a position.
        
        Args:
            fen: The position before the move
            move_played: What the student played
            best_move: What was objectively better
            eval_loss: How much evaluation was lost (centipawns)
            position_type: Type of teaching moment
            
        Returns:
            DialogueContext for tracking the conversation
        """
        import uuid
        
        dialogue_id = str(uuid.uuid4())[:8]
        
        # Determine max hints based on rating
        max_hints = 4 if self.user_rating < 1200 else (3 if self.user_rating < 1600 else 2)
        
        # Analyze what we want them to discover
        key_insight, elements = self._analyze_discovery_target(
            fen, move_played, best_move, position_type
        )
        
        context = DialogueContext(
            dialogue_id=dialogue_id,
            fen=fen,
            move_played=move_played,
            best_move=best_move,
            eval_loss=eval_loss,
            position_type=position_type,
            max_hints=max_hints,
            key_insight=key_insight,
            discovery_elements=elements,
            student_rating=self.user_rating
        )
        
        self.dialogues[dialogue_id] = context
        return context
    
    def get_opening_question(self, context: DialogueContext) -> SocraticResponse:
        """
        Get the opening question - NEVER the answer.
        
        This is where we ask them what they were thinking.
        """
        questions = self.OPENING_QUESTIONS.get(
            context.position_type, 
            self.OPENING_QUESTIONS["blunder"]
        )
        
        question = random.choice(questions).format(
            move=context.move_played
        )
        
        context.state = DialogueState.AWAITING_RESPONSE
        
        return SocraticResponse(
            message=question,
            state=context.state,
            expects_response=True,
            response_type="text"
        )
    
    def process_response(
        self, 
        context: DialogueContext, 
        response: str
    ) -> SocraticResponse:
        """
        Process the student's response and guide them.
        
        This is where the magic happens - we NEVER just give the answer.
        Instead, we acknowledge their thinking and guide further.
        """
        context.student_responses.append(response)
        
        # Check if they mentioned the key insight
        found_insight = self._check_for_discovery(context, response)
        
        if found_insight:
            return self._celebrate_discovery(context)
        
        # Check if they're getting close
        closeness = self._assess_closeness(context, response)
        
        if closeness > 0.7:
            return self._guide_final_step(context)
        elif closeness > 0.4:
            return self._encourage_and_hint(context, HintLevel.SPECIFIC)
        else:
            return self._acknowledge_and_redirect(context)
    
    def process_move_guess(
        self,
        context: DialogueContext,
        guessed_move: str
    ) -> SocraticResponse:
        """Process when they guess a specific move."""
        context.student_guesses.append(guessed_move)
        
        # Check if they got it!
        if self._normalize_move(guessed_move) == self._normalize_move(context.best_move):
            return self._celebrate_discovery(context)
        
        # They guessed wrong - guide them
        return self._respond_to_wrong_guess(context, guessed_move)
    
    def get_next_hint(self, context: DialogueContext) -> SocraticResponse:
        """Get the next progressive hint."""
        context.hints_given += 1
        
        # Determine hint level based on how many hints given
        if context.hints_given == 1:
            level = HintLevel.SUBTLE
        elif context.hints_given == 2:
            level = HintLevel.DIRECTIONAL
        elif context.hints_given == 3:
            level = HintLevel.SPECIFIC
        else:
            level = HintLevel.ALMOST_ANSWER
        
        hint = self._generate_hint(context, level)
        
        # If we've given max hints, prepare for reveal
        if context.hints_given >= context.max_hints:
            context.state = DialogueState.REVEAL
        else:
            context.state = DialogueState.HINT_PHASE
        
        return SocraticResponse(
            message=hint,
            state=context.state,
            expects_response=True,
            response_type="text" if level != HintLevel.ALMOST_ANSWER else "move",
            hint_level=level
        )
    
    def get_reveal(self, context: DialogueContext) -> SocraticResponse:
        """
        Reveal the answer - but ONLY after they've tried.
        
        Even in reveal, we're teaching, not just showing.
        """
        context.state = DialogueState.COMPLETE
        
        # Build a teaching explanation, not just "answer was X"
        explanation = self._build_teaching_explanation(context)
        
        reveal_template = random.choice(self.REVEAL_MESSAGES)
        message = reveal_template.format(explanation=explanation)
        
        # Add encouragement
        if context.hints_given > 0:
            message += f"\n\nYou were working in the right direction. "
            if context.student_guesses:
                message += f"Your guess of {context.student_guesses[-1]} showed good thinking."
        
        return SocraticResponse(
            message=message,
            state=context.state,
            expects_response=False,
            response_type="none"
        )
    
    def _celebrate_discovery(self, context: DialogueContext) -> SocraticResponse:
        """They found it! Celebrate genuinely."""
        context.state = DialogueState.CELEBRATION
        
        celebration = random.choice(self.CELEBRATION_MESSAGES)
        
        # Add context to the celebration
        if context.hints_given == 0:
            celebration += " And you found it without any hints!"
        elif context.hints_given == 1:
            celebration += " You only needed one small nudge."
        
        # Add the teaching moment - reinforce what they learned
        celebration += f"\n\n{context.key_insight}"
        
        return SocraticResponse(
            message=celebration,
            state=context.state,
            expects_response=False,
            response_type="none",
            celebration=True
        )
    
    def _acknowledge_and_redirect(self, context: DialogueContext) -> SocraticResponse:
        """
        Acknowledge their thinking (validate) but redirect.
        
        NEVER say "wrong" - always find something positive first.
        """
        acknowledgments = [
            "I see what you were thinking - that's a reasonable idea.",
            "That's an interesting perspective.",
            "I understand your logic there.",
            "Good that you were thinking about that.",
            "That's one way to look at it.",
        ]
        
        redirects = [
            "But let me ask you this - what could go wrong after {move}?",
            "Consider this though - what's Black's best response?",
            "Here's something to think about - is everything safe?",
            "Let's look deeper - what happens on the next move?",
            "But wait - do you see any danger?",
        ]
        
        ack = random.choice(acknowledgments)
        redirect = random.choice(redirects).format(move=context.move_played)
        
        context.state = DialogueState.HINT_PHASE
        
        return SocraticResponse(
            message=f"{ack} {redirect}",
            state=context.state,
            expects_response=True,
            response_type="text"
        )
    
    def _encourage_and_hint(
        self, 
        context: DialogueContext, 
        level: HintLevel
    ) -> SocraticResponse:
        """They're on the right track - encourage and give targeted hint."""
        encouragements = [
            "You're thinking in the right direction!",
            "Good instinct!",
            "You're onto something!",
            "That's close!",
            "You're warm!",
        ]
        
        hint = self._generate_hint(context, level)
        context.hints_given += 1
        
        message = f"{random.choice(encouragements)} {hint}"
        
        context.state = DialogueState.GUIDED_DISCOVERY
        
        return SocraticResponse(
            message=message,
            state=context.state,
            expects_response=True,
            response_type="text",
            hint_level=level
        )
    
    def _guide_final_step(self, context: DialogueContext) -> SocraticResponse:
        """They're very close - one more nudge."""
        context.state = DialogueState.GUIDED_DISCOVERY
        
        # Give the most specific hint
        final_hints = [
            f"You're so close! What if you played {context.best_move[:2]}...?",
            f"Almost there! Think about moving to {context.best_move[-2:]}.",
            f"One more step - what's the most forcing move here?",
            f"You've got this! What's the best piece to move?",
        ]
        
        return SocraticResponse(
            message=random.choice(final_hints),
            state=context.state,
            expects_response=True,
            response_type="move"
        )
    
    def _respond_to_wrong_guess(
        self, 
        context: DialogueContext, 
        guess: str
    ) -> SocraticResponse:
        """Respond to a wrong move guess - kindly redirect."""
        responses = [
            f"{guess} is an interesting idea, but there's something even stronger.",
            f"Good thinking with {guess}! But can you find something more forcing?",
            f"{guess} is playable, but there's a move that's really special here.",
            f"I like that you considered {guess}. Look for something with more impact.",
        ]
        
        context.state = DialogueState.HINT_PHASE
        
        return SocraticResponse(
            message=random.choice(responses),
            state=context.state,
            expects_response=True,
            response_type="move"
        )
    
    def _generate_hint(self, context: DialogueContext, level: HintLevel) -> str:
        """Generate a hint at the specified level."""
        templates = self.HINT_TEMPLATES.get(level, self.HINT_TEMPLATES[HintLevel.SUBTLE])
        
        # Parse the best move to extract hint elements
        best_move = context.best_move
        board = chess.Board(context.fen)
        
        try:
            move = board.parse_san(best_move)
            to_square = chess.square_name(move.to_square)
            from_square = chess.square_name(move.from_square)
            piece = board.piece_at(move.from_square)
            piece_name = self._piece_name(piece) if piece else "piece"
            
            # Get area descriptions
            to_file = to_square[0]
            to_rank = to_square[1]
            area = "kingside" if to_file in "fgh" else ("queenside" if to_file in "abc" else "center")
            
        except:
            to_square = "a key square"
            piece_name = "a piece"
            area = "an important area"
            to_file = ""
            to_rank = ""
        
        template = random.choice(templates)
        
        # Fill in template
        hint = template.format(
            area=area,
            piece=piece_name,
            square=to_square,
            file_or_rank=f"{to_file}-file" if to_file else "center",
            color="enemy" if board.turn else "your",
            square_area=area,
            target="the opponent's position",
            move_hint=best_move[:2] + "..."
        )
        
        return hint
    
    def _analyze_discovery_target(
        self,
        fen: str,
        move_played: str,
        best_move: str,
        position_type: str
    ) -> Tuple[str, List[str]]:
        """Analyze what we want them to discover."""
        board = chess.Board(fen)
        
        try:
            best = board.parse_san(best_move)
            
            # Check if it's a capture
            is_capture = board.is_capture(best)
            
            # Check if it gives check
            board.push(best)
            gives_check = board.is_check()
            board.pop()
            
            # Build insight
            elements = []
            if gives_check:
                elements.append("check")
            if is_capture:
                elements.append("capture")
            
            # Determine key insight
            if gives_check and is_capture:
                key_insight = f"{best_move} wins material with a forcing check."
            elif gives_check:
                key_insight = f"{best_move} gives a powerful check that improves your position."
            elif is_capture:
                key_insight = f"{best_move} wins material."
            else:
                key_insight = f"{best_move} is the strongest move here, improving your position significantly."
            
            return key_insight, elements
            
        except:
            return f"{best_move} was the best move here.", []
    
    def _check_for_discovery(self, context: DialogueContext, response: str) -> bool:
        """Check if the student has discovered the key insight."""
        response_lower = response.lower()
        best_move_lower = context.best_move.lower()
        
        # Check if they mentioned the move
        if best_move_lower in response_lower:
            return True
        
        # Check for key elements
        for element in context.discovery_elements:
            if element.lower() in response_lower:
                return True
        
        return False
    
    def _assess_closeness(self, context: DialogueContext, response: str) -> float:
        """Assess how close they are to the discovery (0.0 - 1.0)."""
        response_lower = response.lower()
        closeness = 0.0
        
        # Check for tactical keywords
        tactical_words = ["check", "capture", "take", "win", "attack", "threat", "fork", "pin", "skewer"]
        for word in tactical_words:
            if word in response_lower:
                closeness += 0.15
        
        # Check for piece mentions
        pieces = ["queen", "rook", "bishop", "knight", "pawn", "king"]
        for piece in pieces:
            if piece in response_lower:
                closeness += 0.1
        
        # Check for square mentions
        squares = [f"{f}{r}" for f in "abcdefgh" for r in "12345678"]
        for square in squares:
            if square in response_lower:
                closeness += 0.1
        
        return min(closeness, 1.0)
    
    def _build_teaching_explanation(self, context: DialogueContext) -> str:
        """Build a teaching explanation for the reveal."""
        board = chess.Board(context.fen)
        
        try:
            best = board.parse_san(context.best_move)
            played = board.parse_san(context.move_played)
            
            # Build explanation
            explanation = f"{context.best_move}"
            
            # Add what it does
            if board.is_capture(best):
                captured = board.piece_at(best.to_square)
                if captured:
                    explanation += f" wins the {self._piece_name(captured)}"
            
            board.push(best)
            if board.is_check():
                explanation += " with check"
            board.pop()
            
            # Explain why their move was weaker
            explanation += f". Your move {context.move_played}"
            
            if context.eval_loss > 100:
                explanation += f" lost significant advantage"
            elif context.eval_loss > 50:
                explanation += f" gave away some of your edge"
            else:
                explanation += f" was okay but missed the best opportunity"
            
            return explanation
            
        except:
            return f"{context.best_move} was stronger than {context.move_played}"
    
    def _normalize_move(self, move: str) -> str:
        """Normalize move for comparison."""
        return move.lower().replace("+", "").replace("#", "").replace("x", "")
    
    def _piece_name(self, piece: chess.Piece) -> str:
        """Get piece name."""
        names = {
            chess.KING: "King",
            chess.QUEEN: "Queen",
            chess.ROOK: "Rook",
            chess.BISHOP: "Bishop",
            chess.KNIGHT: "Knight",
            chess.PAWN: "pawn"
        }
        return names.get(piece.piece_type, "piece")


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_socratic_dialogue(
    fen: str,
    move_played: str,
    best_move: str,
    eval_loss: float = 0,
    position_type: str = "blunder",
    user_rating: int = 1200
) -> Tuple[DialogueContext, SocraticResponse]:
    """
    Create a new Socratic dialogue and get the opening question.
    
    Returns:
        Tuple of (context, opening_question)
    """
    engine = SocraticEngine(user_rating)
    context = engine.start_position_dialogue(
        fen, move_played, best_move, eval_loss, position_type
    )
    question = engine.get_opening_question(context)
    
    return context, question


def continue_dialogue(
    context: DialogueContext,
    response: str,
    user_rating: int = 1200
) -> SocraticResponse:
    """
    Continue a dialogue with the student's response.
    """
    engine = SocraticEngine(user_rating)
    engine.dialogues[context.dialogue_id] = context
    
    # Check if it looks like a move guess
    if len(response) <= 5 and any(c in response.lower() for c in "abcdefgh"):
        return engine.process_move_guess(context, response)
    else:
        return engine.process_response(context, response)
