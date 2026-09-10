"""Bounded candidate-caption enrichment for one explicitly chosen account.

The command is a dry run unless ``--apply`` is supplied.  Apply additionally
requires the exact scope fingerprint printed by a prior dry run.  It never
runs a full-game analysis, invokes an LLM, or calls a human-policy model: it
reuses stored game analysis and optional stored Maia/Otter evidence, then runs
one restricted Stockfish root search for missing candidates at each of at
most three selected moments per game.

Examples (inside the backend container):

  python scripts/backfill_candidate_caption_evidence.py --user-id user_123
  python scripts/backfill_candidate_caption_evidence.py \
      --user-id user_123 --apply --confirm-plan <dry-run-plan-fingerprint>
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import chess.engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.candidate_caption_evidence import (  # noqa: E402
    MOMENT_CAP,
    candidate_packet_state,
    collect_candidate_evidence,
    fingerprint,
)
from services.game_decryption_v5_service import (  # noqa: E402
    V5_COACHING_VERSION,
    generate_game_decryption_v5,
)
from stockfish_service import DEFAULT_DEPTH, StockfishEngine  # noqa: E402


MAX_GAMES = 10


def _opaque(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _json_size(value: Mapping[str, Any]) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _candidate_projection(moves: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "evidence_fingerprint": (row.get("candidate_caption_evidence") or {}).get(
                "fingerprint"
            ),
        }
        for index, row in enumerate(moves)
        if row.get("candidate_caption_evidence")
    ]


def _comparison_projection(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "move_number": row.get("move_number"),
            "source_fingerprint": (row.get("candidate_comparison") or {}).get(
                "source_fingerprint"
            ),
            "evidence_fingerprint": (row.get("candidate_comparison") or {}).get(
                "evidence_fingerprint"
            ),
            "cause_fingerprint": (row.get("candidate_comparison") or {}).get(
                "cause_fingerprint"
            ),
        }
        for row in rows
        if row.get("candidate_comparison")
    ]


def _update_guard(analysis: Mapping[str, Any], changed_indexes: list[int]) -> dict:
    guard: dict[str, Any] = {"_id": analysis["_id"]}
    if "decryption_v5_version" in analysis:
        guard["decryption_v5_version"] = analysis.get("decryption_v5_version")
    else:
        guard["decryption_v5_version"] = {"$exists": False}
    original = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    for index in changed_indexes:
        row = original[index]
        prefix = f"stockfish_analysis.move_evaluations.{index}"
        guard[f"{prefix}.fen_before"] = row.get("fen_before")
        guard[f"{prefix}.move_uci"] = row.get("move_uci")
        guard[f"{prefix}.cp_loss"] = row.get("cp_loss")
    return guard


async def build_plan(db, *, user_id: str, limit_games: int):
    user = await db.users.find_one({"user_id": user_id}, {"_id": 1})
    if not user:
        raise RuntimeError("No user matched the supplied user_id")

    engine: StockfishEngine | None = None
    engine_calls: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    scanned = 0
    try:
        cursor = db.game_analyses.find(
            {
                "user_id": user_id,
                "stockfish_analysis.move_evaluations.0": {"$exists": True},
            }
        ).sort("analyzed_at", -1)
        async for analysis in cursor:
            if len(pending) >= limit_games:
                break
            scanned += 1
            game_id = str(analysis.get("game_id") or "")
            game = await db.games.find_one(
                {"game_id": game_id, "user_id": user_id},
                {"_id": 0, "pgn": 1, "user_color": 1, "user_plays_as": 1},
            )
            if not game or not game.get("pgn"):
                continue

            original_moves = (
                (analysis.get("stockfish_analysis") or {}).get("move_evaluations")
                or []
            )
            working_moves = copy.deepcopy(original_moves)
            plan_output: dict[str, Any] = {}

            def candidate_builder(row):
                nonlocal engine
                if engine is None:
                    engine = StockfishEngine()
                    engine.start()
                engine_id = dict(engine.engine.id or {})
                started = time.perf_counter()
                packet, stats = collect_candidate_evidence(
                    row,
                    engine=engine.engine,
                    limit=chess.engine.Limit(depth=int(DEFAULT_DEPTH)),
                    engine_identity={
                        "name": str(engine_id.get("name") or "Stockfish"),
                        "author": str(engine_id.get("author") or "unknown"),
                        "analysis_depth": int(DEFAULT_DEPTH),
                    },
                )
                engine_calls.append({
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "stored_bytes": _json_size(packet.document()),
                    **stats,
                })
                return packet, stats

            rendered = await generate_game_decryption_v5(
                str(game["pgn"]),
                str(game.get("user_color") or game.get("user_plays_as") or "white"),
                working_moves,
                user_id,
                db,
                game_id=game_id,
                opponent_move_evaluations=(
                    (analysis.get("stockfish_analysis") or {}).get(
                        "opponent_move_evaluations"
                    )
                    or []
                ),
                game_teaching_plan_output=plan_output,
                persist_learning_side_effects=False,
                allow_llm_polish=False,
                candidate_evidence_builder=candidate_builder,
            )
            enrichment = plan_output.get("candidate_enrichment") or {}
            if int(enrichment.get("composed") or 0) <= 0:
                continue
            if int(enrichment.get("selected") or 0) > MOMENT_CAP:
                raise RuntimeError("selected moment count exceeds the locked cap")
            if len(_comparison_projection(rendered)) > MOMENT_CAP:
                raise RuntimeError("rendered comparison count exceeds the locked cap")

            changed_indexes = [
                index
                for index, (before, after) in enumerate(zip(original_moves, working_moves))
                if before.get("candidate_caption_evidence")
                != after.get("candidate_caption_evidence")
            ]
            states = {
                str(index): candidate_packet_state(
                    original_moves[index].get("candidate_caption_evidence"),
                    original_moves[index],
                )
                for index in changed_indexes
            }

            # A second stored-only render must reproduce the same selected
            # comparisons without starting an engine or model.
            rerun_plan: dict[str, Any] = {}
            rerun_moves = copy.deepcopy(working_moves)
            rerendered = await generate_game_decryption_v5(
                str(game["pgn"]),
                str(game.get("user_color") or game.get("user_plays_as") or "white"),
                rerun_moves,
                user_id,
                db,
                game_id=game_id,
                opponent_move_evaluations=(
                    (analysis.get("stockfish_analysis") or {}).get(
                        "opponent_move_evaluations"
                    )
                    or []
                ),
                game_teaching_plan_output=rerun_plan,
                persist_learning_side_effects=False,
                allow_llm_polish=False,
                candidate_evidence_builder=None,
            )
            deterministic = bool(
                _candidate_projection(working_moves) == _candidate_projection(rerun_moves)
                and _comparison_projection(rendered)
                == _comparison_projection(rerendered)
                and plan_output.get("selected_event_ids")
                == rerun_plan.get("selected_event_ids")
            )
            if not deterministic:
                raise RuntimeError("stored-only rerun was not deterministic")

            set_fields = {
                f"stockfish_analysis.move_evaluations.{index}.candidate_caption_evidence":
                    working_moves[index]["candidate_caption_evidence"]
                for index in changed_indexes
            }
            set_fields.update({
                "decryption_v5_data": rendered,
                "decryption_v5_version": V5_COACHING_VERSION,
                "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
                "game_teaching_plan": plan_output,
            })
            candidate_sources = sorted(
                str(item["source_fingerprint"])
                for item in _comparison_projection(rendered)
                if item.get("source_fingerprint")
            )
            pending.append({
                "analysis": analysis,
                "guard": _update_guard(analysis, changed_indexes),
                "set_fields": set_fields,
                "public": {
                    "game_ref": _opaque(game_id),
                    "selected": int(enrichment.get("selected") or 0),
                    "composed": int(enrichment.get("composed") or 0),
                    "comparisons": len(_comparison_projection(rendered)),
                    "changed_rows": len(changed_indexes),
                    "prior_states": states,
                    "candidate_sources": candidate_sources,
                    "deterministic_rerun": deterministic,
                    "enrichment": enrichment,
                },
            })
    finally:
        if engine is not None:
            engine.stop()

    scope = {
        "schema_version": "candidate_caption_backfill_plan.v1",
        "user_ref": _opaque(user_id),
        "limit_games": limit_games,
        "games": [
            {
                "game_ref": item["public"]["game_ref"],
                "candidate_sources": item["public"]["candidate_sources"],
            }
            for item in pending
        ],
    }
    return {
        "scope": scope,
        "plan_fingerprint": fingerprint(scope),
        "scanned_analyses": scanned,
        "pending": pending,
        "engine_calls": engine_calls,
    }


async def run(args) -> dict[str, Any]:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        plan = await build_plan(
            db,
            user_id=args.user_id,
            limit_games=args.limit_games,
        )
        if args.apply and args.confirm_plan != plan["plan_fingerprint"]:
            raise RuntimeError(
                "Database scope changed or confirm-plan does not match the dry run"
            )
        applied = 0
        if args.apply:
            for item in plan["pending"]:
                result = await db.game_analyses.update_one(
                    item["guard"],
                    {"$set": item["set_fields"]},
                )
                if result.modified_count != 1:
                    raise RuntimeError(
                        "Concurrent analysis change blocked a candidate-caption write"
                    )
                applied += 1

        calls = plan["engine_calls"]
        elapsed = sorted(call["elapsed_ms"] for call in calls)
        report = {
            "schema_version": "candidate_caption_backfill_report.v1",
            "mode": "apply" if args.apply else "dry_run",
            "user_ref": plan["scope"]["user_ref"],
            "plan_fingerprint": plan["plan_fingerprint"],
            "scanned_analyses": plan["scanned_analyses"],
            "eligible_games": len(plan["pending"]),
            "applied_games": applied,
            "engine": {
                "calls": len(calls),
                "elapsed_ms_total": round(sum(elapsed), 3),
                "elapsed_ms_p50": elapsed[len(elapsed) // 2] if elapsed else 0,
                "elapsed_ms_p95": elapsed[min(len(elapsed) - 1, int(len(elapsed) * 0.95))]
                    if elapsed else 0,
                "stored_bytes_total": sum(call["stored_bytes"] for call in calls),
            },
            "games": [item["public"] for item in plan["pending"]],
        }
        return report
    finally:
        client.close()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--limit-games", type=int, default=MAX_GAMES)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-plan")
    args = parser.parse_args()
    if not 1 <= args.limit_games <= MAX_GAMES:
        parser.error(f"--limit-games must be within 1..{MAX_GAMES}")
    if args.apply and not args.confirm_plan:
        parser.error("--apply requires --confirm-plan from a prior dry run")
    return args


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(parse_args())), indent=2, sort_keys=True))
