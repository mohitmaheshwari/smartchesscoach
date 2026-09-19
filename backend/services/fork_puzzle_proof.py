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
from services.stored_line_verifier import (
    STORED_LINE_VERIFIER_VERSION,
    parse_legal_move,
    replay_stored_line,
)
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


FORK_REASON_SEMANTIC_VERSION = "fork_created_reason.v1"


def _piece_name_at(board: chess.Board, square_name: str) -> str:
    piece = board.piece_at(chess.parse_square(square_name))
    return chess.piece_name(piece.piece_type) if piece else "piece"


def _describe(board: chess.Board, square_name: str) -> str:
    return f"the {_piece_name_at(board, square_name)} on {square_name}"


def _join(values) -> str:
    items = [str(value) for value in values if value]
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def build_fork_created_reason_bundle(fen: str, supplied_move: str):
    """Ask what the move forks, using only geometry this detector proved.

    Why this exists: every diagnostic question was a piece-safety question,
    including on fork puzzles, because `build_reason_bundle_for_move`
    dispatched on one quality id. The fork geometry was already proven and
    already authorized at CAPTION grade -- it simply was not reachable from
    the reason layer.

    Deliberately narrow. `verify_created_fork` proves that the moved piece
    attacks two or more enemy pieces; it does NOT prove the fork wins
    material. So the question asks what is attacked, never what is won. A
    "you win a piece" claim would need the payoff proof, which is a different
    entry point with a stored continuation.

    Abstains (no components) rather than guessing when it cannot build a
    distractor that is provably false.
    """
    from services.teaching_reason_contracts import (
        ReasonComponent,
        ReasonProof,
        TeachingReasonBundle,
        build_reason_choices,
    )
    import hashlib
    import json as _json

    board = chess.Board(str(fen or ""))
    move = parse_legal_move(board, supplied_move)
    if move is None:
        raise ValueError("illegal move")
    move_san = board.san(move)

    normalized = " ".join(board.fen().split()[:4])
    position_fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    proof = ReasonProof(
        authority="independent_fork_geometry",
        quality_id=FORK_QUALITY_ID,
        detector_version=FORK_PROOF_VERSION,
        verifier_version=STORED_LINE_VERIFIER_VERSION,
        fingerprint=hashlib.sha256(
            _json.dumps(
                {"position": position_fingerprint, "move": move.uci()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    )

    geometry = verify_created_fork(board, move)
    if not geometry:
        return TeachingReasonBundle(
            semantic_version=FORK_REASON_SEMANTIC_VERSION,
            position_fingerprint=position_fingerprint,
            move_uci=move.uci(),
            move_san=move_san,
            target_result="unmeasured",
            safety_kind="no_fork_created",
            components=(),
            proof=proof,
        )

    after = board.copy(stack=False)
    after.push(move)
    targets = list(geometry["targets"])
    forking_piece = geometry["forking_piece"]
    fork_square = geometry["fork_square"]
    attacked = set(after.attacks(move.to_square))

    # A false alternative must be provably false: same number of enemy
    # pieces, at least one of which this move does not attack.
    decoys = sorted(
        chess.square_name(square)
        for square, piece in after.piece_map().items()
        if piece.color != board.turn and square not in attacked
    )
    if not decoys:
        return TeachingReasonBundle(
            semantic_version=FORK_REASON_SEMANTIC_VERSION,
            position_fingerprint=position_fingerprint,
            move_uci=move.uci(),
            move_san=move_san,
            target_result="unmeasured",
            safety_kind="no_provable_distractor",
            components=(),
            proof=proof,
        )

    correct_label = f"{_join([_describe(after, square) for square in targets]).capitalize()}."
    false_squares = [targets[0], decoys[0]]
    false_label = f"{_join([_describe(after, square) for square in false_squares]).capitalize()}."

    # A king among the targets makes this a royal fork, and the teaching is
    # different in kind: check FORCES a reply, which is what leaves the other
    # piece behind. Without a king, "one of them must fall" is not something
    # this detector proved -- both could be defended, or one recaptured -- so
    # the wording stays descriptive rather than asserting a general rule.
    king_square = next(
        (
            square for square in targets
            if (piece := after.piece_at(chess.parse_square(square))) is not None
            and piece.piece_type == chess.KING
        ),
        None,
    )
    others = [square for square in targets if square != king_square]
    others_text = _join([_describe(after, square) for square in others])
    all_text = _join([_describe(after, square) for square in targets])
    count_word = "two" if len(targets) == 2 else str(len(targets))

    if king_square and others:
        prompt = (
            f"After {move_san}, your {forking_piece} on {fork_square} gives "
            f"check and attacks something else at the same time. What else "
            f"does it attack, besides the king?"
        )
        correct_label = f"{others_text.capitalize()}."
        false_label = f"{_describe(after, decoys[0]).capitalize()}."
        success_text = (
            f"Your {forking_piece} on {fork_square} checks the king on "
            f"{king_square} and attacks {others_text} at the same time. "
            f"The check has to be answered first, so {others_text} is left "
            f"to be taken."
        )
        correction_text = (
            f"From {fork_square} the {forking_piece} checks the king on "
            f"{king_square} and also attacks {others_text}. A check must be "
            f"answered immediately -- that is what leaves the other piece "
            f"behind. When you check, look at what else the checking piece hits."
        )
    else:
        prompt = (
            f"After {move_san}, your {forking_piece} on {fork_square} attacks "
            f"{count_word} of your opponent's pieces at once. Which ones?"
        )
        success_text = (
            f"Your {forking_piece} on {fork_square} attacks {all_text} "
            f"at the same time."
        )
        correction_text = (
            f"From {fork_square} the {forking_piece} attacks {all_text}. "
            f"Before you move a piece, check every square it will attack from "
            f"its new home -- one move can hit two things at once."
        )

    seed = f"{position_fingerprint}|{move.uci()}|fork_targets"
    choices, accepted = build_reason_choices(seed, correct_label, false_label)
    component = ReasonComponent(
        question_id=hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        kind="fork_targets",
        prompt=prompt,
        choices=choices,
        accepted_choice_ids=accepted,
        facts={
            "fork_square": fork_square,
            "forking_piece": forking_piece,
            "target_squares": list(targets),
            "proves_material_gain": False,
        },
        success_text=success_text,
        correction_text=correction_text,
    )
    return TeachingReasonBundle(
        semantic_version=FORK_REASON_SEMANTIC_VERSION,
        position_fingerprint=position_fingerprint,
        move_uci=move.uci(),
        move_san=move_san,
        target_result="pass",
        safety_kind="fork_created",
        components=(component,),
        proof=proof,
    )
