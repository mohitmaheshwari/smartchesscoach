"""
Orchestrator — generate the full post-game voice payload.

Called once after V5 decryption data is computed. Reads V5 + game
metadata, classifies the scenario, picks the critical move, and
produces:

    truth_line         — Coach Voice 3-liner (identity / anchor / trigger)
    player_decryption  — "What kind of player showed up?" (story + pattern + carry_forward)
    decryption_block   — "What was happening on the board?" (LLM prose, the Plan Decryption)

Truth and Player are deterministic templates (Pattern especially must
sound like the player's inner voice, which the LLM gets wrong). Plan
Decryption is LLM-driven with code-level voice validation.

Returns (truth_line, player_decryption, decryption_block). Any may be
None when the user won, no decisive move exists, or generation failed.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .truth_line import generate_truth_line, pick_critical_move
from .player_decryption import build_player_decryption
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
) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict]]:
    """Build (truth_line, player_decryption, decryption_block) for a finished game."""

    # Skip wins — these surfaces are for losses and draws.
    user_won = (
        (user_color == "white" and game_result == "1-0")
        or (user_color == "black" and game_result == "0-1")
    )
    if user_won:
        return (None, None, None)

    # 1. Scenario classification — drives Truth + Player templates
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

    # 2. Truth line — deterministic templates; voice-locked; no LLM
    truth_line = generate_truth_line(
        decryption_v5_data=decryption_v5_data,
        game_reason=game_reason,
        game_id=game_id,
        user_won=False,
    )
    if not truth_line:
        # No critical move detected — no honest story to tell.
        return (None, None, None)

    # 3. Player Decryption — Story / Pattern / Carry-forward.
    # Deterministic templates (Pattern voice locked — LLM cannot match
    # the inner-voice register).
    player_decryption = build_player_decryption(
        decryption_v5_data=decryption_v5_data,
        game_reason=game_reason,
        game_id=game_id,
    )

    # 4. Plan Decryption — LLM prose, validated, retried, fallback-safe.
    decryption_block = None
    critical = pick_critical_move(decryption_v5_data)
    if not critical:
        return (truth_line, player_decryption, None)

    full_move = next(
        (
            m for m in decryption_v5_data
            if m.get("move_number") == critical.get("move_number")
            and m.get("move_san") == critical.get("move_san")
        ),
        None,
    )
    if not full_move or not full_move.get("fen_before"):
        return (truth_line, player_decryption, None)

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

    return (truth_line, player_decryption, decryption_block)
