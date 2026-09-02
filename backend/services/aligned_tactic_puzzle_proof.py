"""Exact pin/skewer proof with independent ray geometry and stored payoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP, _aligned_pieces_evidence
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


ALIGNED_PROOF_VERSION = "aligned_tactic_puzzle_proof.v3"
ALIGNED_QUALITY_ID = "tactic:aligned_with_stored_payoff"
_DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_ORTHOGONALS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True)
class AlignedTacticProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = ALIGNED_QUALITY_ID


def _value(piece: chess.Piece) -> int:
    return (
        10_000
        if piece.piece_type == chess.KING
        else PIECE_VALUE_CP.get(piece.piece_type, 0)
    )


def _ray_alignments(
    board: chess.Board,
    color: chess.Color,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Independent first-two-blockers ray walk keyed by target pair."""
    found: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        directions = (
            _DIAGONALS
            if piece_type == chess.BISHOP
            else _ORTHOGONALS
            if piece_type == chess.ROOK
            else _DIAGONALS + _ORTHOGONALS
        )
        for attacker in board.pieces(piece_type, color):
            for file_step, rank_step in directions:
                file_ = chess.square_file(attacker) + file_step
                rank_ = chess.square_rank(attacker) + rank_step
                hits = []
                while 0 <= file_ < 8 and 0 <= rank_ < 8:
                    square = chess.square(file_, rank_)
                    piece = board.piece_at(square)
                    if piece:
                        hits.append((square, piece))
                        if len(hits) == 2:
                            break
                    file_ += file_step
                    rank_ += rank_step
                if len(hits) != 2 or any(piece.color == color for _, piece in hits):
                    continue
                (front_square, front), (rear_square, rear) = hits
                front_value, rear_value = _value(front), _value(rear)
                kind = (
                    "pin" if front_value < rear_value
                    else "skewer" if front_value > rear_value
                    else None
                )
                if kind:
                    found[(front_square, rear_square)] = {
                        "kind": kind,
                        "attacker_square": attacker,
                        "front_square": front_square,
                        "rear_square": rear_square,
                        "front_piece": front.piece_type,
                        "rear_piece": rear.piece_type,
                    }
    return found


def verify_created_alignment(
    board_before: chess.Board,
    move: Any,
    kind: str,
) -> Optional[dict]:
    """Independently prove that a legal move creates a new pin or skewer."""
    wanted = str(kind or "").strip().lower()
    if wanted not in {"pin", "skewer"}:
        return None
    played = parse_legal_move(board_before, move)
    if played is None:
        return None
    color = board_before.turn
    before = _ray_alignments(board_before, color)
    after_board = board_before.copy(stack=False)
    after_board.push(played)
    after = _ray_alignments(after_board, color)
    created = [
        value
        for key, value in after.items()
        if key not in before
        and value.get("kind") == wanted
        and value.get("attacker_square") == played.to_square
    ]
    if not created:
        return None
    strongest = max(
        created,
        key=lambda item: max(
            _value(after_board.piece_at(item["front_square"])),
            _value(after_board.piece_at(item["rear_square"])),
        ),
    )
    return {
        "kind": wanted,
        "attacker_square": chess.square_name(strongest["attacker_square"]),
        "front_square": chess.square_name(strongest["front_square"]),
        "rear_square": chess.square_name(strongest["rear_square"]),
    }


def _candidate_delta(
    board_before: chess.Board,
    best: chess.Move,
) -> Optional[Dict[str, Any]]:
    color = board_before.turn
    before = _aligned_pieces_evidence(board_before, color)
    before_pairs = {
        (item["front_piece_square"], item["rear_piece_square"])
        for item in before
    }
    after = board_before.copy(stack=False)
    after.push(best)
    candidates = [
        item
        for item in _aligned_pieces_evidence(after, color)
        if (item["front_piece_square"], item["rear_piece_square"])
        not in before_pairs
        and item.get("front_value_vs_rear") in ("lower", "higher")
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: max(
            int(item.get("front_piece_value_cp") or 0),
            int(item.get("rear_piece_value_cp") or 0),
        ),
    )


def _payoff_uses_alignment(
    board_before: chess.Board,
    best: chess.Move,
    continuation: Sequence[Any],
    alignment: Dict[str, Any],
) -> Optional[dict]:
    replay = replay_stored_line(board_before, best, continuation)
    if not replay.complete or replay.net_material_gain_cp < PIECE_VALUE_CP[chess.PAWN]:
        return None

    board = board_before.copy(stack=False)
    initiator = board.turn
    front = alignment["front_square"]
    rear = alignment["rear_square"]
    used = False
    front_moved = False
    attacker_identity = None
    front_identity = None
    rear_identity = None
    for index, uci in enumerate(replay.replayed_uci):
        move = chess.Move.from_uci(uci)
        mover = board.turn
        is_capture = board.is_capture(move)
        if index == 0:
            board.push(move)
            attacker = board.piece_at(alignment["attacker_square"])
            front_piece = board.piece_at(front)
            rear_piece = board.piece_at(rear)
            if attacker is None or front_piece is None or rear_piece is None:
                return None
            attacker_identity = (attacker.piece_type, attacker.color)
            front_identity = (front_piece.piece_type, front_piece.color)
            rear_identity = (rear_piece.piece_type, rear_piece.color)
            continue
        if index > 0:
            if alignment["kind"] == "skewer":
                if mover != initiator and move.from_square == front:
                    front_moved = True
                elif not front_moved and move.from_square == front:
                    return None
                if move.from_square == rear:
                    return None
                if (
                    mover == initiator
                    and front_moved
                    and is_capture
                    and move.from_square == alignment["attacker_square"]
                    and move.to_square == rear
                    and board.piece_at(alignment["attacker_square"]) is not None
                    and (
                        board.piece_at(alignment["attacker_square"]).piece_type,
                        board.piece_at(alignment["attacker_square"]).color,
                    ) == attacker_identity
                    and board.piece_at(rear) is not None
                    and (
                        board.piece_at(rear).piece_type,
                        board.piece_at(rear).color,
                    ) == rear_identity
                ):
                    used = True
            elif (
                mover == initiator
                and is_capture
                and move.from_square == alignment["attacker_square"]
                and move.to_square == front
                and board.piece_at(alignment["attacker_square"]) is not None
                and (
                    board.piece_at(alignment["attacker_square"]).piece_type,
                    board.piece_at(alignment["attacker_square"]).color,
                ) == attacker_identity
                and board.piece_at(front) is not None
                and (
                    board.piece_at(front).piece_type,
                    board.piece_at(front).color,
                ) == front_identity
            ):
                used = True
            elif alignment["kind"] == "pin" and move.from_square == front:
                return None
            if move.from_square == alignment["attacker_square"] and not used:
                return None
        board.push(move)
    if not used:
        return None
    return {
        "kind": alignment["kind"],
        "creation_mode": (
            "direct"
            if alignment["attacker_square"] == best.to_square
            else "discovered"
        ),
        "attacker_piece": chess.piece_name(attacker_identity[0]),
        "attacker_square": chess.square_name(alignment["attacker_square"]),
        "front_piece": chess.piece_name(front_identity[0]),
        "front_square": chess.square_name(front),
        "rear_piece": chess.piece_name(rear_identity[0]),
        "rear_square": chess.square_name(rear),
        "net_material_gain_cp": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
    }


def build_aligned_tactic_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[AlignedTacticProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    candidate = _candidate_delta(board_before, best)
    if not candidate:
        return None
    kind = "pin" if candidate["front_value_vs_rear"] == "lower" else "skewer"
    concept_id = f"tactic.{kind}"

    before_independent = _ray_alignments(board_before, board_before.turn)
    after = board_before.copy(stack=False)
    after.push(best)
    after_independent = _ray_alignments(after, board_before.turn)
    key = (
        chess.parse_square(candidate["front_piece_square"]),
        chess.parse_square(candidate["rear_piece_square"]),
    )
    independent_alignment = after_independent.get(key)
    if key in before_independent or (
        independent_alignment and independent_alignment["kind"] != kind
    ):
        independent_alignment = None
    payoff = (
        _payoff_uses_alignment(
            board_before, best, pv_after_best, independent_alignment
        )
        if independent_alignment
        else None
    )

    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id=f"shape:{kind}",
        detector_version=ALIGNED_PROOF_VERSION,
        calculation_id="canonical_aligned_before_after_delta",
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
        verifier_id="independent_ray_and_payoff_replay",
        verifier_version=ALIGNED_PROOF_VERSION,
        calculation_id="fresh_two_blocker_rays_plus_target_capture",
        verified=payoff is not None,
        acceptable_moves=(best.uci(),) if payoff else (),
        facts=(payoff,) if payoff else (),
    )
    return AlignedTacticProofBundle(detector=detector, verifier=verifier)
