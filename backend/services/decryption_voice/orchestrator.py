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

    # Wins skip the loss-specific surfaces (truth_line / player_decryption /
    # pattern_evidence / singleton decryption_block) — those are framed as
    # "why did you lose". But MOMENTS (turning points) are valuable on
    # won games too — wins still contain mistakes worth reviewing. So
    # we don't early-return on wins anymore; instead each section
    # below checks `user_won` and skips itself when appropriate.
    user_won = (
        (user_color == "white" and game_result == "1-0")
        or (user_color == "black" and game_result == "0-1")
    )

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

    # 2. Truth line — loss-framed; skip on wins.
    truth_line = None
    if not user_won:
        truth_line = generate_truth_line(
            decryption_v5_data=decryption_v5_data,
            game_reason=game_reason,
            game_id=game_id,
            user_won=False,
            user_color=user_color,
        )

    # 3. Player Decryption — Story / Pattern / Carry-forward.
    # Loss-framed; skip on wins.
    player_decryption = None
    if not user_won:
        player_decryption = build_player_decryption(
            decryption_v5_data=decryption_v5_data,
            game_reason=game_reason,
            game_id=game_id,
            user_color=user_color,
        )

    # 4. Pattern Evidence — board geometry. Loss-only surface.
    pattern_evidence = None
    critical = pick_critical_move(decryption_v5_data, user_color=user_color)
    if not user_won and critical:
        try:
            from services.pattern_evidence import extract_pattern_evidence
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

    # 5. Plan Decryption (singleton critical move) — loss-only.
    decryption_block = None
    if user_won or not critical:
        # On wins, skip the singleton block but still produce moments
        # below. On losses with no critical move, nothing to teach.
        pass

    full_move = None
    if not user_won and critical:
        full_move = next(
            (
                m for m in decryption_v5_data
                if m.get("move_number") == critical.get("move_number")
                and m.get("move_san") == critical.get("move_san")
            ),
            None,
        )
        if full_move and full_move.get("fen_before"):
            try:
                import chess
                board = chess.Board(full_move["fen_before"])
                move_obj = board.parse_san(critical["move_san"])
                move_uci = move_obj.uci()

                fen_after = full_move.get("fen_after")
                if not fen_after:
                    board.push(move_obj)
                    fen_after = board.fen()

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
                best_san_for_dispatch = (moment_v5 or {}).get("best_move_san") or ""
                pv_for_dispatch = (moment_v5 or {}).get("pv_after_best") or []
                pv_played_for_dispatch = (moment_v5 or {}).get("pv_after_played") or []

                # Priority order:
                #   1. concept_dispatcher (richest — tactical templates
                #      like missed_pin / missed_capture / walked_into_attack
                #      with specific board geometry).
                #   2. V5 caption (Mohit 2026-05-20 — JSON-driven content
                #      shared with Lab/PWC. Replaces what used to be the
                #      generic "engine prefers X here." fallback).
                #   3. engine_fallback (last resort — needs human review).
                try:
                    from .concept_dispatcher import caption_for_moment, extract_mate_against_user
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
                from .decryption import DecryptionResult

                if concept_text:
                    pattern_label = (concept_meta or {}).get("pattern_type") or "concept"
                    m_result = DecryptionResult(
                        text=concept_text,
                        source=f"template:{pattern_label}",
                        attempts=0,
                        delta_present=True,
                        failed_attempts=None,
                    )
                else:
                    # Concept silent — try V5 caption from the JSON
                    # pipeline. This is the same caption Lab + PWC show
                    # for the same move; single source of truth.
                    v5_caption_text = (moment_v5 or {}).get("caption") or ""
                    v5_rule_name = (moment_v5 or {}).get("rule_name") or ""
                    if v5_caption_text:
                        m_result = DecryptionResult(
                            text=v5_caption_text,
                            source=f"v5:{v5_rule_name}" if v5_rule_name else "v5",
                            attempts=0,
                            delta_present=True,
                            failed_attempts=None,
                        )
                    else:
                        # Last resort: deterministic engine-fact line.
                        # Confidence score marks needs_review.
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
