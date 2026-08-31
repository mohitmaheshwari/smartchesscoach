"""Aggregate corpus measurement for the verified puzzle detector engine.

Read-only by design. The script consumes stored MongoDB analysis and validates
board syntax with python-chess. It never invokes Stockfish and never emits a
user ID, game ID, move, FEN, PGN, free-form caption, or credential.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, Iterable, Mapping, Optional

import chess
from pymongo import MongoClient


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _first(document: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = document.get(key)
        if _present(value):
            return value
    return None


def _counter(counter: Counter) -> Dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common()}


def _parse_move(board: chess.Board, raw: Any) -> Optional[chess.Move]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = raw.strip()
    try:
        move = chess.Move.from_uci(token)
        return move if move in board.legal_moves else None
    except ValueError:
        pass
    try:
        return board.parse_san(token)
    except ValueError:
        return None


def _pool_measurement(collection, game_ids_with_pgn: set[str]) -> Dict[str, Any]:
    approval = Counter()
    labels = Counter()
    sources = Counter()
    field_counts = Counter()
    positions: Dict[str, Counter] = defaultdict(Counter)
    total = 0

    projection = {
        "_id": 0, "fen": 1, "best_move": 1, "best_move_san": 1,
        "best_move_uci": 1, "expected_move": 1, "correct_move": 1,
        "played_move": 1, "user_move": 1, "move": 1, "game_id": 1,
        "source_game_id": 1, "session_id": 1, "approved": 1, "issue_type": 1,
        "pattern_type": 1, "skill_id": 1, "source": 1, "source_type": 1,
    }
    for row in collection.find({}, projection):
        total += 1
        if "approved" not in row:
            approval["missing"] += 1
        else:
            approval[str(bool(row.get("approved"))).lower()] += 1

        label = _first(row, ("skill_id", "issue_type", "pattern_type"))
        labels[str(label) if _present(label) else "missing"] += 1
        source = _first(row, ("source_type", "source"))
        sources[str(source) if _present(source) else "missing"] += 1

        fen = row.get("fen")
        answer = _first(row, (
            "best_move_uci", "best_move_san", "best_move",
            "expected_move", "correct_move",
        ))
        played = _first(row, ("played_move", "user_move", "move"))
        source_game_id = _first(row, ("source_game_id", "game_id"))

        if _present(fen):
            field_counts["with_fen"] += 1
        if _present(answer):
            field_counts["with_answer"] += 1
        if _present(played):
            field_counts["with_played_move"] += 1
        if _present(source_game_id):
            field_counts["with_source_game_id"] += 1
            if str(source_game_id) in game_ids_with_pgn:
                field_counts["source_game_with_pgn"] += 1
        if _present(row.get("session_id")):
            field_counts["with_source_session_id"] += 1

        if not _present(fen):
            continue
        try:
            board = chess.Board(str(fen))
            field_counts["valid_fen"] += 1
        except (ValueError, TypeError):
            field_counts["invalid_fen"] += 1
            continue

        if _present(answer):
            if _parse_move(board, answer) is not None:
                field_counts["legal_answer"] += 1
            else:
                field_counts["unparseable_or_illegal_answer"] += 1
            positions[str(fen)][str(answer)] += 1

    duplicate_same_answer_rows = 0
    conflicting_answer_positions = 0
    repeated_positions = 0
    for answer_counts in positions.values():
        count = sum(answer_counts.values())
        if count > 1:
            repeated_positions += 1
            duplicate_same_answer_rows += sum(max(0, n - 1) for n in answer_counts.values())
        if len(answer_counts) > 1:
            conflicting_answer_positions += 1

    return {
        "total": total,
        "approval": _counter(approval),
        "labels": _counter(labels),
        "sources": _counter(sources),
        "field_coverage": _counter(field_counts),
        "repeated_positions": repeated_positions,
        "duplicate_same_answer_rows": duplicate_same_answer_rows,
        "conflicting_answer_positions": conflicting_answer_positions,
    }


def _analysis_measurement(db, game_ids_with_pgn: set[str]) -> Dict[str, Any]:
    docs = 0
    docs_with_moves = 0
    docs_linked_to_pgn = 0
    moves_total = 0
    user_moves = 0
    fields = Counter()
    versions = Counter()
    gap_counts = Counter()
    move_field_presence = Counter()
    move_role_flags = Counter()

    projection = {
        "_id": 0, "game_id": 1, "analysis_version": 1, "version": 1,
        "stockfish_analysis.version": 1,
        "stockfish_analysis.analysis_version": 1,
        "stockfish_analysis.move_evaluations": 1,
    }
    for analysis in db.game_analyses.find({}, projection):
        docs += 1
        game_id = analysis.get("game_id")
        if _present(game_id) and str(game_id) in game_ids_with_pgn:
            docs_linked_to_pgn += 1
        sf = analysis.get("stockfish_analysis") or {}
        version = _first(analysis, ("analysis_version", "version"))
        if version is None:
            version = _first(sf, ("analysis_version", "version"))
        versions[str(version) if _present(version) else "missing"] += 1
        evaluations = sf.get("move_evaluations") or []
        if evaluations:
            docs_with_moves += 1
        for move in evaluations:
            if not isinstance(move, Mapping):
                continue
            move_field_presence.update(move.keys())
            moves_total += 1
            if "is_user_move" in move:
                is_user = bool(move.get("is_user_move"))
                move_role_flags[f"is_user_move_{str(is_user).lower()}"] += 1
            elif "is_opponent_move" in move:
                is_opponent = bool(move.get("is_opponent_move"))
                is_user = not is_opponent
                move_role_flags[
                    f"is_opponent_move_{str(is_opponent).lower()}"
                ] += 1
            else:
                # Legacy analysis documents stored only the player's moves.
                is_user = True
                move_role_flags["legacy_implicit_user"] += 1
            if is_user:
                user_moves += 1
            prefix = "user_" if is_user else "all_"
            checks = {
                "played_move": _first(move, ("move_uci", "move_san", "move", "played_move")),
                "best_move": _first(move, ("best_move_uci", "best_move_san", "best_move")),
                "fen": _first(move, ("fen_before", "fen", "position")),
                "pv_after_best": _first(move, (
                    "pv_after_best", "pv", "principal_variation", "best_line"
                )),
                "pv_after_played": move.get("pv_after_played"),
                "cp_loss": move.get("cp_loss"),
                "move_index": _first(move, ("ply", "ply_index", "move_number")),
                "evaluation": _first(move, ("evaluation", "eval_before", "eval_after", "score")),
                "cognitive_gap": move.get("cognitive_gap"),
            }
            for name, value in checks.items():
                if _present(value) or (name == "cp_loss" and value == 0):
                    fields[f"all_{name}"] += 1
                    if is_user:
                        fields[f"user_{name}"] += 1
            if is_user:
                gap = move.get("cognitive_gap")
                gap_counts[str(gap) if _present(gap) else "missing"] += 1

    return {
        "documents": docs,
        "documents_with_move_evaluations": docs_with_moves,
        "documents_linked_to_source_pgn": docs_linked_to_pgn,
        "analysis_versions": _counter(versions),
        "move_evaluations": moves_total,
        "user_move_evaluations": user_moves,
        "field_coverage": _counter(fields),
        "move_field_presence": _counter(move_field_presence),
        "move_role_flags": _counter(move_role_flags),
        "user_cognitive_gap": _counter(gap_counts),
    }


def _observation_measurement(db) -> Dict[str, Any]:
    total = 0
    schemas = Counter()
    missed_patterns = Counter()
    subtypes = Counter()
    executed = Counter()
    fields = Counter()
    projection = {
        "_id": 0, "schema_version": 1, "missed_pattern": 1, "subtype": 1,
        "tactical_pattern_executed": 1, "fen_before": 1, "fen_after": 1,
        "move_san": 1, "best_move": 1, "cp_loss": 1, "game_id": 1,
        "user_id": 1,
    }
    for row in db.move_observations.find({"schema_version": {"$gte": 16}}, projection):
        total += 1
        schemas[str(row.get("schema_version", "missing"))] += 1
        missed = row.get("missed_pattern")
        subtype = row.get("subtype")
        applied = row.get("tactical_pattern_executed")
        if _present(missed):
            missed_patterns[str(missed)] += 1
        if _present(subtype):
            subtypes[str(subtype)] += 1
        if _present(applied):
            executed[str(applied)] += 1
        for field in (
            "fen_before", "fen_after", "move_san", "best_move",
            "cp_loss", "game_id", "user_id",
        ):
            value = row.get(field)
            if _present(value) or (field == "cp_loss" and value == 0):
                fields[field] += 1
    return {
        "total": total,
        "schema_versions": _counter(schemas),
        "missed_patterns": _counter(missed_patterns),
        "named_subtypes": _counter(subtypes),
        "applied_tactical_patterns": _counter(executed),
        "field_coverage": _counter(fields),
    }


def measure() -> Dict[str, Any]:
    mongo_url = os.environ["MONGO_URL"]
    database_name = os.environ.get("DB_NAME", "chess_coach")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10_000)
    db = client[database_name]

    game_ids_with_pgn = {
        str(row["game_id"])
        for row in db.games.find(
            {"game_id": {"$exists": True}, "pgn": {"$type": "string", "$ne": ""}},
            {"_id": 0, "game_id": 1},
        )
    }

    report = {
        "_meta": {
            "snapshot_id": f"verified_puzzle_detector_corpus_{date.today().isoformat()}",
            "database": database_name,
            "method": (
                "Read-only full aggregate over stored analysis and puzzle pools; "
                "python-chess syntax/legality checks only; zero Stockfish calls"
            ),
            "privacy": (
                "No user IDs, game IDs, moves, FENs, PGNs, captions, free-form "
                "text, connection strings, or credentials are emitted."
            ),
        },
        "source_counts": {
            "games": db.games.count_documents({}),
            "games_with_pgn": len(game_ids_with_pgn),
            "game_analyses": db.game_analyses.count_documents({}),
            "move_observations": db.move_observations.count_documents({}),
        },
        "stored_analysis": _analysis_measurement(db, game_ids_with_pgn),
        "move_observations_v16plus": _observation_measurement(db),
        "puzzle_pools": {
            "community_puzzles": _pool_measurement(
                db.community_puzzles, game_ids_with_pgn
            ),
            "community_training_positions": _pool_measurement(
                db.community_training_positions, game_ids_with_pgn
            ),
        },
    }
    client.close()
    return report



if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, sort_keys=True))
