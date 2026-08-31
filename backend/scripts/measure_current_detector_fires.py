"""Replay analyzed games through current concept detectors and emit counts only.

The script imports the deployed deterministic detectors and python-chess. It does
not import or invoke Stockfish, an LLM, or a network API. MongoDB reads are
limited to source PGNs and analysis IDs; output contains aggregates only.
"""

from __future__ import annotations

import inspect
import io
import json
import os
import time
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict

import chess
import chess.pgn
from pymongo import MongoClient

from services.concept_detectors.registry import all_detectors
from services.decryption_voice.opening_book import recognize_opening_from_history
from services.detector_quality import (
    QualitySurface,
    can_influence,
    concept_quality_id,
    grade_for,
)


EXTRA_KWARGS = (
    "move_number",
    "opening_name",
    "move_history_san",
    "best_move_san",
    "best_move_uci",
)


def _user_color(raw: Any):
    value = str(raw or "").strip().lower()
    if value in {"white", "w"}:
        return chess.WHITE
    if value in {"black", "b"}:
        return chess.BLACK
    return None


def _opening_key(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("name") or result.get("opening_key") or "missing")
    if result:
        return str(result)
    return "missing"


def _analysis_move_is_user(record: Dict[str, Any]) -> bool:
    if "is_user_move" in record:
        return bool(record.get("is_user_move"))
    if "is_opponent_move" in record:
        return not bool(record.get("is_opponent_move"))
    return True


def _cp_summary(values, missing: int) -> Dict[str, Any]:
    ordered = sorted(max(0.0, float(value)) for value in values)
    buckets = Counter()
    for value in ordered:
        if value <= 25:
            buckets["0_25"] += 1
        elif value <= 50:
            buckets["26_50"] += 1
        elif value <= 100:
            buckets["51_100"] += 1
        elif value <= 200:
            buckets["101_200"] += 1
        else:
            buckets["over_200"] += 1
    if not ordered:
        return {"matched": 0, "missing": missing, "buckets": dict(buckets)}
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[midpoint]
    else:
        median = (ordered[midpoint - 1] + ordered[midpoint]) / 2
    p75 = ordered[int((len(ordered) - 1) * 0.75)]
    return {
        "matched": len(ordered),
        "missing": missing,
        "median_cp_loss": round(median, 3),
        "p75_cp_loss": round(p75, 3),
        "buckets": dict(buckets),
    }


def measure() -> Dict[str, Any]:
    started = time.monotonic()
    client = MongoClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000
    )
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    analyzed_ids = {
        str(row["game_id"])
        for row in db.game_analyses.find(
            {"game_id": {"$exists": True}}, {"_id": 0, "game_id": 1}
        )
    }
    stored_move_truth = {}
    stored_truth_records = 0
    analysis_projection = {
        "_id": 0, "game_id": 1,
        "stockfish_analysis.move_evaluations.move": 1,
        "stockfish_analysis.move_evaluations.move_uci": 1,
        "stockfish_analysis.move_evaluations.move_number": 1,
        "stockfish_analysis.move_evaluations.cp_loss": 1,
        "stockfish_analysis.move_evaluations.best_move": 1,
        "stockfish_analysis.move_evaluations.best_move_san": 1,
        "stockfish_analysis.move_evaluations.best_move_uci": 1,
        "stockfish_analysis.move_evaluations.is_user_move": 1,
        "stockfish_analysis.move_evaluations.is_opponent_move": 1,
    }
    for analysis in db.game_analyses.find({}, analysis_projection):
        game_id = str(analysis.get("game_id") or "")
        if not game_id:
            continue
        game_index = {}
        evaluations = (analysis.get("stockfish_analysis") or {}).get(
            "move_evaluations"
        ) or []
        for record in evaluations:
            if not isinstance(record, dict) or not _analysis_move_is_user(record):
                continue
            move_number = record.get("move_number")
            if move_number is None:
                continue
            truth = {
                "cp_loss": record.get("cp_loss"),
                "best_move_san": (
                    record.get("best_move_san") or record.get("best_move")
                ),
                "best_move_uci": record.get("best_move_uci"),
            }
            for token in (record.get("move_uci"), record.get("move")):
                if token:
                    game_index[(int(move_number), str(token))] = truth
            stored_truth_records += 1
        stored_move_truth[game_id] = game_index
    detectors = all_detectors()
    accepted_kwargs = {
        skill_id: {
            name
            for name in EXTRA_KWARGS
            if name in inspect.signature(detector).parameters
        }
        for skill_id, detector in detectors.items()
    }

    outcomes: Dict[str, Counter] = {skill_id: Counter() for skill_id in detectors}
    games_with_fire: Dict[str, set[str]] = defaultdict(set)
    cp_loss_values = defaultdict(lambda: defaultdict(list))
    cp_loss_missing = defaultdict(Counter)
    errors = Counter()
    opening_recognition = Counter()
    recognized_opening_keys = set()
    totals = Counter()

    cursor = db.games.find(
        {"game_id": {"$in": list(analyzed_ids)}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
    )
    for row in cursor:
        totals["source_games"] += 1
        game_id = str(row.get("game_id") or "")
        stored_truth = stored_move_truth.get(game_id, {})
        color = _user_color(row.get("user_color"))
        if color is None:
            totals["skipped_missing_user_color"] += 1
            continue
        try:
            game = chess.pgn.read_game(io.StringIO(row.get("pgn") or ""))
        except Exception:
            game = None
        if game is None:
            totals["skipped_invalid_pgn"] += 1
            continue

        board = game.board()
        moves = list(game.mainline_moves())
        full_history = []
        parse_failed = False
        for move in moves:
            try:
                full_history.append(board.san(move))
                board.push(move)
            except Exception:
                parse_failed = True
                break
        if parse_failed:
            totals["skipped_illegal_mainline"] += 1
            continue

        board = game.board()
        history = []
        opening = None
        game_opening_recognized = False
        for ply, move in enumerate(moves):
            try:
                san = board.san(move)
            except Exception:
                totals["skipped_illegal_move"] += 1
                break
            history.append(san)
            try:
                recognition_event = recognize_opening_from_history(history)
            except Exception:
                recognition_event = None
                errors["opening_recognizer"] += 1
            if recognition_event:
                opening = recognition_event
                game_opening_recognized = True
                recognized_opening_keys.add(_opening_key(recognition_event))
            if board.turn == color:
                totals["user_moves_replayed"] += 1
                move_number = ply // 2 + 1
                move_truth = stored_truth.get((move_number, move.uci()))
                if move_truth is None:
                    move_truth = stored_truth.get((move_number, san))
                move_truth = move_truth or {}
                for skill_id, detector in detectors.items():
                    kwargs = {}
                    accepted = accepted_kwargs[skill_id]
                    if "move_number" in accepted:
                        kwargs["move_number"] = move_number
                    if "opening_name" in accepted:
                        kwargs["opening_name"] = (
                            _opening_key(opening) if opening else None
                        )
                    if "move_history_san" in accepted:
                        kwargs["move_history_san"] = list(history)
                    if "best_move_san" in accepted:
                        kwargs["best_move_san"] = move_truth.get("best_move_san")
                    if "best_move_uci" in accepted:
                        kwargs["best_move_uci"] = move_truth.get("best_move_uci")
                    try:
                        verdict = detector(board, move, color, **kwargs)
                    except Exception:
                        errors[skill_id] += 1
                        continue
                    if verdict in {"applied", "missed"}:
                        outcomes[skill_id][verdict] += 1
                        games_with_fire[skill_id].add(game_id)
                        cp_loss = move_truth.get("cp_loss")
                        if cp_loss is None:
                            cp_loss_missing[skill_id][verdict] += 1
                        else:
                            cp_loss_values[skill_id][verdict].append(cp_loss)
            board.push(move)
        opening_recognition[
            "recognized" if game_opening_recognized else "unrecognized"
        ] += 1
        totals["games_replayed"] += 1

    authorizations = {}
    detector_results = {}
    for skill_id in detectors:
        quality_id = concept_quality_id(skill_id)
        authorizations[skill_id] = {
            "quality_id": quality_id,
            "grade": str(grade_for(quality_id).value),
            "mastery_authorized": bool(
                can_influence(quality_id, QualitySurface.MASTERY)
            ),
            "prompt_authorized": bool(
                can_influence(quality_id, QualitySurface.PROMPT)
            ),
        }
        detector_results[skill_id] = {
            "applied": outcomes[skill_id]["applied"],
            "missed": outcomes[skill_id]["missed"],
            "total_fires": sum(outcomes[skill_id].values()),
            "games_with_fire": len(games_with_fire[skill_id]),
            "exceptions": errors[skill_id],
            "stored_cp_loss": {
                outcome: _cp_summary(
                    cp_loss_values[skill_id][outcome],
                    cp_loss_missing[skill_id][outcome],
                )
                for outcome in ("applied", "missed")
            },
        }

    client.close()
    return {
        "_meta": {
            "snapshot_id": f"current_detector_fires_{date.today().isoformat()}",
            "database": os.environ.get("DB_NAME", "chess_coach"),
            "method": (
                "Full deterministic PGN replay through deployed concept detectors; "
                "zero Stockfish and LLM calls"
            ),
            "privacy": (
                "Aggregate counts only; no users, games, moves, FENs or PGNs emitted"
            ),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        },
        "totals": dict(totals),
        "stored_truth_index": {
            "games": len(stored_move_truth),
            "user_move_records_indexed": stored_truth_records,
        },
        "detectors": detector_results,
        "authorization": authorizations,
        "opening_recognition": {
            "recognized_games": opening_recognition["recognized"],
            "unrecognized_games": opening_recognition["unrecognized"],
            "distinct_opening_keys": len(recognized_opening_keys),
        },
        "aggregate_exceptions": dict(errors),
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, sort_keys=True))
