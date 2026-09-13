"""One fail-closed decision boundary for the unified Play with Coach flow.

Chess truth and teaching prose come from ``caption_pipeline``.  This module
only decides whether that verified caption is important enough to interrupt,
important enough to show without blocking, or better left unsaid.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Mapping, Sequence

import chess


UNIFIED_DECISION_SOURCE = "pwc_unified_v1"
MAX_CRITICAL_PER_SESSION = 3
NONCRITICAL_WINDOW = 6
MAX_NONCRITICAL_PER_WINDOW = 2


def _history_san(move_history: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(item.get("move") or "").strip()
        for item in move_history
        if str(item.get("move") or "").strip()
    ]


def build_verified_caption(
    *,
    fen_before: str,
    uci: str,
    eval_result: Mapping[str, Any],
    user_color: str,
    user_rating: int,
    move_history: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Adapt fast-eval evidence to the canonical caption pipeline.

    Fresh engine verification is disabled here: a live intervention must be
    supported by the evidence already obtained for this exact pending move.
    If the shared verifier cannot prove the resulting sentence, it returns an
    empty caption and the coach remains silent.
    """
    from services.caption_pipeline import (
        CrossMoveState,
        MoveInputs,
        build_move_teaching_decision,
    )

    board = chess.Board(fen_before)
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        return {"verified": False, "caption": ""}

    played_san = board.san(move)
    mover_is_white = board.turn == chess.WHITE
    history_san = _history_san(move_history)
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=fen_before,
            played_san=played_san,
            mover_is_user=True,
            mover_is_white=mover_is_white,
            user_color=user_color,
            full_move_number=board.fullmove_number,
            move_history_san=history_san,
            prev_move_san=history_san[-1] if history_san else None,
            best_move_san=eval_result.get("best_move") or None,
            eval_before_cp=round(float(eval_result.get("eval_before", 0)) * 100),
            eval_after_cp=round(float(eval_result.get("eval_after", 0)) * 100),
            cp_loss=abs(int(eval_result.get("cp_loss") or 0)),
            user_rating=int(user_rating or 1200),
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )
    verified = bool(
        not decision.should_skip
        and decision.explanation.final_verified
        and decision.text.caption.strip()
    )
    primary_reason = decision.debug_facts.get("primary_reason") or {}
    return {
        "verified": verified,
        "caption": decision.text.caption.strip() if verified else "",
        "instruction": (
            decision.explanation.transferable_instruction.strip()
            if verified else ""
        ),
        "category": primary_reason.get("category"),
        "concept_key": (
            decision.teaching_meta.shape_pattern_id
            or decision.teaching_meta.principle_id_used
            or decision.text.rule_name
        ),
        "caption_tier": decision.teaching_meta.caption_tier,
        "has_teaching_content": bool(decision.teaching_meta.has_teaching_content),
        "rule_name": decision.text.rule_name,
        "arrows": decision.visual.arrows,
        "highlight_squares": decision.visual.highlight_squares,
    }


def _visible_unified(decision: Mapping[str, Any]) -> bool:
    return (
        decision.get("source") == UNIFIED_DECISION_SOURCE
        and decision.get("layer") in {"advisory", "critical_interrupt"}
    )


def _unified_history(
    decisions: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return [
        decision
        for decision in decisions
        if decision.get("source") == UNIFIED_DECISION_SOURCE
    ]


def select_unified_decision(
    *,
    game_mode: str,
    eval_result: Mapping[str, Any],
    eval_valid: bool,
    caption: Mapping[str, Any],
    coaching_decisions: Sequence[Mapping[str, Any]],
    user_color: str,
    user_rating: int,
    coaching_context: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Choose at most one visible action for one pending move."""
    silent = {
        "source": UNIFIED_DECISION_SOURCE,
        "layer": "silent",
        "text": None,
        "requires_hold": False,
        "category": None,
        "concept_key": None,
        "focus_match": False,
    }
    if game_mode != "coach" or not eval_valid or not caption.get("verified"):
        return silent

    from services.realtime_coaching_feedback import _classify_move_quality

    quality = _classify_move_quality(
        float(eval_result.get("eval_before", 0)),
        float(eval_result.get("eval_after", 0)),
        user_color,
        int(user_rating or 1200),
    )
    unified_history = _unified_history(coaching_decisions)
    previous = [item for item in unified_history if _visible_unified(item)]
    critical_count = sum(
        item.get("layer") == "critical_interrupt" for item in previous
    )
    recent_noncritical = sum(
        item.get("layer") == "advisory"
        for item in unified_history[-NONCRITICAL_WINDOW:]
    )

    teachable = bool(caption.get("has_teaching_content"))
    if (
        quality == "blunder"
        and teachable
        and critical_count < MAX_CRITICAL_PER_SESSION
    ):
        layer = "critical_interrupt"
    elif (
        quality in {"inaccuracy", "mistake", "blunder"}
        and teachable
        and recent_noncritical < MAX_NONCRITICAL_PER_WINDOW
    ):
        layer = "advisory"
    else:
        return {**silent, "move_quality": quality}

    primary = (coaching_context or {}).get("primary_focus") or {}
    category = caption.get("category")
    return {
        "source": UNIFIED_DECISION_SOURCE,
        "layer": layer,
        "text": caption.get("caption"),
        "instruction": caption.get("instruction") or None,
        "requires_hold": layer == "critical_interrupt",
        "category": category,
        "concept_key": caption.get("concept_key"),
        "focus_match": bool(category and category == primary.get("topic_key")),
        "move_quality": quality,
        "arrows": caption.get("arrows") or [],
        "highlight_squares": caption.get("highlight_squares") or [],
        "proof": {
            "caption_verified": True,
            "rule_name": caption.get("rule_name"),
        },
    }


def _silent_response(move_quality: str = "good") -> Dict[str, Any]:
    return {
        "shouldAutoCommit": True,
        "coachingDecision": {
            "source": UNIFIED_DECISION_SOURCE,
            "layer": "silent",
            "gamePhase": None,
            "requiresHold": False,
        },
        "coachingMoment": None,
        "moveEvaluation": {
            "moveQuality": move_quality,
            "cpLoss": 0,
            "bestMove": None,
        },
        "checklist": {},
        "weaknesses": [],
        "playerProfile": None,
        "rootProblem": None,
        "commentary": None,
        "openingGuidance": None,
        "trapWarning": None,
    }


async def evaluate_unified_pending(
    *,
    session_doc: Mapping[str, Any],
    fen_before: str,
    uci: str,
    user_rating: int,
) -> Dict[str, Any]:
    """Evaluate one unified pending move through one chess/prose pipeline."""
    if session_doc.get("game_mode") != "coach":
        return _silent_response()
    if fen_before != session_doc.get("current_fen"):
        return _silent_response()

    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return _silent_response()
    except (ValueError, chess.InvalidMoveError):
        return _silent_response()

    from services.fast_eval_service import fast_eval
    from services.realtime_coaching_feedback import _classify_move_quality

    cached_eval = None
    evaluations = session_doc.get("evaluations") or []
    if evaluations:
        cached_eval = evaluations[-1].get("eval_after")
        if cached_eval is None:
            cached_eval = evaluations[-1].get("score")
    loop = asyncio.get_running_loop()
    eval_result = await loop.run_in_executor(
        None, fast_eval, fen_before, uci, cached_eval
    )
    eval_valid = bool(eval_result.get("depth", 0) > 0)
    quality = _classify_move_quality(
        float(eval_result.get("eval_before", 0)),
        float(eval_result.get("eval_after", 0)),
        str(session_doc.get("user_color") or "white"),
        int(user_rating or session_doc.get("user_rating") or 1200),
    ) if eval_valid else "unknown"

    # Clean moves need no caption construction. This is both quieter and keeps
    # the live path inside its response budget.
    if quality in {"excellent", "good"} or not eval_valid:
        response = _silent_response(quality)
        response["moveEvaluation"] = {
            "moveQuality": quality,
            "cpLoss": int(eval_result.get("cp_loss") or 0),
            "bestMove": eval_result.get("best_move") or None,
        }
        return response

    caption = await loop.run_in_executor(
        None,
        lambda: build_verified_caption(
            fen_before=fen_before,
            uci=uci,
            eval_result=eval_result,
            user_color=str(session_doc.get("user_color") or "white"),
            user_rating=int(user_rating or session_doc.get("user_rating") or 1200),
            move_history=session_doc.get("move_history") or [],
        ),
    )
    decision = select_unified_decision(
        game_mode=str(session_doc.get("game_mode") or "coach"),
        eval_result=eval_result,
        eval_valid=eval_valid,
        caption=caption,
        coaching_decisions=session_doc.get("coaching_decisions") or [],
        user_color=str(session_doc.get("user_color") or "white"),
        user_rating=int(user_rating or session_doc.get("user_rating") or 1200),
        coaching_context=session_doc.get("coaching_context"),
    )
    layer = decision.get("layer") or "silent"
    requires_hold = bool(decision.get("requires_hold"))
    public_decision = {
        "source": UNIFIED_DECISION_SOURCE,
        "layer": layer,
        "category": decision.get("category"),
        "severity": "high" if requires_hold else "medium",
        "text": decision.get("text"),
        "instruction": decision.get("instruction"),
        "question": None,
        "conceptKey": decision.get("concept_key"),
        "focusMatch": bool(decision.get("focus_match")),
        "requiresHold": requires_hold,
        "minHoldMs": 0,
        "showInTimeline": layer != "silent",
        "showInActiveStrip": layer == "advisory",
        "proof": decision.get("proof"),
    }
    return {
        "shouldAutoCommit": not requires_hold,
        "coachingDecision": public_decision,
        "coachingMoment": public_decision if requires_hold else None,
        "moveEvaluation": {
            "moveQuality": decision.get("move_quality") or quality,
            "cpLoss": int(eval_result.get("cp_loss") or 0),
            "bestMove": eval_result.get("best_move") or None,
        },
        "checklist": {},
        "weaknesses": [],
        "playerProfile": None,
        "rootProblem": None,
        "commentary": None,
        "openingGuidance": None,
        "trapWarning": None,
        "coachingContext": session_doc.get("coaching_context"),
        "visual": {
            "arrows": decision.get("arrows") or [],
            "highlightSquares": decision.get("highlight_squares") or [],
        },
    }


__all__ = [
    "MAX_CRITICAL_PER_SESSION",
    "MAX_NONCRITICAL_PER_WINDOW",
    "NONCRITICAL_WINDOW",
    "UNIFIED_DECISION_SOURCE",
    "build_verified_caption",
    "evaluate_unified_pending",
    "select_unified_decision",
]
