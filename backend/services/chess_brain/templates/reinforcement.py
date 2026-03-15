"""
Reinforcement Templates
========================

Positive feedback and habit breakthrough celebration templates.
Encourages good moves and celebrates improvements.
"""

import random
from typing import Dict, Any, Optional
from ..enums import TeachingMode


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


def select_variation(variations: list, variation_index: Optional[int] = None):
    """
    Select a variation from a list.
    If variation_index is None, select randomly.
    """
    if not variations:
        return None
    
    if variation_index is not None:
        return variations[variation_index % len(variations)]
    
    return random.choice(variations)


# === POSITIVE REINFORCEMENT TEMPLATES ===

POSITIVE_TEMPLATES = [
    {
        "main_insight": "Excellent move! {{user_move}} is spot on.",
        "explanation": "{{reason}}. This shows strong {{skill_area}} understanding. You're finding the key moves in critical moments.",
        "why_section": None,
        "next_idea": "Keep up this level of play—you're thinking well.",
        "socratic_question": None
    },
    {
        "main_insight": "Great find with {{user_move}}!",
        "explanation": "That's exactly the right move. {{explanation}}. This is the kind of accuracy that wins games.",
        "why_section": None,
        "next_idea": "You're playing with good energy—maintain this focus.",
        "socratic_question": None
    },
    {
        "main_insight": "Perfect! {{user_move}} is the best move.",
        "explanation": "You found the key continuation. {{what_it_accomplishes}}. Strong players consistently find these moves.",
        "why_section": None,
        "next_idea": "Stay sharp—you're in a good rhythm.",
        "socratic_question": None
    },
    {
        "main_insight": "Well done! {{user_move}} keeps the advantage.",
        "explanation": "{{reason}}. You're maintaining your edge and not giving your opponent any chances. That's how you convert advantages.",
        "why_section": None,
        "next_idea": "Continue playing precisely—you're on the right track.",
        "socratic_question": None
    }
]


# === HABIT BREAKTHROUGH TEMPLATES ===

BREAKTHROUGH_TEMPLATES = [
    {
        "main_insight": "Breakthrough moment! You usually struggle with {{pattern_name}}, but you nailed it this time!",
        "explanation": "In the past, you've missed {{pattern_name}} patterns {{miss_count}} times. But here, you found {{user_move}}, which {{what_it_does}}. This is exactly the kind of improvement that shows you're growing as a player!",
        "why_section": "You've been working on recognizing {{pattern_name}}, and it's paying off. This pattern used to trip you up, but now you're seeing it clearly.",
        "next_idea": "This is a real milestone. Keep trusting your pattern recognition—it's getting stronger.",
        "socratic_question": None
    },
    {
        "main_insight": "Yes! You avoided your usual {{pattern_name}} mistake!",
        "explanation": "You've had trouble with {{pattern_name}} in previous games ({{miss_count}} times recently). But in this position, you played {{user_move}}, which shows you're learning to spot these patterns. That's growth!",
        "why_section": "Recognizing patterns that used to confuse you is one of the clearest signs of improvement. You're building stronger chess intuition.",
        "next_idea": "This pattern is becoming part of your instincts now. Celebrate this progress!",
        "socratic_question": None
    },
    {
        "main_insight": "Big improvement! You spotted the {{pattern_name}} this time!",
        "explanation": "{{pattern_name}} has been a recurring blind spot for you. But here, you found {{user_move}}, completely avoiding the trap. {{explanation}}. This is the kind of breakthrough that means your pattern recognition is evolving.",
        "why_section": "Every player has patterns they initially struggle with. Breaking through on a recurring weakness is one of the best feelings in chess improvement.",
        "next_idea": "You're conquering this pattern. Keep this up and it'll become second nature.",
        "socratic_question": None
    },
    {
        "main_insight": "Achievement unlocked! You've overcome your {{pattern_name}} weakness!",
        "explanation": "You used to miss {{pattern_name}} regularly ({{miss_count}} recent instances), but you just played {{user_move}}, which {{achievement_description}}. This is proof your training is working!",
        "why_section": "The gap between knowing a pattern intellectually and seeing it in your games can take time to bridge. You've just bridged it.",
        "next_idea": "Mark this moment—you've leveled up on {{pattern_name}} recognition.",
        "socratic_question": None
    }
]


# === GOOD MOVE TEMPLATES (Simple reinforcement) ===

GOOD_MOVE_TEMPLATES = [
    {
        "main_insight": "Good move! {{user_move}} is solid.",
        "explanation": "{{reason}}. This maintains your position and doesn't give your opponent any counterplay.",
        "why_section": None,
        "next_idea": "Keep finding good moves like this.",
        "socratic_question": None
    },
    {
        "main_insight": "Nice! {{user_move}} is a strong choice.",
        "explanation": "{{explanation}}. You're making sound decisions.",
        "why_section": None,
        "next_idea": "Stay focused on the position.",
        "socratic_question": None
    },
    {
        "main_insight": "Solid move. {{user_move}} keeps things under control.",
        "explanation": "{{reason}}. You're not giving away any chances.",
        "why_section": None,
        "next_idea": "Continue with this steady approach.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_reinforcement_template(
    teaching_mode: TeachingMode,
    pattern_or_quality: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for positive reinforcement or habit breakthrough."""
    
    if teaching_mode == TeachingMode.HABIT_BREAKTHROUGH:
        templates = BREAKTHROUGH_TEMPLATES
    elif variables.get("quality") == "excellent":
        templates = POSITIVE_TEMPLATES
    else:
        templates = GOOD_MOVE_TEMPLATES
    
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "Good move!",
            "explanation": "",
            "why_section": None,
            "next_idea": "Keep it up.",
            "socratic_question": None
        }
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
