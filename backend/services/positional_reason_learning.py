"""Authoring contract for reviewed positional teaching reasons.

This module does not generate player-facing captions. It turns one admin review
into auditable candidate evidence. Runtime authority still belongs to promoted
caption-principle detectors and their independent verifiers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Dict, Iterable, Mapping, Optional

import chess

from services.teaching_reason_contracts import ReasonProof


SCHEMA_VERSION = "positional_reason_candidate.v1"
VERIFIER_VERSION = "contrastive_admin.v1"

DISPOSITION_LABELS: Dict[str, str] = {
    "eligible_positional": "Eligible positional mistake",
    "not_mistake": "Not a meaningful mistake",
    "already_decided": "Position was already decided",
    "tactical_or_forced": "Tactical or forced",
    "duplicate": "Duplicate teaching example",
    "unstable_engine_choice": "Engine choice is unstable",
    "insufficient_evidence": "Not enough evidence",
}
INELIGIBLE_DISPOSITIONS = frozenset(
    key for key in DISPOSITION_LABELS if key != "eligible_positional"
)
TEACHING_FIELDS = (
    "better_move_fact",
    "played_move_fact",
    "contrast",
    "transferable_lesson",
)
_MAX_TEXT = 1200
_MAX_LABEL = 100

_JARGON_REPLACEMENTS = {
    "fianchetto": "name the bishop and its diagonal",
    "prophylaxis": "stopping their threat before they make it",
    "zwischenzug": "an in-between move",
    "zugzwang": "every legal move makes the position worse",
    "luft": "an escape square for the king",
    "opposition": "describe how the kings face each other",
    "outpost": "name the square and why a pawn cannot chase the piece",
}
_CP_AS_MATERIAL = re.compile(
    r"\b(?:drops?|loses?|costs?)\s+(?:about\s+)?\d+(?:\.\d+)?\s+pawns?\b",
    re.IGNORECASE,
)
_SQUARE = re.compile(r"\b[a-h][1-8]\b", re.IGNORECASE)


class PositionalReasonValidationError(ValueError):
    pass


def _clean_text(value: Any, field_name: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise PositionalReasonValidationError(f"{field_name} is required")
    if len(text) > _MAX_TEXT:
        raise PositionalReasonValidationError(f"{field_name} is too long")
    return text


def normalized_fen(fen: str) -> str:
    """Normalize away clocks while preserving all position semantics."""
    try:
        board = chess.Board(str(fen or "").strip())
    except ValueError as exc:
        raise PositionalReasonValidationError("fen is not a legal position") from exc
    return " ".join(board.fen().split()[:4])


def position_fingerprint(fen: str, played_uci: str, best_uci: str) -> str:
    identity = "|".join(
        (normalized_fen(fen), str(played_uci or "").strip(), str(best_uci or "").strip())
    )
    return sha256(identity.encode("utf-8")).hexdigest()


def _phase(board: chess.Board) -> str:
    men = len(board.piece_map())
    if men <= 8:
        return "bare_endgame"
    if men <= 14:
        return "endgame"
    has_queen = bool(
        board.pieces(chess.QUEEN, chess.WHITE)
        or board.pieces(chess.QUEEN, chess.BLACK)
    )
    return "middlegame_with_queens" if has_queen else "middlegame"


def _destination_zone(square: int) -> str:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    if 2 <= file_index <= 5 and 2 <= rank_index <= 5:
        return "center"
    if file_index in (0, 7) or rank_index in (0, 7):
        return "edge"
    return "near_center"


def _center_distance(square: int) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    return min(
        abs(file_index - center_file) + abs(rank_index - center_rank)
        for center_file in (3, 4)
        for center_rank in (3, 4)
    )


def _file_state(board: chess.Board, file_index: int, mover: chess.Color) -> str:
    own_pawns = any(
        chess.square_file(square) == file_index
        for square in board.pieces(chess.PAWN, mover)
    )
    other_pawns = any(
        chess.square_file(square) == file_index
        for square in board.pieces(chess.PAWN, not mover)
    )
    if not own_pawns and not other_pawns:
        return "open"
    if not own_pawns:
        return "semi_open"
    return "pawn_blocked"


def _move_profile(board: chess.Board, move: chess.Move) -> Dict[str, Any]:
    piece = board.piece_at(move.from_square)
    if piece is None or move not in board.legal_moves:
        raise PositionalReasonValidationError("stored move is not legal in the position")
    mover = board.turn
    capture = board.is_capture(move)
    after = board.copy()
    after.push(move)
    profile: Dict[str, Any] = {
        "piece": chess.piece_name(piece.piece_type),
        "capture": capture,
        "check": after.is_check(),
        "castle": board.is_castling(move),
        "promotion": bool(move.promotion),
        "destination_zone": _destination_zone(move.to_square),
        "centralizes": _center_distance(move.to_square) < _center_distance(move.from_square),
        "destination_defended": bool(after.attackers(mover, move.to_square)),
        "activity_after": len(after.attacks(move.to_square)),
    }
    if piece.piece_type == chess.ROOK:
        profile["rook_file"] = _file_state(after, chess.square_file(move.to_square), mover)
    if piece.piece_type == chess.KING and len(board.piece_map()) <= 14:
        profile["king_centralizes"] = profile["centralizes"]
    return profile


def structural_features(
    fen: str,
    played_uci: str,
    best_uci: str,
) -> Dict[str, Any]:
    """Coarse board-aware features for offline grouping, never runtime truth."""
    board = chess.Board(normalized_fen(fen))
    try:
        played = chess.Move.from_uci(str(played_uci or ""))
        best = chess.Move.from_uci(str(best_uci or ""))
    except ValueError as exc:
        raise PositionalReasonValidationError("played_uci and best_uci must be legal UCI") from exc
    played_profile = _move_profile(board, played)
    best_profile = _move_profile(board, best)
    return {
        "phase": _phase(board),
        "same_piece_type": played_profile["piece"] == best_profile["piece"],
        "played": played_profile,
        "better": best_profile,
    }


def structural_signature(fen: str, played_uci: str, best_uci: str) -> str:
    features = structural_features(fen, played_uci, best_uci)
    encoded = json.dumps(features, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def canonical_concepts() -> Dict[str, Dict[str, str]]:
    from services.caption_principles import PRINCIPLES

    return {
        str(item["id"]): {
            "id": str(item["id"]),
            "name": str(item.get("name") or item["id"]),
        }
        for item in PRINCIPLES
        if isinstance(item, dict) and item.get("id")
    }


def voice_warnings(parts: Iterable[str]) -> list[str]:
    text = " ".join(str(part or "") for part in parts).strip()
    lower = text.lower()
    warnings: list[str] = []
    for term, replacement in _JARGON_REPLACEMENTS.items():
        if re.search(rf"\b{re.escape(term)}\b", lower):
            warnings.append(f'Explain "{term}" in plain language: {replacement}.')
    if _CP_AS_MATERIAL.search(text):
        warnings.append(
            "Centipawn loss is not captured material; describe the board consequence instead."
        )
    if text and not _SQUARE.search(text):
        warnings.append(
            "Name a square when the board proof supports one; concrete geometry teaches better."
        )
    return warnings


def _promotion_readiness(
    *,
    disposition: str,
    canonical_concept_id: Optional[str],
    proof_coverage: float,
) -> Dict[str, Any]:
    blockers: list[str] = []
    quality_id = (
        f"principle:{canonical_concept_id}"
        if canonical_concept_id
        else "candidate:unmapped"
    )
    if disposition != "eligible_positional":
        blockers.append("The disposition is not eligible_positional.")
    if proof_coverage < 1.0:
        blockers.append("The contrastive teaching proof is incomplete.")
    if not canonical_concept_id:
        blockers.append("Map the candidate to a canonical concept ID.")
    if canonical_concept_id:
        try:
            from services.detector_quality import QualitySurface, is_authorized
            if not is_authorized(quality_id, QualitySurface.CAPTION):
                blockers.append("The deterministic detector is not Caption-authorized.")
            if not is_authorized(quality_id, QualitySurface.MASTERY):
                blockers.append("The detector is not Mastery-authorized.")
        except Exception:
            blockers.append("Detector authorization could not be verified.")
    blockers.append("Attach promoted detector and verifier versions during code review.")
    return {
        "ready": not blockers,
        "quality_id": quality_id,
        "caption_authorized": False,
        "tracker_authorized": False,
        "blockers": blockers,
    }


def normalize_submission(
    payload: Mapping[str, Any],
    queue_row: Mapping[str, Any],
    *,
    submitted_by: str,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and normalize one admin review into candidate evidence."""
    disposition = str(payload.get("disposition") or "").strip()
    if disposition not in DISPOSITION_LABELS:
        raise PositionalReasonValidationError("a supported disposition is required")

    fen = str(payload.get("fen") or queue_row.get("fen") or "").strip()
    if not fen or fen != str(queue_row.get("fen") or "").strip():
        raise PositionalReasonValidationError("fen does not match the queued position")

    played_uci = str(queue_row.get("played_uci") or "").strip()
    best_uci = str(queue_row.get("best_uci") or "").strip()
    fingerprint = position_fingerprint(fen, played_uci, best_uci)
    features = structural_features(fen, played_uci, best_uci)
    signature = structural_signature(fen, played_uci, best_uci)
    timestamp = now or datetime.now(timezone.utc).isoformat()

    notes = _clean_text(payload.get("notes"), "notes")
    concept_label = _clean_text(payload.get("concept_label"), "concept_label")
    if len(concept_label) > _MAX_LABEL:
        raise PositionalReasonValidationError("concept_label is too long")
    concept_id = str(payload.get("canonical_concept_id") or "").strip() or None
    if concept_id and concept_id not in canonical_concepts():
        raise PositionalReasonValidationError("canonical_concept_id is not registered")

    teaching = {
        field_name: _clean_text(
            payload.get(field_name),
            field_name,
            required=(disposition == "eligible_positional"),
        )
        for field_name in TEACHING_FIELDS
    }
    if disposition == "eligible_positional" and not concept_label:
        raise PositionalReasonValidationError(
            "a plain-language teaching-idea headline is required"
        )

    completed = sum(bool(teaching[field_name]) for field_name in TEACHING_FIELDS)
    coverage = completed / len(TEACHING_FIELDS)
    quality_id = f"principle:{concept_id}" if concept_id else (
        "candidate:" + re.sub(r"[^a-z0-9]+", "_", concept_label.lower()).strip("_")
    )
    proof = ReasonProof(
        authority="human_reviewed_candidate",
        quality_id=quality_id,
        detector_version="unpromoted",
        verifier_version=VERIFIER_VERSION,
        fingerprint=fingerprint,
    )
    warnings = voice_warnings([concept_label, *teaching.values()])
    if disposition == "eligible_positional" and warnings:
        raise PositionalReasonValidationError(" ".join(warnings))
    readiness = _promotion_readiness(
        disposition=disposition,
        canonical_concept_id=concept_id,
        proof_coverage=coverage,
    )

    reason = " ".join(
        teaching[field_name]
        for field_name in TEACHING_FIELDS
        if teaching[field_name]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "position_fingerprint": fingerprint,
        "structural_signature": signature,
        "structural_features": features,
        "fen": normalized_fen(fen),
        "game_id": queue_row.get("game_id"),
        "move_number": queue_row.get("move_number"),
        "side_to_move": queue_row.get("side_to_move"),
        "played_san": queue_row.get("played_san"),
        "best_san": queue_row.get("best_san"),
        "played_uci": played_uci,
        "best_uci": best_uci,
        "cp_loss": queue_row.get("cp_loss"),
        "fresh_cp_loss": queue_row.get("fresh_cp_loss"),
        "eval_before": queue_row.get("eval_before"),
        "eval_after": queue_row.get("eval_after"),
        "bucket": queue_row.get("bucket"),
        "already_explained_by": list(queue_row.get("already_explained_by") or []),
        "disposition": disposition,
        "disposition_label": DISPOSITION_LABELS[disposition],
        "concept_label": concept_label or None,
        "canonical_concept_id": concept_id,
        "teaching": teaching,
        "reason": reason or notes or DISPOSITION_LABELS[disposition],
        "notes": notes or None,
        "voice_warnings": warnings,
        "proof_coverage": coverage,
        "proof": proof.private_dict(),
        "promotion": readiness,
        "caption_eligible": False,
        "tracker_eligible": False,
        "submitted_by": submitted_by,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


__all__ = [
    "DISPOSITION_LABELS",
    "INELIGIBLE_DISPOSITIONS",
    "PositionalReasonValidationError",
    "canonical_concepts",
    "normalize_submission",
    "normalized_fen",
    "position_fingerprint",
    "structural_features",
    "structural_signature",
    "voice_warnings",
]
