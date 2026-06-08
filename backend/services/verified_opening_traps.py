"""Verified opening traps — loaded from opening_theory_tree.json.

All trap data lives in the JSON tree under each opening's "traps" array.
This file reads and indexes them, providing lookup functions.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


def _normalize(move: str) -> str:
    return (
        (move or "")
        .replace("+", "")
        .replace("#", "")
        .replace("!", "")
        .replace("?", "")
        .strip()
        .lower()
    )


@dataclass(frozen=True)
class VerifiedOpeningTrap:
    trap_id: str
    name: str
    opening_key: str
    opening_name: str
    variation_name: str
    setup_moves: List[str]
    full_line: List[str]
    trap_move: str
    explanation: str
    refutation: str
    victim_color: str
    trap_for: str
    difficulty: str
    category: str = "trap"


# ─── LOAD FROM JSON ──────────────────────────────────────────────

def _load_traps_from_json() -> Dict[str, VerifiedOpeningTrap]:
    """Load all traps from opening_theory_tree.json."""
    tree_path = os.path.join(os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json")
    registry = {}
    try:
        with open(tree_path, encoding="utf-8") as f:
            tree = json.load(f)
    except Exception as e:
        logger.warning(f"[TRAPS] Could not load opening_theory_tree.json: {e}")
        return registry

    for opening_key, opening in tree.items():
        if not isinstance(opening, dict) or opening_key.startswith("_"):
            continue
        traps_list = opening.get("traps", [])
        for trap_data in traps_list:
            trap_id = trap_data.get("trap_id", "")
            if not trap_id:
                continue
            try:
                trap = VerifiedOpeningTrap(
                    trap_id=trap_id,
                    name=trap_data.get("name", ""),
                    opening_key=opening_key,
                    opening_name=opening.get("name", ""),
                    variation_name=trap_data.get("variation", "") or "",
                    setup_moves=trap_data.get("setup_moves", []),
                    full_line=trap_data.get("full_line", []),
                    trap_move=trap_data.get("trap_move", ""),
                    explanation=trap_data.get("explanation", ""),
                    refutation=trap_data.get("refutation", ""),
                    victim_color=trap_data.get("victim_color", ""),
                    trap_for=trap_data.get("trap_for", ""),
                    difficulty=trap_data.get("difficulty", "beginner"),
                    category=trap_data.get("category", "trap"),
                )
                registry[trap_id] = trap
            except Exception as e:
                logger.warning(f"[TRAPS] Failed to load trap {trap_id}: {e}")

    logger.info(f"[TRAPS] Loaded {len(registry)} traps from JSON")
    return registry


def _load_traps_from_library_json() -> Dict[str, VerifiedOpeningTrap]:
    """Load the admin-editable trap content from data/traps.json (the real ~54
    traps incl. the Fried Liver) and map it into the VerifiedOpeningTrap shape so
    the PWC move-flow detection (get_applicable_traps_for_moves) actually finds
    traps. The legacy opening_theory_tree.json source above is currently empty.
    (Mohit 2026-06-09: traps weren't wired — detection read the empty file while
    the real content sat unused in traps.json.) Existing data only — no new traps."""
    import ast
    path = os.path.join(os.path.dirname(__file__), "..", "data", "traps.json")
    registry: Dict[str, VerifiedOpeningTrap] = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"[TRAPS] Could not load traps.json: {e}")
        return registry
    if not isinstance(data, dict):
        return registry

    def _as_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = ast.literal_eval(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return []

    for raw_key, traps in data.items():
        if not isinstance(traps, list) or raw_key.startswith("_"):
            continue
        opening_key = raw_key.replace("-", "_")          # 'italian-game' -> 'italian_game'
        opening_name = raw_key.replace("-", " ").title()  # -> 'Italian Game'
        for t in traps:
            if not isinstance(t, dict) or not t.get("name"):
                continue
            setup = _as_list(t.get("setup_moves"))
            trap_line = _as_list(t.get("trap_line"))
            line_moves = [m.get("move", "") for m in trap_line if isinstance(m, dict) and m.get("move")]
            trap_move = line_moves[0] if line_moves else ""
            trap_color = t.get("trap_color", "")
            victim = "black" if trap_color == "white" else "white" if trap_color == "black" else ""
            trap_id = f"{opening_key}_{t['name'].lower().replace(' ', '_')}"
            registry[trap_id] = VerifiedOpeningTrap(
                trap_id=trap_id,
                name=t["name"],
                opening_key=opening_key,
                opening_name=opening_name,
                variation_name="",
                setup_moves=setup,
                full_line=list(setup) + line_moves,
                trap_move=trap_move,
                explanation=t.get("description", ""),
                refutation=t.get("success_message", ""),
                victim_color=victim,
                trap_for=trap_color,
                difficulty=t.get("difficulty", "beginner"),
                category="trap",
            )
    logger.info(f"[TRAPS] Loaded {len(registry)} traps from traps.json")
    return registry


ALL_REGISTRY = _load_traps_from_json()
# The theory-tree source above is currently empty; the real admin-editable trap
# content lives in data/traps.json. Merge it so PWC trap detection actually fires.
ALL_REGISTRY.update(_load_traps_from_library_json())
VERIFIED_TRAP_REGISTRY = {k: v for k, v in ALL_REGISTRY.items() if v.category == "trap"}
OPENING_WARNINGS = {k: v for k, v in ALL_REGISTRY.items() if v.category == "warning"}


def get_verified_trap_registry() -> Dict[str, VerifiedOpeningTrap]:
    return VERIFIED_TRAP_REGISTRY


def get_all_traps_and_warnings() -> Dict[str, VerifiedOpeningTrap]:
    return ALL_REGISTRY


def get_verified_trap(trap_id: str) -> Optional[VerifiedOpeningTrap]:
    return ALL_REGISTRY.get(trap_id)


def get_verified_traps_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in VERIFIED_TRAP_REGISTRY.values() if trap.opening_key == opening_key]


def get_warnings_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in OPENING_WARNINGS.values() if trap.opening_key == opening_key]


def get_all_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in ALL_REGISTRY.values() if trap.opening_key == opening_key]


def get_verified_trap_by_name(opening_key: str, trap_name: str) -> Optional[VerifiedOpeningTrap]:
    normalized_name = (trap_name or "").strip().lower()
    for trap in get_all_for_opening(opening_key):
        if trap.name.lower() == normalized_name:
            return trap
    return None


def get_applicable_traps_for_moves(opening_key: str, moves: List[str]) -> List[VerifiedOpeningTrap]:
    clean_moves = [_normalize(move) for move in moves if move]
    applicable = []
    for trap in get_all_for_opening(opening_key):
        trap_setup = [_normalize(move) for move in trap.setup_moves]
        if len(clean_moves) > len(trap_setup):
            continue
        if trap_setup[: len(clean_moves)] == clean_moves:
            applicable.append(trap)
    return applicable


def select_preferred_trap(opening_key: str, moves: List[str]) -> Optional[VerifiedOpeningTrap]:
    applicable = get_applicable_traps_for_moves(opening_key, moves)
    if not applicable:
        return None
    # Prefer real traps over warnings
    traps_first = sorted(applicable, key=lambda t: (0 if t.category == "trap" else 1, -len(t.setup_moves)))
    return traps_first[0]


def validate_verified_trap_registry() -> List[str]:
    issues: List[str] = []
    seen_name_opening_pairs = set()

    for trap_id, trap in ALL_REGISTRY.items():
        pair = (trap.opening_key, trap.name.lower())
        if pair in seen_name_opening_pairs:
            issues.append(f"Duplicate trap name within opening: {trap.opening_key}:{trap.name}")
        seen_name_opening_pairs.add(pair)

        board = chess.Board()
        try:
            for move in trap.full_line:
                board.push_san(move)
        except Exception as exc:
            issues.append(f"Illegal trap line for {trap_id}: {exc}")
            continue

        setup_board = chess.Board()
        try:
            for move in trap.setup_moves:
                setup_board.push_san(move)
        except Exception as exc:
            issues.append(f"Illegal trap setup for {trap_id}: {exc}")
            continue

        suffix_moves = [_normalize(move) for move in trap.full_line[len(trap.setup_moves):]]
        if suffix_moves and _normalize(trap.trap_move) not in suffix_moves:
            issues.append(f"Trap move mismatch for {trap_id}")

    return issues
