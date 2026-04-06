"""
Position Evaluation Labels
===========================

Converts Stockfish centipawn evaluations into human-readable labels.

Usage:
    from services.position_eval_label import get_eval_label, get_eval_label_from_fen

    # From existing eval (fast, no Stockfish call)
    label = get_eval_label(150, "white")
    # {"label": "Slight edge", "short": "+1.5", "category": "slight_edge",
    #  "color": "white", "icon": "trending_up", "description": "White is slightly better."}

    # From FEN (runs Stockfish, ~0.3s)
    label = get_eval_label_from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "white")
"""

import chess
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_eval_label(eval_cp: int, user_color: str = "white") -> Dict:
    """
    Convert centipawn eval into a human-readable position assessment.

    Args:
        eval_cp: Evaluation in centipawns from WHITE's perspective
        user_color: "white" or "black" — determines "you" vs "opponent"

    Returns dict with:
        label: Human-readable (e.g., "You're winning")
        short: Compact eval (e.g., "+2.3")
        raw_cp: Raw centipawns
        category: Machine-readable (e.g., "winning", "losing", "equal")
        description: One sentence about the position
        sentiment: "positive" | "neutral" | "negative" (from user's perspective)
    """
    # Flip eval to user's perspective
    user_eval = eval_cp if user_color == "white" else -eval_cp

    # Format the short eval string
    if abs(eval_cp) >= 10000:
        # Mate
        mate_in = (10000 - abs(eval_cp)) if eval_cp > 0 else (10000 + eval_cp)
        if user_eval > 0:
            short = f"M{max(1, abs(mate_in) // 100)}"
        else:
            short = f"-M{max(1, abs(mate_in) // 100)}"
    else:
        val = user_eval / 100
        short = f"+{val:.1f}" if val > 0 else f"{val:.1f}" if val < 0 else "0.0"

    # Categorize
    if user_eval >= 900:
        return _build("Completely winning", short, eval_cp, "completely_winning", "positive",
                       "You're completely winning. Convert carefully — don't give chances.")
    elif user_eval >= 500:
        return _build("Winning", short, eval_cp, "winning", "positive",
                       "You're winning. Simplify by trading pieces, not pawns.")
    elif user_eval >= 300:
        return _build("Clear advantage", short, eval_cp, "clear_advantage", "positive",
                       "You have a clear advantage — about a full piece ahead in value.")
    elif user_eval >= 150:
        return _build("Solid edge", short, eval_cp, "solid_edge", "positive",
                       "You have a solid edge. Keep pressing — small advantages add up.")
    elif user_eval >= 50:
        return _build("Slight edge", short, eval_cp, "slight_edge", "positive",
                       "Slightly better. The position is close but you have a small pull.")
    elif user_eval > -50:
        return _build("Equal", short, eval_cp, "equal", "neutral",
                       "The position is roughly equal. Both sides have chances.")
    elif user_eval > -150:
        return _build("Slightly worse", short, eval_cp, "slightly_worse", "negative",
                       "Your opponent has a small edge. Stay solid and look for counterplay.")
    elif user_eval > -300:
        return _build("Under pressure", short, eval_cp, "under_pressure", "negative",
                       "You're under pressure. Don't panic — look for active moves.")
    elif user_eval > -500:
        return _build("Losing", short, eval_cp, "losing", "negative",
                       "You're behind. Keep the position complicated and look for tricks.")
    elif user_eval > -900:
        return _build("Badly losing", short, eval_cp, "badly_losing", "negative",
                       "Tough position. Fight for every move — comebacks happen.")
    else:
        return _build("Lost", short, eval_cp, "lost", "negative",
                       "The position is lost. Look for any trick or stalemate chance.")


def _build(label, short, raw_cp, category, sentiment, description):
    return {
        "label": label,
        "short": short,
        "raw_cp": raw_cp,
        "category": category,
        "sentiment": sentiment,
        "description": description,
    }


def get_eval_label_from_fen(fen: str, user_color: str = "white", depth: int = 12) -> Optional[Dict]:
    """
    Run Stockfish on a FEN and return the eval label.
    Costs ~0.3s per call.
    """
    try:
        from stockfish_service import StockfishEngine
        engine = StockfishEngine()
        engine.start()
        try:
            board = chess.Board(fen)
            result = engine.analyze(board, depth=depth)
            eval_cp = result.get("eval_cp", 0)
            return get_eval_label(eval_cp, user_color)
        finally:
            engine.stop()
    except Exception as e:
        logger.warning(f"Stockfish eval failed: {e}")
        return None
