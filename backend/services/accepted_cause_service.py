"""Turn a player's accepted reflection answer into durable, provenance-carrying evidence.

WHY THIS EXISTS
The player is shown an engine-verified mistake and asked what they were
thinking, before any reveal. Every existing consumer treats that answer as a
COUNT -- home intelligence counts documents for an engagement score, the
adaptive profile uses the rate to tune UI friction, the behavioural analyzer
uses has_reflection as a boolean. Nothing reads which option they chose. This
module is the first thing that does.

WHY ITS OWN COLLECTION
The obvious home was user_active_focus, and that is unsafe. Its invariant --
one active weakness row per user -- is enforced by an unsorted find_one rather
than a unique index, and routes/training_advanced.py reads it with no `type`
filter at all. A second active row would make "the user's focus"
non-deterministic across the five consumers of get_active_focus_bundle and
leak into Lab Coach's-Pick. So the accepted cause lives here and is JOINED at
render time. It never competes to be the focus.

WHAT IT DELIBERATELY DOES NOT DO
No improvement verdict. The Phase 8 transfer machinery cannot be reused: it
takes no parameter naming what is measured and is gated on a PLAN-grade
authorization that demands board-verified evidence, which a self-report is
not. This module stores what was said, with everything needed to measure it
later, and stops there.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

COLLECTION = "player_accepted_causes"
SOURCE = "player_accepted"
SCHEMA_VERSION = "player_accepted_cause.v1"

# Tiers that produce a stored cause. A non-answer ("not sure", "none of
# these") is the player declining, and the reflection row already records
# that -- writing it here would turn a refusal into evidence.
_STORABLE_TIERS = frozenset({"board_anchored", "self_reported_state"})


def build_accepted_cause_document(
    stored_reflection: Mapping[str, Any],
    *,
    user_id: str,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Derive the storable cause document, or None when there is nothing honest to store.

    Pure: no I/O, so the mapping can be tested without a database.
    """
    from quick_tag_registry import resolve_accepted_cause

    reflection_id = str((stored_reflection or {}).get("reflection_id") or "").strip()
    event = (stored_reflection or {}).get("event") or {}
    response = (stored_reflection or {}).get("response") or {}
    event_id = str(event.get("event_id") or "").strip()
    game_id = str((stored_reflection or {}).get("game_id") or "").strip()
    option_id = str(response.get("selected_option_id") or "").strip()
    if not reflection_id or not event_id or not option_id or not str(user_id or "").strip():
        return None

    cause = resolve_accepted_cause(option_id)
    if not cause or cause.get("tier") not in _STORABLE_TIERS:
        return None

    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        # Same key the reflection upserts on, so re-answering REPLACES the
        # cause instead of appending a second one. store_event_reflection is
        # idempotent on reflection_id = sha256(user_id, game_id, event_id);
        # if this appended, a player changing their mind -- or any client
        # retry -- would inflate their own weakness model.
        "reflection_id": reflection_id,
        "user_id": str(user_id),
        "game_id": game_id,
        "event_id": event_id,
        "selected_option_id": option_id,
        "fundamental": cause.get("fundamental"),
        "predicate": cause.get("predicate"),
        "tier": cause.get("tier"),
        # The whole point: this weakness was accepted by the player, not
        # inferred by a detector. Every reader must be able to tell.
        "source": SOURCE,
        "answered_before_reveal": bool(response.get("answered_before_reveal")),
        "concept_id": str(event.get("concept_id") or "") or None,
        "quality_id": str(event.get("quality_id") or "") or None,
        "vocabulary_version": cause.get("version"),
        "updated_at": stamp,
    }


async def store_accepted_cause(
    collection: Any,
    document: Mapping[str, Any],
) -> Dict[str, Any]:
    """Idempotently upsert one accepted cause, keyed on reflection_id."""
    stored = dict(document)
    await collection.update_one(
        {"reflection_id": stored["reflection_id"]},
        {"$set": stored, "$setOnInsert": {"created_at": stored["updated_at"]}},
        upsert=True,
    )
    return stored


async def record_accepted_cause(
    db: Any,
    stored_reflection: Mapping[str, Any],
    *,
    user_id: str,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Derive and persist. Returns None when nothing storable was derived."""
    document = build_accepted_cause_document(
        stored_reflection, user_id=user_id, now=now
    )
    if not document:
        return None
    return await store_accepted_cause(db[COLLECTION], document)


async def accepted_causes_for_user(
    db: Any,
    user_id: str,
    *,
    limit: int = 200,
) -> list:
    """Every stored accepted cause for one player, newest first."""
    if not str(user_id or "").strip():
        return []
    cursor = db[COLLECTION].find(
        {"user_id": str(user_id), "source": SOURCE},
        {"_id": 0},
    ).sort("updated_at", -1).limit(int(limit))
    return await cursor.to_list(length=int(limit))


def summarize_accepted_causes(documents: Any) -> Dict[str, Dict[str, Any]]:
    """Group stored causes by fundamental for the /progress join.

    Counts DISTINCT games, not rows: two accepted causes in one game is one
    game's worth of evidence, and "you told us this twice" should mean two
    games rather than two clicks.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for doc in documents or []:
        if str((doc or {}).get("source") or "") != SOURCE:
            continue
        fundamental = str((doc or {}).get("fundamental") or "").strip()
        if not fundamental:
            # Self-reported states carry no fundamental and are not grouped
            # here; they are shown on their own terms, never measured.
            continue
        bucket = grouped.setdefault(
            fundamental,
            {
                "fundamental": fundamental,
                "games": set(),
                "events": 0,
                "options": {},
                "source": SOURCE,
            },
        )
        bucket["events"] += 1
        game_id = str(doc.get("game_id") or "").strip()
        if game_id:
            bucket["games"].add(game_id)
        option_id = str(doc.get("selected_option_id") or "").strip()
        if option_id:
            bucket["options"][option_id] = bucket["options"].get(option_id, 0) + 1
    return {
        key: {
            "fundamental": value["fundamental"],
            "accepted_games": len(value["games"]),
            "accepted_events": value["events"],
            "options": dict(sorted(value["options"].items())),
            "source": SOURCE,
        }
        for key, value in sorted(grouped.items())
    }
