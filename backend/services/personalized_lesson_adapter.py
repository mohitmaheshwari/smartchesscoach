"""Normalize verified canonical lessons for one personalized workspace.

This is a derived view. Opening, trap, endgame, and tactical facts remain in
their existing canonical owners; this adapter stores no lesson copy.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import chess


ADAPTER_SCHEMA_VERSION = "personalized_lesson_adapter.v1"
TACTICAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "theory"
    / "tactical_patterns.json"
)
TACTICAL_SOURCE = "backend/data/theory/tactical_patterns.json"


class LessonUnavailable(ValueError):
    pass


def _reason_choices(kind: str) -> list[Dict[str, str]]:
    """Return player-visible reasons while keeping the expected reason private."""
    choices = {
        "opening": (
            ("continues_plan", "It brings the next piece into my plan."),
            ("wins_now", "It wins a piece or pawn immediately."),
        ),
        "trap": (
            ("answers_threat", "It answers the opponent's immediate threat."),
            ("starts_attack", "It starts my own attack first."),
        ),
        "endgame": (
            ("uses_rule", "It uses the rule for this ending."),
            ("gives_check", "It gives check, so it must be best."),
        ),
        "concept": (
            ("keeps_piece_safe", "It leaves my pieces protected or able to move."),
            ("looks_active", "It looks active, even if a piece can be taken."),
        ),
    }[kind]
    return [
        {"id": key, "label": label}
        for key, label in (*choices, ("not_sure", "I am not sure yet."))
    ]


def _content_version(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def supports_personalized_lesson_identity(
    content_kind: str,
    content_id: str,
) -> bool:
    """Check canonical availability before a curriculum CTA enters the workspace."""
    kind = str(content_kind or "").strip().lower()
    lesson_id = str(content_id or "").strip()
    try:
        if kind == "opening":
            from services.opening_theory_json_service import (
                get_lesson_move_steps,
                get_opening_theory,
            )

            return bool(
                get_opening_theory(lesson_id)
                and get_lesson_move_steps(lesson_id)
            )
        if kind == "trap":
            from trick_library_service import get_trap_for_practice

            return bool(
                get_trap_for_practice(lesson_id, "avoidance")
                or get_trap_for_practice(lesson_id, "execution")
            )
        if kind == "trap_set":
            from trick_library_service import get_traps_by_opening

            return bool(get_traps_by_opening(lesson_id))
        if kind == "endgame":
            from services.endgame_theory_service import get_lesson

            parts = lesson_id.split("/", 1)
            return bool(len(parts) == 2 and get_lesson(parts[0], parts[1]))
        if kind == "concept":
            with TACTICAL_PATH.open("r", encoding="utf-8") as handle:
                patterns = json.load(handle)
            key = (
                "undefended_piece"
                if lesson_id in ("piece_safety", "piece_safety_simple_hang")
                else lesson_id
            )
            return isinstance(patterns.get(key), Mapping)
    except (KeyError, TypeError, ValueError):
        return False
    return False


def _lesson_skill_id(
    kind: str,
    content_id: str,
    params: Mapping[str, Any],
) -> str:
    """Resolve tracking identity through the canonical skill tree owner."""
    from services.engine2_skill_builder import resolve_skill_id

    return resolve_skill_id(
        kind,
        content_id,
        requested_skill_id=str(params.get("skill_id") or "") or None,
    )


def _stage(index: int, total: int) -> str:
    if total <= 1:
        return "guide"
    if index == total - 1:
        return "transfer"
    if index == 0:
        return "guide"
    return "recall"


def _blind_diagnostic_candidate(
    supplied: Mapping[str, Any],
    resolved: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Shape one exact own-game puzzle for strict diagnostic pairing."""
    from services.destination_safety_detector import QUALITY_ID

    verdict = resolved.get("verified_admission") or {}
    if verdict.get("quality_id") != QUALITY_ID:
        return None
    detector_version = str(verdict.get("detector_version") or "")
    game_id = str(
        supplied.get("source_game_id")
        or resolved.get("source_game_id")
        or ""
    )
    fen = str(resolved.get("fen") or supplied.get("fen") or "")
    played_uci = str(verdict.get("played_move_uci") or "")
    if not detector_version or not game_id or not fen or not played_uci:
        return None
    try:
        board = chess.Board(fen)
        played = chess.Move.from_uci(played_uci)
        if played not in board.legal_moves:
            return None
        piece = board.piece_at(played.from_square)
        if piece is None or piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            return None
    except (TypeError, ValueError):
        return None
    return {
        "puzzle_id": str(supplied.get("puzzle_id") or resolved.get("puzzle_id") or ""),
        "fen": fen,
        "normalized_fen": " ".join(board.fen().split()[:4]),
        "orientation": "white" if board.turn == chess.WHITE else "black",
        "source_game_id": game_id,
        "source_kind": "own_game",
        "quality_id": QUALITY_ID,
        "detector_version": detector_version,
        "moved_piece": chess.piece_name(piece.piece_type),
        "moved_origin": chess.square_name(played.from_square),
    }


def select_blind_diagnostic_pair(
    candidates: list[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Choose a deterministic cross-game, cross-position, cross-piece pair."""
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1:]:
            if left.get("quality_id") != right.get("quality_id"):
                continue
            if left.get("detector_version") != right.get("detector_version"):
                continue
            if left.get("source_game_id") == right.get("source_game_id"):
                continue
            if left.get("normalized_fen") == right.get("normalized_fen"):
                continue
            if left.get("moved_piece") == right.get("moved_piece"):
                continue
            selected = [dict(left), dict(right)]
            identity = [{
                "puzzle_id": item.get("puzzle_id"),
                "game_id": item.get("source_game_id"),
                "fen": item.get("normalized_fen"),
                "piece": item.get("moved_piece"),
                "quality_id": item.get("quality_id"),
                "detector_version": item.get("detector_version"),
            } for item in selected]
            return {
                "items": selected,
                "fingerprint": _content_version({"pair": identity}),
            }
    return None


def _move_uci(board: chess.Board, san: str) -> str:
    return board.parse_san(str(san)).uci()


def _opening_descriptor(content_id: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    from services.opening_theory_json_service import (
        get_lesson_move_steps,
        get_opening_theory,
        resolve_opening_key,
    )

    resolved = resolve_opening_key(content_id)
    opening = get_opening_theory(content_id)
    steps = get_lesson_move_steps(
        content_id,
        str(params.get("variation") or "") or None,
    )
    if not resolved or not opening or not steps:
        raise LessonUnavailable("Verified opening lesson not found")

    player_color = str(
        params.get("player_color") or opening.get("color") or "white"
    ).lower()
    if player_color not in ("white", "black"):
        player_color = "white"
    board = chess.Board()
    candidates = []
    for index, step in enumerate(steps):
        san = str(step.get("move") or "")
        if not san:
            continue
        before = board.fen()
        try:
            uci = _move_uci(board, san)
            board.push_uci(uci)
        except (ValueError, AssertionError):
            raise LessonUnavailable("Opening lesson contains an invalid move")
        if str(step.get("side") or "") != player_color:
            continue
        candidates.append({
            "item_id": f"{resolved}:{index}",
            "fen": before,
            "orientation": player_color,
            "prompt": "What move continues your plan here?",
            "reason_prompt": "Why does your move belong here?",
            "reason_choices": _reason_choices("opening"),
            "_expected_reason": "continues_plan",
            "_help_squares": [uci[:2]],
            "_expected_san": san,
            "_expected_uci": uci,
            "_on_correct": str(step.get("explanation") or ""),
            "_on_wrong": "Check which piece or pawn should leave its starting square next.",
            "source": "canonical_opening",
            "source_ref": f"{resolved}:{index}",
            "board_verified": True,
        })
    if not candidates:
        raise LessonUnavailable("Opening lesson has no moves for this color")
    for index, item in enumerate(candidates):
        item["stage"] = _stage(index, len(candidates))

    raw_version = {
        "opening": resolved,
        "variation": params.get("variation"),
        "steps": steps,
    }
    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "opening",
        "id": resolved,
        "skill_id": _lesson_skill_id("opening", resolved, params),
        "title": str(opening.get("name") or resolved.replace("_", " ").title()),
        "rule": str(
            (opening.get("golden_rules") or ["Develop with a clear plan."])[0]
        ),
        "intro": str(opening.get("summary") or ""),
        "canonical_source": "backend/data/opening_curriculum.json",
        "content_version": _content_version(raw_version),
        "items": candidates,
        "player_color": player_color,
        "mastery_capability": (
            "independent" if len(candidates) > 1 else "guided"
        ),
    }


def _trap_descriptor(content_id: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    from trick_library_service import get_trap_for_practice

    mode = str(params.get("mode") or "avoidance")
    trap = get_trap_for_practice(content_id, mode)
    if not trap and mode != "execution":
        mode = "execution"
        trap = get_trap_for_practice(content_id, mode)
    if not trap:
        raise LessonUnavailable("Verified trap lesson not found")

    expected_indexes = {
        int(item["index"]) for item in trap.get("user_moves") or []
    }
    board = chess.Board()
    candidates = []
    for index, san in enumerate(trap.get("full_sequence") or []):
        before = board.fen()
        try:
            uci = _move_uci(board, str(san))
            board.push_uci(uci)
        except (ValueError, AssertionError):
            raise LessonUnavailable("Trap lesson contains an invalid move")
        if index not in expected_indexes:
            continue
        candidates.append({
            "item_id": f"{content_id}:{mode}:{index}",
            "fen": before,
            "orientation": trap.get("user_color") or "white",
            "prompt": (
                "What move answers the danger?"
                if mode == "avoidance"
                else "What move continues the line?"
            ),
            "reason_prompt": "What matters most before you move?",
            "reason_choices": _reason_choices("trap"),
            "_expected_reason": "answers_threat",
            "_expected_san": str(san),
            "_expected_uci": uci,
            "_on_correct": str(
                trap.get("how_to_avoid")
                if mode == "avoidance"
                else trap.get("success_message")
                or trap.get("why_it_works")
                or ""
            ),
            "_on_wrong": str(
                trap.get("danger")
                or "Find the immediate threat before starting your own plan."
            ),
            "source": "canonical_trap",
            "source_ref": str(trap.get("content_id") or content_id),
            "board_verified": True,
            "_help_squares": list(trap.get("key_squares") or []),
        })
    if not candidates:
        raise LessonUnavailable("Trap lesson has no playable moves")
    for index, item in enumerate(candidates):
        item["stage"] = _stage(index, len(candidates))

    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "trap",
        "id": content_id,
        "skill_id": _lesson_skill_id("trap", content_id, params),
        "title": str(trap.get("name") or content_id.replace("_", " ").title()),
        "rule": str(trap.get("how_to_avoid") or trap.get("description") or ""),
        "intro": str(trap.get("danger") or trap.get("description") or ""),
        "canonical_source": "backend/data/traps.json",
        "content_version": _content_version(trap),
        "items": candidates,
        "player_color": str(trap.get("user_color") or "white"),
        "mastery_capability": (
            "independent" if len(candidates) > 1 else "guided"
        ),
    }


def _trap_set_descriptor(
    content_id: str,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build one verified defensive decision per trap in an opening family."""
    from trick_library_service import get_traps_by_opening

    traps = get_traps_by_opening(content_id)
    if not traps:
        raise LessonUnavailable("Verified trap family not found")

    items = []
    included = []
    seen_positions = set()
    for trap in traps:
        trap_key = str(trap.get("key") or "")
        if not trap_key:
            continue
        try:
            descriptor = _trap_descriptor(
                trap_key,
                {**dict(params), "mode": "avoidance"},
            )
        except LessonUnavailable:
            continue
        # The first user decision is the moment the defender must recognise.
        # Later moves in the authored line explain the consequence, but they do
        # not become extra mastery credit for the same trap.
        item = dict(descriptor["items"][0])
        position_key = " ".join(str(item["fen"]).split()[:4])
        if position_key in seen_positions:
            continue
        seen_positions.add(position_key)
        item["prompt"] = f"What move avoids {descriptor['title']}?"
        item["source"] = "canonical_trap_family"
        items.append(item)
        included.append({
            "key": trap_key,
            "content_id": trap.get("content_id"),
            "content_version": descriptor["content_version"],
        })

    if not items:
        raise LessonUnavailable("Trap family has no verified defensive positions")
    for index, item in enumerate(items):
        item["stage"] = _stage(index, len(items))

    family_name = str(content_id or "").replace("-", " ").replace("_", " ").title()
    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "trap_set",
        "id": content_id,
        "skill_id": _lesson_skill_id("trap_set", content_id, params),
        "title": f"{family_name} trap defenses",
        "rule": "Find the opponent's immediate threat before starting your own plan.",
        "intro": (
            "These are different dangers from the same opening family. "
            "Recognise each threat, then choose the verified defensive move."
        ),
        "canonical_source": "backend/data/traps.json",
        "content_version": _content_version({
            "family": content_id,
            "traps": included,
        }),
        "items": items,
        "mastery_capability": (
            "independent" if len(items) > 1 else "guided"
        ),
    }


def _endgame_descriptor(content_id: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    from services.endgame_theory_service import get_lesson

    parts = str(content_id or "").split("/", 1)
    if len(parts) != 2:
        raise LessonUnavailable("Endgame lesson id must include category and lesson")
    category_key, lesson_key = parts
    lesson = get_lesson(category_key, lesson_key)
    if not lesson:
        raise LessonUnavailable("Verified endgame lesson not found")
    items = []
    for position in lesson.get("positions") or []:
        index = int(position["index"])
        items.append({
            "item_id": f"{content_id}:{index}",
            "fen": position["fen"],
            "orientation": position.get("side_to_move") or "white",
            "prompt": position.get("prompt") or "What move works here?",
            "reason_prompt": "Why does this move fit the position?",
            "reason_choices": _reason_choices("endgame"),
            "_expected_reason": "uses_rule",
            "stage": "transfer" if position.get("stage") == "independent_proof" else "guide",
            "source": "canonical_endgame",
            "source_ref": f"{content_id}:{index}",
            "board_verified": True,
            "_help_squares": list(position.get("square_corners") or []),
            "_endgame_position_index": index,
        })
    if not items:
        raise LessonUnavailable("Endgame lesson has no verified positions")
    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "endgame",
        "id": content_id,
        "skill_id": _lesson_skill_id("endgame", content_id, params),
        "title": lesson["name"],
        "rule": lesson["rule"],
        "intro": str(lesson.get("intro") or lesson.get("description") or ""),
        "canonical_source": lesson["canonical_source"],
        "content_version": _content_version(lesson),
        "items": items,
        "category_key": category_key,
        "lesson_key": lesson_key,
        "mastery_capability": "independent",
    }


async def _concept_descriptor(
    db,
    user_id: str,
    content_id: str,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    with TACTICAL_PATH.open("r", encoding="utf-8") as handle:
        patterns = json.load(handle)
    pattern_key = (
        "undefended_piece"
        if content_id in ("piece_safety", "piece_safety_simple_hang")
        else content_id
    )
    pattern = patterns.get(pattern_key)
    if not isinstance(pattern, Mapping):
        raise LessonUnavailable("Verified concept lesson not found")

    blind_diagnostic = str(params.get("mode") or "") == "blind_diagnostic"
    if blind_diagnostic:
        from services.destination_safety_detector import FACT_VERSION
        from services.verified_puzzle_runtime import resolve_verified_puzzle

        cursor = db.move_observations.find(
            {
                "user_id": user_id,
                "schema_version": {"$gte": 18},
                "destination_safety_exact.version": FACT_VERSION,
                "destination_safety_exact.fires": True,
            },
            {
                "_id": 0,
                "game_id": 1,
                "move_number": 1,
                "fen_before": 1,
                "destination_safety_exact": 1,
                "derived_at": 1,
            },
        ).sort("derived_at", -1).limit(200)
        observations = await cursor.to_list(length=200)
        own = [{
            "puzzle_id": f"{row.get('game_id')}_m{row.get('move_number')}",
            "source_game_id": row.get("game_id"),
            "fen": row.get("fen_before"),
        } for row in observations if row.get("game_id") and row.get("move_number") is not None]
        candidates = []
        pair = None
        for supplied in own:
            resolved = await resolve_verified_puzzle(
                db,
                str(supplied.get("puzzle_id") or ""),
                user_id=user_id,
            )
            if not resolved:
                continue
            candidate = _blind_diagnostic_candidate(supplied, resolved)
            if candidate:
                candidates.append(candidate)
                pair = select_blind_diagnostic_pair(candidates)
                if pair:
                    break
        if not pair:
            raise LessonUnavailable(
                "Two independent verified positions are not available yet"
            )
        selected = pair["items"]
    else:
        from services.puzzle_extraction_service import get_pattern_training_puzzles

        requested = max(1, min(int(params.get("limit") or 5), 5))
        supply = await get_pattern_training_puzzles(
            db,
            user_id,
            "piece_safety" if pattern_key == "undefended_piece" else pattern_key,
            requested,
            private=True,
        )
        own = [
            item for item in (supply.get("own_puzzles") or [])
            if not item.get("already_solved")
        ]
        pair = None
        selected = (own + list(supply.get("community_puzzles") or []))[:requested]
    items = []
    seen_fens = set()
    for item in selected:
        if not item.get("fen") or not item.get("puzzle_id"):
            continue
        normalized_fen = " ".join(str(item["fen"]).split()[:4])
        if normalized_fen in seen_fens:
            continue
        seen_fens.add(normalized_fen)
        board = chess.Board(item["fen"])
        attacked_piece_squares = [
            chess.square_name(square)
            for square, piece in board.piece_map().items()
            if piece.color == board.turn
            and board.is_attacked_by(not board.turn, square)
        ]
        item_number = len(items) + 1
        reason_fields = (
            {}
            if blind_diagnostic
            else {
                "reason_prompt": "What did you check before choosing the move?",
                "reason_choices": _reason_choices("concept"),
                "_expected_reason": "keeps_piece_safe",
            }
        )
        items.append({
            "item_id": (
                f"diagnostic-position-{item_number}"
                if blind_diagnostic
                else str(item.get("puzzle_id"))
            ),
            "fen": item["fen"],
            "orientation": (
                "black" if str(item["fen"]).split()[1] == "b" else "white"
            ),
            "prompt": "Which move keeps every piece safe?",
            **reason_fields,
            "_help_squares": (
                [item.get("moved_origin")]
                if blind_diagnostic and item.get("moved_origin")
                else attacked_piece_squares
            ),
            "stage": "",
            "source": (
                "own_game"
                if blind_diagnostic
                else str(item.get("source") or "verified_practice")
            ),
            "source_ref": str(item.get("source_game_id") or item.get("puzzle_id")),
            "board_verified": True,
            "_puzzle_id": str(item["puzzle_id"]),
            "_puzzle_evaluator": True,
            "_diagnostic_quality_id": item.get("quality_id") if blind_diagnostic else None,
            "_detector_version": item.get("detector_version") if blind_diagnostic else None,
            "_normalized_fen": item.get("normalized_fen") if blind_diagnostic else None,
            "_moved_piece": item.get("moved_piece") if blind_diagnostic else None,
        })
    if not items:
        raise LessonUnavailable("No verified practice positions are available yet")
    for index, item in enumerate(items):
        item["stage"] = (
            "diagnose" if blind_diagnostic and index == 0
            else "transfer" if blind_diagnostic
            else _stage(index, len(items))
        )

    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "concept",
        "id": content_id,
        "skill_id": _lesson_skill_id("concept", content_id, params),
        "title": str(pattern.get("name") or "Piece safety"),
        "rule": str(pattern.get("prevention") or pattern.get("rule") or ""),
        "intro": str(pattern.get("explanation") or ""),
        "canonical_source": TACTICAL_SOURCE,
        "content_version": str(
            (patterns.get("_meta") or {}).get("version")
            or _content_version(pattern)
        ),
        "items": items,
        "mastery_capability": (
            "independent" if len(items) > 1 else "guided"
        ),
        "delivery_mode": "blind_diagnostic" if blind_diagnostic else "lesson",
        "diagnostic_version": "home_replay_diagnostic.v2" if blind_diagnostic else None,
        "pair_fingerprint": pair.get("fingerprint") if pair else None,
    }


async def resolve_personalized_lesson(
    db,
    user_id: str,
    *,
    content_kind: str,
    content_id: str,
    params: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    kind = str(content_kind or "").strip().lower()
    lesson_id = str(content_id or "").strip()
    options = params or {}
    if kind == "opening":
        return _opening_descriptor(lesson_id, options)
    if kind == "trap":
        return _trap_descriptor(lesson_id, options)
    if kind == "trap_set":
        return _trap_set_descriptor(lesson_id, options)
    if kind == "endgame":
        return _endgame_descriptor(lesson_id, options)
    if kind == "concept":
        return await _concept_descriptor(db, user_id, lesson_id, options)
    raise LessonUnavailable(f"Unsupported lesson kind: {kind}")


def public_lesson_descriptor(descriptor: Mapping[str, Any]) -> Dict[str, Any]:
    items = []
    for raw in descriptor.get("items") or []:
        item = {
            key: value
            for key, value in raw.items()
            if not str(key).startswith("_")
        }
        items.append(item)
    return {
        key: value
        for key, value in descriptor.items()
        if key != "items" and not str(key).startswith("_")
    } | {"items": items}


def _parse_move(fen: str, supplied: str) -> Optional[chess.Move]:
    board = chess.Board(fen)
    text = str(supplied or "").strip()
    try:
        move = chess.Move.from_uci(text.lower())
        return move if move in board.legal_moves else None
    except ValueError:
        try:
            return board.parse_san(text)
        except (ValueError, AssertionError):
            return None


async def grade_personalized_move(
    descriptor: Mapping[str, Any],
    item: Mapping[str, Any],
    supplied_move: str,
    *,
    db=None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    kind = descriptor["kind"]
    if kind == "endgame":
        from services.endgame_theory_service import check_move

        result = check_move(
            descriptor["category_key"],
            descriptor["lesson_key"],
            int(item["_endgame_position_index"]),
            supplied_move,
        )
        return {
            "correct": bool(result.get("correct")),
            "feedback": (
                result.get("on_correct")
                if result.get("correct")
                else result.get("on_wrong")
            ),
            "answer_san": result.get("correct_move_san"),
            "answer_uci": result.get("correct_move_uci"),
            "grader_version": "endgame_theory_service.v1",
        }
    if item.get("_diagnostic_quality_id"):
        from coach_play.coach_blunder_guard import (
            ONE_MOVE_FLOOR_CP,
            material_hung_after,
        )
        from services.destination_safety_detector import (
            QUALITY_ID,
            grade_destination_safety_candidate,
        )

        if item.get("_diagnostic_quality_id") != QUALITY_ID:
            return {
                "correct": False,
                "target_result": "unmeasured",
                "soundness": {"status": "unmeasured", "reason": "unsupported_proof_family"},
                "feedback": "I cannot verify this position safely yet.",
                "answer_san": None,
                "answer_uci": None,
                "grader_version": "home_replay_diagnostic.unavailable",
            }
        target = grade_destination_safety_candidate(item["fen"], supplied_move)
        parsed = _parse_move(item["fen"], supplied_move)
        if parsed is None:
            return {
                "correct": False,
                "target_result": "unmeasured",
                "soundness": {"status": "unmeasured", "reason": "illegal_move"},
                "feedback": "That move is not legal here.",
                "answer_san": None,
                "answer_uci": None,
                "grader_version": "home_replay_diagnostic.v2",
            }

        board = chess.Board(item["fen"])
        immediate_loss, _ = material_hung_after(board, parsed)
        from services.puzzle_move_evaluator import evaluate_puzzle_move

        engine_grade = await evaluate_puzzle_move(
            item["fen"],
            parsed.uci(),
            depth=14,
        )
        if engine_grade.get("quality") == "invalid" or engine_grade.get("error"):
            soundness = {"status": "unmeasured", "reason": "engine_unavailable"}
        elif immediate_loss >= ONE_MOVE_FLOOR_CP:
            soundness = {"status": "serious_problem", "reason": "immediate_material_loss"}
        elif engine_grade.get("quality") in {"mistake", "blunder"}:
            soundness = {"status": "serious_problem", "reason": "move_loses_ground"}
        else:
            soundness = {"status": "sound", "reason": "verified_acceptable"}

        target_status = str(target.get("status") or "unmeasured")
        if target_status == "pass" and soundness["status"] == "sound":
            feedback = "You kept the moved piece safe, and the move holds up."
        elif target_status == "pass":
            feedback = (
                "You kept the moved piece safe. "
                "There is a separate problem with the move that we should examine."
            )
        elif target_status == "fail":
            feedback = "The piece can still be won on its new square."
        else:
            feedback = "This move does not let me measure the decision fairly."
        return {
            "correct": target_status == "pass",
            "target_result": target_status,
            "target_reason": target.get("reason"),
            "soundness": soundness,
            "feedback": feedback,
            "answer_san": None,
            "answer_uci": None,
            "grader_version": "home_replay_diagnostic.v2",
        }

    if item.get("_puzzle_evaluator"):
        if db is None or not item.get("_puzzle_id"):
            return {
                "correct": False,
                "feedback": "This position is still being checked.",
                "answer_san": None,
                "answer_uci": None,
                "grader_version": "verified_puzzle_admission.unavailable",
            }
        from services.verified_puzzle_runtime import (
            grade_resolved_puzzle,
            resolve_verified_puzzle,
        )

        resolved = await resolve_verified_puzzle(
            db,
            str(item["_puzzle_id"]),
            user_id=user_id,
        )
        result = (
            grade_resolved_puzzle(resolved, supplied_move)
            if resolved
            else {"quality": "invalid", "feedback": "This position is still being checked."}
        )
        return {
            "correct": bool(result.get("correct")),
            "feedback": result.get("feedback"),
            "answer_san": result.get("best_move_san"),
            "answer_uci": result.get("best_move_uci"),
            "grader_version": "verified_puzzle_admission.v2",
        }

    parsed = _parse_move(item["fen"], supplied_move)
    correct = bool(parsed and parsed.uci() == item.get("_expected_uci"))
    return {
        "correct": correct,
        "feedback": item.get("_on_correct") if correct else item.get("_on_wrong"),
        "answer_san": item.get("_expected_san"),
        "answer_uci": item.get("_expected_uci"),
        "grader_version": "canonical_line_match.v1",
    }
