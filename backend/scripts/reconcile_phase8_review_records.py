"""Classify and explicitly reconcile Phase 8 Game Review records.

Dry-run is the default and inspects stored data only. It never runs Stockfish
or changes a detector. Apply is limited to explicit users/games and reuses the
canonical V5 generator over already-stored engine analysis; current rows and
invalid/unowned rows are never regenerated.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.destination_safety_detector import (  # noqa: E402
    FACT_VERSION,
    QUALITY_ID,
)
from services.game_decryption_v5_service import (  # noqa: E402
    V5_COACHING_VERSION,
)
from services.move_observation_deriver import (  # noqa: E402
    SCHEMA_VERSION as OBSERVATION_SCHEMA_VERSION,
    current_deriver_identity,
)
from services.verified_puzzle_admission import ADMISSION_VERSION  # noqa: E402


REPORT_VERSION = "phase8_review_reconciliation.v1"
PLAN_SCHEMA_VERSION = "personalized_game_review.shadow_plan.v1"
GAME_STATES = (
    "already_current",
    "partially_reconciled",
    "never_had_required_records",
    "stale_version",
    "no_authorized_evidence",
    "invalid_or_unowned",
)


def _at_least(value: Any, minimum: int) -> bool:
    try:
        return int(value or 0) >= int(minimum)
    except (TypeError, ValueError):
        return False


def _expected_user_move_records(analysis: Dict[str, Any]) -> int:
    evaluations = (
        (analysis.get("stockfish_analysis") or {}).get("move_evaluations")
        or []
    )
    if not isinstance(evaluations, list):
        return 0
    return sum(
        1
        for move in evaluations
        if isinstance(move, dict) and move.get("is_opponent_move") is not True
    )


def _current_observation(row: Dict[str, Any]) -> bool:
    fact = row.get("destination_safety_exact") or {}
    return bool(
        _at_least(row.get("schema_version"), OBSERVATION_SCHEMA_VERSION)
        and fact.get("version") == FACT_VERSION
        and fact.get("quality_id") == QUALITY_ID
        and fact.get("derivation_status") in {"ok", "unavailable"}
    )


def _current_plan(plan: Any, caption_version: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    try:
        same_caption_version = int(plan.get("source_v5_version") or 0) == int(
            caption_version or 0
        )
    except (TypeError, ValueError):
        return False
    identity = plan.get("deriver_identity")
    return bool(
        plan.get("schema_version") == PLAN_SCHEMA_VERSION
        and _at_least(caption_version, V5_COACHING_VERSION)
        and same_caption_version
        and _at_least(
            plan.get("observation_schema_version"),
            OBSERVATION_SCHEMA_VERSION,
        )
        and identity == current_deriver_identity()
        and (
            plan.get("plan") is None
            or isinstance(plan.get("plan"), dict)
        )
    )


def _authorized_plan_events(plan: Any) -> int:
    if not isinstance(plan, dict) or not isinstance(plan.get("plan"), dict):
        return 0
    chapters = (plan.get("plan") or {}).get("chapters") or []
    return sum(
        1
        for chapter in chapters
        if isinstance(chapter, dict)
        and isinstance(chapter.get("event"), dict)
        and ((chapter.get("event") or {}).get("display") or {}).get(
            "authorized"
        ) is True
    )


def classify_game_reconciliation(
    game: Optional[Dict[str, Any]],
    analysis: Optional[Dict[str, Any]],
    observations: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return one exclusive game state plus separately counted move records."""
    rows = [row for row in observations if isinstance(row, dict)]
    game_id = str((game or {}).get("game_id") or "")
    user_id = str((game or {}).get("user_id") or "")
    analysis_user = str((analysis or {}).get("user_id") or "")
    invalid = bool(
        not game
        or not analysis
        or not game_id
        or not user_id
        or (analysis_user and analysis_user != user_id)
        or (game or {}).get("is_analyzed") is not True
        or _expected_user_move_records(analysis or {}) <= 0
    )
    if invalid:
        return {
            "state": "invalid_or_unowned",
            "write_required": False,
            "move_records": {
                "expected": 0,
                "caption_current": 0,
                "caption_stale": 0,
                "proof_current": 0,
                "proof_stale": len(rows),
                "proof_missing": 0,
                "authorized_events": 0,
            },
        }

    expected = _expected_user_move_records(analysis)
    v5_data = analysis.get("decryption_v5_data")
    v5_rows = v5_data if isinstance(v5_data, list) else []
    caption_version_current = _at_least(
        analysis.get("decryption_v5_version"),
        V5_COACHING_VERSION,
    )
    caption_shape_current = bool(
        v5_rows
        and all(
            isinstance(row, dict)
            and row.get("move_number") is not None
            and "caption" in row
            for row in v5_rows
        )
    )
    captions_current = caption_version_current and caption_shape_current
    proof_current = sum(1 for row in rows if _current_observation(row))
    proof_stale = len(rows) - proof_current
    proof_missing = max(0, expected - len(rows))
    proofs_complete = (
        proof_current >= expected
        and proof_stale == 0
        and proof_missing == 0
    )
    plan = analysis.get("game_teaching_plan")
    plan_current = _current_plan(
        plan,
        analysis.get("decryption_v5_version"),
    )
    authorized = _authorized_plan_events(plan) if plan_current else 0

    any_required = bool(v5_rows or plan or rows)
    any_current = bool(captions_current or plan_current or proof_current)
    any_stale = bool(
        (v5_rows and not captions_current)
        or (plan and not plan_current)
        or proof_stale
    )
    all_current = captions_current and plan_current and proofs_complete
    if all_current and authorized == 0:
        state = "no_authorized_evidence"
    elif all_current:
        state = "already_current"
    elif not any_required:
        state = "never_had_required_records"
    elif any_stale and not any_current:
        state = "stale_version"
    else:
        state = "partially_reconciled"
    return {
        "state": state,
        "write_required": state in {
            "partially_reconciled",
            "never_had_required_records",
            "stale_version",
        },
        "move_records": {
            "expected": expected,
            "caption_current": len(v5_rows) if captions_current else 0,
            "caption_stale": len(v5_rows) if v5_rows and not captions_current else 0,
            "proof_current": proof_current,
            "proof_stale": proof_stale,
            "proof_missing": proof_missing,
            "authorized_events": authorized,
        },
    }


async def _known_caption_concept_coverage(db) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for collection in (
        "community_puzzles",
        "community_training_positions",
    ):
        counts = Counter()
        cursor = db[collection].find(
            {},
            {
                "_id": 0,
                "approved": 1,
                "verified_admission.admission_version": 1,
                "verified_admission.status": 1,
                "verified_admission.caption_concept_id": 1,
            },
        )
        async for row in cursor:
            admission = row.get("verified_admission") or {}
            if admission.get("admission_version") != ADMISSION_VERSION:
                counts["stale_or_missing_admission"] += 1
            elif admission.get("caption_concept_id"):
                counts["current_caption_concept_id"] += 1
            else:
                counts["current_without_caption_concept_id"] += 1
            if row.get("approved") is False:
                counts["preserved_rejection"] += 1
        result[collection] = dict(sorted(counts.items()))
    return result


async def _regenerate_one(db, game: Dict[str, Any], analysis: Dict[str, Any]):
    from services.game_decryption_v5_service import generate_game_decryption_v5

    pgn = str(game.get("pgn") or "")
    engine = analysis.get("stockfish_analysis") or {}
    moves = engine.get("move_evaluations") or []
    opponent_moves = engine.get("opponent_move_evaluations") or []
    if not pgn or not moves:
        return "invalid_inputs"
    plan: Dict[str, object] = {}
    generated = await generate_game_decryption_v5(
        pgn,
        game.get("user_color") or game.get("user_plays_as") or "white",
        moves,
        str(game.get("user_id") or ""),
        db,
        game_id=str(game.get("game_id")),
        opponent_move_evaluations=opponent_moves,
        game_teaching_plan_output=plan,
        persist_learning_side_effects=False,
        allow_llm_polish=False,
    )
    if not generated:
        return "no_output"
    if not plan:
        return "no_plan_output"
    now = datetime.now(timezone.utc)
    await db.game_analyses.update_one(
        {"game_id": game["game_id"]},
        {
            "$set": {
                "decryption_v5_data": generated,
                "decryption_v5_generated_at": now.isoformat(),
                "decryption_v5_generating": False,
                "decryption_v5_version": V5_COACHING_VERSION,
                "game_teaching_plan": plan,
            }
        },
    )
    return "updated"


async def build_reconciliation_report(
    db,
    *,
    user_id: Optional[str] = None,
    game_ids: Iterable[str] = (),
    apply: bool = False,
) -> Dict[str, Any]:
    ids = tuple(sorted({str(value) for value in game_ids if value}))
    if apply and not (user_id or ids):
        raise ValueError("apply requires --user-id or --game-id")
    query: Dict[str, Any] = {"is_analyzed": True}
    if user_id:
        query["user_id"] = user_id
    if ids:
        query["game_id"] = {"$in": list(ids)}
    games = await db.games.find(
        query,
        {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "user_color": 1,
            "user_plays_as": 1,
            "is_analyzed": 1,
            "pgn": 1,
        },
    ).to_list(length=None)
    states = Counter()
    moves = Counter()
    apply_results = Counter()
    for game in games:
        analysis = await db.game_analyses.find_one(
            {"game_id": game.get("game_id")},
            {"_id": 0},
        )
        observations = await db.move_observations.find(
            {"game_id": game.get("game_id")},
            {"_id": 0},
        ).to_list(length=None)
        classification = classify_game_reconciliation(
            game,
            analysis,
            observations,
        )
        states[classification["state"]] += 1
        moves.update(classification["move_records"])
        if apply and classification["write_required"]:
            apply_results[await _regenerate_one(db, game, analysis or {})] += 1
        else:
            apply_results["not_selected"] += 1
    for state in GAME_STATES:
        states[state] += 0
    return {
        "schema_version": REPORT_VERSION,
        "mode": "apply" if apply else "dry_run",
        "scope": {
            "all_analyzed_games": not bool(user_id or ids),
            "user_scoped": bool(user_id),
            "game_count_requested": len(ids),
        },
        "games_inspected": len(games),
        "game_states": {
            state: int(states[state])
            for state in GAME_STATES
        },
        "move_records": dict(sorted(moves.items())),
        "writes_required": sum(
            states[state]
            for state in (
                "partially_reconciled",
                "never_had_required_records",
                "stale_version",
            )
        ),
        "apply_results": dict(sorted(apply_results.items())),
        "known_caption_concept_reconciliation": (
            await _known_caption_concept_coverage(db)
        ),
        "contains_identifiers": False,
    }


async def _main(args) -> int:
    if args.apply and args.confirm != "phase8-review-reconciliation":
        raise SystemExit(
            "--apply requires --confirm phase8-review-reconciliation"
        )
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    try:
        report = await build_reconciliation_report(
            client[db_name],
            user_id=args.user_id,
            game_ids=args.game_id,
            apply=args.apply,
        )
    finally:
        client.close()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report_json:
        Path(args.report_json).write_text(rendered + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--game-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--report-json")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
