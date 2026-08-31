"""Exact proof that the stored best move takes an unrecapturable piece."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.shape_detectors import detect_free_piece
from services.verified_puzzle_admission import DetectorProof, VerifierProof


FREE_PIECE_PROOF_VERSION = "free_piece_puzzle_proof.v1"
FREE_PIECE_QUALITY_ID = "tactic:free_piece_exact"
MIN_TARGET_VALUE_CP = PIECE_VALUE_CP[chess.KNIGHT]


@dataclass(frozen=True)
class FreePieceProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = FREE_PIECE_QUALITY_ID


def _parse_legal(board: chess.Board, raw: str) -> Optional[chess.Move]:
    try:
        move = chess.Move.from_uci(str(raw).lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(str(raw))
    except (ValueError, AssertionError):
        return None


def _independent_free_capture(
    board_before: chess.Board,
    move: chess.Move,
) -> Optional[dict]:
    """Verify capture value and enumerate every legal immediate recapture."""
    if move not in board_before.legal_moves or not board_before.is_capture(move):
        return None
    captured_square = move.to_square
    if board_before.is_en_passant(move):
        captured_square += -8 if board_before.turn == chess.WHITE else 8
    captured = board_before.piece_at(captured_square)
    if (
        captured is None
        or captured.color == board_before.turn
        or captured.piece_type == chess.KING
    ):
        return None
    value = PIECE_VALUE_CP.get(captured.piece_type, 0)
    if value < MIN_TARGET_VALUE_CP:
        return None

    after = board_before.copy(stack=False)
    after.push(move)
    recaptures = tuple(sorted(
        reply.uci()
        for reply in after.legal_moves
        if reply.to_square == move.to_square and after.is_capture(reply)
    ))
    if recaptures:
        return None
    return {
        "captured_piece": chess.piece_name(captured.piece_type),
        "captured_square": chess.square_name(captured_square),
        "captured_value_cp": value,
        "recaptures": recaptures,
    }


def build_free_piece_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    cp_loss: Any,
) -> Optional[FreePieceProofBundle]:
    try:
        played = _parse_legal(board_before, played_move)
        best = _parse_legal(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    matches = [
        evidence
        for evidence in detect_free_piece(board_before)
        if evidence.get("executing_move") == best.uci()
    ]
    if not matches:
        return None
    candidate = matches[0]

    independent = _independent_free_capture(board_before, best)
    concept_id = "tactic.free_piece"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="shape:free_piece",
        detector_version=FREE_PIECE_PROOF_VERSION,
        calculation_id="canonical_shape_free_piece_scan",
        facts=({
            "mover": candidate.get("mover"),
            "targets": tuple(candidate.get("targets") or ()),
            "executing_move": best.uci(),
        },),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_legal_recapture_enumerator",
        verifier_version=FREE_PIECE_PROOF_VERSION,
        calculation_id="post_capture_all_legal_replies",
        verified=independent is not None,
        acceptable_moves=(best.uci(),) if independent else (),
        facts=(independent,) if independent else (),
    )
    return FreePieceProofBundle(detector=detector, verifier=verifier)
