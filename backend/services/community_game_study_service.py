"""Fail-closed contracts for coach-selected community game studies.

This module validates licensed, anonymous whole-game study records, ranks
already-authorized neutral chapters, and projects only independently admitted
studies to player-facing review services. It does not select a learner's focus,
invent chess claims, own review prescriptions, or expose routes directly.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
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
from services.game_review_planner import COHERENT_STORY_FORMULA


SCHEMA_VERSION = "community_game_study.v2"
SHADOW_SCHEMA_VERSION = "community_game_study_shadow_selection.v1"
ADMISSION_POLICY_VERSION = "licensed_neutral_coherent_guided.v2"
SELECTOR_VERSION = "focus_band_breadth_richness.v1"
COLLECTION = "community_game_studies"
SHADOW_EVENT_COLLECTION = "community_game_study_shadow_events"
SAFE_PROJECTION_VERSION = "community_neutral_projection.v3"
GUIDED_INTERACTION_VERSION = "community_guided_review_interaction.v1"
SHADOW_FEATURE_FLAG = "COMMUNITY_GAME_STUDY_SHADOW_ENABLED"
VISIBLE_FEATURE_FLAG = "COMMUNITY_GAME_STUDY_VISIBLE_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
OPERABILITY_ROLES = frozenset({"admin", "super_admin"})

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
    "ply",
    "move_number",
    "role",
    "primary_principle_id",
)
NEUTRAL_CHAPTER_FIELDS = (
    "event_id",
    "concept_id",
    "quality_id",
    "phase",
    "headline",
    "explanation",
    "principle",
    "primary_principle_id",
    "move_number",
    "move_san",
    "demonstration",
    "interaction",
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


def shadow_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(SHADOW_FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES


def visible_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return bool(
        shadow_enabled(source)
        and str(source.get(VISIBLE_FEATURE_FLAG, "false")).strip().lower()
        in _TRUE_VALUES
    )


def visible_for_operability_role(
    role: Any,
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Narrow visibility to the approved admin operability cohort.

    This is never an access bypass: the caller must still pass the canonical
    Complete Coaching enrollment, locked-target and immutable-baseline gate.
    There is deliberately no second email or user-id allowlist.
    """
    normalized_role = str(role or "user").strip().lower()
    return bool(
        visible_enabled(env) and normalized_role in OPERABILITY_ROLES
    )


def _verified_cause(source_event: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return one intact typed cause, or fail closed on a broken stamp."""
    cause = source_event.get("cause")
    if cause is None:
        return None
    if not isinstance(cause, Mapping):
        raise CommunityGameStudyError("source event cause must be a mapping")
    fingerprint = _required_sha(
        cause.get("fingerprint"), "source_event.cause.fingerprint"
    )
    payload = dict(cause)
    payload.pop("fingerprint", None)
    computed = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if computed != fingerprint:
        raise CommunityGameStudyError("source event cause fingerprint is stale")
    teaching = source_event.get("teaching")
    if not isinstance(teaching, Mapping) or teaching.get(
        "cause_fingerprint"
    ) != fingerprint:
        raise CommunityGameStudyError("source event teaching is not bound to its cause")
    return cause


def _cause_piece(cause: Mapping[str, Any], field: str) -> tuple[str, str]:
    raw = cause.get(field)
    if not isinstance(raw, Mapping):
        raise CommunityGameStudyError(f"source event cause.{field} is missing")
    piece = _required_text(raw.get("piece"), f"source event cause.{field}.piece")
    square = _required_text(
        raw.get("square"), f"source event cause.{field}.square"
    )
    try:
        chess.parse_square(square)
    except ValueError as exc:
        raise CommunityGameStudyError(
            f"source event cause.{field}.square is invalid"
        ) from exc
    return piece, square


def _verified_line(
    cause: Mapping[str, Any],
    field: str,
    *,
    through_ply: Optional[int] = None,
) -> list[str]:
    raw = cause.get(field)
    if not isinstance(raw, list) or not raw or any(
        not str(move or "").strip() for move in raw
    ):
        raise CommunityGameStudyError(f"source event cause.{field} is invalid")
    moves = [str(move).strip() for move in raw]
    if through_ply is not None:
        if through_ply < 1 or through_ply > len(moves):
            raise CommunityGameStudyError(
                f"source event cause.{field} does not reach the payoff"
            )
        moves = moves[:through_ply]
    return moves


def _line_words(moves: Sequence[str]) -> str:
    return " → ".join(moves)


def _first_initiator_capture(cause: Mapping[str, Any]) -> Mapping[str, Any]:
    captures = cause.get("best_captures")
    if not isinstance(captures, list) or not captures:
        raise CommunityGameStudyError(
            "source event cause.best_captures is missing"
        )
    for index, capture in enumerate(captures):
        if not isinstance(capture, Mapping):
            raise CommunityGameStudyError(
                f"source event cause.best_captures[{index}] is invalid"
            )
        if capture.get("actor") == "initiator":
            return capture
    raise CommunityGameStudyError(
        "source event cause.best_captures has no initiator capture"
    )


def _neutral_cause_teaching(
    source_event: Mapping[str, Any],
    cause: Mapping[str, Any],
) -> tuple[
    str,
    str,
    str,
    str,
    Optional[dict[str, Any]],
    dict[str, Any],
]:
    """Render only facts already present in a verified typed cause.

    These bounded templates change audience perspective; they do not name a
    new motif, infer psychology, or evaluate a position. Unsupported cause
    kinds abstain instead of falling back to copied learner-facing prose.
    """
    move = source_event.get("move")
    if not isinstance(move, Mapping):
        raise CommunityGameStudyError("source event move is missing")
    played = _required_text(move.get("san"), "source_event.move.san")
    kind = _required_text(cause.get("kind"), "source_event.cause.kind")

    if kind == "legal_material_loss":
        affected_piece, affected_square = _cause_piece(cause, "affected")
        attacker_piece, attacker_square = _cause_piece(cause, "attacker")
        punishment = _required_text(
            cause.get("punishment_san"), "source_event.cause.punishment_san"
        )
        best = _required_text(
            cause.get("best_move_san"), "source_event.cause.best_move_san"
        )
        try:
            material_loss = int(cause.get("material_loss_cp") or 0)
        except (TypeError, ValueError) as exc:
            raise CommunityGameStudyError(
                "source event cause material loss is invalid"
            ) from exc
        if material_loss <= 0:
            raise CommunityGameStudyError(
                "source event cause material loss must be positive"
            )
        purpose = cause.get("best_move_purpose")
        if purpose == "moves_affected_piece":
            best_reason = f"{best} moves that {affected_piece} out of danger."
        elif purpose == "removes_attacker":
            best_reason = f"{best} removes the attacker on {attacker_square}."
        elif purpose == "adds_defender":
            best_reason = f"{best} adds enough protection to {affected_square}."
        else:
            best_reason = f"{best} avoids that loss."
        headline = f"The {affected_piece} on {affected_square} is left unprotected"
        explanation = (
            f"{played} allows {punishment} because the {attacker_piece} on "
            f"{attacker_square} can take the {affected_piece} on "
            f"{affected_square}. {best_reason}"
        )
        principle = (
            "Before choosing a move, check what the opponent can capture next."
        )
        return (
            headline,
            explanation,
            principle,
            "piece_safety.check_the_next_capture",
            {"kind": "played_refutation", "moves_san": [played, punishment]},
            {
                "question": "What danger should decide the move?",
                "options": [
                    {
                        "id": "capture_next",
                        "label": (
                            f"After {played}, {punishment} can take the "
                            f"{affected_piece} on {affected_square}."
                        ),
                    },
                    {
                        "id": "activity_is_enough",
                        "label": (
                            f"{played} is active enough, so the "
                            f"{affected_piece} does not need protection."
                        ),
                    },
                ],
                "correct_option_id": "capture_next",
                "hint": (
                    f"Follow the {attacker_piece} from {attacker_square} "
                    f"to {affected_square} after {played}."
                ),
            },
        )

    if kind == "verified_stored_line":
        lesson = _required_text(
            cause.get("lesson_kind"), "source_event.cause.lesson_kind"
        )
        best = _required_text(
            cause.get("best_move_san"), "source_event.cause.best_move_san"
        )
        if lesson == "missed_forced_mate":
            line = _verified_line(cause, "best_line_san")
            return (
                "The king could be trapped with checkmate",
                f"{played} missed checkmate. The sequence {_line_words(line)} "
                "ends the game.",
                "When the king has few safe squares, examine every check first.",
                "king_safety.examine_every_check",
                {"kind": "better_line", "moves_san": line},
                {
                    "question": "What should be examined first around this king?",
                    "options": [
                        {
                            "id": "checks_first",
                            "label": f"Every legal check, starting with {best}.",
                        },
                        {
                            "id": "quiet_move_first",
                            "label": "A quiet move; the king still has time to escape.",
                        },
                    ],
                    "correct_option_id": "checks_first",
                    "hint": f"Start with {best} and count the king's legal replies.",
                },
            )
        if lesson == "allowed_forced_mate":
            reply = _required_text(
                cause.get("reply_san"), "source_event.cause.reply_san"
            )
            line = _verified_line(cause, "played_line_san")
            return (
                "The king runs out of safe squares",
                f"{played} allows the sequence {_line_words(line)}, which ends "
                f"in checkmate. {best} avoids that finish.",
                "Before moving, scan every check the opponent can play next.",
                "king_safety.scan_opponent_checks",
                {"kind": "played_refutation", "moves_san": line},
                {
                    "question": "What must be checked before this move is played?",
                    "options": [
                        {
                            "id": "opponent_checks",
                            "label": f"The checking sequence that starts after {played}.",
                        },
                        {
                            "id": "own_threat_only",
                            "label": f"Only the threat created by {played}.",
                        },
                    ],
                    "correct_option_id": "opponent_checks",
                    "hint": f"After {played}, begin with the opponent's checks.",
                },
            )
        if lesson == "exchange_sequence":
            line = _verified_line(cause, "played_line_san")
            return (
                "The last capture decides the trade",
                f"{played} goes wrong because the sequence {_line_words(line)} "
                f"gives up more material than it wins. {best} avoids that trade.",
                "Before starting an exchange, count every recapture to the end.",
                "calculation.count_every_recapture",
                {"kind": "played_refutation", "moves_san": line},
                {
                    "question": "What decides whether this trade works?",
                    "options": [
                        {
                            "id": "last_capture",
                            "label": "The material left after every recapture.",
                        },
                        {
                            "id": "first_capture",
                            "label": f"Only the first capture made by {played}.",
                        },
                    ],
                    "correct_option_id": "last_capture",
                    "hint": f"Do not stop at {played}; follow {_line_words(line)}.",
                },
            )
        if lesson == "missed_material_opportunity":
            first_capture = _first_initiator_capture(cause)
            target_piece = _required_text(
                first_capture.get("captured_piece"),
                "source event cause.best_captures[].captured_piece",
            )
            target_square = _required_text(
                first_capture.get("captured_square"),
                "source event cause.best_captures[].captured_square",
            )
            try:
                chess.parse_square(target_square)
            except ValueError as exc:
                raise CommunityGameStudyError(
                    "source event cause.best_captures[].captured_square is invalid"
                ) from exc
            try:
                payoff_ply = int(first_capture.get("ply") or 0)
            except (TypeError, ValueError) as exc:
                raise CommunityGameStudyError(
                    "source event cause.best_captures[].ply is invalid"
                ) from exc
            line = _verified_line(
                cause,
                "best_line_san",
                through_ply=payoff_ply,
            )
            capturing_piece = _required_text(
                first_capture.get("capturing_piece"),
                "source event cause.best_captures[].capturing_piece",
            )
            return (
                f"A loose {target_piece} on {target_square} could be won",
                f"{played} missed the chance because {_line_words(line)} ends "
                f"with the {capturing_piece} taking the {target_piece} on "
                f"{target_square}.",
                "Check captures and follow each reply until the gain is clear.",
                "tactics.follow_the_payoff",
                {"kind": "better_line", "moves_san": line},
                {
                    "question": f"Which move starts the gain on {target_square}?",
                    "options": [
                        {"id": "better_line", "label": best},
                        {"id": "played_move", "label": played},
                    ],
                    "correct_option_id": "better_line",
                    "hint": f"Follow {best} until the {target_piece} on {target_square} is taken.",
                },
            )
        raise CommunityGameStudyError("source event verified-line lesson is unsupported")

    if kind == "exact_endgame_result_change":
        best = _required_text(
            cause.get("best_move_san"), "source_event.cause.best_move_san"
        )
        before = _required_text(
            cause.get("outcome_before"), "source_event.cause.outcome_before"
        )
        after = _required_text(
            cause.get("outcome_after"), "source_event.cause.outcome_after"
        )
        if before not in {"win", "draw"} or after not in {"draw", "loss"}:
            raise CommunityGameStudyError(
                "source event exact endgame result change is invalid"
            )
        return (
            "One move changed the exact result",
            f"Before {played}, the position was a {before}. After it, the "
            f"result became a {after}. {best} preserved the {before}.",
            "With only a few pieces left, verify that the move keeps the result.",
            "endgame.preserve_exact_result",
            {"kind": "better_line", "moves_san": [best]},
            {
                "question": f"Which move preserves the {before}?",
                "options": [
                    {"id": "preserves_result", "label": best},
                    {"id": "changes_result", "label": played},
                ],
                "correct_option_id": "preserves_result",
                "hint": f"Compare the exact result after {best} and after {played}.",
            },
        )

    raise CommunityGameStudyError("source event cause kind is unsupported")


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


def _verify_replay(
    game: Mapping[str, Any], replay: Mapping[str, Any]
) -> Dict[int, str]:
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
    positions: Dict[int, str] = {}
    for ply, move_text in enumerate(moves_uci, start=1):
        positions[ply] = board.fen()
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
    return positions


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
            "role",
            "primary_principle_id",
        }:
            value = _required_text(value, f"chapters[{index}].{field}")
        normalized[field] = value
    ply = normalized.get("ply")
    if isinstance(ply, bool) or not isinstance(ply, int) or ply < 1:
        raise CommunityGameStudyError(
            f"chapters[{index}].ply must be a positive integer"
        )
    move_number = normalized.get("move_number")
    if move_number is not None and (
        not isinstance(move_number, int) or move_number < 1
    ):
        raise CommunityGameStudyError(
            f"chapters[{index}].move_number must be a positive integer"
        )
    if normalized["phase"] not in {"opening", "middlegame", "endgame"}:
        raise CommunityGameStudyError(f"chapters[{index}].phase is invalid")
    if normalized["role"] not in {
        "setup",
        "turning_point",
        "consequence",
        "finish",
    }:
        raise CommunityGameStudyError(f"chapters[{index}].role is invalid")
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
    demonstration: Optional[dict[str, Any]] = None
    primary_principle_id = ""
    interaction: Optional[dict[str, Any]] = None
    personalized = any(
        _SECOND_PERSON.search(value)
        for value in (headline, explanation, principle)
    )
    if personalized:
        cause = _verified_cause(source_event)
        if cause is None:
            raise CommunityGameStudyError(
                "source event teaching is personalized without a typed cause"
            )
        (
            headline,
            explanation,
            principle,
            primary_principle_id,
            demonstration,
            interaction,
        ) = _neutral_cause_teaching(source_event, cause)
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
        "primary_principle_id": primary_principle_id,
        "move_number": event_move_number,
        "move_san": event_move_san,
        "demonstration": demonstration,
        "interaction": (
            {"schema_version": GUIDED_INTERACTION_VERSION, **interaction}
            if interaction is not None
            else None
        ),
    }
    return {field: projected.get(field) for field in NEUTRAL_CHAPTER_FIELDS}


def validate_guided_interaction(
    chapter: Mapping[str, Any],
    *,
    fen_before: str,
) -> Dict[str, Any]:
    """Validate one complete interaction against the chapter position.

    The stored answer remains server-side. The legal demonstration, rather
    than the selected option, is the chess proof.
    """
    interaction = chapter.get("interaction")
    demonstration = chapter.get("demonstration")
    if not isinstance(interaction, Mapping):
        raise CommunityGameStudyError("chapter interaction is missing")
    if interaction.get("schema_version") != GUIDED_INTERACTION_VERSION:
        raise CommunityGameStudyError("chapter interaction schema is not current")
    question = _required_text(interaction.get("question"), "interaction.question")
    hint = _required_text(interaction.get("hint"), "interaction.hint")
    correct = _required_text(
        interaction.get("correct_option_id"), "interaction.correct_option_id"
    )
    options = interaction.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise CommunityGameStudyError("interaction needs two position-relevant options")
    normalized_options = []
    for index, option in enumerate(options):
        if not isinstance(option, Mapping):
            raise CommunityGameStudyError(f"interaction.options[{index}] is invalid")
        normalized_options.append({
            "id": _required_text(option.get("id"), f"interaction.options[{index}].id"),
            "label": _required_text(
                option.get("label"), f"interaction.options[{index}].label"
            ),
        })
    option_ids = [option["id"] for option in normalized_options]
    if len(option_ids) != len(set(option_ids)) or correct not in option_ids:
        raise CommunityGameStudyError("interaction option identity is invalid")
    if not isinstance(demonstration, Mapping):
        raise CommunityGameStudyError("interactive chapter needs a demonstration")
    kind = str(demonstration.get("kind") or "")
    moves = demonstration.get("moves_san")
    if kind not in {"played_refutation", "better_line"}:
        raise CommunityGameStudyError("demonstration kind is invalid")
    if not isinstance(moves, list) or not moves:
        raise CommunityGameStudyError("demonstration moves are missing")
    try:
        board = chess.Board(_required_text(fen_before, "position.fen"))
        normalized_moves = []
        for raw in moves:
            san = _required_text(raw, "demonstration move")
            board.push_san(san)
            normalized_moves.append(san)
    except (AssertionError, ValueError) as exc:
        raise CommunityGameStudyError("demonstration is not legal from the chapter") from exc
    played = _required_text(chapter.get("move_san"), "chapter.move_san")
    if kind == "played_refutation" and normalized_moves[0] != played:
        raise CommunityGameStudyError("played refutation must begin with the played move")
    if kind == "better_line" and normalized_moves[0] == played:
        raise CommunityGameStudyError("better line cannot begin with the played move")
    return {
        "schema_version": GUIDED_INTERACTION_VERSION,
        "question": question,
        "options": normalized_options,
        "correct_option_id": correct,
        "hint": hint,
    }


def public_guided_interaction(interaction: Mapping[str, Any]) -> Dict[str, Any]:
    """Project an answer-free interaction for an authenticated learner."""
    return {
        "schema_version": interaction["schema_version"],
        "question": interaction["question"],
        "options": [dict(option) for option in interaction["options"]],
        "hint_available": bool(str(interaction.get("hint") or "").strip()),
    }


def _derived_principle_id(principle: str, concept_id: str) -> str:
    normalized = " ".join(str(principle or "").lower().split())
    if normalized:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"principle:{digest}"
    return f"concept:{_required_text(concept_id, 'concept_id')}"


def principle_identity(chapter: Mapping[str, Any]) -> str:
    """Return the one canonical teaching identity used for story de-duplication."""
    explicit = str(chapter.get("primary_principle_id") or "").strip()
    return explicit or _derived_principle_id(
        str(chapter.get("principle") or ""),
        str(chapter.get("concept_id") or ""),
    )


def _project_stored_chapter(
    source_event: Mapping[str, Any],
    chapter_ref: Mapping[str, Any],
    *,
    fen_before: str,
) -> Dict[str, Any]:
    projected = project_neutral_chapter(source_event, chapter_ref)
    if not projected.get("primary_principle_id"):
        projected["primary_principle_id"] = principle_identity(projected)
    if projected["primary_principle_id"] != chapter_ref["primary_principle_id"]:
        raise CommunityGameStudyError(
            "chapter primary principle does not match current projection"
        )
    projected["interaction"] = validate_guided_interaction(
        projected,
        fen_before=fen_before,
    )
    projected["role"] = chapter_ref["role"]
    projected["position"] = {
        "fen": fen_before,
        "side_to_move": "white" if chess.Board(fen_before).turn else "black",
    }
    return projected


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
    evidence = study.get("evidence")
    privacy = study.get("privacy")
    if not all(
        isinstance(value, Mapping)
        for value in (source, game, replay, plan, evidence, privacy)
    ):
        raise CommunityGameStudyError(
            "source, game, replay, plan, evidence and privacy must be mappings"
        )
    _validate_source(source)
    replay_positions = _verify_replay(game, replay)

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
    if plan.get("story_formula") != COHERENT_STORY_FORMULA:
        raise CommunityGameStudyError("plan.story_formula is not current")
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
    if not 2 <= len(normalized_chapters) <= 3:
        raise CommunityGameStudyError(
            "a whole-game study needs two or three chapters"
        )
    event_ids = [chapter["event_id"] for chapter in normalized_chapters]
    if len(event_ids) != len(set(event_ids)):
        raise CommunityGameStudyError("chapter event ids must be unique")
    plies = [chapter["ply"] for chapter in normalized_chapters]
    if plies != sorted(plies) or len(plies) != len(set(plies)):
        raise CommunityGameStudyError("chapters must be unique and chronological")
    principles = [
        chapter["primary_principle_id"] for chapter in normalized_chapters
    ]
    if len(principles) != len(set(principles)):
        raise CommunityGameStudyError("chapter principles must be distinct")

    source_events = evidence.get("events")
    chapter_positions = evidence.get("chapter_positions")
    if not isinstance(source_events, list) or not isinstance(chapter_positions, list):
        raise CommunityGameStudyError(
            "evidence events and chapter positions must be lists"
        )
    event_index: Dict[str, Mapping[str, Any]] = {}
    for event in source_events:
        if not isinstance(event, Mapping):
            raise CommunityGameStudyError("every evidence event must be a mapping")
        event_id = _required_text(event.get("event_id"), "evidence.event_id")
        if event_id in event_index:
            raise CommunityGameStudyError("evidence event ids must be unique")
        event_index[event_id] = event
    position_index: Dict[str, Mapping[str, Any]] = {}
    for position in chapter_positions:
        if not isinstance(position, Mapping):
            raise CommunityGameStudyError(
                "every chapter position must be a mapping"
            )
        unexpected = set(position) - {"event_id", "ply", "fen"}
        if unexpected:
            raise CommunityGameStudyError(
                f"chapter position has unsupported fields: {sorted(unexpected)}"
            )
        event_id = _required_text(
            position.get("event_id"), "chapter_position.event_id"
        )
        if event_id in position_index:
            raise CommunityGameStudyError("chapter position ids must be unique")
        position_index[event_id] = position
    if set(event_index) != set(event_ids) or set(position_index) != set(event_ids):
        raise CommunityGameStudyError(
            "stored evidence must match the selected chapters exactly"
        )
    for chapter in normalized_chapters:
        position = position_index[chapter["event_id"]]
        ply = position.get("ply")
        if ply != chapter["ply"] or replay_positions.get(chapter["ply"]) != position.get("fen"):
            raise CommunityGameStudyError(
                "chapter position does not match the legal whole-game replay"
            )
        _project_stored_chapter(
            event_index[chapter["event_id"]],
            chapter,
            fen_before=str(position["fen"]),
        )

    if privacy.get("identity_state") != "anonymous":
        raise CommunityGameStudyError("privacy.identity_state must be anonymous")
    if privacy.get("contains_identity_fields") is not False:
        raise CommunityGameStudyError(
            "privacy.contains_identity_fields must be false"
        )

    normalized = deepcopy(dict(study))
    normalized["plan"] = {**dict(plan), "chapters": normalized_chapters}
    return normalized


def project_visible_study(study: Mapping[str, Any]) -> Dict[str, Any]:
    """Return an anonymous answer-hidden study shell for one learner."""
    normalized = validate_study(study)
    events = {
        str(item["event_id"]): item for item in normalized["evidence"]["events"]
    }
    positions = {
        str(item["event_id"]): item
        for item in normalized["evidence"]["chapter_positions"]
    }
    chapters = []
    for reference in normalized["plan"]["chapters"]:
        event_id = reference["event_id"]
        projected = _project_stored_chapter(
            events[event_id],
            reference,
            fen_before=str(positions[event_id]["fen"]),
        )
        chapters.append(
            {
                "event_id": event_id,
                "role": projected["role"],
                "phase": projected["phase"],
                "ply": reference["ply"],
                "move_number": projected["move_number"],
                "position": projected["position"],
                "interaction": public_guided_interaction(
                    projected["interaction"]
                ),
            }
        )
    return {
        "schema_version": "community_game_study_player.v1",
        "study_id": normalized["study_id"],
        "source_kind": "community",
        "game": {
            "initial_fen": normalized["game"]["initial_fen"],
            "moves_uci": list(normalized["game"]["moves_uci"]),
            "rating_band": normalized["game"]["rating_band"],
            "time_control_category": normalized["game"]["time_control_category"],
        },
        "chapters": chapters,
    }


def verify_guided_replay_move(
    study: Mapping[str, Any],
    *,
    event_id: str,
    played_move_uci: str,
) -> Dict[str, Any]:
    """Verify the learner replayed the chapter's key move on its exact board.

    The full demonstration has already been replay-validated at admission. The
    learner owns the first decision; the remaining replies are the line they
    just watched. This prevents a client from marking replay complete by
    sending only a UI event.
    """
    normalized = validate_study(study)
    reference = next(
        (
            chapter
            for chapter in normalized["plan"]["chapters"]
            if chapter["event_id"] == event_id
        ),
        None,
    )
    if reference is None:
        raise CommunityGameStudyError("chapter does not belong to this study")
    source_event = next(
        item
        for item in normalized["evidence"]["events"]
        if item["event_id"] == event_id
    )
    position = next(
        item
        for item in normalized["evidence"]["chapter_positions"]
        if item["event_id"] == event_id
    )
    projected = _project_stored_chapter(
        source_event,
        reference,
        fen_before=str(position["fen"]),
    )
    try:
        board = chess.Board(str(position["fen"]))
        expected = board.parse_san(projected["demonstration"]["moves_san"][0])
        played = chess.Move.from_uci(
            _required_text(played_move_uci, "played_move_uci").lower()
        )
    except (AssertionError, ValueError) as exc:
        raise CommunityGameStudyError("replayed move is not valid UCI") from exc
    if played not in board.legal_moves:
        raise CommunityGameStudyError("replayed move is illegal on this board")
    if played != expected:
        raise CommunityGameStudyError("replay the key move from the shown line")
    return {
        "event_id": event_id,
        "correct": True,
        "played_move_uci": played.uci(),
        "expected_move_san": board.san(expected),
    }


def reveal_study_chapter(
    study: Mapping[str, Any],
    *,
    event_id: str,
    selected_option_id: Optional[str] = None,
    include_hint: bool = False,
) -> Dict[str, Any]:
    """Grade or hint one chapter; only this server projection reveals truth."""
    normalized = validate_study(study)
    reference = next(
        (
            chapter
            for chapter in normalized["plan"]["chapters"]
            if chapter["event_id"] == event_id
        ),
        None,
    )
    if reference is None:
        raise CommunityGameStudyError("chapter does not belong to this study")
    source_event = next(
        item
        for item in normalized["evidence"]["events"]
        if item["event_id"] == event_id
    )
    position = next(
        item
        for item in normalized["evidence"]["chapter_positions"]
        if item["event_id"] == event_id
    )
    projected = _project_stored_chapter(
        source_event,
        reference,
        fen_before=str(position["fen"]),
    )
    if include_hint:
        return {
            "event_id": event_id,
            "hint": projected["interaction"]["hint"],
        }
    selected = _required_text(selected_option_id, "selected_option_id")
    option_ids = {
        item["id"] for item in projected["interaction"]["options"]
    }
    if selected not in option_ids:
        raise CommunityGameStudyError("selected option was not shown")
    correct_id = projected["interaction"]["correct_option_id"]
    return {
        "event_id": event_id,
        "selected_option_id": selected,
        "correct_option_id": correct_id,
        "correct": selected == correct_id,
        "headline": projected["headline"],
        "explanation": projected["explanation"],
        "principle": projected["principle"],
        "demonstration": projected["demonstration"],
    }


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


async def load_admitted_selection(
    db,
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
    terminal_study_ids: Sequence[str] = (),
) -> Dict[str, Any]:
    """Rank only independently admitted studies for a visible prescription."""
    rows = await db[COLLECTION].find(
        {
            "status": "admitted",
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


async def load_study(db, study_id: str) -> Optional[Dict[str, Any]]:
    """Load one current anonymous study; malformed rows disappear safely."""
    row = await db[COLLECTION].find_one(
        {"study_id": str(study_id), "status": {"$in": sorted(ELIGIBLE_STATUSES)}},
        {"_id": 0},
    )
    if not isinstance(row, Mapping):
        return None
    try:
        return validate_study(row)
    except CommunityGameStudyError:
        return None


async def load_admitted_study(
    db, study_id: str
) -> Optional[Dict[str, Any]]:
    """Load one independently admitted study for a player-facing surface."""
    row = await db[COLLECTION].find_one(
        {"study_id": str(study_id), "status": "admitted"},
        {"_id": 0},
    )
    if not isinstance(row, Mapping):
        return None
    try:
        normalized = validate_study(row)
    except CommunityGameStudyError:
        return None
    if normalized["status"] != "admitted":
        return None
    return normalized


async def record_shadow_evidence(
    db,
    selection: Mapping[str, Any],
    *,
    focus_concept_id: str,
    focus_quality_id: str,
    rating_band: str,
) -> None:
    """Record aggregate selection reach without learner or source identity."""
    from datetime import datetime, timezone

    candidate = selection.get("candidate")
    now = datetime.now(timezone.utc)
    hour = now.replace(minute=0, second=0, microsecond=0)
    payload = {
        "schema_version": "community_game_study_shadow_event.v1",
        "rating_band": rating_band,
        "focus_concept_id": str(focus_concept_id or ""),
        "focus_quality_id": str(focus_quality_id or ""),
        "status": str(selection.get("status") or "empty"),
        "eligible_count": int(selection.get("eligible_count") or 0),
        "focus_match": bool(
            isinstance(candidate, Mapping) and candidate.get("focus_match")
        ),
        "observed_hour": hour,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {**payload, "observed_hour": hour.isoformat()},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    await db[SHADOW_EVENT_COLLECTION].update_one(
        {"_id": f"cgse_{fingerprint[:24]}"},
        {"$setOnInsert": {"_id": f"cgse_{fingerprint[:24]}", **payload}},
        upsert=True,
    )


__all__ = [
    "ADMISSION_POLICY_VERSION",
    "APPROVED_LICENSE",
    "APPROVED_PROVIDER",
    "COLLECTION",
    "CommunityGameStudyError",
    "SCHEMA_VERSION",
    "SAFE_PROJECTION_VERSION",
    "SHADOW_FEATURE_FLAG",
    "SHADOW_EVENT_COLLECTION",
    "GUIDED_INTERACTION_VERSION",
    "SELECTOR_VERSION",
    "SHADOW_SCHEMA_VERSION",
    "VISIBLE_FEATURE_FLAG",
    "OPERABILITY_ROLES",
    "candidate_from_study",
    "load_admitted_selection",
    "load_admitted_study",
    "load_shadow_selection",
    "load_study",
    "rank_studies",
    "replay_fingerprint",
    "project_neutral_chapter",
    "principle_identity",
    "project_visible_study",
    "verify_guided_replay_move",
    "public_guided_interaction",
    "reveal_study_chapter",
    "record_shadow_evidence",
    "shadow_selection",
    "shadow_enabled",
    "validate_study",
    "validate_guided_interaction",
    "visible_enabled",
    "visible_for_operability_role",
]
