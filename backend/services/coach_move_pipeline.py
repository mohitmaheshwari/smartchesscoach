"""
Coach Move Pipeline — Broken down from _process_move_and_respond
==================================================================

Three clear paths, each a separate function:
1. curriculum_coach_move() — when curriculum is active (fast, no Stockfish)
2. simple_coach_move() — fallback with low-depth Stockfish
3. full_coach_move() — the heavy path with analysis + coaching + pedagogy

All paths end by calling _apply_coach_move() to update the session.
"""

import logging
import random
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def get_curriculum_coach_move(db, session_doc: Dict, user_color: str) -> Optional[str]:
    """
    Get the coach's move from the curriculum tree.
    Returns the SAN move or None if curriculum doesn't apply.
    """
    teaching_opening = session_doc.get("teaching_opening")
    if not teaching_opening:
        return None

    from services.opening_curriculum_engine import _load_curriculum

    curriculum = _load_curriculum()
    opening_data = curriculum.get(teaching_opening, {})
    if not opening_data:
        return None

    curriculum_color = opening_data.get("color", "white")
    user_plays_curriculum = (user_color == curriculum_color)

    move_history = session_doc.get("move_history", [])
    moves_san = [m.get("move", "") for m in move_history]

    tree = opening_data.get("tree", {})
    if not tree:
        return None

    first_key = list(tree.keys())[0]

    if user_plays_curriculum:
        # User plays White — coach plays Black (pick from responses)
        node = None
        if moves_san and moves_san[0] == first_key:
            node = tree[first_key]
            for idx in range(1, len(moves_san)):
                mv = moves_san[idx]
                is_user = (idx % 2 == 0)
                if not is_user:
                    responses = node.get("responses", {})
                    if mv in responses:
                        node = responses[mv]
                    else:
                        break
                else:
                    if node.get("next") == mv:
                        pass
                    else:
                        break

        if node:
            responses = node.get("responses", {})
            if responses:
                response_keys = list(responses.keys())
                # 30% chance to play trap lines
                traps = opening_data.get("traps", [])
                trap_moves = [t.get("trigger_move") for t in traps if t.get("trigger_move") in response_keys]

                if trap_moves and random.random() < 0.3:
                    move = random.choice(trap_moves)
                    logger.info(f"[CURRICULUM] Coach plays trap: {move}")
                    return move
                else:
                    move = response_keys[0]
                    logger.info(f"[CURRICULUM] Coach plays main line: {move}")
                    return move
    else:
        # User plays Black — coach plays White (use "next" moves)
        if not moves_san:
            move = first_key
            logger.info(f"[CURRICULUM] Coach opens with: {move}")
            return move

        if moves_san[0] == first_key:
            node = tree[first_key]
            for idx in range(1, len(moves_san)):
                mv = moves_san[idx]
                is_black = (idx % 2 == 1)
                if is_black:
                    responses = node.get("responses", {})
                    if mv in responses:
                        node = responses[mv]
                    else:
                        break
                else:
                    if node.get("next") == mv:
                        pass
                    else:
                        break

            if node and node.get("next"):
                move = node["next"]
                logger.info(f"[CURRICULUM] Coach plays curriculum: {move}")
                return move

    return None


async def get_simple_coach_move(db, fen: str, user_rating: int) -> Optional[str]:
    """
    Simple Stockfish move at low depth.
    Used as fallback when curriculum doesn't have a move.
    """
    try:
        from coach_play.coach_opponent import CoachOpponent
        opponent = CoachOpponent(user_rating=user_rating)
        opponent.depth = 6
        opponent.skill_level = min(opponent.skill_level, 8)
        move = await opponent.get_move(fen)
        logger.info(f"[SIMPLE] Coach plays: {move}")
        return move
    except Exception as e:
        logger.error(f"[SIMPLE] Failed: {e}")
        return None
