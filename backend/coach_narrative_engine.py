"""
Coach Narrative Engine - Structured Explanation Generator

Transforms structured coaching data into human-like explanations
using a deterministic template system with tone adjustment.

Pipeline:
    selected_moment + context → narrative_strategy
                              → structured_components
                              → tone_adjustment (Step 7: StyleDirective)
                              → assembled_text

This is NOT an LLM generator. It's a coaching grammar system.

Key principle: Store structure, render text.

Step 7: Adaptive Teaching Style
- Same truth, different delivery
- StyleDirective controls sentence count, component visibility, tone
- No changes to analysis or lesson selection
"""

import logging
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Step 7: Import teaching style service
from coach_state.teaching_style_service import (
    StyleDirective,
    get_style_directive,
    adjust_for_trend,
    get_component_list,
    enforce_sentence_limit,
    maturity_to_tier,
    detect_trend,
    get_palette_phrase,
    get_lesson_aware_cue,
    MaturityTier,
    StrategyType,
)

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
# NOTE: Positive coaching triggers when:
#   - max_CRS < threshold AND no result_flipped AND no advantage_lost AND blunders == 0
# This means "no meaningful learning interruption occurred"
POSITIVE_CRS_THRESHOLD = {
    "Novice": 150,      # More forgiving - novice games naturally have small issues
    "Developing": 100,  # Moderate
    "Disciplined": 60,  # Higher standard
    "Advanced": 40      # Very high standard
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
# Step 7 Fix: Removed filler phrases ("However, there was a problem", "held a surprise")
BREAK_TEMPLATES = {
    "threat_missed": [
        "But you didn't check what they could do first.",
        "Their forcing reply was available.",
        "Opponent had a forcing move you missed.",
    ],
    "calculation_short": [
        "But you stopped calculating one move too soon.",
        "The sequence wasn't calculated fully.",
        "One more move would have shown the problem.",
    ],
    "position_read": [
        "But the position required a different approach.",
        "The structure demanded something different.",
        "The dynamics were different than expected.",
    ],
    "pattern_repeat": [
        "This is a pattern appearing in your games.",
        "This thinking error has shown up before.",
        "The same type of oversight happened recently.",
    ],
    "default": [
        "A forcing reply was missed.",
        "The opponent's response wasn't calculated.",
        "There was a forcing move available.",
    ]
}

# Consequence templates - HABIT-FOCUSED, not engine-like
# Avoid specific moves like "Bxb6 wins" - instead focus on what to CHECK
CONSEQUENCE_TEMPLATES = {
    "tactical": [
        "There was a forcing move you missed.",
        "The position had hidden tactics.",
        "A combination was available.",
    ],
    "positional": [
        "Your position became passive.",
        "The structure turned against you.",
        "Opponent gained lasting pressure.",
    ],
    "tempo": [
        "You lost important time.",
        "The initiative switched sides.",
        "Opponent took over the game.",
    ],
    "mate": [
        "There was a forced checkmate.",
        "A winning attack was available.",
        "The king was vulnerable.",
    ],
    "advantage_lost": [
        "The advantage slipped away.",
        "The winning position became unclear.",
        "The position needed more care.",
    ],
    "default": [
        "The position needed extra attention.",
        "This was a critical moment.",
        "More time was needed here.",
    ]
}

# Teaching templates - underlying principle (Fix 3: Expanded to 5-7 variants)
TEACHING_TEMPLATES = {
    "threat_verification": [
        "Always verify opponent threats before committing.",
        "Forcing moves must be checked first.",
        "Defense comes before attack.",
        "The opponent's possibilities were underestimated.",
        "Their counterplay wasn't factored in.",
        "Every move should ask: What can they do now?",
    ],
    "calculation": [
        "Calculate one move deeper than feels necessary.",
        "Complete the sequence before moving.",
        "Check the opponent's best reply.",
        "The forcing line wasn't calculated to completion.",
        "This required calculating until the position settled.",
        "Deeper calculation would have revealed the issue.",
    ],
    "conversion": [
        "When ahead, simplify carefully.",
        "Winning positions require patience.",
        "Don't attack when consolidation wins.",
        "The position called for consolidation, not action.",
        "In better positions, reduce complexity first.",
        "The advantage needed protection, not expansion.",
    ],
    "defense": [
        "Hold the position before counterattacking.",
        "Defensive moves can be the strongest.",
        "Patience in defense often pays off.",
        "Defense creates attacking opportunities.",
        "Solid defense frustrates aggressive opponents.",
    ],
    "mate_awareness": [
        "In winning positions, check for forcing finishes.",
        "Mate patterns should be scanned actively.",
        "When attacking, calculate to the end.",
        "The winning combination was available.",
        "Forcing sequences lead to mates when ahead.",
    ],
    "default": [
        "Slow down at critical moments.",
        "Double-check before committing.",
        "The position deserved more attention.",
        "This moment required more careful thinking.",
        "Critical positions need extra time.",
        "The situation called for deeper thought.",
    ]
}

# Rule templates - actionable takeaway (Fix 3: Expanded to 5-7 variants)
RULE_TEMPLATES = {
    "threat_scan": [
        "Before YOUR move, check what THEY can do.",
        "Scan checks-captures-threats before committing.",
        "Ask: What's their best reply?",
        "Always consider opponent's forcing moves first.",
        "Check their active pieces before moving yours.",
        "Anticipate their response before you act.",
    ],
    "calculation_depth": [
        "Calculate one move further than usual.",
        "Ask: Then what? after every move.",
        "Don't stop until the position is quiet.",
        "Extend calculation through forcing sequences.",
        "Keep calculating until no forcing moves remain.",
        "Push through the uncomfortable depth.",
    ],
    "piece_safety": [
        "Check if the piece is safe on its new square.",
        "Count attackers vs defenders before moving.",
        "Undefended pieces cause problems.",
        "Every piece needs a defender or escape square.",
        "Loose pieces invite tactics.",
        "Verify piece safety before and after each move.",
    ],
    "conversion": [
        "When winning, trade pieces not pawns.",
        "Simplify when ahead materially.",
        "No need to attack — just maintain.",
        "Reduce complexity when you're better.",
        "Protect your advantage before expanding it.",
    ],
    "patience": [
        "Improve your worst piece first.",
        "Don't rush when the position is unclear.",
        "Small improvements beat forcing moves.",
        "Patience prevents premature action.",
        "When unsure, strengthen your position.",
    ],
    "default": [
        "At critical moments, check forcing moves first.",
        "Check opponent's forcing replies before committing.",
        "At turning points, slow down and calculate.",
        "Critical positions demand extra attention.",
        "Check forcing moves before deciding.",
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


# =============================================================================
# MEMORY-AWARE NARRATIVE MODIFICATIONS (Step 5)
# =============================================================================
# Memory influences phrasing in 4 CONTROLLED ways ONLY:
# 1. Lesson cooldown phrasing
# 2. Pattern trend phrasing
# 3. Milestone acknowledgment
# 4. Theme evolution phrasing

# Cooldown modifications - when lesson was recently taught
COOLDOWN_RULE_MODIFICATIONS = [
    "You've seen this idea recently — apply it more consistently.",
    "We've covered this. Now it's about execution.",
    "This is familiar territory. Focus on applying it.",
    "You know the principle — it's practice time now.",
]

# Pattern trend modifications for break/teaching lines
# NOTE: These are polarity-aware based on the type of pattern
PATTERN_TREND_MODIFIERS = {
    # For NEGATIVE patterns (mistakes) - these mean pattern is recurring badly
    "improving": [
        "This mistake is appearing less often now.",
        "This pattern is improving in your games.",
        "You're making progress on this.",
    ],
    "persistent": [
        "This continues to appear.",
        "This pattern persists in your games.",
        "We keep seeing this.",
    ],
    "recurring": [
        "This is appearing more often recently.",
        "This pattern needs attention.",
        "This is recurring more frequently.",
    ],
    "stable": []  # No modification for stable patterns
}

# For POSITIVE patterns (good habits) - these track discipline
POSITIVE_TREND_MODIFIERS = {
    "improving": [
        "This discipline is becoming natural.",
        "This good habit is settling in.",
        "Your consistency here is growing.",
    ],
    "persistent": [
        "This stability continues.",
        "Your discipline here is holding.",
        "This solid pattern persists.",
    ],
    "recurring": [
        "This stability is building.",
        "Your focus here is intensifying.",
        "This positive pattern is strengthening.",
    ],
    "stable": []
}

# Milestone acknowledgments (rare, earned)
MILESTONE_CELEBRATIONS = {
    "first_clean_game": [
        "This was a clean game. That's a milestone.",
        "First game without major errors — that matters.",
    ],
    "first_three_streak": [
        "That's three stable games in a row.",
        "Three games without breakdown — real progress.",
    ],
    "first_five_streak": [
        "Five games of discipline. That's rare.",
        "Five-game streak shows real control.",
    ],
    "lesson_mastery": [
        "This pattern hasn't appeared in 10 games — you've internalized it.",
        "You've moved past this lesson. It's becoming instinct.",
    ],
}

# Theme evolution phrasing based on games on theme
THEME_EVOLUTION_PHRASES = {
    "early": "We're focusing on {theme}.",
    "mid": "You've been working on {theme}.",
    "late": "{theme} is becoming more natural for you.",
    "mastery": "You applied {theme} instinctively.",
}


def apply_memory_modifications(
    components: 'NarrativeComponents',
    memory_context: Optional[Dict] = None,
    games_on_theme: int = 0,
    active_theme: str = None,
    is_positive_coaching: bool = False
) -> Tuple['NarrativeComponents', int]:
    """
    Apply memory-based modifications to narrative components.
    
    GUARDRAILS:
    - Max 2 memory-based modifications per explanation
    - Milestone suppression if mentioned < 2 games ago
    - Memory influences PHRASING only, not analysis
    
    Args:
        components: Original narrative components
        memory_context: MemoryContext.to_dict() or None
        games_on_theme: How many games on current theme
        active_theme: Current theme name
        is_positive_coaching: Whether this is positive (clean game) or corrective coaching
        
    Returns:
        (modified_components, modification_count)
    """
    if not memory_context:
        return components, 0
    
    modification_count = 0
    MAX_MODIFICATIONS = 2
    
    # Work with mutable copies
    rule_line = components.rule_line
    teaching_line = components.teaching_line
    theme_line = components.theme_reinforcement_line
    
    # 1. Lesson cooldown phrasing
    if (memory_context.get("is_lesson_on_cooldown") and 
        modification_count < MAX_MODIFICATIONS):
        # Replace rule line with cooldown-aware version
        rule_line = random.choice(COOLDOWN_RULE_MODIFICATIONS)
        modification_count += 1
    
    # 2. Pattern trend phrasing (polarity-aware)
    # Fix 2: Use different modifiers for positive vs negative patterns
    pattern_trend = memory_context.get("lesson_trend", "stable")
    if pattern_trend != "stable" and modification_count < MAX_MODIFICATIONS:
        # Select correct modifier set based on coaching type
        if is_positive_coaching:
            modifiers = POSITIVE_TREND_MODIFIERS.get(pattern_trend, [])
        else:
            modifiers = PATTERN_TREND_MODIFIERS.get(pattern_trend, [])
        
        if modifiers:
            trend_phrase = random.choice(modifiers)
            teaching_line = f"{trend_phrase} {teaching_line}"
            modification_count += 1
    
    # 3. Milestone acknowledgment (rare)
    active_milestone = memory_context.get("active_milestone")
    if (active_milestone and 
        active_milestone in MILESTONE_CELEBRATIONS and
        modification_count < MAX_MODIFICATIONS):
        # Add milestone to teaching line
        celebration = random.choice(MILESTONE_CELEBRATIONS[active_milestone])
        teaching_line = f"{teaching_line} {celebration}"
        modification_count += 1
    
    # 4. Theme evolution phrasing
    if (active_theme and 
        theme_line and
        modification_count < MAX_MODIFICATIONS):
        # Determine evolution stage
        if games_on_theme < 5:
            stage = "early"
        elif games_on_theme < 15:
            stage = "mid"
        elif games_on_theme < 30:
            stage = "late"
        else:
            stage = "mastery"
        
        # Apply stage-appropriate theme phrasing
        theme_display = active_theme.replace("_", " ").lower()
        theme_line = THEME_EVOLUTION_PHRASES[stage].format(theme=theme_display)
        modification_count += 1
    
    # Create modified components
    modified = NarrativeComponents(
        intent_mirror_line=components.intent_mirror_line,
        thinking_break_line=components.thinking_break_line,
        position_consequence_line=components.position_consequence_line,
        teaching_line=teaching_line,
        rule_line=rule_line,
        theme_reinforcement_line=theme_line
    )
    
    return modified, modification_count


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
        good_game_streak: int = 0,
        blunders_count: int = 0
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
            blunders_count: Number of blunders in the game
            
        Returns:
            (NarrativeComponents, narrative_strategy, explanation_confidence)
        """
        # Check if this should be positive coaching
        # Positive coaching = "no meaningful learning interruption occurred"
        threshold = POSITIVE_CRS_THRESHOLD.get(maturity_level, 100)
        
        # Conditions for positive coaching:
        # 1. No critical moves OR max CRS below threshold
        # 2. No result-flipping moments
        # 3. No advantage lost
        # 4. No blunders
        no_critical = selection_reason == "no_critical_moves"
        low_crs = max_crs_score is not None and max_crs_score < threshold
        no_result_flip = not position_context.get("result_flipped", False)
        no_advantage_lost = not position_context.get("advantage_lost", False)
        no_blunders = blunders_count == 0
        
        is_positive = (
            (no_critical or low_crs) and
            no_result_flip and
            no_advantage_lost and
            no_blunders
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
        """
        Generate intent mirror line.
        
        Step 6 Enhancement: If intent_sentence is available (from intent recognition
        and calibration), use it directly. This provides specific, calibrated
        intent phrasing like "You tried to attack, but the timing was early."
        
        Otherwise, fall back to template-based generic intent mirroring.
        """
        # Step 6: Use calibrated intent_sentence if available
        intent_sentence = move.get("intent_sentence")
        if intent_sentence:
            # The calibrated sentence already contains:
            # - Intent type recognition (ATTACKING, DEFENDING, etc.)
            # - Quality calibration (excellent, good, premature, etc.)
            # - Pressure-aware phrasing (accounts for winning/losing context)
            return intent_sentence
        
        # Fallback: Infer intent from position context (legacy behavior)
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
            # Mate consequence - NO engine lines, just habit-focused
            return "A forced checkmate was available. Build the habit: check ALL captures in winning positions."
        
        if threat:
            # Tactical consequence - habit-focused, not engine-like
            templates = CONSEQUENCE_TEMPLATES["tactical"]
            return self._select_non_repetitive(templates)
        
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
        """Select a template that hasn't been used recently using similarity matching"""
        # Filter using similarity matching (not exact string)
        available = []
        for t in templates:
            is_similar = False
            for recent in self.recent_sentences:
                # Check if first 20 chars match (pattern similarity)
                if len(t) >= 20 and len(recent) >= 20:
                    if t[:20].lower() == recent[:20].lower():
                        is_similar = True
                        break
                # Also check exact match
                if t == recent:
                    is_similar = True
                    break
            if not is_similar:
                available.append(t)
        
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
    Assembles narrative components based on user's maturity level.
    
    Step 7: Now uses StyleDirective for precise control over:
    - Sentence count (hard cap)
    - Component visibility
    - Encouragement inclusion
    - Firmness tone
    
    Same truth → different delivery.
    """
    
    def render(
        self,
        components: NarrativeComponents,
        maturity_level: str,
        strategy: str = "PATTERN_COACHING",
        game_id: str = "",
        lesson_key: str = "",
        trend: str = "stable",
        lesson_repeated: bool = False,
    ) -> str:
        """
        Assemble final text from components based on StyleDirective.
        
        Step 7: Uses StyleDirective for adaptive teaching.
        
        Args:
            components: Structured narrative components
            maturity_level: User's behavioral maturity
            strategy: Coaching strategy (PATTERN, TACTICAL, etc.)
            game_id: For deterministic palette selection
            lesson_key: For palette rotation
            trend: improving/stable/declining
            lesson_repeated: Is this lesson repeating?
            
        Returns:
            Assembled coaching text with tier-appropriate delivery
        """
        # Convert to typed tier
        tier = maturity_to_tier(maturity_level)
        
        # Map strategy string to StrategyType
        strategy_map = {
            "pattern_coaching": "PATTERN_COACHING",
            "tactical_coaching": "TACTICAL_COACHING",
            "turning_point_coaching": "TURNING_POINT_COACHING",
            "positive_coaching": "POSITIVE_COACHING",
            "mate_alert": "TACTICAL_COACHING",  # Treat mate as tactical
        }
        strategy_type = strategy_map.get(strategy.lower(), "PATTERN_COACHING")
        
        # Get StyleDirective
        style = get_style_directive(tier, strategy_type, game_id, lesson_key)
        
        # Apply trend-based strictness adjustment
        style = adjust_for_trend(style, trend, lesson_repeated)
        
        # Get component list for this strategy + tier
        component_order = get_component_list(strategy_type, tier)
        
        # Build lines following the component order
        lines = []
        
        for comp in component_order:
            line = self._get_component_line(comp, components, style, game_id, lesson_key)
            if line:
                lines.append(line)
        
        # Filter empty lines
        lines = [line for line in lines if line and line.strip()]
        
        # HARD CAP: Enforce sentence limit from StyleDirective
        lines = enforce_sentence_limit(lines, style.max_sentences)
        
        return " ".join(lines)
    
    def _get_component_line(
        self,
        component: str,
        components: NarrativeComponents,
        style: StyleDirective,
        game_id: str,
        lesson_key: str,
    ) -> Optional[str]:
        """
        Get the line for a specific component.
        
        Maps component names to NarrativeComponents fields and applies styling.
        """
        if component == "intent":
            if not style.include_intent:
                return None
            return components.intent_mirror_line
        
        elif component == "break_point":
            line = components.thinking_break_line
            if line and style.firmness == "soft":
                # Soften for Novice - but don't add filler
                line = line.replace("But you ", "You ")
                line = line.replace("didn't", "may not have")
            return line
        
        elif component == "consequence":
            if not style.include_consequence:
                return None
            # Step 7 Fix: Remove trailing "after this" for cleaner output
            consequence = components.position_consequence_line
            if consequence:
                consequence = consequence.replace(" after this", "")
                consequence = consequence.replace("After this, ", "")
            return consequence
        
        elif component == "pattern_reminder":
            # Use teaching_line as pattern reminder
            return components.teaching_line if not style.reduce_fluff else None
        
        elif component == "rule":
            if not style.include_rule:
                return None
            # Step 7 Fix: For Advanced tier with firm tone, make rule sharper
            rule = components.rule_line
            if style.firmness == "firm" and style.tier == "Advanced":
                # Remove motivational verbs for Advanced
                rule = rule.replace("Slow down at ", "At ")
                rule = rule.replace("Take more time on ", "")
                rule = rule.replace("Double-check ", "Check ")
            return rule
        
        elif component == "encouragement":
            if not style.include_encouragement:
                return None
            return get_palette_phrase(
                style.wording_palette_id,
                "encouragement",
                hash(game_id) % 2
            )
        
        elif component == "example_cue":
            if not style.include_example_cue:
                return None
            # Step 7 Fix: Use lesson-aware cue for specificity
            return get_lesson_aware_cue(
                style.wording_palette_id,
                lesson_key,
                hash(lesson_key) % 2
            )
        
        elif component == "what_changed":
            # Use break line for "what changed" in turning point
            return components.thinking_break_line
        
        elif component == "why_it_mattered":
            return components.position_consequence_line
        
        elif component == "what_went_right":
            # For positive coaching - use teaching line
            return components.teaching_line
        
        elif component == "stability_insight":
            # Use rule line for stability insight
            return components.rule_line
        
        # Theme reinforcement (not in standard component lists)
        elif component == "theme_reinforcement":
            return components.theme_reinforcement_line
        
        return None
    
    def render_advanced_minimal(
        self,
        components: NarrativeComponents,
    ) -> str:
        """
        Ultra-minimal rendering for Advanced tier.
        
        Format: "Consequence. Rule."
        No intent, no encouragement, no fluff.
        """
        lines = []
        
        if components.position_consequence_line:
            lines.append(components.position_consequence_line)
        
        if components.rule_line:
            lines.append(components.rule_line)
        
        lines = [line for line in lines if line and line.strip()]
        return " ".join(lines[:2])  # Hard cap at 2


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
    good_game_streak: int = 0,
    blunders_count: int = 0,
    memory_context: Dict = None,
    games_on_theme: int = 0,
    game_id: str = "",
    lesson_key: str = "",
    recent_accuracies: List[float] = None,
    lesson_repeated: bool = False,
) -> Dict:
    """
    Generate complete coaching narrative with tone adjustment and memory awareness.
    
    Step 7: Now uses StyleDirective for adaptive teaching.
    
    Args:
        selected_move: Critical move data
        selection_reason: Why selected (pattern_event, tactical_error, no_critical_moves, etc.)
        position_context: Position state before/after
        maturity_level: User's behavioral maturity
        active_theme: Current coaching theme
        recent_sentences: Recently used sentences (for anti-repetition)
        max_crs_score: Maximum CRS in game (for positive coaching trigger)
        good_game_streak: Consecutive good games count
        blunders_count: Number of blunders in the game
        memory_context: MemoryContext.to_dict() for memory-aware modifications (Step 5)
        games_on_theme: How many games on current theme (for theme evolution phrasing)
        game_id: For deterministic palette selection (Step 7)
        lesson_key: For lesson tracking and palette rotation (Step 7)
        recent_accuracies: Recent game accuracies for trend detection (Step 7)
        lesson_repeated: Is this same lesson repeating? (Step 7)
    
    Returns:
        {
            "narrative_components": {...},
            "narrative_strategy": "...",
            "explanation_confidence": 0.85,
            "assembled_text": "...",
            "tone_profile_used": "...",
            "memory_modifications_applied": int,
            "style_directive_tier": str  # Step 7
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
        good_game_streak=good_game_streak,
        blunders_count=blunders_count
    )
    
    # Apply memory modifications (Step 5: Memory Continuity)
    # This influences PHRASING only, not analysis
    modifications_count = 0
    is_positive = strategy == "positive_coaching"
    if memory_context:
        components, modifications_count = apply_memory_modifications(
            components=components,
            memory_context=memory_context,
            games_on_theme=games_on_theme,
            active_theme=active_theme,
            is_positive_coaching=is_positive
        )
        if modifications_count > 0:
            logger.debug(f"Applied {modifications_count} memory modifications to narrative")
    
    # Step 7: Detect trend from recent accuracies
    trend = detect_trend(recent_accuracies or [])
    
    # Step 7: Render with StyleDirective
    renderer = ToneRenderer()
    assembled = renderer.render(
        components=components,
        maturity_level=maturity_level,
        strategy=strategy,
        game_id=game_id,
        lesson_key=lesson_key or active_theme or "",
        trend=trend,
        lesson_repeated=lesson_repeated,
    )
    
    # Get tier for reporting
    tier = maturity_to_tier(maturity_level)
    
    return {
        "narrative_components": components.to_dict(),
        "narrative_strategy": strategy,
        "explanation_confidence": confidence,
        "assembled_text": assembled,
        "tone_profile_used": maturity_level,
        "memory_modifications_applied": modifications_count,
        "style_directive_tier": tier,  # Step 7
    }
