"""Private Phase 6 old/new review validation rubric and evidence storage."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Mapping, Optional, Sequence

from services.game_review_contracts import (
    ReviewContractViolation,
    ReviewPresentationMode,
)


VALIDATION_SCHEMA_VERSION = "personalized_game_review.validation.v1"
VALIDATION_COLLECTION = "game_review_validation_reviews"
BLIND_VARIANTS = ("a", "b")


_RUBRIC = (
    {
        "id": "chess_truth",
        "label": "Chess truth",
        "options": (
            ("correct", "Correct"),
            ("minor_issue", "Minor issue"),
            ("critical_false_claim", "Critical false claim"),
        ),
    },
    {
        "id": "moment_choice",
        "label": "Moment choice",
        "options": (
            ("strong", "Strong"),
            ("mixed", "Mixed"),
            ("missed_key_moment", "Missed the key moment"),
        ),
    },
    {
        "id": "explanation_clarity",
        "label": "Explanation clarity",
        "options": (
            ("clear", "Clear"),
            ("mostly_clear", "Mostly clear"),
            ("confusing", "Confusing"),
        ),
    },
    {
        "id": "personalization",
        "label": "Personalization",
        "options": (
            ("specific", "Specific to this player"),
            ("partly_generic", "Partly generic"),
            ("generic_or_false", "Generic or false"),
        ),
    },
    {
        "id": "reflection_value",
        "label": "Reflection value",
        "options": (
            ("useful", "Useful"),
            ("neutral", "Neutral"),
            ("leading_or_unhelpful", "Leading or unhelpful"),
        ),
    },
    {
        "id": "story_coherence",
        "label": "Story coherence",
        "options": (
            ("coherent", "Coherent"),
            ("loose", "Loose"),
            ("false_connection", "False connection"),
        ),
    },
    {
        "id": "next_action_quality",
        "label": "Next action",
        "options": (
            ("useful", "Useful"),
            ("weak", "Weak"),
            ("unsupported_or_wrong", "Unsupported or wrong"),
            ("not_shown", "Not shown"),
        ),
    },
)


async def ensure_validation_indexes(db) -> None:
    """Enforce idempotency and the active-mode re-entry lookup in Mongo."""
    collection = db[VALIDATION_COLLECTION]
    await collection.create_index("review_id", unique=True)
    await collection.create_index([
        ("reviewer_user_id", 1),
        ("game_id", 1),
        ("presentation_variant", 1),
        ("source_v5_version", 1),
        ("plan_id", 1),
    ])


def blind_variant_modes(
    reviewer_user_id: str,
    game_id: str,
) -> Dict[str, ReviewPresentationMode]:
    """Deterministically counterbalance A/B without exposing mode to clients."""
    identity = f"{reviewer_user_id}|{game_id}|phase6-blind-v1"
    first_is_personalized = hashlib.sha256(
        identity.encode("utf-8")
    ).digest()[0] % 2 == 1
    first = (
        ReviewPresentationMode.PERSONALIZED
        if first_is_personalized
        else ReviewPresentationMode.LEGACY
    )
    second = (
        ReviewPresentationMode.LEGACY
        if first_is_personalized
        else ReviewPresentationMode.PERSONALIZED
    )
    return {"a": first, "b": second}


def resolve_blind_variant(
    *,
    comparison_allowed: bool,
    requested_variant: Optional[str],
) -> str:
    """Resolve A/B only inside the approved comparison cohort."""
    if not comparison_allowed:
        raise ReviewContractViolation(
            "review comparison is not enabled for this account"
        )
    variant = str(requested_variant or "a").strip().lower()
    if variant not in BLIND_VARIANTS:
        raise ReviewContractViolation("unknown review presentation variant")
    return variant


def public_validation_rubric() -> list[Dict[str, Any]]:
    """Return the one backend-owned rubric as a JSON-safe client view."""
    return [
        {
            "id": dimension["id"],
            "label": dimension["label"],
            "options": [
                {"id": option_id, "label": label}
                for option_id, label in dimension["options"]
            ],
        }
        for dimension in _RUBRIC
    ]


def validate_validation_ratings(
    ratings: Mapping[str, Any],
) -> Dict[str, str]:
    """Require one exact server-rubric answer for every dimension."""
    if not isinstance(ratings, Mapping):
        raise ReviewContractViolation("validation ratings must be a mapping")
    expected_ids = {dimension["id"] for dimension in _RUBRIC}
    if set(ratings) != expected_ids:
        raise ReviewContractViolation(
            "validation ratings must answer every rubric dimension exactly once"
        )
    clean = {}
    for dimension in _RUBRIC:
        allowed = {option_id for option_id, _label in dimension["options"]}
        selected = str(ratings.get(dimension["id"]) or "")
        if selected not in allowed:
            raise ReviewContractViolation(
                f"invalid validation option for {dimension['id']}"
            )
        clean[dimension["id"]] = selected
    return clean


def _clean_notes(notes: Optional[str]) -> str:
    value = str(notes or "").strip()
    if len(value) > 1000:
        raise ReviewContractViolation("validation notes exceed 1000 characters")
    return value


def build_validation_review_document(
    *,
    reviewer_user_id: str,
    game_id: str,
    presentation_variant: str,
    presentation_mode: str,
    ratings: Mapping[str, Any],
    notes: Optional[str],
    source_v5_version: int,
    plan_id: Optional[str],
    submitted_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build private, idempotent review evidence without board or caption data."""
    try:
        mode = ReviewPresentationMode(str(presentation_mode))
    except ValueError as exc:
        raise ReviewContractViolation("unknown review presentation mode") from exc
    reviewer = str(reviewer_user_id or "").strip()
    game = str(game_id or "").strip()
    if not reviewer or not game:
        raise ReviewContractViolation("reviewer_user_id and game_id are required")
    variant = str(presentation_variant or "").strip().lower()
    if variant not in BLIND_VARIANTS:
        raise ReviewContractViolation("unknown review presentation variant")
    if not isinstance(source_v5_version, int) or source_v5_version < 1:
        raise ReviewContractViolation("source_v5_version must be a positive integer")
    clean_ratings = validate_validation_ratings(ratings)
    clean_plan_id = str(plan_id or "").strip() or None
    if mode == ReviewPresentationMode.PERSONALIZED and not clean_plan_id:
        raise ReviewContractViolation(
            "personalized validation requires the rendered plan_id"
        )
    when = submitted_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ReviewContractViolation("submitted_at must be timezone-aware")
    identity = "|".join(
        (
            reviewer,
            game,
            variant,
            mode.value,
            str(source_v5_version),
            clean_plan_id or "legacy",
        )
    )
    review_id = "review-validation:" + hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "review_id": review_id,
        "reviewer_user_id": reviewer,
        "game_id": game,
        "presentation_variant": variant,
        "presentation_mode": mode.value,
        "source_v5_version": source_v5_version,
        "plan_id": clean_plan_id,
        "ratings": clean_ratings,
        "critical_truth_failure": (
            clean_ratings["chess_truth"] == "critical_false_claim"
        ),
        "notes": _clean_notes(notes),
        "submitted_at": when.isoformat(),
    }


async def store_validation_review(collection, document: Mapping[str, Any]):
    """Upsert the reviewer/game/version scorecard without duplicate rows."""
    await collection.update_one(
        {"review_id": document["review_id"]},
        {
            "$set": dict(document),
            "$setOnInsert": {"first_submitted_at": document["submitted_at"]},
        },
        upsert=True,
    )
    return dict(document)


def public_validation_submission(
    document: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return only the state needed to revisit one private scorecard."""
    if not isinstance(document, Mapping):
        return None
    ratings = document.get("ratings")
    if not isinstance(ratings, Mapping):
        return None
    try:
        clean_ratings = validate_validation_ratings(ratings)
    except ReviewContractViolation:
        return None
    return {
        "presentation_variant": document.get("presentation_variant"),
        "ratings": clean_ratings,
        "notes": str(document.get("notes") or ""),
        "critical_truth_failure": bool(document.get("critical_truth_failure")),
        "submitted_at": document.get("submitted_at"),
    }


def public_validation_packet(
    *,
    active_variant: str,
    personalized_available: bool,
    existing_submission: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Describe the internal comparison UI without exposing account flags."""
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "enabled": True,
        "active_variant": active_variant,
        "comparison_ready": bool(personalized_available),
        "presentation_options": [
            {"id": "a", "label": "Review A"},
            {"id": "b", "label": "Review B"},
        ],
        "rubric": public_validation_rubric(),
        "existing_submission": public_validation_submission(existing_submission),
    }
