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
# Two paths to MASTERED (Mohit 2026-06-04 — original 80%/3 games was too
# steep for 600-1500 audience; only 1 of 36 user×opening rows was mastered
# across the population). Loosened to:
#   Path A — consistency: last 3 free-play games all ≥ 65% accuracy
#   Path B — experience : ≥ 10 free-play games, average accuracy ≥ 55%
# Either path qualifies.
FREEPLAY_TO_MASTERED_ACCURACY = 0.65          # path A per-game floor
FREEPLAY_TO_MASTERED_GAMES = 3                # path A streak length
FREEPLAY_TO_MASTERED_EXPERIENCE_GAMES = 10    # path B total game count
FREEPLAY_TO_MASTERED_EXPERIENCE_ACC = 0.55    # path B average floor


# ─── MOVE IDEAS — loaded from JSON theory tree ───────────────────
#
# All teaching data (ideas, arrows, variations, intros) lives in
# opening_curriculum.json — the single source of truth (via unified source).
# This code just reads and indexes it.

def _load_teaching_data():
    """Load move ideas from the curriculum. Called once at import."""
    try:
        from services.opening_unified_source import get_unified_source
        source = get_unified_source()
        tree = source.get_theory_tree()
    except Exception:
        logger.warning("[MASTERY] Could not load opening curriculum")
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


# ─── ENGINE-AWARE OPENING ACCURACY (Mohit 2026-06-04) ──────────────
#
# The original metric (moves_correct/moves_total from PWC teaching mode)
# treats ANY deviation from the curriculum setup_order as wrong. That
# punishes reasonable book alternatives. Real test: was the move ACTUALLY
# bad (engine cp_loss high) or just different from our prescribed line?
#
# This module's helpers:
#   compute_engine_aware_opening_accuracy(v5_data, setup_order)
#     Walks the user's opening-phase moves in v5_data, scoring each:
#       - exact match w/ setup_order → 1.0
#       - cp_loss ≤ 20  (book alternative or near-book) → 1.0
#       - cp_loss ≤ 60  (decent move, small loss) → 0.7
#       - cp_loss ≤ 150 (questionable) → 0.3
#       - cp_loss > 150 (mistake/blunder) → 0.0
#     Returns (accuracy_float, n_user_moves_evaluated).
#
#   update_mastery_from_analyzed_game(db, user_id, game_id)
#     Composes the above with curriculum lookup + DB write. Idempotent
#     via user_opening_mastery._accuracy_evaluated_games.
#
# Works on EVERY analyzed game (PWC + imported), not just PWC sessions.


def _normalize_san_for_accuracy(san):
    """Strip check/mate/annotation marks and lowercase for tolerant compare."""
    if not san:
        return ""
    s = san.strip()
    for ch in ("+", "#", "!", "?"):
        s = s.replace(ch, "")
    return s.lower()


def compute_engine_aware_opening_accuracy(v5_data, setup_order, max_user_plies=8):
    """Score user opening moves with engine-aware credit.

    Returns (accuracy_float or None, n_user_moves_evaluated).
    Returns (None, 0) when there are no user opening moves to score.
    """
    if not v5_data or not setup_order:
        return None, 0
    setup_norm = [_normalize_san_for_accuracy(m) for m in setup_order]
    scores = []
    user_ply = 0
    for rec in v5_data:
        if not isinstance(rec, dict):
            continue
        if not rec.get("is_user_move"):
            continue
        if rec.get("phase") != "opening":
            break  # we've left the opening phase; stop scoring
        move_san = _normalize_san_for_accuracy(rec.get("move_san") or "")
        cp_loss = int(rec.get("cp_loss") or 0)
        expected = setup_norm[user_ply] if user_ply < len(setup_norm) else None
        if expected and move_san == expected:
            score = 1.0
        elif cp_loss <= 20:
            score = 1.0
        elif cp_loss <= 60:
            score = 0.7
        elif cp_loss <= 150:
            score = 0.3
        else:
            score = 0.0
        scores.append(score)
        user_ply += 1
        if user_ply >= max_user_plies:
            break
    if not scores:
        return None, 0
    return sum(scores) / len(scores), len(scores)


# Map free-form opening_name → curriculum key. Used when the game record
# carries a chess.com-style "Italian Game Knight Attack" instead of the
# canonical curriculum key.
_OPENING_NAME_KEYWORDS = {
    "italian": "italian_game",
    "ruy lopez": "ruy_lopez",
    "spanish": "ruy_lopez",
    "scotch": "scotch_game",
    "petrov": "petrov_defense",
    "petroff": "petrov_defense",
    "sicilian": "sicilian_defense",
    "caro kann": "caro_kann",
    "caro-kann": "caro_kann",
    "french": "french_defense",
    "scandinavian": "scandinavian_defense",
    "queens gambit": "queens_gambit",
    "queen's gambit": "queens_gambit",
    "queens pawn": "queens_gambit",
    "slav": "slav_defense",
    "london": "london_system",
    "kings indian": "kings_indian_defense",
    "king\'s indian": "kings_indian_defense",
    "nimzo": "nimzo_indian_defense",
    "modern defense": "modern_defense",
    "philidor": "philidor_defense",
    "bishop\'s opening": "bishops_opening",
    "bishops opening": "bishops_opening",
    "vienna": "vienna_game",
    "english": "english_opening",
    "englund": "englund_gambit_response",
}


def _curriculum_key_from_opening_name(opening_name):
    """Map a free-form opening_name to a curriculum key (best-effort)."""
    if not opening_name:
        return None
    name_lower = opening_name.lower()
    for keyword, key in _OPENING_NAME_KEYWORDS.items():
        if keyword in name_lower:
            return key
    return None


# Cache for the setup_order curriculum (different file from
# opening_theory_tree.json that _load_teaching_data reads).
_OPENING_CURRICULUM_CACHE = None


def _load_opening_curriculum():
    """Load opening_curriculum.json (the setup_order source). Cached."""
    global _OPENING_CURRICULUM_CACHE
    if _OPENING_CURRICULUM_CACHE is not None:
        return _OPENING_CURRICULUM_CACHE
    import os, json
    path = os.path.join(os.path.dirname(__file__), "..", "data", "opening_curriculum.json")
    try:
        with open(path, encoding="utf-8") as f:
            _OPENING_CURRICULUM_CACHE = json.load(f) or {}
    except Exception as e:
        logger.warning(f"[MASTERY] Could not load opening_curriculum.json: {e}")
        _OPENING_CURRICULUM_CACHE = {}
    return _OPENING_CURRICULUM_CACHE


async def update_mastery_from_analyzed_game(db, user_id, game_id):
    """Compute engine-aware opening accuracy for a single analyzed game
    and update the user's opening_mastery row.

    Idempotent via _accuracy_evaluated_games. Returns None on
    short-circuit, dict on success.
    """
    ga = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "decryption_v5_data": 1},
    )
    if not ga:
        return None
    v5 = ga.get("decryption_v5_data") or []
    if not v5:
        return None
    g = await db.games.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "opening_key": 1, "opening_name": 1},
    )
    opening_key = (g or {}).get("opening_key") or _curriculum_key_from_opening_name(
        (g or {}).get("opening_name")
    )
    if not opening_key:
        return None
    curr = _load_opening_curriculum()
    opening_data = curr.get(opening_key)
    if not opening_data:
        return None
    setup_order = opening_data.get("setup_order") or []
    if not setup_order:
        return None
    accuracy, n_moves = compute_engine_aware_opening_accuracy(v5, setup_order)
    if accuracy is None:
        return None
    # Idempotency: skip if this game already contributed.
    current = await db.user_opening_mastery.find_one(
        {"user_id": user_id, "opening_key": opening_key},
        {"_id": 0, "_accuracy_evaluated_games": 1},
    )
    evaluated = set((current or {}).get("_accuracy_evaluated_games") or [])
    if game_id in evaluated:
        return None
    # Write via update_mastery_after_game using accuracy_override.
    result = await update_mastery_after_game(
        db, user_id, opening_key,
        moves_correct=0, moves_total=0,
        accuracy_override=accuracy,
    )
    # Mark game as evaluated.
    await db.user_opening_mastery.update_one(
        {"user_id": user_id, "opening_key": opening_key},
        {"$addToSet": {"_accuracy_evaluated_games": game_id}},
    )
    return {
        "opening_key": opening_key,
        "accuracy": accuracy,
        "n_moves_evaluated": n_moves,
        "result": result,
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
    moves_correct: int = 0, moves_total: int = 0,
    traps_encountered: List[str] = None,
    traps_handled: List[str] = None,
    traps_fallen_for: List[str] = None,
    branch_played: str = None,
    accuracy_override: Optional[float] = None,
) -> Dict:
    """Update mastery after a coached game.

    Pass moves_correct/moves_total for the original PWC code path
    (curriculum-match accuracy). Pass accuracy_override for the
    engine-aware path — value is appended directly to history,
    counters aren't inflated. See compute_engine_aware_opening_accuracy.
    """
    current = await get_opening_mastery(db, user_id, opening_key)

    games_played = current.get("games_played", 0) + 1
    if accuracy_override is not None:
        # Engine-aware path: don't inflate the curriculum-match counters.
        accuracy = float(accuracy_override)
        total_correct = current.get("moves_correct", 0)
        total_moves = current.get("moves_total", 0)
    else:
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
        # Path A — consistency: last N games all above the per-game floor.
        recent = accuracy_history[-FREEPLAY_TO_MASTERED_GAMES:]
        if (len(recent) >= FREEPLAY_TO_MASTERED_GAMES
                and all(a >= FREEPLAY_TO_MASTERED_ACCURACY for a in recent)):
            return MASTERED
        # Path B — experience: long history at a moderate average.
        if (len(accuracy_history) >= FREEPLAY_TO_MASTERED_EXPERIENCE_GAMES
                and (sum(accuracy_history) / len(accuracy_history))
                    >= FREEPLAY_TO_MASTERED_EXPERIENCE_ACC):
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
