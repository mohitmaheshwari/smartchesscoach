"""Exact back-rank mate proof over a stored best move.

The existing detector registry supplies the candidate.  This adapter promotes
the narrower lesson only after an independent terminal-board check proves the
classic geometry: a rook or queen mates a king on its home rank along that
rank.  No engine or runtime model is called.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import chess

from services.chess_brain.detector_registry import detect_back_rank
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof
from services.mate_lesson import back_rank_seal


BACK_RANK_MATE_PROOF_VERSION = "back_rank_mate_puzzle_proof.v1"
BACK_RANK_MATE_QUALITY_ID = "tactic:back_rank_mate_exact"


@dataclass(frozen=True)
class BackRankMateProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = BACK_RANK_MATE_QUALITY_ID


def _independent_back_rank_mate(
    board_before: chess.Board,
    best: chess.Move,
) -> Optional[dict]:
    attacker = board_before.turn
    moving_piece = board_before.piece_at(best.from_square)
    if moving_piece is None or moving_piece.color != attacker:
        return None
    if moving_piece.piece_type not in (chess.ROOK, chess.QUEEN):
        return None

    after = board_before.copy(stack=False)
    after.push(best)
    if not after.is_checkmate() or after.turn == attacker:
        return None
    king_square = after.king(after.turn)
    if king_square is None:
        return None
    home_rank = 0 if after.turn == chess.WHITE else 7
    if (
        chess.square_rank(king_square) != home_rank
        or chess.square_rank(best.to_square) != home_rank
    ):
        return None
    checker = after.piece_at(best.to_square)
    if (
        checker is None
        or checker.color != attacker
        or checker.piece_type not in (chess.ROOK, chess.QUEEN)
        or best.to_square not in after.checkers()
    ):
        return None

    # The motif is the king trapped by ITS OWN PAWNS. Everything above is
    # satisfied by any rook or queen mate delivered along the home rank,
    # including one where the king's escape squares are covered by ENEMY
    # pieces -- a fine mate, but not this lesson.
    #
    # Measured 2026-09-21 on 1000 Lichess mateIn1 puzzles: the verifier
    # fired 205 times, and only 82 of those (40%) had the king sealed by
    # its own pawns. 123 fires were rank mates wearing the wrong name, and
    # a caption saying "your own pawns trapped your king" would have been
    # wrong 60% of the time it spoke.
    #
    # back_rank_seal already tests exactly this and already lives in
    # services/mate_lesson.py. It was simply never called from here.
    seal = back_rank_seal(after, best, king_square, after.turn)
    if seal < 2:
        return None

    return {
        "own_pawns_sealing_king": seal,
        "mating_piece": chess.piece_name(checker.piece_type),
        "mating_square": chess.square_name(best.to_square),
        "king_square": chess.square_name(king_square),
        "home_rank": home_rank + 1,
    }


def build_back_rank_mate_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    cp_loss: Any,
) -> Optional[BackRankMateProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    try:
        candidate = detect_back_rank(
            board_before,
            board_before.san(played),
            board_before.san(best),
            {},
        )
    except (ValueError, AssertionError):
        return None
    if not candidate.detected:
        return None

    verified = _independent_back_rank_mate(board_before, best)
    concept_id = "tactic.back_rank_mate"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="canonical_back_rank_detector",
        detector_version=BACK_RANK_MATE_PROOF_VERSION,
        calculation_id="registry_terminal_mate_candidate",
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
        verifier_id="independent_back_rank_terminal_geometry",
        verifier_version=BACK_RANK_MATE_PROOF_VERSION,
        calculation_id="fresh_mate_board_heavy_piece_home_rank_check",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return BackRankMateProofBundle(detector=detector, verifier=verifier)
