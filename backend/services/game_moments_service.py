"""
Game Moments Service
=====================

Extracts 3-4 key moments from a game for Coach Replay.
Not every move. Not one move. The STORY of the game.

Each moment has:
- FEN (before and after)
- What was happening (eval-driven context)
- What the user missed (board reading)
- Connection to their behavior pattern

Moments:
1. Context — where things were fine (or already wrong)
2. Warning — first sign of trouble (or missed opportunity)
3. Break — the decisive mistake
4. (Optional) Missed opportunity from opponent
"""

import chess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_game_moments(
    move_evaluations: List[Dict],
    game_result: str,
    user_color: str,
    termination: str = "unknown",
) -> List[Dict]:
    """
    Extract 3-4 key moments from a game.

    Returns list of moments, each with:
    {
        "type": "context" | "warning" | "break" | "missed_chance",
        "move_number": 18,
        "fen_before": "...",
        "fen_after": "...",
        "move_played": "Nd4",
        "best_move": "Be3",
        "eval_before": 1.8,   (from user's perspective)
        "eval_after": -2.3,
        "cp_loss": 410,
        "context_text": "You were winning here.",  (eval-driven, not hardcoded)
    }
    """
    if not move_evaluations:
        return []

    user_is_white = user_color == "white"
    user_won = (game_result == "1-0" and user_is_white) or (game_result == "0-1" and not user_is_white)
    user_lost = not user_won and "1/2" not in game_result

    # Compute user-perspective evals for all moves
    moves_with_eval = []
    for m in move_evaluations:
        eb = m.get("eval_before", 0) or 0
        ea = m.get("eval_after", 0) or 0

        # Normalize to centipawns if float
        if isinstance(eb, float) and abs(eb) < 100:
            eb = eb * 100
        if isinstance(ea, float) and abs(ea) < 100:
            ea = ea * 100

        # User perspective
        user_eb = eb if user_is_white else -eb
        user_ea = ea if user_is_white else -ea

        cp_loss = m.get("cp_loss", 0) or 0
        moves_with_eval.append({
            **m,
            "user_eval_before": user_eb,
            "user_eval_after": user_ea,
            "abs_cp_loss": abs(cp_loss),
        })

    moments = []

    # ── FIND THE BREAK — the decisive mistake (highest cp_loss) ──
    sorted_by_loss = sorted(moves_with_eval, key=lambda x: x["abs_cp_loss"], reverse=True)
    break_move = sorted_by_loss[0] if sorted_by_loss else None

    if not break_move or break_move["abs_cp_loss"] < 50:
        return []  # No significant mistake

    # ── FIND CONTEXT — a calm position 3-5 moves before the break ──
    break_mn = break_move.get("move_number", 0)
    context_move = None
    for m in moves_with_eval:
        mn = m.get("move_number", 0)
        if mn >= break_mn - 5 and mn <= break_mn - 2 and m["abs_cp_loss"] < 30:
            context_move = m
            break
    # Fallback: just pick 3 moves before
    if not context_move:
        for m in moves_with_eval:
            if m.get("move_number", 0) == max(1, break_mn - 3):
                context_move = m
                break

    # ── FIND WARNING — a smaller mistake or the first sign of trouble ──
    # Look for moves between context and break with moderate cp_loss
    warning_move = None
    for m in moves_with_eval:
        mn = m.get("move_number", 0)
        if mn > (context_move.get("move_number", 0) if context_move else 0) and mn < break_mn:
            if m["abs_cp_loss"] >= 50 and m["abs_cp_loss"] < break_move["abs_cp_loss"]:
                warning_move = m
                break

    # ── FIND MISSED CHANCE — opponent blundered but user didn't punish ──
    # Look for moves where eval swung IN user's favor but user didn't capitalize
    missed_chance = None
    if user_lost:
        for m in moves_with_eval:
            # Eval improved for user (opponent's mistake) but then dropped again
            mn = m.get("move_number", 0)
            if mn > break_mn:
                continue
            if m["user_eval_before"] < -50 and m["user_eval_after"] > 50:
                # Opponent gave back advantage but we need to check if user used it
                # Find the next move — did eval drop again?
                next_moves = [x for x in moves_with_eval if x.get("move_number", 0) == mn + 1]
                if next_moves and next_moves[0]["abs_cp_loss"] >= 100:
                    missed_chance = next_moves[0]
                    break

    # ── BUILD MOMENTS ──

    # 1. Context
    if context_move:
        eval_b = context_move["user_eval_before"]
        moments.append({
            "type": "context",
            "move_number": context_move.get("move_number"),
            "fen_before": context_move.get("fen_before", ""),
            "eval_before": round(eval_b / 100, 1),
            "context_text": _eval_context(eval_b, "context"),
        })

    # 2. Warning (optional)
    if warning_move:
        eval_b = warning_move["user_eval_before"]
        eval_a = warning_move["user_eval_after"]
        moments.append({
            "type": "warning",
            "move_number": warning_move.get("move_number"),
            "fen_before": warning_move.get("fen_before", ""),
            "fen_after": _get_fen_after(warning_move),
            "eval_before": round(eval_b / 100, 1),
            "eval_after": round(eval_a / 100, 1),
            "cp_loss": warning_move["abs_cp_loss"],
            "context_text": _eval_context(eval_b, "warning"),
        })

    # 3. Break (always)
    eval_b = break_move["user_eval_before"]
    eval_a = break_move["user_eval_after"]
    moments.append({
        "type": "break",
        "move_number": break_move.get("move_number"),
        "fen_before": break_move.get("fen_before", ""),
        "fen_after": _get_fen_after(break_move),
        "eval_before": round(eval_b / 100, 1),
        "eval_after": round(eval_a / 100, 1),
        "cp_loss": break_move["abs_cp_loss"],
        "context_text": _eval_context(eval_b, "break"),
        "pv_after_played": break_move.get("pv_after_played", []),
    })

    # 4. Missed chance (optional)
    if missed_chance:
        eval_b = missed_chance["user_eval_before"]
        moments.append({
            "type": "missed_chance",
            "move_number": missed_chance.get("move_number"),
            "fen_before": missed_chance.get("fen_before", ""),
            "eval_before": round(eval_b / 100, 1),
            "context_text": "Your opponent made a mistake here. You didn't see it.",
        })

    return moments


def _eval_context(eval_cp: float, moment_type: str) -> str:
    """Generate truthful context based on eval — no lies."""
    if moment_type == "context":
        if eval_cp > 200:
            return "You were winning here."
        elif eval_cp > 50:
            return "You had a small edge."
        elif eval_cp > -50:
            return "The position was balanced."
        elif eval_cp > -200:
            return "You were slightly worse."
        else:
            return "You were already under pressure."

    elif moment_type == "warning":
        if eval_cp > 200:
            return "You were still winning, but this was the first slip."
        elif eval_cp > 50:
            return "The position was starting to shift."
        elif eval_cp > -50:
            return "Things were getting uncomfortable."
        else:
            return "You were already in trouble."

    elif moment_type == "break":
        if eval_cp > 200:
            return "You were winning. Then this happened."
        elif eval_cp > 50:
            return "You had an edge. This is where it disappeared."
        elif eval_cp > -50:
            return "The position was level. One move changed everything."
        elif eval_cp > -200:
            return "You were worse, but there was still a chance. This ended it."
        else:
            return "The position was already difficult."

    return ""


def _get_fen_after(move_data: Dict) -> str:
    """Get FEN after a move was played."""
    fen_before = move_data.get("fen_before", "")
    move_san = move_data.get("move", "")
    if not fen_before or not move_san:
        return fen_before
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(move_san)
        board.push(move)
        return board.fen()
    except Exception:
        return fen_before
