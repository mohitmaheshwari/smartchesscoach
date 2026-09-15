"""One fail-closed decision boundary for the unified Play with Coach flow.

Chess truth and teaching prose come from ``caption_pipeline``.  This module
only decides whether that verified caption is important enough to interrupt,
important enough to show without blocking, or better left unsaid.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Mapping, Optional, Sequence

import chess

logger = logging.getLogger(__name__)

UNIFIED_DECISION_SOURCE = "pwc_unified_v1"
MAX_CRITICAL_PER_SESSION = 3
NONCRITICAL_WINDOW = 6
MAX_NONCRITICAL_PER_WINDOW = 2
UNIFIED_HELP_ACTIONS = frozenset({"explain_last_move", "focus_check"})


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
    mover_is_user: bool = True,
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
            mover_is_user=mover_is_user,
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


def _engine_evidence(
    eval_result: Mapping[str, Any],
    *,
    eval_valid: bool,
    move_quality: str,
) -> Dict[str, Any]:
    """Private persistence payload consumed and removed by the route.

    The background opponent turn needs the exact live evaluation for the
    session record and postgame analysis.  Keeping it beside the decision
    prevents a second Stockfish pass without asking the browser to echo
    trusted engine data back to us.
    """
    return {
        "eval_valid": bool(eval_valid),
        "move_quality": move_quality,
        "cp_loss": int(eval_result.get("cp_loss") or 0),
        "best_move": eval_result.get("best_move") or None,
        "eval_before": (
            float(eval_result.get("eval_before", 0)) if eval_valid else None
        ),
        "eval_after": (
            float(eval_result.get("eval_after", 0)) if eval_valid else None
        ),
    }


def engine_evidence_for_player(
    evidence: Mapping[str, Any], user_color: str
) -> Dict[str, Any]:
    """Convert Stockfish's White-view score into the player's perspective."""
    result = dict(evidence)
    if str(user_color).lower() != "black":
        return result
    for field in ("eval_before", "eval_after"):
        value = result.get(field)
        if value is not None:
            result[field] = -float(value)
    return result


def _degraded_advisory(
    board: chess.Board,
    move: chess.Move,
    session_doc: Mapping[str, Any],
    eval_result: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Speak from the board when the engine could not speak from search.

    `detect_signals_fast` is pure python-chess and documented to run in under
    5ms, so this costs nothing on the path where it matters. It only fires on
    the two signals legacy also trusts without an eval -- a piece left hanging,
    or a threat ignored. Anything less certain stays quiet, because the point
    is to stop losing the unmissable ones, not to guess.
    """
    try:
        from services.fast_eval_service import detect_signals_fast

        board_after = board.copy(stack=False)
        board_after.push(move)
        user_color = (chess.WHITE
                      if str(session_doc.get("user_color") or "white") == "white"
                      else chess.BLACK)
        signals = detect_signals_fast(
            board, board_after, user_color, dict(eval_result),
            session_doc.get("evaluations") or [],
        )
    except Exception as exc:
        logger.warning("[unified] degraded fallback failed: %s", exc)
        return None

    hung = signals.get("hung_piece")
    missed = signals.get("missed_threat")
    if hung:
        piece = str(hung.get("piece") or "piece")
        square = str(hung.get("square") or "")
        where = f" on {square}" if square else ""
        text = f"Stop. Your {piece}{where} can be taken."
        concept = "hung_pieces"
    elif missed:
        piece = str(missed.get("piece") or "piece")
        text = f"Check what your opponent is threatening — your {piece} is not safe."
        concept = "missed_threat"
    else:
        return None

    logger.info("[unified] engine unavailable; speaking from board heuristics: %s",
                concept)
    response = _silent_response("unknown")
    response["coachingDecision"] = {
        "source": UNIFIED_DECISION_SOURCE,
        # advisory, not critical: the client renders advisory on the
        # auto-commit path, and we are reasoning from geometry rather than a
        # completed search, so it should not carry the heaviest weight.
        "layer": "advisory",
        "category": "critical_tactic",
        "severity": "medium",
        "text": text,
        "conceptKey": concept,
        "gamePhase": None,
        "requiresHold": False,
        "showInTimeline": True,
        "showInActiveStrip": True,
        "degradedEval": True,
    }
    response["moveEvaluation"] = {
        "moveQuality": "unknown",
        "cpLoss": 0,
        "bestMove": None,
    }
    response["_engineEvidence"] = _engine_evidence(
        eval_result, eval_valid=False, move_quality="unknown",
    )
    return response


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

    # depth 0 means fast_eval ran out of its own 800ms budget before it
    # searched anything -- not that the position is quiet. It is a transient:
    # three consecutive calls on one position have returned depth [0, 10, 10].
    # On a contended box the engine takes 900-1400ms, so this fires often, and
    # every time it did the whole move went silent.
    #
    # One retry, because the failure is a race rather than a property of the
    # position. The engine is a warm singleton, so the retry is another search,
    # not another process.
    if not eval_valid:
        logger.info(
            "[unified] eval came back at depth 0; retrying once before "
            "deciding this move is not worth a word"
        )
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

    # Two different things used to share this exit. Keeping a clean move quiet
    # is deliberate -- it is quieter and it keeps the live path inside its
    # response budget. Going quiet because the ENGINE failed is not: it turns
    # "we could not look" into "there was nothing to see".
    #
    # The legacy path never did that. When its eval is invalid it falls back to
    # board heuristics (coach_play.py, the `not eval_is_valid and
    # fast_signals.get("hung_piece")` branch) and still speaks. Unified had no
    # such floor, which is why one real 27-move game produced 14 silent
    # decisions and zero messages while the same player's legacy games produce
    # 22 to 38.
    if not eval_valid:
        degraded = _degraded_advisory(board, move, session_doc, eval_result)
        if degraded is not None:
            return degraded

    if quality in {"excellent", "good"} or not eval_valid:
        response = _silent_response(quality)
        response["moveEvaluation"] = {
            "moveQuality": quality,
            "cpLoss": int(eval_result.get("cp_loss") or 0),
            "bestMove": eval_result.get("best_move") or None,
        }
        response["_engineEvidence"] = _engine_evidence(
            eval_result,
            eval_valid=eval_valid,
            move_quality=quality,
        )
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
    response = {
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
    response["_engineEvidence"] = _engine_evidence(
        eval_result,
        eval_valid=eval_valid,
        move_quality=decision.get("move_quality") or quality,
    )
    return response


def _help_abstention(
    coaching_context: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    primary = (coaching_context or {}).get("primary_focus") or {}
    instruction = str(primary.get("instruction_text") or "").strip()
    suffix = f" Use today’s check: {instruction}" if instruction else ""
    return {
        "action": "explain_last_move",
        "answer": (
            "I can’t explain that move confidently from this position, so I "
            f"won’t guess.{suffix}"
        ),
        "instruction": instruction or None,
        "source": UNIFIED_DECISION_SOURCE,
        "proof": {"caption_verified": False, "abstained": True},
        "visual": {"arrows": [], "highlightSquares": []},
    }


async def answer_unified_help(
    *,
    session_doc: Mapping[str, Any],
    action: str,
) -> Dict[str, Any]:
    """Answer one low-typing help action through verified existing sources."""
    if action not in UNIFIED_HELP_ACTIONS:
        raise ValueError("unknown coach help action")

    coaching_context = session_doc.get("coaching_context") or {}
    primary = coaching_context.get("primary_focus") or {}
    if action == "focus_check":
        instruction = str(primary.get("instruction_text") or "").strip()
        if instruction:
            answer = instruction
            source = "canonical_focus"
        else:
            answer = str(
                (coaching_context.get("evidence") or {}).get("message")
                or "I’m still learning what deserves to become your main focus."
            ).strip()
            source = "canonical_focus_evidence"
        return {
            "action": action,
            "answer": answer,
            "instruction": None,
            "source": source,
            "proof": {"caption_verified": False, "context_verified": True},
            "visual": {"arrows": [], "highlightSquares": []},
        }

    move_history = session_doc.get("move_history") or []
    indexed_last = next(
        (
            (index, item)
            for index, item in reversed(list(enumerate(move_history)))
            if item.get("by") == "coach"
            and item.get("fen_before")
            and (item.get("uci") or item.get("move"))
        ),
        None,
    )
    if not indexed_last:
        return _help_abstention(coaching_context)

    index, last_move = indexed_last
    fen_before = str(last_move.get("fen_before") or "")
    try:
        board = chess.Board(fen_before)
        raw_move = str(last_move.get("uci") or last_move.get("move") or "")
        try:
            move = chess.Move.from_uci(raw_move)
            if move not in board.legal_moves:
                raise ValueError
        except ValueError:
            move = board.parse_san(raw_move)
        uci = move.uci()
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
        return _help_abstention(coaching_context)

    from services.fast_eval_service import fast_eval

    loop = asyncio.get_running_loop()
    eval_result = await loop.run_in_executor(
        None, fast_eval, fen_before, uci, None
    )
    if not eval_result.get("depth"):
        return _help_abstention(coaching_context)

    caption = await loop.run_in_executor(
        None,
        lambda: build_verified_caption(
            fen_before=fen_before,
            uci=uci,
            eval_result=eval_result,
            user_color=str(session_doc.get("user_color") or "white"),
            user_rating=int(session_doc.get("user_rating") or 1200),
            move_history=move_history[:index],
            mover_is_user=False,
        ),
    )
    if not caption.get("verified") or not caption.get("has_teaching_content"):
        return _help_abstention(coaching_context)

    return {
        "action": action,
        "answer": caption.get("caption"),
        "instruction": caption.get("instruction") or None,
        "source": UNIFIED_DECISION_SOURCE,
        "proof": {
            "caption_verified": True,
            "rule_name": caption.get("rule_name"),
        },
        "visual": {
            "arrows": caption.get("arrows") or [],
            "highlightSquares": caption.get("highlight_squares") or [],
        },
    }


def build_unified_postgame_summary(
    *,
    session_doc: Mapping[str, Any],
) -> Dict[str, Any]:
    """Project one honest postgame story from stored canonical evidence."""
    coaching_context = session_doc.get("coaching_context") or {}
    next_action = coaching_context.get("next_action") or {}
    if session_doc.get("game_mode") == "play":
        return {
            "focus_label": None,
            "story": "The game is complete. Your review is ready.",
            "detail": (
                "I stayed out of the game. Now we can look at the moments "
                "that mattered."
            ),
            "turning_point": None,
            "next_action": {
                "label": "Review the game",
                "href": "/lab",
            },
            "evidence": {
                "verified_moments": 0,
                "focus_moments": 0,
                "warnings_overridden": 0,
            },
        }

    primary = coaching_context.get("primary_focus") or {}
    focus_label = str(primary.get("label") or "").strip() or None
    focus_topic = str(primary.get("topic_key") or "").strip() or None
    decisions = [
        item
        for item in (session_doc.get("coaching_decisions") or [])
        if item.get("source") == UNIFIED_DECISION_SOURCE
        and item.get("layer") in {"advisory", "critical_interrupt"}
        and item.get("caption_verified")
        and str(item.get("text") or "").strip()
    ]
    decisions.sort(
        key=lambda item: (
            int(item.get("cp_loss") or 0),
            int(item.get("move_index") or 0),
        ),
        reverse=True,
    )
    turning = decisions[0] if decisions else None
    focus_moments = sum(
        bool(focus_topic and item.get("category") == focus_topic)
        for item in decisions
    )

    if focus_label and focus_moments:
        noun = "moment" if focus_moments == 1 else "moments"
        story = (
            f"We found {focus_moments} clear {noun} where today's focus "
            "mattered."
        )
    elif focus_label:
        story = (
            "I did not see a clear moment to measure this focus in this "
            "game, so I am not claiming you have fixed it yet."
        )
    elif decisions:
        story = "One clear moment from this game is worth carrying forward."
    else:
        story = (
            "I do not have a lesson from this game that I can stand behind, "
            "so I am not inventing one."
        )

    instruction = str(primary.get("instruction_text") or "").strip()
    detail = str((turning or {}).get("text") or "").strip() or instruction or None
    return {
        "focus_label": focus_label,
        "story": story,
        "detail": detail,
        "turning_point": (
            {
                "move_index": turning.get("move_index"),
                "text": turning.get("text"),
                "category": turning.get("category"),
                "cp_loss": turning.get("cp_loss"),
            }
            if turning else None
        ),
        "next_action": {
            "label": str(next_action.get("label") or "Review the game"),
            "href": str(next_action.get("href") or "/lab"),
        },
        "evidence": {
            "verified_moments": len(decisions),
            "focus_moments": focus_moments,
            "warnings_overridden": len(session_doc.get("guardian_overrides") or []),
        },
    }


def attach_unified_postgame_to_end_result(
    *,
    result: Dict[str, Any],
    session_doc: Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach the unified summary to the legacy-compatible end response.

    The resign endpoint returns its postgame payload under ``summary`` while
    the dedicated postgame endpoint returns it at the top level. Keep that
    established API shape, but make both paths use the same deterministic
    summary builder so the player's focus survives every way a game can end.
    """
    if session_doc.get("experience_version") != "unified_v1":
        return result

    summary = result.get("summary")
    if not isinstance(summary, dict):
        summary = {}
        result["summary"] = summary
    summary["unified_summary"] = build_unified_postgame_summary(
        session_doc=session_doc,
    )
    return result


__all__ = [
    "MAX_CRITICAL_PER_SESSION",
    "MAX_NONCRITICAL_PER_WINDOW",
    "NONCRITICAL_WINDOW",
    "UNIFIED_DECISION_SOURCE",
    "UNIFIED_HELP_ACTIONS",
    "answer_unified_help",
    "attach_unified_postgame_to_end_result",
    "build_unified_postgame_summary",
    "engine_evidence_for_player",
    "build_verified_caption",
    "evaluate_unified_pending",
    "select_unified_decision",
]
