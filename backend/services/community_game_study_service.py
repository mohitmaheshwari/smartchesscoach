"""Fail-closed contracts for coach-selected community game studies.

The first release is deliberately a pure Shadow foundation.  This module may
validate licensed, anonymous whole-game study records and rank their already
authorized neutral chapters.  It does not select a learner's focus, generate
chess claims, mutate a review prescription, or expose a route.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import chess

from deterministic_coach_service import RATING_BANDS
from services.detector_quality import QualitySurface, is_authorized
from services.destination_safety_detector import (
    CONCEPT_ID as DESTINATION_SAFETY_CONCEPT_ID,
    QUALITY_ID as DESTINATION_SAFETY_QUALITY_ID,
)
from services.game_review_contracts import CONTRACT_SCHEMA_VERSION


SCHEMA_VERSION = "community_game_study.v1"
SHADOW_SCHEMA_VERSION = "community_game_study_shadow_selection.v1"
ADMISSION_POLICY_VERSION = "licensed_neutral_two_chapter.v1"
SELECTOR_VERSION = "focus_band_breadth_richness.v1"
COLLECTION = "community_game_studies"
SAFE_PROJECTION_VERSION = CONTRACT_SCHEMA_VERSION

APPROVED_PROVIDER = "lichess_open_database"
APPROVED_LICENSE = "CC0-1.0"
ELIGIBLE_STATUSES = frozenset({"shadow", "admitted"})
KNOWN_STATUSES = frozenset(
    {"shadow", "admitted", "quarantined", "withdrawn", "stale"}
)
CANONICAL_RATING_BANDS = frozenset(RATING_BANDS)
CHAPTER_REFERENCE_FIELDS = (
    "event_id",
    "concept_id",
    "quality_id",
    "phase",
    "move_number",
)
NEUTRAL_CHAPTER_FIELDS = (
    "event_id",
    "concept_id",
    "quality_id",
    "phase",
    "headline",
    "explanation",
    "principle",
    "move_number",
    "move_san",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECOND_PERSON = re.compile(r"\b(?:you|your|yours|yourself)\b", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_PRIVATE_KEYS = frozenset(
    {
        "user_id",
        "email",
        "username",
        "player_name",
        "white_name",
        "black_name",
        "opponent_name",
        "profile_url",
        "source_url",
        "personal_focus",
        "reflection",
        "private_answer",
        "next_action",
        "coach_memory",
    }
)


class CommunityGameStudyError(ValueError):
    """Raised when a community study cannot safely enter Shadow selection."""


def replay_fingerprint(initial_fen: str, moves_uci: Sequence[str]) -> str:
    seed = f"{initial_fen.strip()}\n{' '.join(str(move).strip() for move in moves_uci)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CommunityGameStudyError(f"{field} is required")
    return text


def _required_sha(value: Any, field: str) -> str:
    text = _required_text(value, field).lower()
    if not _SHA256.fullmatch(text):
        raise CommunityGameStudyError(f"{field} must be a sha256 hex digest")
    return text


def _private_path(value: Any, path: str = "study") -> Optional[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}"
            if normalized in _PRIVATE_KEYS:
                return child_path
            found = _private_path(child, child_path)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _private_path(child, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str) and (
        _EMAIL.search(value) or _URL.search(value)
    ):
        return path
    return None


def _verify_replay(game: Mapping[str, Any], replay: Mapping[str, Any]) -> None:
    initial_fen = str(game.get("initial_fen") or chess.STARTING_FEN).strip()
    moves_uci = game.get("moves_uci")
    if not isinstance(moves_uci, list) or not moves_uci:
        raise CommunityGameStudyError("game.moves_uci must be a non-empty list")
    try:
        board = chess.Board(initial_fen)
    except ValueError as exc:
        raise CommunityGameStudyError("game.initial_fen is invalid") from exc
    if not board.is_valid():
        raise CommunityGameStudyError("game.initial_fen is not a legal position")
    for ply, move_text in enumerate(moves_uci, start=1):
        try:
            move = chess.Move.from_uci(str(move_text))
        except ValueError as exc:
            raise CommunityGameStudyError(
                f"game.moves_uci contains invalid UCI at ply {ply}"
            ) from exc
        if move not in board.legal_moves:
            raise CommunityGameStudyError(
                f"game.moves_uci contains an illegal move at ply {ply}"
            )
        board.push(move)
    if replay.get("legal") is not True:
        raise CommunityGameStudyError("replay.legal must be true")
    expected = replay_fingerprint(initial_fen, moves_uci)
    if _required_sha(replay.get("fingerprint"), "replay.fingerprint") != expected:
        raise CommunityGameStudyError("replay fingerprint does not match the game")


def _validate_source(source: Mapping[str, Any]) -> None:
    if _required_text(source.get("provider"), "source.provider") != APPROVED_PROVIDER:
        raise CommunityGameStudyError("source provider is not approved")
    if _required_text(source.get("license"), "source.license") != APPROVED_LICENSE:
        raise CommunityGameStudyError("source license is not approved")
    _required_text(source.get("release_id"), "source.release_id")
    _required_sha(source.get("source_checksum"), "source.source_checksum")
    _required_sha(source.get("record_key_hash"), "source.record_key_hash")
    _required_text(source.get("terms_reviewed_at"), "source.terms_reviewed_at")


def _validate_chapter(chapter: Mapping[str, Any], index: int) -> Dict[str, Any]:
    unexpected = set(chapter) - set(CHAPTER_REFERENCE_FIELDS)
    if unexpected:
        raise CommunityGameStudyError(
            f"chapters[{index}] has unsupported fields: {sorted(unexpected)}"
        )
    concept_id = _required_text(
        chapter.get("concept_id"), f"chapters[{index}].concept_id"
    )
    quality_id = _required_text(
        chapter.get("quality_id"), f"chapters[{index}].quality_id"
    )
    if not is_authorized(quality_id, QualitySurface.CAPTION):
        raise CommunityGameStudyError(
            f"chapters[{index}] is not currently Caption-authorized"
        )
    # This exact detector has one canonical concept identity. Import both
    # values from its owner so a malformed projection cannot pair its strong
    # Plan-grade authorization with an unrelated lesson label.
    if (
        quality_id == DESTINATION_SAFETY_QUALITY_ID
        and concept_id != DESTINATION_SAFETY_CONCEPT_ID
    ):
        raise CommunityGameStudyError(
            f"chapters[{index}] concept does not match its evidence"
        )
    normalized: Dict[str, Any] = {}
    for field in CHAPTER_REFERENCE_FIELDS:
        value = chapter.get(field)
        if field in {
            "event_id",
            "concept_id",
            "quality_id",
            "phase",
        }:
            value = _required_text(value, f"chapters[{index}].{field}")
        normalized[field] = value
    move_number = normalized.get("move_number")
    if move_number is not None and (
        not isinstance(move_number, int) or move_number < 1
    ):
        raise CommunityGameStudyError(
            f"chapters[{index}].move_number must be a positive integer"
        )
    return normalized


def project_neutral_chapter(
    source_event: Mapping[str, Any],
    chapter_ref: Mapping[str, Any],
) -> Dict[str, Any]:
    """Project one canonical event without copying source-player coaching.

    The admission row stores only the reference. The neutral words are
    resolved from the current canonical event contract when a Shadow packet
    is built, so stale or personalized source captions never become a second
    content authority.
    """
    reference = _validate_chapter(chapter_ref, 0)
    if not isinstance(source_event, Mapping):
        raise CommunityGameStudyError("source event must be a mapping")
    private = _private_path(source_event, "source_event")
    if private:
        raise CommunityGameStudyError(f"private field is not allowed: {private}")
    if source_event.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise CommunityGameStudyError("source event schema is not current")
    if _required_text(source_event.get("event_id"), "source_event.event_id") != (
        reference["event_id"]
    ):
        raise CommunityGameStudyError("source event does not match chapter event")

    concept = source_event.get("concept")
    evidence = source_event.get("evidence")
    display = source_event.get("display")
    teaching = source_event.get("teaching")
    move = source_event.get("move")
    if not all(
        isinstance(value, Mapping)
        for value in (concept, evidence, display, teaching, move)
    ):
        raise CommunityGameStudyError(
            "source event is missing a canonical contract section"
        )
    if _required_text(concept.get("id"), "source_event.concept.id") != (
        reference["concept_id"]
    ):
        raise CommunityGameStudyError("source event concept does not match chapter")
    if _required_text(evidence.get("quality_id"), "source_event.evidence.quality_id") != (
        reference["quality_id"]
    ):
        raise CommunityGameStudyError("source event evidence does not match chapter")
    _required_text(evidence.get("source_version"), "source_event.evidence.source_version")
    provenance = evidence.get("provenance")
    if not isinstance(provenance, list) or not provenance or any(
        not str(item or "").strip() for item in provenance
    ):
        raise CommunityGameStudyError("source event provenance is incomplete")
    if evidence.get("final_verified") is not True:
        raise CommunityGameStudyError("source event is not finally verified")
    if display.get("requested_surface") not in {
        QualitySurface.CAPTION.value,
        QualitySurface.PLAN.value,
    }:
        raise CommunityGameStudyError("source event requested surface is invalid")
    if display.get("authorized") is not True or not is_authorized(
        reference["quality_id"], QualitySurface.CAPTION
    ):
        raise CommunityGameStudyError("source event is not player-authorized")

    headline = str(teaching.get("headline") or "").strip()
    explanation = str(
        teaching.get("caption") or teaching.get("practical_lead") or ""
    ).strip()
    principle = str(teaching.get("principle") or "").strip()
    if not explanation or not (headline or principle):
        raise CommunityGameStudyError("source event lacks neutral teaching words")
    for field, value in (
        ("headline", headline),
        ("explanation", explanation),
        ("principle", principle),
    ):
        if _SECOND_PERSON.search(value):
            raise CommunityGameStudyError(
                f"source_event.teaching.{field} is personalized, not neutral"
            )

    event_move_number = move.get("number")
    if not isinstance(event_move_number, int) or event_move_number < 1:
        raise CommunityGameStudyError("source event move number is invalid")
    event_move_san = _required_text(move.get("san"), "source_event.move.san")
    if reference.get("move_number") not in (None, event_move_number):
        raise CommunityGameStudyError("source event move does not match chapter")
    projected = {
        **reference,
        "headline": headline or principle,
        "explanation": explanation,
        "principle": principle,
        "move_number": event_move_number,
        "move_san": event_move_san,
    }
    return {field: projected.get(field) for field in NEUTRAL_CHAPTER_FIELDS}


def validate_study(study: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and normalize one stored study without mutating the input."""
    if not isinstance(study, Mapping):
        raise CommunityGameStudyError("study must be a mapping")
    private = _private_path(study)
    if private:
        raise CommunityGameStudyError(f"private field is not allowed: {private}")
    if study.get("schema_version") != SCHEMA_VERSION:
        raise CommunityGameStudyError("unknown community study schema")
    if study.get("admission_policy_version") != ADMISSION_POLICY_VERSION:
        raise CommunityGameStudyError("unknown admission policy version")
    status = _required_text(study.get("status"), "status")
    if status not in KNOWN_STATUSES:
        raise CommunityGameStudyError("unknown community study status")
    _required_text(study.get("study_id"), "study_id")
    _required_text(study.get("game_id"), "game_id")

    source = study.get("source")
    game = study.get("game")
    replay = study.get("replay")
    plan = study.get("plan")
    privacy = study.get("privacy")
    if not all(
        isinstance(value, Mapping)
        for value in (source, game, replay, plan, privacy)
    ):
        raise CommunityGameStudyError(
            "source, game, replay, plan and privacy must be mappings"
        )
    _validate_source(source)
    _verify_replay(game, replay)

    rating_band = _required_text(game.get("rating_band"), "game.rating_band")
    if rating_band not in CANONICAL_RATING_BANDS:
        raise CommunityGameStudyError("game.rating_band is not canonical")
    _required_text(game.get("time_control_category"), "game.time_control_category")

    _required_text(plan.get("plan_id"), "plan.plan_id")
    _required_sha(plan.get("input_fingerprint"), "plan.input_fingerprint")
    if (
        _required_text(
            plan.get("safe_projection_version"), "plan.safe_projection_version"
        )
        != SAFE_PROJECTION_VERSION
    ):
        raise CommunityGameStudyError("plan.safe_projection_version is not current")
    chapters = plan.get("chapters")
    if not isinstance(chapters, list):
        raise CommunityGameStudyError("plan.chapters must be a list")
    normalized_chapters = [
        _validate_chapter(chapter, index)
        for index, chapter in enumerate(chapters)
        if isinstance(chapter, Mapping)
    ]
    if len(normalized_chapters) != len(chapters):
        raise CommunityGameStudyError("every chapter must be a mapping")
    if len(normalized_chapters) < 2:
        raise CommunityGameStudyError("a whole-game study needs two chapters")
    event_ids = [chapter["event_id"] for chapter in normalized_chapters]
    if len(event_ids) != len(set(event_ids)):
        raise CommunityGameStudyError("chapter event ids must be unique")

    if privacy.get("identity_state") != "anonymous":
        raise CommunityGameStudyError("privacy.identity_state must be anonymous")
    if privacy.get("contains_identity_fields") is not False:
        raise CommunityGameStudyError(
            "privacy.contains_identity_fields must be false"
        )

    normalized = deepcopy(dict(study))
    normalized["plan"] = {**dict(plan), "chapters": normalized_chapters}
    return normalized


def candidate_from_study(
    study: Mapping[str, Any],
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
    terminal_study_ids: Sequence[str] = (),
) -> Optional[Dict[str, Any]]:
    """Return an eligible Shadow candidate or None for a safe exclusion."""
    try:
        normalized = validate_study(study)
    except CommunityGameStudyError:
        return None
    if normalized["status"] not in ELIGIBLE_STATUSES:
        return None
    study_id = str(normalized["study_id"])
    if study_id in set(terminal_study_ids):
        return None
    game = normalized["game"]
    if game["rating_band"] != rating_band:
        return None
    chapters = normalized["plan"]["chapters"]
    focus_matches = [
        chapter
        for chapter in chapters
        if (
            chapter["concept_id"] == focus_concept_id
            and chapter["quality_id"] == focus_quality_id
        )
    ]
    return {
        "study_id": study_id,
        "source_kind": "community",
        "rating_band": game["rating_band"],
        "time_control_category": game["time_control_category"],
        "focus_match": bool(focus_matches),
        "focus_chapter_count": len(focus_matches),
        "phase_breadth": len({chapter["phase"] for chapter in chapters}),
        "authorized_chapter_count": len(chapters),
        "chapter_refs": chapters,
    }


def rank_studies(
    studies: Iterable[Mapping[str, Any]],
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
    terminal_study_ids: Sequence[str] = (),
) -> list[Dict[str, Any]]:
    """Apply the measured focus/band/breadth/richness formula."""
    candidates = [
        candidate
        for study in studies
        if (
            candidate := candidate_from_study(
                study,
                focus_concept_id=focus_concept_id,
                focus_quality_id=focus_quality_id,
                rating_band=rating_band,
                terminal_study_ids=terminal_study_ids,
            )
        )
    ]
    return sorted(
        candidates,
        key=lambda item: (
            -int(item["focus_match"]),
            -int(item["phase_breadth"]),
            -int(item["focus_chapter_count"]),
            -int(item["authorized_chapter_count"]),
            str(item["study_id"]),
        ),
    )


def shadow_selection(
    studies: Iterable[Mapping[str, Any]],
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
    terminal_study_ids: Sequence[str] = (),
) -> Dict[str, Any]:
    ranked = rank_studies(
        studies,
        focus_concept_id=focus_concept_id,
        focus_quality_id=focus_quality_id,
        rating_band=rating_band,
        terminal_study_ids=terminal_study_ids,
    )
    selected = ranked[0] if ranked else None
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "selector_version": SELECTOR_VERSION,
        "status": "candidate" if selected else "empty",
        "candidate": selected,
        "eligible_count": len(ranked),
        "visible_prescription_changed": False,
    }


async def load_shadow_selection(
    db,
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
    terminal_study_ids: Sequence[str] = (),
) -> Dict[str, Any]:
    """Read and rank stored candidates without writing or changing a surface."""
    rows = await db[COLLECTION].find(
        {
            "status": {"$in": sorted(ELIGIBLE_STATUSES)},
            "game.rating_band": rating_band,
        },
        {"_id": 0},
    ).to_list(length=None)
    return shadow_selection(
        rows,
        focus_concept_id=focus_concept_id,
        focus_quality_id=focus_quality_id,
        rating_band=rating_band,
        terminal_study_ids=terminal_study_ids,
    )


__all__ = [
    "ADMISSION_POLICY_VERSION",
    "APPROVED_LICENSE",
    "APPROVED_PROVIDER",
    "COLLECTION",
    "CommunityGameStudyError",
    "SCHEMA_VERSION",
    "SAFE_PROJECTION_VERSION",
    "SELECTOR_VERSION",
    "SHADOW_SCHEMA_VERSION",
    "candidate_from_study",
    "load_shadow_selection",
    "rank_studies",
    "replay_fingerprint",
    "project_neutral_chapter",
    "shadow_selection",
    "validate_study",
]
