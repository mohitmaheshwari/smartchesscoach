"""
Endgame Technique Templates
===========================

Templates for endgame phase teaching.
Covers endgame principles, technique, and common patterns.
"""

import random
from typing import Dict, Any, Optional


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


# === ENDGAME PRINCIPLES TEMPLATES ===

ENDGAME_PRINCIPLE_TEMPLATES = [
    {
        "main_insight": "In the endgame, activate your king!",
        "explanation": "The king transforms from a liability in the middlegame to a powerful piece in the endgame. With fewer pieces on the board, there's less danger. Bring your king toward the center to support pawns, attack enemy pawns, or help deliver checkmate.",
        "why_section": "King activity often decides endgames. A centralized king can support passed pawns, blockade enemy pawns, or help coordinate with other pieces.",
        "next_idea": "March your king forward to help your pawns or restrict your opponent's pawns.",
        "socratic_question": "Can your king safely advance toward the action?"
    },
    {
        "main_insight": "Passed pawns must be pushed!",
        "explanation": "In the endgame, passed pawns become incredibly powerful. They tie down enemy pieces and create promotion threats. The general principle: push passed pawns (especially when they're far from the enemy king) and support them with your king and pieces.",
        "why_section": "Passed pawns are worth more in the endgame because there are fewer pieces to blockade or capture them.",
        "next_idea": "Advance your passed pawn when your opponent's king is far away or when you have good support.",
        "socratic_question": "What's stopping your passed pawn from advancing?"
    },
    {
        "main_insight": "Rook endgames: activity trumps material!",
        "explanation": "In rook endgames, an active rook (on the 7th rank, cutting off the enemy king, or attacking pawns) is often worth more than an extra pawn. Prioritize rook activity—get your rook to the 7th rank, create threats, and restrict the enemy king.",
        "why_section": "Rook endgames are the most common endgame type. Active rooks create so many threats that they can compensate for material deficits.",
        "next_idea": "Get your rook active before pushing pawns. An active rook supports pawn advances better.",
        "socratic_question": "Is your rook active or passive right now?"
    },
    {
        "main_insight": "Opposition matters in pawn endgames!",
        "explanation": "Opposition is when the two kings face each other with one square between them. The side NOT to move has the opposition. In pawn endgames, having the opposition often means winning because you control key squares and can support your pawns or block enemy pawns.",
        "why_section": "Many pawn endgames are decided by opposition and square counting—seemingly simple positions have deep geometry.",
        "next_idea": "Calculate king and pawn races carefully. Count tempos to see who promotes first.",
        "socratic_question": "Who has the opposition in this position?"
    }
]


# === TECHNIQUE TEMPLATES ===

TECHNIQUE_TEMPLATES = [
    {
        "main_insight": "Convert your advantage with technique.",
        "explanation": "You're ahead in material. Now the goal is to trade pieces, simplify, and convert the endgame. Technique means: {{technique_steps}}. Don't rush—you're winning if you don't blunder.",
        "why_section": "Many players win material but lose in the endgame due to poor technique. Slow down, trade pieces, activate your king.",
        "next_idea": "Trade pieces, activate your king, create passed pawns.",
        "socratic_question": "What's the simplest way to convert this advantage?"
    },
    {
        "main_insight": "Time to simplify and trade.",
        "explanation": "When you're ahead in material, trading pieces makes your advantage more significant. Each trade brings you closer to a winning king and pawn endgame. Look for opportunities to trade {{piece_type}} and simplify.",
        "why_section": "The rule: when you're ahead, trade pieces but not pawns. When you're behind, avoid trades.",
        "next_idea": "After trades, activate your king and push passed pawns.",
        "socratic_question": "What pieces can you trade off?"
    },
    {
        "main_insight": "Don't let your opponent create counterplay.",
        "explanation": "You're winning, but your opponent is trying to create threats. In the endgame, shut down counterplay by {{defensive_action}}. Once their activity is neutralized, you can convert safely.",
        "why_section": "Many won endgames are thrown away by allowing desperate counterplay. Deal with threats before pushing for the win.",
        "next_idea": "First stop their threats, then methodically convert your advantage.",
        "socratic_question": "What's your opponent threatening?"
    }
]


# === SPECIFIC ENDGAME PATTERNS ===

ENDGAME_PATTERN_TEMPLATES = [
    {
        "main_insight": "This is a {{pattern_name}} endgame.",
        "explanation": "{{pattern_name}} endgames have specific winning/drawing techniques. The key ideas: {{key_ideas}}. You need to {{winning_plan}}.",
        "why_section": "Standard endgame patterns appear frequently. Learning them means you can play these positions perfectly.",
        "next_idea": "Follow the standard technique: {{technique}}.",
        "socratic_question": "Do you know the winning method for this endgame?"
    },
    {
        "main_insight": "Classic {{pattern_name}}—there's a standard winning method.",
        "explanation": "This endgame type has been studied extensively. The winning side should {{winning_method}}, while the defending side tries to {{defensive_method}}. With best play, {{result}}.",
        "why_section": "Studying endgame patterns is like learning vocabulary—once you know them, you recognize them instantly.",
        "next_idea": "Apply the standard technique and calculate accurately.",
        "socratic_question": None
    }
]


# === ZUGZWANG TEMPLATES ===

ZUGZWANG_TEMPLATES = [
    {
        "main_insight": "This is zugzwang—whoever moves loses!",
        "explanation": "Zugzwang is a German word meaning 'compulsion to move.' In this position, the side to move would prefer to pass their turn because any move worsens their position. This is a critical endgame concept.",
        "why_section": "Zugzwang is more common in endgames than in other phases because there are fewer pieces and every move matters.",
        "next_idea": "Try to put your opponent in zugzwang by forcing them to move when all moves are bad.",
        "socratic_question": "What happens if your opponent has to move?"
    },
    {
        "main_insight": "You can force zugzwang with accurate play.",
        "explanation": "By playing {{move}}, you put your opponent in a position where any move loses material or allows a decisive breakthrough. This is the essence of zugzwang—making your opponent's obligation to move a disadvantage.",
        "why_section": "Creating zugzwang requires accurate calculation and understanding of square control.",
        "next_idea": "Force your opponent into positions where all their moves are bad.",
        "socratic_question": None
    }
]


# === DRAWING TECHNIQUE TEMPLATES ===

DRAWING_TEMPLATES = [
    {
        "main_insight": "You can hold this position with correct defense.",
        "explanation": "You're slightly worse, but this endgame is defensible. The key defensive ideas: {{defensive_ideas}}. Keep your pieces active, don't allow breakthroughs, and stay patient.",
        "why_section": "Many endgames that look losing are actually drawable with good defensive technique. Don't resign prematurely.",
        "next_idea": "Focus on {{defensive_focus}} and avoid pawn weaknesses.",
        "socratic_question": "What's your opponent trying to achieve?"
    },
    {
        "main_insight": "Activate your pieces for the best defensive chances.",
        "explanation": "When defending worse endgames, activity is crucial. Keep your {{piece}} active by {{activity_plan}}. Don't let your opponent push you into passivity.",
        "why_section": "Passive defense usually loses. Active defense can hold even significantly worse positions.",
        "next_idea": "Create enough counterplay to make winning difficult for your opponent.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_endgame_template(
    template_type: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for endgame technique."""
    
    template_map = {
        "principle": ENDGAME_PRINCIPLE_TEMPLATES,
        "technique": TECHNIQUE_TEMPLATES,
        "pattern": ENDGAME_PATTERN_TEMPLATES,
        "zugzwang": ZUGZWANG_TEMPLATES,
        "drawing": DRAWING_TEMPLATES
    }
    
    templates = template_map.get(template_type, ENDGAME_PRINCIPLE_TEMPLATES)
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "In the endgame, king activity is key.",
            "explanation": "",
            "why_section": None,
            "next_idea": "Activate your king and create passed pawns.",
            "socratic_question": None
        }
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
