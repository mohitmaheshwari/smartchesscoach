"""
Reviewer Routes
===============

Lightweight read-only endpoints for content-quality reviewers (e.g. Parth).
Bypasses the heavy `/lab-coach-pick` flow because reviewers need to scroll
through hundreds-to-thousands of games quickly without per-game Stockfish
re-analysis or coaching enrichment.

Endpoints:
- GET /reviewer/games — paginated, filterable list of games for review

Access control: every endpoint checks `user.is_reviewer` and 403s otherwise.
The is_reviewer flag is set per-user in the users collection and exposed
via routes.auth.User. See scripts/grant_reviewer_to_parth.py.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from routes.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reviewer"])

db = None


def set_db(database):
    global db
    db = database


def _require_reviewer(user: User) -> None:
    if not getattr(user, "is_reviewer", False):
        raise HTTPException(status_code=403, detail="Reviewer access required")


@router.get("/reviewer/games")
async def list_review_games(
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None, description="Filter to one game owner"),
    opening: Optional[str] = Query(None, description="Substring match against game.opening"),
    has_bugs: Optional[str] = Query(None, regex="^(yes|no)$", description="yes = only flagged; no = only unflagged"),
    analyzed_only: bool = Query(True, description="Skip games without analysis"),
    platform: Optional[str] = Query(None, description="chess.com / lichess / coach"),
    regenerated_only: bool = Query(
        True,
        description="Only show games whose decryption has been regenerated with "
                    "the latest V5 code (decryption_v5_regen_at is set). Default "
                    "True so reviewers don't waste cycles flagging stale captions."
    ),
):
    """
    Paginated list of games for review. Reviewer-only. Designed to be
    fast — a single Mongo find on `games` plus two batched lookups for
    analysis stats and flag counts. No coaching enrichment.

    Response shape:
    {
        "games": [
            {
                "game_id": "...",
                "owner_user_id": "...",
                "owner_name": "...",        # display label for the owner
                "opening": "...",
                "result": "win|loss|draw",
                "user_color": "white|black",
                "opponent": "...",
                "platform": "chess.com|lichess|coach",
                "imported_at": "...",
                "blunders": 3,
                "mistakes": 5,
                "accuracy": 78.4,
                "flag_count": 0,            # # of move_feedback entries
                "is_analyzed": true,
            },
            ...
        ],
        "total": 312,                       # total matching pre-pagination
        "page": 1,
        "page_size": 50,
        "has_more": true
    }
    """
    _require_reviewer(user)

    flt = {}
    if analyzed_only:
        flt["is_analyzed"] = True
    if user_id:
        flt["user_id"] = user_id
    if platform:
        flt["platform"] = platform
    if opening:
        flt["opening"] = {"$regex": re.escape(opening), "$options": "i"}

    # When regenerated_only is true, restrict the game set to those whose
    # decryption has been re-generated with the current V5 code. This is
    # the default for reviewers — flagging stale captions wastes cycles.
    # The set is collected from game_analyses where decryption_v5_regen_at
    # exists, then intersected with the games filter.
    regen_at_by_game: dict = {}
    if regenerated_only:
        regen_ids = []
        async for a in db.game_analyses.find(
            {"decryption_v5_regen_at": {"$exists": True}},
            {"_id": 0, "game_id": 1, "decryption_v5_regen_at": 1},
        ):
            gid = a.get("game_id")
            if gid:
                regen_ids.append(gid)
                regen_at_by_game[gid] = a.get("decryption_v5_regen_at")
        if not regen_ids:
            # No games have been regenerated yet — return empty fast.
            return {
                "games": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "regenerated_only": True,
                "regenerated_total": 0,
            }
        flt["game_id"] = {"$in": regen_ids}

    skip = (page - 1) * page_size

    total = await db.games.count_documents(flt)

    cursor = db.games.find(flt, {
        "_id": 0,
        "game_id": 1, "user_id": 1, "opening": 1, "opening_name": 1, "eco": 1,
        "result": 1, "user_color": 1, "user_result": 1,
        "white_player": 1, "black_player": 1,
        "platform": 1, "imported_at": 1, "is_analyzed": 1,
    }).sort("imported_at", -1).skip(skip).limit(page_size)
    games = await cursor.to_list(page_size)

    if not games:
        return {
            "games": [],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }

    game_ids = [g["game_id"] for g in games if g.get("game_id")]
    owner_ids = list({g["user_id"] for g in games if g.get("user_id")})

    # Owner display names — single batched lookup.
    users_by_id = {}
    async for u in db.users.find(
        {"user_id": {"$in": owner_ids}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1}
    ):
        users_by_id[u["user_id"]] = u

    # Analysis summary stats — single batched lookup.
    stats_by_game = {}
    async for a in db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.blunders": 1,
            "stockfish_analysis.mistakes": 1,
            "stockfish_analysis.accuracy": 1,
        }
    ):
        sf = a.get("stockfish_analysis") or {}
        stats_by_game[a["game_id"]] = {
            "blunders": sf.get("blunders", 0),
            "mistakes": sf.get("mistakes", 0),
            "accuracy": sf.get("accuracy", 0),
        }

    # Flag counts from move_feedback collection. context.game_id is the
    # standard field where bug submissions record which game they're
    # against (matches the regen-diff lookup pattern).
    flag_count_by_game = {}
    pipeline = [
        {"$match": {"context.game_id": {"$in": game_ids}}},
        {"$group": {"_id": "$context.game_id", "count": {"$sum": 1}}},
    ]
    async for doc in db.move_feedback.aggregate(pipeline):
        if doc.get("_id"):
            flag_count_by_game[doc["_id"]] = doc.get("count", 0)

    # Apply has_bugs filter post-fetch (Mongo can't easily join across
    # collections). If the filter excludes a lot, the user's pagination
    # numbers will look odd (page may have <page_size results) — that's
    # acceptable for this scale.
    if has_bugs == "yes":
        games = [g for g in games if flag_count_by_game.get(g.get("game_id"), 0) > 0]
    elif has_bugs == "no":
        games = [g for g in games if flag_count_by_game.get(g.get("game_id"), 0) == 0]

    enriched = []
    for g in games:
        owner = users_by_id.get(g.get("user_id", ""), {})
        stats = stats_by_game.get(g.get("game_id", ""), {})
        user_color = (g.get("user_color") or "").lower()
        opp_color = "black" if user_color == "white" else "white"
        opponent = (
            g.get("black_player") if opp_color == "black"
            else g.get("white_player")
        ) or "Unknown"

        # Owner display: name if set, else email-local-part, else user_id.
        owner_name = owner.get("name")
        if not owner_name:
            email = owner.get("email") or ""
            owner_name = email.split("@", 1)[0] if "@" in email else (owner.get("user_id") or g.get("user_id", ""))

        regen_at_val = regen_at_by_game.get(g.get("game_id"))
        if hasattr(regen_at_val, "isoformat"):
            regen_at_val = regen_at_val.isoformat()
        enriched.append({
            "game_id": g.get("game_id"),
            "owner_user_id": g.get("user_id"),
            "owner_name": owner_name,
            "opening": g.get("opening_name") or g.get("opening", ""),
            "eco": g.get("eco", ""),
            "result": (g.get("user_result") or g.get("result") or "").lower(),
            "user_color": user_color,
            "opponent": opponent,
            "platform": g.get("platform", ""),
            "imported_at": g.get("imported_at"),
            "is_analyzed": g.get("is_analyzed", False),
            "blunders": stats.get("blunders", 0),
            "mistakes": stats.get("mistakes", 0),
            "accuracy": round(stats.get("accuracy", 0) or 0, 1),
            "flag_count": flag_count_by_game.get(g.get("game_id"), 0),
            "regenerated_at": regen_at_val,
        })

    return {
        "games": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (skip + len(enriched)) < total,
        "regenerated_only": regenerated_only,
        "regenerated_total": len(regen_at_by_game) if regenerated_only else None,
    }


@router.get("/reviewer/owners")
async def list_review_owners(
    user: User = Depends(get_current_user),
    regenerated_only: bool = Query(
        True,
        description="Only count games whose decryption has been regenerated."
    ),
):
    """List of distinct game owners for the user-id filter dropdown.

    Game counts reflect how many of each owner's games are AVAILABLE
    for review (regenerated, by default). This way the dropdown shows
    a useful number — picking a user with 0 doesn't surprise Parth
    with an empty page.
    """
    _require_reviewer(user)

    owner_ids = await db.games.distinct("user_id")
    if not owner_ids:
        return {"owners": []}

    # Build the set of regenerated game_ids once if filtering.
    regen_game_ids: Optional[set] = None
    if regenerated_only:
        regen_game_ids = set()
        async for a in db.game_analyses.find(
            {"decryption_v5_regen_at": {"$exists": True}},
            {"_id": 0, "game_id": 1},
        ):
            gid = a.get("game_id")
            if gid:
                regen_game_ids.add(gid)

    owners = []
    async for u in db.users.find(
        {"user_id": {"$in": owner_ids}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1}
    ):
        if regen_game_ids is not None:
            # Count this owner's games that intersect the regen set.
            game_count = 0
            async for g in db.games.find(
                {"user_id": u["user_id"], "is_analyzed": True},
                {"_id": 0, "game_id": 1},
            ):
                if g.get("game_id") in regen_game_ids:
                    game_count += 1
        else:
            game_count = await db.games.count_documents(
                {"user_id": u["user_id"], "is_analyzed": True}
            )
        if game_count == 0:
            continue
        email = u.get("email") or ""
        display = u.get("name") or (email.split("@", 1)[0] if "@" in email else u.get("user_id"))
        owners.append({
            "user_id": u["user_id"],
            "name": display,
            "email": email,
            "game_count": game_count,
        })

    owners.sort(key=lambda x: -x["game_count"])
    return {"owners": owners}
