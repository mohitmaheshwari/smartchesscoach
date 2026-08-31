"""One server-owned write path for puzzle attempts and recovery credit."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from services.verified_puzzle_runtime import grade_resolved_puzzle


def _credit_id(user_id: str, puzzle_id: str) -> str:
    return hashlib.sha256(f"{user_id}\0{puzzle_id}".encode("utf-8")).hexdigest()


async def record_verified_puzzle_attempt(
    db,
    *,
    user_id: str,
    puzzle_id: str,
    puzzle: Mapping[str, Any],
    played_uci: str,
    time_taken_ms: Optional[int] = None,
    moves_tried: Optional[list] = None,
    attempt_context: str = "training",
) -> Dict:
    """Grade once on the server, log every try, credit each puzzle once."""
    grade = grade_resolved_puzzle(puzzle, played_uci)
    if grade.get("quality") == "invalid":
        return grade

    now = datetime.now(timezone.utc)
    correct = bool(grade.get("correct"))
    # Only a BROAD/SPECIFIC admission supplies this field. Generic puzzles are
    # still valid calculation practice, but their unverified legacy label must
    # never alter named recovery/decay state.
    weakness = grade.get("recovery_weakness")
    credit_awarded = False
    if correct and weakness:
        claim = await db.puzzle_recovery_credits.update_one(
            {"_id": _credit_id(user_id, puzzle_id)},
            {"$setOnInsert": {
                "user_id": user_id,
                "puzzle_id": puzzle_id,
                "weakness_type": weakness,
                "created_at": now.isoformat(),
            }},
            upsert=True,
        )
        credit_awarded = claim.upserted_id is not None

    await db.puzzle_attempts.insert_one({
        "attempt_id": str(uuid.uuid4()),
        "user_id": user_id,
        "puzzle_id": puzzle_id,
        "correct": correct,
        "quality": grade.get("quality"),
        "played_uci": played_uci,
        "time_taken_ms": time_taken_ms,
        "moves_tried": moves_tried or [],
        "attempt_context": attempt_context,
        "weakness_type": weakness,
        "recovery_credit_awarded": credit_awarded,
        "created_at": now.isoformat(),
    })
    return {**grade, "recovery_credit_awarded": credit_awarded}
