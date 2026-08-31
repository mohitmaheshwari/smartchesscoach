"""
Opening Theory JSON Service
============================
Single source of truth for all opening theory data.
Loads from opening_curriculum.json via unified source.

Provides:
- Full lesson move sequences (10-15+ moves deep)
- Critical position data with explanations
- Variation listings per opening
- Rich teaching context for each move

MIGRATED: now uses opening_unified_source.py
"""

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)

_THEORY_DATA: Optional[Dict] = None


def _load_theory():
    """Load theory data from unified source once."""
    global _THEORY_DATA
    if _THEORY_DATA is not None:
        return
    try:
        from services.opening_unified_source import get_unified_source
        source = get_unified_source()
        _THEORY_DATA = source.get_all_openings()
        logger.info(f"Loaded opening theory: {list(_THEORY_DATA.keys())}")
    except Exception as e:
        logger.error(f"Failed to load opening theory: {e}")
        _THEORY_DATA = {}


def get_all_opening_keys() -> List[str]:
    """Get all opening keys available in the theory database."""
    _load_theory()
    return list(_THEORY_DATA.keys())


def resolve_opening_key(opening_key: str) -> Optional[str]:
    """Resolve public underscore/hyphen aliases to the canonical JSON key."""
    _load_theory()
    for candidate in (
        opening_key,
        opening_key.replace("-", "_"),
        opening_key.replace("_", "-"),
    ):
        if candidate in _THEORY_DATA:
            return candidate
    return None


def get_opening_theory(opening_key: str) -> Optional[Dict]:
    """Get full theory data for an opening."""
    _load_theory()
    # Normalize: try as-is, then with underscores, then with hyphens
    resolved = resolve_opening_key(opening_key)
    return _THEORY_DATA.get(resolved) if resolved else None


def get_available_variations(opening_key: str) -> List[Dict]:
    """Get list of available variations for an opening."""
    _load_theory()
    resolved = resolve_opening_key(opening_key)
    if not resolved:
        return []
    from services.curriculum_content_validator import is_content_publishable
    if not is_content_publishable("openings", resolved):
        return []
    opening = _THEORY_DATA[resolved]
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
    resolved = resolve_opening_key(opening_key)
    if not resolved:
        return None
    from services.curriculum_content_validator import is_content_publishable
    if not is_content_publishable("openings", resolved):
        return None
    opening = _THEORY_DATA[resolved]

    main_line = opening.get("main_line", []) or _derive_guided_tree_line(opening)
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


def get_lesson_move_steps(
    opening_key: str,
    variation_key: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Return a playable lesson line with non-empty authored teaching copy."""
    resolved = resolve_opening_key(opening_key)
    lesson = get_variation_lesson_moves(opening_key, variation_key)
    if not resolved or not lesson:
        return []
    opening = _THEORY_DATA[resolved]
    if variation_key is None and opening.get("tree"):
        tree_steps = _derive_guided_tree_steps(opening)
        if tree_steps:
            return tree_steps
    move_ideas = opening.get("move_ideas") or {}
    common = opening.get("common_learnings") or opening.get("golden_rules") or []
    fallback_rule = str(common[0]) if common else ""
    steps: List[Dict[str, str]] = []

    for index, move in enumerate(lesson.get("moves", [])):
        authored = move_ideas.get(move) or {}
        explanation = str(authored.get("idea") or "").strip()
        if not explanation:
            context = get_move_teaching_context(
                resolved,
                variation_key,
                index,
                move,
            ) or {}
            explanation = str(
                context.get("idea")
                or context.get("why_good")
                or context.get("key_decision")
                or ""
            ).strip()
        if not explanation:
            side_plan = (
                lesson.get("white_plan")
                if index % 2 == 0
                else lesson.get("black_plan")
            )
            explanation = str(side_plan or fallback_rule).strip()
        steps.append(
            {
                "move": move,
                "explanation": explanation,
                "side": "white" if index % 2 == 0 else "black",
            }
        )
    return steps


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
    resolved = resolve_opening_key(opening_key)
    opening = _THEORY_DATA.get(resolved) if resolved else None
    if not opening:
        return None

    return _find_move_context_in_opening(opening, move_san)


def _derive_guided_tree_line(opening: Dict) -> List[str]:
    """Choose one authored, legal path through an interactive opening tree.

    Some early lessons were authored as a response tree rather than a flat
    ``main_line``.  The lesson page and practice board need one concrete path,
    so use insertion order (the author's primary branch) and preserve the
    tree's prescribed ``next`` moves.  This is a projection of the canonical
    lesson, not a second opening database.
    """
    tree = opening.get("tree") or {}
    if not isinstance(tree, dict) or not tree:
        return []

    board = chess.Board()
    curriculum_color = str(opening.get("color") or "white").lower()
    curriculum_turn = chess.WHITE if curriculum_color == "white" else chess.BLACK
    first_san, node = next(iter(tree.items()))
    try:
        board.push_san(str(first_san))
    except ValueError:
        return []

    moves = [str(first_san)]
    for _ in range(40):
        if not isinstance(node, dict):
            break

        if board.turn == curriculum_turn and node.get("next"):
            prescribed = str(node["next"])
            try:
                board.push_san(prescribed)
            except ValueError:
                break
            moves.append(prescribed)

        responses = node.get("responses") or {}
        if not isinstance(responses, dict) or not responses:
            break

        selected = None
        for response_san, child in responses.items():
            candidate = board.copy(stack=False)
            try:
                candidate.push_san(str(response_san))
            except ValueError:
                continue
            selected = (str(response_san), child, candidate)
            break
        if not selected:
            break
        response_san, node, board = selected
        moves.append(response_san)

    return moves


def _derive_guided_tree_steps(opening: Dict) -> List[Dict[str, str]]:
    """Project the primary tree path with the explanation authored at each node."""
    tree = opening.get("tree") or {}
    if not isinstance(tree, dict) or not tree:
        return []

    board = chess.Board()
    curriculum_color = str(opening.get("color") or "white").lower()
    curriculum_turn = chess.WHITE if curriculum_color == "white" else chess.BLACK
    first_san, node = next(iter(tree.items()))
    try:
        board.push_san(str(first_san))
    except ValueError:
        return []

    first_explanation = ""
    if isinstance(node, dict):
        first_explanation = str(
            node.get("idea")
            or node.get("idea_opponent")
            or node.get("right_feedback")
            or node.get("hint")
            or ""
        ).strip()
    steps = [{
        "move": str(first_san),
        "explanation": first_explanation,
        "side": "white",
    }]

    for _ in range(40):
        if not isinstance(node, dict):
            break
        if board.turn == curriculum_turn and node.get("next"):
            prescribed = str(node["next"])
            try:
                board.push_san(prescribed)
            except ValueError:
                break
            steps.append({
                "move": prescribed,
                "explanation": str(
                    node.get("right_feedback")
                    or node.get("idea")
                    or node.get("hint")
                    or ""
                ).strip(),
                "side": "white" if board.turn == chess.BLACK else "black",
            })

        responses = node.get("responses") or {}
        if not isinstance(responses, dict) or not responses:
            break
        selected = None
        for response_san, child in responses.items():
            candidate = board.copy(stack=False)
            try:
                candidate.push_san(str(response_san))
            except ValueError:
                continue
            selected = (str(response_san), child, candidate)
            break
        if not selected:
            break
        response_san, child, board = selected
        child_data = child if isinstance(child, dict) else {}
        steps.append({
            "move": response_san,
            "explanation": str(
                child_data.get("idea_opponent")
                or child_data.get("idea")
                or child_data.get("name")
                or ""
            ).strip(),
            "side": "white" if board.turn == chess.BLACK else "black",
        })
        node = child

    move_ideas = opening.get("move_ideas") or {}
    for step in steps:
        if step["explanation"]:
            continue
        authored = move_ideas.get(step["move"]) or {}
        step["explanation"] = str(authored.get("idea") or "").strip()
    return steps


def get_all_lesson_move_paths(opening_key: str) -> List[List[Dict[str, str]]]:
    """Return every legal authored lesson branch from the canonical record."""
    _load_theory()
    resolved = resolve_opening_key(opening_key)
    if not resolved:
        return []
    from services.curriculum_content_validator import is_content_publishable
    if not is_content_publishable("openings", resolved):
        return []
    opening = _THEORY_DATA[resolved]

    def legal_identity(path: List[Dict[str, str]]) -> tuple[str, ...]:
        board = chess.Board()
        identity: List[str] = []
        for step in path:
            try:
                move = board.parse_san(str(step.get("move") or ""))
            except ValueError:
                return ()
            identity.append(move.uci())
            board.push(move)
        return tuple(identity)

    def deduplicate_legal(paths: List[List[Dict[str, str]]]) -> List[List[Dict[str, str]]]:
        unique: Dict[tuple[str, ...], List[Dict[str, str]]] = {}
        for path in paths:
            identity = legal_identity(path)
            if path and identity:
                unique[identity] = path
        return list(unique.values())

    tree = opening.get("tree") or {}
    if not isinstance(tree, dict) or not tree:
        variation_keys = list((opening.get("variations") or {}).keys())
        candidates = variation_keys or [None]
        paths = [get_lesson_move_steps(resolved, key) for key in candidates]
        return deduplicate_legal(paths)

    curriculum_color = str(opening.get("color") or "white").lower()
    curriculum_turn = chess.WHITE if curriculum_color == "white" else chess.BLACK
    move_ideas = opening.get("move_ideas") or {}
    completed: List[List[Dict[str, str]]] = []

    def explanation(node: Dict, move_san: str, opponent: bool) -> str:
        node = node if isinstance(node, dict) else {}
        text = (
            node.get("idea_opponent") if opponent else
            node.get("right_feedback") or node.get("idea") or node.get("hint")
        )
        if not text:
            text = (move_ideas.get(move_san) or {}).get("idea")
        return str(text or "").strip()

    def walk(board: chess.Board, node: Dict, steps: List[Dict[str, str]], depth: int) -> None:
        if depth >= 40 or not isinstance(node, dict):
            completed.append(steps)
            return
        current_board = board.copy(stack=False)
        current_steps = list(steps)
        if current_board.turn == curriculum_turn and node.get("next"):
            move_san = str(node["next"])
            side = "white" if current_board.turn == chess.WHITE else "black"
            try:
                current_board.push_san(move_san)
            except ValueError:
                return
            current_steps.append({
                "move": move_san,
                "explanation": explanation(node, move_san, False),
                "side": side,
            })

        responses = node.get("responses") or {}
        if not isinstance(responses, dict) or not responses:
            completed.append(current_steps)
            return
        advanced = False
        for response_san, child in responses.items():
            candidate = current_board.copy(stack=False)
            side = "white" if candidate.turn == chess.WHITE else "black"
            try:
                candidate.push_san(str(response_san))
            except ValueError:
                continue
            child_data = child if isinstance(child, dict) else {}
            walk(
                candidate,
                child_data,
                current_steps + [{
                    "move": str(response_san),
                    "explanation": explanation(child_data, str(response_san), True),
                    "side": side,
                }],
                depth + 1,
            )
            advanced = True
        if not advanced:
            completed.append(current_steps)

    for first_san, first_node in tree.items():
        board = chess.Board()
        side = "white" if board.turn == chess.WHITE else "black"
        try:
            board.push_san(str(first_san))
        except ValueError:
            continue
        node_data = first_node if isinstance(first_node, dict) else {}
        walk(board, node_data, [{
            "move": str(first_san),
            "explanation": explanation(
                node_data, str(first_san), side != curriculum_color
            ),
            "side": side,
        }], 0)

    # Mature lessons can contain both an interactive response tree and
    # separately authored variations.  Those variations carry additional
    # decisions and must be available to replay and proof generation too.
    for variation_key in (opening.get("variations") or {}):
        variation_path = get_lesson_move_steps(resolved, variation_key)
        if variation_path:
            completed.append(variation_path)

    return deduplicate_legal(completed)


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
