"""
Strategic Concept Templates
============================

Templates for strategic concepts with multiple variations.
Covers pawn structure, piece activity, king safety, and positional ideas.
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


# === ISOLATED PAWN TEMPLATES ===

ISOLATED_PAWN_TEMPLATES = [
    {
        "main_insight": "You have an isolated pawn on {{square}}.",
        "explanation": "An isolated pawn has no friendly pawns on adjacent files to support it. This pawn on {{square}} is vulnerable and will need constant piece protection. Isolated pawns are weak because they can become targets in the endgame.",
        "why_section": "Pawns can't move backward, so once a pawn is isolated, it stays that way unless you trade it off.",
        "next_idea": "Either support this pawn with pieces or consider trading it for activity elsewhere.",
        "socratic_question": "Can this pawn be defended by another pawn?"
    },
    {
        "main_insight": "The pawn on {{square}} is isolated—a long-term weakness.",
        "explanation": "This pawn has no neighboring pawns to help defend it. Isolated pawns are strategic liabilities because they require piece support, tying down your forces. Your opponent can pile pressure on it.",
        "why_section": "In pawn structure evaluation, isolated pawns are generally weak. However, they can provide some compensation like open files for your rooks.",
        "next_idea": "Consider whether you can blockade this pawn or trade it off to eliminate the weakness.",
        "socratic_question": "What pieces need to stay back to defend this pawn?"
    },
    {
        "main_insight": "Watch out for the isolated pawn weakness on {{square}}.",
        "explanation": "Without pawn neighbors, this {{file}}-pawn is isolated. In the middlegame, it might be okay if you have active pieces. But in the endgame, isolated pawns become serious weaknesses that can cost you the game.",
        "why_section": "Pawn structure weaknesses persist throughout the game, so creating isolated pawns should be a conscious decision.",
        "next_idea": "Think about pawn trades carefully—each exchange changes the pawn structure permanently.",
        "socratic_question": None
    }
]


# === PASSED PAWN TEMPLATES ===

PASSED_PAWN_TEMPLATES = [
    {
        "main_insight": "You have a passed pawn on {{square}}—that's a big asset!",
        "explanation": "A passed pawn has no enemy pawns blocking its path to promotion. Your {{file}}-pawn can march toward the 8th rank (or 1st for Black), and only pieces can stop it. Passed pawns increase in value as the endgame approaches.",
        "why_section": "Passed pawns are powerful because they force your opponent to tie down pieces to stop them. This is especially strong in the endgame.",
        "next_idea": "Support this pawn with your king and rooks. Push it when your opponent's pieces are far away.",
        "socratic_question": "What's stopping this pawn from advancing right now?"
    },
    {
        "main_insight": "Your passed {{file}}-pawn is a powerful asset!",
        "explanation": "This pawn has a clear path forward with no enemy pawns to block it. As the great chess teacher Aron Nimzowitsch said, 'passed pawns must be pushed!' The threat of promotion ties down your opponent's pieces.",
        "why_section": "Passed pawns become unstoppable when supported. They're worth protecting and advancing.",
        "next_idea": "Use your pieces to escort this pawn forward, especially in the endgame.",
        "socratic_question": "How close is this pawn to promoting?"
    },
    {
        "main_insight": "The passed pawn on {{square}} is a game-changer!",
        "explanation": "No enemy pawns can stop this pawn from advancing. In the endgame, passed pawns often decide the game. Your opponent must use pieces to blockade or capture it, which gives you control elsewhere on the board.",
        "why_section": "The rule of thumb: passed pawns should be pushed, especially if they're far from the enemy king.",
        "next_idea": "Calculate whether you can safely advance this pawn or if it needs more support first.",
        "socratic_question": None
    }
]


# === KNIGHT OUTPOST TEMPLATES ===

OUTPOST_TEMPLATES = [
    {
        "main_insight": "Your knight has a strong outpost on {{square}}!",
        "explanation": "An outpost is a square deep in enemy territory that's protected by your pawns and can't be attacked by enemy pawns. Your knight on {{square}} is sitting pretty—it's safe, active, and controlling key squares. Outpost knights are often better than bishops.",
        "why_section": "Knights love outposts because they're short-range pieces. Being centralized and protected makes them extremely powerful.",
        "next_idea": "Use this knight to control key squares and support attacks. It's well-placed, so bring other pieces into the attack.",
        "socratic_question": "What important squares is this knight controlling?"
    },
    {
        "main_insight": "That knight on {{square}} is sitting on a perfect outpost!",
        "explanation": "Your knight is occupying a square where enemy pawns can't challenge it, and your own pawn supports it. Outpost knights are stable, dominant pieces. They can stay there as long as you want, controlling space and supporting operations.",
        "why_section": "Outposts are one of the key positional advantages. A well-placed knight on an outpost is often worth more than a poorly placed bishop.",
        "next_idea": "With a stable knight outpost, look to create threats around it or bring more pieces to that sector.",
        "socratic_question": "Can your opponent challenge this knight with pieces?"
    },
    {
        "main_insight": "Great outpost for your knight on {{square}}!",
        "explanation": "This is an ideal square for a knight—protected by your pawn, immune to enemy pawn attacks, and centrally placed. Outpost knights are permanent thorns in your opponent's position. They control dark or light squares depending on placement and can't easily be dislodged.",
        "why_section": "Creating outposts requires good pawn play earlier. This is why pawn structure matters.",
        "next_idea": "Maintain this outpost and build your position around it.",
        "socratic_question": None
    }
]


# === ROOK ACTIVITY TEMPLATES ===

ROOK_ACTIVITY_TEMPLATES = [
    {
        "main_insight": "Your rooks need better squares—they're passive right now.",
        "explanation": "Rooks thrive on open files where they can penetrate the enemy position. Right now, your rooks on {{rook_squares}} are blocked by your own pawns or sitting on closed files. Look for opportunities to activate them via open files or the 7th rank.",
        "why_section": "Rooks are most powerful in the endgame, but only if they're active. Passive rooks on closed files don't contribute much.",
        "next_idea": "Try to place your rooks on open or semi-open files where they can invade.",
        "socratic_question": "Which files are open or semi-open?"
    },
    {
        "main_insight": "You can activate your rook with {{move}}!",
        "explanation": "Rooks love open files. By playing {{move}}, you place your rook on the {{file}}-file where it has scope and can pressure your opponent's position. Active rooks on open files are one of the most important positional advantages.",
        "why_section": "The principle 'rooks belong on open files' is foundational. They control the file and can invade on the 7th or 8th rank.",
        "next_idea": "Once your rook is active, look to double rooks on the file or invade the 7th rank.",
        "socratic_question": "What can your rook accomplish on this open file?"
    },
    {
        "main_insight": "Rook to the 7th rank would be powerful!",
        "explanation": "The 7th rank (2nd rank for Black) is called the 'pig rank' because rooks love to feast there. Your opponent's pawns are usually on the 7th rank, making them targets. With {{move}}, your rook invades and creates serious threats.",
        "why_section": "Rooks on the 7th rank attack pawns, restrict the king, and often coordinate for devastating attacks.",
        "next_idea": "If you can get both rooks to the 7th rank, it's usually winning.",
        "socratic_question": None
    }
]


# === KING SAFETY TEMPLATES ===

KING_SAFETY_TEMPLATES = [
    {
        "main_insight": "Your king position looks unsafe—watch out for attacks.",
        "explanation": "Your king on {{king_square}} has vulnerabilities. {{weakness_description}}. In the opening and middlegame, king safety is paramount. An exposed king invites attacks that can be hard to defend.",
        "why_section": "Most games are decided by attacks on the king. If your king isn't safe, everything else matters less.",
        "next_idea": "Consider castling, moving pawns to create luft (escape squares), or bringing pieces back for defense.",
        "socratic_question": "If your opponent attacks your king, what pieces defend it?"
    },
    {
        "main_insight": "King safety issue: {{specific_weakness}}.",
        "explanation": "Your king's pawn shield is compromised or your king is still in the center. This creates tactical vulnerabilities. Your opponent can launch an attack with pieces aimed at your king, and you may not have time to organize a defense.",
        "why_section": "The principle 'safety first' applies to chess. Before launching your own attack, make sure your king is secure.",
        "next_idea": "Improve your king's safety before committing to aggressive plans.",
        "socratic_question": "Is your king safer than your opponent's king?"
    },
    {
        "main_insight": "Your king needs better protection!",
        "explanation": "Right now, your king on {{king_square}} is exposed to potential threats. {{threat_description}}. In positions where both sides can attack, the side with the safer king usually wins.",
        "why_section": "King safety isn't just about castling—it's about maintaining a solid pawn shield and keeping defending pieces nearby.",
        "next_idea": "Before attacking, ensure your own king is safe. Don't ignore defense.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_strategic_template(
    concept: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for a strategic concept."""
    
    template_map = {
        "ISOLATED_PAWN": ISOLATED_PAWN_TEMPLATES,
        "PASSED_PAWN": PASSED_PAWN_TEMPLATES,
        "KNIGHT_OUTPOST": OUTPOST_TEMPLATES,
        "ROOK_ACTIVITY": ROOK_ACTIVITY_TEMPLATES,
        "KING_SAFETY": KING_SAFETY_TEMPLATES
    }
    
    templates = template_map.get(concept, ISOLATED_PAWN_TEMPLATES)
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "There's a strategic consideration here.",
            "explanation": "",
            "why_section": None,
            "next_idea": "Think about long-term planning.",
            "socratic_question": None
        }
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
