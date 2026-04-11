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


ALL_REGISTRY = _load_traps_from_json()
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
