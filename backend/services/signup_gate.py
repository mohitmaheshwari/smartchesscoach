"""Invite-only signup gate.

ChessGuru is going on social media before it is open to everyone, so account
CREATION is closed while authentication stays completely untouched: every
existing user signs in exactly as before, because the Google callback matches
on `email` and finds them. See docs/invite_only_signup_scope.md.

A new account may be created when EITHER
  * SIGNUPS_OPEN=true  — the post-launch posture, or
  * the email has a waitlist row with status "invited" — which is what
    Mohit's one-click Invite button sets.

Nothing here issues passwords or invite codes: the allowlist IS the email, so
an invited person just signs in with Google and the account is created on
first login.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

WAITLIST_COLLECTION = "waitlist"

STATUS_PENDING = "pending"
STATUS_INVITED = "invited"

_TRUE = {"1", "true", "yes", "on"}


def signups_open() -> bool:
    """Whether anyone may create an account. Fail CLOSED by default.

    Default false is deliberate: this ships while Mohit is posting publicly,
    and the failure we cannot have is the gate quietly being open.
    """
    return os.environ.get("SIGNUPS_OPEN", "false").strip().lower() in _TRUE


def normalise_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


async def is_invited(db, email: Optional[str]) -> bool:
    """True when this email has been invited from the waitlist."""
    addr = normalise_email(email)
    if not addr:
        return False
    row = await db[WAITLIST_COLLECTION].find_one(
        {"email": addr, "status": STATUS_INVITED}, {"_id": 1}
    )
    return row is not None


async def signup_allowed(db, email: Optional[str]) -> bool:
    """May we create an account for this email right now?"""
    if signups_open():
        return True
    return await is_invited(db, email)


async def record_request(
    db,
    email: str,
    name: str = "",
    note: str = "",
    source: str = "landing",
) -> Dict[str, Any]:
    """Upsert a waitlist request. Re-requesting is not an error and never
    downgrades someone who has already been invited."""
    addr = normalise_email(email)
    now = datetime.now(timezone.utc).isoformat()
    existing = await db[WAITLIST_COLLECTION].find_one({"email": addr}, {"_id": 0})
    if existing:
        await db[WAITLIST_COLLECTION].update_one(
            {"email": addr},
            {"$set": {
                "name": name or existing.get("name") or "",
                "note": note or existing.get("note") or "",
                "last_requested_at": now,
            }},
        )
        return {"email": addr, "status": existing.get("status") or STATUS_PENDING,
                "already_requested": True}
    await db[WAITLIST_COLLECTION].insert_one({
        "email": addr,
        "name": name or "",
        "note": note or "",
        "source": source or "landing",
        "status": STATUS_PENDING,
        "created_at": now,
        "last_requested_at": now,
        "invited_at": None,
        "invited_by": None,
    })
    return {"email": addr, "status": STATUS_PENDING, "already_requested": False}
