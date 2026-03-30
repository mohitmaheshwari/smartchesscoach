"""
Opening Curriculum Engine
==========================

Reads from opening_curriculum.json and guides the player move-by-move
through their opening during a live game.

Given the current move sequence, returns:
- What to play next
- Why (the idea)
- The plan going forward
- Any trap warnings
- Candidate moves if off-book
"""

import json
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CURRICULUM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "opening_curriculum.json")

_CURRICULUM = None

def _load_curriculum() -> Dict:
    global _CURRICULUM
    if _CURRICULUM is None:
        try:
            with open(CURRICULUM_PATH, "r") as f:
                _CURRICULUM = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load curriculum: {e}")
            _CURRICULUM = {}
    return _CURRICULUM


def get_available_openings(color: str = None) -> List[Dict]:
    """Get list of available openings to learn."""
    curriculum = _load_curriculum()
    result = []
    for key, data in curriculum.items():
        if color and data.get("color") != color:
            continue
        result.append({
            "key": key,
            "name": data.get("name", key),
            "color": data.get("color", "white"),
            "summary": data.get("summary", ""),
            "difficulty": data.get("difficulty", "intermediate"),
        })
    return result


def get_opening_guidance(opening_key: str, moves_played: List[str], user_color: str) -> Optional[Dict]:
    """
    Given the moves played so far, return coaching guidance from the curriculum.
    
    Returns:
    {
        "suggested_move": "Bf4",
        "idea": "THE London move. Bishop comes out BEFORE e3.",
        "plan": "Next: e3 to solidify, then Nf3, Bd3, O-O.",
        "is_in_book": True,
        "trap_warning": None,
        "golden_rule": "Bishop to f4 BEFORE e3. Always.",
        "alternatives": [{"move": "Nf3", "idea": "Also fine but Bf4 first is the London way"}],
        "position_name": "London Main Line",
    }
    """
    curriculum = _load_curriculum()
    opening = curriculum.get(opening_key)
    if not opening:
        return None

    tree = opening.get("tree", {})
    if not tree:
        return None

    # Walk the tree following the moves played
    node = None
    position_name = opening.get("name", "Opening")
    current_branch = tree

    # The tree starts with White's first move as keys
    # We need to walk: move1 -> response -> move2 -> response -> ...
    for i, move in enumerate(moves_played):
        is_our_move = (i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black")

        if is_our_move:
            # Our move — check if it matches the tree's expected move
            if isinstance(current_branch, dict) and move in current_branch:
                node = current_branch[move]
                current_branch = node.get("responses", {})
                if node.get("name"):
                    position_name = node["name"]
            elif isinstance(current_branch, dict):
                # Check if any node's "next" matches
                for key, branch_node in current_branch.items():
                    if isinstance(branch_node, dict) and branch_node.get("next") == move:
                        node = branch_node
                        current_branch = branch_node.get("responses", {})
                        break
                else:
                    # Off book
                    return _off_book_guidance(opening, moves_played, i, user_color)
        else:
            # Opponent's move — look in current responses
            if isinstance(current_branch, dict) and move in current_branch:
                node = current_branch[move]
                current_branch = node.get("responses", {})
                if node.get("name"):
                    position_name = node["name"]
            else:
                # Opponent played something unexpected
                return _opponent_surprise_guidance(opening, current_branch, move, moves_played, user_color)

    # Now build guidance for the NEXT move
    if node is None and not moves_played:
        # Game just started — suggest first move
        first_move = list(tree.keys())[0] if tree else None
        if first_move:
            first_node = tree[first_move]
            return {
                "suggested_move": first_move,
                "idea": first_node.get("idea", f"Play {first_move} to start."),
                "plan": first_node.get("plan", ""),
                "is_in_book": True,
                "trap_warning": None,
                "golden_rule": opening.get("golden_rules", [""])[0] if opening.get("golden_rules") else None,
                "alternatives": [],
                "position_name": opening.get("name"),
                "middlegame_plan": None,
            }
        return None

    # We're at a node — what's the next move?
    if node:
        next_move = node.get("next")
        next_idea = node.get("next_idea", "")
        plan = node.get("plan", "")
        trap_ref = node.get("trap_reference")
        warning = node.get("warning")

        # Check for trap warning
        trap_warning = None
        if trap_ref:
            for trap in opening.get("traps", []):
                if trap.get("name") == trap_ref:
                    trap_warning = {
                        "name": trap["name"],
                        "description": trap.get("trap_idea", trap.get("description", "")),
                        "how_to_set": trap.get("how_to_set", ""),
                    }
                    break

        if warning:
            if trap_warning:
                trap_warning["extra_warning"] = warning
            else:
                trap_warning = {"name": "Watch out", "description": warning}

        # Build alternatives from sibling responses
        alternatives = []
        if isinstance(current_branch, dict):
            for alt_move, alt_node in current_branch.items():
                if isinstance(alt_node, dict) and alt_node.get("next"):
                    alternatives.append({
                        "move": alt_node["next"],
                        "idea": alt_node.get("next_idea", ""),
                    })

        # Check if we're transitioning to middlegame
        middlegame_plan = None
        move_count = len(moves_played)
        if move_count >= 12:
            mp = opening.get("middlegame_plans", {})
            middlegame_plan = mp.get("when_equal", {}).get("plan")

        # Pick a golden rule based on position
        golden_rule = None
        rules = opening.get("golden_rules", [])
        if rules:
            rule_index = min(len(moves_played) // 4, len(rules) - 1)
            golden_rule = rules[rule_index]

        return {
            "suggested_move": next_move,
            "idea": next_idea,
            "plan": plan,
            "is_in_book": True,
            "trap_warning": trap_warning,
            "golden_rule": golden_rule,
            "alternatives": alternatives[:2],
            "position_name": position_name,
            "middlegame_plan": middlegame_plan,
        }

    return None


def _off_book_guidance(opening: Dict, moves: List[str], off_book_at: int, user_color: str) -> Dict:
    """Player went off-book. Give general guidance."""
    plans = opening.get("middlegame_plans", {})
    general_plan = plans.get("when_equal", {}).get("plan", "Develop your pieces and control the center.")
    setup = opening.get("setup_order", [])

    # Suggest the next setup move they haven't played
    suggested = None
    for m in setup:
        if m not in moves:
            suggested = m
            break

    return {
        "suggested_move": suggested,
        "idea": f"You went off the main line. That's OK — stick to the setup: {', '.join(setup[:4])}.",
        "plan": general_plan,
        "is_in_book": False,
        "trap_warning": None,
        "golden_rule": opening.get("golden_rules", [""])[0] if opening.get("golden_rules") else None,
        "alternatives": [],
        "position_name": "Off Book",
        "middlegame_plan": general_plan,
    }


def _opponent_surprise_guidance(opening: Dict, current_branch: Dict, opponent_move: str, moves: List[str], user_color: str) -> Dict:
    """Opponent played something unexpected. Give guidance."""
    # Check if it's a known response we should handle
    setup = opening.get("setup_order", [])
    next_setup = None
    for m in setup:
        if m not in moves:
            next_setup = m
            break

    return {
        "suggested_move": next_setup,
        "idea": f"Your opponent played {opponent_move} — not the most common, but don't worry. Stick to your plan.",
        "plan": f"Continue with your setup: {next_setup or 'develop normally'}.",
        "is_in_book": False,
        "trap_warning": None,
        "golden_rule": None,
        "alternatives": [],
        "position_name": "Surprise Move",
        "middlegame_plan": None,
    }


def get_opening_summary(opening_key: str) -> Optional[Dict]:
    """Get a summary of an opening for the pre-game screen."""
    curriculum = _load_curriculum()
    opening = curriculum.get(opening_key)
    if not opening:
        return None

    return {
        "name": opening.get("name"),
        "summary": opening.get("summary"),
        "golden_rules": opening.get("golden_rules", []),
        "setup_order": opening.get("setup_order", []),
        "trap_count": len(opening.get("traps", [])),
        "difficulty": opening.get("difficulty"),
    }
