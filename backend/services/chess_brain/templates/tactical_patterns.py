"""
Tactical Pattern Templates
===========================

Templates for all 10 tactical patterns with multiple variations.
Each pattern has 3-4 variations to avoid repetition.
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


# === FORK TEMPLATES ===

FORK_TEMPLATES = [
    {
        "main_insight": "Your {{piece}} on {{square}} could fork the {{target1}} and {{target2}}!",
        "explanation": "A fork is when one piece attacks two or more enemy pieces at once. Here, moving your {{piece}} to {{square}} would attack both the {{target1}} and {{target2}} simultaneously. Your opponent can only save one piece, so you'll win material.",
        "why_section": "Forks work because your opponent can't defend two pieces at once with one move. Even if they move one piece to safety, you'll capture the other.",
        "next_idea": "Look for squares where your pieces can attack multiple targets at once.",
        "socratic_question": "Can you see which square lets your {{piece}} attack two pieces at once?"
    },
    {
        "main_insight": "There's a fork opportunity with {{piece}} to {{square}}.",
        "explanation": "By placing your {{piece}} on {{square}}, you'd be attacking the {{target1}} on {{target1_square}} and the {{target2}} on {{target2_square}} at the same time. This tactic, called a fork, forces your opponent to lose material since they can only move one piece per turn.",
        "why_section": "The power of a fork is in the tempo—your opponent must respond to both threats but can only address one.",
        "next_idea": "When you see enemy pieces close together, check if any of your pieces can reach a square that attacks both.",
        "socratic_question": "What happens if your opponent moves the {{target1}}? Can you still capture something?"
    },
    {
        "main_insight": "{{piece}} to {{square}} wins material through a fork!",
        "explanation": "This is a classic forking pattern. Your {{piece}} jumps to {{square}} and suddenly both the {{target1}} and {{target2}} are under attack. Your opponent saves one, you take the other. That's how forks work—create two threats, win material.",
        "why_section": "Forks are one of the most common tactical motifs in chess because pieces naturally cluster together during the game.",
        "next_idea": "Knights are especially good at forking because they can jump over other pieces.",
        "socratic_question": None
    }
]


# === PIN TEMPLATES ===

PIN_TEMPLATES = [
    {
        "main_insight": "You can pin the {{pinned_piece}} to the {{valuable_piece}} with {{attacker}} to {{square}}.",
        "explanation": "A pin restricts a piece because moving it would expose something more valuable. Here, your {{attacker}} on {{square}} would attack the {{pinned_piece}}, and behind it is the {{valuable_piece}}. If the {{pinned_piece}} moves, you'd capture the {{valuable_piece}}.",
        "why_section": "Pins are powerful because they paralyze pieces. The pinned piece can't move without creating a bigger problem.",
        "next_idea": "Look for pieces lined up on the same rank, file, or diagonal—one might be shielding another.",
        "socratic_question": "What happens if your opponent moves the {{pinned_piece}}?"
    },
    {
        "main_insight": "There's a pin available: {{attacker}} pins {{pinned_piece}} to {{valuable_piece}}.",
        "explanation": "By moving your {{attacker}} to {{square}}, you'd create a pin. The {{pinned_piece}} is stuck because moving it would lose the {{valuable_piece}} behind it. Pins are like invisible chains—the piece is technically free to move, but doing so would be disastrous.",
        "why_section": "Bishops, rooks, and queens create pins by attacking along lines. The pinned piece becomes a liability.",
        "next_idea": "Once you create a pin, you can often pile on more attackers to win the pinned piece.",
        "socratic_question": "Can the {{pinned_piece}} move at all, or is it completely stuck?"
    },
    {
        "main_insight": "{{attacker}} to {{square}} creates a powerful pin!",
        "explanation": "This move sets up a pin that restricts your opponent's {{pinned_piece}}. The piece can't move freely because the {{valuable_piece}} is behind it on the same line. You're not just attacking one piece—you're controlling it.",
        "why_section": "Pins work because of geometry. When pieces line up on ranks, files, or diagonals, long-range pieces can pin them.",
        "next_idea": "Think about which of your opponent's pieces are lined up—that's where pins happen.",
        "socratic_question": None
    }
]


# === SKEWER TEMPLATES ===

SKEWER_TEMPLATES = [
    {
        "main_insight": "You can skewer the {{front_piece}} to win the {{back_piece}} with {{attacker}} to {{square}}!",
        "explanation": "A skewer is like a reverse pin—you attack a valuable piece, forcing it to move, and then capture something behind it. Here, your {{attacker}} attacks the {{front_piece}}, which must move to safety. Once it moves, you capture the {{back_piece}} behind it.",
        "why_section": "Skewers work because the front piece has to move out of check or away from capture, exposing what's behind.",
        "next_idea": "Skewers are especially powerful against kings since they must move when attacked.",
        "socratic_question": "After the {{front_piece}} moves, what can you capture?"
    },
    {
        "main_insight": "There's a skewer pattern: {{attacker}} to {{square}} forces the {{front_piece}} to move.",
        "explanation": "By placing your {{attacker}} on {{square}}, you attack the {{front_piece}}. When it moves to safety, the {{back_piece}} behind it becomes vulnerable. This tactic is called a skewer—you force movement and win material.",
        "why_section": "Unlike pins where the piece wants to stay, in skewers the piece must move, which is exactly what you want.",
        "next_idea": "Look for high-value pieces in front of lower-value pieces on the same line.",
        "socratic_question": "Why must the {{front_piece}} move?"
    },
    {
        "main_insight": "{{attacker}} to {{square}} creates a skewer winning material!",
        "explanation": "This is a classic skewer. Your {{attacker}} attacks the {{front_piece}}, forcing it away, and then you collect the {{back_piece}}. Kings and queens are often the front pieces in skewers because they're valuable and must move.",
        "why_section": "Skewers demonstrate the power of geometry and forcing moves in chess.",
        "next_idea": "After checks and captures, skewers are the next tactical pattern to look for.",
        "socratic_question": None
    }
]


# === HANGING PIECE TEMPLATES ===

HANGING_TEMPLATES = [
    {
        "main_insight": "The {{piece}} on {{square}} is hanging—you can take it for free!",
        "explanation": "A hanging piece is one that's undefended and can be captured without consequences. The enemy {{piece}} on {{square}} has no protection. You can simply capture it and win material.",
        "why_section": "Before every move, check: What pieces can I take? What pieces are my opponent threatening?",
        "next_idea": "Always scan the board for undefended pieces before making your move.",
        "socratic_question": "Is the {{piece}} on {{square}} defended by anything?"
    },
    {
        "main_insight": "Free piece alert! The {{piece}} on {{square}} is undefended.",
        "explanation": "This is called a hanging piece—it's not protected by any other piece. You can capture it with your {{capturer}} and there's no recapture available. This is one of the most common ways to win material in chess.",
        "why_section": "Hanging pieces often appear after your opponent makes a move and forgets about a piece they had defended before.",
        "next_idea": "After your opponent moves, check if they left anything hanging.",
        "socratic_question": "What defends this {{piece}} right now?"
    },
    {
        "main_insight": "Your opponent left the {{piece}} on {{square}} undefended!",
        "explanation": "The {{piece}} is sitting there with no defenders. You can take it cleanly with {{capturer}}. Always look for hanging pieces—they're the simplest way to win material.",
        "why_section": "Even strong players occasionally hang pieces after complex sequences or under time pressure.",
        "next_idea": "Make it a habit: before you move, scan for hanging enemy pieces.",
        "socratic_question": None
    }
]


# === TRAPPED PIECE TEMPLATES ===

TRAPPED_TEMPLATES = [
    {
        "main_insight": "The {{piece}} on {{square}} is trapped with no good squares!",
        "explanation": "Your opponent's {{piece}} has run out of escape squares. It can't move without being captured. This often happens when pieces venture too far into enemy territory or get cornered by pawns.",
        "why_section": "Trapped pieces are valuable lessons in piece coordination—sometimes winning isn't about direct captures but about cutting off escape routes.",
        "next_idea": "When you see an enemy piece in a tight spot, check if you can close off its remaining escape squares.",
        "socratic_question": "Can the {{piece}} escape, or are all its squares controlled?"
    },
    {
        "main_insight": "You can trap the {{piece}}—it has nowhere safe to go!",
        "explanation": "The {{piece}} is boxed in. All of its potential escape squares are either controlled by your pieces or blocked. Now you can capture it at your leisure, or even better, use the threat to improve your position first.",
        "why_section": "Trapping pieces requires planning ahead—you need to control the squares around it before it realizes it's in danger.",
        "next_idea": "Pawns are excellent for trapping pieces because they can't move backward.",
        "socratic_question": "What would happen if the {{piece}} tries to escape to {{escape_square}}?"
    },
    {
        "main_insight": "The {{piece}} walked into a trap on {{square}}!",
        "explanation": "That {{piece}} has no good moves left. It's trapped. This is often the result of overextension—the piece ventured too deep without support and now can't get back safely.",
        "why_section": "Advanced pieces without escape routes become liabilities instead of assets.",
        "next_idea": "Be careful not to trap your own pieces—always leave yourself escape routes.",
        "socratic_question": None
    }
]


# === BACK RANK TEMPLATES ===

BACK_RANK_TEMPLATES = [
    {
        "main_insight": "Back rank mate is available with {{move}}!",
        "explanation": "Your opponent's king is trapped on the back rank by its own pawns. Your {{piece}} can deliver checkmate by attacking along the back rank. The king has no escape squares because the pawns block its way forward.",
        "why_section": "Back rank mates are one of the most common checkmate patterns, especially in the endgame when rooks become active.",
        "next_idea": "When you see a king trapped on the back rank, look for ways to invade with your rooks or queen.",
        "socratic_question": "Why can't the king escape to the second rank?"
    },
    {
        "main_insight": "There's a back rank weakness you can exploit!",
        "explanation": "The enemy king is stuck on the back rank, hemmed in by its own pawns. With {{move}}, your {{piece}} delivers checkmate. This pattern is why experienced players often give their king 'luft' (breathing room) in German—an escape square.",
        "why_section": "The irony of back rank mates is that your opponent's own pieces create the prison.",
        "next_idea": "Always check: does my king have an escape square? Does my opponent's?",
        "socratic_question": "What's stopping the king from escaping?"
    },
    {
        "main_insight": "{{move}} is checkmate—classic back rank mate!",
        "explanation": "Your rook (or queen) attacks the king on the back rank, and there's nowhere to go. The friendly pawns that were protecting the king are now trapping it. This is one of the fundamental checkmate patterns every player should recognize instantly.",
        "why_section": "This pattern appears in countless games because it's easy to overlook until it's too late.",
        "next_idea": "Consider playing h3 or h6 to give your own king an escape square.",
        "socratic_question": None
    }
]


# === MATE TEMPLATES ===

MATE_TEMPLATES = [
    {
        "main_insight": "Checkmate in {{mate_in}} with {{move}}!",
        "explanation": "There's a forced checkmate sequence starting with {{move}}. No matter how your opponent responds, you can deliver checkmate in {{mate_in}} moves. This is the goal of chess—when you see mate, nothing else matters.",
        "why_section": "Checkmate ends the game immediately, so it takes priority over any material gain.",
        "next_idea": "Before every move, check: is there a checkmate available?",
        "socratic_question": "Can you see how this leads to checkmate?"
    },
    {
        "main_insight": "You missed mate in {{mate_in}}!",
        "explanation": "There was a forced checkmate sequence here. Starting with {{move}}, you could have ended the game in {{mate_in}} moves. This is the most important type of tactic to recognize—when you can force mate, always go for it.",
        "why_section": "Checkmate is absolute. Even if you're down material, mate wins the game.",
        "next_idea": "In every position, especially when attacking the king, look for checkmate patterns first.",
        "socratic_question": "What's your opponent's king position? Any weaknesses?"
    },
    {
        "main_insight": "{{move}} ends the game—checkmate!",
        "explanation": "This move delivers checkmate. The enemy king is attacked and has no legal moves to escape, block, or capture the attacking piece. Game over. Recognizing mate patterns is the single most important tactical skill.",
        "why_section": "The king's safety is paramount. Everything in chess ultimately revolves around checkmating your opponent while protecting your own king.",
        "next_idea": "Study common checkmate patterns—they appear more often than you think.",
        "socratic_question": None
    }
]


# === DISCOVERY TEMPLATES ===

DISCOVERY_TEMPLATES = [
    {
        "main_insight": "{{move}} creates a discovered attack on the {{target}}!",
        "explanation": "By moving your {{moving_piece}}, you uncover an attack from your {{attacker}} behind it. The {{attacker}} now attacks the {{target}}, and your opponent has to deal with both the piece that just moved AND the discovered attack. This double-threat is very powerful.",
        "why_section": "Discovered attacks work because your opponent suddenly faces two threats at once, like a fork but with two different pieces.",
        "next_idea": "Look for pieces lined up behind each other—moving the front piece might reveal an attack.",
        "socratic_question": "What piece is hiding behind your {{moving_piece}}?"
    },
    {
        "main_insight": "There's a discovered attack pattern here!",
        "explanation": "When your {{moving_piece}} moves from {{from_square}}, it opens up a line for your {{attacker}}. Now the {{target}} is suddenly under attack. Plus, your {{moving_piece}} is making its own threat. Two threats, one move.",
        "why_section": "Discovered attacks are especially powerful because the moving piece often moves with check or creates its own threat.",
        "next_idea": "Some discovered attacks come with check, forcing your opponent to move their king while you capture elsewhere.",
        "socratic_question": "After your {{moving_piece}} moves, what does the {{attacker}} attack?"
    },
    {
        "main_insight": "Move your {{moving_piece}} to discover an attack!",
        "explanation": "Your {{moving_piece}} is currently blocking your {{attacker}}'s line to the {{target}}. By moving it, you unveil the attack while potentially creating another threat with the moving piece itself. This is called a discovered attack.",
        "why_section": "The beauty of discovered attacks is that you get to make two moves' worth of threats in one turn.",
        "next_idea": "When you have long-range pieces aimed at enemy pieces, think about what you could discover.",
        "socratic_question": None
    }
]


# === OVERLOAD TEMPLATES ===

OVERLOAD_TEMPLATES = [
    {
        "main_insight": "The {{defender}} is overloaded—it can't defend everything!",
        "explanation": "Your opponent's {{defender}} is trying to protect multiple pieces: the {{target1}} and the {{target2}}. You can exploit this by attacking {{target1}} with {{move}}. The {{defender}} can't protect both targets, so you'll win material.",
        "why_section": "Overloaded pieces are common because as the game progresses, fewer pieces need to do more defensive work.",
        "next_idea": "Look for pieces defending multiple targets—they're vulnerable to tactical blows.",
        "socratic_question": "What happens if you attack the {{target1}}? Can the {{defender}} still protect the {{target2}}?"
    },
    {
        "main_insight": "That {{defender}} has too many jobs!",
        "explanation": "The {{defender}} on {{square}} is defending both the {{target1}} and the {{target2}}. This is called an overload. With {{move}}, you attack one of these pieces, and the defender must abandon the other. You win material through the overload.",
        "why_section": "In chess, pieces can only be in one place at a time. When one piece tries to defend two things, it usually fails at both.",
        "next_idea": "When you see a single piece defending multiple targets, test it by attacking one target.",
        "socratic_question": "How many things is the {{defender}} protecting?"
    },
    {
        "main_insight": "Exploit the overworked {{defender}} with {{move}}!",
        "explanation": "The {{defender}} is stretched too thin, trying to protect multiple pieces. You can break through with {{move}}, attacking {{target1}}. If the defender saves {{target1}}, you capture {{target2}}. If it doesn't move, you win {{target1}}.",
        "why_section": "Recognizing overloaded pieces is about counting: how many things is this piece defending, and can it really do it all?",
        "next_idea": "During your opponent's moves, note which pieces are doing heavy defensive duty.",
        "socratic_question": None
    }
]


# === REMOVAL TEMPLATES ===

REMOVAL_TEMPLATES = [
    {
        "main_insight": "Remove the guard with {{move}}!",
        "explanation": "The {{target}} is protected by the {{defender}}. By playing {{move}}, you remove or deflect the {{defender}}, and then the {{target}} falls. This is called removing the defender—you eliminate the piece that's protecting something valuable.",
        "why_section": "Sometimes you can't directly capture a defended piece. But if you eliminate the defender first, the target becomes vulnerable.",
        "next_idea": "Ask yourself: what's defending the piece I want to capture? Can I remove that defender?",
        "socratic_question": "What happens to the {{target}} after you capture the {{defender}}?"
    },
    {
        "main_insight": "Capture the {{defender}} to win the {{target}}!",
        "explanation": "Your opponent's {{target}} looks safe because the {{defender}} is protecting it. But you can play {{move}}, removing the defender. Once the defender is gone, the {{target}} is hanging and you can capture it next move.",
        "why_section": "Removal of the defender is a two-step tactic: first eliminate the guard, then capture the target.",
        "next_idea": "Sometimes you sacrifice material to remove a key defender, winning more material back.",
        "socratic_question": "After the {{defender}} is gone, what can you capture?"
    },
    {
        "main_insight": "{{move}} removes the key defender!",
        "explanation": "The {{defender}} is the only thing protecting the {{target}}. With {{move}}, you eliminate the defender (either by capturing it or forcing it away), and suddenly the {{target}} is undefended. This tactic is called deflection or removal of the guard.",
        "why_section": "This pattern teaches an important principle: in chess, defenses can be broken by removing the defenders.",
        "next_idea": "Look for pieces that are defending important targets—they might be vulnerable themselves.",
        "socratic_question": None
    }
]


# === TEMPLATE GETTER ===

def get_tactical_template(
    pattern: str,
    variables: Dict[str, Any],
    variation: Optional[int] = None
) -> Dict[str, str]:
    """Get template for a tactical pattern."""
    
    template_map = {
        "MISSED_FORK": FORK_TEMPLATES,
        "MISSED_PIN": PIN_TEMPLATES,
        "MISSED_SKEWER": SKEWER_TEMPLATES,
        "HANGING_PIECE": HANGING_TEMPLATES,
        "TRAPPED_PIECE": TRAPPED_TEMPLATES,
        "MISSED_BACK_RANK": BACK_RANK_TEMPLATES,
        "MISSED_MATE": MATE_TEMPLATES,
        "MISSED_DISCOVERY": DISCOVERY_TEMPLATES,
        "MISSED_OVERLOAD": OVERLOAD_TEMPLATES,
        "MISSED_REMOVAL": REMOVAL_TEMPLATES
    }
    
    templates = template_map.get(pattern, FORK_TEMPLATES)
    template = select_variation(templates, variation)
    
    if not template:
        return {
            "main_insight": "There was a tactical opportunity here.",
            "explanation": "",
            "why_section": None,
            "next_idea": "Look for forcing moves.",
            "socratic_question": None
        }
    
    return {
        "main_insight": render_template(template["main_insight"], variables),
        "explanation": render_template(template["explanation"], variables),
        "why_section": render_template(template["why_section"], variables) if template.get("why_section") else None,
        "next_idea": render_template(template["next_idea"], variables),
        "socratic_question": render_template(template["socratic_question"], variables) if template.get("socratic_question") else None
    }
