"""Exact, deterministic destination-safety evidence for planning.

This detector makes one narrow claim: after a player moves a non-pawn piece,
the stored best reply immediately captures that exact piece and exhaustive
legal exchange analysis says the capture wins at least a minor-piece-equivalent
amount. Stored Stockfish cp_loss remains the independent consequence gate.

No engine or model is called here. The service consumes only the board and
Stockfish evidence already stored with a move evaluation.
"""
from __future__ import annotations

from typing import Any, Dict

import chess


FACT_VERSION = "piece_safety.destination_safety_exact.v1"
QUALITY_ID = "gap:piece_safety:destination_safety_exact"
SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured = board.piece_at(move.to_square)
    return PIECE_VALUES[captured.piece_type] if captured else 0


def _promotion_gain(move: chess.Move) -> int:
    if move.promotion is None:
        return 0
    return PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]


def _exact_exchange_gain(board: chess.Board, target: int) -> int:
    """Return the best material gain from optional legal captures on target.

    Every legal capturing choice is explored at every ply. Returning zero
    models declining an unfavorable continuation. This deliberately avoids the
    least-valuable-attacker approximation used by the broad D_live census.
    """
    best = 0
    replies = [
        move
        for move in board.legal_moves
        if board.is_capture(move) and move.to_square == target
    ]
    for move in replies:
        captured = _captured_value(board, move) + _promotion_gain(move)
        board.push(move)
        continuation = _exact_exchange_gain(board, target)
        board.pop()
        best = max(best, captured - continuation)
    return max(0, best)


def derive_destination_safety_exact(move_evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the exact planning fact from one stored move evaluation."""
    fact: Dict[str, Any] = {
        "version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "derivation_status": "ok",
        "eligible": False,
        "outcome": "not_eligible",
        "fires": False,
        "reason": "not_eligible",
        "moved_piece": None,
        "destination": None,
        "opponent_reply_san": None,
        "opponent_reply_uci": None,
        "legal_destination_captures": 0,
        "exact_exchange_gain_cp": 0,
        "stockfish_cp_loss": _safe_cp(move_evaluation.get("cp_loss")),
    }
    fen = move_evaluation.get("fen_before")
    uci = str(move_evaluation.get("move_uci") or "")
    if not fen or len(uci) < 4:
        fact.update(derivation_status="unavailable", reason="missing_position")
        return fact
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            fact.update(derivation_status="unavailable", reason="illegal_move")
            return fact
        moved_piece = board.piece_at(move.from_square)
        if moved_piece is None:
            fact.update(derivation_status="unavailable", reason="missing_piece")
            return fact
        fact["moved_piece"] = chess.piece_name(moved_piece.piece_type)
        fact["destination"] = chess.square_name(move.to_square)
        if moved_piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            fact["reason"] = "piece_not_eligible"
            return fact

        board.push(move)
        captures = [
            reply
            for reply in board.legal_moves
            if board.is_capture(reply) and reply.to_square == move.to_square
        ]
        has_promotion_capture = any(reply.promotion is not None for reply in captures)
        fact["legal_destination_captures"] = len(captures)
        if not captures:
            fact["reason"] = "not_legally_capturable"
            return fact

        fact["eligible"] = True
        exact_gain = _exact_exchange_gain(board, move.to_square)
        fact["exact_exchange_gain_cp"] = exact_gain
        if exact_gain < SEE_FLOOR_CP:
            fact["outcome"] = "handled"
            fact["reason"] = "exchange_is_safe"
            return fact
        if fact["stockfish_cp_loss"] < CP_LOSS_FLOOR:
            fact["outcome"] = "handled"
            fact["reason"] = "move_not_costly"
            return fact
        fact["outcome"] = "miss"

        # Promotion material is counted exactly for honest measurement, but
        # promotion-rank diagnoses were not present in the sealed Plan packet.
        # Keep them measurable and silent until reviewed independently.
        if has_promotion_capture:
            fact["reason"] = "promotion_exchange_not_promoted"
            return fact

        pv = move_evaluation.get("pv_after_played") or []
        if not pv:
            fact["reason"] = "missing_stored_reply"
            return fact
        reply = board.parse_san(str(pv[0]))
        fact["opponent_reply_san"] = board.san(reply)
        fact["opponent_reply_uci"] = reply.uci()
        if not board.is_capture(reply):
            fact["reason"] = "stored_reply_is_not_capture"
            return fact
        if reply.to_square != move.to_square:
            fact["reason"] = "stored_reply_captures_elsewhere"
            return fact

        fact["fires"] = True
        fact["reason"] = "exact_destination_capture"
        return fact
    except (
        AssertionError,
        TypeError,
        ValueError,
        chess.InvalidMoveError,
        chess.IllegalMoveError,
        chess.AmbiguousMoveError,
    ):
        fact.update(derivation_status="unavailable", reason="invalid_position_or_reply")
        return fact


def grade_destination_safety_candidate(fen: str, supplied_move: str) -> Dict[str, Any]:
    """Grade a new move against this detector's narrow concept."""
    result: Dict[str, Any] = {
        "version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "status": "unmeasured",
        "reason": "invalid_position_or_move",
        "move_uci": None,
        "moved_piece": None,
        "destination": None,
        "exact_exchange_gain_cp": None,
        "independent_exchange_gain_cp": None,
        "proofs_agree": False,
    }
    try:
        board = chess.Board(str(fen or ""))
        text = str(supplied_move or "").strip()
        try:
            move = chess.Move.from_uci(text.lower())
            if move not in board.legal_moves:
                raise ValueError("illegal move")
        except ValueError:
            move = board.parse_san(text)
        if move not in board.legal_moves:
            return result
        piece = board.piece_at(move.from_square)
        if piece is None:
            return result
        result.update({
            "move_uci": move.uci(),
            "moved_piece": chess.piece_name(piece.piece_type),
            "destination": chess.square_name(move.to_square),
        })
        if piece.piece_type not in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            result["reason"] = "piece_not_eligible"
            return result
        after = board.copy(stack=False)
        after.push(move)
        exact_gain = _exact_exchange_gain(after, move.to_square)
        from services.legal_exchange_verifier import independent_exchange_gain
        independent_gain = independent_exchange_gain(after, move.to_square)
        agrees = exact_gain == independent_gain
        result.update({
            "exact_exchange_gain_cp": exact_gain,
            "independent_exchange_gain_cp": independent_gain,
            "proofs_agree": agrees,
        })
        if not agrees:
            result["reason"] = "proof_disagreement"
            return result
        if exact_gain >= SEE_FLOOR_CP:
            result.update(status="fail", reason="destination_loses_material")
        else:
            result.update(status="pass", reason="destination_is_safe")
        return result
    except (AssertionError, TypeError, ValueError, chess.InvalidMoveError,
            chess.IllegalMoveError, chess.AmbiguousMoveError):
        return result


__all__ = [
    "CP_LOSS_FLOOR",
    "FACT_VERSION",
    "QUALITY_ID",
    "SEE_FLOOR_CP",
    "derive_destination_safety_exact",
    "grade_destination_safety_candidate",
]
