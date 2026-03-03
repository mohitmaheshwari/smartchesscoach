"""
Teaching Style Service - Step 7: Adaptive Teaching Style

Determines delivery style based on user maturity tier.
Same truth, different delivery depth and tone.

Rules:
- Does NOT change analysis or lesson selection
- Only controls: sentence count, component visibility, tone, encouragement
- Deterministic: same inputs always produce same StyleDirective
"""

from dataclasses import dataclass, replace
from typing import Literal, Optional
import hashlib


# Type definitions
MaturityTier = Literal["Novice", "Developing", "Disciplined", "Advanced"]
FirmnessLevel = Literal["soft", "neutral", "firm"]
StrategyType = Literal[
    "PATTERN_COACHING",
    "TACTICAL_COACHING",
    "TURNING_POINT_COACHING",
    "POSITIVE_COACHING",
]
TrendType = Literal["improving", "stable", "declining"]


@dataclass(frozen=True)
class StyleDirective:
    """
    Controls how coaching content is delivered.
    
    Does NOT affect what is taught - only how it's presented.
    """
    tier: MaturityTier
    strategy: StrategyType
    
    # Sentence Control
    max_sentences: int                 # Hard cap on output length
    include_intent: bool               # Show intent_mirror_line?
    include_consequence: bool          # Show consequence line?
    include_rule: bool                 # Show rule_line?
    include_encouragement: bool        # Add encouragement sentence?
    include_example_cue: bool          # Add micro example cue (CCC etc.)
    
    # Tone Modulation
    firmness: FirmnessLevel            # soft | neutral | firm
    reduce_fluff: bool                 # Remove filler phrases?
    
    # Variant Control
    wording_palette_id: str            # Used to rotate template bank


# =============================================================================
# TIER DEFAULTS (Deterministic Rules - NOT suggestions)
# =============================================================================

TIER_DEFAULTS: dict[MaturityTier, dict] = {
    "Novice": {
        "max_sentences": 5,
        "include_intent": True,
        "include_consequence": True,
        "include_rule": True,
        "include_encouragement": True,
        "include_example_cue": True,
        "firmness": "soft",
        "reduce_fluff": False,
    },
    "Developing": {
        "max_sentences": 4,
        "include_intent": True,
        "include_consequence": True,
        "include_rule": True,
        "include_encouragement": False,
        "include_example_cue": True,
        "firmness": "neutral",
        "reduce_fluff": True,
    },
    "Disciplined": {
        "max_sentences": 3,
        "include_intent": True,
        "include_consequence": True,
        "include_rule": True,
        "include_encouragement": False,
        "include_example_cue": False,
        "firmness": "firm",
        "reduce_fluff": True,
    },
    "Advanced": {
        "max_sentences": 2,
        "include_intent": False,      # Skip intent entirely
        "include_consequence": True,
        "include_rule": True,
        "include_encouragement": False,
        "include_example_cue": False,
        "firmness": "firm",
        "reduce_fluff": True,
    },
}


# =============================================================================
# WORDING PALETTES (Rotation Without Chaos)
# =============================================================================

WORDING_PALETTES = {
    "neutral_1": {
        "encouragement": [
            "Keep building this habit.",
            "This will pay off over time.",
        ],
        "firm_cue": [
            "Execute.",
            "No excuses here.",
        ],
        "soft_cue": [
            "Take a breath before committing.",
            "Give the position one more look.",
        ],
        "example_cue": [
            "Scan checks-captures-threats first.",
            "Look for forcing moves before committing.",
        ],
    },
    "neutral_2": {
        "encouragement": [
            "You're developing the right instincts.",
            "Stay patient with this process.",
        ],
        "firm_cue": [
            "Fix this pattern.",
            "This must change.",
        ],
        "soft_cue": [
            "Slow down in these moments.",
            "One more look before you commit.",
        ],
        "example_cue": [
            "CCC scan before every decision.",
            "Checks, captures, threats — in that order.",
        ],
    },
    "neutral_3": {
        "encouragement": [
            "Trust the process.",
            "This habit will stick.",
        ],
        "firm_cue": [
            "Lock this in.",
            "No shortcuts.",
        ],
        "soft_cue": [
            "Pause and reassess.",
            "The position deserves another look.",
        ],
        "example_cue": [
            "Always check forcing replies first.",
            "What can opponent do to you?",
        ],
    },
}

PALETTE_IDS = list(WORDING_PALETTES.keys())


def get_palette_id(game_id: str, lesson_key: str = "") -> str:
    """
    Deterministic palette selection.
    Same game + lesson always gets same palette.
    """
    combined = f"{game_id}:{lesson_key}"
    hash_val = int(hashlib.md5(combined.encode()).hexdigest(), 16)
    return PALETTE_IDS[hash_val % len(PALETTE_IDS)]


def get_palette_phrase(palette_id: str, category: str, index: int = 0) -> str:
    """Get a phrase from the palette, with fallback."""
    palette = WORDING_PALETTES.get(palette_id, WORDING_PALETTES["neutral_1"])
    phrases = palette.get(category, [])
    if not phrases:
        return ""
    return phrases[index % len(phrases)]


# =============================================================================
# STYLE DIRECTIVE FACTORY
# =============================================================================

def get_style_directive(
    tier: MaturityTier,
    strategy: StrategyType,
    game_id: str = "",
    lesson_key: str = "",
) -> StyleDirective:
    """
    Create a StyleDirective for given tier and strategy.
    
    This is the primary factory function.
    """
    defaults = TIER_DEFAULTS.get(tier, TIER_DEFAULTS["Developing"])
    palette_id = get_palette_id(game_id, lesson_key)
    
    return StyleDirective(
        tier=tier,
        strategy=strategy,
        max_sentences=defaults["max_sentences"],
        include_intent=defaults["include_intent"],
        include_consequence=defaults["include_consequence"],
        include_rule=defaults["include_rule"],
        include_encouragement=defaults["include_encouragement"],
        include_example_cue=defaults["include_example_cue"],
        firmness=defaults["firmness"],
        reduce_fluff=defaults["reduce_fluff"],
        wording_palette_id=palette_id,
    )


# =============================================================================
# STRICTNESS SWITCH (Dynamic Override)
# =============================================================================

def adjust_for_trend(
    style: StyleDirective,
    trend: TrendType,
    lesson_repeated: bool,
) -> StyleDirective:
    """
    Dynamically adjust style based on recent performance.
    
    Rules:
    - declining + lesson_repeated → firmer tone, no encouragement
    - improving → add encouragement (even for Developing)
    
    This makes coach feel emotionally intelligent without being random.
    """
    # Rule 1: Declining + repeated lesson → firm override
    if trend == "declining" and lesson_repeated:
        return replace(
            style,
            firmness="firm",
            include_encouragement=False,
            reduce_fluff=True,
        )
    
    # Rule 2: Improving → add encouragement (even for Developing)
    if trend == "improving":
        # Only add encouragement for Novice/Developing tiers
        if style.tier in ("Novice", "Developing"):
            return replace(
                style,
                include_encouragement=True,
            )
    
    # No adjustment needed
    return style


# =============================================================================
# STRATEGY-SPECIFIC COMPONENT RULES
# =============================================================================

# Which components to include per strategy per tier
# Format: {strategy: {tier: [ordered component list]}}

STRATEGY_COMPONENTS: dict[StrategyType, dict[MaturityTier, list[str]]] = {
    "PATTERN_COACHING": {
        "Novice": ["intent", "consequence", "pattern_reminder", "rule", "encouragement"],
        "Developing": ["intent", "consequence", "pattern_reminder", "rule"],
        "Disciplined": ["intent", "consequence", "rule"],
        "Advanced": ["consequence", "rule"],
    },
    "TACTICAL_COACHING": {
        "Novice": ["intent", "break_point", "consequence", "rule", "encouragement"],
        "Developing": ["intent", "break_point", "consequence", "rule"],
        "Disciplined": ["intent", "consequence", "rule"],
        "Advanced": ["consequence", "rule"],
    },
    "TURNING_POINT_COACHING": {
        "Novice": ["intent", "what_changed", "why_it_mattered", "rule", "encouragement"],
        "Developing": ["intent", "what_changed", "why_it_mattered", "rule"],
        "Disciplined": ["intent", "what_changed", "rule"],
        "Advanced": ["what_changed", "rule"],
    },
    "POSITIVE_COACHING": {
        "Novice": ["intent", "what_went_right", "stability_insight", "rule", "encouragement"],
        "Developing": ["what_went_right", "stability_insight", "rule"],
        "Disciplined": ["what_went_right", "rule"],
        "Advanced": ["what_went_right"],  # No rule needed for positive
    },
}


def get_component_list(strategy: StrategyType, tier: MaturityTier) -> list[str]:
    """
    Get ordered list of components to include for this strategy + tier.
    """
    strategy_rules = STRATEGY_COMPONENTS.get(strategy, STRATEGY_COMPONENTS["PATTERN_COACHING"])
    return strategy_rules.get(tier, strategy_rules["Developing"])


def should_include_component(
    component: str,
    style: StyleDirective,
) -> bool:
    """
    Check if a specific component should be included based on StyleDirective.
    
    Maps component names to StyleDirective flags.
    """
    component_map = {
        "intent": style.include_intent,
        "consequence": style.include_consequence,
        "rule": style.include_rule,
        "encouragement": style.include_encouragement,
        "example_cue": style.include_example_cue,
        # These are always included if in component list
        "break_point": True,
        "pattern_reminder": True,
        "what_changed": True,
        "why_it_mattered": True,
        "what_went_right": True,
        "stability_insight": True,
    }
    return component_map.get(component, True)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def enforce_sentence_limit(lines: list[str], max_sentences: int) -> list[str]:
    """
    Hard cap on sentence count.
    No overflow allowed.
    """
    return lines[:max_sentences]


def maturity_to_tier(maturity_level: str) -> MaturityTier:
    """
    Convert maturity level string to MaturityTier.
    Handles various formats from the existing system.
    """
    level = maturity_level.lower().strip()
    
    if level in ("novice", "beginner", "new"):
        return "Novice"
    elif level in ("developing", "intermediate", "growing"):
        return "Developing"
    elif level in ("disciplined", "consistent", "solid"):
        return "Disciplined"
    elif level in ("advanced", "expert", "master"):
        return "Advanced"
    else:
        # Default to Developing for unknown levels
        return "Developing"


def detect_trend(
    recent_accuracies: list[float],
    window_size: int = 5,
) -> TrendType:
    """
    Detect performance trend from recent game accuracies.
    
    improving: average of recent > average of older
    declining: average of recent < average of older  
    stable: within 5% difference
    """
    if len(recent_accuracies) < 3:
        return "stable"
    
    # Take last window_size games
    recent = recent_accuracies[-window_size:]
    
    if len(recent) < 3:
        return "stable"
    
    # Compare first half vs second half
    mid = len(recent) // 2
    first_half = recent[:mid]
    second_half = recent[mid:]
    
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    
    diff_pct = (avg_second - avg_first) / max(avg_first, 1) * 100
    
    if diff_pct > 5:
        return "improving"
    elif diff_pct < -5:
        return "declining"
    else:
        return "stable"
