"""The Why queue: positions the button could not explain, studied later.

Mohit, 2026-11-02: "when we click why and it finds no tactics, it should store
in a queue which should run automatically on Claude, local scheduler on this
machine, and then submit the reason back to that position."

Scope: docs/why_queue_claude_scope.md. Signed with three answers: review the
first batch before anything is shown, queue only what a Why click could not
explain, both sides.

Two collections, both keyed by POSITION (the first four FEN fields plus the
move played), never by game: the same position in nine games is studied once.

  why_queue    one row per position still to study, with every (game, move,
               side, user) that asked for it
  why_reasons  what the study produced: the reason, its claims, what the gate
               said about each claim, and whether a human has let it ship

Only `published` rows ever reach a player. Everything else the route turns
into "the coach will study this one" or into nothing at all.

This module holds no engine and no model: the worker on Mohit's machine does
the studying (scripts/why_queue_worker.py); the route only asks two questions
of it, "is there a published answer" and "queue this".
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

QUEUE_COLLECTION = "why_queue"
REASONS_COLLECTION = "why_reasons"

# why_queue.status
QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
# why_reasons.status
HELD_FOR_REVIEW = "held_for_review"   # gate passed, waiting for a human (review-first)
HELD = "held"                         # gate failed: a claim did not replay
PUBLISHED = "published"
REJECTED = "rejected"
NO_LESSON = "no_lesson"

# The live reasons that mean "nothing to say": these are studied. The engine's
# own choice (engine_choice / no_gap) is not a silence, it is an answer, and an
# engine error is an outage, not a position.
STUDY_WHEN = frozenset({"no_mechanism", "shared_consequence_only", "no_explainable_candidate"})

# Review-first is the default Mohit chose. Flip to "1" only after the first
# batch has been graded (scope: 30 positions).
AUTO_PUBLISH = os.environ.get("WHY_QUEUE_AUTO_PUBLISH", "0") == "1"

STUDYING_LINE = "The coach will study this one and leave the answer here."
NO_LESSON_LINE = ("The coach studied this one: there is no single lesson here, "
                  "the position is simply a little worse.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fen4(fen: str) -> str:
    return " ".join(str(fen or "").split()[:4])


def position_key(fen_before: str, played_san: str) -> str:
    """One key per position-and-move. The move counters are left out on purpose."""
    return f"{fen4(fen_before)}|{str(played_san or '').strip()}"


async def ensure_indexes(db) -> None:
    await db[QUEUE_COLLECTION].create_index("key", unique=True)
    await db[QUEUE_COLLECTION].create_index([("status", 1), ("created_at", 1)])
    await db[REASONS_COLLECTION].create_index("key", unique=True)
    await db[REASONS_COLLECTION].create_index("status")


async def enqueue(db, *, fen_before: str, played_san: str, game_id: str, move_number: int,
                  opponent: bool, user_id: str, stored_best: Optional[str], stored_class: Optional[str],
                  rating: Optional[int], live_reason: Optional[str],
                  differential: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Record that this position wants studying. Idempotent per position; every
    asker is kept so the answer can be traced back to each card that wanted it."""
    key = position_key(fen_before, played_san)
    request = {"game_id": game_id, "move_number": int(move_number),
               "side": "opponent" if opponent else "user", "user_id": user_id, "requested_at": _now()}
    await db[QUEUE_COLLECTION].update_one(
        {"key": key},
        {
            "$setOnInsert": {
                "key": key, "fen_before": fen_before, "played_san": played_san,
                "side_to_move": "white" if " w " in f" {fen_before} " else "black",
                "status": QUEUED, "attempts": 0, "created_at": _now(),
            },
            "$set": {
                "stored_best": stored_best, "stored_class": stored_class, "rating": rating,
                "live_reason": live_reason, "differential": differential or None,
                "last_requested_at": _now(),
            },
            "$addToSet": {"requests": request},
        },
        upsert=True,
    )
    row = await db[QUEUE_COLLECTION].find_one({"key": key}, {"_id": 0, "status": 1})
    return {"key": key, "status": (row or {}).get("status", QUEUED)}


async def lookup(db, fen_before: str, played_san: str) -> Dict[str, Any]:
    """What the store knows about this position: the reason row and the queue row."""
    key = position_key(fen_before, played_san)
    reason = await db[REASONS_COLLECTION].find_one({"key": key}, {"_id": 0})
    queue = await db[QUEUE_COLLECTION].find_one({"key": key}, {"_id": 0, "status": 1})
    return {"key": key, "reason": reason, "queue_status": (queue or {}).get("status")}


def _arrows(claims: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, str]]:
    """Arrows the card can draw: a claim's subject square to its target square."""
    out: List[Dict[str, str]] = []
    for c in claims or []:
        a, b = c.get("subject"), c.get("target")
        if a and b and a != b and {"from": a, "to": b} not in out:
            out.append({"from": str(a), "to": str(b)})
        if len(out) >= limit:
            break
    return out


def studied_response(reason: Dict[str, Any], *, move_number: int, played_san: str,
                     fen_before: str) -> Dict[str, Any]:
    """A published study, in the Why endpoint's existing contract."""
    claims = list(reason.get("claims") or [])
    return {
        "found": True,
        "direction": "missed",
        "mechanism": "STUDIED",
        "text": reason.get("reason"),
        "move_san": reason.get("better_san"),
        "line_san": [reason.get("better_san")] if reason.get("better_san") else [],
        "arrows": _arrows(claims),
        "candidate_rank": None,
        "eval_gap_cp": None,
        "payoff_cp": None,
        "punishment": None,
        "engine": "studied",
        "better_move": reason.get("better_san"),
        "causes": [],
        "facts": {"claims": claims},
        "move_number": move_number,
        "played_san": played_san,
        "fen_before": fen_before,
        "study": {"state": "published", "studied_at": reason.get("created_at"),
                  "published_at": reason.get("published_at")},
    }


def study_state(reason: Optional[Dict[str, Any]], queue_status: Optional[str]) -> Optional[Dict[str, Any]]:
    """What to tell the card about a position that has no live answer.

    `studying`  queued, running, or waiting for a human: the card says so.
    `no_lesson` the study said there is nothing to teach: the card says that.
    None        rejected by a human, or never asked: the card adds nothing.
    """
    status = (reason or {}).get("status")
    if status == NO_LESSON:
        return {"state": "no_lesson", "text": NO_LESSON_LINE}
    if status == REJECTED:
        return None
    if status in (HELD_FOR_REVIEW, HELD) or queue_status in (QUEUED, RUNNING):
        return {"state": "studying", "text": STUDYING_LINE}
    if queue_status in (DONE, FAILED):
        # done without a reason row is a worker bug; failed is an outage. Say
        # "studying" rather than nothing: the position is still in the system.
        return {"state": "studying", "text": STUDYING_LINE}
    return None


async def on_nothing_found(db, out: Dict[str, Any], *, fen_before: str, played_san: str,
                           game_id: str, move_number: int, opponent: bool, user_id: str,
                           stored_best: Optional[str], stored_class: Optional[str],
                           rating: Optional[int], differential: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The route's one call on a `found: false` exit.

    Returns the studied answer when one is published; otherwise queues the
    position (first time) and adds `study` to the found-false answer. Never
    raises: a queue problem must not break the button.
    """
    try:
        if out.get("reason") not in STUDY_WHEN:
            return out
        known = await lookup(db, fen_before, played_san)
        reason = known.get("reason")
        if reason and reason.get("status") == PUBLISHED:
            return studied_response(reason, move_number=move_number, played_san=played_san,
                                    fen_before=fen_before)
        queue_status = known.get("queue_status")
        first_time = reason is None and queue_status is None
        if first_time or queue_status in (QUEUED, RUNNING):
            queued = await enqueue(db, fen_before=fen_before, played_san=played_san, game_id=game_id,
                                   move_number=move_number, opponent=opponent, user_id=user_id,
                                   stored_best=stored_best, stored_class=stored_class, rating=rating,
                                   live_reason=out.get("reason"), differential=differential)
            queue_status = queued["status"]
        state = study_state(reason, queue_status)
        if state:
            out["study"] = state
        return out
    except Exception:                                   # noqa: BLE001
        logger.exception("why queue failed for %s move %s", game_id, move_number)
        return out


# --- the review side: the admin tab reads and rules on these -----------------

def review_row(reason: Dict[str, Any]) -> Dict[str, Any]:
    """A why_reasons row in the shape the geometry-gaps claude panel draws."""
    gate = reason.get("gate") or {}
    failures = list(gate.get("failures") or [])
    passed = bool(gate.get("passed"))
    probes = []
    for c in reason.get("claims") or []:
        probes.append({
            "label": c.get("label") or c.get("note") or c.get("kind"),
            "kind": c.get("kind"),
            "verdict": "passed" if c.get("verified") else ("FAILED: " + str(c.get("failure") or "")),
        })
    status = reason.get("status")
    if status == NO_LESSON:
        bucket = "why queue · no lesson"
    elif passed:
        bucket = "why queue · awaiting your ruling"
    else:
        bucket = "why queue · gate failed: " + (failures[0] if failures else "?")
    packet = reason.get("packet") or {}
    return {
        "key": reason.get("key"),
        "idx": 0,
        "source": "why_queue",
        "queue": "claude",
        "status": status,
        "game_id": (reason.get("requests") or [{}])[0].get("game_id") if reason.get("requests") else None,
        "move_number": (reason.get("requests") or [{}])[0].get("move_number") if reason.get("requests") else None,
        "fen": reason.get("fen_before"),
        "played_san": reason.get("played_san"),
        "best_san": reason.get("better_san"),
        "side": reason.get("side"),
        "tier": reason.get("stored_class"),
        "cp_loss": reason.get("gap_cp"),
        "grade_fresh": reason.get("class"),
        "reason": reason.get("reason") or reason.get("no_lesson_why"),
        "judge_overall": "confirmed" if passed else "refuted",
        "bucket": bucket,
        "probes": probes,
        "pv_after_played": list(packet.get("pv_after_played") or []),
        "pv_after_best": list(packet.get("pv_after_best") or []),
        "model": reason.get("model"),
        "created_at": reason.get("created_at"),
    }


async def apply_ruling(db, key: str, verdict: str, *, ruled_by: str, note: str = "") -> Optional[str]:
    """A human's agree / disagree on a why_reasons row. Returns the new status, or
    None when the key is not a why-queue row (the old seeded set is ruled as before)."""
    row = await db[REASONS_COLLECTION].find_one({"key": key}, {"_id": 0, "status": 1})
    if not row:
        return None
    if verdict == "agree":
        new_status = PUBLISHED if row.get("status") in (HELD_FOR_REVIEW, HELD) else row.get("status")
    elif verdict == "disagree":
        new_status = REJECTED
    else:
        return row.get("status")
    update: Dict[str, Any] = {"status": new_status, "ruled_by": ruled_by, "ruled_at": _now(),
                              "ruling": verdict, "ruling_note": (note or "")[:2000]}
    if new_status == PUBLISHED:
        update["published_at"] = _now()
    await db[REASONS_COLLECTION].update_one({"key": key}, {"$set": update})
    return new_status


__all__ = [
    "AUTO_PUBLISH", "DONE", "FAILED", "HELD", "HELD_FOR_REVIEW", "NO_LESSON", "PUBLISHED", "QUEUED",
    "QUEUE_COLLECTION", "REASONS_COLLECTION", "REJECTED", "RUNNING", "STUDY_WHEN", "apply_ruling",
    "enqueue", "ensure_indexes", "lookup", "on_nothing_found", "position_key", "review_row",
    "studied_response", "study_state",
]
