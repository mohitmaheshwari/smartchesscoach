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


# ─── MOVE IDEAS (why each move matters, not notation) ─────────────

OPENING_MOVE_IDEAS = {
    "italian_game": [
        {"move": "e4", "idea": "Push your king's pawn forward to control the center", "arrow": ["e2", "e4"]},
        {"move": "e5", "idea": "Opponent fights for the center too", "arrow": None},
        {"move": "Nf3", "idea": "Develop your knight toward the center — it attacks e5", "arrow": ["g1", "f3"]},
        {"move": "Nc6", "idea": "Opponent defends their pawn", "arrow": None},
        {"move": "Bc4", "idea": "Point your bishop at f7 — the weakest square in Black's position", "arrow": ["f1", "c4"]},
        {"move": "Bc5", "idea": "Opponent mirrors — their bishop targets f2", "arrow": None},
        {"move": "c3", "idea": "Prepare to push d4 and build a big center", "arrow": ["c2", "c3"]},
        {"move": "Nf6", "idea": "Opponent develops and attacks your e4 pawn", "arrow": None},
        {"move": "d4", "idea": "Open the center! This is the key break in the Italian", "arrow": ["d2", "d4"]},
    ],
    "french_defense": [
        {"move": "e4", "idea": "Control the center with your king's pawn", "arrow": ["e2", "e4"]},
        {"move": "e6", "idea": "Opponent prepares to challenge with d5", "arrow": None},
        {"move": "d4", "idea": "Take more space in the center", "arrow": ["d2", "d4"]},
        {"move": "d5", "idea": "Opponent challenges your center — this is the French Defense", "arrow": None},
        {"move": "e5", "idea": "Push forward to gain space. The Advance Variation.", "arrow": ["e4", "e5"]},
        {"move": "c5", "idea": "Opponent attacks your center from the side", "arrow": None},
        {"move": "c3", "idea": "Support your d4 pawn — keep the center strong", "arrow": ["c2", "c3"]},
    ],
    "queens_gambit": [
        {"move": "d4", "idea": "Control the center with the queen's pawn", "arrow": ["d2", "d4"]},
        {"move": "d5", "idea": "Opponent mirrors — both sides fight for center", "arrow": None},
        {"move": "c4", "idea": "Offer a pawn to pull Black's center apart. This is the Queen's Gambit.", "arrow": ["c2", "c4"]},
        {"move": "e6", "idea": "Opponent declines — keeps the center solid", "arrow": None},
        {"move": "Nc3", "idea": "Develop your knight and support the center", "arrow": ["b1", "c3"]},
        {"move": "Nf6", "idea": "Opponent develops toward the center", "arrow": None},
        {"move": "Bg5", "idea": "Pin their knight to the queen. This creates pressure.", "arrow": ["c1", "g5"]},
    ],
    "london_system": [
        {"move": "d4", "idea": "Control the center", "arrow": ["d2", "d4"]},
        {"move": "d5", "idea": "Opponent mirrors", "arrow": None},
        {"move": "Bf4", "idea": "Develop bishop BEFORE e3. This is the #1 rule of the London.", "arrow": ["c1", "f4"]},
        {"move": "Nf6", "idea": "Opponent develops", "arrow": None},
        {"move": "e3", "idea": "NOW play e3 — the bishop is already out", "arrow": ["e2", "e3"]},
        {"move": "e6", "idea": "Opponent builds a solid structure", "arrow": None},
        {"move": "Nf3", "idea": "Develop your knight to its natural square", "arrow": ["g1", "f3"]},
    ],
    "sicilian_defense": [
        {"move": "e4", "idea": "Control the center", "arrow": ["e2", "e4"]},
        {"move": "c5", "idea": "The Sicilian! Opponent fights for the center from the side", "arrow": None},
        {"move": "Nf3", "idea": "Develop and prepare to open the center with d4", "arrow": ["g1", "f3"]},
        {"move": "d6", "idea": "Opponent prepares a solid setup", "arrow": None},
        {"move": "d4", "idea": "Open the center — this is the main plan against the Sicilian", "arrow": ["d2", "d4"]},
        {"move": "cxd4", "idea": "Opponent takes — now you get an open file", "arrow": None},
        {"move": "Nxd4", "idea": "Recapture with the knight — it's centralized and strong", "arrow": ["f3", "d4"]},
    ],
    "caro_kann": [
        {"move": "e4", "idea": "Control the center", "arrow": ["e2", "e4"]},
        {"move": "c6", "idea": "The Caro-Kann! Opponent prepares d5 with support", "arrow": None},
        {"move": "d4", "idea": "Take more space", "arrow": ["d2", "d4"]},
        {"move": "d5", "idea": "Opponent challenges your center — the key moment", "arrow": None},
        {"move": "Nc3", "idea": "Defend your e4 pawn with the knight", "arrow": ["b1", "c3"]},
    ],
    "ruy_lopez": [
        {"move": "e4", "idea": "Control the center", "arrow": ["e2", "e4"]},
        {"move": "e5", "idea": "Opponent fights back", "arrow": None},
        {"move": "Nf3", "idea": "Attack their e5 pawn", "arrow": ["g1", "f3"]},
        {"move": "Nc6", "idea": "Opponent defends", "arrow": None},
        {"move": "Bb5", "idea": "The Ruy Lopez! Pin the knight that defends e5. Long-term pressure.", "arrow": ["f1", "b5"]},
        {"move": "a6", "idea": "Opponent challenges your bishop — the Morphy Defense", "arrow": None},
        {"move": "Ba4", "idea": "Retreat but maintain the pin. The bishop is still powerful.", "arrow": ["b5", "a4"]},
    ],
    "scotch_game": [
        {"move": "e4", "idea": "Control the center", "arrow": ["e2", "e4"]},
        {"move": "e5", "idea": "Opponent mirrors", "arrow": None},
        {"move": "Nf3", "idea": "Develop and attack e5", "arrow": ["g1", "f3"]},
        {"move": "Nc6", "idea": "Opponent defends", "arrow": None},
        {"move": "d4", "idea": "Open the center immediately! The Scotch Game — direct and aggressive.", "arrow": ["d2", "d4"]},
    ],
    "petrov_defense": [
        {"move": "e4", "idea": "Control the center", "arrow": ["e2", "e4"]},
        {"move": "e5", "idea": "Opponent mirrors", "arrow": None},
        {"move": "Nf3", "idea": "Attack their e5 pawn", "arrow": ["g1", "f3"]},
        {"move": "Nf6", "idea": "The Petrov! Opponent counterattacks your e4 instead of defending", "arrow": None},
        {"move": "Nxe5", "idea": "Take the pawn. Now the critical moment begins.", "arrow": ["f3", "e5"]},
    ],
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
