"""
Chess Trap Library — loader + queries.

Data lives in data/traps.json (admin-editable). This module loads it at
import time and exposes the existing API: TRAP_LIBRARY dict + helper
functions. Callers unchanged.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data load ─────────────────────────────────────────────────────────

_TRAPS_PATH = Path(__file__).resolve().parent.parent / "data" / "traps.json"


def _load_traps() -> Dict[str, List[Dict]]:
    try:
        with open(_TRAPS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {_TRAPS_PATH}: {e}")
        return {}


TRAP_LIBRARY: Dict[str, List[Dict]] = _load_traps()


def reload_traps() -> None:
    """Force-reload from disk. Useful for admin edits without a restart."""
    global TRAP_LIBRARY
    TRAP_LIBRARY = _load_traps()


# ── Queries ───────────────────────────────────────────────────────────


def get_traps_for_opening(opening_key: str) -> List[Dict]:
    """All traps for a specific opening."""
    return TRAP_LIBRARY.get(opening_key, [])


def get_all_traps() -> Dict[str, List[Dict]]:
    """The entire trap library."""
    return TRAP_LIBRARY


def get_trap_by_name(trap_name: str) -> Optional[Dict]:
    """Find a trap by name across all openings."""
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap["name"].lower() == trap_name.lower():
                return {**trap, "opening_key": opening_key}
    return None


def get_checkmate_traps() -> List[Dict]:
    """All traps that end in checkmate."""
    out = []
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap.get("result_type") == "checkmate":
                out.append({**trap, "opening_key": opening_key})
    return out


def get_traps_by_difficulty(difficulty: str) -> List[Dict]:
    """Traps filtered by difficulty."""
    out = []
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap.get("difficulty") == difficulty:
                out.append({**trap, "opening_key": opening_key})
    return out


# ── Training routing ──────────────────────────────────────────────────
#
# Each trap maps to a cognitive_gap weakness — used to route Lab-page
# trap-intelligence cards to `/training/prescribed?weakness=<X>`.
#
# Rule of thumb:
#   - checkmate traps         → king_safety (teaches defending the king)
#   - wins_material traps     → tactical_oversight (teaches seeing threats)
#   - anything else           → tactical_oversight (safe default)
#
# Tag per trap in the JSON via `training_weakness` if you want a different
# mapping than the rule above.

DEFAULT_TRAINING_WEAKNESS = "tactical_oversight"


def training_weakness_for_trap(trap: Dict) -> str:
    """Return the cognitive_gap weakness to route this trap's training to.

    Prefers the explicit `training_weakness` field on the trap; otherwise
    infers from `result_type`.
    """
    explicit = trap.get("training_weakness")
    if explicit:
        return explicit
    rt = (trap.get("result_type") or "").lower()
    if "mate" in rt:  # matches "checkmate"
        return "king_safety"
    if "material" in rt:
        return "tactical_oversight"
    return DEFAULT_TRAINING_WEAKNESS


def find_relevant_trap(fen: str, move_history: List[str]) -> Optional[Dict]:
    """If the current move history matches any trap setup, return it."""
    normalized_history = [m.replace("+", "").replace("#", "").lower() for m in move_history]
    history_len = len(normalized_history)

    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            setup_moves = trap.get("setup_moves", [])
            setup_len = len(setup_moves)
            if setup_len - 2 <= history_len <= setup_len:
                normalized_setup = [m.replace("+", "").replace("#", "").lower() for m in setup_moves[:history_len]]
                if normalized_history == normalized_setup:
                    remaining_setup = setup_moves[history_len:]
                    return {
                        **trap,
                        "opening_key": opening_key,
                        "position_type": "at_trap" if history_len == setup_len else "approaching_trap",
                        "moves_to_trap": remaining_setup,
                        "trap_ready": history_len == setup_len,
                    }
    return None


def get_trap_for_position(move_history: List[str]) -> Optional[Dict]:
    """Check if the current position is a prefix of a known trap setup."""
    history_str = " ".join(move_history).lower()
    best_match = None
    best_match_len = 0

    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            setup_moves = trap.get("setup_moves", [])
            setup_str = " ".join(setup_moves).lower()
            if setup_str.startswith(history_str):
                match_len = len(move_history)
                if match_len > best_match_len:
                    best_match_len = match_len
                    remaining = setup_moves[len(move_history):]
                    best_match = {
                        **trap,
                        "opening_key": opening_key,
                        "setup_remaining": remaining,
                        "trap_line": trap.get("trap_line", []),
                        "moves_until_trap": len(remaining),
                    }
    return best_match


def get_all_trap_statistics() -> Dict[str, Any]:
    """Library statistics."""
    total_traps = 0
    checkmate_traps = 0
    by_difficulty = {"beginner": 0, "intermediate": 0, "advanced": 0}
    by_result: Dict[str, int] = {}
    by_opening: Dict[str, int] = {}

    for opening_key, traps in TRAP_LIBRARY.items():
        by_opening[opening_key] = len(traps)
        total_traps += len(traps)
        for trap in traps:
            result = trap.get("result_type", "unknown")
            diff = trap.get("difficulty", "unknown")
            if result == "checkmate":
                checkmate_traps += 1
            by_result[result] = by_result.get(result, 0) + 1
            if diff in by_difficulty:
                by_difficulty[diff] += 1

    return {
        "total_traps": total_traps,
        "checkmate_traps": checkmate_traps,
        "by_difficulty": by_difficulty,
        "by_result": by_result,
        "by_opening": by_opening,
    }


# Openings whose ECO/name ownership belongs to Black. Used by
# analyze_game_for_traps to figure out who benefits from a trap.
_BLACK_OPENINGS = {
    "sicilian-defense", "french-defense", "caro-kann", "scandinavian-defense",
    "petrov-defense", "philidor-defense", "kings-indian-defense", "nimzo-indian",
    "queens-indian", "grunfeld-defense", "benoni-defense", "slav-defense",
    "dutch-defense", "budapest-gambit",
}


def analyze_game_for_traps(moves: List[str], user_color: str) -> Dict:
    """
    Analyze a game's moves to detect if any traps were played or fallen into.
    Returns {traps_executed, traps_fallen_into, trap_opportunities_missed, summary}.
    """
    traps_executed: List[Dict] = []
    traps_fallen_into: List[Dict] = []
    trap_opportunities_missed: List[Dict] = []

    normalized_moves = [m.replace("+", "").replace("#", "").replace("!", "").replace("?", "") for m in moves]
    moves_str = " ".join(normalized_moves).lower()

    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            setup_moves = trap.get("setup_moves", [])
            trap_line = trap.get("trap_line", [])

            normalized_setup = [m.replace("+", "").replace("#", "") for m in setup_moves]
            normalized_trap = [t["move"].replace("+", "").replace("#", "") for t in trap_line]

            setup_str = " ".join(normalized_setup).lower()
            full_trap_str = " ".join(normalized_setup + normalized_trap).lower()

            if setup_str in moves_str:
                setup_end_idx = len(setup_moves)
                opening_color = "black" if opening_key in _BLACK_OPENINGS else "white"

                if full_trap_str in moves_str:
                    trap_beneficiary = opening_color
                    if user_color == trap_beneficiary:
                        traps_executed.append({
                            "trap_name": trap["name"],
                            "opening": opening_key,
                            "result": trap.get("result_type"),
                            "move_number": (setup_end_idx // 2) + 1,
                            "description": trap.get("success_message"),
                        })
                    else:
                        traps_fallen_into.append({
                            "trap_name": trap["name"],
                            "opening": opening_key,
                            "result": trap.get("result_type"),
                            "move_number": (setup_end_idx // 2) + 1,
                            "description": f"You fell into the {trap['name']}!",
                            "how_to_avoid": (
                                f"After {setup_moves[-1]}, avoid "
                                f"{normalized_trap[0] if len(trap_line) > 1 else 'the trap sequence'}"
                            ),
                        })

    return {
        "traps_executed": traps_executed,
        "traps_fallen_into": traps_fallen_into,
        "trap_opportunities_missed": trap_opportunities_missed,
        "summary": {
            "executed_count": len(traps_executed),
            "fallen_into_count": len(traps_fallen_into),
            "missed_count": len(trap_opportunities_missed),
        },
    }


def detect_trap_in_position(fen: str, move_history: List[str]) -> Optional[Dict]:
    """Real-time trap detection — returns info if position matches a trap setup or line."""
    normalized_history = [m.replace("+", "").replace("#", "").lower() for m in move_history]
    history_len = len(normalized_history)

    matches: List[Dict] = []
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            setup_moves = trap.get("setup_moves", [])
            normalized_setup = [m.replace("+", "").replace("#", "").lower() for m in setup_moves]

            if history_len <= len(normalized_setup):
                if normalized_history == normalized_setup[:history_len]:
                    remaining = setup_moves[history_len:]
                    matches.append({
                        "trap_name": trap["name"],
                        "opening": opening_key,
                        "status": "in_setup" if remaining else "setup_complete",
                        "moves_remaining": remaining,
                        "trap_line": trap.get("trap_line", []),
                        "result_type": trap.get("result_type"),
                        "difficulty": trap.get("difficulty"),
                    })
            elif history_len <= len(normalized_setup) + len(trap.get("trap_line", [])):
                full_sequence = normalized_setup + [
                    t["move"].lower().replace("+", "").replace("#", "")
                    for t in trap.get("trap_line", [])
                ]
                if normalized_history == full_sequence[:history_len]:
                    matches.append({
                        "trap_name": trap["name"],
                        "opening": opening_key,
                        "status": "in_trap_line",
                        "move_in_trap": history_len - len(normalized_setup),
                        "moves_remaining": len(full_sequence) - history_len,
                        "result_type": trap.get("result_type"),
                    })

    if matches:
        return max(matches, key=lambda x: len(x.get("trap_line", [])) - x.get("moves_remaining", 999))
    return None
