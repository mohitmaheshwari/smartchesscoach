"""
Orchestrator — generate Truth line + Decryption block for a finished game.

Called once after V5 decryption data is computed. Reads V5 + game
metadata, classifies the scenario via game_reason_classifier, picks the
critical move from V5 structural fields, and produces:

    truth_line       — Coach Voice 3-liner (identity / anchor / trigger)
    decryption_block — Decryption Voice prose, validated, retried, with
                       fallback template if LLM consistently misses voice

Returns (truth_line, decryption_block). Either may be None when the user
won, no decisive move exists, or generation hit a hard failure.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .truth_line import generate_truth_line, pick_critical_move
from .decryption import generate_decryption

logger = logging.getLogger(__name__)


async def generate_post_game_voice(
    *,
    decryption_v5_data: List[Dict],
    move_evaluations: List[Dict],
    game_id: str,
    game_result: str,
    user_color: str,
    termination: str = "unknown",
    accuracy: float = 0,
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Build (truth_line, decryption_block) for a finished game."""

    # Skip wins — Truth/Decryption surfaces are for losses and draws.
    user_won = (
        (user_color == "white" and game_result == "1-0")
        or (user_color == "black" and game_result == "0-1")
    )
    if user_won:
        return (None, None)

    # 1. Scenario classification (drives Truth voice + which pool to pick from)
    game_reason = ""
    try:
        from services.game_reason_classifier import classify_game_reason
        reason_result = classify_game_reason(
            move_evaluations=move_evaluations,
            game_result=game_result,
            user_color=user_color,
            termination=termination,
            accuracy=accuracy,
        )
        game_reason = reason_result.get("category", "") or ""
    except Exception as e:
        logger.warning(f"[orchestrator] game_reason_classifier failed: {e}")

    # 2. Truth line (deterministic templates; voice-locked; no LLM)
    truth_line = generate_truth_line(
        decryption_v5_data=decryption_v5_data,
        game_reason=game_reason,
        game_id=game_id,
        user_won=False,
    )
    if not truth_line:
        # No critical move detected (the game had no clear blunder of the
        # user's). Skip both surfaces — no honest story to tell.
        return (None, None)

    # 3. Decryption block (LLM, validated, retried, fallback-template safe)
    decryption_block = None
    critical = pick_critical_move(decryption_v5_data)
    if not critical:
        return (truth_line, None)

    # Locate the full V5 move record to grab FENs.
    full_move = next(
        (
            m for m in decryption_v5_data
            if m.get("move_number") == critical.get("move_number")
            and m.get("move_san") == critical.get("move_san")
        ),
        None,
    )
    if not full_move or not full_move.get("fen_before"):
        return (truth_line, None)

    try:
        import chess
        board = chess.Board(full_move["fen_before"])
        move_obj = board.parse_san(critical["move_san"])
        move_uci = move_obj.uci()

        fen_after = full_move.get("fen_after")
        if not fen_after:
            board.push(move_obj)
            fen_after = board.fen()

        result = await generate_decryption(
            fen_before=full_move["fen_before"],
            fen_after=fen_after,
            move_uci=move_uci,
            user_color=user_color,
        )
        if result:
            decryption_block = {
                "text": result.text,
                "source": result.source,
                "attempts": result.attempts,
                "critical_move_number": critical.get("move_number"),
                "critical_move_san": critical.get("move_san"),
            }
    except Exception as e:
        logger.warning(f"[orchestrator] decryption generation failed: {e}")

    return (truth_line, decryption_block)
