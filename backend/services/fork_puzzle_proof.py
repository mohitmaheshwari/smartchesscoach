"""Exact fork proof with independent geometry and stored-line payoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.shape_detectors import (
    detect_bishop_fork,
    detect_knight_fork,
    detect_pawn_fork,
    detect_rook_fork,
)
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


FORK_PROOF_VERSION = "fork_puzzle_proof.v2"
FORK_QUALITY_ID = "tactic:fork_with_stored_payoff"
_FORK_DETECTORS = (
    detect_knight_fork,
    detect_bishop_fork,
    detect_rook_fork,
    detect_pawn_fork,
)


@dataclass(frozen=True)
class ForkProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = FORK_QUALITY_ID


def verify_created_fork(
    board_before: chess.Board,
    move: Any,
) -> Optional[dict]:
    """Independently prove that one legal move creates a two-target fork.

    This proves only the board geometry, not that the fork wins material. The
    stronger puzzle proof below still requires a stored continuation payoff.
    """
    played = parse_legal_move(board_before, move)
    if played is None:
        return None
    color = board_before.turn
    after = board_before.copy(stack=False)
    after.push(played)
    moved = after.piece_at(played.to_square)
    if moved is None or moved.color != color:
        return None
    targets = []
    for square in after.attacks(played.to_square):
        piece = after.piece_at(square)
        if piece is None or piece.color == color:
            continue
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if piece.piece_type == chess.KING or value >= PIECE_VALUE_CP[chess.KNIGHT]:
            targets.append(square)
    if len(targets) < 2:
        return None
    return {
        "fork_square": chess.square_name(played.to_square),
        "forking_piece": chess.piece_name(moved.piece_type),
        "targets": tuple(chess.square_name(square) for square in targets),
    }


def _independent_fork_and_payoff(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
) -> Optional[dict]:
    initiator = board_before.turn
    after = board_before.copy(stack=False)
    after.push(best)
    moved = after.piece_at(best.to_square)
    if moved is None or moved.color != initiator:
        return None

    targets = []
    for square in after.attacks(best.to_square):
        piece = after.piece_at(square)
        if not piece or piece.color == initiator:
            continue
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if piece.piece_type == chess.KING or value >= PIECE_VALUE_CP[chess.KNIGHT]:
            targets.append((square, piece.piece_type, value))
    if len(targets) < 2:
        return None

    replay = replay_stored_line(board_before, best, pv_after_best)
    if not replay.complete:
        return None
    net_gain = replay.net_material_gain_cp
    if net_gain < PIECE_VALUE_CP[chess.PAWN]:
        return None
    # A material gain elsewhere in the line does not prove that the fork paid
    # off. Track the original target pieces on their original squares; if a
    # target moves, it is no longer eligible. At least one still-original fork
    # target must be captured by the side that played the fork.
    board = board_before.copy(stack=False)
    live_targets = {
        square: (piece_type, board_before.piece_at(square).color)
        for square, piece_type, _value_cp in targets
        if board_before.piece_at(square) is not None
    }
    captured_target = None
    for index, uci in enumerate(replay.replayed_uci):
        move = chess.Move.from_uci(uci)
        if index > 0:
            if move.from_square in live_targets:
                live_targets.pop(move.from_square, None)
            original = live_targets.get(move.to_square)
            captured = board.piece_at(move.to_square)
            if (
                original
                and board.turn == initiator
                and board.is_capture(move)
                and captured is not None
                and (captured.piece_type, captured.color) == original
            ):
                captured_target = move.to_square
        board.push(move)
    if captured_target is None:
        return None
    return {
        "forking_piece": chess.piece_name(moved.piece_type),
        "fork_square": chess.square_name(best.to_square),
        "targets": tuple(chess.square_name(item[0]) for item in targets),
        "captured_target": chess.square_name(captured_target),
        "net_material_gain_cp": net_gain,
        "replayed_uci": replay.replayed_uci,
    }


def build_fork_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[ForkProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    matches = []
    for detector in _FORK_DETECTORS:
        matches.extend(
            item
            for item in detector(board_before)
            if item.get("executing_move") == best.uci()
        )
    if not matches:
        return None
    candidate = max(matches, key=lambda item: len(item.get("targets") or ()))
    pattern_id = str(candidate.get("pattern_id") or "fork")
    concept_id = f"tactic.{pattern_id}"
    independent = _independent_fork_and_payoff(
        board_before, best, pv_after_best
    )

    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id=f"shape:{pattern_id}",
        detector_version=FORK_PROOF_VERSION,
        calculation_id="canonical_fork_shape_scan",
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
        verifier_id="independent_attack_map_and_pv_payoff",
        verifier_version=FORK_PROOF_VERSION,
        calculation_id="post_move_targets_plus_legal_material_walk",
        verified=independent is not None,
        acceptable_moves=(best.uci(),) if independent else (),
        facts=(independent,) if independent else (),
    )
    return ForkProofBundle(detector=detector, verifier=verifier)
