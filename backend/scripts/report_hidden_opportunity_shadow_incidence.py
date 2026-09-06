#!/usr/bin/env python3
"""Read-only production census for canonical Hidden Opportunity proofs.

The report contains aggregate counts only. It does not emit game/user IDs,
positions, moves, ratings, names, or captions; it performs no writes, engine
runs, or model calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

from pymongo import MongoClient


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.game_review_shadow_runtime import (  # noqa: E402
    HIDDEN_OPPORTUNITY_SHADOW_VERSION,
    HIDDEN_OPPORTUNITY_STATUSES,
    evaluate_hidden_opportunity_stored_row,
)
from services.rating_resolver import get_game_side_ratings  # noqa: E402


REPORT_VERSION = "hidden_opportunity_shadow_incidence.v1"


def _row_signature(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        " ".join(str(row.get("fen_before") or "").split()[:4]),
        str(
            row.get("move_uci")
            or row.get("move")
            or row.get("move_san")
            or row.get("played_move")
            or ""
        ),
        str(
            row.get("best_move_uci")
            or row.get("best_move")
            or row.get("best_move_san")
            or ""
        ),
    )


def build_incidence_report(
    *,
    games: Iterable[Mapping[str, Any]],
    analyses: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    games_by_id = {
        str(game.get("game_id")): game
        for game in games
        if game.get("game_id")
    }
    statuses: Counter[str] = Counter({
        status: 0 for status in HIDDEN_OPPORTUNITY_STATUSES
    })
    actors: Counter[str] = Counter()
    families: Counter[str] = Counter()
    analyses_seen = 0
    joined_games = 0
    missing_game_context = 0
    positions_seen = 0
    duplicate_positions = 0
    candidate_games = 0

    for analysis in analyses:
        analyses_seen += 1
        game_id = str(analysis.get("game_id") or "")
        game = games_by_id.get(game_id)
        if game is None:
            missing_game_context += 1
            continue
        user_color = str(game.get("user_color") or "").lower()
        if user_color not in {"white", "black"}:
            missing_game_context += 1
            continue
        joined_games += 1
        ratings = get_game_side_ratings(dict(game))
        stockfish = analysis.get("stockfish_analysis") or {}
        rows = list(stockfish.get("move_evaluations") or [])
        rows.extend(stockfish.get("opponent_move_evaluations") or [])
        seen = set()
        game_has_candidate = False
        for row in rows:
            signature = _row_signature(row)
            signature_complete = all(signature)
            if signature_complete and signature in seen:
                duplicate_positions += 1
                continue
            if signature_complete:
                seen.add(signature)
            positions_seen += 1
            result = evaluate_hidden_opportunity_stored_row(
                game_id=game_id,
                user_color=user_color,
                side_ratings=ratings,
                row=row,
            )
            status = str(result.get("status") or "invalid_stored_evidence")
            if status not in HIDDEN_OPPORTUNITY_STATUSES:
                status = "invalid_stored_evidence"
            statuses[status] += 1
            if status != "candidate":
                continue
            game_has_candidate = True
            candidate = result["candidate"]
            actors[str(candidate["selection_features"]["actor"])] += 1
            families[str(candidate["proof"]["family"])] += 1
        candidate_games += int(game_has_candidate)

    candidate_count = statuses["candidate"]
    above_threshold = (
        candidate_count
        + statuses["not_proved"]
        + statuses["invalid_stored_evidence"]
    )
    return {
        "schema_version": REPORT_VERSION,
        "shadow_runtime_version": HIDDEN_OPPORTUNITY_SHADOW_VERSION,
        "read_only": True,
        "database_writes": 0,
        "stockfish_runs": 0,
        "model_calls": 0,
        "coverage": {
            "analysis_records_seen": analyses_seen,
            "joined_games": joined_games,
            "missing_game_context": missing_game_context,
            "positions_seen": positions_seen,
            "duplicate_positions_skipped": duplicate_positions,
            "above_threshold_positions": above_threshold,
            "candidate_count": candidate_count,
            "candidate_games": candidate_games,
            "status_counts": dict(sorted(statuses.items())),
            "candidate_actor_counts": dict(sorted(actors.items())),
            "candidate_family_counts": dict(sorted(families.items())),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional analysis-record limit for a smoke run; 0 scans all.",
    )
    args = parser.parse_args()
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=15000)
    try:
        database = client[os.environ.get("DB_NAME", "chess_coach")]
        game_rows = list(database.games.find({}, {
            "_id": 0,
            "game_id": 1,
            "user_color": 1,
            "white_rating": 1,
            "black_rating": 1,
            "white.rating": 1,
            "black.rating": 1,
            "pgn": 1,
        }))
        cursor = database.game_analyses.find(
            {"stockfish_analysis": {"$exists": True}},
            {
                "_id": 0,
                "game_id": 1,
                "stockfish_analysis.move_evaluations": 1,
                "stockfish_analysis.opponent_move_evaluations": 1,
            },
        )
        if args.limit > 0:
            cursor = cursor.limit(args.limit)
        report = build_incidence_report(
            games=game_rows,
            analyses=cursor,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
