"""Verified-puzzle proof for the Plan-grade destination-safety fact."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import chess

from services.destination_safety_detector import (
    FACT_VERSION,
    QUALITY_ID,
    SEE_FLOOR_CP,
    derive_destination_safety_exact,
)
from services.legal_exchange_verifier import independent_exchange_gain
from services.verified_puzzle_admission import DetectorProof, VerifierProof


PROOF_VERSION = "destination_safety_puzzle_proof.v1"


@dataclass(frozen=True)
class DestinationSafetyProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = QUALITY_ID


def _parse_move(board: chess.Board, raw: Any) -> chess.Move:
    try:
        move = chess.Move.from_uci(str(raw).lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    return board.parse_san(str(raw))


def _gain_after(board: chess.Board, move: chess.Move) -> int:
    after = board.copy(stack=False)
    after.push(move)
    return independent_exchange_gain(after, move.to_square)


def build_destination_safety_proof(
    board_before: chess.Board,
    move_evaluation: Dict[str, Any],
    played_move: Any,
    best_move: Any,
) -> Optional[DestinationSafetyProofBundle]:
    """Build the canonical candidate plus an independently calculated proof."""
    try:
        played = _parse_move(board_before, played_move)
        best = _parse_move(board_before, best_move)
    except (ValueError, TypeError):
        return None

    candidate_row = dict(move_evaluation)
    candidate_row["move_uci"] = played.uci()
    candidate = derive_destination_safety_exact(candidate_row)
    if not candidate.get("fires"):
        return None

    detector = DetectorProof(
        concept_id="piece_safety.destination_safety_exact",
        family="piece_safety",
        detector_id="destination_safety_exact",
        detector_version=FACT_VERSION,
        calculation_id="exact_destination_capture_tree",
        facts=({
            "piece": candidate.get("moved_piece"),
            "square": candidate.get("destination"),
            "material_loss_cp": candidate.get("exact_exchange_gain_cp"),
            "winning_reply_uci": candidate.get("opponent_reply_uci"),
        },),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
        },
    )

    played_gain = _gain_after(board_before, played)
    best_gain = _gain_after(board_before, best)
    verified = played_gain >= SEE_FLOOR_CP and best_gain < SEE_FLOOR_CP
    verifier = VerifierProof(
        concept_id="piece_safety.destination_safety_exact",
        verifier_id="independent_destination_capture_tree",
        verifier_version=PROOF_VERSION,
        calculation_id="independent_target_capture_minimax",
        verified=verified,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=({
            "played_destination_loss_cp": played_gain,
            "best_destination_loss_cp": best_gain,
            "played_destination": chess.square_name(played.to_square),
            "best_destination": chess.square_name(best.to_square),
        },),
    )
    return DestinationSafetyProofBundle(detector=detector, verifier=verifier)


__all__ = ["DestinationSafetyProofBundle", "build_destination_safety_proof"]
