"""Exact removal-of-defender proof with legal stored target payoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.shape_detectors import detect_remove_the_guard
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


REMOVAL_PROOF_VERSION = "removal_defender_puzzle_proof.v2"
REMOVAL_QUALITY_ID = "tactic:remove_defender_with_stored_payoff"


@dataclass(frozen=True)
class RemovalDefenderProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = REMOVAL_QUALITY_ID


def _independent_removal(
    board_before: chess.Board,
    best: chess.Move,
    defender_square: int,
    target_square: int,
    continuation: Sequence[Any],
) -> Optional[dict]:
    us = board_before.turn
    them = not us
    defender = board_before.piece_at(defender_square)
    target = board_before.piece_at(target_square)
    if (
        best.to_square != defender_square
        or not board_before.is_capture(best)
        or defender is None
        or defender.color != them
        or target is None
        or target.color != them
        or PIECE_VALUE_CP.get(target.piece_type, 0) < PIECE_VALUE_CP[chess.KNIGHT]
    ):
        return None
    defenders = set(board_before.attackers(them, target_square))
    if defenders != {defender_square}:
        return None
    if not board_before.attackers(us, target_square):
        return None

    after = board_before.copy(stack=False)
    after.push(best)
    remaining_defenders = tuple(sorted(
        chess.square_name(square)
        for square in after.attackers(them, target_square)
    ))
    if remaining_defenders:
        return None

    replay = replay_stored_line(board_before, best, continuation)
    if not replay.complete or replay.net_material_gain_cp < PIECE_VALUE_CP[chess.PAWN]:
        return None
    board = board_before.copy(stack=False)
    target_captured = False
    target_identity = (target.piece_type, target.color)
    for index, uci in enumerate(replay.replayed_uci):
        move = chess.Move.from_uci(uci)
        if index > 0 and move.from_square == target_square:
            return None
        if (
            index > 0
            and board.turn == us
            and board.is_capture(move)
            and move.to_square == target_square
            and board.piece_at(target_square) is not None
            and (
                board.piece_at(target_square).piece_type,
                board.piece_at(target_square).color,
            ) == target_identity
        ):
            target_captured = True
        board.push(move)
    if not target_captured:
        return None
    return {
        "defender_piece": chess.piece_name(defender.piece_type),
        "defender_square": chess.square_name(defender_square),
        "target_piece": chess.piece_name(target.piece_type),
        "target_square": chess.square_name(target_square),
        "net_material_gain_cp": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
    }


def build_removal_defender_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[RemovalDefenderProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    matches = [
        item
        for item in detect_remove_the_guard(board_before)
        if item.get("executing_move") == best.uci()
        and len(item.get("targets") or ()) >= 2
    ]
    if not matches:
        return None
    candidate = matches[0]
    try:
        defender_square = chess.parse_square(candidate["targets"][0])
        target_square = chess.parse_square(candidate["targets"][1])
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    independent = _independent_removal(
        board_before,
        best,
        defender_square,
        target_square,
        pv_after_best,
    )
    concept_id = "tactic.removal_of_defender"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="shape:remove_the_guard",
        detector_version=REMOVAL_PROOF_VERSION,
        calculation_id="canonical_sole_guard_scan",
        facts=(candidate,),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_defender_set_and_target_replay",
        verifier_version=REMOVAL_PROOF_VERSION,
        calculation_id="fresh_attackers_after_capture_plus_target_capture",
        verified=independent is not None,
        acceptable_moves=(best.uci(),) if independent else (),
        facts=(independent,) if independent else (),
    )
    return RemovalDefenderProofBundle(detector=detector, verifier=verifier)
