"""Adapters from stored game-analysis records to the shared admission contract."""

from __future__ import annotations

import io
from typing import Any, Mapping, Optional, Tuple

import chess
import chess.pgn

from services.back_rank_mate_puzzle_proof import build_back_rank_mate_proof
from services.canonical_curriculum_puzzle_proof import (
    CurriculumProofBundle,
    build_exact_endgame_proof,
    build_exact_line_proofs,
    build_exact_opening_trap_position_proofs,
)
from services.aligned_tactic_puzzle_proof import build_aligned_tactic_proof
from services.discovered_attack_puzzle_proof import build_discovered_attack_proof
from services.destination_safety_puzzle_proof import build_destination_safety_proof
from services.forced_mate_puzzle_proof import build_forced_mate_proof
from services.free_piece_puzzle_proof import build_free_piece_proof
from services.fork_puzzle_proof import build_fork_proof
from services.removal_defender_puzzle_proof import build_removal_defender_proof
from services.trapped_piece_puzzle_proof import build_trapped_piece_proof
from services.piece_safety_puzzle_proof import build_piece_safety_proof
from services.verified_puzzle_admission import (
    AdmissionVerdict,
    PuzzleCandidate,
    StoredAnalysisEvidence,
    adjudicate_puzzle,
)


def source_ply_for_move(move_number: Any, user_color: str) -> int:
    number = int(move_number)
    if number < 1:
        raise ValueError("move_number must be one-based")
    return (number - 1) * 2 + (1 if str(user_color).lower() == "black" else 0)


def _position_fen(raw: Any) -> Optional[str]:
    try:
        board = raw if isinstance(raw, chess.Board) else chess.Board(str(raw))
        return " ".join(board.fen().split()[:4])
    except (TypeError, ValueError):
        return None


def resolve_source_ply(
    *,
    source_pgn: Any,
    stored_fen: Any,
    played_move: Any,
    preferred_ply: Optional[int],
) -> Optional[int]:
    """Find the exact PGN ply by board plus played move, then use preference."""
    if not source_pgn or not stored_fen:
        return preferred_ply
    wanted = _position_fen(stored_fen)
    if not wanted:
        return preferred_ply
    try:
        game = chess.pgn.read_game(io.StringIO(str(source_pgn)))
        if game is None:
            return preferred_ply
        board = game.board()
        matches = []
        for index, source_move in enumerate(game.mainline_moves()):
            if _position_fen(board) == wanted:
                supplied = _legal_uci(board, played_move)
                if supplied is None or supplied == source_move.uci():
                    matches.append(index)
            board.push(source_move)
    except (ValueError, TypeError, IndexError, AssertionError):
        return preferred_ply
    if preferred_ply in matches:
        return preferred_ply
    return matches[0] if len(matches) == 1 else preferred_ply


def _pv_moves(raw: Any) -> Tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    moves = []
    for item in raw:
        if isinstance(item, str) and item:
            moves.append(item)
        elif isinstance(item, Mapping):
            move = item.get("move") or item.get("san") or item.get("uci")
            if move:
                moves.append(str(move))
    return tuple(moves)


def _stored_analysis(move_evaluation: Mapping[str, Any], played, best) -> StoredAnalysisEvidence:
    return StoredAnalysisEvidence(
        played_move=str(played) if played else None,
        best_move=str(best) if best else None,
        cp_loss=move_evaluation.get("cp_loss"),
        eval_before=move_evaluation.get("eval_before"),
        eval_after=move_evaluation.get("eval_after"),
        pv_after_best=_pv_moves(move_evaluation.get("pv_after_best")),
        pv_after_played=_pv_moves(move_evaluation.get("pv_after_played")),
    )


def _legal_uci(board: chess.Board, raw: Any) -> Optional[str]:
    if not raw:
        return None
    try:
        move = chess.Move.from_uci(str(raw).lower())
        if move in board.legal_moves:
            return move.uci()
    except ValueError:
        pass
    try:
        return board.parse_san(str(raw)).uci()
    except (ValueError, AssertionError):
        return None


def _proof_fields(
    move_evaluation: Mapping[str, Any],
    played,
    best,
    *,
    source_pgn: Optional[str] = None,
    source_ply: Optional[int] = None,
):
    detector_proof = None
    verifier_proof = None
    quality_id = None
    verified_broad_category = None
    acceptable_moves: Tuple[str, ...] = ()
    if played and best:
        try:
            board = chess.Board(move_evaluation.get("fen_before"))
            played_uci = _legal_uci(board, played)
            best_uci = _legal_uci(board, best)
            curriculum = list(build_exact_line_proofs(
                source_pgn=source_pgn,
                source_ply=source_ply,
                best_move_uci=best_uci,
                cp_loss=move_evaluation.get("cp_loss"),
            ))
            curriculum.extend(build_exact_opening_trap_position_proofs(
                board_before=board,
                best_move_uci=best_uci,
                cp_loss=move_evaluation.get("cp_loss"),
            ))
            endgame = build_exact_endgame_proof(
                board,
                played_uci,
                best_uci,
                move_evaluation.get("cp_loss"),
            )
            if endgame:
                curriculum.append(endgame)
            forced_mate = build_forced_mate_proof(
                board,
                str(best),
                _pv_moves(move_evaluation.get("pv_after_best")),
                move_evaluation.get("cp_loss"),
            )
            back_rank_mate = build_back_rank_mate_proof(
                board,
                str(played),
                str(best),
                move_evaluation.get("cp_loss"),
            )
            free_piece = build_free_piece_proof(
                board,
                str(played),
                str(best),
                move_evaluation.get("cp_loss"),
            )
            fork = build_fork_proof(
                board,
                str(played),
                str(best),
                _pv_moves(move_evaluation.get("pv_after_best")),
                move_evaluation.get("cp_loss"),
            )
            aligned = build_aligned_tactic_proof(
                board,
                str(played),
                str(best),
                _pv_moves(move_evaluation.get("pv_after_best")),
                move_evaluation.get("cp_loss"),
            )
            discovered = build_discovered_attack_proof(
                board,
                str(played),
                str(best),
                _pv_moves(move_evaluation.get("pv_after_best")),
                move_evaluation.get("cp_loss"),
            )
            removal = build_removal_defender_proof(
                board,
                str(played),
                str(best),
                _pv_moves(move_evaluation.get("pv_after_best")),
                move_evaluation.get("cp_loss"),
            )
            piece_safety = build_piece_safety_proof(
                board, str(played), str(best), move_evaluation.get("cp_loss")
            )
            destination_safety = build_destination_safety_proof(
                board, dict(move_evaluation), played, best
            )
            trapped_piece = build_trapped_piece_proof(
                board, str(played), str(best), move_evaluation.get("cp_loss")
            )
        except (ValueError, TypeError):
            curriculum = []
            forced_mate = None
            back_rank_mate = None
            free_piece = None
            fork = None
            aligned = None
            discovered = None
            removal = None
            piece_safety = None
            destination_safety = None
            trapped_piece = None

        choices = list(curriculum)
        if forced_mate:
            choices.append(CurriculumProofBundle(
                detector=forced_mate.detector,
                verifier=forced_mate.verifier,
                quality_id=forced_mate.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=forced_mate.verifier.acceptable_moves,
                priority=500,
            ))
        if back_rank_mate:
            choices.append(CurriculumProofBundle(
                detector=back_rank_mate.detector,
                verifier=back_rank_mate.verifier,
                quality_id=back_rank_mate.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=back_rank_mate.verifier.acceptable_moves,
                priority=510,
            ))
        if free_piece:
            choices.append(CurriculumProofBundle(
                detector=free_piece.detector,
                verifier=free_piece.verifier,
                quality_id=free_piece.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=free_piece.verifier.acceptable_moves,
                priority=350,
            ))
        if fork:
            choices.append(CurriculumProofBundle(
                detector=fork.detector,
                verifier=fork.verifier,
                quality_id=fork.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=fork.verifier.acceptable_moves,
                priority=450,
            ))
        if aligned:
            choices.append(CurriculumProofBundle(
                detector=aligned.detector,
                verifier=aligned.verifier,
                quality_id=aligned.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=aligned.verifier.acceptable_moves,
                priority=425,
            ))
        if discovered:
            choices.append(CurriculumProofBundle(
                detector=discovered.detector,
                verifier=discovered.verifier,
                quality_id=discovered.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=discovered.verifier.acceptable_moves,
                priority=435,
            ))
        if removal:
            choices.append(CurriculumProofBundle(
                detector=removal.detector,
                verifier=removal.verifier,
                quality_id=removal.quality_id,
                broad_category="missed_tactic",
                acceptable_moves=removal.verifier.acceptable_moves,
                priority=410,
            ))
        if piece_safety:
            choices.append(CurriculumProofBundle(
                detector=piece_safety.detector,
                verifier=piece_safety.verifier,
                quality_id=piece_safety.quality_id,
                broad_category="piece_safety",
                acceptable_moves=piece_safety.verifier.acceptable_moves,
                priority=200,
            ))
        if destination_safety:
            choices.append(CurriculumProofBundle(
                detector=destination_safety.detector,
                verifier=destination_safety.verifier,
                quality_id=destination_safety.quality_id,
                broad_category="piece_safety",
                acceptable_moves=destination_safety.verifier.acceptable_moves,
                priority=250,
            ))
        if trapped_piece:
            choices.append(CurriculumProofBundle(
                detector=trapped_piece.detector,
                verifier=trapped_piece.verifier,
                quality_id=trapped_piece.quality_id,
                broad_category="piece_safety",
                acceptable_moves=trapped_piece.verifier.acceptable_moves,
                priority=225,
            ))
        # A high-priority candidate that fails its independent verifier must
        # not mask a lower-priority proof that is actually true. Failed
        # candidates belong in offline detector diagnostics, not the served
        # admission verdict.
        verified_choices = [
            item for item in choices if item.verifier.verified
        ]
        if verified_choices:
            bundle = max(verified_choices, key=lambda item: item.priority)
            detector_proof = bundle.detector
            verifier_proof = bundle.verifier
            quality_id = bundle.quality_id
            acceptable_moves = bundle.acceptable_moves
            if bundle.verifier.verified:
                verified_broad_category = bundle.broad_category
    return (
        detector_proof,
        verifier_proof,
        quality_id,
        verified_broad_category,
        acceptable_moves,
    )


def build_imported_game_verdict(
    *,
    game: Mapping[str, Any],
    move_evaluation: Mapping[str, Any],
    broad_category: Optional[str],
) -> AdmissionVerdict:
    """Adjudicate one stored user move without running a chess engine."""
    game_id = str(game.get("game_id") or "")
    user_color = str(game.get("user_color") or "white")
    move_number = move_evaluation.get("move_number")
    try:
        preferred_ply = source_ply_for_move(move_number, user_color)
    except (TypeError, ValueError):
        preferred_ply = None

    played = (
        move_evaluation.get("move")
        or move_evaluation.get("move_san")
        or move_evaluation.get("played_move")
    )
    best = (
        move_evaluation.get("best_move_uci")
        or move_evaluation.get("best_move_san")
        or move_evaluation.get("best_move")
    )
    source_ply = resolve_source_ply(
        source_pgn=game.get("pgn"),
        stored_fen=move_evaluation.get("fen_before"),
        played_move=played,
        preferred_ply=preferred_ply,
    )
    # Detection must not be gated by the legacy category. Otherwise an old
    # misclassification can hide the very false negative this verifier is
    # meant to repair. Run the causal piece-safety proof on every legal
    # analyzed user move; only promote the category when it independently
    # verifies the claim.
    detector_proof, verifier_proof, quality_id, verified_broad_category, accepted = (
        _proof_fields(
            move_evaluation,
            played,
            best,
            source_pgn=game.get("pgn"),
            source_ply=source_ply,
        )
    )

    return adjudicate_puzzle(PuzzleCandidate(
        source_kind="imported_game",
        source_ref=game_id,
        source_pgn=game.get("pgn"),
        source_ply=source_ply,
        stored_fen=move_evaluation.get("fen_before"),
        played_move=str(played) if played else None,
        analysis=_stored_analysis(move_evaluation, played, best),
        # Legacy labels do not become broad truth automatically. V1 has an
        # independent broad verifier only for causal piece safety; all other
        # unsupported labels safely become generic calculation exercises.
        broad_category=verified_broad_category,
        quality_id=quality_id,
        detector_proof=detector_proof,
        verifier_proof=verifier_proof,
        acceptable_moves=accepted,
    ))


def build_position_verdict(
    *,
    source_kind: str,
    source_ref: str,
    move_evaluation: Mapping[str, Any],
    broad_category: Optional[str],
) -> AdmissionVerdict:
    """Adjudicate a trusted stored position such as a coach session."""
    played = (
        move_evaluation.get("move")
        or move_evaluation.get("move_san")
        or move_evaluation.get("played_move")
    )
    best = (
        move_evaluation.get("best_move_uci")
        or move_evaluation.get("best_move_san")
        or move_evaluation.get("best_move")
    )
    detector, verifier, quality_id, verified_broad, accepted = _proof_fields(
        move_evaluation, played, best
    )
    return adjudicate_puzzle(PuzzleCandidate(
        source_kind=source_kind,
        source_ref=source_ref,
        source_position_fen=move_evaluation.get("fen_before"),
        stored_fen=move_evaluation.get("fen_before"),
        played_move=str(played) if played else None,
        analysis=_stored_analysis(move_evaluation, played, best),
        broad_category=verified_broad,
        quality_id=quality_id,
        detector_proof=detector,
        verifier_proof=verifier,
        acceptable_moves=accepted,
    ))
