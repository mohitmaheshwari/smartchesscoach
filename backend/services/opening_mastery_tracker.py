"""
Opening Mastery Tracker
========================

Tracks player's learning progress for each opening across games.

Phases:
  INTRODUCTION → First game, full guidance (arrows + ideas per move)
  AWARENESS    → Games 2-3, trap warnings, lighter guidance
  FREE_PLAY    → Games 4+, no guidance, just track accuracy
  MASTERED     → Consistent correct play without help

Stored per user per opening in user_opening_mastery collection.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─── PHASES ───────────────────────────────────────────────────────

INTRODUCTION = "introduction"
AWARENESS = "awareness"
FREE_PLAY = "free_play"
MASTERED = "mastered"

# Phase transition thresholds
INTRO_TO_AWARENESS_GAMES = 1    # After 1 game with guidance
AWARENESS_TO_FREEPLAY_GAMES = 3  # After 3 games total
FREEPLAY_TO_MASTERED_ACCURACY = 0.8  # 80% correct moves without help
FREEPLAY_TO_MASTERED_GAMES = 3  # Need 3 free play games at 80%+


# ─── MOVE IDEAS — loaded from JSON theory tree ───────────────────
#
# All teaching data (ideas, arrows, variations, intros) lives in
# opening_theory_tree.json — the single source of truth.
# This code just reads and indexes it.

def _load_teaching_data():
    """Load move ideas from the theory tree JSON. Called once at import."""
    import os, json
    tree_path = os.path.join(os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json")
    try:
        with open(tree_path, encoding="utf-8") as f:
            tree = json.load(f)
    except Exception:
        logger.warning("[MASTERY] Could not load opening_theory_tree.json")
        return {}, {}

    flat_ideas = {}   # opening_key -> [{"move", "idea", "arrow"}, ...]
    branch_data = {}  # opening_key -> {"common": [...], "branches": {key: {...}}}

    for key, opening in tree.items():
        if key.startswith("_") or not isinstance(opening, dict):
            continue
        main_line = opening.get("main_line", [])
        move_ideas = opening.get("move_ideas", {})
        variations = opening.get("variations", {})
        if not main_line:
            continue

        # Build common (main_line) ideas
        common_ideas = []
        for move in main_line:
            info = move_ideas.get(move, {})
            common_ideas.append({
                "move": move,
                "idea": info.get("idea", ""),
                "arrow": info.get("arrow"),
            })

        # Check if any variation has teaching data (move_ideas + priority)
        has_branches = False
        branches = {}
        for var_key, var in variations.items():
            if not var.get("move_ideas"):
                continue
            has_branches = True
            var_moves_from_parent = var.get("moves_from_parent", [])
            var_continuation = var.get("continuation", [])
            var_move_ideas = var.get("move_ideas", {})
            branch_move = var_moves_from_parent[0] if var_moves_from_parent else ""

            branch_ideas = []
            for move in var_moves_from_parent + var_continuation:
                info = var_move_ideas.get(move, {})
                branch_ideas.append({
                    "move": move,
                    "idea": info.get("idea", ""),
                    "arrow": info.get("arrow"),
                })

            branches[var_key] = {
                "name": var.get("name", var_key),
                "branch_move": branch_move,
                "priority": var.get("priority", 99),
                "intro": var.get("intro", ""),
                "ideas": branch_ideas,
            }

        if has_branches:
            branch_data[key] = {
                "name": opening.get("name", key),
                "common": common_ideas,
                "branch_point": len(common_ideas),
                "branches": branches,
            }
            # Default flat list = common + highest priority branch
            best_branch = min(branches.values(), key=lambda b: b.get("priority", 99))
            flat_ideas[key] = common_ideas + best_branch.get("ideas", [])
        else:
            # No branch data — just use main_line + first variation continuation
            full_ideas = list(common_ideas)
            if variations:
                first_var = next(iter(variations.values()))
                for move in first_var.get("moves_from_parent", []) + first_var.get("continuation", []):
                    info = move_ideas.get(move, {})
                    full_ideas.append({
                        "move": move,
                        "idea": info.get("idea", ""),
                        "arrow": info.get("arrow"),
                    })
            flat_ideas[key] = full_ideas

    return flat_ideas, branch_data

OPENING_MOVE_IDEAS, OPENING_BRANCH_DATA = _load_teaching_data()


# ─── TEACHING LINE HELPERS ────────────────────────────────────────

def get_teaching_line(opening_key: str, branch_key: str = None):
    """
    Resolve a flat list of move ideas for the given opening + branch.

    Returns:
        (flat_ideas, branch_info) where branch_info is None for single-variation openings.
    """
    bd = OPENING_BRANCH_DATA.get(opening_key)
    if not bd:
        return OPENING_MOVE_IDEAS.get(opening_key, []), None

    branches = bd["branches"]
    if not branch_key:
        branch_key = min(branches, key=lambda k: branches[k].get("priority", 99))

    branch = branches.get(branch_key)
    if not branch:
        branch_key = min(branches, key=lambda k: branches[k].get("priority", 99))
        branch = branches[branch_key]

    flat_list = bd["common"] + branch.get("ideas", [])
    branch_info = {
        "key": branch_key,
        "name": branch.get("name", ""),
        "branch_move": branch.get("branch_move", ""),
        "branch_point": bd["branch_point"],
        "intro": branch.get("intro", ""),
    }
    return flat_list, branch_info


def select_branch_for_game(opening_key: str, branches_seen: List[str] = None) -> Optional[str]:
    """Pick which branch to teach based on what user has already seen."""
    bd = OPENING_BRANCH_DATA.get(opening_key)
    if not bd:
        return None

    branches = bd["branches"]
    seen = branches_seen or []

    unseen = sorted(
        [k for k in branches if k not in seen],
        key=lambda k: branches[k].get("priority", 99)
    )
    if unseen:
        return unseen[0]
    return min(branches, key=lambda k: branches[k].get("priority", 99))


def get_branch_info(opening_key: str) -> Optional[Dict]:
    """Get branch metadata for frontend display."""
    bd = OPENING_BRANCH_DATA.get(opening_key)
    if not bd:
        return None
    return {
        "name": bd["name"],
        "branch_point": bd["branch_point"],
        "branches": {
            k: {"name": v["name"], "branch_move": v["branch_move"], "priority": v.get("priority", 99)}
            for k, v in bd["branches"].items()
        },
    }


# ─── GET / UPDATE MASTERY ────────────────────────────────────────

async def get_opening_mastery(db, user_id: str, opening_key: str) -> Dict:
    """Get mastery data for a specific opening."""
    doc = await db.user_opening_mastery.find_one(
        {"user_id": user_id, "opening_key": opening_key},
        {"_id": 0}
    )
    if not doc:
        return {
            "opening_key": opening_key,
            "phase": INTRODUCTION,
            "games_played": 0,
            "moves_correct": 0,
            "moves_total": 0,
            "traps_encountered": [],
            "traps_handled": [],
            "traps_fallen_for": [],
            "accuracy_history": [],
            "last_played": None,
        }
    return doc


async def get_all_mastery(db, user_id: str) -> List[Dict]:
    """Get all opening mastery data for a user."""
    docs = await db.user_opening_mastery.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(50)
    return docs


async def update_mastery_after_game(
    db, user_id: str, opening_key: str,
    moves_correct: int, moves_total: int,
    traps_encountered: List[str] = None,
    traps_handled: List[str] = None,
    traps_fallen_for: List[str] = None,
    branch_played: str = None,
) -> Dict:
    """Update mastery after a coached game."""
    current = await get_opening_mastery(db, user_id, opening_key)

    games_played = current.get("games_played", 0) + 1
    total_correct = current.get("moves_correct", 0) + moves_correct
    total_moves = current.get("moves_total", 0) + moves_total
    accuracy = moves_correct / moves_total if moves_total > 0 else 0

    # Track trap history
    all_encountered = list(set(current.get("traps_encountered", []) + (traps_encountered or [])))
    all_handled = list(set(current.get("traps_handled", []) + (traps_handled or [])))
    all_fallen = list(set(current.get("traps_fallen_for", []) + (traps_fallen_for or [])))

    # Accuracy history (last 5 games)
    acc_history = current.get("accuracy_history", [])
    acc_history.append(round(accuracy, 2))
    acc_history = acc_history[-5:]

    # Track which branches the user has seen
    branches_seen = list(current.get("branches_seen", []))
    if branch_played and branch_played not in branches_seen:
        branches_seen.append(branch_played)

    # Phase transition
    current_phase = current.get("phase", INTRODUCTION)
    new_phase = _compute_phase(current_phase, games_played, acc_history)

    mastery = {
        "user_id": user_id,
        "opening_key": opening_key,
        "phase": new_phase,
        "games_played": games_played,
        "moves_correct": total_correct,
        "moves_total": total_moves,
        "traps_encountered": all_encountered,
        "traps_handled": all_handled,
        "traps_fallen_for": all_fallen,
        "accuracy_history": acc_history,
        "branches_seen": branches_seen,
        "last_played": datetime.now(timezone.utc).isoformat(),
    }

    await db.user_opening_mastery.update_one(
        {"user_id": user_id, "opening_key": opening_key},
        {"$set": mastery},
        upsert=True,
    )

    if new_phase != current_phase:
        logger.info(f"[MASTERY] {user_id} {opening_key}: {current_phase} -> {new_phase}")

    return mastery


def _compute_phase(current_phase: str, games_played: int, accuracy_history: List[float]) -> str:
    """Determine the teaching phase based on progress."""
    if current_phase == INTRODUCTION:
        if games_played >= INTRO_TO_AWARENESS_GAMES:
            return AWARENESS
        return INTRODUCTION

    if current_phase == AWARENESS:
        if games_played >= AWARENESS_TO_FREEPLAY_GAMES:
            return FREE_PLAY
        return AWARENESS

    if current_phase == FREE_PLAY:
        # Need consistent high accuracy in free play
        recent = accuracy_history[-FREEPLAY_TO_MASTERED_GAMES:]
        if len(recent) >= FREEPLAY_TO_MASTERED_GAMES:
            if all(a >= FREEPLAY_TO_MASTERED_ACCURACY for a in recent):
                return MASTERED
        return FREE_PLAY

    return current_phase


# ─── FOR PLAY WITH COACH ─────────────────────────────────────────

def get_move_guidance(opening_key: str, move_index: int, phase: str) -> Optional[Dict]:
    """
    Get the guidance for a specific move in the opening.

    Returns:
        {"move": "e4", "idea": "Push king's pawn...", "arrow": ["e2", "e4"]}
        or None if no guidance (past the teaching line, or free_play phase)
    """
    if phase in (FREE_PLAY, MASTERED):
        return None  # No guidance in free play

    ideas = OPENING_MOVE_IDEAS.get(opening_key, [])
    if move_index >= len(ideas):
        return None

    guidance = ideas[move_index]

    # In awareness phase, only show ideas for user moves (not opponent)
    if phase == AWARENESS and guidance.get("arrow") is None:
        return None  # Skip opponent move explanations in awareness phase

    return guidance


def get_trap_warning(opening_key: str, moves_played: List[str]) -> Optional[Dict]:
    """
    Check if the current position is approaching a known trap.

    Returns:
        {"trap_name": "Fried Liver Attack", "warning": "...", "trap_move": "Nxf7"}
        or None
    """
    from services.verified_opening_traps import get_applicable_traps_for_moves, select_preferred_trap

    trap = select_preferred_trap(opening_key, moves_played)
    if not trap:
        return None

    # Only warn if we're close to the trap (within 2 moves of setup completion)
    remaining = len(trap.setup_moves) - len(moves_played)
    if remaining > 2 or remaining < 0:
        return None

    return {
        "trap_id": trap.trap_id,
        "trap_name": trap.name,
        "warning": trap.explanation,
        "refutation": trap.refutation,
        "trap_move": trap.trap_move,
        "category": trap.category,
        "difficulty": trap.difficulty,
        "remaining_moves": remaining,
    }


def get_phase_label(phase: str) -> str:
    """Human-readable phase label."""
    return {
        INTRODUCTION: "Learning",
        AWARENESS: "Practicing",
        FREE_PLAY: "Testing",
        MASTERED: "Mastered",
    }.get(phase, "Learning")
