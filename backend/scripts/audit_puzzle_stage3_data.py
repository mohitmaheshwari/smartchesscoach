#!/usr/bin/env python3
"""Audit whether stored puzzle attempts can support difficulty calibration.

Read-only and aggregate-only: no player, puzzle, game, position, or move
identifier is written to the output.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import chess
from pymongo import MongoClient

SCHEMA_VERSION = "human_chess.puzzle_stage3_data_audit.v1"
SUPPORT_FIELDS = (
    "support_level",
    "used_hint",
    "hint_count",
    "assisted",
    "assistance",
    "revealed",
    "evidence_mode",
)
RATING_FIELDS = ("player_rating", "user_rating", "rating", "solver_rating")


def parse_timestamp(row: Mapping[str, Any]) -> Optional[datetime]:
    value = row.get("created_at")
    if value is None:
        value = row.get("attempted_at")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalize_outcome(row: Mapping[str, Any]) -> tuple[Optional[bool], str]:
    correct = row.get("correct")
    solved = row.get("solved")
    has_correct = isinstance(correct, bool)
    has_solved = isinstance(solved, bool)
    if has_correct and has_solved and correct != solved:
        return None, "conflicting"
    if has_correct:
        return correct, "correct"
    if has_solved:
        return solved, "solved"
    return None, "missing"


def support_state(row: Mapping[str, Any]) -> str:
    present = {field: row.get(field) for field in SUPPORT_FIELDS if field in row}
    if not present:
        return "support_unknown"
    positive_strings = {"hint", "assisted", "guided", "revealed", "reveal", "help"}
    for field, value in present.items():
        if value is True:
            return "assisted"
        if field == "hint_count" and isinstance(value, (int, float)) and value > 0:
            return "assisted"
        if isinstance(value, str) and value.strip().lower() in positive_strings:
            return "assisted"
    explicit_none = {
        "none", "independent", "unassisted", "false", "0", "practice_independent"
    }
    if all(
        value is False
        or value == 0
        or (isinstance(value, str) and value.strip().lower() in explicit_none)
        for value in present.values()
    ):
        return "independent"
    return "support_unknown"


def target_move_uci(puzzle: Mapping[str, Any]) -> Optional[str]:
    fen = puzzle.get("fen") or puzzle.get("fen_before")
    if not isinstance(fen, str):
        return None
    try:
        board = chess.Board(fen)
    except ValueError:
        return None
    for field in ("best_move_uci", "solution_uci", "target_move_uci"):
        value = puzzle.get(field)
        if isinstance(value, str):
            try:
                move = chess.Move.from_uci(value.lower())
            except ValueError:
                continue
            if move in board.legal_moves:
                return move.uci()
    for field in ("best_move_san", "solution_san"):
        value = puzzle.get(field)
        if isinstance(value, str):
            try:
                return board.parse_san(value).uci()
            except ValueError:
                continue
    solution = puzzle.get("solution")
    if isinstance(solution, list) and solution and isinstance(solution[0], str):
        try:
            return board.parse_san(solution[0]).uci()
        except ValueError:
            try:
                move = chess.Move.from_uci(solution[0].lower())
                return move.uci() if move in board.legal_moves else None
            except ValueError:
                return None
    return None


def _field_signature(row: Mapping[str, Any]) -> str:
    excluded = {
        "_id", "user_id", "puzzle_id", "moves_tried", "solution_submitted",
        "created_at", "attempted_at",
    }
    return "|".join(sorted(key for key in row if key not in excluded))


def _distribution(values: Iterable[int]) -> Dict[str, Optional[float]]:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        return {"minimum": None, "median": None, "p90": None, "maximum": None}
    at = lambda fraction: ordered[round((len(ordered) - 1) * fraction)]
    return {
        "minimum": ordered[0],
        "median": at(0.5),
        "p90": at(0.9),
        "maximum": ordered[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = client[db_name]

    attempt_projection = {
        "_id": 0,
        "user_id": 1,
        "puzzle_id": 1,
        "correct": 1,
        "solved": 1,
        "created_at": 1,
        "attempted_at": 1,
        "moves_tried": 1,
        "quality": 1,
        "weakness_type": 1,
        "weakness_pattern": 1,
        **{field: 1 for field in SUPPORT_FIELDS},
        **{field: 1 for field in RATING_FIELDS},
    }
    attempts = list(db.puzzle_attempts.find({}, attempt_projection))
    attempt_ids = {
        str(row["puzzle_id"])
        for row in attempts
        if row.get("puzzle_id") not in (None, "")
    }

    community_by_id: Dict[str, Dict[str, Any]] = {}
    community_signature = Counter()
    community_admission_status = Counter()
    community_admission_quality = Counter()
    community_acceptable_count = Counter()
    community_projection = {
        "fen": 1,
        "fen_before": 1,
        "best_move_uci": 1,
        "best_move_san": 1,
        "solution_uci": 1,
        "solution_san": 1,
        "solution": 1,
        "difficulty": 1,
        "cp_loss": 1,
        "issue_type": 1,
        "skill_id": 1,
        "source": 1,
        "rating": 1,
        "verified_admission": 1,
        "admission": 1,
        "approved": 1,
    }
    for row in db.community_puzzles.find({}, community_projection):
        community_signature[_field_signature(row)] += 1
        admission = row.get("verified_admission") or {}
        community_admission_status[str(admission.get("status") or "missing")] += 1
        community_admission_quality[str(admission.get("quality_grade") or "missing")] += 1
        community_acceptable_count[str(len(admission.get("acceptable_moves_uci") or []))] += 1
        identifier = str(row["_id"])
        if identifier in attempt_ids:
            community_by_id[identifier] = row

    training_by_id: Dict[str, Dict[str, Any]] = {}
    training_signature = Counter()
    training_admission_status = Counter()
    training_admission_quality = Counter()
    training_acceptable_count = Counter()
    training_projection = {
        "position_id": 1,
        "puzzle_id": 1,
        "fen": 1,
        "fen_before": 1,
        "best_move_uci": 1,
        "best_move_san": 1,
        "solution_uci": 1,
        "solution_san": 1,
        "difficulty": 1,
        "cp_loss": 1,
        "pattern_type": 1,
        "source": 1,
        "source_user_rating": 1,
        "verified_admission": 1,
        "admission": 1,
        "approved": 1,
    }
    for row in db.community_training_positions.find({}, training_projection):
        training_signature[_field_signature(row)] += 1
        admission = row.get("verified_admission") or {}
        training_admission_status[str(admission.get("status") or "missing")] += 1
        training_admission_quality[str(admission.get("quality_grade") or "missing")] += 1
        training_acceptable_count[str(len(admission.get("acceptable_moves_uci") or []))] += 1
        identifiers = {
            str(value) for value in (row.get("position_id"), row.get("puzzle_id"), row.get("_id"))
            if value not in (None, "")
        }
        for identifier in identifiers & attempt_ids:
            training_by_id[identifier] = row

    schema_signatures = Counter()
    outcome_fields = Counter()
    support_states = Counter()
    rating_availability = Counter()
    rejection = Counter()
    first_by_pair: Dict[tuple[str, str], tuple[datetime, Dict[str, Any]]] = {}
    eligible_attempts = []
    for row in attempts:
        schema_signatures[_field_signature(row)] += 1
        outcome, outcome_field = normalize_outcome(row)
        outcome_fields[outcome_field] += 1
        support_states[support_state(row)] += 1
        available_rating_fields = [field for field in RATING_FIELDS if isinstance(row.get(field), (int, float))]
        rating_availability["has_attempt_time_rating" if available_rating_fields else "missing_attempt_time_rating"] += 1
        user_id = row.get("user_id")
        puzzle_id = row.get("puzzle_id")
        timestamp = parse_timestamp(row)
        if not user_id or not puzzle_id:
            rejection["missing_user_or_puzzle_id"] += 1
            continue
        if outcome is None:
            rejection[f"outcome_{outcome_field}"] += 1
            continue
        if timestamp is None:
            rejection["missing_or_invalid_timestamp"] += 1
            continue
        normalized = dict(row)
        normalized["_outcome"] = outcome
        normalized["_support"] = support_state(row)
        normalized["_timestamp"] = timestamp
        pair = (str(user_id), str(puzzle_id))
        current = first_by_pair.get(pair)
        if current is None or timestamp < current[0]:
            first_by_pair[pair] = (timestamp, normalized)
        eligible_attempts.append(normalized)

    first_attempts = [value[1] for value in first_by_pair.values()]
    first_per_user = Counter(str(row["user_id"]) for row in first_attempts)
    join_counts = Counter()
    first_outcomes = Counter()
    matched_metadata = Counter()
    difficulty_distribution = Counter()
    for row in first_attempts:
        puzzle_id = str(row["puzzle_id"])
        in_community = puzzle_id in community_by_id
        in_training = puzzle_id in training_by_id
        if in_community and in_training:
            source = "cross_pool_conflict"
            puzzle = None
        elif in_community:
            source = "community_puzzles"
            puzzle = community_by_id[puzzle_id]
        elif in_training:
            source = "community_training_positions"
            puzzle = training_by_id[puzzle_id]
        else:
            source = "unmatched"
            puzzle = None
        join_counts[source] += 1
        first_outcomes[f"{row['_support']}|{'correct' if row['_outcome'] else 'incorrect'}"] += 1
        if puzzle is None:
            continue
        matched_metadata["matched"] += 1
        if target_move_uci(puzzle):
            matched_metadata["legal_target_move"] += 1
        else:
            matched_metadata["missing_or_invalid_target_move"] += 1
        if isinstance(puzzle.get("cp_loss"), (int, float)):
            matched_metadata["has_cp_loss"] += 1
        else:
            matched_metadata["missing_cp_loss"] += 1
        difficulty = str(puzzle.get("difficulty") or "missing")
        difficulty_distribution[f"{source}|{difficulty}"] += 1
        admission = puzzle.get("verified_admission") or puzzle.get("admission")
        if isinstance(admission, Mapping):
            matched_metadata["has_admission_evidence_field"] += 1
            matched_metadata[
                f"admission_status_{str(admission.get('status') or 'missing')}"
            ] += 1
        else:
            matched_metadata["missing_admission_evidence_field"] += 1

    collection_counts = {
        "puzzle_attempts": len(attempts),
        "community_puzzles": db.community_puzzles.count_documents({}),
        "community_training_positions": db.community_training_positions.count_documents({}),
    }
    client.close()
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "read_only": True,
        "privacy": {
            "player_identifiers_exported": False,
            "puzzle_identifiers_exported": False,
            "positions_or_moves_exported": False,
        },
        "source": {"database": db_name, "source_revision": args.source_revision},
        "collections": collection_counts,
        "attempt_schema_signatures": dict(schema_signatures.most_common()),
        "outcome_field_counts": dict(sorted(outcome_fields.items())),
        "support_state_counts": dict(sorted(support_states.items())),
        "attempt_rating_counts": dict(sorted(rating_availability.items())),
        "eligibility": {
            "outcome_and_timestamp_eligible_rows": len(eligible_attempts),
            "unique_user_puzzle_first_attempts": len(first_attempts),
            "repeat_rows_removed": len(eligible_attempts) - len(first_attempts),
            "rejections": dict(sorted(rejection.items())),
            "users_with_first_attempts": len(first_per_user),
            "first_attempts_per_user": _distribution(first_per_user.values()),
        },
        "first_attempts": {
            "support_x_outcome": dict(sorted(first_outcomes.items())),
            "puzzle_source_join": dict(sorted(join_counts.items())),
            "matched_metadata": dict(sorted(matched_metadata.items())),
            "difficulty_distribution": dict(sorted(difficulty_distribution.items())),
        },
        "pool_projection_signatures": {
            "community_puzzles": dict(community_signature.most_common()),
            "community_training_positions": dict(training_signature.most_common()),
        },
        "pool_admission": {
            "community_puzzles": {
                "status": dict(sorted(community_admission_status.items())),
                "quality_grade": dict(sorted(community_admission_quality.items())),
                "acceptable_move_count": dict(sorted(community_acceptable_count.items())),
            },
            "community_training_positions": {
                "status": dict(sorted(training_admission_status.items())),
                "quality_grade": dict(sorted(training_admission_quality.items())),
                "acceptable_move_count": dict(sorted(training_acceptable_count.items())),
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "collections": result["collections"],
        "eligibility": result["eligibility"],
        "support": result["support_state_counts"],
        "joins": result["first_attempts"]["puzzle_source_join"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
