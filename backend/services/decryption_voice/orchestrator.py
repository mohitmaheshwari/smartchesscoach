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

from .truth_line import generate_truth_line, pick_critical_move, detect_top_moments
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
        user_color=user_color,
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
        user_color=user_color,
    )

    # 4. Pattern Evidence — board geometry for the visual evidence
    # surface. Independent of the LLM (uses python-chess), so it
    # ships even if the LLM call fails.
    pattern_evidence = None
    critical = pick_critical_move(decryption_v5_data, user_color=user_color)
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

        # Best move + both PVs for the dispatcher / engine fallback.
        # pv_after_best powers combination-chain (user's tactical line);
        # pv_after_played powers walked_into_attack (opp's tactical
        # line after the user's wrong move — Greek Gift, etc.).
        best_san_for_critical = (full_move or {}).get("best_move_san")
        pv_for_critical = (full_move or {}).get("pv_after_best") or []
        pv_played_for_critical = (full_move or {}).get("pv_after_played") or []

        result = await generate_decryption(
            fen_before=full_move["fen_before"],
            fen_after=fen_after,
            move_uci=move_uci,
            user_color=user_color,
            best_move_san=best_san_for_critical,
            pv_after_best=pv_for_critical,
            pv_after_played=pv_played_for_critical,
        )
        if result:
            decryption_block = {
                "text": result.text,
                "source": result.source,
                "attempts": result.attempts,
                "critical_move_number": critical.get("move_number"),
                "critical_move_san": critical.get("move_san"),
                # Board context for the frontend "Show me why" view.
                "fen_before": full_move["fen_before"],
                "fen_after": fen_after,
                "move_uci": move_uci,
                "failed_attempts": result.failed_attempts,
            }
    except Exception as e:
        logger.warning(f"[orchestrator] decryption generation failed: {e}")

    # 6. Multi-pivot moments — real coaching shows multiple turning
    # points, not just the one with biggest cp_loss. Generate decryption
    # for up to 4 key moments per game.
    moments_list = []
    try:
        top_moments = detect_top_moments(
            decryption_v5_data,
            max_moments=4,
            min_separation=3,
            user_color=user_color,
        )
        for moment_struct in top_moments:
            mn = moment_struct.get("move_number")
            ms = moment_struct.get("move_san")
            full_m = next(
                (m for m in decryption_v5_data
                 if m.get("is_user_move") and m.get("move_number") == mn and m.get("move_san") == ms),
                None,
            )
            if not full_m or not full_m.get("fen_before"):
                continue
            try:
                import chess as _chess
                _board = _chess.Board(full_m["fen_before"])
                _move_obj = _board.parse_san(ms)
                _uci = _move_obj.uci()
                _fen_after = full_m.get("fen_after")
                if not _fen_after:
                    _board.push(_move_obj)
                    _fen_after = _board.fen()

                # ── Concept dispatcher FIRST (deterministic, zero
                # hallucination). If no template fires we fall back to
                # the engine-fact line — there is NO LLM path anymore.
                # Look up the V5 record once — used by dispatcher AND
                # by per-commentary confidence scoring below.
                moment_v5 = next(
                    (mm for mm in decryption_v5_data
                     if mm.get("is_user_move")
                     and mm.get("move_number") == mn
                     and mm.get("move_san") == ms),
                    None,
                )
                concept_text = None
                concept_meta = None
                try:
                    from .concept_dispatcher import caption_for_moment, extract_mate_against_user
                    best_san_for_dispatch = (moment_v5 or {}).get("best_move_san") or ""
                    pv_for_dispatch = (moment_v5 or {}).get("pv_after_best") or []
                    pv_played_for_dispatch = (moment_v5 or {}).get("pv_after_played") or []
                    # Stockfish-truth mate detection — positive int means
                    # forced mate against the user from this move.
                    engine_mate = extract_mate_against_user(
                        move_evaluations, mn, ms, user_color,
                    )
                    concept_text, concept_meta = caption_for_moment(
                        fen_before=full_m["fen_before"],
                        user_move_san=ms,
                        best_move_san=best_san_for_dispatch,
                        engine_mate_in_after=engine_mate,
                        pv_after_best=pv_for_dispatch,
                        pv_after_played=pv_played_for_dispatch,
                        user_color=user_color,
                    )
                except Exception as cd_err:
                    logger.warning(f"[orchestrator] concept_dispatcher failed for move {mn}: {cd_err}")

                m_result = None
                if concept_text:
                    # Templated, deterministic. Build a fake DecryptionResult-shape.
                    from .decryption import DecryptionResult
                    pattern_label = (concept_meta or {}).get("pattern_type") or "concept"
                    m_result = DecryptionResult(
                        text=concept_text,
                        source=f"template:{pattern_label}",
                        attempts=0,
                        delta_present=True,
                        failed_attempts=None,
                    )
                else:
                    # No template fired — fall back to the deterministic
                    # engine-fact line ("The engine prefers X here.").
                    # ZERO LLM. Confidence score will mark this moment
                    # needs_review so the coach overrides via the queue.
                    m_result = await generate_decryption(
                        fen_before=full_m["fen_before"],
                        fen_after=_fen_after,
                        move_uci=_uci,
                        user_color=user_color,
                        best_move_san=best_san_for_dispatch,
                        pv_after_best=pv_for_dispatch,
                        pv_after_played=pv_played_for_dispatch,
                    )
                if m_result:
                    # Build the 3 interactive candidates for this moment.
                    # Empty list = fall through to static prose card.
                    try:
                        from .candidate_builder import build_candidates
                        m_candidates = build_candidates(
                            fen_before=full_m["fen_before"],
                            move_uci=_uci,
                            move_san=ms,
                            move_number=mn,
                            decryption_v5_data=decryption_v5_data,
                            engine_caption=m_result.text,
                            move_evaluations=move_evaluations,
                            user_color=user_color,
                        )
                    except Exception as cb_err:
                        logger.warning(f"[orchestrator] candidate_builder failed for move {mn}: {cb_err}")
                        m_candidates = []

                    # Per-commentary confidence score. Below 0.8 the
                    # caption is flagged for human review.
                    try:
                        from .confidence_score import compute_moment_confidence
                        pt = None
                        if m_result.source.startswith("template:"):
                            pt = m_result.source.split(":", 1)[1]
                        score = compute_moment_confidence(
                            source=m_result.source,
                            pattern_type=pt,
                            detector_details=(concept_meta or {}).get("details") if concept_text else None,
                            detector_confidence=(concept_meta or {}).get("confidence") if concept_text else None,
                            attempts=m_result.attempts or 0,
                            failed_attempts=m_result.failed_attempts,
                            cp_loss=moment_struct.get("cp_loss"),
                            best_move_san=(moment_v5 or {}).get("best_move_san"),
                            text=m_result.text or "",
                        )
                    except Exception as conf_err:
                        logger.warning(f"[orchestrator] confidence_score failed for move {mn}: {conf_err}")
                        score = {"confidence": 0.5, "needs_review": True, "breakdown": {}}

                    moments_list.append({
                        "move_number": mn,
                        "move_san": ms,
                        "cp_loss": moment_struct.get("cp_loss"),
                        "severity": moment_struct.get("severity"),
                        "is_pivot": moment_struct.get("is_pivot", False),
                        "pivot_tier": moment_struct.get("pivot_tier"),
                        "fen_before": full_m["fen_before"],
                        "fen_after": _fen_after,
                        "move_uci": _uci,
                        "text": m_result.text,
                        "source": m_result.source,
                        "attempts": m_result.attempts,
                        "failed_attempts": m_result.failed_attempts,
                        "candidates": m_candidates,
                        "confidence": score.get("confidence"),
                        "needs_review": score.get("needs_review"),
                        "confidence_breakdown": score.get("breakdown"),
                    })
            except Exception as ex:
                logger.warning(f"[orchestrator] moment {mn} failed: {ex}")
    except Exception as e:
        logger.warning(f"[orchestrator] multi-pivot moments failed: {e}")

    # Stash the moments list on decryption_block so the frontend can
    # access them without a separate API field. Keep singleton fields
    # for backward compat.
    if decryption_block is not None:
        decryption_block["moments"] = moments_list
    elif moments_list:
        # No singleton block but we have moments — surface them anyway.
        decryption_block = {"moments": moments_list}

    return (truth_line, player_decryption, decryption_block, pattern_evidence)
