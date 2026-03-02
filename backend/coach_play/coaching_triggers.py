"""
Coaching Triggers - Decides WHEN the coach should speak

The coach doesn't comment on every move. Instead, it intelligently
decides when to speak based on:
1. User's rating level (what matters to them)
2. Move quality (was it good, bad, critical?)
3. Position characteristics (tactical, strategic, critical moment?)

Rating-based trigger thresholds:
- <1200: Blunders (>3 pawns), hanging pieces, missed mate
- 1200-1600: Mistakes (>1.5 pawns), obvious tactics, threats
- 1600-2000: Inaccuracies (>0.5 pawns), 2-3 move tactics
- 2000+: Strategic errors, deep tactics, positional nuances
"""

from enum import Enum
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import random


class CoachTriggerType(str, Enum):
    """Types of coaching triggers"""
    ENCOURAGEMENT = "encouragement"      # Good move, celebrate!
    REFLECTION = "reflection"            # Ask why they played this
    TEACHING = "teaching"                # Explain what happened
    WARNING = "warning"                  # Point out what was missed
    OPENING_GUIDANCE = "opening"         # Opening-specific advice
    NONE = "none"                        # Don't speak


@dataclass
class CoachTrigger:
    """Result of trigger evaluation"""
    should_speak: bool
    trigger_type: CoachTriggerType
    priority: int  # 1-10, higher = more important
    context: Dict  # Additional info for message generation


class CoachingTriggers:
    """
    Determines when the coach should speak during a game.
    
    Philosophy:
    - Don't interrupt on every move
    - Speak when there's something meaningful to say
    - Adapt to user's level
    - Celebrate good moves, teach on mistakes
    """
    
    # Thresholds by rating range (eval_loss in pawns)
    THRESHOLDS = {
        # (min_rating, max_rating): (blunder_threshold, mistake_threshold, inaccuracy_threshold)
        (0, 1200): (3.0, 2.0, 1.5),
        (1200, 1400): (2.5, 1.5, 1.0),
        (1400, 1600): (2.0, 1.2, 0.8),
        (1600, 1800): (1.5, 1.0, 0.5),
        (1800, 2000): (1.2, 0.8, 0.4),
        (2000, 2200): (1.0, 0.6, 0.3),
        (2200, 9999): (0.8, 0.5, 0.25),
    }
    
    # Encouragement phrases for good moves
    ENCOURAGEMENT_PHRASES = {
        "best_move": [
            "Excellent! You found the best move.",
            "Perfect! That's exactly right.",
            "Great calculation!",
            "You're playing sharp!",
            "Nicely done!",
        ],
        "good_move": [
            "Good move!",
            "Solid choice.",
            "That's a strong continuation.",
            "Well played.",
            "Nice!",
        ],
        "interesting": [
            "Interesting choice...",
            "That's a creative idea.",
            "I see what you're going for.",
        ]
    }
    
    def __init__(self, user_rating: int = 1200):
        self.user_rating = user_rating
        self.thresholds = self._get_thresholds(user_rating)
        self._move_count = 0
        self._last_spoke_at = -1
        self._consecutive_good_moves = 0
    
    def _get_thresholds(self, rating: int) -> Tuple[float, float, float]:
        """Get eval loss thresholds for user's rating."""
        for (min_r, max_r), thresholds in self.THRESHOLDS.items():
            if min_r <= rating < max_r:
                return thresholds
        return (1.5, 1.0, 0.5)  # Default
    
    def evaluate_trigger(
        self,
        move_san: str,
        eval_before: float,
        eval_after: float,
        is_best_move: bool,
        is_candidate: bool,
        best_move_san: str,
        phase: str,
        move_number: int,
        is_check: bool = False,
        is_capture: bool = False,
        opening_name: Optional[str] = None
    ) -> CoachTrigger:
        """
        Evaluate whether the coach should speak after this move.
        
        Returns a CoachTrigger with decision and context.
        """
        self._move_count = move_number
        
        # Calculate eval loss (from user's perspective)
        eval_loss = eval_before - eval_after
        if eval_loss < 0:
            eval_loss = 0  # Move was better than expected
        
        blunder_thresh, mistake_thresh, inaccuracy_thresh = self.thresholds
        
        # === ENCOURAGEMENT TRIGGERS ===
        
        # Best move found!
        if is_best_move:
            self._consecutive_good_moves += 1
            
            # Don't praise every single best move - that's annoying
            # Praise more at the start, then occasionally
            should_praise = (
                move_number <= 5 or  # Early game, encourage development
                self._consecutive_good_moves >= 3 or  # Streak!
                random.random() < 0.3  # 30% chance otherwise
            )
            
            if should_praise:
                self._last_spoke_at = move_number
                return CoachTrigger(
                    should_speak=True,
                    trigger_type=CoachTriggerType.ENCOURAGEMENT,
                    priority=4,
                    context={
                        "move": move_san,
                        "message_type": "best_move",
                        "streak": self._consecutive_good_moves
                    }
                )
        
        # Good candidate move
        elif is_candidate and eval_loss < 0.2:
            self._consecutive_good_moves += 1
            
            # Occasionally praise good moves
            if random.random() < 0.2:  # 20% chance
                self._last_spoke_at = move_number
                return CoachTrigger(
                    should_speak=True,
                    trigger_type=CoachTriggerType.ENCOURAGEMENT,
                    priority=3,
                    context={
                        "move": move_san,
                        "message_type": "good_move"
                    }
                )
        else:
            self._consecutive_good_moves = 0
        
        # === TEACHING TRIGGERS (mistakes) ===
        
        # Blunder - always speak
        if eval_loss >= blunder_thresh:
            self._last_spoke_at = move_number
            return CoachTrigger(
                should_speak=True,
                trigger_type=CoachTriggerType.WARNING,
                priority=10,
                context={
                    "move": move_san,
                    "eval_loss": eval_loss,
                    "best_move": best_move_san,
                    "severity": "blunder",
                    "eval_before": eval_before,
                    "eval_after": eval_after
                }
            )
        
        # Mistake - usually speak
        if eval_loss >= mistake_thresh:
            self._last_spoke_at = move_number
            return CoachTrigger(
                should_speak=True,
                trigger_type=CoachTriggerType.TEACHING,
                priority=8,
                context={
                    "move": move_san,
                    "eval_loss": eval_loss,
                    "best_move": best_move_san,
                    "severity": "mistake",
                    "eval_before": eval_before,
                    "eval_after": eval_after
                }
            )
        
        # Inaccuracy - speak if we haven't spoken recently
        if eval_loss >= inaccuracy_thresh:
            # Don't spam - only if we haven't spoken in last 3 moves
            if move_number - self._last_spoke_at >= 3:
                self._last_spoke_at = move_number
                return CoachTrigger(
                    should_speak=True,
                    trigger_type=CoachTriggerType.REFLECTION,
                    priority=5,
                    context={
                        "move": move_san,
                        "eval_loss": eval_loss,
                        "best_move": best_move_san,
                        "severity": "inaccuracy"
                    }
                )
        
        # === OPENING GUIDANCE ===
        
        # In opening phase, occasionally comment on the opening
        if phase == "opening" and opening_name and move_number <= 10:
            if move_number == 3 or (move_number == 6 and random.random() < 0.5):
                self._last_spoke_at = move_number
                return CoachTrigger(
                    should_speak=True,
                    trigger_type=CoachTriggerType.OPENING_GUIDANCE,
                    priority=4,
                    context={
                        "opening_name": opening_name,
                        "move_number": move_number
                    }
                )
        
        # === NO TRIGGER ===
        return CoachTrigger(
            should_speak=False,
            trigger_type=CoachTriggerType.NONE,
            priority=0,
            context={}
        )
    
    def get_encouragement_phrase(self, message_type: str, streak: int = 0) -> str:
        """Get a random encouragement phrase."""
        phrases = self.ENCOURAGEMENT_PHRASES.get(message_type, self.ENCOURAGEMENT_PHRASES["good_move"])
        phrase = random.choice(phrases)
        
        # Add streak mention for consecutive good moves
        if streak >= 3:
            phrase += f" That's {streak} strong moves in a row!"
        
        return phrase


def should_coach_speak(
    user_rating: int,
    move_san: str,
    eval_before: float,
    eval_after: float,
    is_best_move: bool,
    is_candidate: bool,
    best_move_san: str,
    phase: str,
    move_number: int,
    **kwargs
) -> CoachTrigger:
    """
    Convenience function to check if coach should speak.
    
    Returns CoachTrigger with decision.
    """
    triggers = CoachingTriggers(user_rating)
    return triggers.evaluate_trigger(
        move_san=move_san,
        eval_before=eval_before,
        eval_after=eval_after,
        is_best_move=is_best_move,
        is_candidate=is_candidate,
        best_move_san=best_move_san,
        phase=phase,
        move_number=move_number,
        **kwargs
    )
