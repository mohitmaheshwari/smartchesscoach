"""
Coach Engine Data Models

Strict contracts for coaching output and events.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Any
from enum import Enum
from datetime import datetime


class TeachingLevel(Enum):
    """Level of coaching intervention"""
    OBSERVE = "observe"      # Light nudge, no numbers
    TEACH = "teach"          # Full validated explanation
    PAUSE = "pause"          # Major mistake - question + retry
    BLUNDER = "blunder"      # Full stop, critical error


class ReasonType(Enum):
    """Allowed concrete reasons (board-verifiable only)"""
    THREAT = "threat"
    PIN = "pin"
    OPEN_FILE = "open_file"
    HANGING_PIECE = "hanging_piece"
    KING_SAFETY = "king_safety"
    DEVELOPMENT_TEMPO = "development_tempo"
    PIECE_ACTIVITY = "piece_activity"
    PAWN_STRUCTURE = "pawn_structure"


@dataclass
class WisdomRule:
    """
    Structured wisdom rule - not prose.
    
    Each rule has:
    - Evidence predicates (Gate A)
    - Counterexample conditions
    - Templates for explanation and questions
    """
    rule_id: str                                    # e.g., "BLOCKED_BISHOP_BY_OWN_PAWN"
    title: str                                      # e.g., "Blocked Bishop"
    category: str                                   # e.g., "piece_activity", "development", "tactics"
    
    # Gate A: Evidence predicates - ALL must pass
    evidence_predicates: List[str]                  # Named predicates to check
    
    # When rule is overridden (SF says it's fine despite rule)
    counterexample_conditions: List[str]
    
    # Short explanation template (1 sentence, board-grounded)
    diagnosis_template: str                         # "Your {piece} on {square} is blocked by your pawn on {blocker}"
    
    # Memorable rule (short)
    memorable_rule: str                             # "Bishops need open diagonals"
    
    # Reason type this rule relates to
    reason_type: ReasonType
    
    # MCQ templates for pause/question mode
    followup_questions: List[Dict] = field(default_factory=list)
    
    # For future puzzle linking
    practice_tag: Optional[str] = None
    
    # Rating range where this rule is most relevant
    min_rating: int = 800
    max_rating: int = 2000


@dataclass
class CoachingOutput:
    """
    Strict output contract for every teaching message.
    
    Shape:
    1. 1 sentence diagnosis (board-grounded)
    2. Your move vs SF move (delta required)
    3. 1 concrete reason (from allowed set)
    4. 1 short rule (memorable)
    """
    # Core teaching content
    diagnosis: str                                  # 1 sentence, board-grounded
    your_move: str                                  # e.g., "Bd3"
    your_eval: float                                # e.g., 0.2
    sf_move: str                                    # e.g., "Nd5"
    sf_eval: float                                  # e.g., 0.8
    delta_cp: int                                   # e.g., -60 (required)
    reason: ReasonType                              # From allowed set
    reason_detail: str                              # Concrete explanation
    memorable_rule: str                             # Short, memorable
    
    # Metadata
    rule_id: Optional[str] = None                   # Which rule triggered this
    level: TeachingLevel = TeachingLevel.TEACH
    confidence: float = 1.0                         # 0-1, affects language
    
    # Board highlights
    highlights: Dict[str, str] = field(default_factory=dict)  # square -> color
    
    # For question mode
    question: Optional[Dict] = None                 # {text, options, correct_idx}
    
    def to_chat_message(self) -> str:
        """Generate chat message (short by default)"""
        soft = self.confidence < 0.8
        likely = "likely " if soft else ""
        
        msg = f"{self.diagnosis}\n\n"
        msg += f"You played: {self.your_move} ({self.your_eval:+.1f})\n"
        msg += f"Better: {self.sf_move} ({self.sf_eval:+.1f}) [{self.delta_cp:+d} cp]\n\n"
        msg += f"Reason: {self.reason_detail}\n\n"
        msg += f"Rule: {self.memorable_rule}"
        
        return msg
    
    def to_observation(self) -> str:
        """Light nudge version (no numbers)"""
        return f"{self.diagnosis}\n\nRule: {self.memorable_rule}"


@dataclass
class CoachEvent:
    """
    Event log for every coaching action.
    Required for Lab replay and telemetry.
    """
    # Position context
    move_number: int
    fen: str
    user_move: str
    best_move: str
    
    # Evaluation
    eval_before: float
    eval_after: float
    delta_cp: int
    
    # Rule application
    rule_id: Optional[str] = None
    level: TeachingLevel = TeachingLevel.OBSERVE
    
    # Question/retry flow
    question: Optional[Dict] = None                 # {text, options, correct_idx}
    user_answer: Optional[int] = None
    retry_move: Optional[str] = None
    retry_eval: Optional[float] = None
    
    # Message tracking
    coach_message_id: str = ""
    coach_message: str = ""
    
    # Board highlights
    highlights: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # User interaction telemetry
    why_clicked: bool = False
    retry_used: bool = False
    dismissed: bool = False
    time_spent_ms: int = 0


@dataclass
class UserRuleHistory:
    """Track rule usage per user for de-duplication"""
    user_id: str
    rule_id: str
    last_triggered: datetime
    trigger_count_last_10_games: int = 0
    total_triggers: int = 0


# Trigger thresholds
TRIGGER_THRESHOLDS = {
    "observe": -80,     # Light observation
    "teach": -120,      # Medium mistake - teach
    "pause": -250,      # Major mistake - question + retry  
    "blunder": -500,    # Critical - full stop (or mate)
}

# Maximum same rule triggers
MAX_RULE_PER_GAME = 1           # Same rule_id can trigger at most once as "teach" per game
MAX_RULE_MAIN_LESSON = 3        # Same rule_id cannot be main lesson more than N times in last 10 games
