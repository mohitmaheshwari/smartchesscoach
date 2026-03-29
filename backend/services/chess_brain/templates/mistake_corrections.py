"""
Mistake Correction Templates
=============================

Templates for immediate mistake corrections.
Covers blunders, mistakes, and inaccuracies with empathetic coaching tone.
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


# === BLUNDER TEMPLATES ===

BLUNDER_TEMPLATES = [
    {
        "main_insight": "That move loses significant material—{{cp_loss}} centipawns.",
        "explanation": "{{user_move}} hangs {{lost_material}} or allows a tactical blow. Better was {{best_move}}, which {{best_move_reason}}. Blunders happen to everyone, especially under time pressure. The key is learning from them.",
        "why_section": "Before moving, take a moment to check: What does this move allow my opponent to do? What am I leaving undefended?",
        "next_idea": "Before your next move, scan for hanging pieces and opponent threats.",
        "socratic_question": "What does your opponent threaten after {{user_move}}?"
    },
    {
        "main_insight": "Careful! {{user_move}} is a serious mistake.",
        "explanation": "This move costs you about {{cp_loss_pawns}} pawns of material. The problem is {{problem_description}}. Instead, {{best_move}} would have {{best_move_benefit}}. Don't worry—blunders are learning opportunities.",
        "why_section": "Blunders often happen when we focus on our own ideas and forget to check what our opponent can do.",
        "next_idea": "Use the 'opponent's eye' technique: after you think of a move, imagine being your opponent. What would you do in response?",
        "socratic_question": "If you were your opponent, what would you play now?"
    },
    {
        "main_insight": "This move gives away too much—let's learn from it.",
        "explanation": "{{user_move}} loses the game or major material. {{mistake_description}}. The better path was {{best_move}}. Remember, every strong player has made thousands of blunders. What separates them is learning to make fewer over time.",
        "why_section": "The most common cause of blunders is rushing. Give yourself time to double-check.",
        "next_idea": "Develop a pre-move checklist: Is anything hanging? What does this move allow? Are there any checks or captures for my opponent?",
        "socratic_question": None
    }
]


# === MISTAKE TEMPLATES ===

MISTAKE_TEMPLATES = [
    {
        "main_insight": "{{user_move}} isn't the best here—you lose some advantage.",
        "explanation": "This move costs you about {{cp_loss}} centipawns (roughly {{cp_loss_pawns}} pawns). {{mistake_description}}. Better was {{best_move}}, which {{best_move_reason}}. This type of mistake is usually about not finding the best continuation.",
        "why_section": "Mistakes often come from not calculating deeply enough or missing a tactical shot.",
        "next_idea": "When you have a candidate move, spend a moment checking if there's something even better.",
        "socratic_question": "Did you see {{best_move}}? What does it accomplish?"
    },
    {
        "main_insight": "There was a better move available.",
        "explanation": "{{user_move}} is playable but not optimal. You missed {{best_move}}, which {{best_move_benefit}}. The difference is about {{cp_loss_pawns}} pawns of advantage. Not critical, but these moves add up over a game.",
        "why_section": "The difference between good players and great players is often in these 'small' moments—finding the most accurate moves.",
        "next_idea": "After finding a good move, pause and ask: Is there something even better?",
        "socratic_question": "What makes {{best_move}} stronger than {{user_move}}?"
    },
    {
        "main_insight": "You missed a stronger continuation.",
        "explanation": "Your move {{user_move}} is reasonable, but {{best_move}} was more accurate. {{reason}}. In this position, precision matters. The evaluation swings by {{cp_loss}} centipawns, which is noticeable.",
        "why_section": "Chess rewards accuracy. Small advantages accumulate into winning positions.",
        "next_idea": "Consider all forcing moves (checks, captures, threats) before settling on quiet moves.",
        "socratic_question": None
    }
]


# === INACCURACY TEMPLATES ===

INACCURACY_TEMPLATES = [
    {
        "main_insight": "{{user_move}} is okay, but slightly inaccurate.",
        "explanation": "This move isn't bad, but {{best_move}} was a bit more precise. {{reason}}. The difference is small—about {{cp_loss}} centipawns—but good technique means finding these improvements.",
        "why_section": "Inaccuracies don't lose games, but they let your opponent back into positions where you had an edge.",
        "next_idea": "Keep refining your move selection. Small improvements add up.",
        "socratic_question": "Can you see why {{best_move}} might be slightly better?"
    },
    {
        "main_insight": "A minor inaccuracy—not critical.",
        "explanation": "{{user_move}} is fine, but there was a marginally better option in {{best_move}}. {{explanation}}. This won't change the outcome, but striving for precision is how you improve.",
        "why_section": "Even small inaccuracies are worth noting because they represent learning opportunities.",
        "next_idea": "As you improve, these small edges become clearer.",
        "socratic_question": None
    },
    {
        "main_insight": "Decent move, but there's a slightly better option.",
        "explanation": "You played {{user_move}}, which is reasonable. However, {{best_move}} was a touch more accurate because {{reason}}. Don't stress over small inaccuracies—they're part of learning.",
        "why_section": "Perfect play is impossible. But analyzing these moments helps you see patterns.",
        "next_idea": "Focus on bigger mistakes first, but keep an eye on these refinements.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_mistake_template(
    mistake_type: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for a mistake correction."""
    
    # Map mistake severity to template set
    cp_loss = variables.get("cp_loss", 0)
    
    if cp_loss >= 200 or mistake_type == "blunder":
        templates = BLUNDER_TEMPLATES
    elif cp_loss >= 100 or mistake_type == "mistake":
        templates = MISTAKE_TEMPLATES
    else:
        templates = INACCURACY_TEMPLATES
    
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "Let's look at this position more carefully.",
            "explanation": "",
            "why_section": None,
            "next_idea": "Think about what your opponent threatens.",
            "socratic_question": None
        }
    
    # Calculate cp_loss in pawns
    variables["cp_loss_pawns"] = round(cp_loss / 100, 1)
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
