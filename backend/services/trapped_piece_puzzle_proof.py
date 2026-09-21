"""Both sides of trapped-piece truth, each with independent escape proof.

A trapped piece has two faces and they are not the same claim:

* the MISTAKE side -- "your move trapped your OWN piece" -- which is
  `build_trapped_piece_proof`, unchanged and still the thing that fires on
  real games; and
* the OPPORTUNITY side -- "this move traps the OPPONENT's piece" -- which is
  `build_trapped_piece_opportunity_proof`, the thing a player is asked to find
  and what Lichess means by its `trappedPiece` theme.

Scoring the first against the second is a category error, not a bug report:
the mistake side returns 0.4% on that theme because the theme asks about the
other colour, one ply later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import chess

from services.board_concepts import (
    PIECE_NAMES,
    TRAPPABLE,
    TRAPPED_FLOOR_CP,
    enemy_trapped_pieces,
)
from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.chess_brain.detector_registry import detect_trapped_piece
from services.legal_exchange_verifier import independent_exchange_gain
from services.stored_line_verifier import parse_legal_move, replay_stored_line
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


# --- opportunity side -------------------------------------------------------
#
# Everything above proves "your move trapped your OWN piece". That is the
# mistake side, and it was the only side that existed. Scored against Lichess's
# `trappedPiece` theme it returns 0.4%, which is not a broken detector: the
# theme asks for the opposite thing. "Find the move that traps the OPPONENT's
# piece" is a different claim, about a different colour, one ply later. It
# needed its own proof rather than a loosened version of this one -- loosening
# this one to "an enemy piece is attacked and has nowhere good to go" was tried
# and reverted at 83.6% recall with 73.3% cross-fire on `fork`.

TRAPPED_PIECE_OPPORTUNITY_VERSION = "trapped_piece_opportunity_proof.v1"
TRAPPED_PIECE_OPPORTUNITY_QUALITY_ID = "tactic:trapped_enemy_piece_exact"
_MAX_TRAP_PLY = 4


@dataclass(frozen=True)
class TrappedPieceOpportunityProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = TRAPPED_PIECE_OPPORTUNITY_QUALITY_ID


def _victim_value_cp(item: Mapping[str, Any]) -> int:
    for piece_type, name in PIECE_NAMES.items():
        if name == item.get("piece"):
            return PIECE_VALUE_CP.get(piece_type, 0)
    return 0


def _independently_trapped_enemy(
    after: chess.Board,
    attacker: chess.Color,
    square: int,
) -> Optional[dict]:
    """Re-prove the trap from scratch, without the board_concepts detector.

    `after` is the real position, with the victim's owner to move. The escape
    enumeration in `_independently_trapped_at` wants the board from the
    attacker's side of the move, so the turn is handed over for it and handed
    back internally before any legal move is generated.
    """
    if after.turn == attacker or after.is_check():
        return None
    owner = not attacker
    if after.is_pinned(owner, square):
        return None
    attacker_view = after.copy(stack=False)
    attacker_view.ep_square = None
    attacker_view.turn = attacker
    return _independently_trapped_at(attacker_view, owner, square)


def _was_already_trapped(
    before: chess.Board,
    attacker: chess.Color,
    square: int,
) -> bool:
    """Was the victim already trapped before the initiator moved?

    The probe hands the victim's owner a free move in `before`. If the piece
    still cannot be saved with that extra tempo then the trap pre-dates the
    move, the move did not cause it, and we must not say that it did.

    The en passant square has to go before the turn is handed over: it belongs
    to the side about to move, so leaving it set while flipping the turn
    describes a position that cannot occur. That is not cosmetic. The first
    version of this probe treated the resulting invalid board as "already
    trapped", which silently discarded every trap sprung one move after a
    double pawn push -- 0BwIq (g4, then ...g6 on the h5 queen) and 0GYZd (g4,
    then ...Nf4 on the h3 queen) both measured as misses for that reason.
    """
    probe = before.copy(stack=False)
    probe.ep_square = None
    probe.turn = not attacker
    king_square = probe.king(attacker)
    if king_square is not None and probe.is_attacked_by(not attacker, king_square):
        # The attacker was in check, so handing the owner a free move describes
        # no reachable position and priorness cannot be established either way.
        return False
    name = chess.square_name(square)
    return any(
        item["square"] == name for item in enemy_trapped_pieces(probe, attacker)
    )


def _trap_anywhere_in_line(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
):
    """Find the initiator move that springs the trap, on or after `best`.

    Measured 2026-09-22 on 1000 Lichess `trappedPiece` puzzles rated 600-1500:
    the trap is on the solution move itself in 81.7% of them, but in a further
    15% the solution only starts the hunt and the piece is sealed one or two
    initiator moves later -- 00AhO is Bb7 (queen runs to a7) Ra8, and 00YeV is
    Bg5 (queen runs to g6) Nh4. Testing one move instead of the line scores
    those as misses even though the motif is plainly there, which is why this
    walks the line exactly as the fork proof does. Nothing is loosened: the
    same two gates and the same escape enumeration run, just from the ply where
    the trap actually closes.

    Returns (position_after_trap, trapping_move, victim_fact, ply_index) or
    None. ply_index 0 means the trap is on the best move itself.
    """
    replay = replay_stored_line(
        board_before, best, pv_after_best,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete:
        return None

    initiator = board_before.turn
    board = board_before.copy(stack=False)
    for index, uci in enumerate(replay.replayed_uci):
        if index > _MAX_TRAP_PLY:
            return None
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        if board.turn != initiator:
            board.push(move)
            continue
        before = board.copy(stack=False)
        board.push(move)
        candidates = [
            item
            for item in enemy_trapped_pieces(board, initiator)
            if not _was_already_trapped(
                before, initiator, chess.parse_square(item["square"])
            )
        ]
        if candidates:
            victim = max(candidates, key=_victim_value_cp)
            return board.copy(stack=False), move, victim, index
    return None


def build_trapped_piece_opportunity_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[TrappedPieceOpportunityProofBundle]:
    """Prove the player missed a move that traps one of the opponent's pieces."""
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    found = _trap_anywhere_in_line(board_before, best, pv_after_best)
    if found is None:
        return None
    after, trapping_move, victim, ply_index = found

    initiator = board_before.turn
    verified = _independently_trapped_enemy(
        after, initiator, chess.parse_square(victim["square"])
    )

    concept_id = "missed_tactic.trapped_enemy_piece"
    facts = dict(victim)
    facts["trapping_move"] = trapping_move.uci()
    facts["trap_ply_index"] = ply_index
    detector = DetectorProof(
        concept_id=concept_id,
        family="missed_tactic",
        detector_id="board_concepts:enemy_trapped_pieces",
        detector_version=TRAPPED_PIECE_OPPORTUNITY_VERSION,
        calculation_id="free_tempo_escape_enumeration_along_stored_line",
        facts=(facts,),
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
        verifier_version=TRAPPED_PIECE_OPPORTUNITY_VERSION,
        calculation_id="fresh_target_minimax_plus_every_legal_escape",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return TrappedPieceOpportunityProofBundle(detector=detector, verifier=verifier)
