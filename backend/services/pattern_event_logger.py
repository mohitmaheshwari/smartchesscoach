"""Per-user pattern event log — the data layer for P2 detector memory.

Records every detector-identified pattern the user encountered, with
outcome (currently MISS only — see Limitations). Aggregated later
into "you've missed pattern X N times" / "you understand pattern Y"
style insights.

Collection schema (`user_pattern_events`):
  {
    "user_id":          str,
    "game_id":          str,
    "move_number":      int,
    "move_san":         str,     # what user actually played
    "best_move_san":    str,     # what engine wanted (the pattern move)
    "pattern_id":       str,     # from pattern_catalog.json
    "outcome":          "miss" | "hit",
    "cp_loss":          int,
    "fen_before":       str,
    "catalog_version":  int,     # bump when catalog semantics change
    "detector_versions": dict,   # {"v5_coaching": 71, ...}
    "created_at":       datetime,
  }

Indexes (created on first write):
  - (user_id, pattern_id)        — primary aggregator path
  - (user_id, game_id)           — for idempotent re-write on regen
  - (user_id, created_at desc)   — for recent-activity views

Idempotent re-write: re-running V5 generation on a game deletes its
existing events for the user before inserting new ones. Prevents
double-counting across regens.

Limitations (v1 — Mohit 2026-05-23):
  - Only "miss" outcomes are recorded. To track "hits" (user played
    the pattern move correctly), detectors would need to run on EVERY
    user move regardless of cp_loss, not just on mistakes — a future
    refactor. Until then we can say "you've missed X N times" but
    not "you usually catch this."
  - Trap_punishment is collapsed into a single pattern_id; per-trap
    splits would need separate IDs in the catalog.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Bump when the resolver logic in pattern_catalog.resolve_pattern_ids
# changes materially (i.e. when a pattern_id starts or stops firing
# under conditions it previously did/didn't). Old events keep their
# stamp so aggregators can decide whether to count or skip them.
CATALOG_VERSION = 1


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
            [("user_id", 1), ("game_id", 1)],
            name="user_pattern_events_user_game",
        )
        await db.user_pattern_events.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="user_pattern_events_user_recent",
        )
        _INDEXES_ENSURED = True
    except Exception as e:
        logger.warning(f"[pattern_events] index ensure failed: {e}")


def build_miss_event(
    *,
    user_id: str,
    game_id: str,
    move_number: int,
    move_san: str,
    best_move_san: str,
    pattern_id: str,
    cp_loss: int,
    fen_before: str,
    detector_versions: Optional[Dict] = None,
) -> Dict:
    """Pure: build an event doc. No DB writes here so callers can batch
    cheaply during V5 generation, then flush once at the end."""
    return {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": move_number,
        "move_san": move_san,
        "best_move_san": best_move_san,
        "pattern_id": pattern_id,
        "outcome": "miss",
        "cp_loss": int(cp_loss or 0),
        "fen_before": fen_before,
        "catalog_version": CATALOG_VERSION,
        "detector_versions": detector_versions or {},
        "created_at": datetime.now(timezone.utc),
    }


async def replace_events_for_game(
    db,
    user_id: str,
    game_id: str,
    events: List[Dict],
) -> int:
    """Idempotent write: delete existing events for this (user, game),
    then bulk-insert the new ones. Returns the number of events
    inserted. Safe to call with an empty list (deletes only).

    Called by V5 generation at the end of a game's processing.
    """
    if not user_id or not game_id:
        return 0
    await _ensure_indexes(db)
    try:
        await db.user_pattern_events.delete_many({
            "user_id": user_id,
            "game_id": game_id,
        })
    except Exception as e:
        logger.warning(f"[pattern_events] delete_many failed: {e}")
    if not events:
        return 0
    try:
        await db.user_pattern_events.insert_many(events, ordered=False)
        return len(events)
    except Exception as e:
        logger.warning(f"[pattern_events] insert_many failed: {e}")
        return 0
