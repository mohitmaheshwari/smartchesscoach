"""
Coach Session Puzzle Extractor
================================

After each Play with Coach game, extract positions where the player
made mistakes. These become training material for the next session.

More relevant than imported game puzzles because:
  - The coach was there when it happened
  - The player can replay the exact moment
  - Tagged with the focus cluster for targeted training
"""

import chess
import logging
from typing import List, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def extract_puzzles_from_coach_session(
    db,
    session_id: str,
    user_id: str,
    min_cp_loss: int = 120,
) -> List[Dict]:
    """
    Extract training positions from a coach session.

    Uses move_history with eval data (eval_before, eval_after, best_move).
    Only extracts user moves with significant cp_loss.

    Returns list of created puzzle dicts.
    """
    session = await db.coach_sessions.find_one(
        {"session_id": session_id},
        {"_id": 0, "move_history": 1, "user_color": 1, "user_rating": 1,
         "evaluations": 1, "detected_opening": 1, "focus_concept": 1}
    )
    if not session:
        return []

    move_history = session.get("move_history", [])
    evaluations = session.get("evaluations", [])
    user_color = session.get("user_color", "white")
    user_rating = session.get("user_rating", 1200)
    opening = session.get("detected_opening", "")
    focus = session.get("focus_concept", {})

    # Rating-aware threshold
    if user_rating < 1000:
        min_cp_loss = max(min_cp_loss, 200)
    elif user_rating < 1400:
        min_cp_loss = max(min_cp_loss, 150)

    created = []

    for i, move_entry in enumerate(move_history):
        if not isinstance(move_entry, dict):
            continue
        if move_entry.get("by") != "player":
            continue

        fen_before = move_entry.get("fen_before")
        move_san = move_entry.get("move")
        best_move = move_entry.get("best_move")
        eval_before = move_entry.get("eval_before", 0)
        eval_after = move_entry.get("eval_after", 0)

        if not fen_before or not move_san:
            continue

        # Compute cp_loss
        if user_color == "white":
            cp_loss = max(0, int((eval_before - eval_after) * 100))
        else:
            cp_loss = max(0, int((eval_after - eval_before) * 100))

        if cp_loss < min_cp_loss:
            continue

        if not best_move or best_move == move_san:
            continue

        # Validate position
        try:
            board = chess.Board(fen_before)
            board.parse_san(best_move)
            best_uci = board.parse_san(best_move).uci()
        except Exception:
            continue

        # Skip if already exists
        existing = await db.community_training_positions.find_one({
            "fen": fen_before,
            "best_move_san": best_move,
            "source_user_id": user_id,
        })
        if existing:
            continue

        # Classify pattern type
        pattern_type = _classify_pattern(board, move_san, best_move, cp_loss)

        # Difficulty
        if cp_loss >= 400:
            difficulty = "easy"
        elif cp_loss >= 200:
            difficulty = "medium"
        else:
            difficulty = "hard"

        move_number = (i // 2) + 1

        puzzle = {
            "position_id": f"coach_{session_id[:8]}_m{move_number}",
            "fen": fen_before,
            "best_move_san": best_move,
            "best_move_uci": best_uci,
            "user_move_san": move_san,
            "user_move_uci": "",
            "cp_loss": cp_loss,
            "eval_cp": int(eval_before * 100),
            "eval_before_user": int(eval_before * 100),
            "eval_after_user": int(eval_after * 100),
            "pattern_type": pattern_type,
            "moment_tag": "learning_moment",
            "difficulty": difficulty,
            "move_number": move_number,
            "opening_name": opening,
            "source_game_id": session_id,
            "source_user_id": user_id,
            "source_user_name": "",
            "source_user_rating": user_rating,
            "source_type": "coach_session",
            "user_color": user_color,
            "attempts": 0,
            "solves": 0,
            "solve_rate": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Tag with focus cluster if available
        if focus and focus.get("signal"):
            puzzle["focus_cluster"] = focus["signal"]

        await db.community_training_positions.insert_one(puzzle)
        created.append(puzzle)

    if created:
        logger.info(f"[COACH-PUZZLES] Extracted {len(created)} puzzles from session {session_id[:8]}")

    return created


def _classify_pattern(board: chess.Board, user_move: str, best_move: str, cp_loss: int) -> str:
    """Classify the type of mistake for puzzle tagging."""
    try:
        move = board.parse_san(user_move)
        best = board.parse_san(best_move)

        # Did user miss a capture?
        if board.is_capture(best) and not board.is_capture(move):
            return "tactical_oversight"

        # Did user leave a piece hanging?
        board_after = board.copy()
        board_after.push(move)
        user_color = board.turn
        opponent = not user_color
        for sq in chess.SQUARES:
            p = board_after.piece_at(sq)
            if p and p.color == user_color and p.piece_type not in (chess.KING, chess.PAWN):
                atts = board_after.attackers(opponent, sq)
                defs = board_after.attackers(user_color, sq)
                if atts and not defs:
                    return "piece_safety"

        if cp_loss >= 300:
            return "calculation_depth"

        return "tactical_oversight"
    except Exception:
        return "calculation_depth"
