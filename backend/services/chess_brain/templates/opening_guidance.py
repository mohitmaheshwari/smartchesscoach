"""
Opening Guidance Templates
==========================

Templates for opening phase teaching.
Covers opening principles, common ideas, and book moves.
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


# === OPENING PRINCIPLES TEMPLATES ===

OPENING_PRINCIPLE_TEMPLATES = [
    {
        "main_insight": "Focus on opening principles: control the center.",
        "explanation": "In the opening, prioritize controlling the center with pawns (e4, d4, e5, d5) and pieces. Central control gives your pieces more scope and limits your opponent's options. Knights and bishops should aim at or occupy central squares.",
        "why_section": "The center is the most important part of the board in the opening because pieces there control the most squares.",
        "next_idea": "Develop your pieces toward the center and castle to ensure king safety.",
        "socratic_question": "Which of your pieces can control central squares?"
    },
    {
        "main_insight": "Develop your pieces before moving them twice.",
        "explanation": "A key opening principle: get all your pieces into the game before moving the same piece multiple times. Each move should develop a new piece or improve your position. Moving the same piece twice while other pieces sit on the back rank wastes time.",
        "why_section": "Development is about tempo—each move should accomplish something. Your opponent develops while you move one piece repeatedly, and suddenly they're ahead.",
        "next_idea": "Aim to develop knights before bishops, and castle early for king safety.",
        "socratic_question": "How many of your pieces are actively developed?"
    },
    {
        "main_insight": "Castle early to secure your king.",
        "explanation": "King safety is crucial. Castling moves your king to safety behind a pawn shield and activates your rook. Most strong players castle within the first 10 moves. An exposed king in the center invites attacks.",
        "why_section": "Many games are lost because one side's king is caught in the center when the position opens up.",
        "next_idea": "After castling, connect your rooks and look for plans in the middlegame.",
        "socratic_question": "Is your king safer in the center or after castling?"
    },
    {
        "main_insight": "Don't move pawns aimlessly—develop pieces first.",
        "explanation": "While pawns control space, moving too many pawns in the opening delays piece development. Focus on developing knights and bishops first. Pawn moves are permanent and can create weaknesses, so make them count.",
        "why_section": "Pieces can retreat and reposition; pawns can't. Early pawn moves should serve a purpose—usually controlling the center or developing bishops.",
        "next_idea": "Get your knights and bishops out, castle, then refine your pawn structure.",
        "socratic_question": "What does this pawn move accomplish?"
    }
]


# === SPECIFIC OPENING TEMPLATES ===

OPENING_NAME_TEMPLATES = [
    {
        "main_insight": "You're in the {{opening_name}}—a {{opening_type}} opening.",
        "explanation": "The {{opening_name}} is characterized by {{key_ideas}}. Your main plans are: {{plans}}. Black/White typically aims to {{typical_goal}}.",
        "why_section": "This opening has been played at the highest levels because {{why_effective}}.",
        "next_idea": "Key moves to know: {{key_moves}}. Watch out for {{typical_traps}}.",
        "socratic_question": "What's your main plan in this opening structure?"
    },
    {
        "main_insight": "The {{opening_name}} leads to {{position_type}} positions.",
        "explanation": "In this opening, {{explanation}}. Typical ideas include {{typical_ideas}}. Both sides fight for {{objective}}.",
        "why_section": "Understanding opening ideas is more important than memorizing moves. Know what you're trying to achieve.",
        "next_idea": "Focus on {{next_focus}} and prepare for the middlegame transition.",
        "socratic_question": "What are you trying to accomplish in this structure?"
    },
    {
        "main_insight": "You're following {{opening_name}} theory.",
        "explanation": "This opening has a clear game plan: {{game_plan}}. The typical pawn structure leads to {{structure_type}} play. Your pieces should be placed on {{piece_placement}}.",
        "why_section": "Different openings lead to different middlegame types. This one creates {{middlegame_type}}.",
        "next_idea": "Continue with {{continuation}} and look for {{tactical_themes}}.",
        "socratic_question": None
    }
]


# === BOOK MOVE TEMPLATES ===

BOOK_MOVE_TEMPLATES = [
    {
        "main_insight": "That's a book move! {{move}} is well-known theory.",
        "explanation": "You're following established opening theory. {{move}} is a standard response that {{reason}}. Strong players have tested this position extensively.",
        "why_section": "Knowing some opening theory helps you reach good middlegame positions without thinking too hard.",
        "next_idea": "Continue developing naturally and stay aware of typical plans for this structure.",
        "socratic_question": None
    },
    {
        "main_insight": "Good! {{move}} is the main line.",
        "explanation": "This is one of the main theoretical moves in this position. {{move}} accomplishes {{purpose}}. You're in well-trodden territory.",
        "why_section": "Following the main line means you're on solid ground. Just understand the ideas behind the moves.",
        "next_idea": "Focus on the resulting structures and typical plans rather than memorizing every move.",
        "socratic_question": None
    }
]


# === DEVIATION TEMPLATES ===

DEVIATION_TEMPLATES = [
    {
        "main_insight": "You've left the main theoretical line.",
        "explanation": "{{move}} isn't the most popular move here. The main line continues with {{book_move}}, which {{reason}}. Your move is playable but less tested. You'll need to rely on general principles now.",
        "why_section": "Deviating from theory isn't bad, but it means you're on your own. Stick to opening principles: develop pieces, control center, castle.",
        "next_idea": "Focus on piece activity and sound development rather than specific moves.",
        "socratic_question": "What's the idea behind your move?"
    },
    {
        "main_insight": "Interesting choice—this is an uncommon move.",
        "explanation": "The standard continuation is {{book_move}}, but {{move}} is a valid alternative. It leads to {{resulting_position}}. You're entering less explored territory.",
        "why_section": "Playing off-beat moves can surprise opponents, but make sure you understand what you're doing.",
        "next_idea": "Ensure your fundamentals are solid—development, king safety, piece coordination.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_opening_template(
    template_type: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for opening guidance."""
    
    template_map = {
        "principle": OPENING_PRINCIPLE_TEMPLATES,
        "opening_name": OPENING_NAME_TEMPLATES,
        "book_move": BOOK_MOVE_TEMPLATES,
        "deviation": DEVIATION_TEMPLATES
    }
    
    templates = template_map.get(template_type, OPENING_PRINCIPLE_TEMPLATES)
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "Focus on opening principles.",
            "explanation": "",
            "why_section": None,
            "next_idea": "Develop pieces, control center, castle.",
            "socratic_question": None
        }
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
