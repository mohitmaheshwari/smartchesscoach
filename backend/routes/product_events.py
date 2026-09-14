"""Where product events actually land.

Forty-odd funnel events have been defined and fired in the frontend for
months -- DIAGNOSTIC_STARTED, DIAGNOSTIC_FIRST_ANSWER, DIAGNOSTIC_ABANDONED,
FUNNEL_ACTIVATION_CTA, FUNNEL_HOME_CTA_CLICKED -- and every one of them was a
no-op. `track()` guards on `window.posthog`, nothing ever calls
`posthog.init()`, there is no project key in the built bundle and no
POSTHOG env on the server. So nothing about what a player does has ever been
recorded, and every question about behaviour has had to be reconstructed from
database side-effects.

This is the sink: our own collection, no third party. Pre-launch the volume is
tiny and the questions are ours, so shipping behaviour to an external service
is a decision to make later and deliberately, not a default.

WHAT IS AND IS NOT STORED
The client already filters to an allow-list of event ids and prop keys before
anything is sent (frontend/src/lib/analytics.js). This layer does not repeat
that vocabulary -- that would be a second copy of a list that already has an
owner -- it enforces SHAPE: how many events, how long a name, how many props,
scalars only, how long a value. Anything outside those bounds is dropped
rather than rejected, because a malformed beacon must never cost a player
their action.

No free text is accepted. Values are truncated. The user id is attached
server-side from the session, never trusted from the client.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

db = None

COLLECTION = "product_events"
SCHEMA_VERSION = "product_events.v1"

# Shape bounds. Deliberately generous for real use and tight enough that a
# bad actor cannot turn this into storage.
MAX_EVENTS_PER_BATCH = 50
MAX_EVENT_NAME = 64
MAX_PROPS = 24
MAX_KEY_LENGTH = 48
MAX_VALUE_LENGTH = 200


def set_db(database):
    global db
    db = database


class EventBatch(BaseModel):
    events: List[Dict[str, Any]] = []


def _clean_value(value: Any) -> Optional[Any]:
    """Scalars only, bounded. Anything else is dropped."""
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:MAX_VALUE_LENGTH] if text else None
    return None


def _clean_props(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    props: Dict[str, Any] = {}
    for key, value in raw.items():
        if len(props) >= MAX_PROPS:
            break
        name = str(key or "").strip()[:MAX_KEY_LENGTH]
        if not name:
            continue
        cleaned = _clean_value(value)
        if cleaned is not None:
            props[name] = cleaned
    return props


def _clean_batch(raw_events: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_events, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in raw_events[:MAX_EVENTS_PER_BATCH]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("event") or "").strip()[:MAX_EVENT_NAME]
        if not name:
            continue
        cleaned.append({"event": name, "props": _clean_props(item.get("props"))})
    return cleaned


async def ensure_product_event_indexes(database) -> None:
    collection = database[COLLECTION]
    await collection.create_index([("event", 1), ("occurred_at", -1)])
    await collection.create_index([("user_id", 1), ("occurred_at", -1)])
    await collection.create_index("occurred_at")


async def _optional_user_id(request: Request) -> Optional[str]:
    """The signed-in user, or None.

    get_current_user raises 401 for an anonymous caller, and anonymous is
    exactly the part of the funnel we cannot currently see -- the landing page
    fires before anyone has signed in. So the 401 is swallowed here rather
    than turning a beacon into an error.
    """
    try:
        user = await get_current_user(request)
    except Exception:
        return None
    return getattr(user, "user_id", None)


@router.post("/events")
async def record_product_events(payload: EventBatch, request: Request):
    """Record a batch of product events. Never fails the caller.

    Anonymous is a first-class case: the landing page fires before anyone has
    signed in, and that is exactly the part of the funnel we cannot currently
    see.
    """
    events = _clean_batch(payload.events)
    if not events or db is None:
        return {"stored": 0}

    now = datetime.now(timezone.utc)
    user_id = await _optional_user_id(request)
    documents = [
        {
            "schema_version": SCHEMA_VERSION,
            "event": item["event"],
            "props": item["props"],
            # Attached here, never taken from the client.
            "user_id": user_id,
            "anonymous": user_id is None,
            "occurred_at": now,
        }
        for item in events
    ]
    try:
        await db[COLLECTION].insert_many(documents, ordered=False)
    except Exception:
        # A beacon is never worth an error in front of a player.
        logger.exception("[product_events] insert failed")
        return {"stored": 0}
    return {"stored": len(documents)}
