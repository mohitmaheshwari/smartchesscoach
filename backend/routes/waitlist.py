"""Invite-only waitlist.

Public: anyone can ask for an invite from the landing page.
Admin:  Mohit reviews requests and invites with one click, which is the only
        thing needed — signup_gate treats an "invited" row as the allowlist,
        so the person just signs in with Google and the account is created on
        first login. No passwords, no invite codes.

See docs/invite_only_signup_scope.md.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.admin import require_super_admin
from routes.auth import User
from services.signup_gate import (
    STATUS_INVITED,
    WAITLIST_COLLECTION,
    normalise_email,
    record_request,
    signups_open,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Waitlist"])

db = None


def set_db(database):
    global db
    db = database


class InviteRequest(BaseModel):
    email: str
    name: str = ""
    note: str = ""
    source: str = "landing"


class InviteDecision(BaseModel):
    email: str


@router.get("/signup-status")
async def signup_status():
    """Lets the frontend render the right call-to-action without guessing."""
    return {"signups_open": signups_open()}


@router.post("/waitlist")
async def request_invite(req: InviteRequest):
    """Public. Asking twice is fine and never downgrades an invited person."""
    email = normalise_email(req.email)
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(req.note or "") > 2000 or len(req.name or "") > 200:
        raise HTTPException(status_code=400, detail="That is longer than we can store")

    result = await record_request(
        db,
        email=email,
        name=(req.name or "").strip(),
        note=(req.note or "").strip(),
        source=(req.source or "landing").strip()[:60],
    )
    # Never reveal whether this email is already invited or already a user —
    # the public form answers the same way for everyone.
    return {
        "ok": True,
        "message": "Thanks — you are on the list. We will be in touch.",
        "already_requested": result.get("already_requested", False),
    }


@router.get("/admin/waitlist")
async def list_waitlist(
    status: Optional[str] = None,
    limit: int = 200,
    user: User = Depends(require_super_admin),
):
    """Every request, newest first."""
    query = {}
    if status:
        query["status"] = status
    rows: List[dict] = await (
        db[WAITLIST_COLLECTION]
        .find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(max(1, min(limit, 1000)))
    )
    pending = await db[WAITLIST_COLLECTION].count_documents({"status": "pending"})
    invited = await db[WAITLIST_COLLECTION].count_documents({"status": STATUS_INVITED})
    return {"rows": rows, "counts": {"pending": pending, "invited": invited},
            "signups_open": signups_open()}


@router.post("/admin/waitlist/invite")
async def invite_from_waitlist(
    req: InviteDecision,
    user: User = Depends(require_super_admin),
):
    """One click. Marking the row invited IS the allowlist entry."""
    from datetime import datetime, timezone

    email = normalise_email(req.email)
    row = await db[WAITLIST_COLLECTION].find_one({"email": email}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="No waitlist request for that email")
    await db[WAITLIST_COLLECTION].update_one(
        {"email": email},
        {"$set": {
            "status": STATUS_INVITED,
            "invited_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": getattr(user, "email", None),
        }},
    )
    logger.info(f"[INVITE-ONLY] invited {email} (by {getattr(user, 'email', None)})")
    return {"ok": True, "email": email, "status": STATUS_INVITED}


@router.post("/admin/waitlist/uninvite")
async def uninvite(req: InviteDecision, user: User = Depends(require_super_admin)):
    """Undo — an invite sent by mistake should be revocable before they sign in."""
    email = normalise_email(req.email)
    res = await db[WAITLIST_COLLECTION].update_one(
        {"email": email}, {"$set": {"status": "pending", "invited_at": None}}
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="No waitlist request for that email")
    return {"ok": True, "email": email, "status": "pending"}
