"""Per-user concept opportunity event ledger.

Every detector-identified opportunity is stored with a stable concept identity,
an explicit hit/miss/unknown outcome, and proof provenance. The ledger remains
idempotent per user and game and is the evidence source for mastery projections.

Legacy pattern_id remains for storage compatibility. concept_id is the
canonical identity used by mastery and progress. Callers that omit proof stay
neutral until an authorized detector and verifier opts the event into tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


CATALOG_VERSION = 2
VALID_OUTCOMES = frozenset({"miss", "hit", "unknown"})

_INDEXES_ENSURED = False


async def _ensure_indexes(db) -> None:
    global _INDEXES_ENSURED
    if _INDEXES_ENSURED:
        return
    try:
        await db.user_pattern_events.create_index(
            [("user_id", 1), ("pattern_id", 1)],
            name="user_pattern_events_user_pattern",
        )
        await db.user_pattern_events.create_index(
            [("user_id", 1), ("concept_id", 1)],
            name="user_pattern_events_user_concept",
        )
        await db.user_pattern_events.create_index(
            [("user_id", 1), ("game_id", 1)],
            name="user_pattern_events_user_game",
        )
        await db.user_pattern_events.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="user_pattern_events_user_recent",
        )
        _INDEXES_ENSURED = True
    except Exception as exc:
        logger.warning("[pattern_events] index ensure failed: %s", exc)


def _canonical_id(pattern_id: str, concept_id: Optional[str]) -> str:
    if concept_id:
        return str(concept_id)
    try:
        from services.pattern_catalog import canonical_concept_id

        return canonical_concept_id(pattern_id)
    except Exception:
        return str(pattern_id)


def _default_quality_id(concept_id: str) -> str:
    prefix = "principle" if concept_id and concept_id.upper() == concept_id else "pattern"
    return f"{prefix}:{concept_id}"


def _version_string(detector_versions: Dict[str, Any]) -> str:
    if not detector_versions:
        return "legacy_detector.v1"
    return ",".join(
        f"{key}:{detector_versions[key]}"
        for key in sorted(detector_versions)
    )


def _event_fingerprint(
    *,
    fen_before: str,
    move_san: str,
    best_move_san: str,
    concept_id: str,
    outcome: str,
) -> str:
    normalized_fen = " ".join(str(fen_before or "").split()[:4])
    payload = {
        "fen": normalized_fen,
        "move": str(move_san or ""),
        "best": str(best_move_san or ""),
        "concept": concept_id,
        "outcome": outcome,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def build_event(
    *,
    user_id: str,
    game_id: str,
    move_number: int,
    move_san: str,
    best_move_san: str,
    pattern_id: str,
    outcome: str,
    cp_loss: int,
    fen_before: str,
    detector_versions: Optional[Dict[str, Any]] = None,
    concept_id: Optional[str] = None,
    opportunity: bool = True,
    tracker_eligible: Optional[bool] = None,
    evidence: Optional[Dict[str, Any]] = None,
    authority: str = "legacy_pattern_detector",
    quality_id: Optional[str] = None,
    detector_version: Optional[str] = None,
    verifier_version: str = "legacy_detector.v1",
    proof_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one immutable concept-opportunity event without writing to DB."""
    normalized_outcome = str(outcome or "").lower()
    if normalized_outcome not in VALID_OUTCOMES:
        raise ValueError(f"unsupported pattern outcome: {outcome}")
    canonical = _canonical_id(str(pattern_id or ""), concept_id)
    if not canonical:
        raise ValueError("pattern_id or concept_id is required")
    versions = dict(detector_versions or {})
    # Evidence is neutral by default. Callers must opt in only after the
    # detector and verifier have been authorized for mastery.
    eligible = bool(tracker_eligible) if tracker_eligible is not None else False
    if not opportunity or normalized_outcome == "unknown":
        eligible = False
    if eligible:
        traceable = (
            bool(quality_id)
            and bool(detector_version)
            and authority not in {"", "unknown", "legacy_pattern_detector"}
            and verifier_version not in {"", "unknown", "legacy_detector.v1"}
        )
        if not traceable:
            eligible = False
        else:
            try:
                from services.detector_quality import (
                    QualitySurface,
                    enforcement_enabled,
                    is_authorized,
                )
                if enforcement_enabled() and not is_authorized(
                    str(quality_id), QualitySurface.MASTERY
                ):
                    eligible = False
            except Exception:
                eligible = False
    fingerprint = proof_fingerprint or _event_fingerprint(
        fen_before=fen_before,
        move_san=move_san,
        best_move_san=best_move_san,
        concept_id=canonical,
        outcome=normalized_outcome,
    )
    return {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": move_number,
        "move_san": move_san,
        "best_move_san": best_move_san,
        "pattern_id": str(pattern_id or canonical),
        "concept_id": canonical,
        "outcome": normalized_outcome,
        "opportunity": bool(opportunity),
        "tracker_eligible": eligible,
        "cp_loss": int(cp_loss or 0),
        "fen_before": fen_before,
        "catalog_version": CATALOG_VERSION,
        "detector_versions": versions,
        "evidence": dict(evidence or {}),
        "proof": {
            "authority": str(authority or "unknown"),
            "quality_id": str(quality_id or _default_quality_id(canonical)),
            "detector_version": str(
                detector_version or _version_string(versions)
            ),
            "verifier_version": str(verifier_version or "unknown"),
            "fingerprint": fingerprint,
        },
        "created_at": datetime.now(timezone.utc),
    }


def build_miss_event(**kwargs) -> Dict[str, Any]:
    return build_event(outcome="miss", **kwargs)


def deduplicate_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep one outcome per move and canonical concept.

    Authorized evidence always wins over neutral evidence. Within the same
    eligibility class, a miss wins over a hit and a known result wins over
    unknown. Direct verified-principle evidence wins exact ties.
    """
    rank = {"unknown": 0, "hit": 1, "miss": 2}
    chosen: Dict[tuple, Dict[str, Any]] = {}
    for event in events or ():
        key = (
            event.get("user_id"),
            event.get("game_id"),
            event.get("move_number"),
            event.get("concept_id") or event.get("pattern_id"),
        )
        current = chosen.get(key)
        if current is None:
            chosen[key] = event
            continue
        new_rank = rank.get(event.get("outcome"), -1)
        old_rank = rank.get(current.get("outcome"), -1)
        new_direct = (event.get("proof") or {}).get("authority") == "verified_caption_principle"
        old_direct = (current.get("proof") or {}).get("authority") == "verified_caption_principle"
        new_eligible = bool(event.get("tracker_eligible"))
        old_eligible = bool(current.get("tracker_eligible"))
        if (
            (new_eligible and not old_eligible)
            or (
                new_eligible == old_eligible
                and new_rank > old_rank
            )
            or (
                new_eligible == old_eligible
                and new_rank == old_rank
                and new_direct
                and not old_direct
            )
        ):
            chosen[key] = event
    return list(chosen.values())


async def replace_events_for_game(
    db,
    user_id: str,
    game_id: str,
    events: List[Dict[str, Any]],
) -> int:
    """Replace the complete event ledger slice for one user and game."""
    if not user_id or not game_id:
        return 0
    await _ensure_indexes(db)
    try:
        await db.user_pattern_events.delete_many({
            "user_id": user_id,
            "game_id": game_id,
        })
    except Exception as exc:
        logger.warning("[pattern_events] delete_many failed: %s", exc)
    normalized = deduplicate_events(events)
    if not normalized:
        return 0
    try:
        await db.user_pattern_events.insert_many(normalized, ordered=False)
        return len(normalized)
    except Exception as exc:
        logger.warning("[pattern_events] insert_many failed: %s", exc)
        return 0


__all__ = [
    "CATALOG_VERSION",
    "VALID_OUTCOMES",
    "build_event",
    "build_miss_event",
    "deduplicate_events",
    "replace_events_for_game",
]
