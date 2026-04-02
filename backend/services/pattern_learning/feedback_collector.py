"""
Feedback Collector

Collects and structures user feedback on coach explanations.
This is the entry point for the self-learning system.

When a user flags a wrong explanation:
1. FeedbackCollector captures all context
2. Structures it for the PatternLearner
3. Stores it for processing
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class UserFeedback:
    """Structured user feedback on a coach explanation"""
    
    # Unique identifier
    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:12]}")
    
    # User info
    user_id: str = ""
    
    # Position context
    position_fen: str = ""
    move_played: str = ""
    move_san: str = ""
    
    # Engine data
    eval_before: float = 0.0
    eval_after: float = 0.0
    eval_drop: float = 0.0
    best_move: str = ""
    pv_after_played: List[str] = field(default_factory=list)
    
    # What the system said
    system_classification: str = ""  # e.g., "MISSED_TRAPPING_OPPORTUNITY"
    system_explanation: str = ""
    
    # What user says it actually was
    correct_classification: str = ""  # e.g., "WALKED_INTO_FORK"
    user_explanation: str = ""
    
    # Additional context
    game_id: str = ""
    move_number: int = 0
    user_color: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending -> processed -> applied
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserFeedback":
        """Create from dictionary"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FeedbackCollector:
    """
    Collects user feedback on coach explanations.
    
    Usage:
        collector = FeedbackCollector(db)
        
        feedback = collector.create_feedback(
            user_id="user123",
            position_fen="rnbqkb1r/...",
            move_played="Nf3",
            system_classification="MISSED_TRAP",
            system_explanation="You could have trapped the bishop",
            correct_classification="WALKED_INTO_FORK",
            user_explanation="The e5 pawn forks my pieces"
        )
        
        await collector.submit(feedback)
    """
    
    def __init__(self, db):
        """
        Initialize with database connection.
        
        Args:
            db: LearningDB instance or motor database
        """
        self.db = db
    
    def create_feedback(
        self,
        user_id: str,
        position_fen: str,
        move_played: str,
        system_classification: str,
        system_explanation: str,
        correct_classification: str,
        user_explanation: str = "",
        move_san: str = "",
        eval_before: float = 0.0,
        eval_after: float = 0.0,
        best_move: str = "",
        pv_after_played: List[str] = None,
        game_id: str = "",
        move_number: int = 0,
        user_color: str = "white"
    ) -> UserFeedback:
        """
        Create a structured feedback object.
        
        Args:
            user_id: ID of the user submitting feedback
            position_fen: FEN of the position BEFORE the move
            move_played: The move that was played (UCI format)
            system_classification: What the system classified it as
            system_explanation: The explanation the system gave
            correct_classification: What the user says it actually was
            user_explanation: User's explanation of what went wrong
            
        Returns:
            UserFeedback object ready for submission
        """
        return UserFeedback(
            user_id=user_id,
            position_fen=position_fen,
            move_played=move_played,
            move_san=move_san or move_played,
            eval_before=eval_before,
            eval_after=eval_after,
            eval_drop=eval_before - eval_after if eval_before and eval_after else 0,
            best_move=best_move,
            pv_after_played=pv_after_played or [],
            system_classification=system_classification,
            system_explanation=system_explanation,
            correct_classification=correct_classification,
            user_explanation=user_explanation,
            game_id=game_id,
            move_number=move_number,
            user_color=user_color
        )
    
    async def submit(self, feedback: UserFeedback) -> str:
        """
        Submit feedback for processing.
        
        Returns:
            feedback_id: ID of the stored feedback
        """
        feedback_dict = feedback.to_dict()
        
        # Store in database
        await self.db.store_feedback(feedback_dict)
        
        logger.info(
            f"Feedback submitted: {feedback.feedback_id} | "
            f"System said: {feedback.system_classification} | "
            f"User says: {feedback.correct_classification}"
        )
        
        return feedback.feedback_id
    
    async def get_pending_count(self) -> int:
        """Get count of pending feedback to process"""
        pending = await self.db.get_pending_feedback(limit=1000)
        return len(pending)
    
    async def get_feedback_for_position(self, position_fen: str) -> List[UserFeedback]:
        """Get all feedback for a specific position"""
        cursor = self.db.db.pattern_feedback.find(
            {"position_fen": position_fen},
            {"_id": 0}
        )
        results = await cursor.to_list(length=100)
        return [UserFeedback.from_dict(r) for r in results]
    
    def validate_feedback(self, feedback: UserFeedback) -> tuple[bool, str]:
        """
        Validate feedback before submission.
        
        Returns:
            (is_valid, error_message)
        """
        if not feedback.position_fen:
            return False, "Position FEN is required"
        
        if not feedback.move_played:
            return False, "Move played is required"
        
        if not feedback.system_classification:
            return False, "System classification is required"
        
        if not feedback.correct_classification:
            return False, "Correct classification is required"
        
        # Same classification = not useful feedback
        if feedback.system_classification == feedback.correct_classification:
            return False, "Correct classification must differ from system classification"
        
        return True, ""
    
    def extract_tactical_signature(self, feedback: UserFeedback) -> Dict:
        """
        Extract a tactical signature from feedback for pattern matching.
        
        This signature is used to:
        1. Find similar positions
        2. Match corrections across games
        3. Identify recurring patterns
        """
        signature = {
            "tactical_motif": feedback.correct_classification,
            "original_classification": feedback.system_classification,
            "eval_drop_range": self._get_eval_drop_range(feedback.eval_drop),
            "has_pv_data": len(feedback.pv_after_played) > 0,
            "pv_length": len(feedback.pv_after_played),
        }
        
        # Extract piece types from PV if available
        if feedback.pv_after_played:
            signature["pv_moves"] = feedback.pv_after_played[:3]  # First 3 moves
        
        return signature
    
    def _get_eval_drop_range(self, eval_drop: float) -> str:
        """Categorize eval drop into ranges for matching"""
        if eval_drop < 0.5:
            return "small"
        elif eval_drop < 1.5:
            return "medium"
        elif eval_drop < 3.0:
            return "large"
        else:
            return "critical"
