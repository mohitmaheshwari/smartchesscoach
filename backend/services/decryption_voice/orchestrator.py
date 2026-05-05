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
) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict]]:
    """Build (truth_line, player_decryption, decryption_block, pattern_evidence)
    for a finished game."""

    # Skip wins — these surfaces are for losses and draws.
    user_won = (
        (user_color == "white" and game_result == "1-0")
        or (user_color == "black" and game_result == "0-1")
    )
    if user_won:
        return (None, None, None, None)

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
        return (None, None, None, None)

    # 3. Player Decryption — Story / Pattern / Carry-forward.
    # Deterministic templates (Pattern voice locked — LLM cannot match
    # the inner-voice register).
    player_decryption = build_player_decryption(
        decryption_v5_data=decryption_v5_data,
        game_reason=game_reason,
        game_id=game_id,
    )

    # 4. Pattern Evidence — board geometry for the visual evidence
    # surface. Independent of the LLM (uses python-chess), so it
    # ships even if the LLM call fails.
    pattern_evidence = None
    critical = pick_critical_move(decryption_v5_data)
    if critical:
        try:
            from services.pattern_evidence import extract_pattern_evidence
            # Find the critical_gap from the V5 move record.
            target_move_n = critical.get("move_number")
            crit_gap = None
            for m in decryption_v5_data:
                if (m.get("is_user_move")
                        and m.get("move_number") == target_move_n):
                    crit_gap = m.get("cognitive_gap")
                    break
            pattern_evidence = extract_pattern_evidence(
                decryption_v5_data=decryption_v5_data,
                user_color=user_color,
                critical_move_number=target_move_n,
                critical_gap=crit_gap,
            )
        except Exception as e:
            logger.warning(f"[orchestrator] pattern_evidence failed: {e}")

    # 5. Plan Decryption — LLM prose, validated, retried, fallback-safe.
    decryption_block = None
    if not critical:
        return (truth_line, player_decryption, None, pattern_evidence)

    full_move = next(
        (
            m for m in decryption_v5_data
            if m.get("move_number") == critical.get("move_number")
            and m.get("move_san") == critical.get("move_san")
        ),
        None,
    )
    if not full_move or not full_move.get("fen_before"):
        return (truth_line, player_decryption, None, pattern_evidence)

    try:
        import chess
        board = chess.Board(full_move["fen_before"])
        move_obj = board.parse_san(critical["move_san"])
        move_uci = move_obj.uci()

        fen_after = full_move.get("fen_after")
        if not fen_after:
            board.push(move_obj)
            fen_after = board.fen()

        # Build the richer moment context so the LLM can name the
        # opponent's plan, the user's missed move, and the saving line.
        moment_ctx = None
        try:
            from .moment_context import build_moment_context
            moment_ctx = build_moment_context(
                decryption_v5_data=decryption_v5_data,
                move_evaluations=move_evaluations,
                critical_move_number=critical.get("move_number"),
                user_color=user_color,
            )
        except Exception as ctx_err:
            logger.warning(f"[orchestrator] moment_context failed: {ctx_err}")

        result = await generate_decryption(
            fen_before=full_move["fen_before"],
            fen_after=fen_after,
            move_uci=move_uci,
            user_color=user_color,
            moment_context=moment_ctx,
        )
        if result:
            decryption_block = {
                "text": result.text,
                "source": result.source,
                "attempts": result.attempts,
                "critical_move_number": critical.get("move_number"),
                "critical_move_san": critical.get("move_san"),
                # Board context for the frontend "Show me why" view —
                # without these the prose has nothing to point at.
                "fen_before": full_move["fen_before"],
                "fen_after": fen_after,
                "move_uci": move_uci,
            }
    except Exception as e:
        logger.warning(f"[orchestrator] decryption generation failed: {e}")

    return (truth_line, player_decryption, decryption_block, pattern_evidence)
