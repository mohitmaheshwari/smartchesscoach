"""
Chess Brain - Template System
==============================

Explanation templates with multiple variations per pattern.
Supports all teaching modes with randomized selection to avoid repetition.
"""

import random
from typing import Dict, Any, Optional, List
from ..enums import TeachingMode

from .tactical_patterns import get_tactical_template
from .strategic_concepts import get_strategic_template
from .mistake_corrections import get_mistake_template
from .reinforcement import get_reinforcement_template
from .opening_guidance import get_opening_template
from .endgame_technique import get_endgame_template


def get_template(
    teaching_mode: TeachingMode,
    pattern_or_concept: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """
    Get explanation template for a teaching mode and pattern.
    
    Args:
        teaching_mode: Which teaching mode to use
        pattern_or_concept: Specific pattern/concept name
        variables: Template variables (piece names, squares, etc.)
        variation: Specific variation index (None = random)
    
    Returns:
        Dict with keys: main_insight, explanation, why_section, next_idea, socratic_question
    """
    
    if teaching_mode == TeachingMode.TACTICAL_PATTERN_TEACHING:
        return get_tactical_template(pattern_or_concept, variables, variation)
    
    elif teaching_mode == TeachingMode.STRATEGIC_CONCEPT_TEACHING:
        return get_strategic_template(pattern_or_concept, variables, variation)
    
    elif teaching_mode == TeachingMode.IMMEDIATE_MISTAKE_CORRECTION:
        return get_mistake_template(pattern_or_concept, variables, variation)
    
    elif teaching_mode in [TeachingMode.POSITIVE_REINFORCEMENT, TeachingMode.HABIT_BREAKTHROUGH]:
        return get_reinforcement_template(teaching_mode, pattern_or_concept, variables, variation)
    
    elif teaching_mode == TeachingMode.OPENING_GUIDANCE:
        return get_opening_template(pattern_or_concept, variables, variation)
    
    elif teaching_mode == TeachingMode.ENDGAME_TECHNIQUE:
        return get_endgame_template(pattern_or_concept, variables, variation)
    
    # Fallback for unknown modes
    return {
        "main_insight": variables.get("main_insight", "Let's look at this position."),
        "explanation": variables.get("explanation", ""),
        "why_section": None,
        "next_idea": "Keep analyzing the position.",
        "socratic_question": None
    }


def render_template(template: str, variables: Dict[str, Any]) -> str:
    """
    Render a template string with variables.
    Simple {{variable}} replacement.
    """
    result = template
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value))
    return result


def select_variation(variations: List[Any], variation_index: Optional[int] = None) -> Any:
    """
    Select a variation from a list.
    If variation_index is None, select randomly.
    """
    if not variations:
        return None
    
    if variation_index is not None:
        return variations[variation_index % len(variations)]
    
    return random.choice(variations)
