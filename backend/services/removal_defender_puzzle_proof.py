"""Exact removal-of-defender proof with legal stored target payoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP, static_exchange_eval
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.shape_detectors import detect_remove_the_guard
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


REMOVAL_PROOF_VERSION = "removal_defender_puzzle_proof.v3"
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
    """Settle the removal on the board, at the ply the target is taken.

    The claim this proves is the one the coach makes: *that piece was
    guarding this one; take the guard and the target falls*. Every
    condition below is therefore read either on the position before the
    capture or on the position at the moment the target is taken --
    never on the position before the move for a fact the move creates.

    Two conditions used to be read too early and were wrong for it. A
    second defender of the target is routinely the piece that recaptures
    the guard, so it is gone by the payoff. And the attack on the target
    is often opened BY that recapture, so demanding it in advance threw
    the line away. What replaces both is a single exchange reading on the
    payoff position, plus the requirement that removing the guard is what
    made that exchange work.
    """
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
    defenders_before = frozenset(board_before.attackers(them, target_square))
    if defender_square not in defenders_before:
        return None
    exchange_before_cp = static_exchange_eval(board_before, target_square, us)

    replay = replay_stored_line(
        board_before,
        best,
        continuation,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete or replay.net_material_gain_cp < PIECE_VALUE_CP[chess.PAWN]:
        return None
    board = board_before.copy(stack=False)
    payoff: Optional[dict] = None
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
            defenders_at_payoff = frozenset(
                board.attackers(them, target_square)
            )
            exchange_at_payoff_cp = static_exchange_eval(
                board, target_square, us
            )
            # One piece clears the guard, another collects. When the
            # capturing piece walks on to take the target itself,
            # nothing was "removed" for anybody: that is a two-move
            # grab, and it is where this proof used to stray into
            # fork positions.
            collected_by_the_same_piece = move.from_square == best.to_square
            if (
                defender_square not in defenders_at_payoff
                and not collected_by_the_same_piece
                and exchange_at_payoff_cp >= 0
                and exchange_at_payoff_cp >= exchange_before_cp
            ):
                payoff = {
                    "payoff_ply": index,
                    "payoff_move_uci": uci,
                    "defenders_before": tuple(sorted(
                        chess.square_name(square)
                        for square in defenders_before
                    )),
                    "defenders_at_payoff": tuple(sorted(
                        chess.square_name(square)
                        for square in defenders_at_payoff
                    )),
                    "exchange_before_cp": exchange_before_cp,
                    "exchange_at_payoff_cp": exchange_at_payoff_cp,
                }
            break
        board.push(move)
    if payoff is None:
        return None
    return {
        "defender_piece": chess.piece_name(defender.piece_type),
        "defender_square": chess.square_name(defender_square),
        "target_piece": chess.piece_name(target.piece_type),
        "target_square": chess.square_name(target_square),
        "net_material_gain_cp": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
        **payoff,
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
        for item in detect_remove_the_guard(
            board_before,
            executing_move=best,
            allow_sacrifice=True,
            require_sole_guard=False,
            require_existing_attacker=False,
        )
        if item.get("executing_move") == best.uci()
        and len(item.get("targets") or ()) >= 2
    ]
    if not matches:
        return None
    candidate = matches[0]
    independent = None
    for item in matches:
        try:
            defender_square = chess.parse_square(item["targets"][0])
            target_square = chess.parse_square(item["targets"][1])
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        independent = _independent_removal(
            board_before,
            best,
            defender_square,
            target_square,
            pv_after_best,
        )
        if independent is not None:
            candidate = item
            break
    concept_id = "tactic.removal_of_defender"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="shape:remove_the_guard",
        detector_version=REMOVAL_PROOF_VERSION,
        calculation_id="guard_scan_for_the_stored_capture",
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
        verifier_id="payoff_ply_defender_set_and_exchange",
        verifier_version=REMOVAL_PROOF_VERSION,
        calculation_id="defenders_and_exchange_read_at_the_payoff_ply",
        verified=independent is not None,
        acceptable_moves=(best.uci(),) if independent else (),
        facts=(independent,) if independent else (),
    )
    return RemovalDefenderProofBundle(detector=detector, verifier=verifier)
