"""
Coach Play Module - P2 Feature

Play With Coach: A training mode where users play full games against a pedagogical coach.

Build Order (per user spec):
1. Bare Session Infrastructure - playable game loop
2. Pre-Move Guardian - intercept blunders before they happen  
3. Live Behavior Extraction - detect impulse, panic, threat ignored
4. CPR Engine - Cognitive Performance Rating
5. Identity Engine - Player identity narrative

Key principle: Interception timing intelligence is the differentiator.
"""

from .coach_game_session import (
    CoachGameSession,
    start_coach_session,
    make_player_move,
    get_session_state,
    end_coach_session
)

from .coach_opponent import CoachOpponent

__all__ = [
    'CoachGameSession',
    'start_coach_session', 
    'make_player_move',
    'get_session_state',
    'end_coach_session',
    'CoachOpponent'
]
