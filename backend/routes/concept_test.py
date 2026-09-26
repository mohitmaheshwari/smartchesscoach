"""
Concept Test Routes
===================

The proof step of the coaching loop. A review teaches a concept; this is
where the user proves he understood it, and only passing moves him on.

docs/teaching_loop_scope.md

Endpoints:
- GET  /coach/concept-test/{concept_id}          - build a 5-position test
- POST /coach/concept-test/{test_id}/submit      - grade it, move the state
- POST /coach/concept-test/{concept_id}/decline  - "Not now"
- GET  /coach/concept-test/{concept_id}/offer    - should we offer it?
- GET  /coach/concept-test/for-game/{game_id}    - which concept did this
                                                   game teach?
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach/concept-test", tags=["Concept Test"])

db = None


def set_db(database):
    global db
    db = database


from routes.auth import User, get_current_user
from services.concept_test_service import (
    build_concept_test,
    grade_concept_test,
    record_test_declined,
    should_offer_test,
    pick_concept_for_game,
)


async def _user_rating(user_id: str, fallback: int = 1200) -> int:
    """Best-known rating, used to select calibrated Lichess positions."""
    try:
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "lichess_stats.rating": 1, "chesscom_stats.rating": 1},
        )
        if profile:
            lichess = (profile.get("lichess_stats") or {}).get("rating") or 0
            chesscom = (profile.get("chesscom_stats") or {}).get("rating") or 0
            best = max(int(lichess or 0), int(chesscom or 0))
            if best:
                return best
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("rating lookup failed for %s: %s", user_id, exc)
    return fallback


class SubmitPayload(BaseModel):
    answers: List[str]


@router.get("/for-game/{game_id}")
async def concept_for_game(game_id: str, user: User = Depends(get_current_user)):
    """Which concept should the review at the end of THIS game test?

    Declared above /{concept_id} for readability; the paths do not actually
    collide because this one has two segments.

    Returns {"concept_id": null} rather than a 404 when the game taught
    nothing testable. That is the ordinary case, not an error -- measured
    2026-09-26, about half of recently analysed games carry a concept -- and
    a 404 would put a red line in the browser console on every other review.
    """
    concept = await pick_concept_for_game(db, user.user_id, game_id)
    if not concept:
        return {"concept_id": None, "reason": "no testable concept in this game"}
    return concept


@router.get("/{concept_id}")
async def get_concept_test(concept_id: str, user: User = Depends(get_current_user)):
    """Build a 5-position test for this concept.

    Lichess first where the concept maps to a theme (calibrated at the
    user's rating), falling back to positions from other players' games for
    the positional concepts Lichess has no theme for.
    """
    rating = await _user_rating(user.user_id)
    test = await build_concept_test(db, user.user_id, concept_id, rating=rating)
    if not test.get("available"):
        raise HTTPException(
            status_code=404,
            detail=f"No test positions available for '{concept_id}'",
        )
    return test


@router.post("/{test_id}/submit")
async def submit_concept_test(
    test_id: str, payload: SubmitPayload, user: User = Depends(get_current_user),
):
    """Grade the test and move the concept's state."""
    result = await grade_concept_test(db, user.user_id, test_id, payload.answers)
    if result.get("error") == "test_not_found":
        raise HTTPException(status_code=404, detail="Test not found")
    if result.get("error") == "already_graded":
        raise HTTPException(status_code=409, detail="This test was already submitted")
    return result


@router.post("/{concept_id}/decline")
async def decline_concept_test(concept_id: str, user: User = Depends(get_current_user)):
    """'Not now'. Recorded, never treated as a failure."""
    await record_test_declined(db, user.user_id, concept_id)
    return {"status": "ok", "concept_id": concept_id}


@router.get("/{concept_id}/offer")
async def offer_concept_test(concept_id: str, user: User = Depends(get_current_user)):
    """Whether the review should show the 'Test me on this' card."""
    return {
        "concept_id": concept_id,
        "should_offer": await should_offer_test(db, user.user_id, concept_id),
    }
