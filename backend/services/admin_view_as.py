"""Let a super-admin browse the product as one of their users, read-only.

Mohit sat with a user whose pages looked empty and had no way to see what that
user was seeing. Working it out afterwards took nginx logs, account
comparisons and cookie-origin checks; none of that is available in the moment,
in front of the person.

Two decisions are load-bearing.

**The admin stays logged in as themselves.** `session_token` is never touched.
A view-as session is a second, separate cookie, so exiting is one request and
can never log the admin out or leave them stranded in someone else's account.
It also means authority is re-derived from the admin's real session on every
single request: revoke their role and the next request stops resolving.

**Writes are refused, at one choke point.** `get_current_user` is a dependency
every authenticated endpoint already uses, so the block is inherited rather
than opted into -- a new endpoint cannot forget it, because there is nothing
to remember. The reason it is refused rather than sandboxed: this product's
premise is that a player's coaching reflects *their* play. An admin solving a
puzzle while viewing as someone would move that person's mastery state and
decay model, and afterwards nothing could say which moves were whose.

The target's own `session_token` is never read and never returned. A view-as
session carries its own freshly minted token, and possessing that token grants
exactly one thing: read access, for thirty minutes, to pages the admin could
already have read straight out of the database.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

COOKIE_NAME = "view_as_token"
COLLECTION = "admin_view_sessions"

TTL_MINUTES = 30

# Methods that cannot change anything, so they are the only ones allowed.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# The exit must work while a session is active, so it is exempt from the
# write block. Matched on the path suffix because the router prefix is /api.
EXIT_PATH_SUFFIX = "/admin/view-as"

READ_ONLY_MESSAGE = (
    "Read-only while viewing as another user. Exit view-as to do this on "
    "your own account."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Any) -> Optional[datetime]:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_write(method: str, path: str) -> bool:
    """Whether this request would be refused during a view-as session."""
    if str(method or "").upper() in SAFE_METHODS:
        return False
    return not str(path or "").rstrip("/").endswith(EXIT_PATH_SUFFIX)


def may_view_as(admin: Any, is_admin_email) -> bool:
    """The same two conditions `require_super_admin` applies.

    Passed in rather than imported so this module does not depend on the
    admin router, which imports plenty of other things.
    """
    if getattr(admin, "role", None) != "super_admin":
        return False
    return bool(is_admin_email(getattr(admin, "email", None)))


async def start(
    db,
    *,
    admin: Any,
    target_user_id: str,
    ip: str = "",
    user_agent: str = "",
) -> Dict[str, Any]:
    """Open a session. Raises ValueError with a user-safe reason."""
    target_user_id = str(target_user_id or "").strip()
    if not target_user_id:
        raise ValueError("No user given")

    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0})
    if not target:
        raise ValueError("No such user")

    # Nothing here should be a route to more privilege than the caller has.
    if target.get("role") == "super_admin":
        raise ValueError("Cannot view as another super admin")

    admin_id = str(getattr(admin, "user_id", "") or "")
    # One at a time. A second click replaces the first rather than leaving an
    # orphan that keeps working.
    await db[COLLECTION].update_many(
        {"admin_user_id": admin_id, "ended_at": None},
        {"$set": {"ended_at": _now(), "ended_reason": "replaced"}},
    )

    token = secrets.token_urlsafe(32)
    now = _now()
    await db[COLLECTION].insert_one({
        "view_token": token,
        "admin_user_id": admin_id,
        "admin_email": getattr(admin, "email", None),
        "target_user_id": target_user_id,
        "target_email": target.get("email"),
        "created_at": now,
        "expires_at": now + timedelta(minutes=TTL_MINUTES),
        "ended_at": None,
        "ip": ip,
        "user_agent": user_agent[:300],
    })
    logger.info(
        "view-as started: %s -> %s", admin_id or "?", target_user_id
    )
    return {
        "token": token,
        "target_user_id": target_user_id,
        "target_name": target.get("name"),
        "target_email": target.get("email"),
        "expires_at": (now + timedelta(minutes=TTL_MINUTES)).isoformat(),
        "read_only": True,
    }


async def resolve(db, token: str, admin: Any, is_admin_email) -> Optional[Dict[str, Any]]:
    """The live session for this token, or None.

    Authority is re-derived from `admin` -- the user the real session belongs
    to -- on every call, so a revoked role takes effect on the next request
    rather than whenever the session happens to expire.
    """
    token = str(token or "").strip()
    if not token or not may_view_as(admin, is_admin_email):
        return None

    row = await db[COLLECTION].find_one({"view_token": token}, {"_id": 0})
    if not row or row.get("ended_at"):
        return None
    if row.get("admin_user_id") != str(getattr(admin, "user_id", "") or ""):
        # The token belongs to a different admin. Possessing it is not enough.
        return None
    expires_at = _as_aware(row.get("expires_at"))
    if expires_at is None or expires_at < _now():
        return None
    return {
        "admin_user_id": row.get("admin_user_id"),
        "admin_email": row.get("admin_email"),
        "target_user_id": row.get("target_user_id"),
        "target_email": row.get("target_email"),
        "expires_at": expires_at.isoformat(),
        "read_only": True,
    }


async def end(db, token: str, reason: str = "exited") -> bool:
    """Close a session. Holding the token is enough to end it."""
    token = str(token or "").strip()
    if not token:
        return False
    result = await db[COLLECTION].update_many(
        {"view_token": token, "ended_at": None},
        {"$set": {"ended_at": _now(), "ended_reason": reason}},
    )
    return bool(result.modified_count)


async def recent(db, limit: int = 50) -> list:
    """The audit trail, newest first. Ended rows are kept deliberately."""
    return await db[COLLECTION].find(
        {}, {"_id": 0, "view_token": 0}
    ).sort("created_at", -1).to_list(limit)
