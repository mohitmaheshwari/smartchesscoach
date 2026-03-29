"""
Reward Message Service - Deterministic Coach Messages
=====================================================
Version: v1
All coach messages are template-based, no LLM.
Messages adapt by rating band and have cooldown/anti-repeat rules.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
from reflect_constants import (
    RatingBand, RewardTone, RewardEventType,
    get_rating_band, ADAPTIVE_DEFAULTS
)
import random
import logging

logger = logging.getLogger(__name__)


# ============================================
# MESSAGE TEMPLATES
# ============================================
# Each template has:
# - id: stable identifier
# - event_type: when to show
# - variants: by reward tone (encouragement/pattern_progress/precision)
# - cooldown_sessions: don't repeat within N sessions

MESSAGE_TEMPLATES = {
    # === REFLECTION REWARDS ===
    "reflect_captured_fast_1": {
        "event_type": RewardEventType.REFLECTION_CAPTURED_FAST,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Good. You captured your thinking while it was fresh.",
            RewardTone.PATTERN_PROGRESS: "Nice. This makes your training more accurate.",
            RewardTone.PRECISION: "Fresh memory captured. This improves pattern detection.",
        },
        "cooldown_sessions": 3,
    },
    "reflect_captured_fast_2": {
        "event_type": RewardEventType.REFLECTION_CAPTURED_FAST,
        "variants": {
            RewardTone.ENCOURAGEMENT: "That's how strong players learn — reflect right after.",
            RewardTone.PATTERN_PROGRESS: "Good habit. Reflection while memory is fresh matters.",
            RewardTone.PRECISION: "Timely reflection. Quality data for training.",
        },
        "cooldown_sessions": 3,
    },
    
    "reflect_honest_unsure_1": {
        "event_type": RewardEventType.REFLECTION_HONEST_NOT_SURE,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Honest answer. 'Not sure' is useful data.",
            RewardTone.PATTERN_PROGRESS: "Good. Recognizing uncertainty helps us build clearer drills.",
            RewardTone.PRECISION: "Honest uncertainty. We'll target this specific pattern.",
        },
        "cooldown_sessions": 5,
    },
    
    "reflect_confidence_insight_1": {
        "event_type": RewardEventType.REFLECTION_CONFIDENCE_INSIGHT,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Useful. You were confident, but the position had a trap.",
            RewardTone.PATTERN_PROGRESS: "This is exactly what we can train — confidence before scan.",
            RewardTone.PRECISION: "Confidence-scan mismatch identified. Trainable pattern.",
        },
        "cooldown_sessions": 3,
    },
    
    "reflect_complete_1": {
        "event_type": RewardEventType.REFLECTION_COMPLETE,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Done. Your training just got more personal.",
            RewardTone.PATTERN_PROGRESS: "Reflection complete. This data improves your drills.",
            RewardTone.PRECISION: "Captured. Mission will now target this specific pattern.",
        },
        "cooldown_sessions": 2,
    },
    
    # === PROCESS REWARDS ===
    "process_threat_scan_1": {
        "event_type": RewardEventType.PROCESS_THREAT_SCAN,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Good. You checked the opponent's threat before moving.",
            RewardTone.PATTERN_PROGRESS: "Nice check. You looked at forcing moves first.",
            RewardTone.PRECISION: "Threat scan before move. That habit prevents blunders.",
        },
        "cooldown_sessions": 2,
    },
    
    "process_slowed_down_1": {
        "event_type": RewardEventType.PROCESS_SLOWED_DOWN,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Good. Slowing down helped here.",
            RewardTone.PATTERN_PROGRESS: "You took time before moving. That itself reduces mistakes.",
            RewardTone.PRECISION: "Deliberate pace. Process over speed.",
        },
        "cooldown_sessions": 3,
    },
    
    # === PATTERN REWARDS ===
    "pattern_recognized_1": {
        "event_type": RewardEventType.PATTERN_RECOGNIZED,
        "variants": {
            RewardTone.ENCOURAGEMENT: "You caught that pattern. Well done.",
            RewardTone.PATTERN_PROGRESS: "Same pattern from your game — you recognized it now.",
            RewardTone.PRECISION: "Pattern match. You're building recognition.",
        },
        "cooldown_sessions": 2,
    },
    "pattern_recognized_2": {
        "event_type": RewardEventType.PATTERN_RECOGNIZED,
        "variants": {
            RewardTone.ENCOURAGEMENT: "That's the same type of position. Good catch.",
            RewardTone.PATTERN_PROGRESS: "You're starting to recognize this earlier now.",
            RewardTone.PRECISION: "Pattern recognition improving.",
        },
        "cooldown_sessions": 2,
    },
    
    "pattern_caught_repeat_1": {
        "event_type": RewardEventType.PATTERN_CAUGHT_REPEAT,
        "variants": {
            RewardTone.ENCOURAGEMENT: "You caught it twice in a row. The pattern is clicking.",
            RewardTone.PATTERN_PROGRESS: "Two in a row on this pattern. Good progress.",
            RewardTone.PRECISION: "Consecutive recognition. Pattern becoming reliable.",
        },
        "cooldown_sessions": 5,
    },
    
    # === RECOVERY REWARDS ===
    "recovery_good_reset_1": {
        "event_type": RewardEventType.RECOVERY_GOOD_RESET,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Good reset after the miss. The next reads were cleaner.",
            RewardTone.PATTERN_PROGRESS: "That recovery matters more than the mistake.",
            RewardTone.PRECISION: "Clean recovery sequence. Resilience matters.",
        },
        "cooldown_sessions": 3,
    },
    
    # === MISSION REWARDS ===
    "mission_complete_pass_1": {
        "event_type": RewardEventType.MISSION_COMPLETE_PASS,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Mission complete. You trained the exact pattern from your game.",
            RewardTone.PATTERN_PROGRESS: "Well done. This was targeted repair, not random practice.",
            RewardTone.PRECISION: "Mission complete. Pattern addressed.",
        },
        "cooldown_sessions": 1,
    },
    "mission_complete_pass_2": {
        "event_type": RewardEventType.MISSION_COMPLETE_PASS,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Good work. You fixed something real today.",
            RewardTone.PATTERN_PROGRESS: "Clean session. Tomorrow we reinforce this.",
            RewardTone.PRECISION: "Objective achieved. Next: apply in game.",
        },
        "cooldown_sessions": 1,
    },
    
    "mission_complete_fail_1": {
        "event_type": RewardEventType.MISSION_COMPLETE_FAIL,
        "variants": {
            RewardTone.ENCOURAGEMENT: "Not clean yet, but useful session. We'll do a shorter one tomorrow.",
            RewardTone.PATTERN_PROGRESS: "This pattern is still active. Good that we caught it.",
            RewardTone.PRECISION: "Pattern needs more work. Shorter mission tomorrow.",
        },
        "cooldown_sessions": 1,
    },
}


class RewardMessageSelector:
    """
    Selects appropriate reward messages based on event type and user context.
    Handles cooldown and anti-repeat rules.
    """
    
    def __init__(
        self,
        rating: int,
        recent_message_ids: List[str] = None,
    ):
        self.rating = rating
        self.rating_band = get_rating_band(rating)
        self.recent_message_ids = recent_message_ids or []
        
        # Get reward tone for this band
        config = ADAPTIVE_DEFAULTS.get(self.rating_band, ADAPTIVE_DEFAULTS[RatingBand.BAND_C])
        self.reward_tone = config["reward_tone"]
    
    def select_message(
        self,
        event_type: RewardEventType,
        context: Dict = None,
    ) -> Optional[Dict]:
        """
        Select a message for the given event type.
        
        Args:
            event_type: The reward event type
            context: Optional context (focus_label, score, etc.)
        
        Returns:
            {
                "message_id": "...",
                "text": "...",
                "event_type": "...",
            }
        """
        # Find all templates for this event type
        candidates = []
        for msg_id, template in MESSAGE_TEMPLATES.items():
            if template["event_type"] == event_type:
                # Check cooldown
                cooldown = template.get("cooldown_sessions", 2)
                recent_count = self.recent_message_ids[-cooldown:].count(msg_id) if self.recent_message_ids else 0
                
                if recent_count == 0:
                    candidates.append((msg_id, template))
        
        if not candidates:
            # All messages on cooldown - pick any
            for msg_id, template in MESSAGE_TEMPLATES.items():
                if template["event_type"] == event_type:
                    candidates.append((msg_id, template))
        
        if not candidates:
            return None
        
        # Select randomly from candidates
        msg_id, template = random.choice(candidates)
        
        # Get text for this tone
        text = template["variants"].get(
            self.reward_tone,
            template["variants"].get(RewardTone.PATTERN_PROGRESS, "Good progress.")
        )
        
        # Apply context substitution if any
        if context:
            for key, value in context.items():
                text = text.replace(f"{{{key}}}", str(value))
        
        return {
            "message_id": msg_id,
            "text": text,
            "event_type": event_type.value,
        }
    
    def get_mission_completion_message(
        self,
        passed: bool,
        score: Dict,
        focus_label: str,
    ) -> Dict:
        """Get message for mission completion."""
        event_type = RewardEventType.MISSION_COMPLETE_PASS if passed else RewardEventType.MISSION_COMPLETE_FAIL
        
        message = self.select_message(event_type, {
            "correct": score.get("correct", 0),
            "attempted": score.get("attempted", 0),
            "focus_label": focus_label,
        })
        
        # Add score summary
        if message:
            message["score_summary"] = f"{score.get('correct', 0)}/{score.get('attempted', 0)}"
        
        return message


def get_reward_message(
    event_type: RewardEventType,
    rating: int,
    context: Dict = None,
    recent_message_ids: List[str] = None,
) -> Optional[Dict]:
    """
    Main entry point for getting reward messages.
    """
    selector = RewardMessageSelector(
        rating=rating,
        recent_message_ids=recent_message_ids,
    )
    return selector.select_message(event_type, context)


# ============================================
# POST-LOSS RECOVERY MESSAGES (special case)
# ============================================
POST_LOSS_MESSAGES = {
    "headline": {
        RewardTone.ENCOURAGEMENT: "Tough game. Don't waste it.",
        RewardTone.PATTERN_PROGRESS: "That game had lessons. Let's fix one now.",
        RewardTone.PRECISION: "Loss captured. One issue to address.",
    },
    "subtext": {
        RewardTone.ENCOURAGEMENT: "We found one pattern worth fixing today.",
        RewardTone.PATTERN_PROGRESS: "Main issue identified. Quick fix available.",
        RewardTone.PRECISION: "Priority leak detected.",
    },
    "cta": {
        RewardTone.ENCOURAGEMENT: "Start {minutes}-minute fix",
        RewardTone.PATTERN_PROGRESS: "Fix in {minutes} minutes",
        RewardTone.PRECISION: "{minutes}-min repair",
    },
}


def get_post_loss_message(rating: int, focus_label: str, minutes: int) -> Dict:
    """Get post-loss recovery screen messages."""
    band = get_rating_band(rating)
    config = ADAPTIVE_DEFAULTS.get(band, ADAPTIVE_DEFAULTS[RatingBand.BAND_C])
    tone = config["reward_tone"]
    
    return {
        "headline": POST_LOSS_MESSAGES["headline"].get(tone, POST_LOSS_MESSAGES["headline"][RewardTone.PATTERN_PROGRESS]),
        "subtext": POST_LOSS_MESSAGES["subtext"].get(tone, POST_LOSS_MESSAGES["subtext"][RewardTone.PATTERN_PROGRESS]),
        "focus_label": focus_label,
        "cta_text": POST_LOSS_MESSAGES["cta"].get(tone, "Start fix").replace("{minutes}", str(minutes)),
        "minutes": minutes,
    }


# ============================================
# WEEKLY PROOF CARD MESSAGES
# ============================================
def generate_weekly_proof(
    rating: int,
    blunders_delta: float,  # negative = improvement
    main_leak: str,
    improvement_area: Optional[str] = None,
    next_focus: str = None,
) -> Dict:
    """
    Generate weekly proof card content.
    3 lines: improvement, ongoing issue, next focus.
    """
    band = get_rating_band(rating)
    config = ADAPTIVE_DEFAULTS.get(band, ADAPTIVE_DEFAULTS[RatingBand.BAND_C])
    tone = config["reward_tone"]
    
    lines = []
    
    # Line 1: Improvement (if any)
    if blunders_delta < -0.3:
        if tone == RewardTone.ENCOURAGEMENT:
            lines.append(f"✅ You're blundering less — good progress")
        elif tone == RewardTone.PATTERN_PROGRESS:
            lines.append(f"✅ Blunder rate improved this week")
        else:
            lines.append(f"✅ Blunder frequency reduced")
    elif improvement_area:
        lines.append(f"✅ {improvement_area}")
    else:
        lines.append("✅ Steady week — no regression")
    
    # Line 2: Ongoing issue
    if main_leak:
        if tone == RewardTone.ENCOURAGEMENT:
            lines.append(f"⚠️ Still working on: {main_leak}")
        else:
            lines.append(f"⚠️ Active leak: {main_leak}")
    
    # Line 3: Next focus
    if next_focus:
        lines.append(f"🎯 Next focus: {next_focus}")
    
    return {
        "lines": lines,
        "rating_band": band.value,
    }
