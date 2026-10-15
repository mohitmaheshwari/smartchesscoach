"""Reply-check session routes.

A sitting in which the player plays his intended move on a board, names the
reply he expects, and rates the position -- all recorded BEFORE he is shown
anything. Spec: docs/reply_check_page_scope.md

The packet is frozen on disk (Stockfish 17.1, Threads=1, hold set swept over
depths 14/16/18/20, replies at depth 14). Nothing here calls an engine, scores
the player, or decides anything about him; it serves prepared positions and
writes down what he answered.

The answer key is deliberately a SEPARATE endpoint from the positions, and it
refuses to serve a position until that position's answers are recorded. If the
key travelled with the positions it would sit in the browser while he was still
deciding.

Endpoints (prefixed /api by server.py):
    GET  /coach/reply-check/packet
    POST /coach/reply-check/response
    GET  /coach/reply-check/evidence/{position_id}
    GET  /coach/reply-check/responses
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routes.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach/reply-check", tags=["Reply check"])

db = None

PACKET_DIR = Path(__file__).resolve().parent.parent / "data" / "reply_check"

# Fields that would give the answer away if they reached the browser early.
ANSWER_KEY_FIELDS = (
    "accept_moves",
    "accept_moves_strict",
    "n_moves_that_hold",
    "hold_count_by_depth",
    "holds_union_across_depths",
    "holds_at_every_depth",
    "hold_set_is_stable",
    "one_move_only_wording_permitted",
    "root_eval_by_move",
    "engine_best",
    "engine_best_cp",
    "reply_evidence_by_candidate_move",
    "engine_reply_to_the_move_he_played_in_the_game",
    "what_he_played",
    "his_move_cost_cp",
    "his_move_was_capture",
    "his_move_gave_check",
    "eval_before_user_pov",
    "eval_after_his_move_user_pov",
    "regained_later_user_pov",
    "game_result_for_him",
    "kind",
    "share_of_moves_that_blunder",
    "loose_pieces_before_his_move",
)

# Kept, because the player can see all of this on the board anyway.
SAFE_FIELDS = (
    "game_id",
    "move_number",
    "platform",
    "date",
    "time_control",
    "to_move",
    "fen",
    "preceding_moves",
    "side_to_move_in_check",
    "checking_squares",
    "all_legal_moves",
    "n_legal",
)


def set_db(database):
    global db
    db = database


def _packet_path(user_id: str) -> Path:
    """One packet per player. The id is used as a filename, so it must not be
    able to walk out of the directory."""
    safe = "".join(ch for ch in str(user_id).replace("user_", "")
                   if ch.isalnum() or ch in "-_")
    return PACKET_DIR / f"{safe}.json"


def _load_packet(user_id: str) -> Dict[str, Any]:
    path = _packet_path(user_id)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No reply-check packet has been prepared for this account.")
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.exception("reply-check packet unreadable: %s", path)
        raise HTTPException(status_code=500,
                            detail="The packet could not be read.") from exc


def position_id(item: Dict[str, Any]) -> str:
    return f"{item.get('game_id')}:{item.get('move_number')}"


def _ordered(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Interleave the two groups so neither clusters, and so the order is the
    same every time the page is opened."""
    missed = [i for i in items if i.get("kind") == "reply_missed"]
    handled = [i for i in items if i.get("kind") == "reply_handled"]
    pattern = [0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1]
    out, mi, hi = [], 0, 0
    for p in pattern:
        if p == 0 and mi < len(missed):
            out.append(missed[mi]); mi += 1
        elif hi < len(handled):
            out.append(handled[hi]); hi += 1
        elif mi < len(missed):
            out.append(missed[mi]); mi += 1
    out.extend(missed[mi:])
    out.extend(handled[hi:])
    return out


class ResponseIn(BaseModel):
    position_id: str
    recognised: Optional[str] = None
    intended_move: Optional[str] = None
    expected_reply: Optional[str] = None
    assessment_now: Optional[str] = None
    assessment_after_predicted_reply: Optional[str] = None
    revised_move: Optional[str] = None
    reason_choice: Optional[str] = None
    reflection_choice: Optional[str] = None
    notes: Optional[str] = None


@router.get("/packet")
async def get_packet(current_user: User = Depends(get_current_user)):
    """The positions, in order, with the answer key removed."""
    pk = _load_packet(current_user.user_id)
    items = []
    for item in _ordered(pk.get("items", [])):
        safe = {k: item.get(k) for k in SAFE_FIELDS if k in item}
        safe["position_id"] = position_id(item)
        items.append(safe)
    return {
        "schema": pk.get("schema"),
        "engine": pk.get("engine"),
        "built": pk.get("built"),
        "count": len(items),
        "items": items,
        "prompt": "It is your move. Take as long as you like.",
    }


@router.post("/response")
async def record_response(payload: ResponseIn,
                          current_user: User = Depends(get_current_user)):
    """Record one position. Append-only: a second submission for the same
    position is stored as another attempt rather than overwriting the first,
    so nothing he said is ever lost."""
    pk = _load_packet(current_user.user_id)
    item = next((i for i in pk.get("items", [])
                 if position_id(i) == payload.position_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown position.")

    answers = payload.model_dump()
    missing = [k for k in ("recognised", "intended_move", "expected_reply",
                           "assessment_now", "assessment_after_predicted_reply")
               if not answers.get(k)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"These answers are still missing: {', '.join(missing)}")

    derived = grade(item, answers)
    doc = {
        "user_id": current_user.user_id,
        "position_id": payload.position_id,
        "game_id": item.get("game_id"),
        "move_number": item.get("move_number"),
        "kind": item.get("kind"),
        "answers": {k: v for k, v in answers.items() if k != "position_id"},
        "derived": derived,
        "recorded_at": datetime.now(timezone.utc),
    }
    if db is not None:
        await db.reply_check_responses.insert_one(dict(doc))
    doc.pop("_id", None)
    doc["recorded_at"] = doc["recorded_at"].isoformat()
    return {"recorded": True, "derived": derived}


def grade(item: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    """Flags, not verdicts.

    `move_holds` says the move is in the frozen accept set. A plausible move
    that is not is `pending_verification`, never wrong -- the hold set moves
    with search depth, and on 11 of these 14 positions it is not identical at
    every depth swept.
    """
    move = (answers.get("revised_move") or answers.get("intended_move") or "").strip()
    first = (answers.get("intended_move") or "").strip()
    reply = (answers.get("expected_reply") or "").strip()
    accept = item.get("accept_moves") or []
    strict = item.get("accept_moves_strict") or []
    branches = item.get("reply_evidence_by_candidate_move") or {}
    branch = branches.get(first)
    not_sure = reply.lower() == "not sure"
    stored = [r.get("reply") for r in (branch or {}).get("engine_top_replies", [])]
    punishing = (branch or {}).get("punishing_replies", []) if branch else []
    reply_known = bool(branch) and (reply in stored or reply in punishing)
    return {
        "move_graded": first,
        "final_move": move,
        "move_holds": (first in accept) if branch else None,
        "move_holds_at_every_depth": (first in strict) if branch else None,
        "move_branch_prepared": branch is not None,
        "reply_as_damaging_as_best": (
            None if (not_sure or not reply_known)
            else reply in ((branch or {}).get("accept_expected_replies") or [])),
        "reply_names_the_capture": (
            None if (not_sure or not reply_known) else reply in punishing),
        "reply_not_sure": not_sure,
        "revised": bool(answers.get("revised_move")),
        "revision_holds": (answers.get("revised_move") in accept
                           if answers.get("revised_move") else None),
        "pending_verification": (branch is None) or (not not_sure and not reply_known),
    }


@router.get("/evidence/{pos_id:path}")
async def get_evidence(pos_id: str,
                       current_user: User = Depends(get_current_user)):
    """The answer key for one position. Refused until that position has been
    recorded, so it cannot reach the browser while he is still deciding."""
    if db is not None:
        seen = await db.reply_check_responses.find_one(
            {"user_id": current_user.user_id, "position_id": pos_id})
        if not seen:
            raise HTTPException(
                status_code=409,
                detail="Record the answers for this position first.")
    pk = _load_packet(current_user.user_id)
    item = next((i for i in pk.get("items", [])
                 if position_id(i) == pos_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown position.")
    return {k: item.get(k) for k in ANSWER_KEY_FIELDS if k in item}


@router.get("/responses")
async def list_responses(current_user: User = Depends(get_current_user)):
    """What has been recorded so far, oldest first, so a reload resumes."""
    if db is None:
        return {"count": 0, "responses": []}
    rows = await db.reply_check_responses.find(
        {"user_id": current_user.user_id}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(500)
    for r in rows:
        if isinstance(r.get("recorded_at"), datetime):
            r["recorded_at"] = r["recorded_at"].isoformat()
    return {"count": len(rows), "responses": rows}
