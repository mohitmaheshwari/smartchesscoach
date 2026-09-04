"""Canonical evidence contract for puzzle attempts.

The route owns database lookups (prior attempts and current rating); this
pure builder owns normalization so every caller produces the same v2 shape.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


ATTEMPT_SCHEMA_VERSION = "puzzle_attempt.v2"
SUPPORT_LEVELS = {"none", "hint", "reveal", "guided", "unknown"}


def build_puzzle_attempt_evidence(
    *,
    request: Mapping[str, Any],
    user_id: str,
    prior_attempts: int,
    rating_evidence: Mapping[str, Any],
    created_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a normalized, provenance-bearing puzzle-attempt record."""
    correct = bool(request.get("correct", False))
    outcome = str(request.get("outcome") or ("correct" if correct else "incorrect")).strip().lower()
    if outcome not in {"correct", "incorrect"}:
        outcome = "correct" if correct else "incorrect"

    support_level = str(request.get("support_level") or "unknown").strip().lower()
    if support_level not in SUPPORT_LEVELS:
        support_level = "unknown"

    attempt_ordinal = max(0, int(prior_attempts)) + 1
    is_first_attempt = attempt_ordinal == 1
    time_taken_ms = request.get("time_taken_ms")
    if not isinstance(time_taken_ms, (int, float)) or time_taken_ms < 0:
        time_taken_ms = None
    elif time_taken_ms:
        time_taken_ms = int(time_taken_ms)

    moves_tried = request.get("moves_tried")
    if not isinstance(moves_tried, list):
        moves_tried = []
    moves_tried = [str(move)[:16] for move in moves_tried[:20]]

    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return {
        "attempt_schema_version": ATTEMPT_SCHEMA_VERSION,
        "user_id": user_id,
        "puzzle_id": request.get("puzzle_id"),
        "correct": correct,
        "outcome": outcome,
        "attempt_ordinal": attempt_ordinal,
        "is_first_attempt": is_first_attempt,
        "support_level": support_level,
        "counts_as_independent_attempt": is_first_attempt and support_level == "none",
        "solver_rating": rating_evidence.get("rating"),
        "solver_rating_source": str(rating_evidence.get("source") or "unknown")[:80],
        "solver_rating_measured": bool(rating_evidence.get("measured", False)),
        "surface": str(request.get("surface") or "unknown")[:80],
        "puzzle_source": str(request.get("puzzle_source") or "unknown")[:80],
        "time_taken_ms": time_taken_ms,
        "moves_tried": moves_tried,
        "weakness_type": str(request.get("weakness_type") or "unknown")[:80],
        "quality": request.get("quality"),
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
    }
