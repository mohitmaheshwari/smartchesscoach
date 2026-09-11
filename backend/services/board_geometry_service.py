"""Board Geometry lesson and live-transfer adapter.

Chess truth stays in caption_facts. This module owns lesson sequencing,
answer evidence, personal-moment projection, and the one-prompt PWC budget.
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import chess

CONTENT_PATH = Path(__file__).resolve().parents[1] / "data" / "board_geometry_lessons.json"
LESSON_TYPE = "board_geometry"
SCHEMA_VERSION = 1
PWC_PROMPT_LIMIT = 1
PWC_COOLDOWN_PLAYER_MOVES = 8
SERIOUS_QUALITIES = {"mistake", "blunder"}
SOUND_QUALITIES = {"best", "great", "good", "excellent", "book"}
MODULE_BY_FAMILY = {
    "knight": "knight_shared_square",
    "pawn": "pawn_fork_v",
    "diagonal": "diagonal_lines",
    "orthogonal": "rank_file_lines",
}
FOCUS_INSTRUCTIONS = {
    "knight_shared_square": "Before moving, scan for one knight square that reaches two pieces.",
    "pawn_fork_v": "Before a pawn move, scan the two forward diagonal squares.",
    "diagonal_lines": "Trace each bishop or queen diagonal to its first blocker.",
    "rank_file_lines": "Trace each rook or queen rank and file to its first blocker.",
}


def feature_enabled(user: Any = None) -> bool:
    """Default-off rollout; reviewers and local dev keep the walking skeleton."""
    if os.environ.get("BOARD_GEOMETRY_LEARNING", "false").lower() == "true":
        return True
    if os.environ.get("DEV_MODE", "false").lower() == "true":
        return True
    return bool(getattr(user, "is_reviewer", False))


def load_content() -> Dict[str, Any]:
    data = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported Board Geometry content schema")
    return data


def get_module(module_id: str) -> Dict[str, Any]:
    for module in load_content().get("modules", []):
        if module.get("module_id") == module_id:
            return module
    raise KeyError(module_id)


def catalog() -> Dict[str, Any]:
    data = load_content()
    return {
        "content_version": data["content_version"],
        "review_status": data["review_status"],
        "pwc_available": (
            os.environ.get("PWC_BOARD_GEOMETRY", "false").lower() == "true"
        ),
        "modules": [
            {
                "module_id": m["module_id"],
                "skill_id": m["skill_id"],
                "title": m["title"],
                "family": m["family"],
                "summary": m["summary"],
                "flash": m["flash"],
                "activity_count": len(m.get("activities", [])) + 1,
            }
            for m in data["modules"]
        ],
    }


def focus_instruction(module_id: str) -> Optional[str]:
    return FOCUS_INSTRUCTIONS.get(module_id)


def _public_item(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not item:
        return None
    return {
        k: copy.deepcopy(v)
        for k, v in item.items()
        if k not in {"expected", "hints", "correct_feedback", "wrong_feedback"}
    } | {"hint_count": len(item.get("hints") or [])}


def _current_item(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    items = session.get("items") or []
    index = int(session.get("current_index") or 0)
    return items[index] if 0 <= index < len(items) else None


def public_session(session: Dict[str, Any]) -> Dict[str, Any]:
    item = _current_item(session)
    return {
        "session_id": session["session_id"],
        "lesson_type": LESSON_TYPE,
        "module_id": session["module_id"],
        "skill_id": session["skill_id"],
        "title": session["title"],
        "mode": session.get("mode", "learning"),
        "status": session["status"],
        "display_stage": session.get("display_stage", "activity"),
        "current_index": int(session.get("current_index") or 0),
        "total_items": len(session.get("items") or []),
        "content_version": session["content_version"],
        "flash": copy.deepcopy(session.get("flash")),
        "current_item": _public_item(item),
        "current_item_state": copy.deepcopy(
            (session.get("item_states") or {}).get(item.get("item_id"), {})
            if item else {}
        ),
        "independent_passed": bool(session.get("independent_passed")),
        "highest_earned_state": session.get("highest_earned_state", "learning"),
        "personal_moment_type": session.get("personal_moment_type"),
        "delayed_available_at": session.get("delayed_available_at"),
    }


def _normalized_san(board: chess.Board, value: str) -> Optional[str]:
    try:
        return board.parse_san(value).uci()
    except Exception:
        try:
            move = chess.Move.from_uci(value)
            return move.uci() if move in board.legal_moves else None
        except Exception:
            return None


def grade_item(item: Dict[str, Any], response: Dict[str, Any]) -> bool:
    kind = item.get("kind")
    expected = item.get("expected") or {}
    if kind in {"select_square", "select_piece", "select_targets"}:
        actual = response.get("squares")
        if isinstance(actual, str):
            actual = [actual]
        return {str(v).lower() for v in (actual or [])} == {
            str(v).lower() for v in expected.get("squares", [])
        }
    if kind == "choose":
        return str(response.get("choice", "")).strip().lower() == str(
            expected.get("choice", "")
        ).strip().lower()
    if kind == "move":
        board = chess.Board(item["fen"])
        actual = _normalized_san(board, str(response.get("move") or ""))
        accepted = {
            _normalized_san(board, str(move)) for move in expected.get("moves", [])
        }
        accepted.discard(None)
        return actual is not None and actual in accepted
    return False


def _state_for(session: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    return copy.deepcopy((session.get("item_states") or {}).get(item_id) or {
        "attempts": 0,
        "hint_level": 0,
        "revealed": False,
        "correct": False,
    })


def _event(event_type: str, key: str, **values: Any) -> Dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "idempotency_key": key,
        "occurred_at": datetime.now(timezone.utc),
        **values,
    }


def _shape_modules(fen_before: str, move_san: str) -> List[Dict[str, Any]]:
    """Project canonical caption facts into learner-facing geometry shapes."""
    from services.caption_facts import extract_facts, named_fork_shapes
    from services.motif_profile_service import classify_aligned_geometry

    try:
        board = chess.Board(fen_before)
        try:
            move = board.parse_san(move_san)
        except Exception:
            move = chess.Move.from_uci(move_san)
            if move not in board.legal_moves:
                return []
        canonical_san = board.san(move)
        facts = extract_facts(
            fen_before=fen_before,
            played_san=canonical_san,
            best_move_san=canonical_san,
            cp_loss=0,
        )
    except Exception:
        return []

    shapes: List[Dict[str, Any]] = []
    for fork in named_fork_shapes(facts.get("multi_target_attack_evidence")):
        attacker = fork.get("attacker_piece_type")
        attacker_sq = fork.get("attacker_square")
        targets = fork.get("attacked_targets") or []
        family = None
        if attacker in ("knight", "pawn"):
            family = attacker
        elif attacker in ("bishop", "rook", "queen") and targets:
            try:
                a = chess.parse_square(attacker_sq)
                t = chess.parse_square(targets[0]["square"])
                df = abs(chess.square_file(a) - chess.square_file(t))
                dr = abs(chess.square_rank(a) - chess.square_rank(t))
                family = "diagonal" if df == dr else "orthogonal"
            except Exception:
                family = None
        if family in MODULE_BY_FAMILY:
            shapes.append({
                "family": family,
                "kind": "fork",
                "attacker_piece": attacker,
                "attacker_square": attacker_sq,
                "target_squares": [t["square"] for t in targets[:2]],
                "target_pieces": [t["piece_type"] for t in targets[:2]],
                "arrows": [[attacker_sq, t["square"]] for t in targets[:2]],
                "highlights": [attacker_sq] + [t["square"] for t in targets[:2]],
            })

    for aligned in facts.get("aligned_pieces_evidence") or []:
        labels = classify_aligned_geometry([aligned])
        if not labels:
            continue
        family = "diagonal" if aligned.get("line_kind") == "diagonal" else "orthogonal"
        shapes.append({
            "family": family,
            "kind": sorted(labels)[0],
            "attacker_piece": aligned.get("attacker_piece_type"),
            "attacker_square": aligned.get("attacker_square"),
            "front_piece": aligned.get("front_piece_type"),
            "front_square": aligned.get("front_piece_square"),
            "rear_piece": aligned.get("rear_piece_type"),
            "rear_square": aligned.get("rear_piece_square"),
            "target_squares": [
                aligned.get("front_piece_square"), aligned.get("rear_piece_square")
            ],
            "arrows": [[
                aligned.get("attacker_square"), aligned.get("rear_piece_square")
            ]],
            "highlights": [
                aligned.get("attacker_square"),
                aligned.get("front_piece_square"),
                aligned.get("rear_piece_square"),
            ],
        })
    return shapes


def _quality(ev: Dict[str, Any]) -> str:
    return str(ev.get("evaluation") or ev.get("quality") or "").lower()


def _cp_loss(ev: Dict[str, Any]) -> int:
    try:
        return abs(int(ev.get("cp_loss") or 0))
    except Exception:
        return 0


def _is_serious(ev: Dict[str, Any]) -> bool:
    quality = _quality(ev)
    return quality in SERIOUS_QUALITIES if quality else _cp_loss(ev) >= 100


def _is_sound(ev: Dict[str, Any]) -> bool:
    q = _quality(ev)
    return (q in SOUND_QUALITIES or not q) and _cp_loss(ev) <= 40


def _moment_copy(moment_type: str, shape: Dict[str, Any], played: str, trigger: str) -> Dict[str, Any]:
    family = shape["family"]
    module_id = MODULE_BY_FAMILY[family]
    attacker = shape.get("attacker_piece") or "piece"
    attacker_sq = shape.get("attacker_square")
    targets = shape.get("target_squares") or []
    if shape.get("kind") == "fork" and len(targets) >= 2:
        fact = f"The {attacker} on {attacker_sq} attacks {targets[0]} and {targets[1]} together."
        prompt = "Which two pieces now share one attack?"
    else:
        front = shape.get("front_piece") or "piece"
        front_sq = shape.get("front_square")
        rear = shape.get("rear_piece") or "piece"
        rear_sq = shape.get("rear_square")
        fact = (
            f"The {attacker} on {attacker_sq}, {front} on {front_sq}, "
            f"and {rear} on {rear_sq} share one line."
        )
        prompt = "Which piece is standing in front on this line?"
    principles = {
        "knight": "Two L-jumps can meet on one square.",
        "pawn": "A pawn attacks in a V pointing forward.",
        "diagonal": "Trace one square color and stop at the first blocker.",
        "orthogonal": "Trace the rank or file and stop at the first blocker.",
    }
    labels = {"allowed": "You allowed it", "missed": "You missed it", "found": "You found it"}  # allow-noncentral-caption
    prefixes = {
        "allowed": f"After {played}, {trigger} created this shape.",
        "missed": f"{trigger} would have created this shape.",
        "found": f"{played} created this shape.",
    }
    return {
        "moment_type": moment_type,
        "module_id": module_id,
        "family": family,
        "eyebrow": labels[moment_type],
        "prompt": prompt,
        "explanation": f"{prefixes[moment_type]} {fact}",
        "lesson": principles[family],
        "played_move": played,
        "trigger_move": trigger,
        "arrows": shape.get("arrows") or [],
        "highlights": shape.get("highlights") or [],
    }


def geometry_moments_for_move(ev: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return allowed, missed, and found projections for one user move."""
    if ev.get("is_opponent_move") is True or ev.get("by") == "coach":
        return []
    fen = ev.get("fen_before")
    played = ev.get("move")
    if not fen or not played:
        return []

    moments: List[Dict[str, Any]] = []
    played_shapes = _shape_modules(fen, played)
    played_families = {s["family"] for s in played_shapes}
    if _is_sound(ev):
        moments.extend(_moment_copy("found", s, played, played) for s in played_shapes)

    best = ev.get("best_move") or ev.get("best_move_san")
    if _is_serious(ev) and best:
        for shape in _shape_modules(fen, best):
            if shape["family"] not in played_families:
                moments.append(_moment_copy("missed", shape, played, best))

    pv = ev.get("pv_after_played") or []
    fen_after = ev.get("fen_after")
    if _is_serious(ev) and fen_after and pv:
        for shape in _shape_modules(fen_after, pv[0]):
            moments.append(_moment_copy("allowed", shape, played, pv[0]))
    order = {"allowed": 0, "missed": 1, "found": 2}
    moments.sort(key=lambda m: (order[m["moment_type"]], m["module_id"]))
    return moments


def _personal_item(
    moment: Dict[str, Any], ev: Dict[str, Any], game_id: str
) -> Optional[Dict[str, Any]]:
    moment_type = moment["moment_type"]
    if moment_type == "found":
        accepted = moment["played_move"]
        prompt = "This was your game. Find the move that creates the geometry."
    else:
        accepted = ev.get("best_move") or ev.get("best_move_san")
        prompt = "This was your game. Find the move that avoids the geometry mistake."
    if not accepted:
        return None
    reveal_fen = ev.get("fen_before")
    reveal_move = moment["trigger_move"]
    try:
        board = chess.Board(
            ev.get("fen_after") if moment_type == "allowed" else ev.get("fen_before")
        )
        board.push_san(reveal_move)
        reveal_fen = board.fen()
    except Exception:
        pass
    return {
        "item_id": f"personal:{game_id}:{ev.get('move_number')}:{moment_type}",
        "stage": "personal",
        "kind": "move",
        "fen": ev["fen_before"],
        "orientation": "black" if chess.Board(ev["fen_before"]).turn == chess.BLACK else "white",
        "prompt": prompt,
        "expected": {"moves": [accepted]},
        "hints": ["Use the same shape you saw on the clean board."],
        "correct_feedback": f"{moment['explanation']} {moment['lesson']}",
        "reveal": {
            "fen": reveal_fen,
            "arrows": moment["arrows"],
            "highlights": moment["highlights"],
        },
        "source": {"game_id": game_id, "move_number": ev.get("move_number")},
        "moment_type": moment_type,
    }


async def find_personal_item(db: Any, user_id: str, module_id: str) -> Optional[Dict[str, Any]]:
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).sort("created_at", -1).limit(30)
    async for analysis in cursor:
        game_id = str(analysis.get("game_id") or "")
        moves = ((analysis.get("stockfish_analysis") or {}).get("move_evaluations") or [])
        for ev in reversed(moves):
            for moment in geometry_moments_for_move(ev):
                if moment["module_id"] == module_id:
                    personal = _personal_item(moment, ev, game_id)
                    if personal:
                        return personal
    return None


async def start_lesson(
    db: Any,
    user_id: str,
    module_id: str,
    *,
    mode: str = "learning",
    admin_preview: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    module = get_module(module_id)
    existing = await db.learning_sessions.find_one({
        "user_id": user_id,
        "lesson_type": LESSON_TYPE,
        "module_id": module_id,
        "mode": mode,
        "status": {"$in": ["active", "paused"]},
    })
    if existing:
        if existing.get("status") == "paused":
            await db.learning_sessions.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}},
            )
            existing["status"] = "active"
        return public_session(existing)

    activities = copy.deepcopy(module["activities"])
    personal = None
    if mode == "delayed":
        prior = await db.learning_sessions.find_one({
            "user_id": user_id,
            "lesson_type": LESSON_TYPE,
            "module_id": module_id,
            "mode": "learning",
            "status": "completed",
            "independent_passed": True,
        }, sort=[("completed_at", -1)])
        if not prior:
            return {"error": "Complete the unseen lesson check first"}
        due = prior.get("delayed_available_at")
        if due and due > datetime.now(timezone.utc) and not admin_preview:
            return {"error": "Delayed recall is not due yet", "available_at": due}
        activities = [a for a in activities if a.get("stage") == "delayed_recall"]
    else:
        activities = [a for a in activities if a.get("stage") != "delayed_recall"]
        personal = await find_personal_item(db, user_id, module_id)
        if personal:
            insert_at = next(
                (i for i, a in enumerate(activities) if a.get("stage") == "post_test"),
                len(activities),
            )
            activities.insert(insert_at, personal)

    now = datetime.now(timezone.utc)
    session = {
        "session_id": session_id or f"geometry_{uuid.uuid4().hex}",
        "user_id": user_id,
        "lesson_type": LESSON_TYPE,
        "module_id": module_id,
        "skill_id": module["skill_id"],
        "title": module["title"],
        "mode": mode,
        "schema_version": SCHEMA_VERSION,
        "content_version": load_content()["content_version"],
        "content_tier": "engine_verified_internal",
        "status": "active",
        "display_stage": "activity" if mode == "delayed" else "flash",
        "current_index": 0,
        "items": activities,
        "item_states": {},
        "flash": copy.deepcopy(module["flash"]),
        "events": [_event("lesson_started", f"start:{user_id}:{module_id}:{mode}")],
        "highest_earned_state": "learning",
        "independent_passed": False,
        "personal_moment_type": personal.get("moment_type") if personal else None,
        "created_at": now,
        "updated_at": now,
    }
    await db.learning_sessions.insert_one(session)
    return public_session(session)


async def get_session(db: Any, user_id: str, session_id: str) -> Dict[str, Any]:
    session = await db.learning_sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": LESSON_TYPE,
    })
    return public_session(session) if session else {"error": "Session not found"}


async def process_action(
    db: Any,
    user_id: str,
    session_id: str,
    response: Dict[str, Any],
    interaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    session = await db.learning_sessions.find_one({
        "session_id": session_id,
        "user_id": user_id,
        "lesson_type": LESSON_TYPE,
    })
    if not session:
        return {"error": "Session not found"}
    key = interaction_id or str(uuid.uuid4())
    for event in session.get("events") or []:
        if event.get("idempotency_key") == key:
            return event.get("result_payload") or public_session(session)
    if session.get("status") == "completed":
        return {**public_session(session), "complete": True}

    action = str(response.get("action") or "answer")
    now = datetime.now(timezone.utc)
    if session.get("display_stage") == "flash":
        if action != "continue":
            return {"error": "Acknowledge the geometry flash first"}
        updated = {**session, "display_stage": "activity"}
        result = {**public_session(updated), "flash_seen": True}
        event = _event("flash_seen", key, evidence_eligible=False, result_payload=result)
        await db.learning_sessions.update_one(
            {"_id": session["_id"], "events.idempotency_key": {"$ne": key}},
            {"$set": {"display_stage": "activity", "updated_at": now}, "$push": {"events": event}},
        )
        return result

    item = _current_item(session)
    if not item:
        return {"error": "Lesson has no current item"}
    item_id = item["item_id"]
    state = _state_for(session, item_id)

    if action == "hint":
        hints = item.get("hints") or []
        level = min(len(hints), int(state.get("hint_level") or 0) + 1)
        state["hint_level"] = level
        result = {"hint": hints[level - 1] if level else "", "hint_level": level}
        event = _event("hint_requested", key, item_id=item_id, hint_level=level,
                       evidence_eligible=False, result_payload=result)
        await db.learning_sessions.update_one(
            {"_id": session["_id"], "events.idempotency_key": {"$ne": key}},
            {"$set": {f"item_states.{item_id}": state, "updated_at": now},
             "$push": {"events": event}},
        )
        return result

    if action == "reveal":
        state["revealed"] = True
        next_index = int(session.get("current_index") or 0) + 1
        complete = next_index >= len(session.get("items") or [])
        result = {
            "revealed": True,
            "answer": copy.deepcopy(item.get("expected")),
            "feedback": item.get("correct_feedback"),
            "reveal": copy.deepcopy(item.get("reveal") or {}),
            "advance": True,
            "complete": complete,
        }
        event = _event(
            "answer_revealed",
            key,
            item_id=item_id,
            stage=item.get("stage"),
            evidence_eligible=False,
            rejection_reason="answer_revealed",
            result_payload=result,
        )
        set_values: Dict[str, Any] = {
            f"item_states.{item_id}": state,
            "current_index": next_index,
            "updated_at": now,
        }
        if complete:
            prior = list(session.get("events") or [])
            passed = any(
                prior_event.get("stage") in {"post_test", "delayed_recall"}
                and prior_event.get("result") == "correct"
                and prior_event.get("evidence_eligible")
                for prior_event in prior
            )
            set_values.update({
                "status": "completed",
                "completed_at": now,
                "independent_passed": passed,
                "highest_earned_state": "remembered" if passed else "learning",
                "delayed_available_at": (
                    now + timedelta(hours=24)
                    if session.get("mode") == "learning" and passed
                    else None
                ),
            })
        await db.learning_sessions.update_one(
            {
                "_id": session["_id"],
                "current_index": int(session.get("current_index") or 0),
                "events.idempotency_key": {"$ne": key},
            },
            {"$set": set_values, "$push": {"events": event}},
        )
        return result

    correct = grade_item(item, response)
    state["attempts"] = int(state.get("attempts") or 0) + 1
    state["correct"] = bool(correct)
    independent = bool(correct and not state.get("revealed") and int(state.get("hint_level") or 0) == 0)
    next_index = int(session.get("current_index") or 0) + (1 if correct else 0)
    complete = correct and next_index >= len(session.get("items") or [])
    result = {
        "correct": correct,
        "feedback": item.get("correct_feedback") if correct else "Not yet. Trace the shape from the first piece and try again.",
        "reveal": copy.deepcopy(item.get("reveal") or {}) if correct else {},
        "advance": correct,
        "complete": complete,
        "current_index": next_index if correct else int(session.get("current_index") or 0),
    }
    event = _event(
        "answer_submitted", key, item_id=item_id, stage=item.get("stage"),
        response=copy.deepcopy(response), result="correct" if correct else "wrong",
        attempt_number=state["attempts"], hint_level=int(state.get("hint_level") or 0),
        revealed=bool(state.get("revealed")),
        evidence_eligible=independent and item.get("stage") in {"baseline", "post_test", "delayed_recall"},
        rejection_reason=None if independent else "assisted_or_incorrect",
        result_payload=result,
    )
    set_values: Dict[str, Any] = {f"item_states.{item_id}": state, "updated_at": now}
    if correct:
        set_values["current_index"] = next_index
    if complete:
        events = list(session.get("events") or []) + [event]
        post_events = [
            e for e in events
            if e.get("stage") in {"post_test", "delayed_recall"}
            and e.get("result") == "correct" and e.get("evidence_eligible")
        ]
        passed = bool(post_events)
        set_values.update({
            "status": "completed", "completed_at": now,
            "independent_passed": passed,
            "highest_earned_state": "remembered" if passed else "learning",
            "delayed_available_at": now + timedelta(hours=24)
                if session.get("mode") == "learning" and passed else None,
        })
    write = await db.learning_sessions.update_one(
        {"_id": session["_id"], "current_index": int(session.get("current_index") or 0),
         "events.idempotency_key": {"$ne": key}},
        {"$set": set_values, "$push": {"events": event}},
    )
    if not write.modified_count:
        latest = await db.learning_sessions.find_one({"_id": session["_id"]})
        for prior in (latest or {}).get("events") or []:
            if prior.get("idempotency_key") == key:
                return prior.get("result_payload") or {"duplicate": True}
        return {"error": "Session changed; reload and try again"}
    if correct and not complete:
        latest = await db.learning_sessions.find_one({"_id": session["_id"]})
        result["next_item"] = _public_item(_current_item(latest))
    return result


async def pause_lesson(db: Any, user_id: str, session_id: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    write = await db.learning_sessions.update_one(
        {"session_id": session_id, "user_id": user_id, "lesson_type": LESSON_TYPE, "status": "active"},
        {"$set": {"status": "paused", "updated_at": now},
         "$push": {"events": _event("lesson_paused", f"pause:{session_id}:{now.isoformat()}")}},
    )
    return {"success": bool(write.modified_count), "status": "paused"}


async def eligible_modules(db: Any, user_id: str) -> Set[str]:
    from services.concept_mastery_service import get_board_geometry_mastery_projection
    projection = await get_board_geometry_mastery_projection(db, user_id)
    return {
        module_id
        for module_id, record in projection.get("modules", {}).items()
        if record.get("state") in {"remembered", "proven_in_games"}
    }


def _history_user_event(session_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    history = session_doc.get("move_history") or []
    player_moves = [m for m in history if m.get("by") == "player"]
    player = player_moves[-1] if player_moves else None
    coach = next((m for m in reversed(history) if m.get("by") == "coach"), None)
    if not player:
        return None
    ev = copy.deepcopy(player)
    player_move_number = len(player_moves)
    ev["move_number"] = player_move_number
    stored = session_doc.get("geometry_last_user_evidence") or {}
    stored_number = stored.get("move_number")
    same_record = (
        stored.get("move") == player.get("move")
        and str(stored_number) == str(player_move_number)
    )
    # Live teaching waits for the completed central move verdict. The coach
    # reply and caption request run concurrently, so defaulting missing facts
    # to a sound move here could create a false "You found it" card.
    if not same_record or not _quality(stored):
        return None
    ev.update(copy.deepcopy(stored))
    eb, ea = ev.get("eval_before"), ev.get("eval_after")
    if eb is not None and ea is not None:
        color = session_doc.get("user_color", "white")
        ev["cp_loss"] = max(0, int(((eb - ea) if color == "white" else (ea - eb)) * 100))
    if (
        coach
        and coach.get("fen_before") == player.get("fen_after")
        and not ev.get("pv_after_played")
    ):
        ev["fen_after"] = player.get("fen_after")
        ev["pv_after_played"] = [coach.get("move")]
    return ev


async def build_pwc_moment(
    db: Any,
    session_doc: Dict[str, Any],
    *,
    allow_surface: bool = True,
) -> Optional[Dict[str, Any]]:
    if os.environ.get("PWC_BOARD_GEOMETRY", "false").lower() != "true":
        return None
    focus_module = session_doc.get("geometry_focus_module")
    if not focus_module:
        return None
    if not session_doc.get("geometry_focus_verified"):
        learned = await eligible_modules(db, session_doc.get("user_id", ""))
        if focus_module not in learned:
            return None
    ev = _history_user_event(session_doc)
    if not ev:
        return None
    move_key = f"{ev.get('move_number') or len(session_doc.get('move_history') or [])}:{ev.get('move')}"
    for old in session_doc.get("geometry_events") or []:
        if old.get("move_key") == move_key:
            return old.get("payload") if old.get("outcome") == "pending" else None
    moments = [
        moment
        for moment in geometry_moments_for_move(ev)
        if moment["module_id"] == focus_module
    ]
    if not moments:
        return None
    surfaced = (
        allow_surface
        and int(session_doc.get("geometry_prompt_count") or 0) < PWC_PROMPT_LIMIT
    )
    payload = {
        **moments[0],
        "event_id": uuid.uuid4().hex,
        "revealed": False,
        "surfaced": surfaced,
    }
    event = {
        "event_id": payload["event_id"], "move_key": move_key,
        "move_number": ev.get("move_number"), "payload": payload,
        "surfaced": surfaced,
        "outcome": "pending" if surfaced else "observed",
        "created_at": datetime.now(timezone.utc),
    }
    session_filter: Dict[str, Any] = {
        "_id": session_doc["_id"],
        "geometry_events.move_key": {"$ne": move_key},
    }
    update: Dict[str, Any] = {"$push": {"geometry_events": event}}
    if surfaced:
        session_filter["$or"] = [
            {"geometry_prompt_count": {"$exists": False}},
            {"geometry_prompt_count": {"$lt": PWC_PROMPT_LIMIT}},
        ]
        update["$inc"] = {"geometry_prompt_count": 1}
    write = await db.coach_sessions.update_one(
        session_filter,
        update,
    )
    return payload if surfaced and write.modified_count else None


async def respond_to_pwc_moment(
    db: Any, user_id: str, session_id: str, event_id: str, action: str
) -> Dict[str, Any]:
    session = await db.coach_sessions.find_one({"session_id": session_id, "user_id": user_id})
    if not session:
        return {"error": "Session not found"}
    event = next((e for e in session.get("geometry_events") or [] if e.get("event_id") == event_id), None)
    if not event:
        return {"error": "Geometry moment not found"}
    action = action if action in {"reveal", "skip", "acknowledge"} else "skip"
    outcome = "revealed" if action == "reveal" else action
    await db.coach_sessions.update_one(
        {"_id": session["_id"], "geometry_events.event_id": event_id},
        {"$set": {"geometry_events.$.outcome": outcome,
                  "geometry_events.$.payload.revealed": action == "reveal",
                  "geometry_events.$.responded_at": datetime.now(timezone.utc)}},
    )
    payload = copy.deepcopy(event["payload"])
    if action == "reveal":
        payload["revealed"] = True
        return {"success": True, "moment": payload}
    return {"success": True, "dismissed": True}


def postgame_summary(session_doc: Dict[str, Any]) -> Dict[str, Any]:
    events = session_doc.get("geometry_events") or []
    if not events:
        return {"measured": False, "message": "This pattern was not measured in this game."}
    found = sum(1 for e in events if (e.get("payload") or {}).get("moment_type") == "found")
    missed = sum(1 for e in events if (e.get("payload") or {}).get("moment_type") in {"missed", "allowed"})
    return {
        "measured": True, "found": found, "missed": missed,
        "message": (
            f"You found {found} geometry moment{'s' if found != 1 else ''} and "
            f"missed {missed}. Keep the same board scan next game."
        ),
    }
