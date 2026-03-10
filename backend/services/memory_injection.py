"""
Memory Injection Service - The Glue
====================================

This service ensures memory is ALWAYS injected into coaching prompts.
No coaching message should be generated without checking player memory.

KEY PRINCIPLE: Every coaching touchpoint calls this service to get
personalized context before generating any message.

USAGE:
    from services.memory_injection import inject_memory_context
    
    # Before any LLM call for coaching:
    memory_context = await inject_memory_context(db, user_id, current_situation)
    
    # Then include memory_context in your prompt

WHAT IT PROVIDES:
1. Pattern recognition: "This is the same mistake you made against X"
2. Frequency data: "This is your 4th missed fork this week"
3. Behavioral alerts: "You're on a losing streak, take a breath"
4. Style-aware coaching: "As an aggressive player, consider..."
5. Priority focus: "Remember we're working on X"
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
import logging

from services.player_identity import (
    PlayerIdentityService,
    BlunderType,
    PlayStyle,
    TiltTrigger,
    GamePhase
)

logger = logging.getLogger(__name__)


class CoachingContext(str, Enum):
    """Types of coaching situations"""
    GAME_START = "game_start"
    MOVE_ANALYSIS = "move_analysis"
    POST_BLUNDER = "post_blunder"
    POST_GAME = "post_game"
    TRAINING = "training"
    GENERAL_CHAT = "general_chat"


class MemoryInjector:
    """
    Injects player memory into coaching contexts.
    
    Every coaching feature should use this to get personalized context.
    """
    
    def __init__(self, db):
        self.db = db
        self.identity_service = PlayerIdentityService(db)
    
    async def get_full_context(
        self,
        user_id: str,
        context_type: CoachingContext,
        current_pattern: Optional[BlunderType] = None,
        current_game_id: Optional[str] = None,
        current_phase: Optional[GamePhase] = None,
        additional_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Get complete memory context for a coaching situation.
        
        This is THE MAIN FUNCTION to call before any coaching message.
        
        Returns a dict ready to be injected into prompts.
        """
        identity = await self.identity_service.get_or_create(user_id)
        
        result = {
            "has_memory": identity.games_analyzed > 0,
            "games_together": identity.games_analyzed,
            "knows_user": identity.games_analyzed >= 5,
            
            # Core memory sections
            "pattern_match": None,
            "frequency_data": None,
            "behavioral_alert": None,
            "style_context": None,
            "focus_reminder": None,
            
            # Injection text for prompts
            "injection_text": "",
        }
        
        if identity.games_analyzed == 0:
            result["injection_text"] = "NEW USER: No history yet. Be welcoming and educational."
            return result
        
        injection_parts = []
        
        # ===========================================
        # 1. PATTERN MATCHING
        # ===========================================
        if current_pattern:
            similar = await self.identity_service.find_similar_pattern(
                user_id, current_pattern, current_game_id
            )
            
            if similar:
                result["pattern_match"] = similar
                injection_parts.append(
                    f"PATTERN MATCH: User made same mistake ({current_pattern.value}) "
                    f"against {similar['opponent']} {similar['when']}. "
                    f">>> SAY: 'Remember your game against {similar['opponent']}? Same pattern.'"
                )
            
            # Get frequency
            freq = await self.identity_service.get_pattern_frequency(user_id, current_pattern)
            result["frequency_data"] = freq
            
            if freq["total_occurrences"] >= 3:
                injection_parts.append(
                    f"RECURRING PATTERN: This is occurrence #{freq['total_occurrences']} of {current_pattern.value}. "
                    f">>> EMPHASIZE: 'This is the {freq['total_occurrences']}th time. We need to fix this.'"
                )
            
            if freq["is_improving"]:
                injection_parts.append(
                    f"PROGRESS: User is improving on {current_pattern.value}. Acknowledge this!"
                )
        
        # ===========================================
        # 2. BEHAVIORAL ALERTS
        # ===========================================
        behavioral_alert = self._get_behavioral_alert(identity, context_type)
        if behavioral_alert:
            result["behavioral_alert"] = behavioral_alert
            injection_parts.append(f"BEHAVIORAL ALERT: {behavioral_alert['message']}")
        
        # ===========================================
        # 3. STYLE-AWARE CONTEXT
        # ===========================================
        if identity.style_profile.confidence > 0.5:
            style_context = self._get_style_context(identity, current_phase)
            result["style_context"] = style_context
            injection_parts.append(f"STYLE: {style_context['message']}")
        
        # ===========================================
        # 4. FOCUS REMINDER
        # ===========================================
        if identity.priority_focus:
            result["focus_reminder"] = identity.priority_focus
            injection_parts.append(
                f"CURRENT FOCUS: User is working on '{identity.priority_focus}'. "
                f"Relate coaching to this when relevant."
            )
        
        # ===========================================
        # 5. BLUNDER PROFILE SUMMARY
        # ===========================================
        blunder_summary = self._get_blunder_summary(identity)
        if blunder_summary:
            injection_parts.append(f"BLUNDER PROFILE: {blunder_summary}")
        
        # ===========================================
        # BUILD INJECTION TEXT
        # ===========================================
        if injection_parts:
            result["injection_text"] = "\n\n=== PLAYER MEMORY (MUST USE IN RESPONSE) ===\n" + \
                                       "\n".join(injection_parts) + \
                                       "\n=== END MEMORY ===\n"
        else:
            result["injection_text"] = f"\n\n[Player has {identity.games_analyzed} games analyzed. " \
                                       f"Style: {identity.style_profile.primary_style.value}]\n"
        
        return result
    
    def _get_behavioral_alert(
        self, 
        identity, 
        context: CoachingContext
    ) -> Optional[Dict]:
        """Get behavioral alert if applicable"""
        
        # Tilt detection
        if identity.consecutive_losses >= 2:
            return {
                "type": "tilt_warning",
                "severity": "high" if identity.consecutive_losses >= 3 else "medium",
                "message": f"User has lost {identity.consecutive_losses} games in a row. "
                          f"May be tilted. Be encouraging, suggest taking a break.",
                "action": "suggest_break"
            }
        
        # Winning streak - positive reinforcement
        if identity.consecutive_wins >= 3:
            return {
                "type": "hot_streak",
                "severity": "positive",
                "message": f"User is on a {identity.consecutive_wins}-game winning streak! "
                          f"Keep the momentum but stay focused.",
                "action": "encourage"
            }
        
        # Time trouble tendency
        if identity.behavioral_profile.time_trouble_frequency > 0.3:
            return {
                "type": "time_warning",
                "severity": "medium",
                "message": "User often gets into time trouble. "
                          "Remind them to watch the clock.",
                "action": "remind_clock"
            }
        
        # Impulse move tendency
        if identity.blunder_taxonomy.impulse_moves / max(identity.blunder_taxonomy.total_blunders, 1) > 0.3:
            return {
                "type": "impulse_warning",
                "severity": "medium",
                "message": "User tends to make impulse moves (<2s). "
                          "Encourage them to slow down.",
                "action": "slow_down"
            }
        
        return None
    
    def _get_style_context(self, identity, phase: Optional[GamePhase]) -> Dict:
        """Get style-aware coaching context"""
        style = identity.style_profile.primary_style
        
        base_message = f"User is a {style.value} player"
        
        style_advice = {
            PlayStyle.AGGRESSIVE: "They like active play. Suggest dynamic moves.",
            PlayStyle.POSITIONAL: "They prefer strategic play. Focus on long-term plans.",
            PlayStyle.TACTICAL: "They enjoy combinations. Point out tactical opportunities.",
            PlayStyle.DEFENSIVE: "They're careful. Emphasize safety but encourage activity.",
            PlayStyle.UNIVERSAL: "They're flexible. Adapt to the position.",
        }
        
        message = f"{base_message}. {style_advice.get(style, '')}"
        
        # Phase-specific additions
        if phase == GamePhase.ENDGAME:
            comfort = identity.style_profile.endgame_comfort
            if comfort < 0.4:
                message += " They're less comfortable in endgames - give extra guidance."
            elif comfort > 0.7:
                message += " They're confident in endgames."
        
        return {
            "style": style.value,
            "message": message,
            "aggression": identity.style_profile.aggression_score,
            "endgame_comfort": identity.style_profile.endgame_comfort
        }
    
    def _get_blunder_summary(self, identity) -> Optional[str]:
        """Get one-line blunder profile summary"""
        tax = identity.blunder_taxonomy
        
        if tax.total_blunders == 0:
            return None
        
        parts = []
        
        if tax.most_common_type:
            parts.append(f"Main weakness: {tax.most_common_type.value}")
        
        if tax.worst_phase:
            parts.append(f"Struggles in: {tax.worst_phase.value}")
        
        if tax.trend == "improving":
            parts.append("Trend: IMPROVING")
        elif tax.trend == "worsening":
            parts.append("Trend: NEEDS ATTENTION")
        
        return " | ".join(parts) if parts else None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def inject_memory_context(
    db,
    user_id: str,
    context_type: CoachingContext = CoachingContext.GENERAL_CHAT,
    current_pattern: Optional[BlunderType] = None,
    current_game_id: Optional[str] = None,
    current_phase: Optional[GamePhase] = None
) -> Dict[str, Any]:
    """
    Main entry point for memory injection.
    
    Call this before any coaching LLM call:
    
        memory = await inject_memory_context(db, user_id, CoachingContext.POST_BLUNDER, BlunderType.MISSED_FORK)
        
        prompt = f'''
        {memory["injection_text"]}
        
        Now analyze this move...
        '''
    """
    injector = MemoryInjector(db)
    return await injector.get_full_context(
        user_id=user_id,
        context_type=context_type,
        current_pattern=current_pattern,
        current_game_id=current_game_id,
        current_phase=current_phase
    )


async def get_game_start_memory(db, user_id: str) -> Dict[str, Any]:
    """
    Get memory context for game start.
    
    Use this when starting a new game to personalize the greeting.
    """
    injector = MemoryInjector(db)
    context = await injector.get_full_context(
        user_id=user_id,
        context_type=CoachingContext.GAME_START
    )
    
    identity = await injector.identity_service.get_or_create(user_id)
    
    # Add game-start specific data
    context["greeting_type"] = _determine_greeting_type(identity)
    context["session_info"] = {
        "games_today": identity.current_session_games,
        "last_result": identity.last_game_result,
        "streak": identity.consecutive_wins if identity.consecutive_wins > 0 else -identity.consecutive_losses
    }
    
    return context


async def get_post_blunder_memory(
    db,
    user_id: str,
    blunder_type: BlunderType,
    game_id: Optional[str] = None,
    phase: Optional[GamePhase] = None
) -> Dict[str, Any]:
    """
    Get memory context after a blunder.
    
    Use this to generate personalized blunder feedback.
    """
    return await inject_memory_context(
        db=db,
        user_id=user_id,
        context_type=CoachingContext.POST_BLUNDER,
        current_pattern=blunder_type,
        current_game_id=game_id,
        current_phase=phase
    )


async def get_post_game_memory(db, user_id: str, game_result: str) -> Dict[str, Any]:
    """
    Get memory context for post-game analysis.
    
    Use this to personalize the game summary.
    """
    injector = MemoryInjector(db)
    context = await injector.get_full_context(
        user_id=user_id,
        context_type=CoachingContext.POST_GAME
    )
    
    identity = await injector.identity_service.get_or_create(user_id)
    
    # Add post-game specific comparisons
    context["comparison"] = {
        "blunders_vs_average": None,  # Will be filled by caller
        "accuracy_vs_average": None,
    }
    
    # Add milestone checks
    if identity.games_analyzed in [10, 25, 50, 100]:
        context["milestone"] = f"Game #{identity.games_analyzed}!"
    
    return context


def _determine_greeting_type(identity) -> str:
    """Determine what kind of greeting to use"""
    if identity.games_analyzed == 0:
        return "first_game"
    
    if identity.consecutive_losses >= 2:
        return "after_losing_streak"
    
    if identity.consecutive_wins >= 2:
        return "after_winning_streak"
    
    if identity.last_game_result == "win":
        return "after_win"
    
    if identity.last_game_result == "loss":
        return "after_loss"
    
    return "normal"


# =============================================================================
# PROMPT TEMPLATES WITH MEMORY
# =============================================================================

def build_coaching_prompt_with_memory(
    base_prompt: str,
    memory_context: Dict[str, Any],
    additional_instructions: Optional[str] = None
) -> str:
    """
    Build a complete coaching prompt with memory injection.
    
    Usage:
        memory = await inject_memory_context(db, user_id, ...)
        
        prompt = build_coaching_prompt_with_memory(
            base_prompt="Analyze this move: e4",
            memory_context=memory,
            additional_instructions="Be encouraging"
        )
    """
    parts = []
    
    # Memory injection at the start
    if memory_context.get("injection_text"):
        parts.append(memory_context["injection_text"])
    
    # Additional instructions
    if additional_instructions:
        parts.append(f"\nINSTRUCTIONS: {additional_instructions}\n")
    
    # Base prompt
    parts.append(base_prompt)
    
    return "\n".join(parts)
