"""One-shot patcher: add engine-aware opening accuracy to
opening_mastery_tracker.py. Adds three helpers + a per-game updater
that computes accuracy from v5_data + cp_loss, scoring non-curriculum
moves by engine quality instead of treating them as wrong.

Idempotent: skips if already patched.
"""
import sys

PATH = "/app/backend/services/opening_mastery_tracker.py"

OLD_ANCHOR = "# ─── GET / UPDATE MASTERY ────────────────────────────────────────"

HELPERS = '''# ─── ENGINE-AWARE OPENING ACCURACY (Mohit 2026-06-04) ──────────────
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
    "king\\'s indian": "kings_indian_defense",
    "nimzo": "nimzo_indian_defense",
    "modern defense": "modern_defense",
    "philidor": "philidor_defense",
    "bishop\\'s opening": "bishops_opening",
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
    curr = _load_teaching_data() or {}
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


# ─── GET / UPDATE MASTERY ────────────────────────────────────────'''

# Also extend update_mastery_after_game with accuracy_override.
OLD_FN_SIG = (
    "async def update_mastery_after_game(\n"
    "    db, user_id: str, opening_key: str,\n"
    "    moves_correct: int, moves_total: int,\n"
    "    traps_encountered: List[str] = None,\n"
    "    traps_handled: List[str] = None,\n"
    "    traps_fallen_for: List[str] = None,\n"
    "    branch_played: str = None,\n"
    ") -> Dict:\n"
    '    """Update mastery after a coached game."""'
)
NEW_FN_SIG = (
    "async def update_mastery_after_game(\n"
    "    db, user_id: str, opening_key: str,\n"
    "    moves_correct: int = 0, moves_total: int = 0,\n"
    "    traps_encountered: List[str] = None,\n"
    "    traps_handled: List[str] = None,\n"
    "    traps_fallen_for: List[str] = None,\n"
    "    branch_played: str = None,\n"
    "    accuracy_override: Optional[float] = None,\n"
    ") -> Dict:\n"
    '    """Update mastery after a coached game.\n'
    "\n"
    "    Pass moves_correct/moves_total for the original PWC code path\n"
    "    (curriculum-match accuracy). Pass accuracy_override for the\n"
    "    engine-aware path — value is appended directly to history,\n"
    "    counters aren't inflated. See compute_engine_aware_opening_accuracy.\n"
    '    """'
)

OLD_ACC = (
    "    games_played = current.get(\"games_played\", 0) + 1\n"
    "    total_correct = current.get(\"moves_correct\", 0) + moves_correct\n"
    "    total_moves = current.get(\"moves_total\", 0) + moves_total\n"
    "    accuracy = moves_correct / moves_total if moves_total > 0 else 0"
)
NEW_ACC = (
    "    games_played = current.get(\"games_played\", 0) + 1\n"
    "    if accuracy_override is not None:\n"
    "        # Engine-aware path: don't inflate the curriculum-match counters.\n"
    "        accuracy = float(accuracy_override)\n"
    "        total_correct = current.get(\"moves_correct\", 0)\n"
    "        total_moves = current.get(\"moves_total\", 0)\n"
    "    else:\n"
    "        total_correct = current.get(\"moves_correct\", 0) + moves_correct\n"
    "        total_moves = current.get(\"moves_total\", 0) + moves_total\n"
    "        accuracy = moves_correct / moves_total if moves_total > 0 else 0"
)


def main():
    with open(PATH) as f:
        content = f.read()
    changed = False
    if "compute_engine_aware_opening_accuracy" not in content:
        if content.count(OLD_ANCHOR) != 1:
            print(f"ERROR: anchor count = {content.count(OLD_ANCHOR)}")
            return 1
        content = content.replace(OLD_ANCHOR, HELPERS, 1)
        changed = True
        print("- added engine-aware helpers")
    else:
        print("- helpers already present")
    if "accuracy_override" not in content:
        if content.count(OLD_FN_SIG) != 1:
            print(f"ERROR: fn-sig anchor count = {content.count(OLD_FN_SIG)}")
            return 1
        content = content.replace(OLD_FN_SIG, NEW_FN_SIG, 1)
        if content.count(OLD_ACC) != 1:
            print(f"ERROR: accuracy-body anchor count = {content.count(OLD_ACC)}")
            return 1
        content = content.replace(OLD_ACC, NEW_ACC, 1)
        changed = True
        print("- extended update_mastery_after_game with accuracy_override")
    else:
        print("- update_mastery_after_game already extended")
    if changed:
        with open(PATH, "w") as f:
            f.write(content)
        print("WROTE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
