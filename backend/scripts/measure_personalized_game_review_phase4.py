"""Aggregate-only comparison of visible PIC and Phase 4 shadow learning.

The script reads the existing ``learning_sessions`` and PIC game-evidence
fields, invokes the two canonical reducers, and prints aggregate JSON. It does
not run chess analysis, call an LLM, write MongoDB, or emit identifiers.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
import os

from pymongo import MongoClient

from services.concept_mastery_service import (
    PIC_SKILL_ID,
    reduce_pic_mastery,
    reduce_review_learning_shadow,
)


def _current_pic_game_event(document: dict) -> dict:
    evidence = document.get("pic_evidence") or {}
    summary = evidence.get("summary") or {}
    return {
        "event_type": "external_game_evidence",
        "occurred_at": document.get("date_played"),
        "stage": evidence.get("evidence_mode") or "ordinary_play",
        "checkpoint_candidate": 8,
        "result": (
            "miss" if int(summary.get("misses") or 0) > 0 else "handled"
        ),
        "evidence_eligible": bool(evidence.get("mastery_eligible")),
        "demotion_eligible": bool(evidence.get("demotion_eligible")),
        "proof_rule_locked": bool(evidence.get("proof_rule_locked")),
        "repeated_verified_misses": bool(
            evidence.get("repeated_verified_misses")
        ),
    }


def build_aggregate_comparison(db) -> dict:
    session_events = defaultdict(list)
    session_count = 0
    for session in db.learning_sessions.find(
        {"skill_id": PIC_SKILL_ID},
        {"_id": 0, "user_id": 1, "events": 1},
    ):
        user_id = str(session.get("user_id") or "")
        if not user_id:
            continue
        session_count += 1
        session_events[user_id].extend(session.get("events") or [])

    game_events = defaultdict(list)
    for game in db.games.find(
        {"pic_evidence.proof_detector_id": "piece_safety.d_live.v1"},
        {"_id": 0, "user_id": 1, "pic_evidence": 1, "date_played": 1},
    ):
        user_id = str(game.get("user_id") or "")
        if user_id:
            game_events[user_id].append(_current_pic_game_event(game))

    users = sorted(set(session_events) | set(game_events))
    current_states = Counter()
    shadow_states = Counter()
    comparison_pairs = Counter()
    shadow_attempts = Counter()
    shadow_accepted = 0
    shadow_rejected = 0
    users_with_shadow = 0

    for user_id in users:
        current = reduce_pic_mastery(
            session_events[user_id] + game_events[user_id]
        )
        shadow = reduce_review_learning_shadow(session_events[user_id])
        current_states[current["state"]] += 1
        shadow_states[shadow["state"]] += 1
        evidence = shadow["evidence"]
        shadow_accepted += int(evidence["accepted_events"])
        shadow_rejected += int(evidence["rejected_events"])
        shadow_attempts.update(evidence["by_attempt"])
        if evidence["accepted_events"]:
            users_with_shadow += 1
            comparison_pairs[
                f'{current["state"]} -> {shadow["state"]}'
            ] += 1

    return {
        "schema_version": "personalized_game_review.phase4_shadow_compare.v1",
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "engine_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "privacy": {
            "contains_user_ids": False,
            "contains_game_ids": False,
            "contains_fens": False,
            "contains_moves": False,
            "aggregate_only": True,
        },
        "rollout": {
            "mode": "shadow",
            "visible_mastery_changed": False,
            "reliable_state_enabled": False,
            "handled_game_application_credit_enabled": False,
        },
        "counts": {
            "users_with_pic_or_shadow_evidence": len(users),
            "learning_sessions": session_count,
            "users_with_accepted_shadow_evidence": users_with_shadow,
            "accepted_shadow_events": shadow_accepted,
            "rejected_shadow_events": shadow_rejected,
        },
        "current_projection_states": dict(sorted(current_states.items())),
        "shadow_projection_states": dict(sorted(shadow_states.items())),
        "shadow_attempts": dict(sorted(shadow_attempts.items())),
        "evidence_cohort_projection_pairs": dict(
            sorted(comparison_pairs.items())
        ),
        "interpretation": [
            (
                "Projection labels are reported side by side because the "
                "legacy PIC and LessonResult state vocabularies differ."
            ),
            (
                "Only users with at least one accepted shadow event enter "
                "the projection-pair cohort."
            ),
            (
                "A verified miss is application evidence but cannot earn a "
                "positive learner state."
            ),
            (
                "No clean or handled game earns application credit until "
                "the comparable-opportunity proof rule is data-locked."
            ),
        ],
    }


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(json.dumps(build_aggregate_comparison(db), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
