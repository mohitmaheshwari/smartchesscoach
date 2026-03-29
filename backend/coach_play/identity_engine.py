"""
Identity Engine - Player Identity Narrative (Step 5)

Builds a player's cognitive identity based on patterns across multiple sessions.
Identity is NOT about chess strength - it's about thinking style.

Identity Traits:
1. AGGRESSIVE vs DEFENSIVE - Attack preference
2. TACTICAL vs POSITIONAL - Calculation vs planning
3. INTUITIVE vs ANALYTICAL - Speed vs depth of thought
4. STEADY vs VOLATILE - Consistency of performance
5. RESILIENT vs FRAGILE - Response to setbacks

Identity Labels (examples):
- "The Calculator" - Analytical, tactical, steady
- "The Warrior" - Aggressive, intuitive, resilient
- "The Strategist" - Positional, analytical, steady
- "The Risk-Taker" - Aggressive, tactical, volatile

Identity evolves over time based on behavior patterns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum

from .live_behavior_extractor import BehaviorType


class IdentityTrait(str, Enum):
    """Trait dimensions for identity"""
    AGGRESSION = "aggression"           # -100 (defensive) to +100 (aggressive)
    CALCULATION = "calculation"         # -100 (intuitive) to +100 (analytical)
    CONSISTENCY = "consistency"         # -100 (volatile) to +100 (steady)
    RESILIENCE = "resilience"           # -100 (fragile) to +100 (resilient)
    RISK_TOLERANCE = "risk_tolerance"   # -100 (conservative) to +100 (bold)


# Identity labels based on trait combinations
IDENTITY_LABELS = [
    {
        "label": "The Calculator",
        "description": "You think deeply, calculating variations with precision.",
        "traits": {IdentityTrait.CALCULATION: (50, 100), IdentityTrait.CONSISTENCY: (30, 100)},
        "icon": "calculator"
    },
    {
        "label": "The Warrior",
        "description": "You attack fearlessly, trusting your instincts in battle.",
        "traits": {IdentityTrait.AGGRESSION: (50, 100), IdentityTrait.RESILIENCE: (30, 100)},
        "icon": "swords"
    },
    {
        "label": "The Strategist",
        "description": "You build positions patiently, planning many moves ahead.",
        "traits": {IdentityTrait.CALCULATION: (30, 100), IdentityTrait.AGGRESSION: (-100, -30)},
        "icon": "chess"
    },
    {
        "label": "The Risk-Taker",
        "description": "You thrive on complications, unafraid of chaos on the board.",
        "traits": {IdentityTrait.RISK_TOLERANCE: (50, 100), IdentityTrait.AGGRESSION: (30, 100)},
        "icon": "flame"
    },
    {
        "label": "The Fortress",
        "description": "You defend solidly, waiting for opponents to overextend.",
        "traits": {IdentityTrait.AGGRESSION: (-100, -30), IdentityTrait.CONSISTENCY: (50, 100)},
        "icon": "shield"
    },
    {
        "label": "The Phoenix",
        "description": "You bounce back from setbacks, learning from every game.",
        "traits": {IdentityTrait.RESILIENCE: (60, 100)},
        "icon": "flame"
    },
    {
        "label": "The Improviser",
        "description": "You play by feel, adapting quickly to changing positions.",
        "traits": {IdentityTrait.CALCULATION: (-100, -30), IdentityTrait.CONSISTENCY: (-50, 50)},
        "icon": "sparkles"
    },
    {
        "label": "The Perfectionist",
        "description": "You seek the best move, sometimes at the cost of time.",
        "traits": {IdentityTrait.CALCULATION: (60, 100), IdentityTrait.RISK_TOLERANCE: (-100, -30)},
        "icon": "target"
    }
]


@dataclass
class TraitSnapshot:
    """Snapshot of trait values at a point in time"""
    aggression: float = 0.0
    calculation: float = 0.0
    consistency: float = 0.0
    resilience: float = 0.0
    risk_tolerance: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "aggression": round(self.aggression, 1),
            "calculation": round(self.calculation, 1),
            "consistency": round(self.consistency, 1),
            "resilience": round(self.resilience, 1),
            "risk_tolerance": round(self.risk_tolerance, 1)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TraitSnapshot':
        return cls(
            aggression=data.get("aggression", 0),
            calculation=data.get("calculation", 0),
            consistency=data.get("consistency", 0),
            resilience=data.get("resilience", 0),
            risk_tolerance=data.get("risk_tolerance", 0)
        )


@dataclass
class PlayerIdentity:
    """A player's cognitive identity"""
    user_id: str
    identity_label: str
    identity_description: str
    identity_icon: str
    trait_snapshot: TraitSnapshot
    confidence: float  # 0-1, how confident we are in the identity
    sessions_analyzed: int
    narrative_timeline: List[Dict] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "identity_label": self.identity_label,
            "identity_description": self.identity_description,
            "identity_icon": self.identity_icon,
            "trait_snapshot": self.trait_snapshot.to_dict(),
            "confidence": round(self.confidence, 2),
            "sessions_analyzed": self.sessions_analyzed,
            "narrative_timeline": self.narrative_timeline[-10:],  # Last 10 entries
            "last_updated": self.last_updated
        }


# Behavior type to trait impact mapping
BEHAVIOR_TRAIT_IMPACTS = {
    BehaviorType.IMPULSE_MOVE: {
        IdentityTrait.CALCULATION: -5,
        IdentityTrait.CONSISTENCY: -3
    },
    BehaviorType.THREAT_IGNORED: {
        IdentityTrait.CALCULATION: -3,
        IdentityTrait.CONSISTENCY: -2
    },
    BehaviorType.PANIC_DEFENSE: {
        IdentityTrait.RESILIENCE: -5,
        IdentityTrait.CONSISTENCY: -4
    },
    BehaviorType.RAPID_STREAK: {
        IdentityTrait.CONSISTENCY: -5,
        IdentityTrait.CALCULATION: -3
    },
    BehaviorType.TIME_PRESSURE_MISTAKE: {
        IdentityTrait.RESILIENCE: -2,
        IdentityTrait.CONSISTENCY: -2
    },
    BehaviorType.CALCULATED_SACRIFICE: {
        IdentityTrait.AGGRESSION: +5,
        IdentityTrait.RISK_TOLERANCE: +5,
        IdentityTrait.CALCULATION: +3
    },
    BehaviorType.POSITIONAL_PATIENCE: {
        IdentityTrait.CALCULATION: +4,
        IdentityTrait.AGGRESSION: -2,
        IdentityTrait.CONSISTENCY: +3
    },
    BehaviorType.TACTICAL_ALERTNESS: {
        IdentityTrait.CALCULATION: +5,
        IdentityTrait.RESILIENCE: +2
    },
    BehaviorType.THREAT_ADDRESSED: {
        IdentityTrait.CALCULATION: +2,
        IdentityTrait.CONSISTENCY: +2
    },
    BehaviorType.ACCURATE_UNDER_PRESSURE: {
        IdentityTrait.RESILIENCE: +5,
        IdentityTrait.CONSISTENCY: +3
    }
}


class IdentityEngine:
    """
    Builds and updates player identity based on behavioral patterns.
    
    Identity should be built over multiple sessions (minimum 3)
    to have meaningful confidence.
    """
    
    MIN_SESSIONS_FOR_IDENTITY = 3
    TRAIT_DECAY_FACTOR = 0.95  # Old traits decay slightly with new data
    
    def __init__(self, existing_identity: Optional[Dict] = None):
        """
        Initialize engine, optionally with existing identity data.
        """
        if existing_identity:
            self.traits = TraitSnapshot.from_dict(existing_identity.get("trait_snapshot", {}))
            self.sessions_analyzed = existing_identity.get("sessions_analyzed", 0)
            self.narrative = existing_identity.get("narrative_timeline", [])
        else:
            self.traits = TraitSnapshot()
            self.sessions_analyzed = 0
            self.narrative = []
    
    def update_from_session(
        self,
        user_id: str,
        behavior_events: List[Dict],
        session_result: str,  # "win", "loss", "draw"
        cpr_score: float,
        cpr_change: Optional[float] = None
    ) -> PlayerIdentity:
        """
        Update identity based on a completed session.
        
        Args:
            user_id: User ID
            behavior_events: List of behavior events from session
            session_result: Game result
            cpr_score: CPR score for the session
            cpr_change: Change in CPR from before session
        
        Returns:
            Updated PlayerIdentity
        """
        # Apply decay to existing traits (recent sessions matter more)
        self.traits.aggression *= self.TRAIT_DECAY_FACTOR
        self.traits.calculation *= self.TRAIT_DECAY_FACTOR
        self.traits.consistency *= self.TRAIT_DECAY_FACTOR
        self.traits.resilience *= self.TRAIT_DECAY_FACTOR
        self.traits.risk_tolerance *= self.TRAIT_DECAY_FACTOR
        
        # Apply behavior impacts
        for event in behavior_events:
            behavior_type = BehaviorType(event["behavior_type"])
            if behavior_type in BEHAVIOR_TRAIT_IMPACTS:
                for trait, impact in BEHAVIOR_TRAIT_IMPACTS[behavior_type].items():
                    current = getattr(self.traits, trait.value)
                    new_value = max(-100, min(100, current + impact))
                    setattr(self.traits, trait.value, new_value)
        
        # Apply result-based adjustments
        if session_result == "win":
            self.traits.resilience += 3
            self.traits.consistency += 2
        elif session_result == "loss":
            # Check for comeback attempts (resilience indicator)
            comeback_behaviors = sum(
                1 for e in behavior_events 
                if e["behavior_type"] in [
                    BehaviorType.ACCURATE_UNDER_PRESSURE.value,
                    BehaviorType.CALCULATED_SACRIFICE.value
                ]
            )
            if comeback_behaviors > 0:
                self.traits.resilience += 2
            else:
                self.traits.resilience -= 2
        
        # Apply CPR-based adjustments
        if cpr_score >= 75:
            self.traits.calculation += 2
            self.traits.consistency += 2
        elif cpr_score < 50:
            self.traits.consistency -= 3
        
        # Update session count
        self.sessions_analyzed += 1
        
        # Add narrative entry
        self._add_narrative_entry(behavior_events, session_result, cpr_score)
        
        # Determine identity label
        label, description, icon = self._determine_identity_label()
        
        # Calculate confidence
        confidence = min(1.0, self.sessions_analyzed / 10)  # Max confidence at 10 sessions
        
        return PlayerIdentity(
            user_id=user_id,
            identity_label=label,
            identity_description=description,
            identity_icon=icon,
            trait_snapshot=self.traits,
            confidence=confidence,
            sessions_analyzed=self.sessions_analyzed,
            narrative_timeline=self.narrative,
            last_updated=datetime.now(timezone.utc).isoformat()
        )
    
    def _determine_identity_label(self) -> Tuple[str, str, str]:
        """Determine best-fitting identity label based on traits"""
        best_match = None
        best_score = -float('inf')
        
        for identity in IDENTITY_LABELS:
            score = 0
            match_count = 0
            
            for trait, (min_val, max_val) in identity["traits"].items():
                trait_value = getattr(self.traits, trait.value)
                
                if min_val <= trait_value <= max_val:
                    # Trait is in range, score based on how centered
                    center = (min_val + max_val) / 2
                    distance = abs(trait_value - center)
                    range_size = max_val - min_val
                    score += 10 - (distance / range_size * 10)
                    match_count += 1
                else:
                    # Trait is out of range, penalty
                    score -= 5
            
            # Bonus for matching all required traits
            if match_count == len(identity["traits"]):
                score += 10
            
            if score > best_score:
                best_score = score
                best_match = identity
        
        if best_match:
            return best_match["label"], best_match["description"], best_match["icon"]
        
        # Default identity if no good match
        return "The Learner", "Still developing your unique style. Keep playing!", "graduation-cap"
    
    def _add_narrative_entry(
        self,
        behavior_events: List[Dict],
        session_result: str,
        cpr_score: float
    ):
        """Add a narrative entry for this session"""
        # Count key behaviors
        impulse_count = sum(1 for e in behavior_events if e["behavior_type"] == BehaviorType.IMPULSE_MOVE.value)
        patience_count = sum(1 for e in behavior_events if e["behavior_type"] == BehaviorType.POSITIONAL_PATIENCE.value)
        sacrifice_count = sum(1 for e in behavior_events if e["behavior_type"] == BehaviorType.CALCULATED_SACRIFICE.value)
        threat_ignored = sum(1 for e in behavior_events if e["behavior_type"] == BehaviorType.THREAT_IGNORED.value)
        
        # Generate narrative snippet
        snippets = []
        
        if cpr_score >= 80:
            snippets.append("Strong cognitive performance.")
        elif cpr_score < 50:
            snippets.append("Struggled with focus this session.")
        
        if impulse_count >= 2:
            snippets.append(f"Made {impulse_count} impulsive moves.")
        
        if patience_count >= 2:
            snippets.append("Showed good patience.")
        
        if sacrifice_count >= 1:
            snippets.append(f"Played {sacrifice_count} calculated sacrifice(s).")
        
        if threat_ignored >= 2:
            snippets.append("Need to work on threat detection.")
        
        result_text = {
            "win": "Won the game.",
            "loss": "Lost but gained experience.",
            "draw": "Drew the game."
        }.get(session_result, "")
        
        narrative = " ".join(snippets) if snippets else result_text
        
        self.narrative.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_result": session_result,
            "cpr_score": cpr_score,
            "narrative": narrative,
            "key_behaviors": {
                "impulse_moves": impulse_count,
                "patience_moments": patience_count,
                "sacrifices": sacrifice_count,
                "threats_ignored": threat_ignored
            }
        })


def update_player_identity(
    user_id: str,
    existing_identity: Optional[Dict],
    behavior_events: List[Dict],
    session_result: str,
    cpr_score: float
) -> Dict:
    """
    Convenience function to update player identity.
    
    Args:
        user_id: User ID
        existing_identity: Existing identity dict from DB (or None)
        behavior_events: Behavior events from session
        session_result: Game result
        cpr_score: CPR score
    
    Returns:
        Updated identity as dict
    """
    engine = IdentityEngine(existing_identity)
    identity = engine.update_from_session(
        user_id=user_id,
        behavior_events=behavior_events,
        session_result=session_result,
        cpr_score=cpr_score
    )
    return identity.to_dict()
