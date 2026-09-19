"""Read-only prerequisite audit, NOT admission or a replacement chess grader.

Run from backend with PYTHONPATH=. in the configured backend environment.
Prints aggregate counts only. Never exports positions, identifiers, stored text,
credentials or moves. No database writes, engines, models or pool rebuilding.
Reason coverage is proposed content availability, not independent teachability.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from typing import Iterable

import chess

from services.caption_pipeline import build_reason_bundle_for_move
from services.destination_safety_detector import QUALITY_ID, FACT_VERSION
from services.detector_quality import QualitySurface, is_authorized
from services.diagnostic_service import (
    CONCEPT_PRIORITY,
    DiagnosticGrader,
    frozen_diagnostic_grades_are_current,
)


def _position(fen):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("invalid board")
    return " ".join(board.fen().split()[:4])


def _steps(row):
    """Bind each frozen map to its actual solver turn in the stored line."""
    board = chess.Board(row["fen"])
    _position(board.fen())
    line = row["moves"]
    if not isinstance(line, list) or not line or row.get("user_move_idx", 0) != 0:
        raise ValueError("unsupported stored line")
    expected = []
    for index, uci in enumerate(line):
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError("illegal stored line")
        if index % 2 == 0:
            expected.append((_position(board.fen()), uci))
        board.push(move)
    steps = row["step_grades"]
    if len(steps) != len(expected):
        raise ValueError("missing or extra step")
    result = []
    for step, (fen_key, solution) in zip(steps, expected):
        if _position(step["fen"]) != fen_key or step["solution_uci"] != solution:
            raise ValueError("step does not match stored line")
        board = chess.Board(step["fen"])
        legal = {move.uci() for move in board.legal_moves}
        grades = step["grade_by_uci"]
        if not isinstance(grades, dict) or not set(grades).issubset(legal):
            raise ValueError("illegal grade entry")
        if solution not in grades:
            raise ValueError("ungraded solution")
        for grade in grades.values():
            if (
                not isinstance(grade, dict)
                or grade.get("verdict") not in {"UNDERSTOOD", "PARTIAL", "MISSING"}
                or type(grade.get("cp_loss")) is not int
                or grade["cp_loss"] < 0
                or type(grade.get("eval_after_cp")) is not int
            ):
                raise ValueError("malformed grade")
        result.append((step, len(legal - set(grades))))
    return result


def build_report(rows: Iterable[dict], *, derive_reasons: bool = False) -> dict:
    """Pure audit over a projected iterable; retains only aggregate results."""
    counts = Counter()
    concepts = Counter()
    outcomes = Counter()
    questions = Counter()
    answer_positions = Counter()
    seen = set()
    grader = DiagnosticGrader()
    authorized = is_authorized(QUALITY_ID, QualitySurface.CAPTION)
    for row in rows:
        counts["rows_scanned"] += 1
        concept = row.get("concept")
        concepts[concept if concept in CONCEPT_PRIORITY else "unknown"] += 1
        try:
            if not frozen_diagnostic_grades_are_current(row):
                counts["stale_or_missing_frozen_grades"] += 1
                continue
            steps = _steps(row)
        except (ValueError, TypeError, KeyError, AttributeError):
            counts["invalid_stored_contract"] += 1
            continue
        counts["current_valid_rows"] += 1
        if any(missing for _, missing in steps):
            counts["rows_missing_legal_move_grades"] += 1
        row_has_reason = False
        for step, missing in steps:
            counts["solver_steps"] += 1
            counts["missing_legal_move_grades"] += missing
            for uci in step["grade_by_uci"]:
                counts["stored_candidate_occurrences"] += 1
                key = (_position(step["fen"]), uci)
                if key in seen:
                    counts["repeated_position_move_occurrences"] += 1
                seen.add(key)
                if not derive_reasons:
                    continue
                if not authorized:
                    counts["reason_authorization_blocked"] += 1
                    continue
                try:
                    grade = grader._grade_move_consequence(
                        uci, row, fen=step["fen"], solution_uci=step["solution_uci"],
                    )
                    bundle = build_reason_bundle_for_move(
                        fen_before=step["fen"], submitted_move=uci, quality_id=QUALITY_ID,
                    )
                    if (
                        bundle is None or bundle.target_result == "unmeasured"
                        or not bundle.components
                    ):
                        counts["no_supported_reason"] += 1
                        continue
                    if (
                        bundle.proof.quality_id != QUALITY_ID
                        or bundle.proof.detector_version != FACT_VERSION
                        or bundle.move_uci != uci
                    ):
                        counts["reason_provenance_mismatch"] += 1
                        continue
                    # Keep move evaluation and the narrow piece-safety fact on
                    # separate axes. Neither proves the player's understanding.
                    outcomes[f'{grade["verdict"]}:{bundle.target_result}'] += 1
                    counts["candidate_occurrences_with_reason"] += 1
                    row_has_reason = True
                    for component in bundle.components:
                        counts["proposed_question_occurrences"] += 1
                        # Only numeric slots, never arbitrary stored labels.
                        questions[str(len(component.choices))] += 1
                        for index, choice in enumerate(component.choices):
                            if choice.choice_id in component.accepted_choice_ids:
                                answer_positions[str(index)] += 1
                except (ValueError, TypeError, KeyError, AttributeError):
                    counts["reason_derivation_errors"] += 1
        if row_has_reason:
            counts["rows_with_at_least_one_proposed_reason"] += 1
    counts["distinct_position_move_pairs"] = len(seen)
    return {
        "schema_version": "diagnostic_teaching_readiness_audit.v1",
        "read_only": True,
        "engine_or_model_calls": False,
        "raw_positions_exported": False,
        "reason_derivation_requested": derive_reasons,
        "reason_quality_id": QUALITY_ID,
        "reason_detector_version": FACT_VERSION,
        "caption_authorized": authorized,
        "counts": dict(sorted(counts.items())),
        "concept_counts": dict(sorted(concepts.items())),
        "move_verdict_by_destination_safety": dict(sorted(outcomes.items())),
        "question_choice_counts": dict(sorted(questions.items())),
        "accepted_answer_slot_counts_zero_based": dict(sorted(answer_positions.items())),
        "ready_for_player_exposure": False,
        "limitations": [
            "Reason coverage measures moved-piece safety only, not the puzzle's whole idea.",
            "Question counts are occurrences, not independent review sample sizes.",
            "No changed-position pairing or independent teaching review is established.",
            "A correct move or reason is not a mastery or weakness verdict.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--derive-reasons", action="store_true",
                        help="Also run existing deterministic reason proofs; no engine.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Explicit row cap for an initial probe; reports partial coverage.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    from pymongo import MongoClient

    client = None
    try:
        client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
        pool = client[os.environ["DB_NAME"]].diagnostic_pool
        population = pool.count_documents({})
        projection = {name: 1 for name in (
            "puzzle_id", "concept", "fen", "moves", "user_move_idx", "puzzle_rating",
            "grade_version", "grade_fingerprint", "step_grades",
        )}
        projection["_id"] = 0
        cursor = pool.find({}, projection).sort("_id", 1)
        if args.limit is not None:
            cursor = cursor.limit(args.limit)
        report = build_report(cursor, derive_reasons=args.derive_reasons)
        report["collection_count_at_start"] = population
        report["requested_row_limit"] = args.limit
        report["scan_scope"] = "limited" if args.limit is not None else "all_rows"
        report["snapshot_consistency"] = "not_a_transactional_snapshot"
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception:
        # DB exception strings can contain connection details or document text.
        print(json.dumps({"status": "audit_failed", "read_only": True,
                          "message": "No coverage result. Check configuration/access privately."}))
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
