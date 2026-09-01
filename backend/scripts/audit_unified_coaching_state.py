"""Read-only audit of the canonical coaching projections for one user.

Runs inside the deployed backend container. It prints only bounded coaching
state, provenance, and counts; it never writes to MongoDB and never prints
credentials, PGNs, FENs, names, or private coaching history.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
import sys
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


sys.path.insert(0, "/app/backend")


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _focus_view(document: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "type",
        "status",
        "topic_key",
        "cycle_version",
        "focus_kind",
        "detector_quality_id",
        "detector_quality_grade",
        "proof_eligibility",
        "instruction_id",
        "instruction_version",
        "started_at",
        "locked_until",
        "baseline_metric",
        "current_metric",
        "resolution",
        "next_action",
        "evidence_summary",
    )
    return {field: document.get(field) for field in fields}


async def audit(email: str) -> dict[str, Any]:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    try:
        user = await db.users.find_one(
            {"email": email.lower()},
            {
                "_id": 0,
                "user_id": 1,
                "email": 1,
                "role": 1,
                "rating_source": 1,
                "assessed_rating": 1,
                "detected_rating": 1,
                "lichess_rating": 1,
            },
        )
        if not user:
            raise SystemExit("user not found")
        user_id = user["user_id"]

        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {
                "_id": 0,
                "current_rating": 1,
                "rating": 1,
                "estimated_rating": 1,
                "games_analyzed_count": 1,
            },
        ) or {}
        strength = await db.player_strength_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "overall_rating": 1, "overall_score": 1, "generated_at": 1},
        ) or {}
        latest_game = await db.games.find_one(
            {"user_id": user_id, "is_analyzed": True},
            {
                "_id": 0,
                "game_id": 1,
                "date_played": 1,
                "user_rating": 1,
                "user_rating_at_time": 1,
                "user_color": 1,
                "white_rating": 1,
                "black_rating": 1,
            },
            sort=[("date_played", -1)],
        ) or {}
        focuses = await db.user_active_focus.find(
            {"user_id": user_id, "status": "active"}, {"_id": 0}
        ).to_list(length=None)

        from services.focus_bridge import build_coaching_context
        from services.personal_curriculum import build_player_curriculum
        from services.destination_safety_detector import FACT_VERSION
        from services.rating_resolver import resolve_coaching_rating

        rating_projection = await resolve_coaching_rating(
            db,
            user_id,
            user=user,
            profile=profile,
        )
        exact_query = {
            "user_id": user_id,
            "schema_version": {"$gte": 18},
            "destination_safety_exact.version": FACT_VERSION,
            "destination_safety_exact.derivation_status": "ok",
            "destination_safety_exact.eligible": True,
        }
        exact_decisions = await db.move_observations.count_documents(exact_query)
        exact_misses = await db.move_observations.count_documents({
            **exact_query,
            "destination_safety_exact.outcome": "miss",
        })
        exact_fires = await db.move_observations.count_documents({
            **exact_query,
            "destination_safety_exact.fires": True,
        })

        contexts: dict[str, Any] = {}
        for surface in ("home", "review", "training", "coach_play"):
            contexts[surface] = await build_coaching_context(
                db,
                user_id,
                surface=surface,
                game_id=latest_game.get("game_id") if surface == "review" else None,
            )

        curriculum = await build_player_curriculum(db, user_id)
        return {
            "user": user,
            "rating_projection": {
                **rating_projection,
                "profile": profile,
                "strength": strength,
            },
            "destination_safety_exact": {
                "fact_version": FACT_VERSION,
                "decisions": exact_decisions,
                "misses": exact_misses,
                "handled": max(0, exact_decisions - exact_misses),
                "diagnostic_fires": exact_fires,
            },
            "latest_analyzed_game": {
                "game_id": latest_game.get("game_id"),
                "date_played": latest_game.get("date_played"),
            },
            "active_focus_count": len(focuses),
            "active_focuses": [_focus_view(focus) for focus in focuses],
            "coaching_contexts": contexts,
            "personal_curriculum": curriculum,
        }
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    result = asyncio.run(audit(args.email))
    print(json.dumps(result, indent=2, default=_json_default, sort_keys=True))


if __name__ == "__main__":
    main()
