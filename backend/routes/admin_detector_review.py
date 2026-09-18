"""Read what a detector would actually say, and rule on it.

Every detector here lands in shadow by default — `_UNKNOWN` grades an
unregistered id SHADOW with "No reviewed promotion packet; unknown IDs fail
closed". That default is right for a live product and wrong for this one.
ChessGuru is not launched. A wrong claim costs one review cycle; silence costs
the review cycle itself, and 47 of 48 registered detectors have been mute
long enough that nobody remembers what they would say.

So this serves the claims. One at a time, rendered exactly as a player would
read them, with the position and the detector's own evidence beside them. A
verdict is true / false / unsure, and it is Mohit's, not a model's.

Two things it deliberately is NOT:

- not a promotion. Verdicts accumulate into the precision figure a promotion
  packet needs, but `detector_quality` remains the only authority on what may
  reach a player, and nothing here writes to it.
- not a sample of the detector's own choosing. Fires are drawn in corpus
  order and skipped once ruled, so the easy ones cannot float to the top.

Follows the geometry-gaps queue (`/admin/geometry-gaps/next` + POST +
`/results`) rather than inventing a fourth review shape.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin
from routes.auth import User

router = APIRouter(tags=["Admin"])
db = None

VERDICTS = {"true", "false", "unsure"}
COLLECTION = "detector_claim_rulings"

# How many analyses to walk before giving up on finding an unjudged fire. The
# detectors here are sparse by design -- allowed_mate fires on well under 1%
# of moves -- so a small scan window returns nothing and looks broken.
SCAN_LIMIT = 900


def set_db(database):
    global db
    db = database


async def _fires_for(detector: str, skip_fens: set, limit: int) -> List[Dict[str, Any]]:
    """Walk real games and render what this detector would say."""
    from services.allowed_mate_detector import detect_allowed_mate, render_claim

    if detector != "allowed_mate":
        raise HTTPException(status_code=400, detail=f"unknown detector: {detector}")

    found: List[Dict[str, Any]] = []
    scanned = 0
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1,
         "stockfish_analysis.move_evaluations": 1},
    )
    async for analysis in cursor:
        scanned += 1
        if scanned > SCAN_LIMIT or len(found) >= limit:
            break
        game = await db.games.find_one(
            {"game_id": analysis.get("game_id")}, {"_id": 0, "user_color": 1})
        colour = (game or {}).get("user_color") or "white"
        for move in (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []:
            if move.get("is_opponent_move"):
                continue
            evidence = detect_allowed_mate(move, colour)
            if not evidence:
                continue
            key = f"{analysis.get('game_id')}:{evidence.get('move_number')}"
            if key in skip_fens:
                continue
            found.append({
                "claim_key": key,
                "detector": detector,
                "game_id": analysis.get("game_id"),
                "claim": render_claim(evidence),
                "evidence": evidence,
            })
            if len(found) >= limit:
                break
    return found


@router.get("/admin/detector-review/next")
async def next_claim(
    detector: str = Query(default="allowed_mate"),
    user: User = Depends(require_admin),
):
    """One unjudged claim, or 404 when the queue is clear."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    found = await _fires_for(detector, ruled, limit=1)
    if not found:
        raise HTTPException(
            status_code=404,
            detail="No unjudged claims found in the scan window")
    return found[0]


@router.get("/admin/detector-review/batch")
async def batch_claims(
    detector: str = Query(default="allowed_mate"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_admin),
):
    """Several at once — reading fifty claims in ten minutes is the point."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    return {"detector": detector, "claims": await _fires_for(detector, ruled, limit)}


@router.post("/admin/detector-review")
async def rule_claim(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Record a verdict. It does not promote anything; see the module docstring."""
    claim_key = str(payload.get("claim_key") or "").strip()
    detector = str(payload.get("detector") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not claim_key or not detector:
        raise HTTPException(status_code=400, detail="claim_key and detector required")
    if verdict not in VERDICTS:
        raise HTTPException(
            status_code=400, detail=f"verdict must be one of {sorted(VERDICTS)}")

    await db[COLLECTION].update_one(
        {"claim_key": claim_key, "detector": detector},
        {"$set": {
            "verdict": verdict,
            "note": str(payload.get("note") or "")[:500],
            "claim": str(payload.get("claim") or "")[:500],
            "ruled_by": user.email,
            "ruled_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"recorded": True, "claim_key": claim_key, "verdict": verdict}


@router.get("/admin/detector-review/results")
async def review_results(user: User = Depends(require_admin)):
    """Tallies, plus every claim ruled false — those are the bug reports."""
    rows = await db[COLLECTION].find({}, {"_id": 0}).to_list(length=None)
    by_detector: Dict[str, Counter] = {}
    for row in rows:
        by_detector.setdefault(row.get("detector"), Counter())[
            row.get("verdict")] += 1

    summary = {}
    for detector, counts in by_detector.items():
        judged = counts["true"] + counts["false"]
        summary[detector] = {
            "true": counts["true"],
            "false": counts["false"],
            "unsure": counts["unsure"],
            # The number a promotion packet needs. Unsure is excluded from the
            # denominator on purpose: it is a reviewer abstention, not evidence
            # either way.
            "precision": round(100 * counts["true"] / judged, 1) if judged else None,
            "judged": judged,
            # docs/detector_quality_threshold_lock_2026_08_27.md
            "caption_bar": {"fires": 50, "precision": 95},
            "plan_bar": {"fires": 200, "precision": 95, "recall": 60},
        }
    return {
        "summary": summary,
        "wrong_claims": [
            {k: r.get(k) for k in ("detector", "claim", "note", "claim_key")}
            for r in rows if r.get("verdict") == "false"
        ],
        "total_ruled": len(rows),
    }
