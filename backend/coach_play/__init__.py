"""
Coach Play Module - P2 Feature

Play With Coach: A training mode where users play full games against a pedagogical coach.

Build Order (per user spec):
1. Bare Session Infrastructure - playable game loop ✅
2. Pre-Move Guardian - intercept blunders before they happen ✅
3. Live Behavior Extraction - detect impulse, panic, threat ignored ✅
4. CPR Engine - Cognitive Performance Rating ✅
5. Identity Engine - Player identity narrative ✅

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

from .pre_move_guardian import (
    PreMoveGuardian,
    evaluate_move_for_guardian,
    RiskLevel,
    RiskType,
    InterventionType,
    GuardianResult
)

from .live_behavior_extractor import (
    LiveBehaviorExtractor,
    BehaviorType,
    BehaviorSeverity,
    BehaviorEvent,
    extract_behaviors_from_move
)

from .cpr_engine import (
    CPREngine,
    CPRComponent,
    CPRResult,
    compute_session_cpr
)

from .identity_engine import (
    IdentityEngine,
    IdentityTrait,
    PlayerIdentity,
    TraitSnapshot,
    update_player_identity
)

__all__ = [
    # Session
    'CoachGameSession',
    'start_coach_session', 
    'make_player_move',
    'get_session_state',
    'end_coach_session',
    'CoachOpponent',
    # Guardian
    'PreMoveGuardian',
    'evaluate_move_for_guardian',
    'RiskLevel',
    'RiskType',
    'InterventionType',
    'GuardianResult',
    # Behavior
    'LiveBehaviorExtractor',
    'BehaviorType',
    'BehaviorSeverity',
    'BehaviorEvent',
    'extract_behaviors_from_move',
    # CPR
    'CPREngine',
    'CPRComponent',
    'CPRResult',
    'compute_session_cpr',
    # Identity
    'IdentityEngine',
    'IdentityTrait',
    'PlayerIdentity',
    'TraitSnapshot',
    'update_player_identity'
]
