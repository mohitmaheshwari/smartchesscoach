"""Shared deterministic admission contract for every training position.

This module does not detect chess concepts. It validates canonical provenance,
stored analysis, legal answer sets, independent detector proof and authorization,
then chooses the most specific honest teaching level. It contains no Stockfish,
LLM, network or authored chess-content dependency.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import chess
import chess.pgn

from services.detector_quality import QualitySurface, grade_for, is_authorized


ADMISSION_VERSION = "verified_puzzle_admission.v2"


class AdmissionStatus(str, Enum):
    SPECIFIC = "specific"
    BROAD = "broad"
    GENERIC = "generic"
    QUARANTINE = "quarantine"


class AdmissionReason(str, Enum):
    SPECIFIC_PROOF_VERIFIED = "specific_proof_verified"
    SPECIFIC_PROOF_UNAUTHORIZED = "specific_proof_unauthorized"
    SPECIFIC_PROOF_MISMATCH = "specific_proof_mismatch"
    BROAD_CATEGORY_VERIFIED = "broad_category_verified"
    GENERIC_ANSWER_VERIFIED = "generic_answer_verified"
    SOURCE_UNRECONSTRUCTABLE = "source_unreconstructable"
    SOURCE_MOVE_MISMATCH = "source_move_mismatch"
    STORED_FEN_MISMATCH = "stored_fen_mismatch"
    PLAYED_MOVE_ILLEGAL = "played_move_illegal"
    BEST_MOVE_ILLEGAL = "best_move_illegal"
    ACCEPTABLE_MOVE_ILLEGAL = "acceptable_move_illegal"
    ANSWER_SET_MISMATCH = "answer_set_mismatch"
    NO_VERIFIED_ANSWER = "no_verified_answer"
    CROSS_POOL_ANSWER_CONFLICT = "cross_pool_answer_conflict"


@dataclass(frozen=True)
class StoredAnalysisEvidence:
    played_move: Optional[str] = None
    best_move: Optional[str] = None
    cp_loss: Optional[float] = None
    eval_before: Optional[float] = None
    eval_after: Optional[float] = None
    pv_after_best: Tuple[str, ...] = ()
    pv_after_played: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DetectorProof:
    concept_id: str
    family: str
    detector_id: str
    detector_version: str
    calculation_id: str
    facts: Tuple[Mapping[str, Any], ...] = ()
    acceptable_moves: Tuple[str, ...] = ()
    counterfactual: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifierProof:
    concept_id: str
    verifier_id: str
    verifier_version: str
    calculation_id: str
    verified: bool
    acceptable_moves: Tuple[str, ...] = ()
    facts: Tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class PuzzleCandidate:
    source_kind: str
    source_ref: str
    source_pgn: Optional[str] = None
    source_ply: Optional[int] = None
    source_position_fen: Optional[str] = None
    stored_fen: Optional[str] = None
    played_move: Optional[str] = None
    analysis: StoredAnalysisEvidence = field(default_factory=StoredAnalysisEvidence)
    broad_category: Optional[str] = None
    quality_id: Optional[str] = None
    detector_proof: Optional[DetectorProof] = None
    verifier_proof: Optional[VerifierProof] = None
    acceptable_moves: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmissionVerdict:
    status: AdmissionStatus
    reason_codes: Tuple[str, ...]
    source_kind: str
    source_fingerprint: str
    analysis_fingerprint: str
    reconstructed_fen: Optional[str]
    played_move_uci: Optional[str]
    acceptable_moves_uci: Tuple[str, ...]
    concept_id: Optional[str]
    broad_category: Optional[str]
    detector_id: Optional[str]
    detector_version: Optional[str]
    verifier_id: Optional[str]
    verifier_version: Optional[str]
    quality_id: Optional[str]
    quality_grade: Optional[str]
    detector_facts: Tuple[Mapping[str, Any], ...] = ()
    verifier_facts: Tuple[Mapping[str, Any], ...] = ()
    admission_version: str = ADMISSION_VERSION

    def to_document(self) -> Dict[str, Any]:
        document = asdict(self)
        document["status"] = self.status.value
        document["verdict_fingerprint"] = _stable_hash(document)
        return document


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _normalized_position_fen(board_or_fen: Any) -> str:
    board = board_or_fen if isinstance(board_or_fen, chess.Board) else chess.Board(str(board_or_fen))
    fields = board.fen().split()
    return " ".join(fields[:4])


def _parse_legal_move(board: chess.Board, raw: Optional[str]) -> Optional[chess.Move]:
    if not raw or not isinstance(raw, str):
        return None
    token = raw.strip()
    if not token:
        return None
    try:
        move = chess.Move.from_uci(token)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(token)
    except ValueError:
        return None


def stored_verdict_is_structurally_current(puzzle: Mapping[str, Any]) -> bool:
    """Validate a persisted verdict before any reader trusts its answer."""
    verdict = puzzle.get("verified_admission") or {}
    if not isinstance(verdict, Mapping):
        return False
    frozen = dict(verdict)
    supplied_fingerprint = frozen.pop("verdict_fingerprint", None)
    if (
        not _is_sha256(supplied_fingerprint)
        or supplied_fingerprint != _stable_hash(frozen)
    ):
        return False
    status = verdict.get("status")
    if verdict.get("admission_version") != ADMISSION_VERSION:
        return False
    if status not in {item.value for item in AdmissionStatus}:
        return False
    if not (
        verdict.get("reason_codes")
        and verdict.get("source_kind")
        and _is_sha256(verdict.get("source_fingerprint"))
        and _is_sha256(verdict.get("analysis_fingerprint"))
    ):
        return False
    # A complete quarantine verdict deliberately has no playable answer.
    if status == AdmissionStatus.QUARANTINE.value:
        return not verdict.get("acceptable_moves_uci")

    try:
        board = chess.Board(str(puzzle.get("fen")))
        reconstructed = _normalized_position_fen(verdict.get("reconstructed_fen"))
        if reconstructed != _normalized_position_fen(board):
            return False
        if _parse_legal_move(board, verdict.get("played_move_uci")) is None:
            return False
        accepted = tuple(verdict.get("acceptable_moves_uci") or ())
        if not accepted:
            return False
        if any(_parse_legal_move(board, str(raw)) is None for raw in accepted):
            return False
        primary_raw = puzzle.get("best_move_uci") or puzzle.get("best_move_san")
        if primary_raw:
            primary = _parse_legal_move(board, str(primary_raw))
            if primary is None or primary.uci() not in accepted:
                return False
    except (TypeError, ValueError):
        return False

    if status == AdmissionStatus.SPECIFIC.value:
        required = (
            "concept_id", "broad_category", "detector_id", "detector_version",
            "verifier_id", "verifier_version", "quality_id", "quality_grade",
        )
        if any(not verdict.get(field) for field in required):
            return False
        if verdict.get("detector_id") == verdict.get("verifier_id"):
            return False
        quality_id = str(verdict.get("quality_id"))
        if (
            not is_authorized(quality_id, QualitySurface.PROMPT)
            or verdict.get("quality_grade") != grade_for(quality_id).value
        ):
            return False
        detector_facts = verdict.get("detector_facts") or ()
        verifier_facts = verdict.get("verifier_facts") or ()
        if (
            not detector_facts
            or not verifier_facts
            or any(not isinstance(item, Mapping) for item in detector_facts)
            or any(not isinstance(item, Mapping) for item in verifier_facts)
        ):
            return False
    elif status == AdmissionStatus.BROAD.value:
        if (
            not verdict.get("broad_category")
            or verdict.get("concept_id")
            or len(accepted) != 1
        ):
            return False
    elif (
        verdict.get("concept_id")
        or verdict.get("broad_category")
        or len(accepted) != 1
    ):
        return False
    return True


def _reconstruct(candidate: PuzzleCandidate) -> Tuple[chess.Board, Optional[chess.Move]]:
    if candidate.source_pgn is not None:
        if candidate.source_ply is None or candidate.source_ply < 0:
            raise ValueError("source_ply is required for PGN sources")
        game = chess.pgn.read_game(io.StringIO(candidate.source_pgn))
        if game is None:
            raise ValueError("invalid PGN")
        board = game.board()
        moves = list(game.mainline_moves())
        if candidate.source_ply >= len(moves):
            raise ValueError("source_ply is outside mainline")
        for move in moves[: candidate.source_ply]:
            if move not in board.legal_moves:
                raise ValueError("illegal PGN mainline")
            board.push(move)
        source_move = moves[candidate.source_ply]
        if source_move not in board.legal_moves:
            raise ValueError("illegal source move")
        return board, source_move

    if candidate.source_position_fen is not None:
        return chess.Board(candidate.source_position_fen), None

    raise ValueError("no canonical source position")


def _quarantine(
    candidate: PuzzleCandidate,
    reason: AdmissionReason,
    source_fingerprint: str,
    analysis_fingerprint: str,
    reconstructed_fen: Optional[str] = None,
) -> AdmissionVerdict:
    return AdmissionVerdict(
        status=AdmissionStatus.QUARANTINE,
        reason_codes=(reason.value,),
        source_kind=candidate.source_kind,
        source_fingerprint=source_fingerprint,
        analysis_fingerprint=analysis_fingerprint,
        reconstructed_fen=reconstructed_fen,
        played_move_uci=None,
        acceptable_moves_uci=(),
        concept_id=None,
        broad_category=None,
        detector_id=None,
        detector_version=None,
        verifier_id=None,
        verifier_version=None,
        quality_id=candidate.quality_id,
        quality_grade=None,
    )


def adjudicate_puzzle(candidate: PuzzleCandidate) -> AdmissionVerdict:
    """Return the most specific deterministic verdict supported by evidence."""
    source_fingerprint = _stable_hash({
        "source_kind": candidate.source_kind,
        "source_pgn": candidate.source_pgn,
        "source_ply": candidate.source_ply,
        "source_position_fen": candidate.source_position_fen,
    })
    analysis_fingerprint = _stable_hash(asdict(candidate.analysis))

    try:
        board, source_move = _reconstruct(candidate)
    except (ValueError, TypeError, IndexError):
        return _quarantine(
            candidate, AdmissionReason.SOURCE_UNRECONSTRUCTABLE,
            source_fingerprint, analysis_fingerprint,
        )

    reconstructed_fen = board.fen()
    if candidate.stored_fen:
        try:
            stored_position = _normalized_position_fen(candidate.stored_fen)
        except (ValueError, TypeError):
            return _quarantine(
                candidate, AdmissionReason.STORED_FEN_MISMATCH,
                source_fingerprint, analysis_fingerprint, reconstructed_fen,
            )
        if stored_position != _normalized_position_fen(board):
            return _quarantine(
                candidate, AdmissionReason.STORED_FEN_MISMATCH,
                source_fingerprint, analysis_fingerprint, reconstructed_fen,
            )

    played_raw = candidate.played_move or candidate.analysis.played_move
    played_move = source_move if played_raw is None else _parse_legal_move(board, played_raw)
    if played_move is None:
        return _quarantine(
            candidate, AdmissionReason.PLAYED_MOVE_ILLEGAL,
            source_fingerprint, analysis_fingerprint, reconstructed_fen,
        )
    if source_move is not None and played_move != source_move:
        return _quarantine(
            candidate, AdmissionReason.SOURCE_MOVE_MISMATCH,
            source_fingerprint, analysis_fingerprint, reconstructed_fen,
        )

    # The stored analysis best move is the only generic answer. Detector
    # proposals and caller-supplied alternatives are never allowed to widen a
    # playable answer set on their own.
    answer_moves: Dict[str, chess.Move] = {}
    best_raw = candidate.analysis.best_move
    best_move_uci = None
    if best_raw:
        best_move = _parse_legal_move(board, best_raw)
        if best_move is None:
            return _quarantine(
                candidate, AdmissionReason.BEST_MOVE_ILLEGAL,
                source_fingerprint, analysis_fingerprint, reconstructed_fen,
            )
        best_move_uci = best_move.uci()
        answer_moves[best_move_uci] = best_move

    # Candidate alternatives are metadata only. Validate their syntax so bad
    # source data still fails closed, but never promote them into grading.
    for raw in candidate.acceptable_moves:
        if _parse_legal_move(board, raw) is None:
            return _quarantine(
                candidate, AdmissionReason.ACCEPTABLE_MOVE_ILLEGAL,
                source_fingerprint, analysis_fingerprint, reconstructed_fen,
            )

    detector = candidate.detector_proof
    verifier = candidate.verifier_proof
    proof_reason = None
    proof_valid = False
    if detector and verifier:
        detector_answers = {
            move.uci()
            for raw in detector.acceptable_moves
            if (move := _parse_legal_move(board, raw)) is not None
        }
        verifier_answers = {
            move.uci()
            for raw in verifier.acceptable_moves
            if (move := _parse_legal_move(board, raw)) is not None
        }
        independent = (
            detector.detector_id != verifier.verifier_id
            and detector.calculation_id != verifier.calculation_id
        )
        same_claim = detector.concept_id == verifier.concept_id
        same_answers = bool(
            detector_answers
            and verifier_answers
            and detector_answers == verifier_answers
            and best_move_uci
            and best_move_uci in detector_answers
        )
        proof_valid = verifier.verified and independent and same_claim and same_answers
        if not same_answers:
            proof_reason = AdmissionReason.ANSWER_SET_MISMATCH
        elif not proof_valid:
            proof_reason = AdmissionReason.SPECIFIC_PROOF_MISMATCH

    if not answer_moves:
        return _quarantine(
            candidate, AdmissionReason.NO_VERIFIED_ANSWER,
            source_fingerprint, analysis_fingerprint, reconstructed_fen,
        )

    if proof_valid and detector and verifier and candidate.quality_id:
        grade = grade_for(candidate.quality_id).value
        if is_authorized(candidate.quality_id, QualitySurface.PROMPT):
            return AdmissionVerdict(
                status=AdmissionStatus.SPECIFIC,
                reason_codes=(AdmissionReason.SPECIFIC_PROOF_VERIFIED.value,),
                source_kind=candidate.source_kind,
                source_fingerprint=source_fingerprint,
                analysis_fingerprint=analysis_fingerprint,
                reconstructed_fen=reconstructed_fen,
                played_move_uci=played_move.uci(),
                acceptable_moves_uci=tuple(sorted(detector_answers)),
                concept_id=detector.concept_id,
                broad_category=candidate.broad_category,
                detector_id=detector.detector_id,
                detector_version=detector.detector_version,
                verifier_id=verifier.verifier_id,
                verifier_version=verifier.verifier_version,
                quality_id=candidate.quality_id,
                quality_grade=grade,
                detector_facts=tuple(detector.facts),
                verifier_facts=tuple(verifier.facts),
            )
        proof_reason = AdmissionReason.SPECIFIC_PROOF_UNAUTHORIZED

    if candidate.broad_category:
        reasons = [AdmissionReason.BROAD_CATEGORY_VERIFIED.value]
        if proof_reason:
            reasons.insert(0, proof_reason.value)
        return AdmissionVerdict(
            status=AdmissionStatus.BROAD,
            reason_codes=tuple(reasons),
            source_kind=candidate.source_kind,
            source_fingerprint=source_fingerprint,
            analysis_fingerprint=analysis_fingerprint,
            reconstructed_fen=reconstructed_fen,
            played_move_uci=played_move.uci(),
            acceptable_moves_uci=tuple(sorted(answer_moves)),
            concept_id=None,
            broad_category=candidate.broad_category,
            detector_id=detector.detector_id if detector else None,
            detector_version=detector.detector_version if detector else None,
            verifier_id=verifier.verifier_id if verifier else None,
            verifier_version=verifier.verifier_version if verifier else None,
            quality_id=candidate.quality_id,
            quality_grade=grade_for(candidate.quality_id).value if candidate.quality_id else None,
            detector_facts=tuple(detector.facts) if detector else (),
            verifier_facts=tuple(verifier.facts) if verifier else (),
        )

    reasons = [AdmissionReason.GENERIC_ANSWER_VERIFIED.value]
    if proof_reason:
        reasons.insert(0, proof_reason.value)
    return AdmissionVerdict(
        status=AdmissionStatus.GENERIC,
        reason_codes=tuple(reasons),
        source_kind=candidate.source_kind,
        source_fingerprint=source_fingerprint,
        analysis_fingerprint=analysis_fingerprint,
        reconstructed_fen=reconstructed_fen,
        played_move_uci=played_move.uci(),
        acceptable_moves_uci=tuple(sorted(answer_moves)),
        concept_id=None,
        broad_category=None,
        detector_id=detector.detector_id if detector else None,
        detector_version=detector.detector_version if detector else None,
        verifier_id=verifier.verifier_id if verifier else None,
        verifier_version=verifier.verifier_version if verifier else None,
        quality_id=candidate.quality_id,
        quality_grade=grade_for(candidate.quality_id).value if candidate.quality_id else None,
        detector_facts=tuple(detector.facts) if detector else (),
        verifier_facts=tuple(verifier.facts) if verifier else (),
    )
