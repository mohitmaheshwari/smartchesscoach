"""
Per-user principle-encounter weights for the live-coaching necessity gate.

Implements Phase 1.6 + the necessity layer of the 3-layer silence model
from [[play-with-coach-phase1-design]]. Without this, the V5 teaching
wedge re-fires the same principle every session — Mohit's reverse
catastrophic case.

Model:
  - Each (user_id, principle_id) row carries a `decay_score` and a
    `last_seen_at` timestamp.
  - On fire: decay the existing score for the time elapsed, then add
    +1.0.
  - Read: returns dict {principle_id: current_decay_score} for the
    user (28 rows max).
  - Decay: ~20% per 24h (configurable). Principle fired 4 times today
    = 4.0; after 1 day = 3.2; after 1 week = ~0.84.

The necessity gate consults this in v5_teaching_decision_for_live_move:
if decay_score > rating-band threshold, suppress the fire. Each
user gets to re-encounter a principle once decay drops below threshold.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 20% decay per 24h. half-life ~3.1 days.
_DECAY_PER_HOUR = math.exp(math.log(0.80) / 24.0)  # ~0.9908

# Rating-band thresholds: max decay_score before we silence the
# principle. Higher rating = lower tolerance for repetition (they know
# it; teaching again is noise).
RATING_BAND_THRESHOLDS = {
    "beginner_low":  5.0,   # <1000   — heavy repetition needed for retention
    "beginner_high": 4.0,   # 1000-1399
    "intermediate":  3.0,   # 1400-1799
    "advanced":      2.0,   # 1800+   — see it twice and we move on
}

# Habit principles bypass the necessity gate entirely for sub-1400
# players. Rationale: "count attackers vs defenders" and "check what
# opponent threatens" are PROCESS habits, not one-time lessons. An 800-
# rated player hangs pieces 5-10x per game on the same geometry; we
# need to fire on every occurrence to drum the habit in.
#
# Locked 2026-05-19 after the audit-coverage-tracks-surface review of
# coaching quality at the 800-1400 band.
HABIT_PRINCIPLE_IDS = frozenset({
    "TAC_HANGING_PIECE",
    "TAC_DEFENDER_COUNT",
    "TAC_CHECKS_CAPTURES_THREATS",
    "DEF_MOST_ATTACKED",
})


def _classify_rating_band(user_rating: Optional[int]) -> str:
    if user_rating is None:
        return "intermediate"
    if user_rating < 1000:
        return "beginner_low"
    if user_rating < 1400:
        return "beginner_high"
    if user_rating < 1800:
        return "intermediate"
    return "advanced"


def _decay(prev_score: float, prev_at: datetime, now: datetime) -> float:
    """Apply continuous decay from `prev_at` to `now`."""
    if prev_score <= 0.0:
        return 0.0
    delta_hours = max(0.0, (now - prev_at).total_seconds() / 3600.0)
    return prev_score * (_DECAY_PER_HOUR ** delta_hours)


async def get_user_principle_weights(db, user_id: str) -> Dict[str, float]:
    """Return {principle_id: current_decay_score} for this user.

    Decays each row's stored score forward to NOW so the caller sees
    fresh values without writing. Caller must NOT mutate the result.
    """
    out: Dict[str, float] = {}
    if not user_id:
        return out
    now = datetime.now(timezone.utc)
    try:
        cursor = db.coaching_encounter_weights.find(
            {"user_id": user_id},
            {"_id": 0, "principle_id": 1, "decay_score": 1, "last_seen_at": 1},
        )
        async for row in cursor:
            pid = row.get("principle_id")
            if not pid:
                continue
            prev_score = float(row.get("decay_score") or 0.0)
            prev_at = row.get("last_seen_at")
            if isinstance(prev_at, str):
                try:
                    prev_at = datetime.fromisoformat(prev_at)
                except Exception:
                    prev_at = now
            if not isinstance(prev_at, datetime):
                prev_at = now
            if prev_at.tzinfo is None:
                prev_at = prev_at.replace(tzinfo=timezone.utc)
            out[pid] = _decay(prev_score, prev_at, now)
    except Exception as e:
        logger.warning(f"[encounter-weights] read failed for {user_id} (non-fatal): {e}")
    return out


async def record_principle_fire(db, user_id: str, principle_id: str) -> None:
    """Bump the fire counter for (user_id, principle_id).

    Decays any prior score forward to NOW, then adds +1.0. Idempotent
    failure (best-effort) — never blocks the live response path.
    """
    if not user_id or not principle_id:
        return
    now = datetime.now(timezone.utc)
    try:
        existing = await db.coaching_encounter_weights.find_one(
            {"user_id": user_id, "principle_id": principle_id},
            {"_id": 0, "decay_score": 1, "last_seen_at": 1, "fire_count": 1},
        )
        if existing:
            prev_at = existing.get("last_seen_at")
            if isinstance(prev_at, str):
                try:
                    prev_at = datetime.fromisoformat(prev_at)
                except Exception:
                    prev_at = now
            if not isinstance(prev_at, datetime):
                prev_at = now
            if prev_at.tzinfo is None:
                prev_at = prev_at.replace(tzinfo=timezone.utc)
            decayed = _decay(float(existing.get("decay_score") or 0.0), prev_at, now)
            new_score = decayed + 1.0
            new_fire_count = int(existing.get("fire_count") or 0) + 1
        else:
            new_score = 1.0
            new_fire_count = 1
        await db.coaching_encounter_weights.update_one(
            {"user_id": user_id, "principle_id": principle_id},
            {"$set": {
                "user_id": user_id,
                "principle_id": principle_id,
                "decay_score": new_score,
                "last_seen_at": now,
                "fire_count": new_fire_count,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(
            f"[encounter-weights] write failed for ({user_id}, {principle_id}) "
            f"(non-fatal): {e}"
        )


def necessity_threshold_for_user(user_rating: Optional[int]) -> float:
    """Return the max decay_score below which a principle is still
    'fresh enough' to teach again. Higher = more tolerant of repetition.
    """
    return RATING_BAND_THRESHOLDS[_classify_rating_band(user_rating)]


def passes_necessity_gate(
    principle_id: Optional[str],
    weights: Dict[str, float],
    user_rating: Optional[int],
) -> bool:
    """True if this principle is fresh enough to teach (under threshold).

    Returns True for None / unknown principle (gate doesn't apply to
    shape-pattern-only fires — those have their own freshness via the
    suppression layer).

    Habit principles ([[HABIT_PRINCIPLE_IDS]]) bypass the gate for
    sub-1400 players — process habits need repetition, not silence.
    For 1400+ players, the gate still applies because they've already
    internalized the habit.
    """
    if not principle_id:
        return True
    # Habit-principle bypass for the bands that need repetition.
    if principle_id in HABIT_PRINCIPLE_IDS:
        if user_rating is None or user_rating < 1400:
            return True
    threshold = necessity_threshold_for_user(user_rating)
    current = weights.get(principle_id, 0.0)
    return current < threshold
