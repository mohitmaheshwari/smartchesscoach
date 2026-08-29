"""Verify coaching_context.v1 against the isolated synthetic fixture DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.seed_coaching_context_validation import (
    VALIDATION_DB_NAME,
    ensure_validation_database_name,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-name", default=VALIDATION_DB_NAME)
    parser.add_argument("--mongo-url", default=os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return parser


async def _verify(mongo_url: str, database_name: str) -> dict:
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.focus_bridge import (
        build_coaching_context,
        coaching_context_visible_in_mode,
        coaching_session_payload_for_mode,
    )

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    await client.admin.command("ping")
    db = client[database_name]

    checks = {}

    no_focus = await build_coaching_context(
        db, "validation_ctx_no_focus", surface="home"
    )
    assert no_focus["state"] == "no_focus"
    assert no_focus["primary_focus"] is None
    checks["no_focus_fails_closed"] = True

    primary_home = await build_coaching_context(
        db, "validation_ctx_primary", surface="home"
    )
    assert primary_home["state"] == "primary_only"
    assert primary_home["primary_focus"]["instruction_id"] == "piece-safety-check-v1"
    checks["home_primary_instruction"] = True

    primary_review = await build_coaching_context(
        db,
        "validation_ctx_primary",
        surface="review",
        game_id="validation-game-primary",
    )
    review_surface = primary_review["surface_context"]
    assert review_surface["focus_evidence_state"] == "observed"
    assert len(review_surface["primary_matches"]) == 1
    assert review_surface["primary_matches"][0]["move_number"] == 1
    checks["review_exact_observation_match"] = True

    no_opportunity = await build_coaching_context(
        db,
        "validation_ctx_no_opportunity",
        surface="review",
        game_id="validation-game-no-opportunity",
    )
    assert no_opportunity["surface_context"]["focus_evidence_state"] == "not_observed"
    assert no_opportunity["surface_context"]["primary_matches"] == []
    checks["review_no_opportunity_does_not_claim_recovery"] = True

    unauthorized = await build_coaching_context(
        db, "validation_ctx_unauthorized", surface="home"
    )
    assert unauthorized["state"] == "no_focus"
    assert unauthorized["primary_focus"] is None
    checks["shadow_detector_fails_closed"] = True

    missing_instruction = await build_coaching_context(
        db, "validation_ctx_missing_instruction", surface="home"
    )
    assert missing_instruction["state"] == "evidence_pending"
    assert missing_instruction["primary_focus"]["instruction_id"] is None
    checks["missing_instruction_is_not_invented"] = True

    training = await build_coaching_context(
        db, "validation_ctx_primary", surface="training"
    )
    assignment = training["surface_context"]["assignment"]
    assert assignment["instruction_id"] == "piece-safety-check-v1"
    assert assignment["href"] == "/training/pattern/piece_safety"
    checks["training_uses_same_instruction"] = True

    coach_play = await build_coaching_context(
        db, "validation_ctx_primary", surface="coach_play"
    )
    cross_surface_contexts = (
        primary_home,
        primary_review,
        training,
        coach_play,
    )
    assert {
        context["primary_focus"]["focus_id"]
        for context in cross_surface_contexts
    } == {"fixture-focus:validation_ctx_primary"}
    assert {
        context["primary_focus"]["instruction_id"]
        for context in cross_surface_contexts
    } == {"piece-safety-check-v1"}
    checks["cross_surface_focus_identity_stable"] = True

    assert coaching_context_visible_in_mode(coach_play, "coach") is coach_play
    assert coaching_context_visible_in_mode(coach_play, "play") is None
    sanitized = coaching_session_payload_for_mode(
        {
            "session_id": "synthetic-session",
            "coaching_context": coach_play,
            "mission_scoreboard": {"focus": "piece_safety"},
            "session_focus": {"focus": "piece_safety"},
            "session_goal": {"goal": "piece_safety"},
            "session_greeting": {"message": "synthetic"},
        },
        "play",
    )
    assert sanitized["session_id"] == "synthetic-session"
    for field in (
        "coaching_context",
        "mission_scoreboard",
        "session_focus",
        "session_goal",
        "session_greeting",
    ):
        assert sanitized[field] is None
    checks["coach_visible_play_sanitized"] = True

    client.close()
    return {
        "database": database_name,
        "schema_version": "coaching_context.v1",
        "passed": len(checks),
        "checks": checks,
    }


def main() -> int:
    args = _parser().parse_args()
    database_name = ensure_validation_database_name(args.db_name)
    # These values are validation-only and are set before importing the bridge.
    os.environ["COACHING_CONTEXT_V1_ENABLED"] = "true"
    os.environ["COACHING_CONTEXT_V1_ROLES"] = "admin,super_admin"
    report = asyncio.run(_verify(args.mongo_url, database_name))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
