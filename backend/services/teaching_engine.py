"""
Teaching Engine — Generic lesson dispatcher for Play with Coach
================================================================

Supports multiple lesson types:
  - "opening" → Opening curriculum moves (existing flow via opening_teaching_integration)
  - "trap"    → Walk through a trap sequence step-by-step (trick_library_service)
  - "endgame" → Solve endgame positions from theory tree

Each lesson type implements:
  - start(db, session_id, user_id, params) → lesson data
  - process_move(db, session_id, move) → feedback + next instruction
  - exit(db, session_id, choice) → restored state or cleanup
"""

import logging
import asyncio
import json
import os
import uuid
import chess
from typing import Any, Dict, Mapping, Optional
from datetime import datetime, timezone

from services.personal_curriculum import PIC_LESSON_ID, PIC_SKILL_ID

logger = logging.getLogger(__name__)

ENDGAME_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "coaching", "endgame_theory_tree.json"
)

_ENDGAME_TREE = None

PIC_LESSON_TYPE = "pic_piece_safety"
PIC_CONTENT_VERSION = 1
PERSONALIZED_LESSON_TYPE = "personalized_curriculum"
PERSONALIZED_SESSION_SCHEMA_VERSION = "personalized_learning_session.v1"

def _load_endgame_tree() -> Dict:
    global _ENDGAME_TREE
    if _ENDGAME_TREE is None:
        try:
            with open(ENDGAME_TREE_PATH, "r") as f:
                _ENDGAME_TREE = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load endgame tree: {e}")
            _ENDGAME_TREE = {}
    return _ENDGAME_TREE


# ─────────────────────────────────────────────
# TRAP LESSONS
# ─────────────────────────────────────────────

async def start_trap_lesson(db, session_id: str, user_id: str, params: Dict) -> Dict:
    """Start a verified trap or opening-plan line inside a coach session."""
    from trick_library_service import (
        get_opening_idea_for_practice,
        get_trap_for_practice,
    )

    lesson_type = str(params.get("lesson_type") or "trap")
    is_opening_plan = lesson_type == "opening_plan"
    trap_key = params.get("lesson_key") if is_opening_plan else params.get("trap_key")
    if not trap_key:
        return {
            "error": "lesson_key is required" if is_opening_plan else "trap_key is required"
        }

    requested_mode = params.get("mode") or (
        "execution" if is_opening_plan else "avoidance"
    )
    trap = (
        get_opening_idea_for_practice(trap_key, requested_mode)
        if is_opening_plan
        else get_trap_for_practice(trap_key, requested_mode)
    )
    if not trap:
        return {
            "error": (
                f"Opening idea '{trap_key}' is not verified for practice"
                if is_opening_plan
                else f"Trap '{trap_key}' not found or has no verified {requested_mode} lesson"
            )
        }

    # Build the lesson move sequence the user needs to play
    user_moves = trap.get("user_moves", [])
    engine_moves = trap.get("engine_moves", [])
    full_sequence = trap.get("full_sequence", [])

    if not full_sequence:
        return {"error": "Trap has no move sequence"}

    # First instruction: first move of the sequence
    first_move_idx = 0
    first_move = full_sequence[first_move_idx]
    is_user_move = any(um["index"] == first_move_idx for um in user_moves)

    # Store teaching state in session
    teaching_state = {
        "teaching_mode": True,
        "lesson_type": lesson_type,
        "lesson_key": trap_key,
        "lesson_name": trap["name"],
        "trap_data": {
            "full_sequence": full_sequence,
            "user_moves": user_moves,
            "engine_moves": engine_moves,
            "user_color": trap.get("user_color", "white"),
            "explanation": trap.get("explanation", ""),
            "why_it_works": trap.get("why_it_works", ""),
            "hints": trap.get("hints", ""),
            "practice_mode": trap.get("mode", "execution"),
        },
        "current_move_index": 0,
        "pre_teaching_fen": None,  # Will be set from session
    }

    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if session_doc:
        teaching_state["pre_teaching_fen"] = session_doc.get("current_fen")

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": teaching_state}
    )

    # Auto-play engine moves at the start if engine goes first
    teaching_fen = trap.get("start_fen", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    auto_played = []

    board = chess.Board(teaching_fen)
    move_idx = 0
    while move_idx < len(full_sequence):
        is_engine = any(em["index"] == move_idx for em in engine_moves)
        if is_engine:
            move_san = full_sequence[move_idx]
            try:
                board.push_san(move_san)
                auto_played.append(move_san)
                move_idx += 1
            except Exception:
                break
        else:
            break

    current_move_index = move_idx
    teaching_fen = board.fen()

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_move_index": current_move_index}}
    )

    next_user_move = full_sequence[current_move_index] if current_move_index < len(full_sequence) else None
    remaining = len([um for um in user_moves if um["index"] >= current_move_index])

    answer_hidden = trap.get("mode") == "avoidance"
    instruction = {
        "is_user_move": True,
        "message": (
            trap.get("how_to_avoid")
            if answer_hidden
            else f"Play {next_user_move} and notice why the line works."
        ),
        "remaining": remaining,
        "stage": "guided_try",
        "answer_hidden": answer_hidden,
    }
    if not answer_hidden:
        instruction["move"] = next_user_move

    return {
        "success": True,
        "lesson_type": lesson_type,
        "lesson_name": trap["name"],
        "lesson_key": trap_key,
        "teaching_fen": teaching_fen,
        "instruction": instruction,
        "auto_played_moves": auto_played,
        "trap_info": {
            "description": trap.get("explanation", ""),
            "why_it_works": trap.get("why_it_works", ""),
            "danger": trap.get("danger", ""),
            "how_to_avoid": trap.get("how_to_avoid", ""),
        },
        "mode": trap.get("mode", "execution"),
    }


async def process_trap_move(db, session_id: str, move: str) -> Dict:
    """Validate a move during trap practice."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    trap_data = session_doc.get("trap_data", {})
    full_sequence = trap_data.get("full_sequence", [])
    user_moves = trap_data.get("user_moves", [])
    engine_moves = trap_data.get("engine_moves", [])
    current_idx = session_doc.get("current_move_index", 0)

    if current_idx >= len(full_sequence):
        return {"complete": True, "message": "Trap complete!"}

    expected_move = full_sequence[current_idx]
    answer_hidden = trap_data.get("practice_mode") == "avoidance"

    # Normalize move comparison
    move_clean = move.replace("+", "").replace("#", "").strip()
    expected_clean = expected_move.replace("+", "").replace("#", "").strip()

    if move_clean != expected_clean:
        response = {
            "correct": False,
            "message": (
                "Not yet. Find the move that answers the threat before you develop."
                if answer_hidden
                else f"Not quite. This guided line uses {expected_move} here."
            ),
            "hint": trap_data.get("hints", ""),
            "answer_hidden": answer_hidden,
        }
        if not answer_hidden:
            response["expected_move"] = expected_move
        return response

    # Correct move! Advance and auto-play engine responses
    next_idx = current_idx + 1
    board = chess.Board(session_doc.get("current_fen", chess.STARTING_FEN))

    # Play the user's move
    try:
        board.push_san(expected_move)
    except Exception:
        board = chess.Board(chess.STARTING_FEN)
        for m in full_sequence[:next_idx]:
            try:
                board.push_san(m)
            except Exception:
                pass

    auto_played = []
    # Auto-play engine moves
    while next_idx < len(full_sequence):
        is_engine = any(em["index"] == next_idx for em in engine_moves)
        if is_engine:
            eng_move = full_sequence[next_idx]
            try:
                board.push_san(eng_move)
                auto_played.append(eng_move)
                next_idx += 1
            except Exception:
                break
        else:
            break

    teaching_fen = board.fen()

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_move_index": next_idx, "current_fen": teaching_fen}}
    )

    # Check if lesson complete
    if next_idx >= len(full_sequence):
        is_winning = any(um.get("is_winning") and um["move"] == expected_move for um in user_moves)
        return {
            "correct": True,
            "complete": True,
            "teaching_fen": teaching_fen,
            "auto_played": bool(auto_played),
            "auto_played_moves": auto_played,
            "message": f"Trap complete! {trap_data.get('explanation', 'Well done!')}",
            "why_it_works": trap_data.get("why_it_works", ""),
            "demonstrated": answer_hidden,
            "stage": "independent_proof" if answer_hidden else "guided_try",
        }

    # More moves to go
    next_move = full_sequence[next_idx]
    remaining_user = len([um for um in user_moves if um["index"] >= next_idx])

    msg = f"Good! Now play {next_move}."
    if auto_played:
        msg = f"Opponent played {', '.join(auto_played)}. Now play {next_move}."

    next_instruction = {
        "is_user_move": True,
        "message": (
            "New position. Answer the threat without seeing the move."
            if answer_hidden
            else msg
        ),
        "remaining": remaining_user,
        "answer_hidden": answer_hidden,
        "stage": "independent_proof" if answer_hidden else "guided_try",
    }
    if not answer_hidden:
        next_instruction["move"] = next_move

    return {
        "correct": True,
        "complete": False,
        "teaching_fen": teaching_fen,
        "auto_played": bool(auto_played),
        "auto_played_moves": auto_played,
        "message": msg,
        "next_instruction": next_instruction,
    }


# ─────────────────────────────────────────────
# ENDGAME LESSONS
# ─────────────────────────────────────────────

async def start_endgame_lesson(db, session_id: str, user_id: str, params: Dict) -> Dict:
    """Start an endgame lesson inside a coach session."""
    from services.endgame_theory_service import (
        get_lesson,
        get_verified_lesson_data,
    )

    category = params.get("category")
    lesson_key = params.get("lesson_key")

    if not category or not lesson_key:
        return {"error": "category and lesson_key are required"}

    public_lesson = get_lesson(category, lesson_key)
    lesson = get_verified_lesson_data(category, lesson_key)
    if not lesson or not public_lesson:
        return {
            "error": (
                f"Lesson '{category}/{lesson_key}' is not available until "
                "its chess content passes verification"
            )
        }

    positions = lesson.get("positions", [])
    if not positions:
        return {"error": "Lesson has no positions"}

    first_pos = positions[0]

    # Store in session
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    teaching_state = {
        "teaching_mode": True,
        "lesson_type": "endgame",
        "lesson_key": f"{category}/{lesson_key}",
        "lesson_name": lesson["name"],
        "endgame_data": {
            "category": category,
            "category_name": public_lesson.get("category_name", category),
            "rule": lesson.get("rule", ""),
            "description": lesson.get("description", ""),
            "positions": positions,
        },
        "current_position_index": 0,
        "lesson_stage": "guided_try",
        "lesson_attempts": 0,
        "lesson_hint_used": False,
        "pre_teaching_fen": session_doc.get("current_fen") if session_doc else None,
    }

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$set": teaching_state}
    )

    return {
        "success": True,
        "lesson_type": "endgame",
        "lesson_name": lesson["name"],
        "lesson_key": f"{category}/{lesson_key}",
        "teaching_fen": first_pos["fen"],
        "instruction": {
            "is_user_move": True,
            "message": first_pos.get("prompt", "Find the best move."),
            "remaining": len(positions),
            "stage": "guided_try",
            "answer_hidden": True,
        },
        "endgame_info": {
            "rule": lesson.get("rule", ""),
            "description": lesson.get("description", ""),
        },
    }


async def process_endgame_move(db, session_id: str, move: str) -> Dict:
    """Validate a move during endgame lesson."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        return {"error": "Session not found"}

    eg_data = session_doc.get("endgame_data", {})
    positions = eg_data.get("positions", [])
    current_idx = session_doc.get("current_position_index", 0)

    if current_idx >= len(positions):
        return {"complete": True, "message": "Endgame lesson complete!"}

    pos = positions[current_idx]
    correct_san = pos.get("correct_move_san", "")
    correct_uci = pos.get("correct_move_uci", "")
    stage = (
        "independent_proof"
        if current_idx == len(positions) - 1
        else "guided_try"
    )

    board = None
    user_move = None
    try:
        board = chess.Board(pos["fen"])
        user_move = board.parse_san(move)
    except (KeyError, ValueError):
        pass

    # Normalize comparison
    move_clean = move.replace("+", "").replace("#", "").strip()
    correct_clean = correct_san.replace("+", "").replace("#", "").strip()

    is_correct = move_clean == correct_clean

    # Also check UCI match
    if not is_correct and correct_uci:
        try:
            if user_move is not None and user_move.uci() == correct_uci:
                is_correct = True
        except Exception:
            pass

    # Exact tablebase truth grades chess correctness.  It may accept a move
    # different from the authored teaching move, but that alternative does not
    # prove the named technique was demonstrated.
    exact_evidence = None
    exact_reason = "not_probed"
    authored_move_matched = is_correct
    if board is not None and user_move is not None:
        try:
            from services.exact_endgame_service import probe_configured_fathom

            exact_evidence, exact_reason = await asyncio.to_thread(
                probe_configured_fathom, pos["fen"]
            )
            if (
                exact_evidence is not None
                and exact_evidence.root_outcome in {"win", "draw"}
            ):
                is_correct = (
                    user_move.uci() in exact_evidence.result_preserving_moves_uci
                )
            elif exact_evidence is not None:
                # Preserving an already-lost result does not prove a lesson move
                # correct. Keep the authored constraint for loss/ambiguous WDL.
                exact_reason = "non_teachable_root_outcome"
                exact_evidence = None
        except Exception:
            exact_evidence = None
            exact_reason = "runtime_failure"

    if not is_correct:
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$inc": {"lesson_attempts": 1}}
        )
        response = {
            "correct": False,
            "message": (
                "Not yet. Use the lesson rule and look at what changes after each candidate move."
                if stage == "independent_proof"
                else pos.get("on_wrong", "Not quite. Let's use the lesson rule.")
            ),
            "hint": pos.get("rule_reminder", pos.get("idea", "")),
            "stage": stage,
            "answer_hidden": stage == "independent_proof",
            "demonstrated": False,
            "exact_endgame_probe_reason": exact_reason,
        }
        if exact_evidence is not None:
            response["exact_endgame_evidence"] = exact_evidence.contract_dict()
        if stage == "guided_try":
            response["expected_move"] = correct_san
            response["explanation"] = pos.get("idea", "")
        return response

    # Correct! Apply the move to get new FEN
    try:
        board = chess.Board(pos["fen"])
        board.push(user_move if user_move is not None else board.parse_san(correct_san))
        new_fen = board.fen()
    except Exception:
        new_fen = pos["fen"]

    next_idx = current_idx + 1

    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "current_position_index": next_idx,
                "lesson_stage": (
                    "independent_proof"
                    if next_idx == len(positions) - 1
                    else "guided_try"
                ),
            },
            "$inc": {"lesson_attempts": 1},
        }
    )

    # Check if lesson complete
    if next_idx >= len(positions):
        response = {
            "correct": True,
            "complete": True,
            "teaching_fen": new_fen,
            "message": f"Excellent! You've completed the {session_doc.get('lesson_name', 'endgame')} lesson. Rule: {eg_data.get('rule', '')}",
            "stage": "independent_proof",
            "demonstrated": authored_move_matched,
            "result_preserved": bool(exact_evidence is not None),
            "exact_endgame_probe_reason": exact_reason,
        }
        if exact_evidence is not None:
            response["exact_endgame_evidence"] = exact_evidence.contract_dict()
            if not authored_move_matched:
                response["message"] = (
                    "That move also keeps the result. It works, although "
                    "it does not demonstrate the lesson's authored technique."
                )
        return response

    # Next position
    next_pos = positions[next_idx]
    next_stage = (
        "independent_proof"
        if next_idx == len(positions) - 1
        else "guided_try"
    )
    response = {
        "correct": True,
        "complete": False,
        "teaching_fen": next_pos["fen"],
        "message": pos.get("on_correct", "Correct!"),
        "next_instruction": {
            "is_user_move": True,
            "message": next_pos.get("prompt", "Find the best move."),
            "remaining": len(positions) - next_idx,
            "stage": next_stage,
            "answer_hidden": True,
        },
        "endgame_info": {
            "rule_reminder": pos.get("rule_reminder", ""),
            "idea": pos.get("idea", ""),
        },
        "demonstrated": authored_move_matched,
        "result_preserved": bool(exact_evidence is not None),
        "exact_endgame_probe_reason": exact_reason,
    }
    if exact_evidence is not None:
        response["exact_endgame_evidence"] = exact_evidence.contract_dict()
        if not authored_move_matched:
            response["message"] = (
                "That move also keeps the result. The lesson move shows "
                "the named technique more directly, but your move is not wrong."
            )
    return response


# ─────────────────────────────────────────────
# PIC PIECE-SAFETY LESSON
# ─────────────────────────────────────────────

def _public_pic_session(session: Dict[str, Any]) -> Dict[str, Any]:
    items = session.get("items") or []
    index = int(session.get("current_index") or 0)
    current = items[index] if index < len(items) else None
    return {
        "session_id": session.get("session_id"),
        "lesson_type": PIC_LESSON_TYPE,
        "status": session.get("status"),
        "current_index": index,
        "total_items": len(items),
        "completed_items": min(index, len(items)),
        "current_item": (
            {
                key: value
                for key, value in current.items()
                if not str(key).startswith("_")
            }
            if current else None
        ),
        "content_version": session.get("content_version"),
        "content_tier": session.get("content_tier"),
        "proof_detector_id": session.get("proof_detector_id"),
        "mastery_eligible": False,
    }


async def get_pic_piece_safety_lesson(
    db, user_id: str, session_id: Optional[str] = None
) -> Dict:
    """Return only a lesson owned by the requesting user."""
    query: Dict[str, Any] = {
        "user_id": user_id,
        "lesson_type": PIC_LESSON_TYPE,
    }
    if session_id:
        query["session_id"] = session_id
    else:
        query["status"] = {"$in": ["active", "paused"]}
    session = await db.learning_sessions.find_one(
        query,
        sort=[("updated_at", -1)],
    )
    if not session:
        return {"error": "Session not found"}
    return _public_pic_session(session)


async def start_pic_piece_safety_lesson(
    db, session_id: str, user_id: str, params: Dict
) -> Dict:
    """Start or resume a finite, own-game-first PIC lesson."""
    proof_detector_id = str((params or {}).get("proof_detector_id") or "")
    exact_focus = (
        proof_detector_id == "piece_safety.destination_safety_exact.v1"
    )
    existing_query = {
        "user_id": user_id,
        "lesson_type": PIC_LESSON_TYPE,
        "status": {"$in": ["active", "paused"]},
    }
    if exact_focus:
        # Never resume an older broad-piece-safety session into an exact plan.
        existing_query["proof_detector_id"] = proof_detector_id
    existing = await db.learning_sessions.find_one(existing_query)
    if existing:
        if existing.get("status") == "paused":
            now = datetime.now(timezone.utc)
            await db.learning_sessions.update_one(
                {"_id": existing["_id"], "status": "paused"},
                {"$set": {"status": "active", "updated_at": now}, "$push": {
                    "events": {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "lesson_resumed",
                        "idempotency_key": f"resume:{existing['session_id']}:{now.isoformat()}",
                        "occurred_at": now,
                        "evidence_eligible": False,
                        "rejection_reason": "assisted_verified_practice",
                    }
                }},
            )
            existing["status"] = "active"
        return _public_pic_session(existing)

    requested = max(1, min(int((params or {}).get("limit", 5)), 5))
    if exact_focus:
        from services.coaching_puzzle_service import CoachingPuzzleService

        supply = await CoachingPuzzleService(db).get_prescribed_training(
            user_id=user_id,
            weakness_pattern="piece_safety",
            num_puzzles=requested,
            required_quality_id="gap:piece_safety:destination_safety_exact",
        )
        selected = list(supply.get("puzzles") or [])[:requested]
    else:
        from services.puzzle_extraction_service import get_pattern_training_puzzles

        supply = await get_pattern_training_puzzles(
            db, user_id, "piece_safety", requested, private=True
        )
        own = [
            p for p in (supply.get("own_puzzles") or [])
            if not p.get("already_solved")
        ]
        community = supply.get("community_puzzles") or []
        selected = (own + community)[:requested]
    if not selected:
        return {"error": "No piece-safety practice positions are available yet"}

    items = [{
        "item_id": str(item.get("puzzle_id")),
        "_puzzle_id": str(item.get("puzzle_id")),
        "fen": item.get("fen"),
        "source": item.get("source"),
        "source_game_id": item.get("source_game_id"),
        "difficulty": item.get("difficulty"),
        "content_tier": "verified",
        "proof_detector_id": proof_detector_id or None,
        "mastery_eligible": False,
    } for item in selected if item.get("fen") and item.get("puzzle_id")]
    if not items:
        return {"error": "Available positions are missing board or solution data"}

    now = datetime.now(timezone.utc)
    session = {
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": PIC_LESSON_TYPE,
        "lesson_id": PIC_LESSON_ID,
        "skill_id": PIC_SKILL_ID,
        "content_version": PIC_CONTENT_VERSION,
        "content_tier": "verified",
        "proof_detector_id": proof_detector_id or None,
        "cohort_role": "admin",
        "status": "active",
        "current_index": 0,
        "items": items,
        "events": [{
            "event_id": str(uuid.uuid4()),
            "event_type": "lesson_started",
            "idempotency_key": f"start:{session_id}",
            "occurred_at": now,
            "evidence_eligible": False,
            "rejection_reason": "assisted_verified_practice",
        }],
        "created_at": now,
        "updated_at": now,
    }
    await db.learning_sessions.insert_one(session)
    return _public_pic_session(session)


async def process_pic_piece_safety_move(
    db,
    session_id: str,
    move: str,
    interaction_id: Optional[str] = None,
) -> Dict:
    session = await db.learning_sessions.find_one({"session_id": session_id})
    if not session:
        return {"error": "Session not found"}
    key = interaction_id or str(uuid.uuid4())
    for event in session.get("events") or []:
        if event.get("idempotency_key") == key:
            return event.get("result_payload") or {"duplicate": True}
    if session.get("status") == "completed":
        return {**_public_pic_session(session), "complete": True}
    if session.get("status") != "active":
        return {"error": "Session is not active"}

    index = int(session.get("current_index") or 0)
    items = session.get("items") or []
    if index >= len(items):
        return {**_public_pic_session(session), "complete": True}
    item = items[index]

    from services.verified_puzzle_runtime import (
        grade_resolved_puzzle,
        resolve_verified_puzzle,
    )

    puzzle = await resolve_verified_puzzle(
        db,
        str(item.get("_puzzle_id") or ""),
        user_id=str(session.get("user_id") or ""),
    )
    if not puzzle:
        return {"error": "This practice position needs verification before use"}
    evaluation = grade_resolved_puzzle(puzzle, move)
    if evaluation.get("quality") == "invalid":
        return evaluation
    correct = bool(evaluation.get("correct"))
    next_index = index + 1 if correct else index
    complete = correct and next_index >= len(items)
    now = datetime.now(timezone.utc)
    result = {
        "correct": correct,
        "quality": evaluation.get("quality"),
        "feedback": evaluation.get("feedback"),
        "best_move_san": evaluation.get("best_move_san"),
        "complete": complete,
        "current_index": next_index,
        "total_items": len(items),
        "next_item": (
            {
                key: value
                for key, value in items[next_index].items()
                if not str(key).startswith("_")
            }
            if next_index < len(items) else None
        ),
    }
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "answer_submitted",
        "idempotency_key": key,
        "occurred_at": now,
        "stage": "assisted_practice",
        "item_id": item["item_id"],
        "attempt_number": 1 + sum(
            1 for e in session.get("events") or []
            if e.get("event_type") == "answer_submitted"
            and e.get("item_id") == item["item_id"]
        ),
        "response": {"move_uci": move},
        "grader_version": "verified_puzzle_admission.v2",
        "result": "correct" if correct else "wrong",
        "evidence_eligible": False,
        "rejection_reason": "assisted_verified_practice",
        "result_payload": result,
    }
    try:
        from services.review_learning_adapter import (
            build_shadow_learning_event,
            lesson_result_from_guided_pic_practice,
        )
        _lesson_result = lesson_result_from_guided_pic_practice(
            session_id=session_id,
            item_id=item["item_id"],
            interaction_id=key,
            occurred_at=now,
            correct=correct,
        )
        _shadow_evidence = build_shadow_learning_event(
            _lesson_result,
            origin="guided_pic_practice",
        )
        event.update({
            "rollout_mode": "shadow",
            "adapter_version": _shadow_evidence["adapter_version"],
            "lesson_result": _shadow_evidence["lesson_result"],
            "shadow_earned_state": _shadow_evidence["shadow_earned_state"],
        })
    except Exception as _learning_exc:
        logger.warning(
            "[review-learning-shadow] PIC evidence adaptation failed: %s",
            _learning_exc,
        )
    update_set: Dict[str, Any] = {
        "current_index": next_index,
        "updated_at": now,
    }
    if complete:
        update_set.update({"status": "completed", "completed_at": now})
    write = await db.learning_sessions.update_one(
        {
            "_id": session["_id"],
            "current_index": index,
            "events.idempotency_key": {"$ne": key},
        },
        {"$set": update_set, "$push": {"events": event}},
    )
    if not write.modified_count:
        latest = await db.learning_sessions.find_one({"_id": session["_id"]})
        for prior in (latest or {}).get("events") or []:
            if prior.get("idempotency_key") == key:
                return prior.get("result_payload") or {"duplicate": True}
        return {"error": "Session changed; reload and try again"}
    return result


# ─────────────────────────────────────────────
# PERSONALIZED CURRICULUM LESSONS
# ─────────────────────────────────────────────

_STATE_RANK = {
    "new": 0,
    "learning": 1,
    "can_do_with_help": 2,
    "can_do_alone": 3,
    "used_in_games": 4,
}


def _public_personalized_item(item: Optional[Mapping[str, Any]]):
    if not item:
        return None
    return {
        key: value
        for key, value in item.items()
        if not str(key).startswith("_")
    }


def _blind_pending_event(
    session: Mapping[str, Any],
    item_id: str,
) -> Optional[Mapping[str, Any]]:
    for event in reversed(list(session.get("events") or [])):
        if event.get("item_id") != item_id:
            continue
        if event.get("event_type") == "answer_submitted":
            return None
        if event.get("event_type") == "move_staged":
            return event
    return None


def _blind_component_events(
    session: Mapping[str, Any],
    pending: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    move_event_id = str(pending.get("event_id") or "")
    return [
        event
        for event in (session.get("events") or [])
        if event.get("event_type") == "reason_component_answered"
        and event.get("move_event_id") == move_event_id
    ]


def _blind_reason_state(
    session: Mapping[str, Any],
    pending: Optional[Mapping[str, Any]],
):
    if not pending or not pending.get("reason_bundle"):
        return None, [], None
    from services.teaching_reason_contracts import (
        ReasonContractViolation,
        TeachingReasonBundle,
    )

    try:
        bundle = TeachingReasonBundle.from_private_dict(pending["reason_bundle"])
        answers = _blind_component_events(session, pending)
        return bundle, answers, bundle.question(len(answers))
    except (ReasonContractViolation, KeyError, TypeError, ValueError):
        return None, [], None


def _position_reason_summary(bundle, component_results):
    demonstrated = []
    missing = []
    for component, result in zip(bundle.components, component_results):
        if result.get("correct") is True:
            demonstrated.append({
                "kind": component.kind,
                "text": component.success_text,
            })
        else:
            missing.append({
                "kind": component.kind,
                "text": component.correction_text,
            })
    if demonstrated and not missing:
        title = "You saw the whole connection."
        eyebrow = "Connection understood"
    elif demonstrated:
        title = "You saw part of the idea."
        eyebrow = "One connection to rebuild"
    else:
        title = "Now I know what to teach first."
        eyebrow = "A useful starting point"
    return {
        "eyebrow": eyebrow,
        "title": title,
        "move_san": bundle.move_san,
        "target_result": bundle.target_result,
        "demonstrated": demonstrated,
        "missing": missing,
        "principle": (
            "Before you move an attacked piece, check the square it lands on "
            "and calculate one reply."
        ),
    }


def _public_blind_item(
    item: Optional[Mapping[str, Any]],
    *,
    awaiting_reason: bool = False,
    reason_question: Optional[Mapping[str, Any]] = None,
    move_san: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not item:
        return None
    result = {
        "item_id": item.get("item_id"),
        "fen": item.get("fen"),
        "orientation": item.get("orientation"),
        "prompt": "What would you play here?",
        "stage": item.get("stage"),
        "source_label": (
            "A position from one of your games"
            if item.get("source") == "own_game"
            else "A new verified position"
        ),
    }
    if awaiting_reason and reason_question:
        result.update({
            "move_san": move_san,
            "reason_question": dict(reason_question),
        })
    elif awaiting_reason:
        # Backward-compatible projection for any V1 session already in flight.
        legacy_choices = list(item.get("reason_choices") or [])
        result.update({
            "reason_prompt": "What did you pay attention to before moving?",
            "reason_choices": legacy_choices,
            "reason_question": {
                "question_id": "legacy-reason",
                "prompt": "What did you pay attention to before moving?",
                "choices": legacy_choices,
                "progress": {"current": 1, "total": 1},
            },
        })
    return result


def _public_personalized_session(session: Mapping[str, Any]) -> Dict[str, Any]:
    descriptor = session.get("descriptor") or {}
    items = descriptor.get("items") or []
    index = int(session.get("current_index") or 0)
    current = items[index] if index < len(items) else None
    highest = str(session.get("highest_earned_state") or "learning")
    blind = session.get("delivery_mode") == "blind_diagnostic"
    pending = (
        _blind_pending_event(session, str((current or {}).get("item_id") or ""))
        if blind and current
        else None
    )
    reason_bundle, reason_answers, reason_question = _blind_reason_state(
        session,
        pending,
    )
    if blind:
        awaiting_continue = session.get("pending_next_index") is not None
        return {
            "schema_version": PERSONALIZED_SESSION_SCHEMA_VERSION,
            "diagnostic_version": str(
                descriptor.get("diagnostic_version")
                or "home_replay_diagnostic.v1"
            ),
            "delivery_mode": "blind_diagnostic",
            "session_id": session.get("session_id"),
            "lesson_type": PERSONALIZED_LESSON_TYPE,
            "status": session.get("status"),
            "current_index": index,
            "completed_items": min(index, len(items)),
            "total_items": len(items),
            "current_item": _public_blind_item(
                None if awaiting_continue else current,
                awaiting_reason=bool(pending),
                reason_question=reason_question,
                move_san=reason_bundle.move_san if reason_bundle else None,
            ),
            "awaiting_reason": bool(pending),
            "awaiting_continue": awaiting_continue,
            "position_summary": (
                session.get("position_summary") if awaiting_continue else None
            ),
            "pending_move_uci": pending.get("move_uci") if pending else None,
            "stage": (current or {}).get("stage") or "result",
            "allowed_help": [
                "show_on_board",
                "ask_one_question",
                "let_me_try",
            ],
            "diagnostic_result": session.get("diagnostic_result"),
            "learner_state": {
                "state": highest,
                "real_game_evidence": "not_measured",
                "retention_evidence": "not_measured",
            },
        }
    return {
        "schema_version": PERSONALIZED_SESSION_SCHEMA_VERSION,
        "session_id": session.get("session_id"),
        "lesson_type": PERSONALIZED_LESSON_TYPE,
        "status": session.get("status"),
        "current_index": index,
        "completed_items": min(index, len(items)),
        "total_items": len(items),
        "current_item": _public_personalized_item(current),
        "stage": (
            session.get("display_stage")
            or (current or {}).get("stage")
            or "retain"
        ),
        "lesson": {
            "kind": descriptor.get("kind"),
            "id": descriptor.get("id"),
            "skill_id": descriptor.get("skill_id"),
            "title": descriptor.get("title"),
            "rule": descriptor.get("rule"),
            "intro": descriptor.get("intro"),
            "canonical_source": descriptor.get("canonical_source"),
            "content_version": descriptor.get("content_version"),
        },
        "teaching_profile": session.get("teaching_profile") or {},
        "learner_state": {
            "state": highest,
            "real_game_evidence": "not_measured",
            "retention_evidence": "not_measured",
        },
        "allowed_help": [
            "show_on_board",
            "ask_one_question",
            "let_me_try",
        ],
        "mastery_eligible": bool(
            current
            and current.get("stage") == "transfer"
            and current.get("board_verified")
        ),
    }


async def get_personalized_lesson(
    db,
    user_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {
        "user_id": user_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
    }
    if session_id:
        query["session_id"] = session_id
    else:
        query["status"] = {"$in": ["active", "paused"]}
    session = await db.learning_sessions.find_one(
        query,
        sort=[("updated_at", -1)],
    )
    if not session:
        return {"error": "Session not found"}
    return _public_personalized_session(session)


async def start_personalized_lesson(
    db,
    session_id: str,
    user_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    content_kind = str((params or {}).get("content_kind") or "")
    content_id = str((params or {}).get("content_id") or "")
    delivery_mode = str((params or {}).get("mode") or "lesson")
    if not content_kind or not content_id:
        return {"error": "content_kind and content_id are required"}

    existing_query = {
        "user_id": user_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
        "content_kind": content_kind,
        "content_id": content_id,
        "status": {"$in": ["active", "paused"]},
    }
    if delivery_mode == "blind_diagnostic":
        existing_query["delivery_mode"] = delivery_mode
    existing = await db.learning_sessions.find_one(existing_query)
    if existing:
        if existing.get("status") == "paused":
            now = datetime.now(timezone.utc)
            await db.learning_sessions.update_one(
                {"_id": existing["_id"], "status": "paused"},
                {
                    "$set": {"status": "active", "updated_at": now},
                    "$push": {
                        "events": {
                            "event_id": str(uuid.uuid4()),
                            "event_type": "lesson_resumed",
                            "idempotency_key": (
                                f"resume:{existing['session_id']}:{now.isoformat()}"
                            ),
                            "occurred_at": now,
                            "evidence_eligible": False,
                        }
                    },
                },
            )
            existing["status"] = "active"
        return _public_personalized_session(existing)

    from services.personalized_lesson_adapter import (
        LessonUnavailable,
        resolve_personalized_lesson,
    )
    try:
        descriptor = await resolve_personalized_lesson(
            db,
            user_id,
            content_kind=content_kind,
            content_id=content_id,
            params=params,
        )
    except LessonUnavailable as exc:
        return {"error": str(exc)}
    if bool((params or {}).get("review")):
        review_item = dict(descriptor["items"][-1])
        review_item["stage"] = "retain"
        descriptor = {
            **descriptor,
            "items": [review_item],
            "mastery_capability": "review",
        }

    from services.personal_teaching_profile import (
        build_personal_teaching_profile,
    )
    identity = {
        "kind": descriptor["kind"],
        "id": descriptor["id"],
        "canonical_source": descriptor["canonical_source"],
        "content_version": descriptor["content_version"],
    }
    profile = await build_personal_teaching_profile(
        db,
        user_id,
        skill_id=descriptor["skill_id"],
        canonical_lesson=identity,
    )
    now = datetime.now(timezone.utc)
    session = {
        "schema_version": PERSONALIZED_SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
        "content_kind": descriptor["kind"],
        "content_id": descriptor["id"],
        "skill_id": descriptor["skill_id"],
        "content_version": descriptor["content_version"],
        "delivery_mode": descriptor.get("delivery_mode") or delivery_mode,
        "diagnostic_version": descriptor.get("diagnostic_version"),
        "pair_fingerprint": descriptor.get("pair_fingerprint"),
        "status": "active",
        "current_index": 0,
        "highest_earned_state": "learning",
        "descriptor": descriptor,
        "teaching_profile": profile,
        "display_stage": (
            "retain"
            if bool((params or {}).get("review"))
            else str(profile.get("first_stage") or "diagnose")
        ),
        "events": [{
            "event_id": str(uuid.uuid4()),
            "event_type": "lesson_started",
            "idempotency_key": f"start:{session_id}",
            "occurred_at": now,
            "evidence_eligible": False,
            "content_version": descriptor["content_version"],
        }],
        "created_at": now,
        "updated_at": now,
    }
    await db.learning_sessions.insert_one(session)
    return _public_personalized_session(session)


def _item_help_events(
    session: Mapping[str, Any],
    item_id: str,
) -> list[Mapping[str, Any]]:
    return [
        event
        for event in (session.get("events") or [])
        if event.get("item_id") == item_id
        and event.get("event_type") in ("help_requested", "answer_submitted")
    ]


async def request_personalized_help(
    db,
    user_id: str,
    session_id: str,
    action: str,
    interaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    from services.personal_curriculum import HelpAction

    try:
        help_action = HelpAction(str(action))
    except ValueError:
        return {"error": "Unknown help action"}
    session = await db.learning_sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
    })
    if not session:
        return {"error": "Session not found"}
    if session.get("status") != "active":
        return {"error": "Session is not active"}
    key = interaction_id or str(uuid.uuid4())
    for event in session.get("events") or []:
        if event.get("idempotency_key") == key:
            return event.get("result_payload") or {"duplicate": True}

    items = (session.get("descriptor") or {}).get("items") or []
    index = int(session.get("current_index") or 0)
    if index >= len(items):
        return {"error": "Lesson is complete"}
    item = items[index]
    if help_action == HelpAction.SHOW_ON_BOARD:
        result = {
            "action": help_action.value,
            "message": (
                "Trace every attack on the piece you want to move, "
                "then check its destination."
            ),
            "highlight_squares": list(item.get("_help_squares") or []),
        }
    elif help_action == HelpAction.ASK_ONE_QUESTION:
        result = {
            "action": help_action.value,
            "message": (
                "After your move, what is the opponent's strongest capture, "
                "check, or direct threat?"
            ),
            "highlight_squares": [],
        }
    else:
        result = {
            "action": help_action.value,
            "message": "No hint. Take your time and make the move you trust.",
            "highlight_squares": [],
        }
    display_stage = (
        "notice"
        if help_action in (
            HelpAction.SHOW_ON_BOARD,
            HelpAction.ASK_ONE_QUESTION,
        )
        else str(item.get("stage") or "guide")
    )
    result["stage"] = display_stage
    now = datetime.now(timezone.utc)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "help_requested",
        "idempotency_key": key,
        "occurred_at": now,
        "item_id": item["item_id"],
        "action": help_action.value,
        "evidence_eligible": False,
        "result_payload": result,
    }
    write = await db.learning_sessions.update_one(
        {
            "_id": session["_id"],
            "events.idempotency_key": {"$ne": key},
        },
        {
            "$set": {"updated_at": now, "display_stage": display_stage},
            "$push": {"events": event},
        },
    )
    if not write.modified_count:
        return {"error": "Session changed; reload and try again"}
    return result


def _attempt_kind_for_stage(stage: str):
    from services.personal_curriculum import AttemptKind

    if stage in ("recall", "mix", "transfer"):
        return AttemptKind.INDEPENDENT
    if stage == "retain":
        return AttemptKind.REVIEW
    return AttemptKind.GUIDED


def _reason_correction(
    lesson_kind: str,
    reason_choice: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if not reason_choice:
        return (
            "reason_not_given",
            "Before the next move, name what you checked on the board.",
        )
    corrections = {
        "concept": {
            "looks_active": (
                "activity_before_safety",
                "An active-looking move is not enough. Check whether every piece you leave behind can be taken.",
            ),
            "not_sure": (
                "piece_safety_relationship_unclear",
                "Start with one question: after your move, which of your pieces can the opponent capture?",
            ),
        },
        "opening": {
            "wins_now": (
                "expects_immediate_opening_win",
                "An opening move does not need to win now. Name the piece it develops and the square that piece helps.",
            ),
            "not_sure": (
                "opening_plan_unclear",
                "Look for the undeveloped piece your plan needs next, then say which square it should reach.",
            ),
        },
        "trap": {
            "starts_attack": (
                "attacks_before_answering_threat",
                "Starting your own attack does not stop the opponent's check, capture, or direct threat. Name their threat first.",
            ),
            "not_sure": (
                "immediate_threat_unclear",
                "Before choosing a move, name the opponent's check, capture, or direct threat.",
            ),
        },
        "endgame": {
            "gives_check": (
                "check_without_endgame_rule",
                "A check is not automatically best. Apply the ending's rule and verify where the king or pawn lands.",
            ),
            "not_sure": (
                "endgame_rule_unclear",
                "Say which king, pawn, or rook relationship the lesson's rule asks you to create.",
            ),
        },
    }
    return corrections.get(lesson_kind, {}).get(
        reason_choice,
        (
            "reason_does_not_match_move",
            "The move works, but that is not why. Before the next position, name which piece or square the move helps.",
        ),
    )


async def process_personalized_move(
    db,
    session_id: str,
    move: str,
    interaction_id: Optional[str] = None,
    *,
    prediction_correct: Optional[bool] = None,
    reason_choice: Optional[str] = None,
    reason_component_id: Optional[str] = None,
    reasoning_consistent: Optional[bool] = None,
) -> Dict[str, Any]:
    session = await db.learning_sessions.find_one({
        "session_id": session_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
    })
    if not session:
        return {"error": "Session not found"}
    key = interaction_id or str(uuid.uuid4())
    for event in session.get("events") or []:
        if event.get("idempotency_key") == key:
            return event.get("result_payload") or {"duplicate": True}
    if session.get("status") == "completed":
        return {**_public_personalized_session(session), "complete": True}
    if session.get("status") != "active":
        return {"error": "Session is not active"}

    descriptor = session.get("descriptor") or {}
    items = descriptor.get("items") or []
    index = int(session.get("current_index") or 0)
    if index >= len(items):
        return {**_public_personalized_session(session), "complete": True}
    item = items[index]

    blind = session.get("delivery_mode") == "blind_diagnostic"
    reason_components = ()
    if blind:
        pending = _blind_pending_event(session, str(item.get("item_id") or ""))
        if not reason_choice:
            from services.personalized_lesson_adapter import _parse_move

            parsed = _parse_move(str(item.get("fen") or ""), move)
            if parsed is None:
                return {"error": "That move is not legal here"}
            if pending:
                staged = pending.get("result_payload") or {}
                if pending.get("move_uci") == parsed.uci():
                    return staged
                return {"error": "A move is already waiting for your reason"}
            v2_blind = bool(
                descriptor.get("diagnostic_version") == "home_replay_diagnostic.v2"
                and item.get("_diagnostic_quality_id")
            )
            if not v2_blind:
                staged = {
                    "awaiting_reason": True,
                    "session_id": session_id,
                    "current_index": index,
                    "current_item": _public_blind_item(item, awaiting_reason=True),
                }
                now = datetime.now(timezone.utc)
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "move_staged",
                    "idempotency_key": key,
                    "occurred_at": now,
                    "item_id": item["item_id"],
                    "move_uci": parsed.uci(),
                    "evidence_eligible": False,
                    "result_payload": staged,
                }
                write = await db.learning_sessions.update_one(
                    {
                        "_id": session["_id"],
                        "current_index": index,
                        "events.idempotency_key": {"$ne": key},
                    },
                    {"$set": {"updated_at": now}, "$push": {"events": event}},
                )
                if not write.modified_count:
                    return {"error": "Session changed; reload and try again"}
                return staged
            from services.caption_pipeline import build_reason_bundle_for_move

            bundle = build_reason_bundle_for_move(
                fen_before=str(item.get("fen") or ""),
                submitted_move=parsed.uci(),
                quality_id=str(item.get("_diagnostic_quality_id") or ""),
            )
            if bundle is None or not bundle.components:
                unavailable = {
                    "awaiting_reason": False,
                    "measurement_status": "unmeasured",
                    "retry_move": True,
                    "message": (
                        "That move may be playable, but I cannot verify its "
                        "chess explanation with this lesson yet. Try another move."
                    ),
                    "session_id": session_id,
                    "current_index": index,
                    "current_item": _public_blind_item(item),
                }
                now = datetime.now(timezone.utc)
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "move_unmeasured",
                    "idempotency_key": key,
                    "occurred_at": now,
                    "item_id": item["item_id"],
                    "move_uci": parsed.uci(),
                    "evidence_eligible": False,
                    "result_payload": unavailable,
                }
                write = await db.learning_sessions.update_one(
                    {
                        "_id": session["_id"],
                        "current_index": index,
                        "events.idempotency_key": {"$ne": key},
                    },
                    {"$set": {"updated_at": now}, "$push": {"events": event}},
                )
                if not write.modified_count:
                    return {"error": "Session changed; reload and try again"}
                return unavailable
            staged = {
                "awaiting_reason": True,
                "session_id": session_id,
                "current_index": index,
                "current_item": _public_blind_item(
                    item,
                    awaiting_reason=True,
                    reason_question=bundle.question(0),
                    move_san=bundle.move_san,
                ),
            }
            now = datetime.now(timezone.utc)
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "move_staged",
                "idempotency_key": key,
                "occurred_at": now,
                "item_id": item["item_id"],
                "move_uci": parsed.uci(),
                "move_san": bundle.move_san,
                "reason_bundle": bundle.private_dict(),
                "evidence_eligible": False,
                "result_payload": staged,
            }
            write = await db.learning_sessions.update_one(
                {
                    "_id": session["_id"],
                    "current_index": index,
                    "events.idempotency_key": {"$ne": key},
                },
                {"$set": {"updated_at": now}, "$push": {"events": event}},
            )
            if not write.modified_count:
                return {"error": "Session changed; reload and try again"}
            return staged
        if not pending:
            return {"error": "Make your move before choosing a reason"}
        if pending.get("move_uci") != str(move or "").lower():
            return {"error": "The reason must belong to the move you just made"}
        bundle, component_events, current_question = _blind_reason_state(
            session,
            pending,
        )
        if bundle is not None:
            if not reason_component_id or not current_question:
                return {"error": "This answer does not match the current question"}
            from services.teaching_reason_contracts import ReasonContractViolation

            try:
                component_result = bundle.grade_component(
                    index=len(component_events),
                    question_id=reason_component_id,
                    selected_choice_id=reason_choice,
                )
            except ReasonContractViolation as exc:
                return {"error": str(exc)}
            completed_components = [
                dict((event.get("result_payload") or {}).get("component_result") or {})
                for event in component_events
            ] + [component_result]
            if len(completed_components) < len(bundle.components):
                next_question = bundle.question(len(completed_components))
                payload = {
                    "awaiting_reason": True,
                    "session_id": session_id,
                    "current_index": index,
                    "component_result": component_result,
                    "current_item": _public_blind_item(
                        item,
                        awaiting_reason=True,
                        reason_question=next_question,
                        move_san=bundle.move_san,
                    ),
                }
                now = datetime.now(timezone.utc)
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "reason_component_answered",
                    "idempotency_key": key,
                    "occurred_at": now,
                    "item_id": item["item_id"],
                    "move_event_id": pending.get("event_id"),
                    "component_result": component_result,
                    "evidence_eligible": False,
                    "result_payload": payload,
                }
                write = await db.learning_sessions.update_one(
                    {
                        "_id": session["_id"],
                        "current_index": index,
                        "events.idempotency_key": {"$ne": key},
                    },
                    {"$set": {"updated_at": now}, "$push": {"events": event}},
                )
                if not write.modified_count:
                    return {"error": "Session changed; reload and try again"}
                return payload
            reason_components = tuple(completed_components)
            reasoning_consistent = all(
                component.get("correct") is True
                for component in reason_components
            )
        elif item.get("_expected_reason"):
            # A V1 in-flight session remains gradable after this release.
            reasoning_consistent = bool(
                reason_choice and reason_choice == item.get("_expected_reason")
            )

    from services.personalized_lesson_adapter import grade_personalized_move

    grade = await grade_personalized_move(
        descriptor,
        item,
        move,
        db=db,
        user_id=str(session.get("user_id") or ""),
    )
    correct = bool(grade.get("correct"))
    expected_reason = item.get("_expected_reason")
    if expected_reason and not reason_components:
        reasoning_consistent = bool(
            reason_choice and reason_choice == expected_reason
        )
    prior = _item_help_events(session, item["item_id"])
    requested_values = [
        event.get("action")
        for event in prior
        if event.get("event_type") == "help_requested"
    ]
    answer_was_revealed = any(
        (event.get("result_payload") or {}).get("answer_san")
        for event in prior
        if event.get("event_type") == "answer_submitted"
    )

    from services.personal_curriculum import (
        AssistanceKind,
        EvidenceSourceType,
        HelpAction,
        LessonResult,
        TeachingStage,
    )

    requested_help = tuple(
        HelpAction(value)
        for value in requested_values
        if value in {action.value for action in HelpAction}
    )
    assistance = []
    if any(
        action in (HelpAction.SHOW_ON_BOARD, HelpAction.ASK_ONE_QUESTION)
        for action in requested_help
    ):
        assistance.append(AssistanceKind.HINT)
    if answer_was_revealed:
        assistance.append(AssistanceKind.ANSWER_REVEALED)

    stage_value = str(item.get("stage") or "guide")
    stage = TeachingStage(stage_value)
    lesson_kind = str(descriptor.get("kind"))
    correction = None
    missed_reason_component = next(
        (
            component for component in reason_components
            if component.get("correct") is not True
        ),
        None,
    )
    if missed_reason_component is not None:
        misconception = f"{missed_reason_component.get('kind')}_not_understood"
        correction = str(missed_reason_component.get("feedback") or "")
    elif not correct:
        misconception = {
            "concept": "piece_left_unsafe",
            "opening": "opening_plan_not_recognized",
            "trap": "threat_not_identified",
            "endgame": "endgame_rule_not_applied",
        }.get(lesson_kind, "board_relationship_missed")
        correction = str(grade.get("feedback") or "")
    elif reasoning_consistent is False:
        misconception, correction = _reason_correction(
            lesson_kind,
            reason_choice,
        )
    else:
        misconception = None
    evidence_correct = correct
    if blind and str((grade.get("soundness") or {}).get("status")) not in {
        "sound",
        "serious_problem",
    }:
        # Keep the target result visible, but never award learning evidence
        # when the independent move-quality check could not run.
        evidence_correct = False
    event_contract = LessonResult(
        content_kind=str(descriptor["kind"]),
        content_id=str(descriptor["id"]),
        canonical_source=str(descriptor["canonical_source"]),
        content_version=str(descriptor["content_version"]),
        skill_id=str(descriptor["skill_id"]),
        primary_skill_id=str(descriptor["skill_id"]),
        attempt_kind=_attempt_kind_for_stage(stage_value),
        occurred_at=datetime.now(timezone.utc),
        stage=stage,
        correct=evidence_correct,
        assistance=tuple(assistance),
        requested_help=requested_help,
        position_id=str(item["item_id"]),
        board_verified=bool(item.get("board_verified")),
        distinct_position=stage_value in ("mix", "transfer", "retain"),
        prediction_correct=prediction_correct,
        reason_choice=reason_choice,
        reasoning_consistent=reasoning_consistent,
        reason_components=reason_components,
        misconception=misconception,
        corrective_action=correction,
        source_type=(
            EvidenceSourceType.MIXED_DRILL
            if stage_value == "mix"
            else EvidenceSourceType.LESSON
        ),
        grader_version=str(grade.get("grader_version") or ""),
        evidence_owner=str(descriptor["canonical_source"]),
        evidence_ref=str(item.get("source_ref") or item["item_id"]),
        source_event_id=key,
    )
    evidence = event_contract.event_dict()
    earned = evidence.get("earned_state") or "learning"
    current_state = str(session.get("highest_earned_state") or "learning")
    highest = (
        earned
        if _STATE_RANK.get(earned, 0) > _STATE_RANK.get(current_state, 0)
        else current_state
    )

    next_index = index + 1 if (correct or blind) else index
    complete = bool(next_index >= len(items)) if blind else bool(
        correct and next_index >= len(items)
    )
    reveal_answer = bool(not correct and stage_value == "guide")
    next_profile = session.get("teaching_profile") or {}
    if misconception:
        from services.personal_teaching_profile import (
            build_personal_teaching_profile,
        )

        next_profile = await build_personal_teaching_profile(
            db,
            str(session.get("user_id") or ""),
            skill_id=str(descriptor["skill_id"]),
            canonical_lesson={
                "kind": descriptor["kind"],
                "id": descriptor["id"],
                "canonical_source": descriptor["canonical_source"],
                "content_version": descriptor["content_version"],
            },
            current_interaction={
                "event_id": key,
                "misconception": misconception,
                "reasoning_consistent": reasoning_consistent,
            },
        )
    result = {
        "correct": correct,
        "feedback": correction or grade.get("feedback"),
        "answer_san": grade.get("answer_san") if reveal_answer else None,
        "answer_uci": grade.get("answer_uci") if reveal_answer else None,
        "misconception": misconception,
        "corrective_action": correction,
        "reasoning_consistent": reasoning_consistent,
        "reason_components": [dict(component) for component in reason_components],
        "target_result": grade.get("target_result"),
        "soundness": grade.get("soundness"),
        "teaching_profile": next_profile,
        "earned_state": evidence.get("earned_state"),
        "highest_earned_state": highest,
        "complete": complete,
        "current_index": next_index,
        "total_items": len(items),
        "next_item": (
            _public_blind_item(items[next_index])
            if blind and next_index < len(items)
            else _public_personalized_item(items[next_index])
            if next_index < len(items)
            else None
        ),
        "next_stage": (
            "contrast"
            if misconception
            else (
                str(items[next_index].get("stage") or "guide")
                if next_index < len(items)
                else "retain"
            )
        ),
    }
    if blind and reason_components:
        result["position_summary"] = _position_reason_summary(
            bundle,
            reason_components,
        )
    awaiting_continue = bool(
        blind
        and descriptor.get("diagnostic_version") == "home_replay_diagnostic.v2"
        and not complete
    )
    if awaiting_continue:
        result.update({
            "awaiting_continue": True,
            "current_index": index,
            "next_item": None,
            "next_stage": "connection",
        })
    now = datetime.now(timezone.utc)
    substantive_help = any(
        action in (HelpAction.SHOW_ON_BOARD, HelpAction.ASK_ONE_QUESTION)
        for action in requested_help
    )
    result["substantive_help"] = substantive_help
    if blind and complete:
        prior_attempts = []
        for prior_event in session.get("events") or []:
            if prior_event.get("event_type") != "answer_submitted":
                continue
            payload = prior_event.get("result_payload") or {}
            prior_attempts.append({
                "target_result": payload.get("target_result"),
                "soundness": payload.get("soundness"),
                "substantive_help": payload.get("substantive_help"),
                "reasoning_consistent": payload.get("reasoning_consistent"),
                "reason_components": payload.get("reason_components") or [],
            })
        prior_attempts.append({
            "target_result": result.get("target_result"),
            "soundness": result.get("soundness"),
            "substantive_help": substantive_help,
            "reasoning_consistent": reasoning_consistent,
            "reason_components": [dict(component) for component in reason_components],
        })
        from services.personal_curriculum import derive_home_diagnostic_result

        diagnostic_result = derive_home_diagnostic_result(
            (prior_attempts[0], prior_attempts[1])
        ).public_dict()
        result["diagnostic_result"] = diagnostic_result
    event = {
        **evidence,
        "event_id": str(uuid.uuid4()),
        "event_type": "answer_submitted",
        "idempotency_key": key,
        "item_id": item["item_id"],
        "result_payload": result,
    }
    update_set: Dict[str, Any] = {
        "current_index": index if awaiting_continue else next_index,
        "highest_earned_state": highest,
        "updated_at": now,
        "teaching_profile": next_profile,
        "display_stage": result["next_stage"],
    }
    if awaiting_continue:
        update_set.update({
            "pending_next_index": next_index,
            "position_summary": result.get("position_summary"),
        })
    if complete:
        games_at_completion = None
        games_collection = getattr(db, "games", None)
        if games_collection is not None:
            games_at_completion = await games_collection.count_documents({
                "user_id": session.get("user_id"),
                "is_analyzed": True,
            })
        update_set.update({"status": "completed", "completed_at": now})
        if blind:
            update_set["diagnostic_result"] = result.get("diagnostic_result")
        if games_at_completion is not None:
            update_set["analyzed_games_at_completion"] = games_at_completion
    write = await db.learning_sessions.update_one(
        {
            "_id": session["_id"],
            "current_index": index,
            "events.idempotency_key": {"$ne": key},
        },
        {"$set": update_set, "$push": {"events": event}},
    )
    if not write.modified_count:
        latest = await db.learning_sessions.find_one({"_id": session["_id"]})
        for prior_event in (latest or {}).get("events") or []:
            if prior_event.get("idempotency_key") == key:
                return prior_event.get("result_payload") or {"duplicate": True}
        return {"error": "Session changed; reload and try again"}
    return result


async def continue_home_diagnostic(
    db,
    user_id: str,
    session_id: str,
    *,
    interaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Acknowledge the persisted position summary and open the transfer board."""
    session = await db.learning_sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": PERSONALIZED_LESSON_TYPE,
        "delivery_mode": "blind_diagnostic",
    })
    if not session:
        return {"error": "Session not found"}
    key = interaction_id or str(uuid.uuid4())
    for event in session.get("events") or []:
        if event.get("idempotency_key") == key:
            return event.get("result_payload") or {"duplicate": True}
    next_index = session.get("pending_next_index")
    if next_index is None:
        return _public_personalized_session(session)
    items = (session.get("descriptor") or {}).get("items") or []
    try:
        next_index = int(next_index)
    except (TypeError, ValueError):
        return {"error": "The next position is not available"}
    if next_index < 0 or next_index >= len(items):
        return {"error": "The next position is not available"}

    now = datetime.now(timezone.utc)
    projected_session = {
        **session,
        "current_index": next_index,
        "pending_next_index": None,
        "position_summary": None,
        "display_stage": str(items[next_index].get("stage") or "transfer"),
        "updated_at": now,
    }
    projected_payload = _public_personalized_session(projected_session)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "position_summary_acknowledged",
        "idempotency_key": key,
        "occurred_at": now,
        "item_id": items[next_index].get("item_id"),
        "evidence_eligible": False,
        "result_payload": projected_payload,
    }
    write = await db.learning_sessions.update_one(
        {
            "_id": session["_id"],
            "pending_next_index": next_index,
            "events.idempotency_key": {"$ne": key},
        },
        {
            "$set": {
                "current_index": next_index,
                "pending_next_index": None,
                "position_summary": None,
                "display_stage": str(items[next_index].get("stage") or "transfer"),
                "updated_at": now,
            },
            "$push": {"events": event},
        },
    )
    if not write.modified_count:
        latest = await db.learning_sessions.find_one({"_id": session["_id"]})
        for prior_event in (latest or {}).get("events") or []:
            if prior_event.get("idempotency_key") == key:
                return _public_personalized_session(latest)
        return {"error": "Session changed; reload and try again"}
    latest = await db.learning_sessions.find_one({"_id": session["_id"]})
    return _public_personalized_session(latest)


# ─────────────────────────────────────────────
# GENERIC DISPATCH
# ─────────────────────────────────────────────

async def start_lesson(db, session_id: str, user_id: str, lesson_type: str, params: Dict) -> Dict:
    """Start a lesson of any type."""
    if lesson_type == "trap":
        return await start_trap_lesson(db, session_id, user_id, params)
    elif lesson_type == "opening_plan":
        return await start_trap_lesson(db, session_id, user_id, params)
    elif lesson_type == "endgame":
        return await start_endgame_lesson(db, session_id, user_id, params)
    elif lesson_type == PIC_LESSON_TYPE:
        return await start_pic_piece_safety_lesson(
            db, session_id, user_id, params
        )
    elif lesson_type == PERSONALIZED_LESSON_TYPE:
        return await start_personalized_lesson(
            db, session_id, user_id, params
        )
    elif lesson_type in ("learn_trap", "learn_main_line", "opening"):
        # Delegate to existing opening teaching. trap_key (when provided)
        # tells the lesson which specific trap to teach — without it the
        # lesson falls back to whatever's "suggested" on the session,
        # which may not match what the user clicked.
        from services.opening_teaching_integration import start_opening_lesson
        trap_key = params.get("trap_key") if isinstance(params, dict) else None
        return await start_opening_lesson(db, session_id, user_id, lesson_type, trap_key=trap_key)
    else:
        return {"error": f"Unknown lesson type: {lesson_type}"}


async def process_lesson_move(
    db,
    session_id: str,
    move: str,
    interaction_id: Optional[str] = None,
    reason_choice: Optional[str] = None,
    reason_component_id: Optional[str] = None,
) -> Dict:
    """Process a move — dispatches based on current lesson type in session."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        learning_session = await db.learning_sessions.find_one(
            {"session_id": session_id}
        )
        if learning_session and learning_session.get("lesson_type") == PIC_LESSON_TYPE:
            return await process_pic_piece_safety_move(
                db, session_id, move, interaction_id=interaction_id
            )
        if (
            learning_session
            and learning_session.get("lesson_type") == PERSONALIZED_LESSON_TYPE
        ):
            return await process_personalized_move(
                db,
                session_id,
                move,
                interaction_id=interaction_id,
                reason_choice=reason_choice,
                reason_component_id=reason_component_id,
            )
        return {"error": "Session not found"}

    lesson_type = session_doc.get("lesson_type", "opening")

    if lesson_type in {"trap", "opening_plan"}:
        return await process_trap_move(db, session_id, move)
    elif lesson_type == "endgame":
        return await process_endgame_move(db, session_id, move)
    else:
        # Default: opening teaching
        from services.opening_teaching_integration import process_teaching_move
        return await process_teaching_move(db, session_id, move)


async def exit_lesson(db, session_id: str, choice: str) -> Dict:
    """Exit any lesson type and restore game state."""
    session_doc = await db.coach_sessions.find_one({"session_id": session_id})
    if not session_doc:
        learning_session = await db.learning_sessions.find_one(
            {"session_id": session_id}
        )
        if learning_session and learning_session.get("lesson_type") in (
            PIC_LESSON_TYPE,
            PERSONALIZED_LESSON_TYPE,
        ):
            now = datetime.now(timezone.utc)
            status = "paused" if choice in ("pause", "continue_later") else "exited"
            await db.learning_sessions.update_one(
                {"_id": learning_session["_id"], "status": "active"},
                {"$set": {"status": status, "updated_at": now}, "$push": {
                    "events": {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "lesson_paused" if status == "paused" else "lesson_exited",
                        "idempotency_key": f"exit:{session_id}:{now.isoformat()}",
                        "occurred_at": now,
                        "evidence_eligible": False,
                        "rejection_reason": (
                            "assisted_verified_practice"
                            if learning_session.get("lesson_type") == PIC_LESSON_TYPE
                            else "navigation_event_only"
                        ),
                    }
                }},
            )
            return {"success": True, "status": status}
        return {"error": "Session not found"}

    restored_fen = session_doc.get("pre_teaching_fen")

    # Clean up teaching state
    await db.coach_sessions.update_one(
        {"session_id": session_id},
        {"$unset": {
            "teaching_mode": "",
            "lesson_type": "",
            "lesson_key": "",
            "lesson_name": "",
            "trap_data": "",
            "endgame_data": "",
            "current_move_index": "",
            "current_position_index": "",
            "pre_teaching_fen": "",
        }}
    )

    if choice == "continue_game" and restored_fen:
        await db.coach_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"current_fen": restored_fen}}
        )
        return {"success": True, "restored_fen": restored_fen}

    return {"success": True}


# ─────────────────────────────────────────────
# LESSON CATALOG (for frontend lesson picker)
# ─────────────────────────────────────────────

def get_lesson_catalog() -> Dict:
    """Return available lessons organized by type for the lesson picker UI."""
    from trick_library_service import get_all_opening_ideas, get_all_traps
    from services.curriculum_content_validator import get_defense_ready_trap_ids

    # Traps
    traps = get_all_traps()
    defense_ready = get_defense_ready_trap_ids()
    trap_lessons = []
    for trap in traps:
        if trap.get("content_id") not in defense_ready:
            continue
        trap_lessons.append({
            "key": trap["key"],
            "name": trap["name"],
            "opening": trap.get("opening", ""),
            "difficulty": trap.get("difficulty", "intermediate"),
            "description": trap.get("description", ""),
            "trap_for": trap.get("trap_for", ""),
            "tactical_theme": trap.get("tactical_theme", ""),
        })

    opening_idea_lessons = [
        {
            "key": lesson["key"],
            "name": lesson["name"],
            "opening": lesson.get("opening", ""),
            "difficulty": lesson.get("difficulty", "intermediate"),
            "description": lesson.get("description", ""),
            "plan_for": lesson.get("trap_for", ""),
            "learning_goal": lesson.get("learning_goal", ""),
            "canonical_source": lesson.get("canonical_source"),
        }
        for lesson in get_all_opening_ideas()
    ]

    # Endgames — already filtered by the offline truth gate.
    from services.endgame_theory_service import get_all_categories

    endgame_lessons = []
    for category in get_all_categories():
        for lesson in category.get("lessons", []):
            endgame_lessons.append({
                "category": category["key"],
                "category_name": category["name"],
                "lesson_key": lesson["key"],
                "name": lesson["name"],
                "rule": lesson.get("rule", ""),
                "description": lesson.get("description", ""),
                "positions_count": lesson.get("position_count", 0),
                "icon": category.get("icon", "book"),
                "canonical_source": lesson.get("canonical_source"),
            })

    return {
        "traps": trap_lessons,
        "opening_ideas": opening_idea_lessons,
        "endgames": endgame_lessons,
    }
