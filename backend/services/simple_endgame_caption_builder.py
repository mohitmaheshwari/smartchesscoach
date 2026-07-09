"""
Simple Endgame Caption Builder — Deterministic, local, no Claude.

Analyzes endgame moves using simple principle checks.
"""

import logging
import chess
from typing import Dict, Optional

logger = logging.getLogger(__name__)


async def build_endgame_caption(
    fen: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str],
) -> Dict:
    """
    Build principle-based endgame caption without Claude.

    Args:
        fen: Position FEN
        move_san: Move SAN
        eval_before: Eval before move
        eval_after: Eval after move
        best_move_san: Best move if different

    Returns:
        {
            "caption": "explanation",
            "principles": ["principle1", ...],
            "quality_score": 0.7,
            "method": "deterministic"
        }
    """

    try:
        board = chess.Board(fen)
    except:
        return _fallback_caption(move_san, best_move_san, eval_before - eval_after)

    # Find the move
    move = None
    for m in board.legal_moves:
        if board.san(m) == move_san:
            move = m
            break

    if not move:
        return _fallback_caption(move_san, best_move_san, eval_before - eval_after)

    cp_loss = eval_before - eval_after
    user_color = chess.WHITE if board.turn else chess.BLACK

    # Analyze the move
    caption_lines = []
    principles = []

    # Check for promotion threats
    opp_color = not user_color
    for pawn_sq in board.pieces(chess.PAWN, opp_color):
        pawn_rank = chess.square_rank(pawn_sq)
        pawn_file = chess.square_file(pawn_sq)

        # Is this pawn threatening?
        if opp_color == chess.WHITE and pawn_rank >= 6:
            promotion_sq = chess.square(pawn_file, 7)
            # After move, do we defend?
            board.push(move)
            defended = board.is_attacked_by(user_color, promotion_sq)
            board.pop()

            if defended:
                caption_lines.append(f"{move_san} defends against the promotion threat on {chess.square_name(promotion_sq)}.")
                principles.append("promotion_defense")
            elif cp_loss > 100:
                caption_lines.append(
                    f"{move_san} allows Black's pawn to promote on {chess.square_name(promotion_sq)}."
                )
                principles.append("allows_promotion")

        elif opp_color == chess.BLACK and pawn_rank <= 2:
            promotion_sq = chess.square(pawn_file, 0)
            # After move, do we defend?
            board.push(move)
            defended = board.is_attacked_by(user_color, promotion_sq)
            board.pop()

            if defended:
                caption_lines.append(
                    f"{move_san} defends against the promotion threat on {chess.square_name(promotion_sq)}."
                )
                principles.append("promotion_defense")
            elif cp_loss > 100:
                caption_lines.append(
                    f"{move_san} allows White's pawn to promote on {chess.square_name(promotion_sq)}."
                )
                principles.append("allows_promotion")

    # If big loss and no explanation yet
    if not caption_lines:
        if cp_loss >= 300:
            caption_lines.append(f"{move_san} is a serious blunder (loses ~{int(cp_loss)} cp).")
        elif cp_loss >= 150:
            caption_lines.append(f"{move_san} is a significant mistake.")
        elif cp_loss >= 50:
            caption_lines.append(f"{move_san} is slightly inaccurate.")

    # Add better move if available
    if best_move_san and cp_loss > 50:
        caption_lines.append(f"Better: {best_move_san}.")

    caption = " ".join(caption_lines) if caption_lines else f"{move_san} is played."

    quality_score = min(0.9, 0.4 + len(principles) * 0.25)

    return {
        "caption": caption,
        "principles": principles,
        "quality_score": quality_score,
        "method": "deterministic",
    }


def _fallback_caption(move_san: str, best_move_san: Optional[str], cp_loss: float) -> Dict:
    """Fallback simple caption"""
    if cp_loss >= 300:
        caption = f"{move_san} is a blunder."
    elif cp_loss >= 150:
        caption = f"{move_san} is a serious mistake."
    elif cp_loss >= 50:
        caption = f"{move_san} is not best."
    else:
        caption = f"{move_san} is played."

    if best_move_san:
        caption += f" {best_move_san} was better."

    return {
        "caption": caption,
        "principles": [],
        "quality_score": 0.3,
        "method": "fallback",
    }
