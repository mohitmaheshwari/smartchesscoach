"""Who sees the coaching-room redesign.

The single source of truth for the presentation gate. Nothing else may decide
this -- route handlers ask `is_enabled(user_id)` and the frontend reads the
boolean this produces off `/auth/me`.

Why not a CRA `REACT_APP_*` flag: Create React App substitutes those at build
time, so one bundle carries one value for every visitor. That cannot give two
accounts different presentation on a single deployment, which is exactly what
the pilot needs. See docs/coaching_room_all_pages_spec.md section 5.

This gate carries every rollout stage, so no second mechanism gets built later:

    COACHING_ROOM_V2_USER_IDS="user_a,user_b"   named pilot accounts
    COACHING_ROOM_V2_PERCENT="10"              a stable 10% of everyone
    COACHING_ROOM_V2_USER_IDS="*"              everyone

Unset means off for every account, including admins. Presentation only -- it
must never gate chess content, evidence, or permissions.
"""

import hashlib
import os
from typing import Optional, Set

ALLOWLIST_ENV = "COACHING_ROOM_V2_USER_IDS"
PERCENT_ENV = "COACHING_ROOM_V2_PERCENT"
EVERYONE = "*"


def _allowlist() -> Set[str]:
    """Read at call time so tests and a restarted process agree."""
    raw = os.environ.get(ALLOWLIST_ENV, "") or ""
    return {part.strip() for part in raw.split(",") if part.strip()}


def _percent() -> int:
    raw = (os.environ.get(PERCENT_ENV, "") or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        # A typo must not silently expose the redesign to everyone.
        return 0
    return max(0, min(100, value))


def bucket_of(user_id: str) -> int:
    """A stable 0-99 bucket for a user_id.

    Stable across processes and restarts, so a user does not flip between the
    old and new presentation on every request. Not security-sensitive; md5 is
    used for a fast, stable spread, not to protect anything.
    """
    digest = hashlib.md5(str(user_id or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def is_enabled(user_id: Optional[str]) -> bool:
    """True when this account should be served the new presentation."""
    if not user_id:
        return False
    allowlist = _allowlist()
    if EVERYONE in allowlist:
        return True
    if str(user_id) in allowlist:
        return True
    percent = _percent()
    if percent <= 0:
        return False
    return bucket_of(user_id) < percent
