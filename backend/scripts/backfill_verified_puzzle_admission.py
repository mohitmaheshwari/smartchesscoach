"""Backfill the shared deterministic admission verdict onto both puzzle pools.

Default is a read-only dry run. This script never invokes Stockfish, an LLM,
HTTP, or a subprocess; it reuses PGN/session provenance and analysis already
stored in MongoDB.

Usage inside the backend container:
  python backend/scripts/backfill_verified_puzzle_admission.py
  python backend/scripts/backfill_verified_puzzle_admission.py --apply
  python backend/scripts/backfill_verified_puzzle_admission.py --limit 1000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import UpdateOne  # noqa: E402

from services.puzzle_extraction_service import verified_issue_type  # noqa: E402
from services.forced_mate_puzzle_proof import (  # noqa: E402
    FORCED_MATE_QUALITY_ID,
)
from services.verified_puzzle_admission import (  # noqa: E402
    AdmissionReason,
    AdmissionStatus,
    PuzzleCandidate,
    StoredAnalysisEvidence,
    adjudicate_puzzle,
)
from services.verified_puzzle_builder import (  # noqa: E402
    build_imported_game_verdict,
    build_position_verdict,
)
from services.verified_puzzle_runtime import find_move_evaluation  # noqa: E402
from services.verified_puzzle_feedback import (  # noqa: E402
    build_verified_puzzle_feedback,
)
from scripts.measure_forced_mate_caption_promotion import (  # noqa: E402
    independent_adjudication,
)


POOL_NAMES = ("community_puzzles", "community_training_positions")
CACHE_LIMIT = 256
BATCH_SIZE = 500
_CACHE_MISS = object()
_FORCED_MATE_FACT_KEYS = (
    "mate_ply",
    "replayed_uci",
    "best_move_san",
    "mating_move_uci",
    "mating_move_san",
    "mating_piece",
    "mating_square",
    "king_square",
    "terminal_legal_replies",
)


def _remember(cache: OrderedDict, key: str, value: Any) -> Any:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > CACHE_LIMIT:
        cache.popitem(last=False)
    return value


def _cached(cache: OrderedDict, key: str) -> Any:
    if key not in cache:
        return _CACHE_MISS
    cache.move_to_end(key)
    return cache[key]


def _normalized_fen(raw: Any) -> Optional[str]:
    try:
        return " ".join(chess.Board(str(raw)).fen().split()[:4])
    except (TypeError, ValueError):
        return None


def _unresolved_verdict(collection: str, row: Dict):
    return adjudicate_puzzle(PuzzleCandidate(
        source_kind=f"unresolved_{collection}",
        source_ref=str(row.get("source_game_id") or row.get("position_id") or row.get("_id")),
        stored_fen=row.get("fen"),
        played_move=row.get("user_move_san") or row.get("played_move"),
        analysis=StoredAnalysisEvidence(
            played_move=row.get("user_move_san") or row.get("played_move"),
            best_move=row.get("best_move_uci") or row.get("best_move_san"),
            cp_loss=row.get("cp_loss"),
        ),
    ))


def _session_move(session: Dict, row: Dict) -> Dict:
    wanted = _normalized_fen(row.get("fen"))
    for move in session.get("move_history") or []:
        if not isinstance(move, dict) or move.get("by") != "player":
            continue
        if _normalized_fen(move.get("fen_before")) == wanted:
            return {
                "fen_before": move.get("fen_before"),
                "move": move.get("move") or row.get("user_move_san"),
                "best_move_san": move.get("best_move") or row.get("best_move_san"),
                "best_move_uci": row.get("best_move_uci"),
                "cp_loss": row.get("cp_loss"),
                "eval_before": move.get("eval_before"),
                "eval_after": move.get("eval_after"),
                "pv_after_best": move.get("pv_after_best") or row.get("pv_after_best") or [],
                "pv_after_played": move.get("pv_after_played") or row.get("pv_after_played") or [],
            }
    return {}


async def _source_verdict(db, collection: str, row: Dict, caches: Dict):
    source_id = row.get("source_game_id")
    if not source_id:
        return _unresolved_verdict(collection, row), None

    game = _cached(caches["games"], source_id)
    if game is _CACHE_MISS:
        game = _remember(
            caches["games"],
            source_id,
            await db.games.find_one({"game_id": source_id}, {"_id": 0}),
        )
    if game:
        analysis = _cached(caches["analyses"], source_id)
        if analysis is _CACHE_MISS:
            analysis = _remember(
                caches["analyses"],
                source_id,
                await db.game_analyses.find_one(
                    {"game_id": source_id}, {"_id": 0}
                ),
            )
        move = find_move_evaluation(
            analysis or {}, move_number=row.get("move_number"), fen=row.get("fen")
        )
        if move:
            verdict = build_imported_game_verdict(
                game=game,
                move_evaluation=move,
                broad_category=move.get("cognitive_gap") or None,
            )
            return verdict, move

    session = _cached(caches["sessions"], source_id)
    if session is _CACHE_MISS:
        session = _remember(
            caches["sessions"],
            source_id,
            await db.coach_sessions.find_one(
                {"session_id": source_id}, {"_id": 0, "move_history": 1}
            ),
        )
    evidence = _session_move(session or {}, row)
    if evidence:
        verdict = build_position_verdict(
            source_kind="coach_session",
            source_ref=str(source_id),
            move_evaluation=evidence,
            broad_category=None,
        )
        return verdict, evidence

    return _unresolved_verdict(collection, row), None


def _safe_description(issue_type: str) -> str:
    if issue_type == "piece_safety":
        return "From a real game — find the move that keeps every piece safe."
    return "From a real game — calculate the best continuation."


def _set_fields(collection: str, row: Dict, verdict, source_move: Optional[Dict]) -> Dict:
    issue_type = verified_issue_type(verdict)
    fields: Dict[str, Any] = {
        "verified_admission": verdict.to_document(),
        # Never turn a prior human/quality-gate rejection into approval. A
        # later reviewer can inspect the new evidence and explicitly approve
        # it; this migration only enriches provenance non-destructively.
        "approved": (
            row.get("approved") is not False
            and verdict.status != AdmissionStatus.QUARANTINE
        ),
    }
    if collection == "community_puzzles":
        fields.update({
            "legacy_issue_type": row.get("legacy_issue_type") or row.get("issue_type"),
            "issue_type": issue_type,
            "theme": "tactical" if issue_type == "piece_safety" else "calculation",
            "description": _safe_description(issue_type),
        })
        if row.get("skill_id") and not row.get("legacy_skill_id"):
            fields["legacy_skill_id"] = row.get("skill_id")
    else:
        fields.update({
            "legacy_pattern_type": row.get("legacy_pattern_type") or row.get("pattern_type"),
            "pattern_type": issue_type,
        })

    if source_move:
        best_san = source_move.get("best_move_san") or source_move.get("best_move")
        if best_san:
            fields["best_move_san"] = best_san
        if source_move.get("best_move_uci"):
            fields["best_move_uci"] = source_move.get("best_move_uci")
        played = source_move.get("move") or source_move.get("move_san")
        if played:
            target = "user_move_san" if collection == "community_training_positions" else "played_move"
            fields[target] = played
        fields["pv_after_best"] = source_move.get("pv_after_best") or []
        fields["pv_after_played"] = source_move.get("pv_after_played") or []
    return fields


def _forced_mate_validation_row(
    row: Mapping[str, Any],
    source_move: Optional[Mapping[str, Any]],
    fields: Mapping[str, Any],
) -> Dict[str, Any]:
    """Reconstruct the evidence the runtime used without trusting old verdict facts."""
    merged = dict(row)
    merged.update({
        key: value
        for key, value in fields.items()
        if key != "verified_admission"
    })
    source = source_move or {}
    merged.update({
        "fen": source.get("fen_before") or merged.get("fen"),
        "played_move": (
            source.get("move")
            or source.get("move_san")
            or merged.get("played_move")
            or merged.get("user_move_san")
        ),
        "best_move_uci": source.get("best_move_uci") or merged.get("best_move_uci"),
        "best_move_san": (
            source.get("best_move_san")
            or source.get("best_move")
            or merged.get("best_move_san")
        ),
        "cp_loss": source.get("cp_loss") if "cp_loss" in source else merged.get("cp_loss"),
        "pv_after_best": (
            source.get("pv_after_best")
            if "pv_after_best" in source
            else merged.get("pv_after_best") or []
        ),
    })
    merged["verified_admission"] = fields.get("verified_admission") or {}
    return merged


def _forced_mate_readmission_check(
    row: Mapping[str, Any],
    source_move: Optional[Mapping[str, Any]],
    fields: Mapping[str, Any],
) -> Tuple[str, Optional[str]]:
    """Check one rebuilt row independently before any targeted batch write."""
    candidate = _forced_mate_validation_row(row, source_move, fields)
    gold = independent_adjudication(candidate)
    admission = candidate.get("verified_admission") or {}
    is_caption_admission = bool(
        admission.get("status") == AdmissionStatus.BROAD.value
        and admission.get("quality_id") == FORCED_MATE_QUALITY_ID
        and admission.get("caption_concept_id")
        in {"tactic.mate_in_one", "tactic.forced_mate"}
        and admission.get("quality_grade") == "caption"
    )

    if gold.get("status") != "exact":
        if is_caption_admission:
            return "violation", "ineligible_candidate_did_not_abstain"
        return "abstained", None
    if not is_caption_admission:
        return "violation", "eligible_candidate_not_caption_admitted"

    facts = admission.get("verifier_facts") or ()
    fact = facts[0] if facts and isinstance(facts[0], Mapping) else {}
    if any(
        (
            tuple(fact.get(key) or ()) != tuple(gold.get(key) or ())
            if key == "replayed_uci"
            else fact.get(key) != gold.get(key)
        )
        for key in _FORCED_MATE_FACT_KEYS
    ):
        return "violation", "independent_fact_mismatch"
    if fact.get("terminal_legal_replies") != 0:
        return "violation", "terminal_reply_count_not_zero"

    try:
        feedback = build_verified_puzzle_feedback(
            candidate,
            str(admission.get("played_move_uci") or ""),
            correct=False,
            primary_uci=str(gold.get("best_move_uci") or ""),
        )
    except (KeyError, TypeError, ValueError, AssertionError):
        return "violation", "caption_render_failed"
    why = str(feedback.get("why") or "")
    rendered_line = " ".join(str(move) for move in gold.get("replayed_san") or ())
    required_caption_facts = (
        (
            gold.get("best_move_san")
            if gold.get("subtype") == "mate_in_one"
            else rendered_line
        ),
        gold.get("king_square"),
        "no legal reply",
    )
    if any(
        not value or str(value).lower() not in why.lower()
        for value in required_caption_facts
    ):
        return "violation", "caption_omits_verified_fact"
    return "validated", None


async def process_rows(
    db,
    *,
    collections,
    limit: Optional[int] = None,
    apply: bool = False,
    quality_id: Optional[str] = None,
):
    """Stream both pools with bounded memory; optionally write in batches."""
    caches = {
        "games": OrderedDict(),
        "analyses": OrderedDict(),
        "sessions": OrderedDict(),
    }
    counts = Counter()
    processed = 0
    by_fen = defaultdict(list)
    strict_forced_mate = quality_id == FORCED_MATE_QUALITY_ID
    staged_updates = defaultdict(list)
    checked_fens = set()
    strict_violations = 0
    for collection in collections:
        pending = []
        query = (
            {"verified_admission.quality_id": quality_id}
            if quality_id
            else {}
        )
        cursor = db[collection].find(query)
        if limit:
            cursor = cursor.limit(limit)
        async for row in cursor:
            verdict, source_move = await _source_verdict(
                db, collection, row, caches
            )
            fields = _set_fields(collection, row, verdict, source_move)
            processed += 1
            if strict_forced_mate:
                normalized = _normalized_fen(row.get("fen"))
                if normalized:
                    checked_fens.add(normalized)
                outcome, violation = _forced_mate_readmission_check(
                    row, source_move, fields
                )
                counts[("all", f"forced_mate_{outcome}")] += 1
                if violation:
                    strict_violations += 1
                    counts[("all", f"violation:{violation}")] += 1
            counts[(collection, verdict.status.value)] += 1
            if row.get("approved") is False and fields.get("approved") is False:
                counts[(collection, "preserved_quality_rejection")] += 1
            verdict_quality_id = getattr(verdict, "quality_id", None)
            if verdict_quality_id:
                counts[(collection, f"quality:{verdict_quality_id}")] += 1
            for reason in verdict.reason_codes:
                counts[(collection, f"reason:{reason}")] += 1
            normalized = _normalized_fen(row.get("fen"))
            answers = frozenset(verdict.acceptable_moves_uci)
            if normalized and answers and verdict.status != AdmissionStatus.QUARANTINE:
                by_fen[normalized].append((
                    collection,
                    row["_id"],
                    verdict,
                ))
            if apply:
                operation = UpdateOne({"_id": row["_id"]}, {"$set": fields})
                if strict_forced_mate:
                    staged_updates[collection].append(operation)
                else:
                    pending.append(operation)
                    if len(pending) >= BATCH_SIZE:
                        await db[collection].bulk_write(pending, ordered=False)
                        pending = []
        if apply and pending:
            await db[collection].bulk_write(pending, ordered=False)

    # A different stored best move for the same FEN is not proof that both moves
    # are equivalent. Do not union answers, downgrade the claim, or serve one
    # source opportunistically: a player could receive contradictory grading.
    # Quarantine every conflicting row until its source evidence is adjudicated.
    conflict_positions = 0
    conflict_rows = 0
    conflict_updates = defaultdict(list)
    for grouped in by_fen.values():
        if len(grouped) < 2:
            continue
        shared = set.intersection(*(
            set(item[2].acceptable_moves_uci) for item in grouped
        ))
        if shared:
            continue
        conflict_positions += 1
        for collection, row_id, old_verdict in grouped:
            conflict_rows += 1
            old_status = old_verdict.status.value
            verdict_quality_id = getattr(old_verdict, "quality_id", None)
            if old_status != AdmissionStatus.QUARANTINE.value:
                counts[(collection, old_status)] -= 1
                counts[(collection, AdmissionStatus.QUARANTINE.value)] += 1
                if verdict_quality_id:
                    counts[(collection, f"quality:{verdict_quality_id}")] -= 1
            counts[(collection, f"reason:{AdmissionReason.CROSS_POOL_ANSWER_CONFLICT.value}")] += 1
            if apply and not strict_forced_mate:
                conflict_verdict = replace(
                    old_verdict,
                    status=AdmissionStatus.QUARANTINE,
                    reason_codes=(AdmissionReason.CROSS_POOL_ANSWER_CONFLICT.value,),
                    played_move_uci=None,
                    acceptable_moves_uci=(),
                    concept_id=None,
                    broad_category=None,
                    detector_id=None,
                    detector_version=None,
                    verifier_id=None,
                    verifier_version=None,
                    quality_id=None,
                    quality_grade=None,
                    detector_facts=(),
                    verifier_facts=(),
                )
                fields = {
                    "verified_admission": conflict_verdict.to_document(),
                    "approved": False,
                }
                conflict_updates[collection].append(UpdateOne(
                    {"_id": row_id},
                    {"$set": fields},
                ))
    counts[("all", "cross_pool_conflict_positions")] = conflict_positions
    counts[("all", "cross_pool_conflict_rows")] = conflict_rows
    if strict_forced_mate:
        if conflict_rows:
            strict_violations += conflict_rows
            counts[("all", "violation:cross_pool_answer_conflict")] += conflict_rows
        counts[("all", "forced_mate_distinct_fens_checked")] = len(checked_fens)
        counts[("all", "forced_mate_violations")] = strict_violations
        gate_passed = bool(
            processed > 0
            and strict_violations == 0
            and (
                counts[("all", "forced_mate_validated")]
                + counts[("all", "forced_mate_abstained")]
                == processed
            )
        )
        counts[("all", "forced_mate_zero_violation_gate_passed")] = int(
            gate_passed
        )
        if apply and not gate_passed:
            raise RuntimeError(
                "forced-mate re-admission aborted before writes: "
                f"rows={processed} violations={strict_violations}"
            )
        if apply:
            for collection, operations in staged_updates.items():
                for start in range(0, len(operations), BATCH_SIZE):
                    await db[collection].bulk_write(
                        operations[start:start + BATCH_SIZE], ordered=False
                    )
    elif apply:
        for collection, operations in conflict_updates.items():
            for start in range(0, len(operations), BATCH_SIZE):
                await db[collection].bulk_write(
                    operations[start:start + BATCH_SIZE], ordered=False
                )
    return processed, counts


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write updates; default is dry-run")
    parser.add_argument("--limit", type=int, default=None, help="limit rows per collection")
    parser.add_argument("--collection", choices=POOL_NAMES, action="append")
    parser.add_argument(
        "--quality-id",
        default=None,
        help=(
            "rebuild only rows carrying this stored verified-admission quality ID; "
            "forced-mate rows receive an automatic zero-violation caption gate"
        ),
    )
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]
    collections = tuple(args.collection or POOL_NAMES)

    processed, counts = await process_rows(
        db,
        collections=collections,
        limit=args.limit,
        apply=args.apply,
        quality_id=args.quality_id,
    )
    print(f"mode={'APPLY' if args.apply else 'DRY_RUN'} rows={processed}")
    for key in sorted(counts, key=str):
        print(f"{key[0]} {key[1]}={counts[key]}")
    if args.apply:
        print(f"applied={processed}")
    else:
        print("No writes made. Pass --apply after reviewing these aggregates.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
