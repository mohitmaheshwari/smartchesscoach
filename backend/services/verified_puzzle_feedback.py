"""One deterministic coaching voice for every verified puzzle attempt.

The renderer consumes only the frozen board, accepted move and the two proof
fact sets stored at admission time.  It never calls an engine, model or network
service, and names an exact fact only when its Caption surface is authorized.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import chess

from services.detector_quality import QualitySurface, is_authorized


def _first_fact(admission: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    facts = admission.get(key) or ()
    return facts[0] if facts and isinstance(facts[0], Mapping) else {}


def _legal_move(board: chess.Board, raw: Any) -> Optional[chess.Move]:
    try:
        move = chess.Move.from_uci(str(raw or "").lower())
        return move if move in board.legal_moves else None
    except ValueError:
        return None


def _san(board: chess.Board, raw: Any) -> str:
    move = _legal_move(board, raw)
    return board.san(move) if move else str(raw or "the move")


def _move_effect(board: chess.Board, raw: Any) -> str:
    move = _legal_move(board, raw)
    if move is None:
        return "It is the move this position asks you to calculate."
    san = board.san(move)
    moving = board.piece_at(move.from_square)
    captured_square = move.to_square
    if board.is_en_passant(move):
        captured_square += -8 if board.turn == chess.WHITE else 8
    captured = board.piece_at(captured_square) if board.is_capture(move) else None
    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        king_square = after.king(after.turn)
        king_text = chess.square_name(king_square) if king_square is not None else "its square"
        return f"{san} gives checkmate: the king on {king_text} has no legal reply."
    if captured is not None:
        return (
            f"{san} takes the {chess.piece_name(captured.piece_type)} "
            f"on {chess.square_name(captured_square)}."
        )
    if move.promotion:
        return f"{san} promotes the pawn on {chess.square_name(move.to_square)}."
    if board.is_castling(move):
        return f"{san} moves the king to safety and brings a rook into play."
    if after.is_check():
        king_square = after.king(after.turn)
        king_text = chess.square_name(king_square) if king_square is not None else "its square"
        return f"{san} checks the king on {king_text}, so the opponent must answer."
    piece_name = chess.piece_name(moving.piece_type) if moving else "piece"
    return (
        f"{san} moves the {piece_name} from {chess.square_name(move.from_square)} "
        f"to {chess.square_name(move.to_square)}."
    )


def _opening_context(
    admission: Mapping[str, Any], best_san: str
) -> tuple[str, str]:
    fact = _first_fact(admission, "detector_facts")
    opening_key = str(fact.get("source_ref") or admission.get("concept_id") or "")
    opening_key = opening_key.removeprefix("opening:")
    try:
        from services.opening_theory_json_service import (
            get_lesson_move_steps,
            get_opening_theory,
        )

        opening = get_opening_theory(opening_key) or {}
        name = str(opening.get("name") or opening_key.replace("_", " ").title())
        index = fact.get("decision_ply")
        steps = get_lesson_move_steps(opening_key)
        step = steps[int(index)] if index is not None and int(index) < len(steps) else {}
        reason = str(fact.get("explanation") or step.get("explanation") or "").strip()
        if not reason:
            reason = f"{best_san} follows the exact {name} position you studied."
        rule_pool = opening.get("golden_rules") or opening.get("common_learnings") or ()
        rule = str(fact.get("lesson_rule") or (rule_pool[0] if rule_pool else "")).strip() or (
            "In the opening, know what your move prepares; do not memorize it without the reason."
        )
        return f"In this {name} position, {reason}", rule
    except (ImportError, TypeError, ValueError, IndexError):
        return (
            f"{best_san} matches the exact opening position you studied.",
            "In the opening, know what your move prepares; do not memorize it without the reason.",
        )


def _trap_context(admission: Mapping[str, Any], best_san: str) -> tuple[str, str]:
    fact = _first_fact(admission, "detector_facts")
    trap_key = str(fact.get("source_ref") or "")
    mode = str(fact.get("mode") or "")
    try:
        from trick_library_service import get_trap_by_key

        trap = get_trap_by_key(trap_key) or {}
        name = str(trap.get("name") or trap_key.replace("_", " ").title())
        reason = str(
            trap.get("how_to_avoid") if mode == "avoidance" else
            trap.get("danger") or trap.get("description") or ""
        ).strip()
        if not reason:
            reason = f"{best_san} is the exact move that makes this line work."
        rule = (
            "Before developing, name the opponent's immediate threat and answer it first."
            if mode == "avoidance"
            else "Before following a trap, check that the opponent has actually made the move that allows it."
        )
        return (f"This is the {name}: {reason}", rule)
    except (ImportError, TypeError):
        rule = (
            "Before developing, name the opponent's immediate threat and answer it first."
            if mode == "avoidance"
            else "Before following a trap, check that the opponent has actually made the move that allows it."
        )
        return (f"{best_san} is the exact move required in this trap position.", rule)


def _endgame_context(
    admission: Mapping[str, Any], best_san: str, correct: bool, alternative: bool
) -> tuple[str, str]:
    fact = _first_fact(admission, "verifier_facts")
    content_id = str(fact.get("content_id") or "")
    try:
        category_key, lesson_key = content_id.split("/", 1)
        from services.endgame_theory_service import get_verified_lesson_data

        lesson = get_verified_lesson_data(category_key, lesson_key) or {}
        name = str(lesson.get("name") or lesson_key.replace("_", " ").title())
        index = int(fact.get("position_index"))
        position = (lesson.get("positions") or ())[index]
        rule = str(position.get("rule_reminder") or lesson.get("rule") or "").strip()
        idea = str(position.get("idea") or "").strip()
        reason = idea or f"{best_san} is the exact move for this {name} position."
        return reason, rule or "In an endgame, calculate the full king route or pawn race before pushing."
    except (ImportError, TypeError, ValueError, KeyError, IndexError):
        return (
            f"{best_san} is the exact move for this endgame position.",
            "In an endgame, calculate the full king route or pawn race before pushing.",
        )


def _specific_context(
    board: chess.Board,
    admission: Mapping[str, Any],
    focus_uci: str,
    *,
    correct: bool,
    alternative: bool,
) -> tuple[str, str]:
    concept = str(admission.get("concept_id") or "")
    fact = _first_fact(admission, "verifier_facts")
    best_san = _san(board, focus_uci)

    if concept.startswith("opening:"):
        return _opening_context(admission, best_san)
    if concept.startswith("trap:"):
        return _trap_context(admission, best_san)
    if concept.startswith("endgame:"):
        return _endgame_context(admission, best_san, correct, alternative)
    if concept == "piece_safety.simple_hang":
        piece, square = fact.get("piece"), fact.get("square")
        return (
            f"The original move left the {piece} on {square} available to be taken; {best_san} avoids that loss.",
            "After choosing a move, scan every piece you own and ask what the opponent can capture.",
        )
    if concept == "piece_safety.trapped_piece":
        piece, square = fact.get("piece"), fact.get("square")
        return (
            f"After the original move, every immediate move by the {piece} on {square} still loses material in the capture sequence we can see. {best_san} avoids that problem.",
            "Before placing a piece near the edge, count its safe escape squares after the opponent replies.",
        )
    if concept.startswith("tactic.") and "fork" in concept:
        piece = fact.get("forking_piece") or "piece"
        square = fact.get("fork_square") or "its square"
        targets = ", ".join(str(item) for item in (fact.get("targets") or ()))
        return (
            f"{best_san} puts the {piece} on {square}, attacking two targets on {targets}.",
            "Before settling on a move, scan every legal check and capture for one move that attacks two pieces.",
        )
    if concept in {"tactic.pin", "tactic.skewer"}:
        kind = str(fact.get("kind") or concept.rsplit(".", 1)[-1])
        front, rear = fact.get("front_square"), fact.get("rear_square")
        if kind == "pin":
            why = f"After {best_san}, the piece on {front} cannot move freely without exposing the piece on {rear}."
        else:
            why = f"After {best_san}, the piece on {front} must answer first, leaving the piece on {rear} behind it."
        return why, "When two pieces share a line, examine the front piece and what sits behind it."
    if concept == "tactic.discovered_attack":
        slider, slider_square = fact.get("slider_piece"), fact.get("slider_square")
        target, target_square = fact.get("target_piece"), fact.get("target_square")
        vacated = fact.get("vacated_square")
        return (
            f"{best_san} clears {vacated}, uncovering the {slider} on {slider_square} against the {target} on {target_square}.",
            "Whenever one of your pieces moves, re-scan the rook, bishop and queen lines it opens.",
        )
    if concept == "tactic.removal_of_defender":
        defender, defender_square = fact.get("defender_piece"), fact.get("defender_square")
        target, target_square = fact.get("target_piece"), fact.get("target_square")
        return (
            f"{best_san} removes the {defender} on {defender_square}, the only guard of the {target} on {target_square}.",
            "Before attacking a piece, identify its last defender; removing that guard may make the target fall.",
        )
    if concept == "tactic.free_piece":
        piece, square = fact.get("captured_piece"), fact.get("captured_square")
        return (
            f"{best_san} takes the {piece} on {square}, and the opponent has no legal recapture.",
            "Before choosing a plan, scan every legal capture and count the recaptures.",
        )
    if concept == "tactic.back_rank_mate":
        piece, square, king = fact.get("mating_piece"), fact.get("mating_square"), fact.get("king_square")
        return (
            f"{best_san} puts the {piece} on {square} with mate; the king on {king} has no legal escape.",
            "Before any quiet move, examine every legal check and count the king's escape squares.",
        )
    if concept in {"tactic.forced_mate", "tactic.missed_mate", "tactic.mate_in_one"}:
        return (
            f"{best_san} starts a forced line that ends in checkmate.",
            "Before any quiet move, examine every legal check and count the king's escape squares.",
        )
    return (
        _move_effect(board, focus_uci),
        "Before you commit, calculate the opponent's strongest legal reply.",
    )


def build_verified_puzzle_feedback(
    puzzle: Mapping[str, Any],
    played_uci: str,
    *,
    correct: bool,
    primary_uci: Optional[str] = None,
) -> Dict[str, str]:
    """Return a concrete WHY plus a reusable habit from frozen evidence."""
    admission = puzzle.get("verified_admission") or {}
    board = chess.Board(str(puzzle.get("fen")))
    primary = str(primary_uci or puzzle.get("best_move_uci") or "")
    focus = played_uci if correct else primary
    alternative = bool(correct and primary and played_uci != primary)
    played_san = _san(board, played_uci)
    focus_san = _san(board, focus)
    status = str(admission.get("status") or "generic")

    if status == "specific":
        why, remember = _specific_context(
            board, admission, focus, correct=correct, alternative=alternative
        )
    elif (
        status == "broad"
        and admission.get("caption_concept_id")
        and admission.get("quality_id")
        and is_authorized(
            str(admission["quality_id"]), QualitySurface.CAPTION
        )
    ):
        caption_admission = dict(admission)
        caption_admission["concept_id"] = admission["caption_concept_id"]
        why, remember = _specific_context(
            board,
            caption_admission,
            focus,
            correct=correct,
            alternative=alternative,
        )
    else:
        why = _move_effect(board, focus)
        remember = "Before you commit, calculate the opponent's strongest legal reply."

    if correct:
        lead = f"Yes — {played_san}."
        behavior = "Name the board clue you used, then look for the same clue in your next game."
    else:
        lead = f"Not this time. The move to compare with yours is {focus_san}."
        behavior = "Try the position again and say the opponent's strongest reply before moving."
    if puzzle.get("source") == "your_game":
        lead = f"This came from your own game. {lead}"
    return {
        "feedback": f"{lead} {why} {remember}".strip(),
        "why": why,
        "remember": remember,
        "behavior": behavior,
        "source": "verified_deterministic",
    }
