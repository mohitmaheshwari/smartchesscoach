"""Causal piece-safety proof adapter for verified puzzle admission.

The candidate detector reuses the canonical Chess Brain hanging-piece adapter.
The verifier independently replays legal captures on the claimed exchange square
and compares played-versus-best issue sets. No engine or LLM is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.chess_brain.detector_registry import (
    CAUSAL_MISTAKE_MIN_CP_LOSS,
    HANGING_PIECE_MIN_GAIN_CP,
    detect_hanging_piece,
)
from services.legal_exchange_verifier import independent_exchange_gain
from services.verified_puzzle_admission import DetectorProof, VerifierProof


PIECE_SAFETY_PROOF_VERSION = "piece_safety_puzzle_proof.v1"
PIECE_SAFETY_QUALITY_ID = "gap:piece_safety:simple_hang"


@dataclass(frozen=True)
class PieceSafetyProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = PIECE_SAFETY_QUALITY_ID


def _parse_move(board: chess.Board, raw: str) -> chess.Move:
    try:
        move = chess.Move.from_uci(raw)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    return board.parse_san(raw)


def _independent_hanging_issues(
    board: chess.Board, owner: chess.Color
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    if board.turn == owner:
        raise ValueError("opponent must be to move for hanging-piece verification")
    issues = {}
    for square, piece in board.piece_map().items():
        if piece.color != owner or piece.piece_type == chess.KING:
            continue
        gain = independent_exchange_gain(board, square)
        if gain < HANGING_PIECE_MIN_GAIN_CP:
            continue
        winning_move = None
        winning_gain = 0
        for move in list(board.legal_moves):
            if move.to_square != square or not board.is_capture(move):
                continue
            forced_gain = independent_exchange_gain(board, square, move)
            if forced_gain > winning_gain:
                winning_gain = forced_gain
                winning_move = move
        issues[(chess.square_name(square), piece.piece_type)] = {
            "square": chess.square_name(square),
            "piece_type_id": piece.piece_type,
            "piece": chess.piece_name(piece.piece_type),
            "material_loss_cp": gain,
            "winning_reply_uci": winning_move.uci() if winning_move else None,
        }
    return issues



def build_piece_safety_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    cp_loss: Any,
) -> Optional[PieceSafetyProofBundle]:
    """Build candidate + independent verifier proof or return no candidate."""
    try:
        played = _parse_move(board_before, played_move)
        best = _parse_move(board_before, best_move)
        played_san = board_before.san(played)
        best_san = board_before.san(best)
    except (ValueError, TypeError):
        return None

    result = detect_hanging_piece(
        board_before, played_san, best_san, {"cp_loss": cp_loss}
    )
    if not result.detected:
        return None

    details = result.details
    all_hanging = tuple(details.get("all_hanging") or ())
    detector = DetectorProof(
        concept_id="piece_safety.simple_hang",
        family="piece_safety",
        detector_id="brain:hanging_piece_detector",
        detector_version=PIECE_SAFETY_PROOF_VERSION,
        calculation_id="canonical_legal_exchange_counterfactual",
        facts=tuple(
            {
                "piece": item.get("piece"),
                "square": item.get("square"),
                "material_loss_cp": item.get("material_loss_cp"),
                "winning_reply": item.get("winning_reply"),
            }
            for item in all_hanging
        ),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "subtype": details.get("subtype"),
        },
    )

    verified = False
    verifier_facts: List[Dict[str, Any]] = []
    try:
        loss = require_nonnegative_cp_loss(cp_loss)
        owner = board_before.turn
        played_after = board_before.copy(stack=False)
        played_after.push(played)
        best_after = board_before.copy(stack=False)
        best_after.push(best)
        played_issues = _independent_hanging_issues(played_after, owner)
        best_issues = _independent_hanging_issues(best_after, owner)
        claimed = {
            (str(item.get("square")), chess.PIECE_NAMES.index(str(item.get("piece"))))
            for item in all_hanging
            if str(item.get("piece")) in chess.PIECE_NAMES
        }
        independently_removed = set(played_issues) - set(best_issues)
        verified = (
            loss >= CAUSAL_MISTAKE_MIN_CP_LOSS
            and bool(claimed)
            and claimed <= independently_removed
            and set(best_issues) < set(played_issues)
        )
        verifier_facts = [
            played_issues[key]
            for key in sorted(independently_removed)
            if key in claimed
        ]
    except (ValueError, TypeError, IndexError):
        verified = False

    verifier = VerifierProof(
        concept_id="piece_safety.simple_hang",
        verifier_id="independent_legal_reply_tree",
        verifier_version=PIECE_SAFETY_PROOF_VERSION,
        calculation_id="independent_target_capture_minimax",
        verified=verified,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=tuple(verifier_facts),
    )
    return PieceSafetyProofBundle(detector=detector, verifier=verifier)
