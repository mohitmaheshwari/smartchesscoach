"""
OAuth Routes — Connect with Lichess and Chess.com
=================================================

Lichess: PKCE flow (no client_secret needed, unregistered client)
Chess.com: Standard OAuth2 (requires registered app — TODO)

Flow:
1. User clicks "Connect with Lichess"
2. Backend generates PKCE code_verifier + code_challenge
3. Redirects to lichess.org/oauth with challenge
4. User approves on Lichess
5. Lichess redirects back to /api/oauth/lichess/callback with code
6. Backend exchanges code for access_token
7. Fetches user profile from Lichess
8. Stores Lichess username + token on user doc
9. Auto-imports games
"""

import hashlib
import base64
import secrets
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from routes.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

db = None

def init_db(database):
    global db
    db = database

# ─── LICHESS CONFIG ──────────────────────────────────────────────

LICHESS_CLIENT_ID = os.environ.get("LICHESS_CLIENT_ID", "chessguru-app")
LICHESS_REDIRECT_URI = os.environ.get("LICHESS_REDIRECT_URI", "")  # Set in env
LICHESS_SCOPES = "preference:read game:read email:read"

LICHESS_AUTH_URL = "https://lichess.org/oauth"
LICHESS_TOKEN_URL = "https://lichess.org/api/token"
LICHESS_PROFILE_URL = "https://lichess.org/api/account"


# ─── PKCE HELPERS ────────────────────────────────────────────────

def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


# ─── LICHESS CONNECT ─────────────────────────────────────────────

@router.get("/lichess/connect")
async def lichess_connect(request: Request, user: User = Depends(get_current_user)):
    """
    Start Lichess OAuth flow. Redirects user to Lichess authorization page.
    """
    if not LICHESS_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="LICHESS_REDIRECT_URI not configured")

    # Generate PKCE pair
    code_verifier, code_challenge = _generate_pkce()

    # Store verifier in DB (tied to user) so callback can use it
    state = secrets.token_urlsafe(32)
    await db.oauth_states.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "state": state,
            "code_verifier": code_verifier,
            "platform": "lichess",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": LICHESS_CLIENT_ID,
        "redirect_uri": LICHESS_REDIRECT_URI,
        "scope": LICHESS_SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{LICHESS_AUTH_URL}?{query}"

    logger.info(f"[OAUTH] Lichess connect: redirecting user {user.user_id}")
    return RedirectResponse(url=auth_url)


@router.get("/lichess/callback")
async def lichess_callback(code: str = None, state: str = None, error: str = None):
    """
    Lichess OAuth callback. Exchanges code for token, fetches profile, imports games.
    """
    import httpx

    if error:
        logger.warning(f"[OAUTH] Lichess auth error: {error}")
        # Redirect to frontend with error
        frontend_url = os.environ.get("FRONTEND_URL", "")
        return RedirectResponse(url=f"{frontend_url}/settings?lichess_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Find the user by state
    oauth_doc = await db.oauth_states.find_one({"state": state})
    if not oauth_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    user_id = oauth_doc["user_id"]
    code_verifier = oauth_doc["code_verifier"]

    # Exchange code for access token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                LICHESS_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": LICHESS_REDIRECT_URI,
                    "client_id": LICHESS_CLIENT_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                logger.error(f"[OAUTH] Token exchange failed: {token_response.status_code} {token_response.text}")
                frontend_url = os.environ.get("FRONTEND_URL", "")
                return RedirectResponse(url=f"{frontend_url}/settings?lichess_error=token_exchange_failed")

            token_data = token_response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise HTTPException(status_code=500, detail="No access token received")

            # Fetch Lichess profile
            profile_response = await client.get(
                LICHESS_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if profile_response.status_code != 200:
                logger.error(f"[OAUTH] Profile fetch failed: {profile_response.status_code}")
                raise HTTPException(status_code=500, detail="Could not fetch Lichess profile")

            profile = profile_response.json()
            lichess_username = profile.get("username", "")
            lichess_rating = profile.get("perfs", {}).get("rapid", {}).get("rating") or \
                             profile.get("perfs", {}).get("blitz", {}).get("rating") or 1200

            logger.info(f"[OAUTH] Lichess connected: {lichess_username} (rating: {lichess_rating})")

    except httpx.HTTPError as e:
        logger.error(f"[OAUTH] HTTP error during Lichess OAuth: {e}")
        frontend_url = os.environ.get("FRONTEND_URL", "")
        return RedirectResponse(url=f"{frontend_url}/settings?lichess_error=connection_failed")

    # Store Lichess connection on user
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "lichess_username": lichess_username,
            "lichess_token": access_token,
            "lichess_rating": lichess_rating,
            "lichess_connected_at": datetime.now(timezone.utc).isoformat(),
            "lichess_profile": {
                "username": lichess_username,
                "rating": lichess_rating,
                "title": profile.get("title"),
                "url": profile.get("url"),
            },
        }}
    )

    # Clean up state
    await db.oauth_states.delete_one({"state": state})

    # Auto-import recent games
    try:
        from journey_service import sync_user_games
        await sync_user_games(db, user_id, platform="lichess")
        logger.info(f"[OAUTH] Auto-imported Lichess games for {user_id}")
    except Exception as e:
        logger.warning(f"[OAUTH] Auto-import failed (non-fatal): {e}")

    # Redirect to frontend
    frontend_url = os.environ.get("FRONTEND_URL", "")
    return RedirectResponse(url=f"{frontend_url}/settings?lichess_connected=true&username={lichess_username}")


@router.get("/lichess/status")
async def lichess_status(user: User = Depends(get_current_user)):
    """Check if user has connected their Lichess account."""
    user_doc = await db.users.find_one(
        {"user_id": user.user_id},
        {"_id": 0, "lichess_username": 1, "lichess_connected_at": 1, "lichess_rating": 1}
    )
    if user_doc and user_doc.get("lichess_username"):
        return {
            "connected": True,
            "username": user_doc["lichess_username"],
            "rating": user_doc.get("lichess_rating"),
            "connected_at": user_doc.get("lichess_connected_at"),
        }
    return {"connected": False}


@router.post("/lichess/disconnect")
async def lichess_disconnect(user: User = Depends(get_current_user)):
    """Disconnect Lichess account."""
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$unset": {
            "lichess_username": "",
            "lichess_token": "",
            "lichess_rating": "",
            "lichess_connected_at": "",
            "lichess_profile": "",
        }}
    )
    return {"success": True}
