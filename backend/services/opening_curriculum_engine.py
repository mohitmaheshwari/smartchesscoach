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

    # Walk the tree following moves played.
    #
    # Tree structure alternates:
    #   Level 0 keys = White's first move (d4)
    #   responses keys = Black's replies (d5, Nf6...)
    #   "next" field = White's next move (Bf4)
    #   responses keys under that = Black's replies to "next" (Nf6, c5...)
    #
    # So the pattern for a White curriculum is:
    #   Move 0 (W): match key at top level
    #   Move 1 (B): match key in responses
    #   Move 2 (W): should equal current node's "next"
    #   Move 3 (B): match key in current node's responses
    #   Move 4 (W): should equal current node's "next"
    #   ... and so on

    node = None
    position_name = opening.get("name", "Opening")

    # Handle empty moves — game just started
    if not moves_played:
        first_move = list(tree.keys())[0] if tree else None
        if first_move:
            first_node = tree[first_move]
            return {
                "mode": "think",
                "hint": first_node.get("hint", "What's the best way to start?"),
                "plan": first_node.get("plan", ""),
                "expected_move": first_move,
                "right_feedback": first_node.get("right_feedback", f"Good — {first_move} is the right start."),
                "wrong_feedback": first_node.get("wrong_feedback", f"The curriculum starts with {first_move}."),
                "is_in_book": True,
                "trap_warning": None,
                "golden_rule": opening.get("golden_rules", [""])[0] if opening.get("golden_rules") else None,
                "alternatives": [],
                "position_name": opening.get("name"),
                "middlegame_plan": None,
            }
        return None

    # Step 1: Match our first move at the top level
    first_move = moves_played[0]
    is_first_ours = (user_color == "white")  # In a White curriculum, move 0 is ours

    if is_first_ours:
        if first_move not in tree:
            return _off_book_guidance(opening, moves_played, 0, user_color)
        node = tree[first_move]
        if node.get("name"):
            position_name = node["name"]
    else:
        # We're Black playing a White curriculum — shouldn't happen normally
        return _off_book_guidance(opening, moves_played, 0, user_color)

    # Step 2: Walk remaining moves
    for i in range(1, len(moves_played)):
        move = moves_played[i]
        is_our_move = (i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black")

        if not is_our_move:
            # Opponent's move — look in current node's "responses"
            responses = node.get("responses", {})
            if move in responses:
                node = responses[move]
                if node.get("name"):
                    position_name = node["name"]
            else:
                return _opponent_surprise_guidance(opening, responses, move, moves_played, user_color)
        else:
            # Our move — should match current node's "next" field
            expected = node.get("next")
            if expected and move == expected:
                # Good — we played the curriculum move. Stay on the same node
                # (the node's responses are still the opponent's next possible replies)
                pass
            else:
                # We played something different from the curriculum suggestion
                return _off_book_guidance(opening, moves_played, i, user_color)

    # We're at a node — build guidance for the NEXT move to be played
    if node:
        total_moves = len(moves_played)
        next_is_ours = (total_moves % 2 == 0 and user_color == "white") or (total_moves % 2 == 1 and user_color == "black")

        if next_is_ours:
            # It's our turn — give a HINT (not the answer)
            next_move = node.get("next")
            hint = node.get("hint", "What's the best move here? Think about your plan.")
            plan = node.get("plan", "")
            right_feedback = node.get("right_feedback", f"Good — {next_move} was the right move.")
            wrong_feedback = node.get("wrong_feedback", f"The curriculum move was {next_move}.")
        else:
            # It's opponent's turn — tell user what to expect
            responses = node.get("responses", {})
            common_responses = list(responses.keys())[:3]
            plan = node.get("plan", "")
            if common_responses:
                return {
                    "mode": "waiting",
                    "hint": f"Waiting for opponent. They'll likely play: {', '.join(common_responses)}.",
                    "plan": plan or "Watch what they do and we'll guide you.",
                    "is_in_book": True,
                    "position_name": position_name,
                }
            return None

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

        # Build alternatives from current node's responses
        alternatives = []
        responses = node.get("responses", {})
        if isinstance(responses, dict):
            for alt_move, alt_node in responses.items():
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
            "mode": "think",
            "hint": hint,
            "plan": plan,
            "expected_move": next_move,
            "right_feedback": right_feedback,
            "wrong_feedback": wrong_feedback,
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
