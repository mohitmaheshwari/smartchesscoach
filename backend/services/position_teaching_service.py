"""
Position Teaching Service
=========================

Given a FEN + move history during Play with Coach, this service:
1. Identifies the opening and where we are in the theory tree
2. Finds reachable traps from the current position
3. Lists available variations with previews
4. Generates a position explanation (what's happening strategically)

This powers the "proactive teaching coach" — the coach recognizes
what's on the board and offers to teach, rather than just commenting.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── POSITION EXPLANATIONS ──
# Short, coach-style descriptions of what's happening in each opening.
# Keyed by opening_key from the detection service.

OPENING_EXPLANATIONS = {
    "italian_game": {
        "position": "White develops the bishop to c4, targeting f7 — Black's weakest square.",
        "idea_white": "Control the center, develop quickly, and look for tactical shots on f7.",
        "idea_black": "Develop solidly, protect f7, and prepare to challenge the center.",
        "fun_fact": "The Italian Game has been played since the 1500s. It's one of the oldest openings in chess.",
        "key_squares": ["f7", "e5", "d4", "c4"],
    },
    "sicilian_defense": {
        "position": "Black fights for the center with c5 instead of the symmetrical e5.",
        "idea_white": "Push d4 to open the center, then attack on the kingside.",
        "idea_black": "Create an asymmetrical game. Trade a c-pawn for White's d-pawn — then attack on the queenside.",
        "fun_fact": "The Sicilian Defense is the most played response to 1.e4 at every level.",
        "key_squares": ["d4", "c5", "e4"],
    },
    "queens_gambit": {
        "position": "White offers the c-pawn to control the center with d4 and c4.",
        "idea_white": "Control the center with pawns. If Black takes on c4, White gets a strong center.",
        "idea_black": "Decide: accept the pawn (Queen's Gambit Accepted) or hold the center with e6 or c6 (Declined/Slav).",
        "fun_fact": "Kasparov and Karpov played this opening in 40+ World Championship games.",
        "key_squares": ["d4", "d5", "c4", "e4"],
    },
    "london_system": {
        "position": "White sets up with d4, Bf4, e3, Nf3 — a solid, easy-to-learn system.",
        "idea_white": "Develop pieces harmoniously. Bishop to f4 BEFORE e3. Castle quickly, then attack.",
        "idea_black": "Challenge the center with c5 or d5. Try to make White's bishop on f4 a target.",
        "fun_fact": "The London System became extremely popular after Magnus Carlsen used it at the top level.",
        "key_squares": ["d4", "f4", "e3"],
    },
    "french_defense": {
        "position": "Black plays e6, preparing d5 to challenge the center next move.",
        "idea_white": "Advance e5 for space. The French can lead to sharp kingside attacks.",
        "idea_black": "Challenge the center with d5 and c5. Accept a slightly cramped position for counterplay.",
        "fun_fact": "Named after a famous correspondence game between London and Paris in 1834.",
        "key_squares": ["e4", "e6", "d4", "d5"],
    },
    "caro_kann": {
        "position": "Black plays c6, preparing d5 — similar idea to the French but keeps the bishop free.",
        "idea_white": "Keep the center strong. Nc3 and f4 setups work well.",
        "idea_black": "Solid position. The light-squared bishop stays active (unlike the French Defense).",
        "fun_fact": "The Caro-Kann is one of the most solid defenses. Very hard to lose with Black.",
        "key_squares": ["e4", "c6", "d5"],
    },
    "kings_indian": {
        "position": "Black lets White build a big center, then attacks it later with e5 or c5.",
        "idea_white": "Build a space advantage. Control the center. Don't let Black's counterattack succeed.",
        "idea_black": "Fianchetto the bishop to g7. Let White expand, then strike with e5 or f5.",
        "fun_fact": "Bobby Fischer and Garry Kasparov both loved the King's Indian. It leads to explosive games.",
        "key_squares": ["d4", "g7", "e5", "f5"],
    },
    "ruy_lopez": {
        "position": "White develops the bishop to b5, pinning the knight that defends e5.",
        "idea_white": "Create long-term pressure on Black's center. The Ruy Lopez leads to deep strategic games.",
        "idea_black": "Hold the center. Play a6 to challenge the bishop. Prepare counterplay on the queenside.",
        "fun_fact": "Named after a Spanish priest from the 1500s. It's been played at the highest level for 500 years.",
        "key_squares": ["b5", "e5", "a6"],
    },
    "scotch_game": {
        "position": "White immediately opens the center with d4 on move 3.",
        "idea_white": "Open lines for your pieces. Fast development and central control.",
        "idea_black": "Take on d4 and develop quickly. The position is more open than the Italian or Ruy Lopez.",
        "fun_fact": "Kasparov brought the Scotch Game back to top-level play in the 1990s.",
        "key_squares": ["d4", "e5", "e4"],
    },
    "scandinavian_defense": {
        "position": "Black immediately challenges e4 with d5 — the most direct response.",
        "idea_white": "Capture on d5 and develop. Black's queen may come out early, which can be targeted.",
        "idea_black": "Recapture on d5 (with queen or Nf6). Get active piece play early.",
        "fun_fact": "The Scandinavian is one of the oldest recorded chess openings, dating back to 1475.",
        "key_squares": ["e4", "d5"],
    },
}

# Default for openings not in the map
DEFAULT_EXPLANATION = {
    "position": "An interesting position with chances for both sides.",
    "idea_white": "Develop your pieces, control the center, and castle early.",
    "idea_black": "Develop your pieces, control the center, and castle early.",
    "fun_fact": None,
    "key_squares": [],
}


def get_position_teaching_context(
    opening_key: str,
    opening_name: str,
    moves: List[str],
    user_color: str,
    traps_available: List[Dict] = None,
    variations_available: List[Dict] = None,
) -> Dict:
    """
    Build a rich teaching context for the current position.

    Returns everything the frontend needs to show a conversational
    teaching offer in the sidebar.
    """
    explanation = OPENING_EXPLANATIONS.get(opening_key, DEFAULT_EXPLANATION)
    is_white = user_color == "white"

    # Build the coach message — conversational, not robotic
    move_count = len(moves) // 2
    if move_count <= 2:
        coach_msg = f"We're entering the {opening_name}!"
    else:
        coach_msg = f"This is the {opening_name}."

    # Add the strategic idea for the user's color
    idea = explanation["idea_white"] if is_white else explanation["idea_black"]
    coach_msg += f" {idea}"

    # Build options with richer descriptions
    options = []

    if traps_available:
        for trap in traps_available[:2]:  # Max 2 trap options
            trap_name = trap.get("name", "")
            trap_desc = trap.get("description", "")
            trap_moves = trap.get("setup_moves", [])
            remaining = len(trap_moves) - len(moves) if len(trap_moves) > len(moves) else 0

            options.append({
                "id": f"learn_trap_{trap.get('key', '')}",
                "label": trap_name,
                "description": trap_desc[:80] if trap_desc else "Learn this trap step by step.",
                "style": "aggressive",
                "moves_remaining": remaining,
                "lesson_type": "learn_trap",
            })

    if variations_available:
        for var in variations_available[:2]:  # Max 2 variation options
            options.append({
                "id": f"learn_var_{var.get('key', '')}",
                "label": var.get("name", "Main Line"),
                "description": f"{var.get('total_moves', '?')} moves deep. {var.get('description', '')}".strip(),
                "style": "solid",
                "moves_remaining": var.get("total_moves", 0),
                "lesson_type": "learn_main_line",
            })

    options.append({
        "id": "just_play",
        "label": "Just play — I'll figure it out",
        "description": "Coach will still comment on your moves.",
        "style": "neutral",
        "lesson_type": None,
    })

    return {
        "type": "opening_teaching_offer",
        "opening_key": opening_key,
        "opening_name": opening_name,
        "coach_message": coach_msg,
        "position_explanation": explanation["position"],
        "strategic_idea": idea,
        "fun_fact": explanation.get("fun_fact"),
        "key_squares": explanation.get("key_squares", []),
        "options": options,
        "move_count": move_count,
    }


def find_reachable_traps(opening_key: str, moves_played: List[str], user_color: str) -> List[Dict]:
    """
    Find traps that are still reachable from the current position.
    A trap is reachable if its setup_moves start with the moves already played.
    Only returns traps for the user's color.
    """
    try:
        from trick_library_service import TRAPS_DATABASE
    except ImportError:
        return []

    reachable = []
    moves_lower = [m.lower() for m in moves_played]

    for trap in TRAPS_DATABASE:
        # Only show traps for the user's color
        if trap.get("trap_for", "") != user_color:
            continue

        setup = trap.get("setup_moves", [])
        if not setup:
            continue

        # Check if current moves are a prefix of the trap's setup
        setup_lower = [m.lower() for m in setup]
        if len(moves_lower) > len(setup_lower):
            continue

        is_prefix = True
        for i, m in enumerate(moves_lower):
            if i >= len(setup_lower) or m != setup_lower[i]:
                is_prefix = False
                break

        if is_prefix:
            reachable.append({
                "key": trap.get("key", ""),
                "name": trap.get("name", ""),
                "description": trap.get("description", ""),
                "setup_moves": setup,
                "difficulty": trap.get("difficulty", "intermediate"),
                "result_type": trap.get("result_type", ""),
            })

    return reachable
