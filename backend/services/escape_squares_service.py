"""
Escape Squares Service — "Count the Escape Squares" coaching tool
==================================================================

Detects positions where counting escape squares is pedagogically valuable,
generates quiz data, and validates user answers.

Teaching moments:
  - King is in check with limited escapes
  - King has weak pawn cover and few escape squares
  - After a move that restricts opponent's king mobility
  - Before delivering a back-rank or corridor mate threat
"""

import chess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def count_king_escape_squares(fen: str, king_color_str: str) -> Dict:
    """
    Count escape squares for a king and return detailed analysis.

    Args:
        fen: Board position in FEN
        king_color_str: "white" or "black"

    Returns:
        Dict with escape_count, squares list, blocked_by info, and teaching context
    """
    board = chess.Board(fen)
    king_color = chess.WHITE if king_color_str == "white" else chess.BLACK
    attacker_color = not king_color
    king_sq = board.king(king_color)

    if king_sq is None:
        return {"error": "No king found", "escape_count": 0, "squares": []}

    escapes = []
    blocked = []

    for sq in chess.SQUARES:
        if chess.square_distance(king_sq, sq) != 1:
            continue

        sq_name = chess.square_name(sq)
        piece = board.piece_at(sq)

        # Occupied by own piece
        if piece and piece.color == king_color:
            blocked.append({"square": sq_name, "reason": "own_piece", "piece": piece.symbol()})
            continue

        # Attacked by opponent
        if board.is_attacked_by(attacker_color, sq):
            reason = "attacked"
            attackers = board.attackers(attacker_color, sq)
            attacker_names = []
            for a_sq in attackers:
                a_piece = board.piece_at(a_sq)
                if a_piece:
                    attacker_names.append(f"{a_piece.symbol()} on {chess.square_name(a_sq)}")
            blocked.append({"square": sq_name, "reason": reason, "attacked_by": attacker_names})
            continue

        escapes.append(sq_name)

    return {
        "king_square": chess.square_name(king_sq),
        "king_color": king_color_str,
        "escape_count": len(escapes),
        "escape_squares": escapes,
        "blocked_squares": blocked,
        "is_in_check": board.is_check(),
        "total_adjacent": sum(1 for sq in chess.SQUARES if chess.square_distance(king_sq, sq) == 1),
    }


def is_escape_squares_teaching_moment(fen: str, user_color_str: str) -> Optional[Dict]:
    """
    Determine if this position is a good moment to ask the user
    to count opponent's king escape squares.

    Returns quiz data if it's a teaching moment, None otherwise.
    """
    board = chess.Board(fen)
    user_color = chess.WHITE if user_color_str == "white" else chess.BLACK
    opp_color_str = "black" if user_color_str == "white" else "white"
    opp_color = not user_color

    opp_king_sq = board.king(opp_color)
    if opp_king_sq is None:
        return None

    # Count escape squares for opponent's king
    analysis = count_king_escape_squares(fen, opp_color_str)
    escape_count = analysis["escape_count"]

    # Teaching moment conditions:
    # 1. Opponent king is in check → always ask
    if board.is_check() and board.turn == opp_color:
        return _build_quiz(analysis, "check", user_color_str)

    # 2. Opponent king has 0-2 escape squares (restricted)
    if escape_count <= 2:
        # Verify there's actual attacking pressure
        opp_king_attacked = board.is_attacked_by(user_color, opp_king_sq)
        adjacent_attacks = sum(
            1 for sq in chess.SQUARES
            if chess.square_distance(opp_king_sq, sq) == 1
            and board.is_attacked_by(user_color, sq)
        )
        if adjacent_attacks >= 3 or opp_king_attacked:
            return _build_quiz(analysis, "restricted", user_color_str)

    # 3. Back-rank situation (king on rank 1 or 8 with pawns blocking)
    king_rank = chess.square_rank(opp_king_sq)
    if king_rank in (0, 7):  # Back rank
        king_file = chess.square_file(opp_king_sq)
        pawn_rank = king_rank + (1 if opp_color == chess.WHITE else -1)
        if 0 <= pawn_rank <= 7:
            pawns_blocking = 0
            for f in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
                sq = chess.square(f, pawn_rank)
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == opp_color:
                    pawns_blocking += 1
            if pawns_blocking >= 2 and escape_count <= 1:
                return _build_quiz(analysis, "back_rank", user_color_str)

    return None


def _build_quiz(analysis: Dict, trigger: str, user_color: str) -> Dict:
    """Build the quiz payload for the frontend."""
    prompts = {
        "check": "The opponent's king is in check! How many escape squares does it have?",
        "restricted": "The opponent's king looks boxed in. Count carefully — how many safe squares can it move to?",
        "back_rank": "Look at the back rank. How many escape squares does the opponent's king have?",
    }

    hints = {
        "check": "Remember: a square is NOT safe if it's attacked by your pieces or occupied by the opponent's own pieces.",
        "restricted": "Check every adjacent square. Is it attacked by you? Occupied by their own piece? Both block escape.",
        "back_rank": "Back-rank mates happen when the king's own pawns trap it. Count the free squares carefully.",
    }

    return {
        "quiz_type": "count_escape_squares",
        "trigger": trigger,
        "prompt": prompts.get(trigger, prompts["restricted"]),
        "hint": hints.get(trigger, hints["restricted"]),
        "correct_answer": analysis["escape_count"],
        "king_square": analysis["king_square"],
        "king_color": analysis["king_color"],
        "user_color": user_color,
        "details": {
            "escape_squares": analysis["escape_squares"],
            "blocked_squares": analysis["blocked_squares"],
            "is_in_check": analysis["is_in_check"],
        },
    }


def validate_escape_squares_answer(quiz_data: Dict, user_answer: int) -> Dict:
    """
    Validate the user's answer and generate feedback.
    """
    correct = quiz_data["correct_answer"]
    is_correct = user_answer == correct
    details = quiz_data.get("details", {})

    if is_correct:
        escape_list = details.get("escape_squares", [])
        squares_text = ", ".join(escape_list) if escape_list else "none"
        message = f"Correct! The king has {correct} escape square{'s' if correct != 1 else ''}"
        if escape_list:
            message += f": {squares_text}."
        else:
            message += ". It's completely trapped!"

        if correct == 0:
            message += " This means a check here could be checkmate!"
        elif correct == 1:
            message += " With only one escape, you can plan to control that square too."
    else:
        message = f"Not quite — the king actually has {correct} escape square{'s' if correct != 1 else ''}, not {user_answer}. "
        if user_answer < correct:
            missed = [sq for sq in details.get("escape_squares", [])]
            if missed:
                message += f"You might have missed: {', '.join(missed)}. "
        else:
            blocked = details.get("blocked_squares", [])
            attacked = [b for b in blocked if b.get("reason") == "attacked"]
            if attacked:
                message += "Remember, squares attacked by your pieces aren't safe. "
        message += "Always check every adjacent square one by one."

    return {
        "correct": is_correct,
        "correct_answer": correct,
        "user_answer": user_answer,
        "message": message,
        "escape_squares": details.get("escape_squares", []),
        "blocked_squares": details.get("blocked_squares", []),
    }
