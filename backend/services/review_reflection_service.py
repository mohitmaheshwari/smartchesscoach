"""Backend-owned, options-only reflection for authorized review events."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Mapping, Sequence

from services.game_review_contracts import (
    PlayerReflection,
    ReflectionOption,
    ReflectionPrompt,
    ReviewContractViolation,
    TeachableEvent,
)


REFLECTION_SOURCE_VERSION = "quick_tag_registry.v2"
REFLECTION_QUESTION = "What were you thinking before this move?"
REQUIRED_ESCAPE_IDS = frozenset({"not_sure", "none_of_these"})
PIC_SIMPLE_HANG_REFLECTION_CATEGORY = "missed_forcing_move"


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    value = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(value).hexdigest()[:20]}"


def build_reflection_prompt(
    event: TeachableEvent,
    quick_tag_result: Mapping[str, Any],
) -> ReflectionPrompt:
    """Convert the existing backend quick-tag result; never parse caption prose."""
    if not isinstance(event, TeachableEvent):
        raise ReviewContractViolation("reflection requires a TeachableEvent")
    if not event.player_authorized or not event.reflection_eligible:
        raise ReviewContractViolation(
            "reflection requires an authorized, reflection-eligible event"
        )

    raw_tags = quick_tag_result.get("tags")
    if not isinstance(raw_tags, list) or not raw_tags:
        raise ReviewContractViolation("quick-tag result must contain backend tags")

    options = []
    for item in raw_tags:
        if not isinstance(item, Mapping):
            raise ReviewContractViolation("quick tags must be objects")
        option_id = item.get("id")
        label = item.get("label")
        options.append(
            ReflectionOption(
                option_id=str(option_id or ""),
                label=str(label or ""),
                diagnosis_tag=str(option_id or ""),
            )
        )

    option_ids = tuple(item.option_id for item in options)
    if not REQUIRED_ESCAPE_IDS.issubset(option_ids):
        raise ReviewContractViolation(
            "backend quick tags must contain not_sure and none_of_these"
        )

    prompt_id = _stable_id(
        "grp",
        (event.event_id, REFLECTION_SOURCE_VERSION, *option_ids),
    )
    return ReflectionPrompt(
        prompt_id=prompt_id,
        event_id=event.event_id,
        question=REFLECTION_QUESTION,
        options=tuple(options),
        source_version=REFLECTION_SOURCE_VERSION,
    )


def build_pic_simple_hang_reflection_prompt(
    event: TeachableEvent,
    *,
    fen_before: str,
    user_move: str,
    best_move: str,
    rating: int,
    cp_loss: float,
    move_number: int,
) -> ReflectionPrompt:
    """Build PIC options through the canonical quick-tag authority."""
    from quick_tag_registry import generate_quick_tags
    from services.personal_curriculum import PIC_CONTENT_ID

    if event.concept.content_ref != PIC_CONTENT_ID:
        raise ReviewContractViolation(
            "PIC reflection helper received unsupported content"
        )
    quick_tags = generate_quick_tags(
        fen_before=fen_before,
        user_move=user_move,
        best_move=best_move,
        mistake_category=PIC_SIMPLE_HANG_REFLECTION_CATEGORY,
        rating=int(rating),
        cp_loss=float(cp_loss),
        move_number=int(move_number),
        include_honest_escapes=True,
        reflection_context=(
            event.cause.contract_dict()
            if event.cause is not None
            else None
        ),
    )
    return build_reflection_prompt(event, quick_tags)


def build_review_event_reflection_prompt(
    event: TeachableEvent,
    *,
    fen_before: str,
    user_move: str,
    best_move: str,
    rating: int,
    cp_loss: float,
    move_number: int,
) -> ReflectionPrompt:
    """Build options for any authorized typed Review cause."""
    if event.cause is None:
        raise ReviewContractViolation("typed Review reflection requires a cause")
    if (event.cause.contract_dict().get("kind") == "legal_material_loss"):
        mistake_category = PIC_SIMPLE_HANG_REFLECTION_CATEGORY
    else:
        lesson_kind = str(
            event.cause.contract_dict().get("lesson_kind") or ""
        )
        mistake_category = (
            "ignored_opponent_forcing"
            if lesson_kind == "allowed_forced_mate"
            else "missed_forcing_move"
        )
    from quick_tag_registry import generate_quick_tags

    quick_tags = generate_quick_tags(
        fen_before=fen_before,
        user_move=user_move,
        best_move=best_move,
        mistake_category=mistake_category,
        rating=int(rating),
        cp_loss=float(cp_loss),
        move_number=int(move_number),
        include_honest_escapes=True,
        reflection_context=event.cause.contract_dict(),
    )
    return build_reflection_prompt(event, quick_tags)


def build_event_reflection_document(
    *,
    user_id: str,
    game_id: str,
    event: TeachableEvent,
    prompt: ReflectionPrompt,
    reflection: PlayerReflection,
) -> Dict[str, Any]:
    """Build the stored learner-evidence document with no raw position text."""
    if not user_id or not game_id:
        raise ReviewContractViolation("user_id and game_id are required")
    if prompt.event_id != event.event_id:
        raise ReviewContractViolation("prompt does not belong to the event")
    if not event.player_authorized or not event.reflection_eligible:
        raise ReviewContractViolation("event cannot accept player reflection")
    reflection.validate_against(prompt)

    reflection_id = _stable_id("grr", (user_id, game_id, event.event_id))
    return {
        "reflection_id": reflection_id,
        "reflection_kind": "game_review_event",
        "user_id": user_id,
        "game_id": game_id,
        "event": {
            "event_id": event.event_id,
            "concept_id": event.concept.concept_id,
            "content_ref": event.concept.content_ref,
            "canonical_source": event.concept.canonical_source,
            "outcome": event.outcome.value,
            "quality_id": event.evidence.quality_id,
            "quality_grade": event.evidence.grade.value,
        },
        "prompt": prompt.public_dict(),
        "response": reflection.event_dict(),
        "schema_version": reflection.event_dict()["schema_version"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_document_from_stored_contracts(
    *,
    user_id: str,
    game_id: str,
    event_contract: Mapping[str, Any],
    prompt_contract: Mapping[str, Any],
    shown_option_ids: Sequence[str],
    selected_option_id: str,
    elapsed_ms: int,
    answered_before_reveal: bool,
) -> Dict[str, Any]:
    """Validate server-stored public contracts and build a submission document.

    The route must load both mappings from the owned game analysis. Nothing in
    these contracts is accepted from the browser except the exact IDs that the
    player was shown and selected.
    """
    display = event_contract.get("display")
    evidence = event_contract.get("evidence")
    if not isinstance(display, Mapping) or not isinstance(evidence, Mapping):
        raise ReviewContractViolation("stored event contract is incomplete")
    if not display.get("authorized") or not display.get("reflection_eligible"):
        raise ReviewContractViolation("stored event is not eligible for reflection")
    if not evidence.get("final_verified"):
        raise ReviewContractViolation("stored event is not finally verified")
    authorized_surfaces = evidence.get("authorized_surfaces") or {}
    if not authorized_surfaces.get("caption"):
        raise ReviewContractViolation("stored event lacks caption authorization")

    event_id = str(event_contract.get("event_id") or "")
    if not event_id or prompt_contract.get("event_id") != event_id:
        raise ReviewContractViolation("stored prompt does not match the event")
    raw_options = prompt_contract.get("options")
    if not isinstance(raw_options, list):
        raise ReviewContractViolation("stored prompt options are missing")
    prompt = ReflectionPrompt(
        prompt_id=str(prompt_contract.get("prompt_id") or ""),
        event_id=event_id,
        question=str(prompt_contract.get("question") or ""),
        options=tuple(
            ReflectionOption(
                option_id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                diagnosis_tag=str(item.get("id") or ""),
            )
            for item in raw_options
            if isinstance(item, Mapping)
        ),
        source_version=str(prompt_contract.get("source_version") or ""),
    )
    reflection = PlayerReflection(
        prompt_id=prompt.prompt_id,
        event_id=event_id,
        shown_option_ids=tuple(str(item) for item in shown_option_ids),
        selected_option_id=selected_option_id,
        elapsed_ms=elapsed_ms,
        answered_before_reveal=answered_before_reveal,
        submitted_at=datetime.now(timezone.utc),
    )
    reflection.validate_against(prompt)

    concept = event_contract.get("concept") or {}
    reflection_id = _stable_id("grr", (user_id, game_id, event_id))
    return {
        "reflection_id": reflection_id,
        "reflection_kind": "game_review_event",
        "user_id": user_id,
        "game_id": game_id,
        "event": {
            "event_id": event_id,
            "concept_id": concept.get("id"),
            "content_ref": concept.get("content_ref"),
            "canonical_source": concept.get("canonical_source"),
            "outcome": event_contract.get("outcome"),
            "quality_id": evidence.get("quality_id"),
            "quality_grade": evidence.get("grade"),
        },
        "prompt": prompt.public_dict(),
        "response": reflection.event_dict(),
        "schema_version": reflection.event_dict()["schema_version"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def store_event_reflection(collection: Any, document: Mapping[str, Any]) -> Dict[str, Any]:
    """Idempotently store one current answer per user/game/event."""
    required = ("reflection_id", "user_id", "game_id", "event", "response")
    if any(not document.get(field) for field in required):
        raise ReviewContractViolation("event reflection document is incomplete")
    stored = dict(document)
    await collection.update_one(
        {"reflection_id": stored["reflection_id"]},
        {
            "$set": stored,
            "$setOnInsert": {"created_at": stored["updated_at"]},
        },
        upsert=True,
    )
    return stored


def public_reflection_receipt(document: Mapping[str, Any]) -> Dict[str, Any]:
    """Return only acknowledgement data; detector provenance remains private."""
    return {
        "success": True,
        "reflection_id": document["reflection_id"],
        "event_id": document["event"]["event_id"],
        "selected_option_id": document["response"]["selected_option_id"],
    }


def public_reflection_history(
    documents: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    """Return only the player's own answer state needed for re-entry."""
    history = []
    for document in documents or []:
        event = document.get("event") or {}
        response = document.get("response") or {}
        event_id = str(event.get("event_id") or "")
        prompt_id = str(response.get("prompt_id") or "")
        selected = str(response.get("selected_option_id") or "")
        if not event_id or not prompt_id or not selected:
            continue
        history.append({
            "event_id": event_id,
            "prompt_id": prompt_id,
            "selected_option_id": selected,
            "answered_before_reveal": bool(
                response.get("answered_before_reveal")
            ),
        })
    return history
