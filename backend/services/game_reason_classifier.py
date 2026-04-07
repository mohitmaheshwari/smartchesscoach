"""
Game Reason Classifier
=======================

Tags each game with ONE human-readable chess category explaining
why the game was won or lost.

NOT engine language. NOT pattern keys. Chess understanding categories.

Categories (losses):
  - tactical_miss:       "Missed a simple tactic"
  - one_move_blunder:    "Left a piece hanging"
  - calculation_error:   "Saw the idea but miscalculated"
  - positional:          "Outplayed positionally"
  - endgame_collapse:    "Couldn't convert the endgame"
  - opening_disaster:    "Went wrong in the opening"
  - time_collapse:       "Collapsed under time pressure"
  - threw_winning:       "Threw a winning position"

Categories (wins):
  - tactical_win:        "Won through tactics"
  - solid_play:          "Played solid — opponent made mistakes"
  - brilliant_play:      "Found a brilliant move"
  - endgame_conversion:  "Converted the endgame well"
  - opponent_blundered:  "Opponent gave the game away"

Categories (draws):
  - held_worse:          "Held a worse position to a draw"
  - missed_win:          "Had a winning position but couldn't convert"
  - solid_draw:          "Solid game, fair result"
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── CATEGORY DEFINITIONS ──
LOSS_CATEGORIES = {
    "tactical_miss": {
        "label": "Missed a simple tactic",
        "description": "You didn't see a tactic that was available — a fork, pin, or winning capture.",
    },
    "one_move_blunder": {
        "label": "Left a piece hanging",
        "description": "You put a piece where it could be taken for free. One careless move cost the game.",
    },
    "calculation_error": {
        "label": "Miscalculated a sequence",
        "description": "You saw the right idea but got the move order wrong or missed a defensive resource.",
    },
    "positional": {
        "label": "Outplayed positionally",
        "description": "Your pieces ended up on bad squares. Your opponent had a better plan.",
    },
    "endgame_collapse": {
        "label": "Couldn't convert the endgame",
        "description": "You reached an endgame you should have drawn or won, but didn't know the technique.",
    },
    "opening_disaster": {
        "label": "Went wrong in the opening",
        "description": "A mistake in the first 15 moves put you in a bad position from the start.",
    },
    "time_collapse": {
        "label": "Ran out of time / collapsed under pressure",
        "description": "Your play fell apart when the clock was low or the position got complicated.",
    },
    "threw_winning": {
        "label": "Threw a winning position",
        "description": "You were winning and gave it away. One moment of carelessness cost everything.",
    },
}

WIN_CATEGORIES = {
    "tactical_win": {
        "label": "Won through tactics",
        "description": "You found a tactic that decided the game.",
    },
    "solid_play": {
        "label": "Played solid chess",
        "description": "You made fewer mistakes than your opponent. Clean game.",
    },
    "brilliant_play": {
        "label": "Found a brilliant move",
        "description": "You calculated deeply and found something special.",
    },
    "endgame_conversion": {
        "label": "Converted the endgame",
        "description": "You reached a favorable endgame and finished the job.",
    },
    "opponent_blundered": {
        "label": "Opponent gave it away",
        "description": "You won because your opponent made a bigger mistake, not because you played great.",
    },
}

DRAW_CATEGORIES = {
    "held_worse": {
        "label": "Held a worse position",
        "description": "You were under pressure but found a way to draw.",
    },
    "missed_win": {
        "label": "Had a win but couldn't convert",
        "description": "You had a winning position but couldn't find the finish.",
    },
    "solid_draw": {
        "label": "Solid game",
        "description": "Even game throughout. Fair result.",
    },
}

ALL_CATEGORIES = {**LOSS_CATEGORIES, **WIN_CATEGORIES, **DRAW_CATEGORIES}


def classify_game_reason(
    move_evaluations: List[Dict],
    game_result: str,
    user_color: str,
    termination: str = "unknown",
    accuracy: float = 0,
) -> Dict:
    """
    Classify a game into ONE chess understanding category.

    Args:
        move_evaluations: List of move eval dicts from stockfish analysis
        game_result: "1-0", "0-1", "1/2-1/2"
        user_color: "white" or "black"
        termination: "checkmate", "resignation", "timeout", etc.
        accuracy: Overall accuracy percentage

    Returns:
        {
            "category": "tactical_miss",
            "label": "Missed a simple tactic",
            "description": "You didn't see a tactic...",
            "result": "loss",
            "critical_move": 18,  # move number where game was decided
        }
    """
    user_won = (game_result == "1-0" and user_color == "white") or \
               (game_result == "0-1" and user_color == "black")
    is_draw = "1/2" in game_result
    user_lost = not user_won and not is_draw

    if not move_evaluations:
        if user_won:
            return _build("solid_play", "win")
        elif is_draw:
            return _build("solid_draw", "draw")
        else:
            return _build("one_move_blunder", "loss")

    # ── EXTRACT SIGNALS FROM MOVES ──
    total_moves = len(move_evaluations)
    blunders = []  # moves with cp_loss >= 200
    mistakes = []  # moves with cp_loss >= 100
    late_mistakes = []  # mistakes in last 15 moves
    opening_mistakes = []  # mistakes in first 15 moves
    endgame_mistakes = []  # mistakes when few pieces on board

    was_winning = False  # Was user ever +200 or more?
    max_advantage = 0
    collapse_move = None  # Move where advantage was lost
    brilliant_count = 0

    for m in move_evaluations:
        cp_loss = abs(m.get("cp_loss", 0) or 0)
        eval_before = m.get("eval_before", 0) or 0
        eval_after = m.get("eval_after", 0) or 0
        move_num = m.get("move_number", 0) or 0
        is_brilliant = m.get("is_brilliant", False)
        fen = m.get("fen_before", "")
        gap = m.get("cognitive_gap", "")

        if is_brilliant:
            brilliant_count += 1

        # Normalize eval to user's perspective
        if isinstance(eval_before, float) and abs(eval_before) < 100:
            user_eval = eval_before * 100 if user_color == "white" else -eval_before * 100
        else:
            user_eval = eval_before if user_color == "white" else -eval_before

        if user_eval > max_advantage:
            max_advantage = user_eval
        if user_eval > 200:
            was_winning = True

        if cp_loss >= 200:
            blunders.append(m)
        if cp_loss >= 100:
            mistakes.append(m)
            if move_num > total_moves - 15:
                late_mistakes.append(m)
            if move_num <= 15:
                opening_mistakes.append(m)
            # Rough endgame check: move > 30 or few pieces
            pieces_in_fen = sum(1 for c in fen.split(" ")[0] if c.isalpha()) if fen else 32
            if pieces_in_fen <= 12 or move_num > 35:
                endgame_mistakes.append(m)

        # Detect collapse point (was winning, now losing)
        if user_eval < -100 and was_winning and not collapse_move:
            collapse_move = move_num

    # ── CLASSIFY LOSSES ──
    if user_lost:
        # Timeout — only actual timeout, not abandonment
        # Abandoned games should be classified by what was happening in the game
        if termination == "timeout":
            return _build("time_collapse", "loss")

        # Threw a winning position
        if was_winning and max_advantage >= 200:
            return _build("threw_winning", "loss", collapse_move)

        # Opening disaster (most mistakes in first 15 moves)
        if len(opening_mistakes) >= 2 and len(opening_mistakes) >= len(mistakes) * 0.6:
            critical = min(opening_mistakes, key=lambda m: -(m.get("cp_loss", 0) or 0))
            return _build("opening_disaster", "loss", critical.get("move_number"))

        # Endgame collapse
        if len(endgame_mistakes) >= 2 and len(endgame_mistakes) >= len(mistakes) * 0.5:
            critical = min(endgame_mistakes, key=lambda m: -(m.get("cp_loss", 0) or 0))
            return _build("endgame_collapse", "loss", critical.get("move_number"))

        # One-move blunder (single huge mistake decided everything)
        huge_blunders = [b for b in blunders if (b.get("cp_loss", 0) or 0) >= 300]
        if len(huge_blunders) == 1 and len(mistakes) <= 3:
            b = huge_blunders[0]
            gap = b.get("cognitive_gap", "")
            if gap in ("piece_safety", "hanging_piece"):
                return _build("one_move_blunder", "loss", b.get("move_number"))
            else:
                return _build("tactical_miss", "loss", b.get("move_number"))

        # Multiple tactical misses
        tactical_gaps = [m for m in mistakes if m.get("cognitive_gap", "") in
                        ("missed_tactic", "tactical_oversight", "piece_safety", "hanging_piece")]
        if len(tactical_gaps) >= 2:
            critical = max(tactical_gaps, key=lambda m: m.get("cp_loss", 0) or 0)
            return _build("tactical_miss", "loss", critical.get("move_number"))

        # Calculation errors
        calc_gaps = [m for m in mistakes if m.get("cognitive_gap", "") in
                    ("calculation_depth", "short_calculation")]
        if len(calc_gaps) >= 2:
            critical = max(calc_gaps, key=lambda m: m.get("cp_loss", 0) or 0)
            return _build("calculation_error", "loss", critical.get("move_number"))

        # Late collapse (time pressure signal)
        if len(late_mistakes) >= 3 and len(late_mistakes) >= len(mistakes) * 0.6:
            return _build("time_collapse", "loss")

        # Positional — many small mistakes, no huge blunders
        if len(blunders) == 0 and len(mistakes) >= 3:
            return _build("positional", "loss")

        # Default loss
        if blunders:
            critical = max(blunders, key=lambda m: m.get("cp_loss", 0) or 0)
            return _build("one_move_blunder", "loss", critical.get("move_number"))

        return _build("tactical_miss", "loss")

    # ── CLASSIFY WINS ──
    if user_won:
        # Brilliant play
        if brilliant_count > 0:
            return _build("brilliant_play", "win")

        # Clean win with high accuracy
        if accuracy >= 80 and len(blunders) == 0:
            return _build("solid_play", "win")

        # Endgame conversion
        if len(endgame_mistakes) == 0 and total_moves > 30:
            return _build("endgame_conversion", "win")

        # Tactical win (opponent had more mistakes)
        if len(mistakes) <= 2:
            return _build("tactical_win", "win")

        # Won despite own mistakes — opponent was worse
        if len(blunders) >= 2:
            return _build("opponent_blundered", "win")

        return _build("solid_play", "win")

    # ── CLASSIFY DRAWS ──
    if is_draw:
        if was_winning and max_advantage >= 300:
            return _build("missed_win", "draw")

        if len(mistakes) <= 1:
            return _build("solid_draw", "draw")

        return _build("held_worse", "draw")

    return _build("solid_play", "win" if user_won else "loss")


def _build(category: str, result: str, critical_move: int = None) -> Dict:
    """Build the classification result."""
    cat_data = ALL_CATEGORIES.get(category, {"label": category, "description": ""})
    return {
        "category": category,
        "label": cat_data["label"],
        "description": cat_data["description"],
        "result": result,
        "critical_move": critical_move,
    }


def aggregate_game_reasons(game_reasons: List[Dict]) -> List[Dict]:
    """
    Aggregate game reasons into top 3 problems.

    Input: list of classify_game_reason outputs
    Output: top 3 categories ranked by frequency + impact

    Only counts losses and draws (wins don't need fixing).
    """
    problem_counts = {}

    for gr in game_reasons:
        result = gr.get("result", "")
        category = gr.get("category", "")

        # Only count problems (losses and negative draws)
        if result == "loss" or (result == "draw" and category == "missed_win"):
            if category not in problem_counts:
                problem_counts[category] = {
                    "category": category,
                    "label": gr.get("label", ""),
                    "description": gr.get("description", ""),
                    "count": 0,
                    "example_moves": [],
                }
            problem_counts[category]["count"] += 1
            if gr.get("critical_move"):
                problem_counts[category]["example_moves"].append(gr["critical_move"])

    # Sort by count, take top 3
    ranked = sorted(problem_counts.values(), key=lambda x: -x["count"])
    return ranked[:3]
