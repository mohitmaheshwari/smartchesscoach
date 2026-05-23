"""Per-user aggregator for the user_pattern_events collection.

Reads the raw event log (one row per detector-fire on a user mistake)
and rolls it up into per-pattern stats consumable by the Insights /
HomePage UI.

Output shape:
  {
    "user_id": str,
    "patterns": [
      {
        "pattern_id":       str,
        "human_name":       str,       # from pattern_catalog.json
        "family":           str,
        "miss_count":       int,
        "first_seen_at":    iso8601,
        "last_seen_at":     iso8601,
        "distinct_games":   int,
        "recent_games":     [game_id, ...],  # up to 5, most-recent first
      },
      ...
    ],
    "totals": {
      "total_misses":   int,
      "patterns_seen":  int,   # distinct pattern_ids with ≥1 miss
    },
  }

Ranking: most-missed first (then by recency). The UI can choose to
show top-N or group by family.

LIMITATION (v1 — same as the writer): only misses are aggregated.
Until detectors run on user GOOD moves too, there's no hit_count.
So we can say "you've missed X N times" but not "K of N — keep it up."
"""
from __future__ import annotations

import logging
from typing import Dict, List

from services.pattern_catalog import get_pattern

logger = logging.getLogger(__name__)


async def get_user_pattern_progress(db, user_id: str) -> Dict:
    """Aggregate the user_pattern_events collection into per-pattern
    stats for one user.

    Cheap: one collection.aggregate() call with a group stage. Trivial
    CPU once the (user_id, pattern_id) index is present.
    """
    if not user_id:
        return {"user_id": "", "patterns": [], "totals": {"total_misses": 0, "patterns_seen": 0}}

    pipeline = [
        {"$match": {"user_id": user_id, "outcome": "miss"}},
        {"$group": {
            "_id": "$pattern_id",
            "miss_count": {"$sum": 1},
            "first_seen_at": {"$min": "$created_at"},
            "last_seen_at": {"$max": "$created_at"},
            "distinct_games": {"$addToSet": "$game_id"},
            # Sample game_ids ordered by created_at; we'll trim client-side.
            "game_events": {"$push": {"game_id": "$game_id", "created_at": "$created_at"}},
        }},
        {"$sort": {"miss_count": -1, "last_seen_at": -1}},
    ]

    patterns: List[Dict] = []
    total_misses = 0
    try:
        async for row in db.user_pattern_events.aggregate(pipeline):
            pattern_id = row.get("_id") or ""
            cat = get_pattern(pattern_id) or {}
            # Sort game_events most-recent-first, dedupe by game_id while preserving order.
            evts = sorted(row.get("game_events") or [], key=lambda e: e.get("created_at") or 0, reverse=True)
            recent_games = []
            for evt in evts:
                gid = evt.get("game_id")
                if gid and gid not in recent_games:
                    recent_games.append(gid)
                if len(recent_games) >= 5:
                    break
            miss_count = int(row.get("miss_count") or 0)
            total_misses += miss_count
            patterns.append({
                "pattern_id": pattern_id,
                "human_name": cat.get("human_name") or pattern_id,
                "short_description": cat.get("short_description"),
                "family": cat.get("family"),
                "miss_count": miss_count,
                "first_seen_at": (row.get("first_seen_at").isoformat()
                                  if row.get("first_seen_at") else None),
                "last_seen_at": (row.get("last_seen_at").isoformat()
                                 if row.get("last_seen_at") else None),
                "distinct_games": len(row.get("distinct_games") or []),
                "recent_games": recent_games,
            })
    except Exception as e:
        logger.warning(f"[pattern_progress] aggregate failed for {user_id}: {e}")
        return {
            "user_id": user_id,
            "patterns": [],
            "totals": {"total_misses": 0, "patterns_seen": 0},
            "error": "aggregate_failed",
        }

    return {
        "user_id": user_id,
        "patterns": patterns,
        "totals": {
            "total_misses": total_misses,
            "patterns_seen": len(patterns),
        },
    }
