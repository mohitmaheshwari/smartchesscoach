"""
Move Teaching Template Engine
Converts Stockfish analysis data into English coaching captions
"""

def classify_move(cp_loss: float, user_rating: int = 1500) -> str:
    """
    Classify a move based on cp_loss and user rating.
    Uses rating-aware thresholds (from deterministic_coach_service.py)
    """
    if user_rating < 1000:
        if cp_loss >= 300:
            return "BLUNDER"
        elif cp_loss >= 150:
            return "MISTAKE"
        elif cp_loss >= 75:
            return "INACCURACY"
        else:
            return "IMPRECISE"
    elif user_rating < 1400:
        if cp_loss >= 200:
            return "BLUNDER"
        elif cp_loss >= 100:
            return "MISTAKE"
        elif cp_loss >= 50:
            return "INACCURACY"
        else:
            return "IMPRECISE"
    elif user_rating < 1800:
        if cp_loss >= 150:
            return "BLUNDER"
        elif cp_loss >= 75:
            return "MISTAKE"
        elif cp_loss >= 40:
            return "INACCURACY"
        else:
            return "IMPRECISE"
    else:  # 1800+
        if cp_loss >= 100:
            return "BLUNDER"
        elif cp_loss >= 50:
            return "MISTAKE"
        elif cp_loss >= 30:
            return "INACCURACY"
        else:
            return "IMPRECISE"


def format_evaluation(cp: int) -> str:
    """
    Convert centipawn evaluation to readable format.
    Example: 250 → "+2.5", -150 → "-1.5"
    """
    if cp == 0:
        return "equal"

    sign = "+" if cp > 0 else ""
    elo_equivalent = cp / 100

    if abs(elo_equivalent) < 0.5:
        return f"{sign}{elo_equivalent:.1f} (nearly equal)"
    elif abs(elo_equivalent) < 2:
        return f"{sign}{elo_equivalent:.1f} (slight advantage)"
    elif abs(elo_equivalent) < 4:
        return f"{sign}{elo_equivalent:.1f} (clear advantage)"
    else:
        return f"{sign}{elo_equivalent:.1f} (winning)"


def build_move_caption(
    user_move: str,
    best_move: str,
    your_eval: int,
    best_eval: int,
    best_line: str = None,
    user_rating: int = 1500,
) -> dict:
    """
    Build a complete move teaching caption from Stockfish analysis.

    Args:
        user_move: SAN notation of user's move (e.g., "Nxd4")
        best_move: SAN notation of best move (e.g., "a3")
        your_eval: Stockfish evaluation after user's move (centipawns)
        best_eval: Stockfish evaluation after best move (centipawns)
        best_line: Best continuation line from Stockfish (e.g., "a3 Nbd7 Qd3")
        user_rating: User's rating for classification thresholds

    Returns:
        Dictionary with caption components:
        - classification: BLUNDER / MISTAKE / INACCURACY / IMPRECISE
        - move_played: user's move
        - best_move: recommended move
        - cp_loss: how much the move loses
        - headline: one-line evaluation
        - analysis: detailed teaching
        - best_plan: what Stockfish wants to play after best move
    """

    # Calculate cp_loss (how much the move costs)
    cp_loss = best_eval - your_eval

    # Classify the move
    classification = classify_move(cp_loss, user_rating)

    # If no evaluation change, it's a good move
    if cp_loss <= 0:
        return {
            "classification": "GOOD",
            "move_played": user_move,
            "best_move": user_move,
            "cp_loss": 0,
            "headline": f"{user_move} — Well played!",
            "analysis": f"Stockfish approves. You maintain {format_evaluation(your_eval)}.",
            "best_plan": extract_plan_from_line(best_line),
            "show_teaching": False  # Good moves don't need explanation
        }

    # Build the teaching caption
    your_eval_str = format_evaluation(your_eval)
    best_eval_str = format_evaluation(best_eval)
    best_plan = extract_plan_from_line(best_line) if best_line else "advantage"

    headline = f"{user_move} is a {classification.lower()} (loses {cp_loss}cp)"

    analysis = f"""You played {user_move}.

Stockfish analysis:
• After {user_move}: White has {your_eval_str}
• After {best_move}: White has {best_eval_str}

Better was {best_move}. After {best_move}, the plan is {best_plan}."""

    return {
        "classification": classification,
        "move_played": user_move,
        "best_move": best_move,
        "cp_loss": cp_loss,
        "your_eval": your_eval,
        "best_eval": best_eval,
        "headline": headline,
        "analysis": analysis,
        "best_plan": best_plan,
        "show_teaching": True  # Show explanation for mistakes
    }


def extract_plan_from_line(best_line: str) -> str:
    """
    Extract the key idea from Stockfish's best line.
    Example: "a3 Nbd7 Qd3" → "a3, developing with Qd3"
    """
    if not best_line:
        return "continuing development"

    moves = best_line.split()[:3]  # First 3 moves give the plan
    if len(moves) >= 2:
        return f"{moves[0]}, followed by {' and '.join(moves[1:])}"
    elif len(moves) == 1:
        return moves[0]
    else:
        return "the best continuation"
