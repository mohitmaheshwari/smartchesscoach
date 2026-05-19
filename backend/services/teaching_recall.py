"""
Cross-game teaching recall — the live lookup layer.

Phase 2.1-2.4. Given the current live-move context (user_id, principle
just fired, current rating, current time control), query
user_teaching_memory for the most resonant past gold moment and return
a recall_block to surface alongside the V5 teaching block.

Vision: "you've been here before." 1200-1500 players remember their
OWN games infinitely better than generic examples. The recall layer
transforms abstract teaching into personal history. See Mohit's
2026-05-19 design discussion.

Voice principles (locked):
  - "you've been here before" tone, not "same Bg5 pin shape"
  - rare and haunting > frequent and helpful — ship at 1 recall/game ceiling
  - strip opponent names (privacy/shame) — anchor on the lesson, not the loss
  - lesson voice, not gotcha voice
  - degrade silently when no history exists (don't promise recall)

Query model:
  - Match on principle_id (Layer 1 — what V1 ships)
  - Weight by recency (decay older entries)
  - Weight by ELO proximity (rating ±200 from current; older mistakes
    when user was 200+ lower-rated are no longer relevant)
  - Filter time-control mismatch (blitz blunders don't apply to daily play)
  - Exclude same game (don't recall the game we're playing right now)
  - Return top 1 — the "haunting" effect dies with multiple hits

The recall_block surfaces ONLY when:
  - User has at least one matching past gold entry
  - Best match's recency_score above threshold (not too stale)
  - Best match within ELO proximity band
  - Not already surfaced in this session (handled at the route layer)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _principles_by_id() -> Dict[str, Dict[str, Any]]:
    """Lazy import so this module's top-level doesn't pull the
    full caption_principles catalog (cyclic risk during tests)."""
    try:
        from services.caption_principles import PRINCIPLES_BY_ID
        return PRINCIPLES_BY_ID
    except Exception:
        return {}


# Recall is more compelling for recent games. Half-life ~14 days.
_RECENCY_DECAY_PER_DAY = math.exp(math.log(0.5) / 14.0)  # ~0.952

# ELO proximity: recall games where user_rating_at_time is within
# ±RATING_BAND of current rating. Beyond this, the recall is about "a
# different player." Higher = more permissive recall, lower = stricter.
RATING_BAND_DEFAULT = 200

# Minimum recency_score (post-decay) to be worth surfacing. A game from
# 30 days ago has recency_score ~ 0.23; a game from 60 days ~0.05.
# 0.15 corresponds to ~40 days.
MIN_RECENCY_SCORE = 0.15

# Cap N candidate documents to read. We pick the top 1 from these.
QUERY_LIMIT = 10


def _classify_time_control_bucket(time_control: Optional[str]) -> str:
    """Bucket time controls so blitz games aren't recalled against rapid
    play and vice versa. Tolerates None / unknown.
    """
    if not time_control:
        return "unknown"
    tc = str(time_control).lower()
    # Chess.com / Lichess style: base_time / increment or "180+2"
    base = 0
    try:
        base = int(tc.split("+")[0].split("/")[0])
    except ValueError:
        return "unknown"
    if base <= 180:
        return "bullet"
    if base <= 599:
        return "blitz"
    if base <= 1799:
        return "rapid"
    return "classical_or_daily"


def _recency_score(occurred_at: Optional[datetime], now: Optional[datetime] = None) -> float:
    """Decay over time, halflife ~14 days."""
    if not occurred_at:
        return 0.0
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(occurred_at, str):
        try:
            occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except Exception:
            return 0.0
    if isinstance(occurred_at, datetime) and occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - occurred_at).total_seconds() / 86400.0)
    return _RECENCY_DECAY_PER_DAY ** days


def _within_elo_band(
    entry_rating: Optional[int],
    current_rating: Optional[int],
    band: int = RATING_BAND_DEFAULT,
) -> bool:
    """True if the entry's rating is close enough to current rating that
    recall is still meaningful. None rating is treated as 'we don't know
    — allow it through' for V1 (better to surface than starve)."""
    if entry_rating is None or current_rating is None:
        return True
    return abs(int(entry_rating) - int(current_rating)) <= band


def _time_control_match(
    entry_tc: Optional[str],
    current_tc: Optional[str],
) -> bool:
    """True if entry's time-control bucket matches the current game's.
    None / unknown is permissive."""
    e_bucket = _classify_time_control_bucket(entry_tc)
    c_bucket = _classify_time_control_bucket(current_tc)
    if e_bucket == "unknown" or c_bucket == "unknown":
        return True
    return e_bucket == c_bucket


def _build_recall_voice(entry: Dict[str, Any]) -> str:
    """Compose the recall caption — "you've been here before" tone.

    Privacy: opponent names are stripped. Anchor on the LESSON, not the
    loss. Format options based on what data the entry has:

      "You faced this same {anchor_name} {N} {days/weeks} ago. Same
       idea here."

      "You missed exactly this idea {N} days ago — {consequence}.
       Watch for it."
    """
    # Source of truth for human-readable principle names is
    # caption_principles.PRINCIPLES (the "name" field). The recall
    # voice should use that, not derive a string from the ID.
    pid = entry.get("principle_id") or ""
    raw_anchor = entry.get("anchor_name") or ""
    anchor: str = ""
    if raw_anchor and not raw_anchor.startswith("TRAP:"):
        anchor = raw_anchor
    elif pid.startswith("TRAP:"):
        # Trap entries: strip the "TRAP:" prefix; the rest is already
        # the human-readable trap name (e.g. "Fried Liver Attack").
        anchor = pid[len("TRAP:"):].strip() or "this idea"
    else:
        # Look up the principle's display name from the catalog.
        catalog_entry = _principles_by_id().get(pid) or {}
        anchor = catalog_entry.get("name") or "this idea"

    occurred = entry.get("occurred_at")
    if isinstance(occurred, str):
        try:
            occurred = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        except Exception:
            occurred = None
    when_phrase = "earlier"
    if isinstance(occurred, datetime):
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        seconds = max(0.0, (datetime.now(timezone.utc) - occurred).total_seconds())
        hours = seconds / 3600.0
        days = int(seconds / 86400.0)
        if hours < 12:
            when_phrase = "earlier today"
        elif days < 1:
            when_phrase = "yesterday" if hours >= 12 else "earlier today"
        elif days == 1:
            when_phrase = "yesterday"
        elif days < 7:
            when_phrase = f"{days} days ago"
        elif days < 14:
            when_phrase = "a week ago"
        elif days < 35:
            weeks = max(2, days // 7)
            when_phrase = f"{weeks} weeks ago"
        else:
            months = max(1, days // 30)
            when_phrase = f"{months} month{'s' if months > 1 else ''} ago"

    gold_class = entry.get("gold_class") or ""
    consequence = entry.get("best_move_consequence")

    # Present the anchor as a tag after an em-dash rather than nested
    # mid-sentence. This avoids two grammar pitfalls caught 2026-05-19:
    #   - Proper nouns ("Fried Liver Attack") shouldn't be lowercased.
    #   - Verb-phrase anchors ("Walk the king to safety") read
    #     awkwardly when nested as "the X idea".
    # Tag-style works uniformly for all anchor shapes.
    anchor_tag = anchor or "this idea"

    if gold_class == "gold":
        if consequence:
            return (
                f"You've been here before. You missed this idea {when_phrase} "
                f"— {consequence}. Watch for it now."
            )
        return (
            f"You've been here before. {when_phrase.capitalize()} you missed "
            f"the same idea — {anchor_tag}. Watch for it now."
        )

    if gold_class == "lucky":
        return (
            f"You've been here before. {when_phrase.capitalize()} this same "
            f"shape was on the board — {anchor_tag} — and your opponent "
            f"missed it. Don't count on it twice."
        )

    if gold_class == "celebration":
        return (
            f"You nailed this exact idea {when_phrase} — {anchor_tag}. "
            f"Same shape on the board now."
        )

    return (
        f"You've been here before. {when_phrase.capitalize()} the same idea "
        f"appeared — {anchor_tag}."
    )


async def get_recall_for_principle(
    db,
    *,
    user_id: str,
    principle_id: str,
    current_game_id: Optional[str],
    current_rating: Optional[int],
    current_time_control: Optional[str],
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Look up the best matching past gold moment for this principle.

    Returns a recall_block dict ready to attach to coach_messages, or
    None when no qualifying entry exists.

    Schema of the returned block:
        {
            "recall_text":         str,             # voice-rendered string
            "ref_game_id":         str,             # for click-through
            "ref_move_number":     int | None,
            "ref_occurred_at":     datetime,
            "principle_id":        str,
            "anchor_name":         str | None,
            "gold_class":          str,
            "recency_score":       float,           # 0..1
            "source":              "v5" | "trap",
        }
    """
    if not (user_id and principle_id):
        return None
    now = now or datetime.now(timezone.utc)

    try:
        cursor = db.user_teaching_memory.find(
            {
                "user_id": user_id,
                "principle_id": principle_id,
                "gold_class": {"$in": ["gold", "lucky", "celebration"]},
                **({"game_id": {"$ne": current_game_id}} if current_game_id else {}),
            },
            {
                "_id": 0,
                "game_id": 1,
                "move_number": 1,
                "occurred_at": 1,
                "user_rating_at_time": 1,
                "time_control": 1,
                "principle_id": 1,
                "anchor_name": 1,
                "gold_class": 1,
                "best_move_consequence": 1,
                "narrative": 1,
                "source": 1,
            },
        ).sort("occurred_at", -1).limit(QUERY_LIMIT)

        candidates: List[Dict[str, Any]] = []
        async for row in cursor:
            if not _within_elo_band(row.get("user_rating_at_time"), current_rating):
                continue
            if not _time_control_match(row.get("time_control"), current_time_control):
                continue
            score = _recency_score(row.get("occurred_at"), now=now)
            if score < MIN_RECENCY_SCORE:
                continue
            row["_recency_score"] = score
            candidates.append(row)

        if not candidates:
            return None

        # Prefer GOLD over LUCKY over CELEBRATION at equal recency
        # (gold = "you missed it" = most teach-worthy).
        priority = {"gold": 0, "lucky": 1, "celebration": 2}
        candidates.sort(
            key=lambda r: (
                priority.get(r.get("gold_class", "celebration"), 3),
                -r["_recency_score"],
            )
        )
        best = candidates[0]
    except Exception as e:
        logger.warning(f"[teaching_recall] query failed for ({user_id}, {principle_id}): {e}")
        return None

    return {
        "recall_text": _build_recall_voice(best),
        "ref_game_id": best.get("game_id"),
        "ref_move_number": best.get("move_number"),
        "ref_occurred_at": best.get("occurred_at"),
        "principle_id": principle_id,
        "anchor_name": best.get("anchor_name"),
        "gold_class": best.get("gold_class"),
        "recency_score": best.get("_recency_score"),
        "source": best.get("source") or "v5",
    }
