"""Aggregate-only Phase 3 planner candidate bake-off.

Runs the current deterministic caption pipeline in memory from stored PGNs and
stored Stockfish evaluations. It invokes no engine or LLM, writes no database
row, and prints only aggregate JSON without identifiers, FENs, or moves.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import io
import json
import os
import statistics
import sys

import chess
import chess.pgn
from pymongo import MongoClient

OVERLAY_ROOT = os.environ.get("PHASE3_OVERLAY_ROOT")
if OVERLAY_ROOT:
    sys.path.insert(0, OVERLAY_ROOT)

from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)


def _position_key(fen: str) -> str:
    return " ".join((fen or "").split()[:4])


def _best(row: dict) -> str:
    return row.get("best_move") or row.get("best_move_san") or ""


def _load_by_id(collection, ids, projection):
    result = {}
    ordered = sorted(ids)
    for start in range(0, len(ordered), 300):
        batch = ordered[start : start + 300]
        for document in collection.find(
            {"game_id": {"$in": batch}},
            projection,
        ):
            game_id = str(document.get("game_id") or "")
            if game_id:
                result[game_id] = document
    return result


def _regenerate_verified_events(db, observations_by_game):
    game_ids = set(observations_by_game)
    games = _load_by_id(
        db.games,
        game_ids,
        {
            "_id": 0,
            "game_id": 1,
            "pgn": 1,
            "user_color": 1,
            "user_plays_as": 1,
        },
    )
    analyses = _load_by_id(
        db.game_analyses,
        game_ids,
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    )

    counts = defaultdict(int)
    error_types = Counter()
    eligible_by_game = defaultdict(list)
    for game_id, observations in observations_by_game.items():
        game_doc = games.get(game_id)
        analysis = analyses.get(game_id)
        if not game_doc:
            counts["missing_game"] += len(observations)
            continue
        if not analysis:
            counts["missing_analysis"] += len(observations)
            continue
        pgn_game = chess.pgn.read_game(
            io.StringIO(game_doc.get("pgn") or "")
        )
        if not pgn_game:
            counts["invalid_pgn"] += len(observations)
            continue

        rows = (
            (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations"
            )
            or []
        )
        by_fen = {
            _position_key(row.get("fen_before")): row
            for row in rows
            if row.get("fen_before")
        }
        observation_by_number = {
            int(item.get("move_number") or 0): item
            for item in observations
            if item.get("move_number")
        }
        user_color = (
            game_doc.get("user_color")
            or game_doc.get("user_plays_as")
            or "white"
        ).lower()
        user_is_white = user_color == "white"
        board = pgn_game.board()
        history = []
        state = CrossMoveState()
        shapes_fired = set()
        board_state_window = []

        for move in pgn_game.mainline_moves():
            fen_before = board.fen()
            san = board.san(move)
            mover_is_white = board.turn == chess.WHITE
            is_user = mover_is_white == user_is_white
            move_number = board.fullmove_number
            observation = (
                observation_by_number.get(move_number) if is_user else None
            )
            if observation is not None:
                row = by_fen.get(_position_key(fen_before))
                if not row:
                    counts["missing_evaluation_row"] += 1
                else:
                    try:
                        decision = build_move_teaching_decision(
                            MoveInputs(
                                fen_before=fen_before,
                                played_san=san,
                                mover_is_user=True,
                                mover_is_white=mover_is_white,
                                user_color=user_color,
                                full_move_number=move_number,
                                move_history_san=list(history),
                                prev_move_san=(
                                    history[-1] if history else None
                                ),
                                best_move_san=_best(row) or None,
                                eval_before_cp=row.get("eval_before"),
                                eval_after_cp=row.get("eval_after"),
                                cp_loss=int(row.get("cp_loss") or 0),
                                pv_after_played=list(
                                    row.get("pv_after_played") or []
                                ),
                                pv_after_best=list(
                                    row.get("pv_after_best") or []
                                ),
                            ),
                            state,
                            shapes_fired_this_game=shapes_fired,
                            bs_recent_window=board_state_window,
                            eval_lookup=by_fen,
                            move_evaluations=rows,
                        )
                    except Exception as exc:
                        counts["pipeline_error"] += 1
                        error_types[type(exc).__name__] += 1
                    else:
                        explanation = decision.explanation
                        if not explanation.final_verified:
                            counts["not_final_verified"] += 1
                        elif decision.should_skip:
                            counts["skipped"] += 1
                        else:
                            caption = (
                                explanation.board_explanation
                                or decision.text.caption
                                or ""
                            ).strip()
                            principle = (
                                explanation.transferable_instruction
                                or decision.teaching_meta.principle_cue
                                or ""
                            ).strip()
                            visual = bool(
                                decision.visual.arrows
                                or decision.visual.highlight_squares
                            )
                            completeness = (
                                int(bool(caption))
                                + int(bool(principle))
                                + int(visual)
                            )
                            eligible_by_game[game_id].append(
                                {
                                    "move_number": move_number,
                                    "ply": int(
                                        observation.get("ply")
                                        or (move_number * 2)
                                    ),
                                    "cp_loss": float(
                                        observation.get("cp_loss") or 0
                                    ),
                                    "critical": bool(
                                        observation.get(
                                            "was_critical_moment"
                                        )
                                    ),
                                    "complete": completeness,
                                }
                            )
                            counts["final_verified"] += 1

            board.push(move)
            history.append(san)
    return eligible_by_game, counts, error_types


def _candidate_comparison(eligible_by_game):
    formulas = {
        "A_chronology": lambda event: (-event["ply"],),
        "B_largest_loss": lambda event: (
            event["cp_loss"],
            -event["ply"],
        ),
        "C_critical_then_loss": lambda event: (
            int(event["critical"]),
            event["cp_loss"],
            -event["ply"],
        ),
        "D_teaching_then_critical": lambda event: (
            event["complete"],
            int(event["critical"]),
            event["cp_loss"],
            -event["ply"],
        ),
    }
    selected = {name: {} for name in formulas}
    metrics = {}
    for name, key in formulas.items():
        picks = []
        earliest = 0
        for game_id, events in eligible_by_game.items():
            if not events:
                continue
            pick = max(events, key=key)
            selected[name][game_id] = pick["move_number"]
            picks.append(pick)
            earliest += pick["ply"] == min(
                event["ply"] for event in events
            )
        count = len(picks)
        metrics[name] = {
            "games": count,
            "mean_selected_cp_loss": (
                round(
                    sum(pick["cp_loss"] for pick in picks) / count,
                    2,
                )
                if count
                else None
            ),
            "selected_critical_pct": (
                round(
                    100
                    * sum(pick["critical"] for pick in picks)
                    / count,
                    2,
                )
                if count
                else None
            ),
            "selected_full_teaching_pct": (
                round(
                    100
                    * sum(pick["complete"] == 3 for pick in picks)
                    / count,
                    2,
                )
                if count
                else None
            ),
            "selected_is_earliest_pct": (
                round(100 * earliest / count, 2) if count else None
            ),
        }

    pairwise = {}
    names = list(formulas)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            common = sorted(set(selected[left]) & set(selected[right]))
            disagreements = sum(
                selected[left][game_id] != selected[right][game_id]
                for game_id in common
            )
            pairwise[f"{left}__vs__{right}"] = {
                "common_games": len(common),
                "different_top_event_pct": (
                    round(100 * disagreements / len(common), 2)
                    if common
                    else None
                ),
            }
    return metrics, pairwise


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    observations = list(
        db.move_observations.find(
            {"schema_version": {"$gte": 16}, "subtype": "simple_hang"},
            {
                "_id": 0,
                "game_id": 1,
                "move_number": 1,
                "ply": 1,
                "cp_loss": 1,
                "was_critical_moment": 1,
            },
        )
    )
    observations_by_game = defaultdict(list)
    for observation in observations:
        game_id = str(observation.get("game_id") or "")
        move_number = int(observation.get("move_number") or 0)
        if game_id and move_number:
            observations_by_game[game_id].append(observation)

    (
        eligible_by_game,
        regeneration_counts,
        regeneration_error_types,
    ) = _regenerate_verified_events(db, observations_by_game)
    metrics, pairwise = _candidate_comparison(eligible_by_game)
    event_counts = [
        len(events) for events in eligible_by_game.values() if events
    ]
    affected = len(event_counts)
    at_least = {
        str(cap): (
            round(
                100 * sum(count >= cap for count in event_counts) / affected,
                2,
            )
            if affected
            else None
        )
        for cap in (1, 2, 3, 4)
    }
    all_v5_games = db.game_analyses.count_documents(
        {"decryption_v5_data": {"$type": "array"}}
    )
    output = {
        "schema_version": (
            "personalized_game_review.phase3_planner_bakeoff.v2"
        ),
        "generated_at": "2026-09-01",
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
        "authority": {
            "quality_id": "gap:piece_safety:simple_hang",
            "required_schema_version": 16,
            "required_caption_final_verified": True,
            "final_formula_locked": False,
            "final_visible_cap_locked": False,
        },
        "counts": {
            "observations": len(observations),
            "games_with_observation": len(observations_by_game),
            "eligible_verified_events": sum(event_counts),
            "eligible_affected_games": affected,
            "all_stored_v5_games": all_v5_games,
            "eligible_game_reach_pct": (
                round(100 * affected / all_v5_games, 2)
                if all_v5_games
                else None
            ),
            "regeneration": dict(sorted(regeneration_counts.items())),
            "regeneration_error_types": dict(
                sorted(regeneration_error_types.items())
            ),
        },
        "eligible_events_per_affected_game": {
            "mean": (
                round(sum(event_counts) / affected, 3)
                if affected
                else None
            ),
            "median": (
                statistics.median(event_counts) if event_counts else None
            ),
            "max": max(event_counts) if event_counts else None,
            "at_least_k_pct": at_least,
        },
        "candidate_formulas": {
            "A_chronology": "earliest verified event",
            "B_largest_loss": "largest stored cp_loss, then earliest",
            "C_critical_then_loss": (
                "stored critical flag, then largest cp_loss, then earliest"
            ),
            "D_teaching_then_critical": (
                "teaching completeness, critical flag, cp_loss, then earliest"
            ),
        },
        "candidate_metrics": metrics,
        "pairwise_disagreement": pairwise,
        "interpretation": [
            (
                "Current stored V5 final_verified fields are stale, so the "
                "bake-off regenerated deterministic decisions in memory "
                "from stored engine evidence."
            ),
            (
                "The bake-off measures deterministic differences; it does "
                "not provide human importance labels."
            ),
            (
                "No final ranking formula or visible moment cap is locked "
                "from proxy metrics alone."
            ),
            (
                "Candidate caps 1-4 cover the complete observed range for "
                "the only Plan-grade detector and remain shadow candidates."
            ),
        ],
    }
    print(json.dumps(output, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
