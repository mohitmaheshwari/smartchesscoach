"""
Mirror Window Engagement
========================

The Home Mirror groups games into "windows" — a window is the stretch
of analyzed imported games since the user last meaningfully engaged
with the coach (clicked Open in Lab, opened a game review, or clicked
a training/opening CTA).

Why windows: a single user can play 5 games back-to-back. Per-game
mirror updates would just overwrite themselves and flicker. The window
aggregates the recent stretch into one verdict.

When a window CLOSES, we persist a snapshot — the patterns flagged in
those games — so the next window can ask "did the user actually do
something about what I called out?".

Honest signal of "listening":
  Last window flagged piece_safety in 3 games.
  This window: 0 piece_safety in 3 new games.
  → "You listened. Pattern broken."

Storage shape (embedded on the users doc):
  {
    "mirror_window": {
      "opened_at": datetime,
      "snapshots": [             # FIFO, capped at MAX_SNAPSHOTS
        {
          "opened_at": datetime,
          "closed_at": datetime,
          "closed_reason": "lab_open" | "game_open" | "train_click" | "auto_stale",
          "game_ids": [...],
          "game_count": int,
          "patterns_flagged": [...],   # gaps that REPEATED in this window
          "outcomes": {"won": int, "lost": int, "drawn": int}
        },
        ...
      ]
    }
  }
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cap on persisted snapshots per user. Five gives us "the trend over a
# few sessions" without bloating the user doc.
MAX_SNAPSHOTS = 5

# Hard ceiling on how far back the Mirror window can stretch. If the
# user goes silent for a full day, drop the old games rather than
# carrying them forward forever — staleness corrupts the verdict.
WINDOW_MAX_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(v) -> Optional[datetime]:
    """Normalize datetime/iso-string to a tz-aware UTC datetime."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


async def get_window_open_floor(db, user_id: str) -> datetime:
    """Return the datetime that bounds the current Mirror window:
    games with imported_at > floor are in the window. The floor is
    max(stored opened_at, now - WINDOW_MAX_HOURS) so windows can't
    drift older than the cap.
    """
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mirror_window.opened_at": 1},
    )
    stored = _to_dt((user or {}).get("mirror_window", {}).get("opened_at"))
    auto_floor = _utcnow() - timedelta(hours=WINDOW_MAX_HOURS)
    if stored is None:
        return auto_floor
    return max(stored, auto_floor)


async def latest_snapshot(db, user_id: str) -> Optional[Dict]:
    """Most recently CLOSED window's snapshot, or None."""
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mirror_window.snapshots": 1},
    )
    snaps = (user or {}).get("mirror_window", {}).get("snapshots") or []
    if not snaps:
        return None
    return snaps[-1]


async def close_window(
    db,
    user_id: str,
    closed_reason: str,
    game_ids: List[str],
    patterns_flagged: List[str],
    outcomes: Dict[str, int],
) -> None:
    """Snapshot the current open window and advance opened_at to now.
    Caller is responsible for computing the snapshot fields (we don't
    re-fetch — the Mirror service has already done the work).

    Idempotent guard: if the current window is empty (no games), we
    don't bother snapshotting — there's nothing to remember.
    """
    if not game_ids:
        # Still advance opened_at so the next read starts fresh.
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"mirror_window.opened_at": _utcnow()}},
        )
        return

    floor = await get_window_open_floor(db, user_id)
    snapshot = {
        "opened_at": floor,
        "closed_at": _utcnow(),
        "closed_reason": closed_reason,
        "game_ids": list(game_ids),
        "game_count": len(game_ids),
        "patterns_flagged": sorted(set(patterns_flagged)),
        "outcomes": dict(outcomes),
    }

    # Trim to MAX_SNAPSHOTS by computing in-memory, since pymongo's $slice
    # on push uses a slightly awkward syntax and motor handles dicts cleanly.
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mirror_window.snapshots": 1},
    )
    snaps = (user or {}).get("mirror_window", {}).get("snapshots") or []
    snaps.append(snapshot)
    snaps = snaps[-MAX_SNAPSHOTS:]

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "mirror_window.opened_at": _utcnow(),
            "mirror_window.snapshots": snaps,
        }},
    )
