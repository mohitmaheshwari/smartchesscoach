"""predict_coach_move.py — core logic for the predict-coach-move mechanic (PWC premium S2 keystone).

This is the CORE everything wires around (docs/predict_coach_move_scope.md). It holds the firing SEAM
(the conductor replaces its body later) and the option builder. Stockfish multi-PV is computed by the
caller (/check endpoint) and passed in — this module stays pure + unit-testable.

Data-driven design (probe 2026-06-10, 448 real coach-move positions):
- Coach's move is top-3 of the engine's moves 71% of the time, top-4 76%, outside top-4 24%.
  -> FIRE only when the coach's move is top-3 (a sensible thing to predict); skip the 24% offbeat moves.
     This also guarantees the coach's move is in the multi-PV, so the correct answer is always an option.
- Median top1-top2 eval gap = 16cp (several near-equal moves in most positions) -> plausible decoys
  almost always exist; difficulty = how close the decoys' eval is to the coach's move.
- 95% of coach moves are eligible under a loose rule -> the per-game CAP is the throttle, not eligibility.
"""
import random
from typing import List, Tuple, Optional


def band_of(rating: Optional[int]) -> str:
    if rating is None or rating < 1000:
        return "beginner"
    if rating < 1400:
        return "improver"
    return "intermediate"


# Per-game cap = the cadence throttle (probe: ~95% eligible, so the cap controls how often it fires).
PER_GAME_CAP = {"beginner": 3, "improver": 2, "intermediate": 1}
# Difficulty = decoy closeness in cp: beginner gets clearly-worse decoys; intermediate near-equal.
DIFFICULTY = {"beginner": "easy", "improver": "medium", "intermediate": "hard"}

ELIGIBLE_MAX_RANK = 3   # only predict when the coach's move is a top-3 engine move
MIN_LEGAL = 3           # need a real choice, not a near-forced position


def should_fire(coach_move_rank: Optional[int], num_legal: int,
                predictions_this_game: int, rating: Optional[int]) -> bool:
    """The firing SEAM. V1 = rating-banded eligibility + per-game cap.
    The conductor (later) replaces THIS BODY, not the seam or its callers."""
    if coach_move_rank is None or coach_move_rank > ELIGIBLE_MAX_RANK:
        return False
    if num_legal < MIN_LEGAL:
        return False
    return predictions_this_game < PER_GAME_CAP[band_of(rating)]


def difficulty_for(rating: Optional[int]) -> str:
    return DIFFICULTY[band_of(rating)]


def build_options(multipv: List[Tuple[str, int]], coach_san: str,
                  rating: Optional[int], k: int = 3,
                  rng: Optional[random.Random] = None) -> List[str]:
    """Build k display options: the coach's ACTUAL move + (k-1) decoys from the engine's other top moves.

    multipv: [(san, cp)] best-first, from the mover's POV. Difficulty (by band) selects decoys CLOSE in cp
    to the coach's move (hard) or FAR (easy). The coach's move is always included (we only fire when it is
    top-3, so it is present in multipv). Returns [] if there isn't a clean option set.
    """
    rng = rng or random.Random()
    coach_cp = next((cp for s, cp in multipv if s == coach_san), None)
    others = [(s, cp) for s, cp in multipv if s != coach_san]
    if coach_cp is None or len(others) < k - 1:
        return []
    diff = DIFFICULTY[band_of(rating)]
    others_by_closeness = sorted(others, key=lambda sc: abs(sc[1] - coach_cp))
    if diff == "easy":
        decoys = [s for s, _ in others_by_closeness[::-1][:k - 1]]   # furthest in eval = easiest to tell apart
    else:  # medium / hard -> closest in eval = hardest
        decoys = [s for s, _ in others_by_closeness[:k - 1]]
    options = [coach_san] + decoys
    rng.shuffle(options)
    return options


def prediction_log_row(session_id, user_id, move_number, fen_before, options,
                       coach_move, guessed_move, rating, difficulty, fired_reason, ts) -> dict:
    """The evidence-log row = the student model's INPUT INTERFACE (move_predictions collection).
    Append-only + over-captured so the model (next phase) reads it with no migration."""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "move_number": move_number,
        "fen_before": fen_before,
        "options": options,
        "coach_move": coach_move,
        "guessed_move": guessed_move,
        "correct": guessed_move == coach_move,
        "rating": rating,
        "difficulty": difficulty,
        "fired_reason": fired_reason,
        "ts": ts,
    }
