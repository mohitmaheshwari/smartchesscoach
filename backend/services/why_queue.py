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
import re
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

# The live reasons that are studied: every silence the player can meet. The
# button renders only on a card that already called the move a fault, so "no
# gap" and "the engine's own choice" are not answers to that player, they are
# the card contradicting itself. Mohit 2026-11-05 on Ke7 in 5e68fc88, caption
# "That was a mistake", box "No single tactic to point at here. The engine
# simply prefers Bd6." and no study line: "i don't see that on the UI". Until
# then those two were left out as answers. An engine error is an outage, not a
# position, and a move with no stored position cannot be studied.
STUDY_WHEN = frozenset({"no_mechanism", "shared_consequence_only", "no_explainable_candidate",
                        "no_gap", "engine_choice"})

# Review-first is the default Mohit chose. Flip to "1" only after the first
# batch has been graded (scope: 30 positions).
AUTO_PUBLISH = os.environ.get("WHY_QUEUE_AUTO_PUBLISH", "0") == "1"

STUDYING_LINE = "The coach will study this one and leave the answer here."
# Says nothing about the position. The first study of a real click (5e68fc88
# move 13, 2026-11-05) was a dead-lost position, and the old line's "the
# position is simply a little worse" was false there.
NO_LESSON_LINE = "The coach studied this one: there is no single lesson in this move."


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


def study_fits_viewer(reason: Optional[Dict[str, Any]], *, opponent: bool) -> bool:
    """Is the viewer on the side this study was written for?

    A study is keyed by position, but its "you" and "their" belong to the
    first asker (`side`: "user" = the asker made the move, "opponent" = the
    asker faced it). The same position seen from the other side would read
    backwards, so it is used only when the viewer's side matches (2026-11-12).
    """
    side = str((reason or {}).get("side") or "user")
    return (side == "opponent") == bool(opponent)


# The card's caption came from a published study: the frontend labels it
# "Studied by the coach" and hides the Why button (its answer would repeat it).
COACH_STUDY_SOURCE = "coach_study"


def card_caption_from_study(existing: Optional[str], study_text: str, played_san: str,
                            *, mover_is_user: bool) -> str:
    """The card's caption with its explanation replaced by the study.

    The grade line the card already wrote stays ("Rf7 was a mistake." /
    "Your opponent played e5. That was a mistake."); everything after it is
    the study. No grade line found: the study alone (it names the move).
    """
    text = (existing or "").strip()
    san = re.escape(str(played_san or "").strip())
    lead_re = (rf"^{san} (?:was|is) [^.]*\." if mover_is_user
               else rf"^Your opponent played {san}\. That [^.]*\.")
    m = re.match(lead_re, text)
    study_text = (study_text or "").strip()
    return f"{m.group(0)} {study_text}" if m else study_text


async def published_studies_by_key(db) -> Dict[str, Dict[str, Any]]:
    """Every published study with text, by position key. One small read per review render."""
    if db is None:
        return {}
    try:
        rows = await db[REASONS_COLLECTION].find(
            {"status": PUBLISHED},
            {"_id": 0, "key": 1, "side": 1, "reason": 1, "claims": 1, "better_san": 1},
        ).to_list(length=5000)
    except Exception:                                   # noqa: BLE001
        logger.exception("published why studies could not be read")
        return {}
    return {r["key"]: r for r in rows if r.get("key") and str(r.get("reason") or "").strip()}


def card_arrows_from_study(reason: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The study's arrows in the card's caption_arrows shape (the Why box draws the same ones)."""
    return [{**a, "color": "blue", "teach": True} for a in _arrows(reason.get("claims") or [])]


async def mark_asking_games_stale(db, key: str) -> int:
    """Re-render the reviews of every game that asked about this position.

    Clearing the stored version sends the next open of each review through
    the existing regeneration path (routes/coach.py), which is where a newly
    published study reaches the caption, or a withdrawn one leaves it.
    Returns the number of reviews marked.
    """
    try:
        queue = await db[QUEUE_COLLECTION].find_one({"key": key}, {"_id": 0, "requests.game_id": 1})
        ids = sorted({r.get("game_id") for r in (queue or {}).get("requests") or [] if r.get("game_id")})
        if not ids:
            return 0
        res = await db.game_analyses.update_many({"game_id": {"$in": ids}},
                                                 {"$set": {"decryption_v5_version": 0}})
        return int(res.modified_count)
    except Exception:                                   # noqa: BLE001
        logger.exception("could not mark reviews stale for %s", key)
        return 0


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


async def known_answer(db, *, fen_before: str, played_san: str, game_id: str, move_number: int,
                       opponent: bool, user_id: str) -> Optional[Dict[str, Any]]:
    """The answer for a position the queue already holds, WITHOUT the live engine.

    A position is only in the queue because the live engine found nothing for
    it, so running that engine again on the next click repeats the same search
    to the same end. On 2026-11-10/11 that search took 93.5 s on 6.e5 of
    2d86e1f9; nginx gives /api 60 s, so all four of Mohit's clicks came back 504
    and the card said "We can't show a clear reason" while a finished study
    sat in the review tab. The route asks here first.

    Returns None when the queue has never seen the position (the live engine
    runs as before) or when the store cannot be read (never break the button).
    The click is still recorded as an asker.
    """
    try:
        key = position_key(fen_before, played_san)
        queue = await db[QUEUE_COLLECTION].find_one(
            {"key": key},
            {"_id": 0, "status": 1, "live_reason": 1, "differential": 1, "stored_best": 1})
        reason = await db[REASONS_COLLECTION].find_one({"key": key}, {"_id": 0})
        if queue is None and reason is None:
            return None
        if queue is not None:
            await db[QUEUE_COLLECTION].update_one(
                {"key": key},
                {"$set": {"last_requested_at": _now()},
                 "$addToSet": {"requests": {
                     "game_id": game_id, "move_number": int(move_number),
                     "side": "opponent" if opponent else "user", "user_id": user_id,
                     "requested_at": _now()}}})
        if reason and reason.get("status") == PUBLISHED:
            if not study_fits_viewer(reason, opponent=opponent):
                return None   # written for the other side: the live engine answers as before
            return studied_response(reason, move_number=move_number, played_san=played_san,
                                    fen_before=fen_before)
        queue = queue or {}
        out: Dict[str, Any] = {
            "found": False,
            "reason": queue.get("live_reason") or "no_mechanism",
            "better_move": ((queue.get("differential") or {}).get("better_move")
                            or queue.get("stored_best") or (reason or {}).get("better_san")),
            "move_number": move_number, "played_san": played_san, "fen_before": fen_before,
            "from_queue": True,
        }
        state = study_state(reason, queue.get("status"))
        if state:
            out["study"] = state
        return out
    except Exception:                                   # noqa: BLE001
        logger.exception("why queue lookup failed for %s move %s", game_id, move_number)
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
            if not study_fits_viewer(reason, opponent=opponent):
                return out    # written for the other side: say nothing rather than "studying" forever
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


# --- the list page: /admin/why-queue (docs/why_queue_admin_page_scope.md) ----

STATUS_WORDS = {
    QUEUED: "To be processed",
    RUNNING: "Being processed",
    HELD_FOR_REVIEW: "Waiting for your review",
    HELD: "Failed the check",
    PUBLISHED: "Published",
    REJECTED: "Rejected",
    NO_LESSON: "No single lesson",
    DONE: "Processed, no study saved",
    FAILED: "Failed",
}


def _uci_squares(fen: Optional[str], san: Optional[str]) -> Optional[Dict[str, str]]:
    """From/to squares of a SAN in this position, for a board arrow."""
    if not fen or not san:
        return None
    try:
        import chess
        mv = chess.Board(fen).parse_san(san)
        return {"from": chess.square_name(mv.from_square), "to": chess.square_name(mv.to_square)}
    except Exception:                                   # noqa: BLE001
        return None


def admin_list_row(queue: Dict[str, Any], reason: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """One queued position as the list page draws it.

    The study's status wins over the queue's: a `done` queue row with a study
    reads as what the study says. No user ids leave the server; the page needs
    the games, not who asked.
    """
    reason = reason or {}
    fen = queue.get("fen_before") or reason.get("fen_before")
    played = queue.get("played_san") or reason.get("played_san")
    better = (reason.get("better_san")
              or (queue.get("differential") or {}).get("better_move")
              or queue.get("stored_best"))
    status = reason.get("status") or queue.get("status") or QUEUED
    requests = sorted(queue.get("requests") or reason.get("requests") or [],
                      key=lambda r: str(r.get("requested_at") or ""))
    games: list = []
    for r in requests:
        g = {"game_id": r.get("game_id"), "move_number": r.get("move_number"), "side": r.get("side")}
        if g not in games:
            games.append(g)
    gate = reason.get("gate") or {}
    return {
        "key": queue.get("key") or reason.get("key"),
        "fen_before": fen,
        "side_to_move": "white" if " w " in f" {fen or ''} " else "black",
        "played_san": played,
        "played_squares": _uci_squares(fen, played),
        "better_san": better,
        "better_squares": _uci_squares(fen, better),
        "stored_class": queue.get("stored_class") or reason.get("stored_class"),
        "side": (requests[-1].get("side") if requests else reason.get("side")),
        "status": status,
        "status_words": STATUS_WORDS.get(status, status),
        "processed": bool(reason),
        "games": games,
        "times_asked": len(requests),
        "first_asked_at": requests[0].get("requested_at") if requests else queue.get("created_at"),
        "last_asked_at": queue.get("last_requested_at") or (requests[-1].get("requested_at") if requests else None),
        "claude_text": reason.get("reason"),
        "no_lesson_why": reason.get("no_lesson_why"),
        "gate_passed": gate.get("passed") if reason else None,
        "gate_failures": list(gate.get("failures") or []),
        "cost_usd": reason.get("cost_usd"),
        "model": reason.get("model"),
        "studied_at": reason.get("studied_at") or reason.get("created_at"),
        "published_at": reason.get("published_at"),
    }


async def admin_list(db, limit: int = 500) -> List[Dict[str, Any]]:
    """Every queued position with its study, newest ask first."""
    queue_rows = await db[QUEUE_COLLECTION].find({}, {"_id": 0}).sort(
        "last_requested_at", -1).limit(limit).to_list(length=limit)
    keys = [q.get("key") for q in queue_rows if q.get("key")]
    reasons = {r["key"]: r for r in await db[REASONS_COLLECTION].find(
        {"key": {"$in": keys}}, {"_id": 0, "packet": 0}).to_list(length=None) if r.get("key")}
    return [admin_list_row(q, reasons.get(q.get("key"))) for q in queue_rows]


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
    read = reason.get("readability") or {}
    if read:
        hard = ", ".join(read.get("hard_words") or []) or "none"
        probes.append({
            "label": "plain English",
            "kind": "readability",
            "verdict": (f"longest sentence {read.get('longest_sentence_words', '?')} words · "
                        f"{read.get('words', '?')} words in all · hard words: {hard}"),
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
    if new_status == PUBLISHED or row.get("status") == PUBLISHED:
        # The study reaches (or leaves) the card caption on the next render.
        await mark_asking_games_stale(db, key)
    return new_status


__all__ = [
    "AUTO_PUBLISH", "DONE", "FAILED", "HELD", "HELD_FOR_REVIEW", "NO_LESSON", "PUBLISHED", "QUEUED",
    "QUEUE_COLLECTION", "REASONS_COLLECTION", "REJECTED", "RUNNING", "STUDY_WHEN", "apply_ruling",
    "enqueue", "ensure_indexes", "lookup", "on_nothing_found", "position_key", "review_row",
    "studied_response", "study_state",
]
