"""
Opening Theory JSON Service
============================
Single source of truth for all opening theory data.
Loads from /data/coaching/opening_theory_tree.json.

Provides:
- Full lesson move sequences (10-15+ moves deep)
- Critical position data with explanations
- Variation listings per opening
- Rich teaching context for each move
"""

import json
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_THEORY_DATA: Optional[Dict] = None
_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json")


def _load_theory():
    """Load the JSON theory file once."""
    global _THEORY_DATA
    if _THEORY_DATA is not None:
        return
    try:
        with open(_JSON_PATH, "r") as f:
            _THEORY_DATA = json.load(f)
        # Remove metadata key
        _THEORY_DATA.pop("_meta", None)
        logger.info(f"Loaded opening theory: {list(_THEORY_DATA.keys())}")
    except Exception as e:
        logger.error(f"Failed to load opening theory JSON: {e}")
        _THEORY_DATA = {}


def get_all_opening_keys() -> List[str]:
    """Get all opening keys available in the theory database."""
    _load_theory()
    return list(_THEORY_DATA.keys())


def get_opening_theory(opening_key: str) -> Optional[Dict]:
    """Get full theory data for an opening."""
    _load_theory()
    # Normalize: try as-is, then with underscores, then with hyphens
    result = _THEORY_DATA.get(opening_key)
    if not result:
        result = _THEORY_DATA.get(opening_key.replace("-", "_"))
    if not result:
        result = _THEORY_DATA.get(opening_key.replace("_", "-"))
    return result


def get_available_variations(opening_key: str) -> List[Dict]:
    """Get list of available variations for an opening."""
    _load_theory()
    opening = _THEORY_DATA.get(opening_key) or _THEORY_DATA.get(opening_key.replace("-", "_"))
    if not opening:
        return []

    variations = opening.get("variations", {})
    result = []
    for var_key, var_data in variations.items():
        main_line = opening.get("main_line", [])
        moves_from_parent = var_data.get("moves_from_parent", [])
        continuation = var_data.get("continuation", [])
        total_moves = len(main_line) + len(moves_from_parent) + len(continuation)

        result.append({
            "key": var_key,
            "name": var_data.get("name", var_key),
            "total_moves": total_moves,
            "white_plan": var_data.get("white_plan", ""),
            "black_plan": var_data.get("black_plan", ""),
        })
    return result


def get_variation_lesson_moves(opening_key: str, variation_key: Optional[str] = None) -> Optional[Dict]:
    """
    Get the full lesson move sequence for a variation.
    
    Returns:
        Dict with:
        - moves: Full ordered list of moves (10-15+)
        - variation_name: Name of the variation
        - white_plan: White's strategic plan
        - black_plan: Black's strategic plan
        - common_learnings: Key takeaways
        - critical_positions: Teaching data keyed by move index
    """
    _load_theory()
    opening = _THEORY_DATA.get(opening_key) or _THEORY_DATA.get(opening_key.replace("-", "_"))
    if not opening:
        return None

    main_line = opening.get("main_line", [])
    variations = opening.get("variations", {})

    # If no variation specified, pick the first one (or return just the main line)
    if not variation_key:
        if variations:
            variation_key = next(iter(variations))
        else:
            # No variations, just return the main line
            return {
                "moves": main_line,
                "variation_name": opening.get("name", "Main Line"),
                "white_plan": opening.get("white_plan", ""),
                "black_plan": opening.get("black_plan", ""),
                "common_learnings": opening.get("common_learnings", []),
                "critical_positions": _build_critical_position_index(opening, main_line, 0),
            }

    var_data = variations.get(variation_key)
    if not var_data:
        return None

    # Build the full move sequence: main_line + moves_from_parent + continuation
    moves_from_parent = var_data.get("moves_from_parent", [])
    continuation = var_data.get("continuation", [])
    full_moves = main_line + moves_from_parent + continuation

    # Build critical position index (maps move indices to teaching data)
    critical_positions = _build_critical_position_index(opening, full_moves, 0)
    # Also include variation-level critical positions
    var_critical = _build_critical_position_index_from_variation(var_data, full_moves, len(main_line))

    critical_positions.update(var_critical)

    return {
        "moves": full_moves,
        "variation_name": var_data.get("name", variation_key),
        "white_plan": var_data.get("white_plan", opening.get("white_plan", "")),
        "black_plan": var_data.get("black_plan", opening.get("black_plan", "")),
        "common_learnings": opening.get("common_learnings", []),
        "critical_positions": critical_positions,
    }


def get_move_teaching_context(opening_key: str, variation_key: str, move_index: int, move_san: str) -> Optional[Dict]:
    """
    Get rich teaching context for a specific move in a lesson.
    
    Returns context like: "This is the key French idea - attack the base of the chain!"
    """
    lesson = get_variation_lesson_moves(opening_key, variation_key)
    if not lesson:
        return None

    critical = lesson.get("critical_positions", {})
    
    # Check if this move index has critical position data
    context = critical.get(move_index)
    if context:
        return context

    # Check if the move itself is referenced as a best or mistake move
    # in any of the opening's critical positions
    _load_theory()
    opening = _THEORY_DATA.get(opening_key)
    if not opening:
        return None

    return _find_move_context_in_opening(opening, move_san)


def _build_critical_position_index(opening_data: Dict, full_moves: List[str], offset: int) -> Dict[int, Dict]:
    """
    Map critical positions to move indices in the lesson sequence.
    
    Scans the opening's critical_positions and figures out at which move index
    each critical position is reached.
    """
    index = {}
    critical_positions = opening_data.get("critical_positions", {})

    for cp_key, cp_data in critical_positions.items():
        # Try to figure out which move index triggers this critical position
        # by matching the key name pattern (e.g., "after_Bc4" -> find Bc4 in moves)
        key_parts = cp_key.replace("after_", "").split("_")
        for i, move in enumerate(full_moves):
            move_clean = move.replace("+", "").replace("#", "")
            if move_clean in key_parts or move_clean.lower() in [p.lower() for p in key_parts]:
                # This critical position is reached after this move
                teaching = _extract_teaching_from_critical(cp_data)
                if teaching:
                    index[i] = teaching
                break

    return index


def _build_critical_position_index_from_variation(var_data: Dict, full_moves: List[str], offset: int) -> Dict[int, Dict]:
    """Map variation-level critical positions to move indices."""
    index = {}
    critical_positions = var_data.get("critical_positions", {})

    for cp_key, cp_data in critical_positions.items():
        key_parts = cp_key.replace("after_", "").replace("_", " ").split()
        for i in range(offset, len(full_moves)):
            move = full_moves[i]
            move_clean = move.replace("+", "").replace("#", "")
            if move_clean.lower() in [p.lower() for p in key_parts]:
                teaching = _extract_teaching_from_critical(cp_data)
                if teaching:
                    index[i] = teaching
                break

    return index


def _extract_teaching_from_critical(cp_data: Dict) -> Optional[Dict]:
    """Extract teaching content from a critical position entry."""
    key_decision = cp_data.get("key_decision", "")
    
    # Collect best moves info
    best_moves = {}
    for key in ["best_moves", "best_moves_white", "best_moves_black"]:
        if key in cp_data:
            best_moves.update(cp_data[key])
    
    # Collect mistake info
    mistake_moves = cp_data.get("mistake_moves", {})

    if not key_decision and not best_moves and not mistake_moves:
        return None

    return {
        "key_decision": key_decision,
        "best_moves": {
            move: {
                "idea": data.get("idea", ""),
                "why_good": data.get("why_good", ""),
            }
            for move, data in best_moves.items()
        },
        "mistake_moves": {
            move: {
                "why_bad": data.get("why_bad", ""),
                "consequence": data.get("consequence", ""),
                "learning": data.get("learning", ""),
            }
            for move, data in mistake_moves.items()
        },
    }


def _find_move_context_in_opening(opening_data: Dict, move_san: str) -> Optional[Dict]:
    """Search all critical positions for context about a specific move."""
    move_clean = move_san.replace("+", "").replace("#", "").lower()
    
    # Check opening-level critical positions
    for cp_data in opening_data.get("critical_positions", {}).values():
        for key in ["best_moves", "best_moves_white", "best_moves_black"]:
            best = cp_data.get(key, {})
            for move, data in best.items():
                if move.lower() == move_clean:
                    return {
                        "is_best_move": True,
                        "idea": data.get("idea", ""),
                        "why_good": data.get("why_good", ""),
                    }
        
        for move, data in cp_data.get("mistake_moves", {}).items():
            if move.lower() == move_clean:
                return {
                    "is_mistake": True,
                    "why_bad": data.get("why_bad", ""),
                    "learning": data.get("learning", ""),
                }

    # Check variation-level critical positions
    for var_data in opening_data.get("variations", {}).values():
        for cp_data in var_data.get("critical_positions", {}).values():
            for key in ["best_moves", "best_moves_white", "best_moves_black"]:
                best = cp_data.get(key, {})
                for move, data in best.items():
                    if move.lower() == move_clean:
                        return {
                            "is_best_move": True,
                            "idea": data.get("idea", ""),
                            "why_good": data.get("why_good", ""),
                        }

    return None
