"""Deterministic missed-mate proof over already stored engine continuations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.missed_mate_detector import detect_missed_mate
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


FORCED_MATE_PROOF_VERSION = "forced_mate_puzzle_proof.v2"
FORCED_MATE_QUALITY_ID = "tactic:forced_mate_exact"


@dataclass(frozen=True)
class ForcedMateProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = FORCED_MATE_QUALITY_ID


def _terminal_mate_candidate(
    board_before: chess.Board,
    best: chess.Move,
    continuation: Sequence[Any],
) -> Optional[dict]:
    """Independent UCI/SAN walk for stored lines without a `#` marker."""
    tokens = []
    for raw in continuation:
        if isinstance(raw, dict):
            raw = raw.get("move") or raw.get("san") or raw.get("uci")
        if raw:
            tokens.append(str(raw))
    first = parse_legal_move(board_before, tokens[0]) if tokens else None
    full = ([] if first == best else [best.uci()]) + tokens
    if not full or len(full) > 64:
        return None
    board = board_before.copy(stack=False)
    initiator = board.turn
    mate_ply = None
    for index, raw in enumerate(full, start=1):
        move = parse_legal_move(board, raw)
        if move is None:
            return None
        mover = board.turn
        board.push(move)
        if board.is_checkmate():
            if index != len(full) or mover != initiator:
                return None
            mate_ply = index
    if mate_ply is None:
        return None
    return {
        "kind": "mate_in_1" if mate_ply == 1 else "forced_mate",
        "mate_in": (mate_ply + 1) // 2,
        "source": "terminal_legal_line",
    }


def build_forced_mate_proof(
    board_before: chess.Board,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[ForcedMateProofBundle]:
    """Build marker-based candidate plus independent legal mate replay."""
    try:
        best = parse_legal_move(board_before, best_move)
        if best is None:
            return None
        best_san = board_before.san(best)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError, AssertionError):
        return None

    tokens = tuple(str(raw) for raw in pv_after_best)
    candidate = detect_missed_mate(
        board_before,
        best_san,
        list(tokens),
        loss,
    )
    if not candidate:
        candidate = _terminal_mate_candidate(
            board_before, best, pv_after_best
        )
    if not candidate:
        return None

    replay = replay_stored_line(board_before, best, pv_after_best)
    verified = bool(
        replay.complete
        and replay.checkmate
        and replay.checkmating_color == board_before.turn
    )
    concept_id = (
        "tactic.mate_in_one"
        if candidate.get("kind") == "mate_in_1"
        else "tactic.forced_mate"
    )
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="canonical_missed_mate_detector",
        detector_version=FORCED_MATE_PROOF_VERSION,
        calculation_id="stored_pv_mate_marker_scan",
        facts=({
            "kind": candidate.get("kind"),
            "claimed_mate_in": candidate.get("mate_in"),
        },),
        acceptable_moves=(best.uci(),),
        counterfactual={"best_move": best.uci(), "cp_loss": loss},
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_legal_checkmate_replay",
        verifier_version=FORCED_MATE_PROOF_VERSION,
        calculation_id="full_legal_line_terminal_state",
        verified=verified and loss >= 100,
        acceptable_moves=(best.uci(),) if verified and loss >= 100 else (),
        facts=({
            "mate_ply": replay.mate_ply,
            "replayed_uci": replay.replayed_uci,
        },),
    )
    return ForcedMateProofBundle(detector=detector, verifier=verifier)
