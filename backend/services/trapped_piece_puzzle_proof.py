"""Causal trapped-own-piece proof with independent escape enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import chess

from services.board_concepts import TRAPPED_FLOOR_CP, TRAPPABLE
from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.chess_brain.detector_registry import detect_trapped_piece
from services.legal_exchange_verifier import independent_exchange_gain
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof


TRAPPED_PIECE_PROOF_VERSION = "trapped_piece_puzzle_proof.v1"
TRAPPED_PIECE_QUALITY_ID = "gap:piece_safety:trapped_piece_exact"


@dataclass(frozen=True)
class TrappedPieceProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = TRAPPED_PIECE_QUALITY_ID


def _capture_credit(board: chess.Board, move: chess.Move) -> int:
    if not board.is_capture(move):
        return 0
    if board.is_en_passant(move):
        return PIECE_VALUE_CP[chess.PAWN]
    target = board.piece_at(move.to_square)
    return PIECE_VALUE_CP.get(target.piece_type, 0) if target else 0


def _independently_trapped_at(
    post_move: chess.Board,
    owner: chess.Color,
    square: int,
) -> Optional[dict]:
    """Check immediate loss and every legal escape with a separate minimax."""
    piece = post_move.piece_at(square)
    if (
        post_move.turn == owner
        or piece is None
        or piece.color != owner
        or piece.piece_type not in TRAPPABLE
        or not post_move.is_attacked_by(not owner, square)
    ):
        return None
    stay_loss = independent_exchange_gain(post_move, square)
    if stay_loss < TRAPPED_FLOOR_CP:
        return None

    probe = post_move.copy(stack=False)
    probe.turn = owner
    legal_escapes = []
    for move in list(probe.legal_moves):
        if move.from_square != square:
            continue
        credit = _capture_credit(probe, move)
        after = probe.copy(stack=False)
        after.push(move)
        destination_loss = independent_exchange_gain(after, move.to_square)
        net_loss = max(0, destination_loss - credit)
        legal_escapes.append({
            "move": move.uci(),
            "net_loss_cp": net_loss,
        })
        if net_loss < TRAPPED_FLOOR_CP:
            return None
    return {
        "piece": chess.piece_name(piece.piece_type),
        "square": chess.square_name(square),
        "stay_loss_cp": stay_loss,
        "legal_escapes": tuple(legal_escapes),
    }


def build_trapped_piece_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    cp_loss: Any,
) -> Optional[TrappedPieceProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    candidate = detect_trapped_piece(
        board_before,
        board_before.san(played),
        board_before.san(best),
        {"cp_loss": loss},
    )
    if not candidate.detected:
        return None
    try:
        claimed_square = chess.parse_square(candidate.details["trapped_square"])
    except (KeyError, TypeError, ValueError):
        return None

    played_after = board_before.copy(stack=False)
    played_after.push(played)
    trapped = _independently_trapped_at(
        played_after, board_before.turn, claimed_square
    )

    original_piece = board_before.piece_at(played.from_square)
    best_after = board_before.copy(stack=False)
    best_after.push(best)
    best_square = (
        best.to_square
        if original_piece is not None and best.from_square == played.from_square
        else played.from_square
    )
    avoided = _independently_trapped_at(
        best_after, board_before.turn, best_square
    ) is None
    verified = trapped if trapped and avoided else None

    concept_id = "piece_safety.trapped_piece"
    detector = DetectorProof(
        concept_id=concept_id,
        family="piece_safety",
        detector_id="brain:trapped_piece_detector",
        detector_version=TRAPPED_PIECE_PROOF_VERSION,
        calculation_id="canonical_newly_trapped_counterfactual",
        facts=(dict(candidate.details or {}),),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_all_escape_exchange_verifier",
        verifier_version=TRAPPED_PIECE_PROOF_VERSION,
        calculation_id="fresh_target_minimax_plus_every_legal_escape",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return TrappedPieceProofBundle(detector=detector, verifier=verifier)
