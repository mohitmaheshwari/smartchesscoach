"""
Coach Narrative Engine - Structured Explanation Generator

Transforms structured coaching data into human-like explanations
using a deterministic template system with tone adjustment.

Pipeline:
    selected_moment + context → narrative_strategy
                              → structured_components
                              → tone_adjustment
                              → assembled_text

This is NOT an LLM generator. It's a coaching grammar system.

Key principle: Store structure, render text.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NarrativeStrategy(str, Enum):
    """Which narrative approach to use based on selection reason"""
    PATTERN_COACHING = "pattern_coaching"
    TURNING_POINT_COACHING = "turning_point_coaching"
    TACTICAL_COACHING = "tactical_coaching"
    MATE_ALERT = "mate_alert"
    POSITIVE_COACHING = "positive_coaching"  # Good game - reinforce discipline


class ToneProfile(str, Enum):
    """Tone adjustment based on behavioral maturity"""
    NOVICE = "Novice"           # More explanation, encouraging
    DEVELOPING = "Developing"   # Balanced
    DISCIPLINED = "Disciplined" # Shorter, direct, challenging
    ADVANCED = "Advanced"       # Minimal, assumes understanding


# Threshold for triggering positive coaching (max CRS below this = good game)
# Higher maturity = higher standards
POSITIVE_CRS_THRESHOLD = {
    "Novice": 80,
    "Developing": 50,
    "Disciplined": 30,
    "Advanced": 20
}


@dataclass
class NarrativeComponents:
    """Structured coaching explanation components"""
    intent_mirror_line: str
    thinking_break_line: str
    position_consequence_line: str
    teaching_line: str
    rule_line: str
    theme_reinforcement_line: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "intent_mirror_line": self.intent_mirror_line,
            "thinking_break_line": self.thinking_break_line,
            "position_consequence_line": self.position_consequence_line,
            "teaching_line": self.teaching_line,
            "rule_line": self.rule_line,
            "theme_reinforcement_line": self.theme_reinforcement_line
        }


# =============================================================================
# NARRATIVE TEMPLATES BY STRATEGY
# =============================================================================

# Intent mirrors - acknowledge what player was trying to do
INTENT_TEMPLATES = {
    "attack": [
        "You wanted to create attacking chances.",
        "The idea was to generate pressure.",
        "You were looking for activity.",
    ],
    "defend": [
        "You tried to hold the position.",
        "The idea was defensive.",
        "You were trying to consolidate.",
    ],
    "simplify": [
        "You wanted to simplify.",
        "The trade made sense in principle.",
        "You were looking to exchange pieces.",
    ],
    "develop": [
        "You wanted to complete development.",
        "The idea was to improve your pieces.",
        "You were working on piece activity.",
    ],
    "default": [
        "This move had a clear intent.",
        "You had a plan here.",
        "The idea wasn't wrong.",
    ]
}

# Thinking break templates - where cognition failed
BREAK_TEMPLATES = {
    "threat_missed": [
        "But you didn't check what they could do first.",
        "However, their reply was not considered.",
        "But opponent had a forcing move.",
    ],
    "calculation_short": [
        "But you stopped calculating one move too soon.",
        "The sequence wasn't calculated fully.",
        "But one more move would have shown the problem.",
    ],
    "position_read": [
        "But the position required a different approach.",
        "However, the structure changed character.",
        "But the dynamics were different than expected.",
    ],
    "pattern_repeat": [
        "This is a pattern appearing in your games.",
        "This thinking error has shown up before.",
        "The same type of oversight happened recently.",
    ],
    "default": [
        "But there was a problem.",
        "However, something was missed.",
        "But the position held a surprise.",
    ]
}

# Consequence templates - what happened on the board
CONSEQUENCE_TEMPLATES = {
    "tactical": [
        "After {played}, {threat} wins material.",
        "Following {played}, opponent has {threat}.",
        "{best} would have avoided the tactic.",
    ],
    "positional": [
        "After this, your position became passive.",
        "The structure turned against you.",
        "Opponent gained lasting pressure.",
    ],
    "tempo": [
        "You lost important time.",
        "The initiative switched sides.",
        "Opponent took over the game.",
    ],
    "mate": [
        "There was a forced mate: {line}.",
        "Mate in {count} was available.",
        "A winning attack was missed.",
    ],
    "default": [
        "The position worsened significantly.",
        "This changed the evaluation.",
        "The game became more difficult.",
    ]
}

# Teaching templates - underlying principle
TEACHING_TEMPLATES = {
    "threat_verification": [
        "Always verify opponent threats before committing.",
        "Forcing moves must be checked first.",
        "Defense comes before attack.",
    ],
    "calculation": [
        "Calculate one move deeper than feels necessary.",
        "Complete the sequence before moving.",
        "Check the opponent's best reply.",
    ],
    "conversion": [
        "When ahead, simplify carefully.",
        "Winning positions require patience.",
        "Don't attack when consolidation wins.",
    ],
    "defense": [
        "Hold the position before counterattacking.",
        "Defensive moves can be the strongest.",
        "Patience in defense often pays off.",
    ],
    "mate_awareness": [
        "In winning positions, check for forcing finishes.",
        "Mate patterns should be scanned actively.",
        "When attacking, calculate to the end.",
    ],
    "default": [
        "Slow down at critical moments.",
        "Double-check before committing.",
        "The position deserved more attention.",
    ]
}

# Rule templates - actionable takeaway
RULE_TEMPLATES = {
    "threat_scan": [
        "Before YOUR move, check what THEY can do.",
        "Scan checks-captures-threats before committing.",
        "Ask: What's their best reply?",
    ],
    "calculation_depth": [
        "Calculate one move further than usual.",
        "Ask: Then what? after every move.",
        "Don't stop until the position is quiet.",
    ],
    "piece_safety": [
        "Check if the piece is safe on its new square.",
        "Count attackers vs defenders before moving.",
        "Undefended pieces cause problems.",
    ],
    "conversion": [
        "When winning, trade pieces not pawns.",
        "Simplify when ahead materially.",
        "No need to attack — just maintain.",
    ],
    "patience": [
        "Improve your worst piece first.",
        "Don't rush when the position is unclear.",
        "Small improvements beat forcing moves.",
    ],
    "default": [
        "Take more time on critical decisions.",
        "Verify before executing.",
        "Slow down at turning points.",
    ]
}

# Theme reinforcement templates
THEME_REINFORCEMENT = {
    "ThreatVerification": "This connects to your current focus: verifying opponent threats.",
    "CalculationDepth": "This ties to your work on calculating deeper.",
    "ConversionDiscipline": "This relates to your focus on converting winning positions.",
    "PieceSafety": "This connects to keeping your pieces safe.",
    "TimeManagement": "This relates to using your time wisely.",
    "OpeningRepertoire": "This ties to your opening preparation.",
    "EndgameTechnique": "This connects to your endgame improvement.",
    "PositionalPatience": "This relates to your work on positional play.",
}

# =============================================================================
# POSITIVE COACHING TEMPLATES
# =============================================================================

# Validation lines - what went right
VALIDATION_TEMPLATES = {
    "ThreatVerification": [
        "Your threat scanning was disciplined this game.",
        "You consistently checked opponent possibilities.",
        "No simple tactics got through.",
    ],
    "CalculationDepth": [
        "Your calculation was thorough today.",
        "You didn't stop sequences early.",
        "The depth of your thinking showed.",
    ],
    "ConversionDiscipline": [
        "You simplified correctly when ahead.",
        "No unnecessary risks when winning.",
        "You converted advantages cleanly.",
    ],
    "PieceSafety": [
        "Your pieces stayed coordinated throughout.",
        "Nothing was left hanging.",
        "Piece placement was secure.",
    ],
    "default": [
        "You played with discipline today.",
        "No major thinking errors appeared.",
        "The game showed good control.",
    ]
}

# Stability insight - position stayed controlled
STABILITY_TEMPLATES = [
    "Even when the position became sharp, you stayed composed.",
    "The evaluation stayed stable throughout.",
    "You didn't give opponent free chances.",
    "Pressure was maintained without overextending.",
    "The position never became uncomfortable.",
]

# Positive teaching - reinforce good habits
POSITIVE_TEACHING = {
    "ThreatVerification": [
        "This is exactly how to avoid unnecessary losses.",
        "Consistent checking pays off over time.",
        "Keep this awareness in every game.",
    ],
    "CalculationDepth": [
        "Deep thinking prevents accidents.",
        "This patience will serve you well.",
        "Thoroughness becomes habit with practice.",
    ],
    "ConversionDiscipline": [
        "Winning games is about not losing them.",
        "This restraint separates improving players.",
        "Converting cleanly is a skill.",
    ],
    "default": [
        "This is the discipline that leads to rating gains.",
        "Consistent play beats occasional brilliance.",
        "Keep this approach in future games.",
    ]
}

# Positive intent mirrors
POSITIVE_INTENT = [
    "You approached this game with patience.",
    "Your mindset was solid from the start.",
    "The game showed careful thinking.",
    "You played within your abilities.",
]

# Streak acknowledgment (when good_game_streak >= 2)
STREAK_ACKNOWLEDGMENT = [
    "This is becoming a pattern.",
    "Consistency is emerging.",
    "Your discipline is building.",
]


class CoachNarrativeEngine:
    """
    Generates structured coaching explanations.
    
    Does NOT call LLMs. Uses deterministic template selection
    with variation to avoid repetition.
    """
    
    def __init__(self, recent_sentences: List[str] = None):
        self.recent_sentences = recent_sentences or []
    
    def generate_narrative(
        self,
        selected_move: Dict,
        selection_reason: str,
        position_context: Dict,
        maturity_level: str,
        active_theme: str = None,
        game_result: str = None,
        max_crs_score: float = None,
        good_game_streak: int = 0
    ) -> Tuple[NarrativeComponents, str, float]:
        """
        Generate structured coaching narrative.
        
        Args:
            selected_move: The critical move data
            selection_reason: Why this move was selected (pattern_event, tactical_error, etc.)
            position_context: Position state before/after
            maturity_level: User's behavioral maturity (Novice, Developing, etc.)
            active_theme: Current coaching theme
            game_result: Game outcome
            max_crs_score: Maximum CRS score in the game (for positive coaching trigger)
            good_game_streak: Number of consecutive good games
            
        Returns:
            (NarrativeComponents, narrative_strategy, explanation_confidence)
        """
        # Check if this should be positive coaching
        threshold = POSITIVE_CRS_THRESHOLD.get(maturity_level, 50)
        is_positive = (
            selection_reason == "no_critical_moves" or
            (max_crs_score is not None and max_crs_score < threshold)
        )
        
        if is_positive:
            return self._generate_positive_narrative(
                active_theme=active_theme,
                maturity_level=maturity_level,
                good_game_streak=good_game_streak
            )
        
        # Standard corrective coaching
        strategy = self._determine_strategy(selection_reason)
        
        # Generate each component
        intent = self._generate_intent(selected_move, position_context)
        thinking_break = self._generate_break(selected_move, strategy)
        consequence = self._generate_consequence(selected_move, strategy, position_context)
        teaching = self._generate_teaching(selected_move, strategy)
        rule = self._generate_rule(selected_move, strategy)
        
        # Theme reinforcement
        theme_line = None
        if active_theme and active_theme in THEME_REINFORCEMENT:
            theme_line = THEME_REINFORCEMENT[active_theme]
        
        # Calculate explanation confidence
        confidence = self._calculate_confidence(selected_move, position_context)
        
        components = NarrativeComponents(
            intent_mirror_line=intent,
            thinking_break_line=thinking_break,
            position_consequence_line=consequence,
            teaching_line=teaching,
            rule_line=rule,
            theme_reinforcement_line=theme_line
        )
        
        return components, strategy.value, confidence
    
    def _generate_positive_narrative(
        self,
        active_theme: str = None,
        maturity_level: str = "Developing",
        good_game_streak: int = 0
    ) -> Tuple[NarrativeComponents, str, float]:
        """
        Generate positive coaching narrative for good games.
        
        Structure:
        - Intent: Acknowledge good approach
        - Validation: What went right (theme-specific)
        - Stability: Position control observation
        - Teaching: Reinforce good habits
        - Rule: Anchor for continuation
        - Theme tie: Connect to focus
        """
        # Intent - acknowledge good approach
        intent = self._select_non_repetitive(POSITIVE_INTENT)
        
        # Validation - theme-specific what went right
        theme_key = active_theme if active_theme in VALIDATION_TEMPLATES else "default"
        validation = self._select_non_repetitive(VALIDATION_TEMPLATES[theme_key])
        
        # Stability insight
        stability = self._select_non_repetitive(STABILITY_TEMPLATES)
        
        # Teaching - reinforce good habits
        teaching_key = active_theme if active_theme in POSITIVE_TEACHING else "default"
        teaching = self._select_non_repetitive(POSITIVE_TEACHING[teaching_key])
        
        # Rule - continuation anchor
        rule = "Keep this discipline in your next games."
        
        # Theme reinforcement with positive framing
        theme_line = None
        if active_theme:
            theme_line = f"This aligns with your focus: {active_theme.replace('_', ' ')}."
        
        # Add streak acknowledgment if applicable
        if good_game_streak >= 2:
            streak_line = self._select_non_repetitive(STREAK_ACKNOWLEDGMENT)
            teaching = f"{teaching} {streak_line}"
        
        components = NarrativeComponents(
            intent_mirror_line=intent,
            thinking_break_line=validation,  # Repurposed for validation
            position_consequence_line=stability,  # Repurposed for stability
            teaching_line=teaching,
            rule_line=rule,
            theme_reinforcement_line=theme_line
        )
        
        # High confidence for positive coaching
        confidence = 0.9
        
        return components, NarrativeStrategy.POSITIVE_COACHING.value, confidence
    
    def _determine_strategy(self, selection_reason: str) -> NarrativeStrategy:
        """Map selection reason to narrative strategy"""
        mapping = {
            "pattern_event": NarrativeStrategy.PATTERN_COACHING,
            "turning_point": NarrativeStrategy.TURNING_POINT_COACHING,
            "tactical_error": NarrativeStrategy.TACTICAL_COACHING,
            "missed_mate": NarrativeStrategy.MATE_ALERT,
            "advantage_squander": NarrativeStrategy.TURNING_POINT_COACHING,
        }
        return mapping.get(selection_reason, NarrativeStrategy.TACTICAL_COACHING)
    
    def _generate_intent(self, move: Dict, context: Dict) -> str:
        """Generate intent mirror line"""
        # Infer intent from position context
        state_before = context.get("state_before", "")
        eval_before = context.get("eval_before", 0)
        
        if eval_before > 150:
            category = "attack"
        elif eval_before < -100:
            category = "defend"
        elif context.get("momentum_shift"):
            category = "simplify"
        else:
            category = "default"
        
        templates = INTENT_TEMPLATES.get(category, INTENT_TEMPLATES["default"])
        return self._select_non_repetitive(templates)
    
    def _generate_break(self, move: Dict, strategy: NarrativeStrategy) -> str:
        """Generate thinking break line"""
        cognitive_gap = move.get("cognitive_gap", "")
        
        # Map cognitive gap to break category
        if "THREAT" in cognitive_gap.upper() or "threat" in cognitive_gap.lower():
            category = "threat_missed"
        elif "CALCULATION" in cognitive_gap.upper() or "calculation" in cognitive_gap.lower():
            category = "calculation_short"
        elif strategy == NarrativeStrategy.PATTERN_COACHING:
            category = "pattern_repeat"
        elif "POSITION" in cognitive_gap.upper():
            category = "position_read"
        else:
            category = "default"
        
        templates = BREAK_TEMPLATES.get(category, BREAK_TEMPLATES["default"])
        return self._select_non_repetitive(templates)
    
    def _generate_consequence(
        self,
        move: Dict,
        strategy: NarrativeStrategy,
        context: Dict
    ) -> str:
        """Generate position consequence line"""
        threat = move.get("threat")
        best_move = move.get("best_move", "")
        played_move = move.get("move", "")
        pv_best = move.get("pv_after_best", [])
        
        if strategy == NarrativeStrategy.MATE_ALERT:
            # Mate consequence
            if pv_best and len(pv_best) >= 2:
                line = " ".join(pv_best[:3])
                return f"After {line}, it was mate."
            return "A forced mate was available."
        
        if threat:
            # Tactical consequence with threat
            template = random.choice(CONSEQUENCE_TEMPLATES["tactical"])
            return template.format(
                played=played_move or "the move",
                threat=threat,
                best=best_move or "another move"
            )
        
        if context.get("result_flipped"):
            return "This changed the game completely."
        
        if context.get("advantage_lost"):
            return "The advantage slipped away after this."
        
        # Default consequence
        templates = CONSEQUENCE_TEMPLATES["default"]
        return self._select_non_repetitive(templates)
    
    def _generate_teaching(self, move: Dict, strategy: NarrativeStrategy) -> str:
        """Generate teaching line"""
        cognitive_gap = move.get("cognitive_gap", "").lower()
        
        if "threat" in cognitive_gap:
            category = "threat_verification"
        elif "calculation" in cognitive_gap:
            category = "calculation"
        elif strategy == NarrativeStrategy.TURNING_POINT_COACHING:
            category = "conversion"
        elif strategy == NarrativeStrategy.MATE_ALERT:
            category = "mate_awareness"
        else:
            category = "default"
        
        templates = TEACHING_TEMPLATES.get(category, TEACHING_TEMPLATES["default"])
        return self._select_non_repetitive(templates)
    
    def _generate_rule(self, move: Dict, strategy: NarrativeStrategy) -> str:
        """Generate actionable rule line"""
        cognitive_gap = move.get("cognitive_gap", "").lower()
        coaching_focus = move.get("coaching_focus", "")
        
        # If we have a specific coaching focus, use it
        if coaching_focus and len(coaching_focus) > 10:
            return coaching_focus
        
        # Otherwise select from templates
        if "threat" in cognitive_gap:
            category = "threat_scan"
        elif "calculation" in cognitive_gap:
            category = "calculation_depth"
        elif "hanging" in cognitive_gap or "piece" in cognitive_gap:
            category = "piece_safety"
        elif strategy == NarrativeStrategy.TURNING_POINT_COACHING:
            category = "patience"
        else:
            category = "default"
        
        templates = RULE_TEMPLATES.get(category, RULE_TEMPLATES["default"])
        return self._select_non_repetitive(templates)
    
    def _select_non_repetitive(self, templates: List[str]) -> str:
        """Select a template that hasn't been used recently"""
        # Filter out recently used sentences
        available = [t for t in templates if t not in self.recent_sentences]
        
        if not available:
            available = templates  # Fall back if all used
        
        selected = random.choice(available)
        return selected
    
    def _calculate_confidence(self, move: Dict, context: Dict) -> float:
        """Calculate how confident we are in this explanation"""
        confidence = 1.0
        
        # Lower confidence if context is unclear
        gap_confidence = move.get("gap_confidence", 0.5)
        confidence *= (0.5 + gap_confidence * 0.5)
        
        # Higher confidence for clear position changes
        if context.get("result_flipped"):
            confidence = min(confidence + 0.2, 1.0)
        
        # Lower if no PV data
        if not move.get("pv_after_played") and not move.get("pv_after_best"):
            confidence *= 0.8
        
        return round(confidence, 2)


class ToneRenderer:
    """
    Adjusts narrative components based on user's maturity level.
    
    Same components → different delivery.
    """
    
    # Tone modifiers by maturity level
    TONE_CONFIGS = {
        ToneProfile.NOVICE: {
            "include_all_lines": True,
            "soften_break": True,
            "expand_teaching": True,
            "add_encouragement": True,
        },
        ToneProfile.DEVELOPING: {
            "include_all_lines": True,
            "soften_break": False,
            "expand_teaching": False,
            "add_encouragement": False,
        },
        ToneProfile.DISCIPLINED: {
            "include_all_lines": False,  # Skip some lines
            "soften_break": False,
            "expand_teaching": False,
            "add_encouragement": False,
        },
        ToneProfile.ADVANCED: {
            "include_all_lines": False,
            "soften_break": False,
            "expand_teaching": False,
            "add_encouragement": False,
        }
    }
    
    def render(
        self,
        components: NarrativeComponents,
        maturity_level: str
    ) -> str:
        """
        Assemble final text from components based on tone.
        
        Args:
            components: Structured narrative components
            maturity_level: User's behavioral maturity
            
        Returns:
            Assembled coaching text
        """
        try:
            profile = ToneProfile(maturity_level)
        except ValueError:
            profile = ToneProfile.DEVELOPING
        
        config = self.TONE_CONFIGS.get(profile, self.TONE_CONFIGS[ToneProfile.DEVELOPING])
        
        lines = []
        
        # Intent (always included)
        lines.append(components.intent_mirror_line)
        
        # Break (soften for novice)
        break_line = components.thinking_break_line
        if config["soften_break"] and break_line:
            break_line = break_line.replace("But ", "However, ")
            break_line = break_line.replace("didn't", "may not have")
        lines.append(break_line)
        
        # Consequence (skip for advanced if short)
        if config["include_all_lines"] or len(components.position_consequence_line) > 30:
            lines.append(components.position_consequence_line)
        
        # Teaching (expand for novice)
        if config["include_all_lines"]:
            lines.append(components.teaching_line)
        
        # Rule (always included)
        lines.append(components.rule_line)
        
        # Theme reinforcement
        if components.theme_reinforcement_line:
            lines.append(components.theme_reinforcement_line)
        
        # Add encouragement for novice
        if config["add_encouragement"]:
            lines.append("This gets easier with practice.")
        
        # Filter empty lines
        lines = [l for l in lines if l and l.strip()]
        
        return " ".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_coaching_narrative(
    selected_move: Dict,
    selection_reason: str,
    position_context: Dict,
    maturity_level: str = "Developing",
    active_theme: str = None,
    recent_sentences: List[str] = None,
    max_crs_score: float = None,
    good_game_streak: int = 0
) -> Dict:
    """
    Generate complete coaching narrative with tone adjustment.
    
    Args:
        selected_move: Critical move data
        selection_reason: Why selected (pattern_event, tactical_error, no_critical_moves, etc.)
        position_context: Position state before/after
        maturity_level: User's behavioral maturity
        active_theme: Current coaching theme
        recent_sentences: Recently used sentences (for anti-repetition)
        max_crs_score: Maximum CRS in game (for positive coaching trigger)
        good_game_streak: Consecutive good games count
    
    Returns:
        {
            "narrative_components": {...},
            "narrative_strategy": "...",
            "explanation_confidence": 0.85,
            "assembled_text": "...",
            "tone_profile_used": "..."
        }
    """
    engine = CoachNarrativeEngine(recent_sentences or [])
    
    components, strategy, confidence = engine.generate_narrative(
        selected_move=selected_move,
        selection_reason=selection_reason,
        position_context=position_context,
        maturity_level=maturity_level,
        active_theme=active_theme,
        max_crs_score=max_crs_score,
        good_game_streak=good_game_streak
    )
    
    renderer = ToneRenderer()
    assembled = renderer.render(components, maturity_level)
    
    return {
        "narrative_components": components.to_dict(),
        "narrative_strategy": strategy,
        "explanation_confidence": confidence,
        "assembled_text": assembled,
        "tone_profile_used": maturity_level
    }
