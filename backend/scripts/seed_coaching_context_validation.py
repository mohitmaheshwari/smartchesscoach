"""Seed the isolated coaching-context V1 reviewer database.

This script is deliberately incapable of targeting the application database.
It creates synthetic users and synthetic games only; it never reads from or
copies records out of another database.

Examples (from the backend container)::

    python scripts/seed_coaching_context_validation.py --dry-run
    python scripts/seed_coaching_context_validation.py
    python scripts/seed_coaching_context_validation.py \
        --reset --confirm-reset chessguru_validation
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Iterable


VALIDATION_DB_NAME = "chessguru_validation"
FIXTURE_SET = "coaching_context.v1.2026-08-28"
BOUNDARY_MARKER_ID = "database_boundary"
MUTABLE_COLLECTIONS = (
    "users",
    "user_active_focus",
    "games",
    "game_analyses",
    "move_observations",
    "coach_memory",
    "player_profiles",
    "community_training_positions",
)

_FORBIDDEN_IDENTITY_KEYS = {
    "email",
    "password",
    "password_hash",
    "oauth_id",
    "oauth_token",
    "access_token",
    "refresh_token",
    "stripe_customer_id",
    "payment_customer_id",
    "chess_com_username",
    "lichess_username",
}

_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_SYNTHETIC_PGN = (
    '[Event "ChessGuru isolated validation"]\n'
    '[Site "local-validation"]\n'
    '[Date "2026.08.28"]\n'
    '[Round "-"]\n'
    '[White "Synthetic learner"]\n'
    '[Black "Synthetic opponent"]\n'
    '[Result "1/2-1/2"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Bc5 5. O-O O-O 1/2-1/2"
)


def ensure_validation_database_name(database_name: str) -> str:
    """Return the allowlisted name or refuse the operation."""
    if database_name != VALIDATION_DB_NAME:
        raise ValueError(
            "Refusing database operation: target must be exactly "
            f"{VALIDATION_DB_NAME!r}, got {database_name!r}."
        )
    return database_name


def fixture_filter() -> Dict[str, str]:
    """The only deletion selector this script is allowed to use."""
    return {"validation_fixture_set": FIXTURE_SET}


def _tag(document: Dict[str, Any]) -> Dict[str, Any]:
    return {**document, "validation_fixture_set": FIXTURE_SET}


def _user(user_id: str, scenario: str, now: datetime) -> Dict[str, Any]:
    return _tag({
        "_id": f"fixture-user:{user_id}",
        "user_id": user_id,
        "name": f"Synthetic reviewer: {scenario.replace('_', ' ')}",
        "role": "admin",
        "rating": 1200,
        "account_kind": "synthetic_validation",
        "validation_scenario": scenario,
        "created_at": now,
        "updated_at": now,
    })


def _game(user_id: str, suffix: str, now: datetime) -> Dict[str, Any]:
    game_id = f"validation-game-{suffix}"
    return _tag({
        "_id": f"fixture-game:{game_id}",
        "game_id": game_id,
        "user_id": user_id,
        "platform": "synthetic_validation",
        "pgn": _SYNTHETIC_PGN,
        "user_color": "white",
        "result": "1/2-1/2",
        "opponent_name": "Synthetic opponent",
        "opponent_rating": 1200,
        "time_control": "600+0",
        "is_analyzed": True,
        "played_at": now - timedelta(days=1),
        "created_at": now - timedelta(days=1),
    })


def _analysis(
    user_id: str,
    suffix: str,
    now: datetime,
    *,
    include_piece_safety_miss: bool,
) -> Dict[str, Any]:
    game_id = f"validation-game-{suffix}"
    if include_piece_safety_miss:
        move = {
            "move_number": 1,
            "move": "f3",
            "move_san": "f3",
            "move_uci": "f2f3",
            "best_move": "e4",
            "fen_before": _START_FEN,
            "cp_loss": 180,
            "cognitive_gap": "piece_safety",
            "is_opponent_move": False,
            "threat": "The move leaves the king and centre harder to protect.",
        }
    else:
        move = {
            "move_number": 1,
            "move": "e4",
            "move_san": "e4",
            "move_uci": "e2e4",
            "best_move": "e4",
            "fen_before": _START_FEN,
            "cp_loss": 0,
            "cognitive_gap": None,
            "is_opponent_move": False,
        }
    return _tag({
        "_id": f"fixture-analysis:{game_id}",
        "game_id": game_id,
        "user_id": user_id,
        "analyzed_at": now,
        "analysis_version": "synthetic-validation-v1",
        "stockfish_analysis": {
            "accuracy": 71.0 if include_piece_safety_miss else 94.0,
            "move_evaluations": [move],
        },
    })


def _focus(
    user_id: str,
    scenario: str,
    now: datetime,
    *,
    detector_quality_id: str = "gap:piece_safety:simple_hang",
    include_instruction: bool = True,
) -> Dict[str, Any]:
    instruction_id = "piece-safety-check-v1" if include_instruction else None
    instruction_text = (
        "Before you move, check whether every piece you leave behind is safe."
        if include_instruction
        else None
    )
    return _tag({
        "_id": f"fixture-focus:{user_id}",
        "user_id": user_id,
        "status": "active",
        "type": "weakness",
        "focus_kind": "cognitive_gap",
        "topic_key": "piece_safety",
        "coaching_label": "Keep every piece safe",
        "coaching_narrative": (
            "Your current job is to check every piece before you commit to a move."
        ),
        "detector_quality_id": detector_quality_id,
        "diagnosis_detector_id": detector_quality_id,
        "proof_eligibility": "verified",
        "instruction_id": instruction_id,
        "instruction_text": instruction_text,
        "instruction_version": 1 if include_instruction else None,
        "subtype_histogram": {
            "simple_hang": {"count": 2, "dominant_severity": "blunder"}
        },
        "baseline_metric": {
            "value": 2,
            "name": "verified piece-safety misses",
            "occurrence_count": 2,
            "n_games_at_baseline": 3,
        },
        "runners_up": [],
        "rating_band": "beginner_high",
        "started_at": now - timedelta(days=2),
        "locked_until": now + timedelta(days=5),
        "validation_scenario": scenario,
        "updated_at": now,
    })


def build_fixture_documents(now: datetime | None = None) -> Dict[str, list[Dict[str, Any]]]:
    """Build deterministic, synthetic-only documents for reviewer scenarios."""
    now = now or datetime.now(timezone.utc)
    users = [
        _user("validation_ctx_no_focus", "no_focus", now),
        _user("validation_ctx_primary", "primary_observed", now),
        _user("validation_ctx_no_opportunity", "primary_not_observed", now),
        _user("validation_ctx_unauthorized", "unauthorized_focus", now),
        _user("validation_ctx_missing_instruction", "missing_instruction", now),
    ]

    games = [
        _game("validation_ctx_no_focus", "no-focus", now),
        _game("validation_ctx_primary", "primary", now),
        _game("validation_ctx_no_opportunity", "no-opportunity", now),
        _game("validation_ctx_unauthorized", "unauthorized", now),
        _game("validation_ctx_missing_instruction", "missing-instruction", now),
    ]
    analyses = [
        _analysis("validation_ctx_no_focus", "no-focus", now, include_piece_safety_miss=False),
        _analysis("validation_ctx_primary", "primary", now, include_piece_safety_miss=True),
        _analysis(
            "validation_ctx_no_opportunity",
            "no-opportunity",
            now,
            include_piece_safety_miss=False,
        ),
        _analysis(
            "validation_ctx_unauthorized",
            "unauthorized",
            now,
            include_piece_safety_miss=True,
        ),
        _analysis(
            "validation_ctx_missing_instruction",
            "missing-instruction",
            now,
            include_piece_safety_miss=True,
        ),
    ]
    focuses = [
        _focus("validation_ctx_primary", "primary_observed", now),
        _focus("validation_ctx_no_opportunity", "primary_not_observed", now),
        _focus(
            "validation_ctx_unauthorized",
            "unauthorized_focus",
            now,
            detector_quality_id="gap:king_safety:king_in_center",
        ),
        _focus(
            "validation_ctx_missing_instruction",
            "missing_instruction",
            now,
            include_instruction=False,
        ),
    ]
    observations = [
        _tag({
            "_id": "fixture-observation:validation-game-primary:1",
            "user_id": "validation_ctx_primary",
            "game_id": "validation-game-primary",
            "move_number": 1,
            "move_san": "f3",
            "fen_before": _START_FEN,
            "missed_pattern": "piece_safety",
            "subtype": "simple_hang",
            "severity": "blunder",
            "schema_version": 16,
            "derived_at": now,
        })
    ]

    memories = []
    profiles = []
    legacy_memory_focus = {
        "validation_ctx_primary": "hanging_piece",
        "validation_ctx_no_opportunity": "hanging_piece",
        "validation_ctx_missing_instruction": "hanging_piece",
    }
    for user in users:
        user_id = user["user_id"]
        memories.append(_tag({
            "_id": f"fixture-memory:{user_id}",
            "user_id": user_id,
            "learning": (
                {"current_focus": legacy_memory_focus[user_id]}
                if user_id in legacy_memory_focus
                else {}
            ),
            "updated_at": now,
        }))
        profiles.append(_tag({
            "_id": f"fixture-profile:{user_id}",
            "user_id": user_id,
            "rating": 1200,
            "games_analyzed": 1,
            "average_accuracy": 78.0,
            "updated_at": now,
        }))

    community_positions = [
        _tag({
            "_id": "fixture-community-position:piece-safety-1",
            "position_id": "validation-community-piece-safety-1",
            "source_user_id": "validation_synthetic_peer",
            "source_user_rating": 1220,
            "pattern_type": "piece_safety",
            "fen": _START_FEN,
            "best_move_uci": "e2e4",
            "best_move_san": "e4",
            "user_move_uci": "f2f3",
            "user_move_san": "f3",
            "move_number": 1,
            "cp_loss": 180,
            "solve_rate": 0.72,
            "opening_name": "Synthetic starting position",
            "created_at": now,
        })
    ]

    documents = {
        "users": users,
        "user_active_focus": focuses,
        "games": games,
        "game_analyses": analyses,
        "move_observations": observations,
        "coach_memory": memories,
        "player_profiles": profiles,
        "community_training_positions": community_positions,
    }
    validate_fixture_documents(documents)
    return documents


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def validate_fixture_documents(documents: Dict[str, list[Dict[str, Any]]]) -> None:
    """Fail before I/O if fixtures drift outside the synthetic contract."""
    if set(documents) != set(MUTABLE_COLLECTIONS):
        raise ValueError("Fixture collections do not match the guarded allowlist.")
    seen_ids: set[tuple[str, str]] = set()
    for collection, rows in documents.items():
        for row in rows:
            if row.get("validation_fixture_set") != FIXTURE_SET:
                raise ValueError(f"Untagged validation document in {collection}.")
            if "_id" not in row:
                raise ValueError(f"Validation document in {collection} has no stable _id.")
            identity = (collection, str(row["_id"]))
            if identity in seen_ids:
                raise ValueError(f"Duplicate fixture id {identity!r}.")
            seen_ids.add(identity)
            forbidden = set(_walk_keys(row)) & _FORBIDDEN_IDENTITY_KEYS
            if forbidden:
                raise ValueError(
                    f"Forbidden identity/payment fields in {collection}: {sorted(forbidden)}"
                )


def _assert_boundary_marker(db) -> None:
    marker = db.validation_meta.find_one({"_id": BOUNDARY_MARKER_ID})
    if not marker:
        raise RuntimeError(
            "Validation boundary marker is missing; initialize it explicitly first."
        )
    if marker.get("database_name") not in (None, VALIDATION_DB_NAME):
        raise RuntimeError("Validation boundary marker names a different database.")
    if marker.get("contains_real_player_state") is not False:
        raise RuntimeError("Validation DB is not certified synthetic-only.")


def _initialize_boundary_marker(db, now: datetime) -> None:
    existing = db.validation_meta.find_one({"_id": BOUNDARY_MARKER_ID})
    if existing and existing.get("contains_real_player_state") is not False:
        raise RuntimeError("Refusing to overwrite a non-synthetic boundary marker.")
    db.validation_meta.update_one(
        {"_id": BOUNDARY_MARKER_ID},
        {"$set": {
            "database_name": VALIDATION_DB_NAME,
            "purpose": "Synthetic coaching-context reviewer validation only",
            "contains_real_player_state": False,
            "external_side_effects_allowed": False,
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


def _write_fixtures(db, documents: Dict[str, list[Dict[str, Any]]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for collection in MUTABLE_COLLECTIONS:
        target = db[collection]
        target.delete_many(fixture_filter())
        rows = documents[collection]
        if rows:
            target.insert_many(rows, ordered=True)
        counts[collection] = len(rows)
    return counts


def _reset_fixtures(db) -> Dict[str, int]:
    return {
        collection: db[collection].delete_many(fixture_filter()).deleted_count
        for collection in MUTABLE_COLLECTIONS
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-name",
        default=VALIDATION_DB_NAME,
        help="Must be exactly chessguru_validation.",
    )
    parser.add_argument("--mongo-url", default=os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    parser.add_argument("--initialize-boundary", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--confirm-reset",
        help="Required for --reset and must equal chessguru_validation.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    database_name = ensure_validation_database_name(args.db_name)
    now = datetime.now(timezone.utc)
    documents = build_fixture_documents(now)
    if args.dry_run:
        print({"database": database_name, "fixture_set": FIXTURE_SET,
               "counts": {key: len(value) for key, value in documents.items()}})
        return 0

    # Import only in the I/O path so safety/shape tests need no Mongo driver.
    from pymongo import MongoClient

    client = MongoClient(args.mongo_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[database_name]
    if args.initialize_boundary:
        _initialize_boundary_marker(db, now)
    _assert_boundary_marker(db)

    if args.reset:
        if args.confirm_reset != VALIDATION_DB_NAME:
            raise ValueError(
                "--reset requires --confirm-reset chessguru_validation."
            )
        counts = _reset_fixtures(db)
        print({"database": database_name, "fixture_set": FIXTURE_SET,
               "deleted": counts})
        return 0

    counts = _write_fixtures(db, documents)
    print({"database": database_name, "fixture_set": FIXTURE_SET,
           "inserted": counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
