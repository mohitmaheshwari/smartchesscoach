"""Resolve and grade every served puzzle from stored deterministic evidence."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import chess

from services.puzzle_extraction_service import verified_puzzle_admission_enforced
from services.verified_puzzle_admission import (
    ADMISSION_VERSION,
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import (
    build_imported_game_verdict,
    build_position_verdict,
)
from services.verified_puzzle_feedback import build_verified_puzzle_feedback


_PRIVATE_PUZZLE_FIELDS = frozenset({
    "accepted_moves",
    "acceptable_moves",
    "acceptable_moves_uci",
    "answer",
    "best_move",
    "best_move_san",
    "best_move_uci",
    "correct_move",
    "correct_move_san",
    "correct_move_uci",
    "pv",
    "pv_after_best",
    "pv_after_played",
    "solution",
    "solution_san",
    "solution_uci",
    "verified_admission",
})


def public_puzzle_payload(puzzle: Mapping[str, Any]) -> Dict:
    """Return the pre-attempt shape; answers and proof internals stay server-side."""
    def redact(value):
        if isinstance(value, Mapping):
            return {
                key: redact(child)
                for key, child in value.items()
                if key not in _PRIVATE_PUZZLE_FIELDS
                and not str(key).startswith("answer_")
            }
        if isinstance(value, (list, tuple)):
            return [redact(child) for child in value]
        return value

    return redact(dict(puzzle))


def _position_fen(raw: Any) -> Optional[str]:
    try:
        board = raw if isinstance(raw, chess.Board) else chess.Board(str(raw))
        return " ".join(board.fen().split()[:4])
    except (TypeError, ValueError):
        return None


def _move_number_matches(left: Any, right: Any) -> bool:
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return left == right


def find_move_evaluation(analysis: Mapping[str, Any], *, move_number=None, fen=None):
    wanted_fen = _position_fen(fen) if fen else None
    candidates = (
        ((analysis.get("stockfish_analysis") or {}).get("move_evaluations")) or []
    )
    for move in candidates:
        if move_number is not None and not _move_number_matches(
            move.get("move_number"), move_number
        ):
            continue
        if wanted_fen and _position_fen(move.get("fen_before")) != wanted_fen:
            continue
        return move
    return None


async def _resolve_imported(
    db,
    *,
    game_id: str,
    move_number=None,
    fen=None,
    user_id: Optional[str] = None,
) -> Optional[Dict]:
    game_query = {"game_id": game_id}
    if user_id:
        game_query["user_id"] = user_id
    game = await db.games.find_one(game_query, {"_id": 0})
    analysis_query = {"game_id": game_id}
    if user_id:
        analysis_query["user_id"] = user_id
    analysis = await db.game_analyses.find_one(analysis_query, {"_id": 0})
    if not game or not analysis:
        return None
    move = find_move_evaluation(analysis, move_number=move_number, fen=fen)
    if not move:
        return None
    verdict = build_imported_game_verdict(
        game=game,
        move_evaluation=move,
        broad_category=move.get("cognitive_gap") or None,
    )
    if verdict.status == AdmissionStatus.QUARANTINE:
        return None
    best_san = move.get("best_move_san") or move.get("best_move") or ""
    return {
        "puzzle_id": f"{game_id}_m{move.get('move_number')}",
        "fen": move.get("fen_before"),
        "best_move_san": best_san,
        "best_move_uci": move.get("best_move_uci"),
        "pattern_type": verdict.broad_category or "calculation_depth",
        "cp_loss": move.get("cp_loss"),
        "pv_after_best": move.get("pv_after_best") or [],
        "pv_after_played": move.get("pv_after_played") or [],
        "verified_admission": verdict.to_document(),
        "source": "your_game" if user_id else "imported_game",
    }


def _row_belongs_to_user(row: Mapping[str, Any], user_id: Optional[str]) -> bool:
    return bool(
        user_id
        and user_id in {
            str(row.get("shared_by") or ""),
            str(row.get("source_user_id") or ""),
            str(row.get("user_id") or ""),
        }
    )


async def _resolve_pool_row(
    db, row: Dict, *, user_id: Optional[str] = None
) -> Optional[Dict]:
    # Historic reviewer rejections are an explicit human-quality decision.
    # A new structural verdict may inform a later review, but cannot silently
    # override that decision or expose the row in the meantime.
    if row.get("approved") is False:
        return None
    verdict = row.get("verified_admission") or {}
    is_own = _row_belongs_to_user(row, user_id)
    # Imported-game rows are cheap to rebuild at answer time. Do this before
    # trusting the persisted verdict so changed source analysis, detector code,
    # or authorization cannot leave a stale row grading as current.
    source_game_id = row.get("source_game_id")
    if source_game_id and row.get("source_type") != "coach_session":
        imported = await _resolve_imported(
            db,
            game_id=str(source_game_id),
            move_number=row.get("move_number"),
            fen=row.get("fen"),
            user_id=user_id if is_own else None,
        )
        if imported:
            imported.update({
                "puzzle_id": row.get("position_id") or str(row.get("_id") or ""),
                "source": (
                    "your_game" if is_own else
                    row.get("source") or row.get("source_type") or "community"
                ),
            })
            return imported

    if stored_verdict_is_structurally_current(row):
        if verdict.get("status") == AdmissionStatus.QUARANTINE.value:
            return None
        result = dict(row)
        if is_own:
            result["source"] = "your_game"
        return result

    if verified_puzzle_admission_enforced():
        return None

    # Rollout-only compatibility for coach-session/legacy rows. This validates
    # the position and answer structurally but never promotes a specific label.
    evidence = {
        "fen_before": row.get("fen"),
        "move": row.get("user_move_san") or row.get("played_move")
        or row.get("best_move_san"),
        "best_move_san": row.get("best_move_san"),
        "best_move_uci": row.get("best_move_uci"),
        "cp_loss": row.get("cp_loss"),
        "pv_after_best": row.get("pv_after_best") or [],
        "pv_after_played": row.get("pv_after_played") or [],
    }
    structural = build_position_verdict(
        source_kind="legacy_pool",
        source_ref=str(row.get("position_id") or row.get("_id") or ""),
        move_evaluation=evidence,
        broad_category=None,
    )
    if structural.status == AdmissionStatus.QUARANTINE:
        return None
    result = dict(row)
    result["pattern_type"] = structural.broad_category or "calculation_depth"
    result["verified_admission"] = structural.to_document()
    return result


async def _resolve_lichess(db, puzzle_id: str) -> Optional[Dict]:
    raw_id = puzzle_id.removeprefix("lichess_")
    puzzle = await db.lichess_puzzles.find_one(
        {"puzzle_id": raw_id}, {"_id": 0}
    )
    if not puzzle:
        return None
    try:
        board = chess.Board(puzzle.get("fen"))
        moves = [chess.Move.from_uci(raw) for raw in (puzzle.get("moves") or [])]
        if len(moves) < 2 or moves[0] not in board.legal_moves:
            return None
        board.push(moves[0])
        solve_fen = board.fen()
        solution = moves[1:]
        for move in solution:
            if move not in board.legal_moves:
                return None
            board.push(move)
        first = solution[0]
        solve_board = chess.Board(solve_fen)
        first_san = solve_board.san(first)
    except (TypeError, ValueError):
        return None
    verdict = build_position_verdict(
        source_kind="lichess_import",
        source_ref=raw_id,
        move_evaluation={
            "fen_before": solve_fen,
            "move": first.uci(),
            "best_move_uci": first.uci(),
            "best_move_san": first_san,
            "pv_after_best": [move.uci() for move in solution[1:]],
        },
        broad_category=None,
    )
    if verdict.status == AdmissionStatus.QUARANTINE:
        return None
    return {
        "puzzle_id": puzzle_id,
        "fen": solve_fen,
        "best_move_san": first_san,
        "best_move_uci": first.uci(),
        "pattern_type": "calculation_depth",
        "pv_after_best": [move.uci() for move in solution[1:]],
        "verified_admission": verdict.to_document(),
        "source": "lichess",
    }


async def resolve_verified_puzzle(
    db, puzzle_id: str, *, user_id: Optional[str] = None
) -> Optional[Dict]:
    """Resolve a public puzzle id without trusting client FEN or labels."""
    if not puzzle_id:
        return None

    row = await db.community_training_positions.find_one(
        {"position_id": puzzle_id}, {"_id": 0}
    )
    if row:
        return await _resolve_pool_row(db, row, user_id=user_id)

    try:
        from bson import ObjectId

        oid = ObjectId(puzzle_id)
    except Exception:
        oid = None
    if oid is not None:
        row = await db.community_puzzles.find_one({"_id": oid})
        if row:
            return await _resolve_pool_row(db, row, user_id=user_id)

    if puzzle_id.startswith("lichess_"):
        return await _resolve_lichess(db, puzzle_id)

    if "_m" in puzzle_id:
        game_id, raw_move_number = puzzle_id.rsplit("_m", 1)
        try:
            move_number = int(raw_move_number)
        except ValueError:
            move_number = None
        if game_id and move_number is not None:
            return await _resolve_imported(
                db,
                game_id=game_id,
                move_number=move_number,
                user_id=user_id,
            )
    return None


def grade_resolved_puzzle(puzzle: Mapping[str, Any], played_uci: str) -> Dict:
    """Grade from the frozen accepted answer set; never call an engine."""
    verdict = puzzle.get("verified_admission") or {}
    if not stored_verdict_is_structurally_current(puzzle):
        return {"quality": "invalid", "feedback": "This puzzle needs verification."}
    if verdict.get("status") == AdmissionStatus.QUARANTINE.value:
        return {"quality": "invalid", "feedback": "This puzzle is not available."}
    try:
        board = chess.Board(str(puzzle.get("fen")))
        played = chess.Move.from_uci(played_uci)
        if played not in board.legal_moves:
            raise ValueError("illegal move")
    except (TypeError, ValueError):
        return {"quality": "invalid", "feedback": "That move is not legal here."}

    accepted = set(verdict.get("acceptable_moves_uci") or [])
    primary = puzzle.get("best_move_uci")
    if not primary and accepted:
        primary = sorted(accepted)[0]
    correct = played.uci() in accepted
    is_best = correct and played.uci() == primary
    is_acceptable = correct and not is_best
    played_san = board.san(played)
    best_san = puzzle.get("best_move_san") or ""
    coaching = build_verified_puzzle_feedback(
        puzzle,
        played.uci(),
        correct=correct,
        primary_uci=primary,
    )
    admission_status = verdict.get("status")
    # Persisted legacy labels are candidate metadata, not verified truth. Only
    # a BROAD/SPECIFIC admission has earned the right to name the weakness it
    # exercises. A GENERIC puzzle proves only its answer, so it stays neutral
    # and cannot reduce an arbitrary profile weakness after a correct solve.
    verified_pattern = (
        verdict.get("broad_category")
        if admission_status in {
            AdmissionStatus.SPECIFIC.value,
            AdmissionStatus.BROAD.value,
        }
        else None
    )
    return {
        "quality": "best" if is_best else ("excellent" if is_acceptable else "mistake"),
        "cp_loss": None,
        "is_best": is_best,
        "is_acceptable": is_acceptable,
        "correct": correct,
        "best_move_san": best_san,
        "best_move_uci": primary,
        "user_move_san": played_san,
        "feedback": coaching["feedback"],
        "coaching_feedback": coaching,
        "pattern_type": verified_pattern or "calculation_depth",
        "recovery_weakness": verified_pattern,
        "admission_status": admission_status,
        "source": "verified_stored_evidence",
    }
