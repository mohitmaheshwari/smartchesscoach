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


def get_opening_guidance(opening_key: str, moves_played: List[str], user_color: str, assessment: Dict = None) -> Optional[Dict]:
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
    curriculum_color = opening.get("color", "white")  # The color this curriculum teaches
    user_plays_curriculum_color = (user_color == curriculum_color)

    # Handle empty moves — game just started
    if not moves_played:
        first_move = list(tree.keys())[0] if tree else None
        if first_move:
            first_node = tree[first_move]
            if user_plays_curriculum_color:
                # User is White learning London — they play d4
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
            else:
                # User is Black — coach (White) plays first. User waits.
                return {
                    "mode": "waiting",
                    "hint": f"Coach will play {first_move} to start the {opening.get('name', 'opening')}. Watch and get ready.",
                    "plan": "",
                    "is_in_book": True,
                    "position_name": opening.get("name"),
                }
        return None

    # Step 1: First move must be the curriculum's opening move
    first_move = moves_played[0]
    expected_first = list(tree.keys())[0] if tree else None

    if first_move != expected_first:
        if user_plays_curriculum_color:
            return _off_book_guidance(opening, moves_played, 0, user_color)
        else:
            # Coach played something unexpected — shouldn't happen
            return _opponent_surprise_guidance(opening, {}, first_move, moves_played, user_color)

    node = tree[first_move]
    if node.get("name"):
        position_name = node["name"]

    # Step 2: Walk remaining moves
    # The tree alternates: first_move(White) → responses(Black) → next(White) → responses(Black)...
    # When user is White: our moves match "next", opponent matches "responses" keys
    # When user is Black: our moves match "responses" keys, opponent matches "next"
    for i in range(1, len(moves_played)):
        move = moves_played[i]
        is_our_move = (i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black")

        if user_plays_curriculum_color:
            # User plays White (curriculum color)
            if not is_our_move:
                # Opponent (Black) move — match against responses
                responses = node.get("responses", {})
                if move in responses:
                    node = responses[move]
                    if node.get("name"):
                        position_name = node["name"]
                else:
                    return _opponent_surprise_guidance(opening, responses, move, moves_played, user_color)
            else:
                # Our (White) move — should match "next"
                expected = node.get("next")
                if expected and move == expected:
                    pass
                else:
                    return _off_book_guidance(opening, moves_played, i, user_color)
        else:
            # User plays Black (opposite of curriculum color)
            if is_our_move:
                # Our (Black) move — match against responses (Black's moves in the tree)
                responses = node.get("responses", {})
                if move in responses:
                    node = responses[move]
                    if node.get("name"):
                        position_name = node["name"]
                else:
                    return _off_book_guidance(opening, moves_played, i, user_color)
            else:
                # Coach (White) move — should match "next"
                expected = node.get("next")
                if expected and move == expected:
                    pass
                else:
                    return _opponent_surprise_guidance(opening, {}, move, moves_played, user_color)

    # We're at a node — build guidance for the NEXT move to be played
    if node:
        total_moves = len(moves_played)
        next_is_ours = (total_moves % 2 == 0 and user_color == "white") or (total_moves % 2 == 1 and user_color == "black")

        if next_is_ours:
            if user_plays_curriculum_color:
                # User plays curriculum color (White) — our move = "next"
                next_move = node.get("next")
                hint = node.get("hint", "What's the best move here?")
                plan = node.get("plan", "")
                right_feedback = node.get("right_feedback", f"Good — {next_move} was the right move.")
                wrong_feedback = node.get("wrong_feedback", f"The curriculum move was {next_move}.")
            else:
                # User plays opposite (Black) — our move = pick from responses
                responses = node.get("responses", {})
                if not responses:
                    # No known responses — we're past the tree
                    next_move = None
                    hint = "Opening done. What feels right here?"
                    plan = ""
                    right_feedback = "Good choice."
                    wrong_feedback = "Think about this position more carefully."
                else:
                    # Pick the main/first response as the expected move
                    main_response = list(responses.keys())[0]
                    resp_node = responses[main_response]
                    next_move = main_response
                    hint = resp_node.get("hint", node.get("hint", f"What's the best response here?"))
                    plan = resp_node.get("plan", node.get("plan", ""))
                    right_feedback = resp_node.get("right_feedback", f"Good — {main_response} is solid.")
                    wrong_feedback = resp_node.get("wrong_feedback", f"The best response here is {main_response}.")

            # Adapt based on assessment — if user already knows this move, lighten the hint
            mastered_moves = set(assessment.get("moves_mastered", [])) if assessment else set()
            pos_key = f"move_{(total_moves // 2) + 1}"
            user_knows_this = any(pos_key in m for m in mastered_moves)

            if user_knows_this:
                # They know this — quick confirmation instead of full hint
                hint = "You know this one. What do you play?"
                right_feedback = "Yep. You've got this down."
            
            # If this position is their WEAK spot, emphasize it
            weak_moves = assessment.get("weak_moves", []) if assessment else []
            is_weak_spot = False
            for w in weak_moves:
                if pos_key in str(w.get("position", "")):
                    is_weak_spot = True
                    wrong_moves_str = ", ".join(w.get("user_played", []))
                    hint = f"This is where you usually go wrong. Last time you played {wrong_moves_str}. Think carefully — what's the right move?"
                    wrong_feedback = f"You played this wrong {w.get('times_wrong', 0)} times before. The right move is {next_move}. {node.get('wrong_feedback', '')}"
                    break
        else:
            # It's opponent/coach's turn
            if user_plays_curriculum_color:
                # User is White — waiting for Black's response
                responses = node.get("responses", {})
                common_responses = list(responses.keys())[:3]
                plan = node.get("plan", "")
                if common_responses:
                    return {
                        "mode": "waiting",
                        "hint": f"Waiting for opponent. They'll likely play: {', '.join(common_responses)}.",
                        "plan": plan or "Watch what they do.",
                        "is_in_book": True,
                        "position_name": position_name,
                    }
            else:
                # User is Black — waiting for coach (White) to play "next"
                next_move = node.get("next")
                if next_move:
                    return {
                        "mode": "waiting",
                        "hint": f"Coach will play {next_move}. Get ready for your response.",
                        "plan": node.get("plan", ""),
                        "is_in_book": True,
                        "position_name": position_name,
                    }
            # No known responses — opening book ended, transition to middlegame
            mp = opening.get("middlegame_plans", {})
            mid_plan = mp.get("when_equal", {}).get("plan", "Develop pieces and look for a plan.")
            return {
                "mode": "waiting",
                "hint": "Opening phase done. See how they respond — then we'll figure out the plan.",
                "plan": mid_plan,
                "is_in_book": False,
                "position_name": "Middlegame",
            }

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
            "is_weak_spot": is_weak_spot if 'is_weak_spot' in dir() else False,
            "user_knows_this": user_knows_this if 'user_knows_this' in dir() else False,
            "trap_warning": trap_warning,
            "golden_rule": golden_rule,
            "alternatives": alternatives[:2],
            "position_name": position_name,
            "middlegame_plan": middlegame_plan,
        }

    # Tree ended but game continues — transition to middlegame guidance
    if node:
        setup = opening.get("setup_order", [])
        played_moves = set(moves_played)
        next_setup = None
        for m in setup:
            if m not in played_moves:
                next_setup = m
                break

        mp = opening.get("middlegame_plans", {})
        plan = mp.get("when_equal", {}).get("plan", "Develop your remaining pieces and look for a plan.")
        ideas = mp.get("when_equal", {}).get("ideas", [])
        tips = opening.get("endgame_tips", [])

        total_moves = len(moves_played)
        if total_moves >= 24 and tips:
            plan = tips[0]

        return {
            "mode": "think",
            "hint": "Opening phase is done. What's your plan now?" if not next_setup else f"You still haven't played {next_setup}. Is now a good time?",
            "plan": plan,
            "expected_move": next_setup,
            "right_feedback": "Good choice." if next_setup else "Keep developing your plan.",
            "wrong_feedback": f"{next_setup} was worth considering." if next_setup else "Think about your long-term plan.",
            "is_in_book": False,
            "trap_warning": None,
            "golden_rule": ideas[0] if ideas else None,
            "alternatives": [],
            "position_name": "Middlegame",
            "middlegame_plan": plan,
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
        "mode": "think",
        "hint": "That's off the main line — but that's OK. What's the next piece in your setup that needs to come out?",
        "plan": general_plan,
        "expected_move": suggested,
        "right_feedback": "Good — back on track." if suggested else "Keep developing.",
        "wrong_feedback": f"Consider {suggested} — it's part of your standard setup." if suggested else "Think about the position.",
        "is_in_book": False,
        "trap_warning": None,
        "golden_rule": opening.get("golden_rules", [""])[0] if opening.get("golden_rules") else None,
        "alternatives": [],
        "position_name": "Off Book",
        "middlegame_plan": general_plan,
    }


def _opponent_surprise_guidance(opening: Dict, current_branch: Dict, opponent_move: str, moves: List[str], user_color: str) -> Dict:
    """Opponent played something unexpected. Give guidance."""
    setup = opening.get("setup_order", [])
    next_setup = None
    for m in setup:
        if m not in moves:
            next_setup = m
            break

    mp = opening.get("middlegame_plans", {})
    plan = mp.get("when_equal", {}).get("plan", "Develop your pieces and control the center.")

    if next_setup:
        hint = f"They played {opponent_move} — unusual, but don't worry. Think about your setup. What piece needs to come out next?"
    else:
        hint = f"They played {opponent_move}. Opening is done — what's your plan for the middlegame?"

    return {
        "mode": "think",
        "hint": hint,
        "plan": plan,
        "expected_move": next_setup,
        "right_feedback": "Good choice." if next_setup else "Keep developing your plan.",
        "wrong_feedback": f"Consider {next_setup} — stick to your setup." if next_setup else "Think about the position carefully.",
        "is_in_book": False,
        "trap_warning": None,
        "golden_rule": None,
        "alternatives": [],
        "position_name": "Off Book",
        "middlegame_plan": plan,
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
