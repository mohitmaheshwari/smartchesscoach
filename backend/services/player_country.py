"""player_country.py — the ONE place ChessGuru resolves a player's country.

Nothing in the product captured country before 2026-08-24. Both platforms
expose it and both were being discarded:

  Lichess    /api/account  -> profile.country   already an ISO-3166 alpha-2 code
  Chess.com  /pub/player/{u} -> country          a URL, e.g.
                                https://api.chess.com/pub/country/IN

Two platforms, two shapes, one stored field. Resolving in one module keeps the
normalisation honest -- a caller must not store a chess.com URL in the same
field a lichess ISO code goes into.

Storage contract on `users`:
    country         ISO-3166 alpha-2, upper case, e.g. "IN"   (None when unknown)
    country_source  "lichess" | "chesscom"                    (which platform said so)

Chess.com is queryable WITHOUT auth, so it can backfill existing accounts.
Lichess needs the user's token, so it is forward-only.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ISO2 = re.compile(r"^[A-Za-z]{2}$")

# Chess.com does not use pure ISO-3166. It adds four X-prefixed codes:
#   XE England, XS Scotland, XW Wales  -- real places, keep them
#   XX International                   -- explicitly NOT a country; it is
#                                         chess.com's "unset / prefer not to say"
# A live dry run over 117 users returned one XX. Storing that as a country
# would assert a fact the user declined to give, so it resolves to unknown.
_NOT_A_COUNTRY = {"XX"}


def normalize_iso2(value: Optional[str]) -> Optional[str]:
    """Accept either a bare ISO code or a chess.com country URL; return 'IN'.

    Chess.com's field is a URL, not a code -- storing it raw would put
    'https://api.chess.com/pub/country/IN' next to lichess's 'IN' in the same
    field and quietly break every comparison downstream.
    """
    if not value or not isinstance(value, str):
        return None
    tail = value.rstrip("/").rsplit("/", 1)[-1].strip()
    if not _ISO2.match(tail):
        return None
    code = tail.upper()
    return None if code in _NOT_A_COUNTRY else code


def country_from_lichess_profile(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    """Lichess /api/account nests it under `profile`, which is often absent."""
    return normalize_iso2(((profile or {}).get("profile") or {}).get("country"))


async def fetch_chesscom_country(username: str, client=None) -> Optional[str]:
    """Chess.com public profile -> ISO code. No auth required.

    Returns None on any failure: a missing country must never break linking,
    syncing or a backfill run.
    """
    if not username:
        return None
    import httpx

    owns_client = client is None
    try:
        if owns_client:
            client = httpx.AsyncClient(timeout=10.0)
        resp = await client.get(
            f"https://api.chess.com/pub/player/{username.strip().lower()}",
            headers={"User-Agent": "ChessGuru/1.0 (+https://chessguru.ai)"},
        )
        if resp.status_code != 200:
            return None
        return normalize_iso2((resp.json() or {}).get("country"))
    except Exception as e:
        logger.debug(f"[country] chess.com lookup failed for {username}: {e}")
        return None
    finally:
        if owns_client and client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


def country_update_fields(country: Optional[str], source: str) -> Dict[str, str]:
    """The $set fragment to merge into a users update. Empty when unknown, so a
    failed lookup never overwrites a country we already knew."""
    if not country:
        return {}
    return {"country": country, "country_source": source}
