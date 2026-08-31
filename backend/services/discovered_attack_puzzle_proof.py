"""Exact discovered-attack proof with independent ray and payoff replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP, _discovered_attack_evidence
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


DISCOVERED_ATTACK_PROOF_VERSION = "discovered_attack_puzzle_proof.v2"
DISCOVERED_ATTACK_QUALITY_ID = "tactic:discovered_attack_with_stored_payoff"


@dataclass(frozen=True)
class DiscoveredAttackProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = DISCOVERED_ATTACK_QUALITY_ID


def _ray_step(origin: int, target: int) -> Optional[tuple[int, int]]:
    file_delta = chess.square_file(target) - chess.square_file(origin)
    rank_delta = chess.square_rank(target) - chess.square_rank(origin)
    if file_delta == 0 and rank_delta:
        return 0, 1 if rank_delta > 0 else -1
    if rank_delta == 0 and file_delta:
        return 1 if file_delta > 0 else -1, 0
    if abs(file_delta) == abs(rank_delta) and file_delta:
        return (
            1 if file_delta > 0 else -1,
            1 if rank_delta > 0 else -1,
        )
    return None


def _between(origin: int, target: int) -> tuple[int, ...]:
    step = _ray_step(origin, target)
    if step is None:
        return ()
    file_step, rank_step = step
    file_ = chess.square_file(origin) + file_step
    rank_ = chess.square_rank(origin) + rank_step
    squares = []
    while 0 <= file_ < 8 and 0 <= rank_ < 8:
        square = chess.square(file_, rank_)
        if square == target:
            return tuple(squares)
        squares.append(square)
        file_ += file_step
        rank_ += rank_step
    return ()


def _independent_discovery_payoff(
    board_before: chess.Board,
    best: chess.Move,
    slider_square: int,
    target_square: int,
    continuation: Sequence[Any],
) -> Optional[dict]:
    us = board_before.turn
    slider = board_before.piece_at(slider_square)
    blocker = board_before.piece_at(best.from_square)
    target = board_before.piece_at(target_square)
    if (
        slider is None
        or slider.color != us
        or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN)
        or blocker is None
        or blocker.color != us
        or target is None
        or target.color == us
        or PIECE_VALUE_CP.get(target.piece_type, 0) < PIECE_VALUE_CP[chess.KNIGHT]
    ):
        return None
    step = _ray_step(slider_square, target_square)
    if step is None:
        return None
    file_step, rank_step = step
    if (
        slider.piece_type == chess.BISHOP
        and (file_step == 0 or rank_step == 0)
    ) or (
        slider.piece_type == chess.ROOK
        and file_step != 0
        and rank_step != 0
    ):
        return None
    between = _between(slider_square, target_square)
    occupied_before = tuple(
        square for square in between if board_before.piece_at(square)
    )
    if occupied_before != (best.from_square,):
        return None

    after = board_before.copy(stack=False)
    after.push(best)
    if any(after.piece_at(square) for square in between):
        return None
    if slider_square not in after.attackers(us, target_square):
        return None

    replay = replay_stored_line(board_before, best, continuation)
    if not replay.complete or replay.net_material_gain_cp < PIECE_VALUE_CP[chess.PAWN]:
        return None
    board = board_before.copy(stack=False)
    payoff_ply = None
    target_identity = (target.piece_type, target.color)
    slider_identity = (slider.piece_type, slider.color)
    for index, uci in enumerate(replay.replayed_uci):
        move = chess.Move.from_uci(uci)
        if index > 0 and move.from_square == target_square:
            return None
        if (
            index > 0
            and board.turn == us
            and move.from_square == slider_square
            and move.to_square == target_square
            and board.is_capture(move)
            and board.piece_at(slider_square) is not None
            and (
                board.piece_at(slider_square).piece_type,
                board.piece_at(slider_square).color,
            ) == slider_identity
            and board.piece_at(target_square) is not None
            and (
                board.piece_at(target_square).piece_type,
                board.piece_at(target_square).color,
            ) == target_identity
        ):
            payoff_ply = index + 1
        elif index > 0 and move.from_square == slider_square:
            return None
        board.push(move)
    if payoff_ply is None:
        return None
    return {
        "slider_piece": chess.piece_name(slider.piece_type),
        "slider_square": chess.square_name(slider_square),
        "vacated_square": chess.square_name(best.from_square),
        "target_piece": chess.piece_name(target.piece_type),
        "target_square": chess.square_name(target_square),
        "payoff_ply": payoff_ply,
        "net_material_gain_cp": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
    }


def build_discovered_attack_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[DiscoveredAttackProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    after = board_before.copy(stack=False)
    after.push(best)
    candidates = [
        item
        for item in _discovered_attack_evidence(board_before, after, best)
        if int(item.get("target_value_cp") or 0) >= PIECE_VALUE_CP[chess.KNIGHT]
    ]
    if not candidates:
        return None
    candidate = max(candidates, key=lambda item: int(item["target_value_cp"]))
    try:
        slider_square = chess.parse_square(candidate["discovered_attacker_square"])
        target_square = chess.parse_square(candidate["target_square"])
    except (ValueError, KeyError, TypeError):
        return None
    verified = _independent_discovery_payoff(
        board_before,
        best,
        slider_square,
        target_square,
        pv_after_best,
    )
    concept_id = "tactic.discovered_attack"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="canonical_discovered_attack_evidence",
        detector_version=DISCOVERED_ATTACK_PROOF_VERSION,
        calculation_id="canonical_vacated_ray_candidate",
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
        verifier_id="independent_discovery_ray_and_payoff",
        verifier_version=DISCOVERED_ATTACK_PROOF_VERSION,
        calculation_id="fresh_single_blocker_ray_plus_exact_slider_capture",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return DiscoveredAttackProofBundle(detector=detector, verifier=verifier)
