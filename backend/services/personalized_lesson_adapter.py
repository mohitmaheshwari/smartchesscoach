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


ADAPTER_SCHEMA_VERSION = "personalized_lesson_adapter.v2"
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


def _ordered_reason_choices(
    choices: list[Dict[str, str]],
    *,
    expected_id: str,
    position_id: str,
) -> list[Dict[str, str]]:
    """Vary answer order deterministically so “click first” never works."""
    ordered = sorted(
        choices,
        key=lambda choice: hashlib.sha256(
            f"{position_id}:{choice.get('id')}".encode("utf-8")
        ).hexdigest(),
    )
    if len(ordered) > 1 and ordered[0].get("id") == expected_id:
        ordered[0], ordered[1] = ordered[1], ordered[0]
    return ordered


def _content_version(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        {
            "adapter_schema": ADAPTER_SCHEMA_VERSION,
            "canonical_content": value,
        },
        sort_keys=True,
        default=str,
    ).encode("utf-8")
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


def _stage(index: int, total: int) -> str:
    if total <= 1:
        return "guide"
    if index == total - 1:
        return "transfer"
    if index == 0:
        return "guide"
    return "recall"


def _move_uci(board: chess.Board, san: str) -> str:
    return board.parse_san(str(san)).uci()


def _piece_safety_diagnosis(
    fen: str,
    best_move_san: str,
) -> Optional[Dict[str, Any]]:
    """Derive one teachable danger from the shared piece-safety geometry.

    `mission_scoreboard.find_hanging_pieces` remains the owner of what counts
    as an undefended attacked piece. This adapter only checks that the known
    solution actually resolves that board fact and shapes it for a lesson.
    """
    from services.mission_scoreboard import find_hanging_pieces

    try:
        board = chess.Board(fen)
        own_is_white = board.turn == chess.WHITE
        hanging = find_hanging_pieces(fen, own_is_white)
        if len(hanging) != 1:
            return None
        problem = dict(hanging[0])
        problem_square = chess.parse_square(problem["square"])
        move = board.parse_san(str(best_move_san))
        before_hanging = {item["square"] for item in hanging}
        attacker_squares = sorted(
            board.attackers(not board.turn, problem_square)
        )
        attacker_labels = []
        for square in attacker_squares:
            piece = board.piece_at(square)
            if piece:
                attacker_labels.append(
                    f"{chess.piece_name(piece.piece_type)} on "
                    f"{chess.square_name(square)}"
                )

        board.push(move)
        after_hanging = {
            item["square"]
            for item in find_hanging_pieces(board.fen(), own_is_white)
        }
        if move.from_square == problem_square:
            resolved = chess.square_name(move.to_square) not in after_hanging
        else:
            resolved = problem["square"] not in after_hanging
        new_hangs = after_hanging - (before_hanging - {problem["square"]})
        if not resolved or new_hangs:
            return None

        return {
            **problem,
            "attacker_squares": [
                chess.square_name(square) for square in attacker_squares
            ],
            "attacker_labels": attacker_labels,
            "side_to_move": "White" if own_is_white else "Black",
        }
    except (KeyError, TypeError, ValueError, AssertionError):
        return None


def _piece_safety_reason_choices(
    board: chess.Board,
    problem: Mapping[str, Any],
) -> list[Dict[str, str]]:
    problem_square = str(problem["square"])
    expected = {
        "id": f"piece_in_danger:{problem_square}",
        "label": (
            f"My {problem['piece_name']} on {problem_square} can be taken."
        ),
    }
    alternatives = []
    own_color = board.turn
    opponent = not own_color
    candidates = []
    for square, piece in board.piece_map().items():
        square_name = chess.square_name(square)
        if (
            piece.color != own_color
            or piece.piece_type == chess.KING
            or square_name == problem_square
        ):
            continue
        candidates.append((
            0 if board.attackers(opponent, square) else 1,
            chess.square_distance(square, chess.parse_square(problem_square)),
            square_name,
            chess.piece_name(piece.piece_type),
        ))
    for _, _, square_name, piece_name in sorted(candidates)[:2]:
        alternatives.append({
            "id": f"piece_in_danger:{square_name}",
            "label": f"My {piece_name} on {square_name} can be taken.",
        })
    return [
        expected,
        *alternatives,
        {"id": "not_sure", "label": "I am not sure yet."},
    ]


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
        item_id = f"{resolved}:{index}"
        candidates.append({
            "item_id": item_id,
            "fen": before,
            "orientation": player_color,
            "prompt": "What move continues your plan here?",
            "reason_prompt": "Why does your move belong here?",
            "reason_choices": _ordered_reason_choices(
                _reason_choices("opening"),
                expected_id="continues_plan",
                position_id=item_id,
            ),
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
        "skill_id": str(params.get("skill_id") or resolved),
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
        item_id = f"{content_id}:{mode}:{index}"
        candidates.append({
            "item_id": item_id,
            "fen": before,
            "orientation": trap.get("user_color") or "white",
            "prompt": (
                "What move answers the danger?"
                if mode == "avoidance"
                else "What move continues the line?"
            ),
            "reason_prompt": "What matters most before you move?",
            "reason_choices": _ordered_reason_choices(
                _reason_choices("trap"),
                expected_id="answers_threat",
                position_id=item_id,
            ),
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
        "skill_id": str(params.get("skill_id") or content_id),
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
        item_id = f"{content_id}:{index}"
        items.append({
            "item_id": item_id,
            "fen": position["fen"],
            "orientation": position.get("side_to_move") or "white",
            "prompt": position.get("prompt") or "What move works here?",
            "reason_prompt": "Why does this move fit the position?",
            "reason_choices": _ordered_reason_choices(
                _reason_choices("endgame"),
                expected_id="uses_rule",
                position_id=item_id,
            ),
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
        "skill_id": str(params.get("skill_id") or content_id),
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

    from services.puzzle_extraction_service import get_pattern_training_puzzles

    requested = max(1, min(int(params.get("limit") or 5), 5))
    supply = await get_pattern_training_puzzles(
        db,
        user_id,
        "piece_safety" if pattern_key == "undefended_piece" else pattern_key,
        max(10, requested * 4),
    )
    own = [
        item for item in (supply.get("own_puzzles") or [])
        if not item.get("already_solved")
    ]
    selected = (own + list(supply.get("community_puzzles") or []))[:requested]
    items = []
    seen_fens = set()
    for item in selected:
        if not item.get("fen") or not item.get("best_move_san"):
            continue
        normalized_fen = " ".join(str(item["fen"]).split()[:4])
        if normalized_fen in seen_fens:
            continue
        seen_fens.add(normalized_fen)
        board = chess.Board(item["fen"])
        diagnosis = (
            _piece_safety_diagnosis(item["fen"], item["best_move_san"])
            if pattern_key == "undefended_piece"
            else None
        )
        if pattern_key == "undefended_piece" and not diagnosis:
            continue
        problem_square = str((diagnosis or {}).get("square") or "")
        problem_piece = str((diagnosis or {}).get("piece_name") or "piece")
        attackers = list((diagnosis or {}).get("attacker_labels") or [])
        attacker_text = (
            " and ".join(attackers)
            if attackers
            else "an opposing piece"
        )
        expected_reason = (
            f"piece_in_danger:{problem_square}"
            if diagnosis
            else "keeps_piece_safe"
        )
        reason_choices = (
            _piece_safety_reason_choices(board, diagnosis)
            if diagnosis
            else _reason_choices("concept")
        )
        reason_choices = _ordered_reason_choices(
            reason_choices,
            expected_id=expected_reason,
            position_id=str(item.get("puzzle_id")),
        )
        items.append({
            "item_id": str(item.get("puzzle_id")),
            "fen": item["fen"],
            "orientation": (
                "black" if str(item["fen"]).split()[1] == "b" else "white"
            ),
            "side_to_move": (
                diagnosis["side_to_move"]
                if diagnosis
                else ("White" if board.turn == chess.WHITE else "Black")
            ),
            "move_number": item.get("move_number"),
            "diagnosis_kind": (
                "piece_in_danger" if diagnosis else "concept_reason"
            ),
            "prompt": (
                "One of your pieces can be taken. Find a move that saves it "
                "or answers the attack."
                if diagnosis
                else "Which move fits this idea?"
            ),
            "reason_prompt": (
                "Which piece needs your attention first?"
                if diagnosis
                else "What did you check before choosing the move?"
            ),
            "reason_choices": reason_choices,
            "_expected_reason": expected_reason,
            "_problem_square": problem_square or None,
            "_problem_piece_name": problem_piece if diagnosis else None,
            "_attacker_labels": attackers,
            "_help_squares": (
                [problem_square, *(diagnosis.get("attacker_squares") or [])]
                if diagnosis
                else []
            ),
            "_help_message": (
                f"Your {problem_piece} on {problem_square} is attacked by "
                f"the {attacker_text}."
                if diagnosis
                else "Trace every attack before choosing your move."
            ),
            "_coach_question": (
                f"If you ignore your {problem_piece} on {problem_square}, "
                "what can your opponent take next?"
                if diagnosis
                else "What can your opponent take after your move?"
            ),
            "_on_correct": (
                f"Yes. You dealt with the attack on your {problem_piece} "
                f"on {problem_square}. Before starting your own idea, check "
                "whether an attacked piece needs help."
                if diagnosis
                else "You checked the board before moving."
            ),
            "_on_wrong": (
                f"That still leaves your {problem_piece} on {problem_square} "
                f"where the {attacker_text} can take it. Deal with that "
                "attack first."
                if diagnosis
                else "Check what your opponent can take next."
            ),
            "stage": "",
            "source": str(item.get("source") or "verified_practice"),
            "source_ref": str(
                item.get("source_game_id") or item.get("puzzle_id")
            ),
            "board_verified": True,
            "_expected_san": item["best_move_san"],
            "_puzzle_evaluator": True,
        })
        if len(items) >= requested:
            break
    if not items:
        raise LessonUnavailable("No verified practice positions are available yet")
    for index, item in enumerate(items):
        item["stage"] = _stage(index, len(items))

    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "kind": "concept",
        "id": content_id,
        "skill_id": str(params.get("skill_id") or content_id),
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
    if item.get("_puzzle_evaluator"):
        from services.puzzle_move_evaluator import evaluate_puzzle_move

        result = await evaluate_puzzle_move(
            fen=item["fen"],
            played_uci=supplied_move,
            known_best_san=item["_expected_san"],
        )
        if item.get("_problem_square"):
            board = chess.Board(item["fen"])
            parsed = _parse_move(item["fen"], supplied_move)
            exact_known_move = False
            resolves_lesson_goal = False
            if parsed:
                exact_known_move = bool(
                    parsed == board.parse_san(str(item["_expected_san"]))
                )
                diagnosis = _piece_safety_diagnosis(
                    item["fen"],
                    board.san(parsed),
                )
                resolves_lesson_goal = bool(
                    diagnosis
                    and diagnosis.get("square") == item.get("_problem_square")
                )
            engine_acceptable = bool(
                result.get("is_acceptable") or exact_known_move
            )
            correct = bool(resolves_lesson_goal and engine_acceptable)
            if correct:
                feedback = item.get("_on_correct")
            elif not resolves_lesson_goal:
                feedback = item.get("_on_wrong")
            else:
                feedback = (
                    f"You moved your {item.get('_problem_piece_name') or 'piece'} "
                    "out of danger, but this move creates a bigger problem. "
                    "A safe move must solve the immediate danger without "
                    "creating a new one."
                )
            return {
                "correct": correct,
                "feedback": feedback,
                "answer_san": (
                    result.get("best_move_san") or item.get("_expected_san")
                ),
                "answer_uci": None,
                "grader_version": "piece_safety_geometry+puzzle_move_evaluator.v1",
            }
        return {
            "correct": bool(result.get("is_acceptable")),
            "feedback": result.get("feedback"),
            "answer_san": result.get("best_move_san"),
            "answer_uci": None,
            "grader_version": "puzzle_move_evaluator.v1",
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
