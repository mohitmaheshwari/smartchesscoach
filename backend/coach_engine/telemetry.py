"""
Coach Engine Telemetry

Logs user interactions for analysis and tuning.
Required from Day 1 to avoid arguing opinions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from enum import Enum


class InteractionType(Enum):
    """Types of user interactions with coach"""
    MESSAGE_SHOWN = "message_shown"
    WHY_CLICKED = "why_clicked"
    RETRY_USED = "retry_used"
    DISMISSED = "dismissed"
    QUESTION_ANSWERED = "question_answered"
    QUESTION_SKIPPED = "question_skipped"
    CONTINUE_CLICKED = "continue_clicked"


@dataclass
class TelemetryEvent:
    """Single telemetry event"""
    event_id: str
    user_id: str
    session_id: str
    game_id: str
    move_number: int
    
    interaction_type: InteractionType
    coach_message_id: str
    rule_id: Optional[str]
    
    # For questions
    question_text: Optional[str] = None
    user_answer: Optional[int] = None
    correct_answer: Optional[int] = None
    was_correct: Optional[bool] = None
    
    # Timing
    time_spent_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetryCollector:
    """
    Collects and stores telemetry events.
    
    Tracks:
    - How often users click "Why?"
    - How often they choose "Retry"
    - How often they dismiss messages
    - Question accuracy by type
    - Churn points (which intervention caused exit)
    """
    
    def __init__(self, user_id: str, session_id: str, game_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.game_id = game_id
        self.events: List[TelemetryEvent] = []
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        self._event_counter += 1
        return f"{self.session_id}_{self._event_counter}"
    
    def log_message_shown(
        self, 
        move_number: int, 
        coach_message_id: str,
        rule_id: Optional[str] = None
    ):
        """Log when a coaching message is shown"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.MESSAGE_SHOWN,
            coach_message_id=coach_message_id,
            rule_id=rule_id,
        ))
    
    def log_why_clicked(
        self,
        move_number: int,
        coach_message_id: str,
        rule_id: Optional[str] = None,
        time_spent_ms: int = 0
    ):
        """Log when user clicks 'Why?' for more explanation"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.WHY_CLICKED,
            coach_message_id=coach_message_id,
            rule_id=rule_id,
            time_spent_ms=time_spent_ms,
        ))
    
    def log_retry_used(
        self,
        move_number: int,
        coach_message_id: str,
        rule_id: Optional[str] = None,
    ):
        """Log when user chooses to retry a move"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.RETRY_USED,
            coach_message_id=coach_message_id,
            rule_id=rule_id,
        ))
    
    def log_dismissed(
        self,
        move_number: int,
        coach_message_id: str,
        rule_id: Optional[str] = None,
        time_spent_ms: int = 0
    ):
        """Log when user dismisses/ignores a message"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.DISMISSED,
            coach_message_id=coach_message_id,
            rule_id=rule_id,
            time_spent_ms=time_spent_ms,
        ))
    
    def log_question_answered(
        self,
        move_number: int,
        coach_message_id: str,
        rule_id: Optional[str],
        question_text: str,
        user_answer: int,
        correct_answer: int,
        time_spent_ms: int = 0
    ):
        """Log when user answers a coaching question"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.QUESTION_ANSWERED,
            coach_message_id=coach_message_id,
            rule_id=rule_id,
            question_text=question_text,
            user_answer=user_answer,
            correct_answer=correct_answer,
            was_correct=user_answer == correct_answer,
            time_spent_ms=time_spent_ms,
        ))
    
    def log_continue(
        self,
        move_number: int,
        coach_message_id: str,
        time_spent_ms: int = 0
    ):
        """Log when user clicks continue to proceed"""
        self.events.append(TelemetryEvent(
            event_id=self._generate_event_id(),
            user_id=self.user_id,
            session_id=self.session_id,
            game_id=self.game_id,
            move_number=move_number,
            interaction_type=InteractionType.CONTINUE_CLICKED,
            coach_message_id=coach_message_id,
            rule_id=None,
            time_spent_ms=time_spent_ms,
        ))
    
    def get_events(self) -> List[TelemetryEvent]:
        """Get all telemetry events"""
        return self.events
    
    def get_summary(self) -> Dict:
        """Get summary statistics for this session"""
        total_messages = sum(1 for e in self.events if e.interaction_type == InteractionType.MESSAGE_SHOWN)
        why_clicks = sum(1 for e in self.events if e.interaction_type == InteractionType.WHY_CLICKED)
        retries = sum(1 for e in self.events if e.interaction_type == InteractionType.RETRY_USED)
        dismissals = sum(1 for e in self.events if e.interaction_type == InteractionType.DISMISSED)
        
        questions = [e for e in self.events if e.interaction_type == InteractionType.QUESTION_ANSWERED]
        correct_answers = sum(1 for e in questions if e.was_correct)
        
        return {
            "total_messages": total_messages,
            "why_clicks": why_clicks,
            "why_click_rate": why_clicks / total_messages if total_messages > 0 else 0,
            "retries": retries,
            "retry_rate": retries / total_messages if total_messages > 0 else 0,
            "dismissals": dismissals,
            "dismissal_rate": dismissals / total_messages if total_messages > 0 else 0,
            "questions_answered": len(questions),
            "questions_correct": correct_answers,
            "question_accuracy": correct_answers / len(questions) if questions else 0,
            "avg_time_on_message_ms": sum(e.time_spent_ms for e in self.events) / len(self.events) if self.events else 0,
        }
    
    def get_rule_effectiveness(self) -> Dict[str, Dict]:
        """Get effectiveness metrics per rule"""
        rule_stats = {}
        
        for event in self.events:
            if event.rule_id:
                if event.rule_id not in rule_stats:
                    rule_stats[event.rule_id] = {
                        "shown": 0,
                        "why_clicked": 0,
                        "retried": 0,
                        "dismissed": 0,
                        "questions_correct": 0,
                        "questions_total": 0,
                    }
                
                stats = rule_stats[event.rule_id]
                
                if event.interaction_type == InteractionType.MESSAGE_SHOWN:
                    stats["shown"] += 1
                elif event.interaction_type == InteractionType.WHY_CLICKED:
                    stats["why_clicked"] += 1
                elif event.interaction_type == InteractionType.RETRY_USED:
                    stats["retried"] += 1
                elif event.interaction_type == InteractionType.DISMISSED:
                    stats["dismissed"] += 1
                elif event.interaction_type == InteractionType.QUESTION_ANSWERED:
                    stats["questions_total"] += 1
                    if event.was_correct:
                        stats["questions_correct"] += 1
        
        return rule_stats
    
    def identify_churn_points(self) -> List[Dict]:
        """
        Identify potential churn points.
        A churn point is where user disengages after a coaching intervention.
        """
        churn_candidates = []
        
        for i, event in enumerate(self.events):
            # Look for patterns: message shown -> dismissed quickly -> no more events
            if event.interaction_type == InteractionType.DISMISSED:
                # Check if this was near the end of the session
                remaining_events = len(self.events) - i - 1
                if remaining_events <= 2:
                    churn_candidates.append({
                        "move_number": event.move_number,
                        "rule_id": event.rule_id,
                        "time_spent_ms": event.time_spent_ms,
                        "type": "quick_dismissal_then_exit",
                    })
        
        return churn_candidates


def create_telemetry_collector(user_id: str, session_id: str, game_id: str) -> TelemetryCollector:
    """Factory function to create a telemetry collector"""
    return TelemetryCollector(user_id, session_id, game_id)
