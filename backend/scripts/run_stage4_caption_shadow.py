"""Read-only Stage 4 causal/personal caption shadow audit.

Uses stored PGNs and stored Stockfish move evaluations.  It never invokes an
engine, writes MongoDB, or exports caption/user text.  Output is aggregate JSON.

Run inside the backend environment:
  python scripts/run_stage4_caption_shadow.py --email user@example.com --games 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DEPLOYED_BACKEND = Path("/app/backend")
if DEPLOYED_BACKEND.exists() and str(DEPLOYED_BACKEND) not in sys.path:
    # Temporary-overlay audits take the two Stage 4 modules from BACKEND and
    # resolve every unchanged dependency from the deployed read-only tree.
    sys.path.append(str(DEPLOYED_BACKEND))

from services.caption_pipeline import CrossMoveState, MoveInputs, build_move_teaching_decision
from services.coach_conductor import load_player_caption_context


GENERIC_SHELLS = (
    re.compile(r"\bwas (?:the )?(?:better|stronger) move(?: here)?\.", re.I),
    re.compile(r"\bwould have made things harder for your opponent\.", re.I),
)


def _is_generic(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in GENERIC_SHELLS)


def _san(row: dict) -> str:
    return row.get("move") or row.get("move_san") or row.get("san") or ""


def _best(row: dict) -> str:
    return row.get("best_move") or row.get("best_move_san") or ""


async def run(email: str, game_limit: int) -> dict:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if not user:
        raise SystemExit("user not found")
    user_id = user["user_id"]
    context = await load_player_caption_context(db, user_id)

    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1},
    ).sort("imported_at", -1).limit(game_limit).to_list(length=game_limit)

    counts = Counter()
    sources = Counter()
    kinds = Counter()
    rules = Counter()
    tiers = Counter()
    reasons = Counter()
    per_game_connections = []

    for game_doc in games:
        analysis = await db.game_analyses.find_one(
            {"game_id": game_doc.get("game_id")},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1},
        ) or {}
        rows = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {
            " ".join((row.get("fen_before") or "").split()[:4]): row
            for row in rows if row.get("fen_before")
        }
        pgn_game = chess.pgn.read_game(__import__("io").StringIO(game_doc.get("pgn") or ""))
        if not pgn_game:
            continue

        user_color = (game_doc.get("user_color") or "white").lower()
        user_is_white = user_color == "white"
        board = pgn_game.board()
        history = []
        state = CrossMoveState()
        shapes_fired = set()
        board_state_window = []
        game_connections = 0

        for move in pgn_game.mainline_moves():
            fen_before = board.fen()
            san = board.san(move)
            mover_is_white = board.turn == chess.WHITE
            is_user = mover_is_white == user_is_white
            row = by_fen.get(" ".join(fen_before.split()[:4])) or {}
            if is_user and row:
                cp_loss = int(row.get("cp_loss") or 0)
                if cp_loss >= 30:
                    counts["eligible_moves"] += 1
                    inputs = MoveInputs(
                        fen_before=fen_before,
                        played_san=san,
                        mover_is_user=True,
                        mover_is_white=mover_is_white,
                        user_color=user_color,
                        full_move_number=board.fullmove_number,
                        move_history_san=list(history),
                        prev_move_san=(history[-1] if history else None),
                        best_move_san=_best(row) or None,
                        eval_before_cp=row.get("eval_before"),
                        eval_after_cp=row.get("eval_after"),
                        cp_loss=cp_loss,
                        pv_after_played=list(row.get("pv_after_played") or []),
                        pv_after_best=list(row.get("pv_after_best") or []),
                        player_motif_threads=context.get("player_motif_threads"),
                        player_opening_threads=context.get("player_opening_threads"),
                        player_concept_threads=context.get("player_concept_threads"),
                        strong_openings=context.get("strong_openings") or set(),
                        player_identity=context.get("player_identity"),
                        session_focus=context.get("session_focus"),
                        player_context_shadow_only=True,
                    )
                    decision = build_move_teaching_decision(
                        inputs,
                        state,
                        shapes_fired_this_game=shapes_fired,
                        bs_recent_window=board_state_window,
                        eval_lookup=by_fen,
                        move_evaluations=rows,
                    )
                    explanation = decision.explanation
                    rules[decision.text.rule_name] += 1
                    tiers[decision.teaching_meta.caption_tier] += 1
                    primary = (decision.debug_facts.get("primary_reason") or {})
                    if isinstance(primary, dict):
                        reasons[str(primary.get("category") or "unknown")] += 1
                    _has_best_purpose = bool(decision.debug_facts.get("best_move_why"))
                    if _has_best_purpose:
                        counts["has_best_move_purpose_fact"] += 1
                    if decision.teaching_meta.principle_id_used:
                        counts["has_principle_id"] += 1
                    if explanation.final_verified:
                        counts["final_verified"] += 1
                    if explanation.board_explanation:
                        counts["has_board_explanation"] += 1
                    if explanation.transferable_instruction:
                        counts["has_transferable_instruction"] += 1
                    if _is_generic(explanation.board_explanation):
                        counts["generic_recommendation_shell"] += 1
                        if _has_best_purpose:
                            counts["generic_shell_with_best_move_purpose_fact"] += 1
                    if explanation.player_connection:
                        counts["personal_connection_eligible"] += 1
                        game_connections += 1
                        evidence = explanation.personal_evidence or {}
                        sources[str(evidence.get("source") or "position_only")] += 1
                        kinds[str(evidence.get("kind") or "unknown")] += 1

            board.push(move)
            history.append(san)

        per_game_connections.append(game_connections)

    result = {
        "schema_version": 1,
        "mode": "read_only_stored_engine_evidence",
        "email_redacted": True,
        "games_requested": game_limit,
        "games_found": len(games),
        "counts": dict(sorted(counts.items())),
        "personal_connection_sources": dict(sorted(sources.items())),
        "personal_connection_kinds": dict(sorted(kinds.items())),
        "caption_rules": dict(rules.most_common()),
        "caption_tiers": dict(tiers.most_common()),
        "primary_reason_categories": dict(reasons.most_common()),
        "games_with_personal_connection": sum(1 for n in per_game_connections if n),
        "max_connections_in_one_game": max(per_game_connections or [0]),
        "visible_text_changed": False,
        "database_writes": 0,
        "engine_runs": 0,
    }
    for key in (
        "eligible_moves", "final_verified", "has_board_explanation",
        "has_best_move_purpose_fact", "has_transferable_instruction",
        "personal_connection_eligible", "generic_recommendation_shell",
        "generic_shell_with_best_move_purpose_fact",
    ):
        result["counts"].setdefault(key, 0)
    client.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--games", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.email, args.games)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
