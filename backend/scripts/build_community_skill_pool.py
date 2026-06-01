"""Build the community pool of skill-drillable puzzles.

For a given skill_id, walks every analyzed game across every user
and runs the corresponding concept detector. Positions where the
detector fires ("applied" or "missed") become community_puzzles
entries tagged with the skill_id.

Why a community pool: the per-user evidence pool is tiny (Mohit had
6 missed ROS positions across 200 games — typical sparsity for any
single endgame skill). Community pool gives the drill enough volume
to be useful even for a brand-new user, and surfaces "you missed
this; here are 8 community positions that test the same idea."

Caps:
  - At most ONE puzzle per game per skill. A long pawn race walks
    through 4-5 sequential positions where the detector keeps
    firing on the same race — drilling the same race multiple times
    is dead repetition.
  - Per-game cap is applied PER PUZZLE outcome (one "applied" + one
    "missed" max per game) so we can still learn from BOTH sides of
    the same race when applicable.

Idempotent: skips inserts that already exist with the same
(skill_id, fen) regardless of shared_by. Re-running the script
across new games is safe.

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/build_community_skill_pool.py
    docker exec chess-coach-backend python /app/backend/scripts/build_community_skill_pool.py --skill endgame_rule_of_square --apply
    docker exec chess-coach-backend python /app/backend/scripts/build_community_skill_pool.py --skill endgame_rule_of_square --max-games 500 --apply
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

from services.concept_detectors.registry import DETECTORS


SKILL_PROMPT = {
    "endgame_rule_of_square": (
        "Pawn race. Can the king catch it? Find the right move."
    ),
}


def _walk_game_for_skill(pgn: str, user_color: chess.Color, detector):
    """Yield {fen_before, move_san, move_uci, move_number, outcome}
    for each move the detector grades."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return
    board = game.board()
    for ply, mv in enumerate(game.mainline_moves()):
        if board.turn == user_color:
            try:
                v = detector(board, mv, user_color)
            except Exception:
                v = None
            if v is not None:
                move_n = (ply // 2) + 1
                try:
                    san = board.san(mv)
                except Exception:
                    san = mv.uci()
                yield {
                    "move_number": move_n,
                    "move_san": san,
                    "move_uci": mv.uci(),
                    "fen_before": board.fen(),
                    "outcome": v,
                }
        try:
            board.push(mv)
        except Exception:
            return


async def _engine_best_for_move(db, game_id: str, move_number: int, move_san: str):
    """Pull (best_move_san, cp_loss) for this user move from
    game_analyses, if available. Used only as decoration on the
    puzzle doc — the detector is the grader."""
    a = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "move_evaluations": 1},
    )
    for me in (a or {}).get("move_evaluations") or []:
        if me.get("move_number") == move_number and me.get("move") == move_san:
            return me.get("best_move"), me.get("cp_loss")
    return None, None


async def _user_rating_for(db, user_id: str) -> int:
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "rating": 1})
    if u and u.get("rating"):
        try:
            return int(u["rating"])
        except (TypeError, ValueError):
            pass
    return 1200


async def build_pool(
    db,
    skill_id: str,
    apply_changes: bool,
    max_games: Optional[int] = None,
):
    detector = DETECTORS.get(skill_id)
    if detector is None:
        print(f"FATAL: no detector registered for skill_id={skill_id}")
        return

    prompt = SKILL_PROMPT.get(
        skill_id,
        "Apply the skill — what's the right move?"
    )

    games_q = db.games.find(
        {"is_analyzed": True, "pgn": {"$ne": ""}},
        {"_id": 0, "game_id": 1, "user_id": 1, "user_color": 1, "pgn": 1,
         "opening_name": 1, "opening_eco": 1}
    ).sort("end_time", -1)
    if max_games:
        games_q = games_q.limit(max_games)

    seen_fens_for_skill = set()
    async for p in db.community_puzzles.find(
        {"skill_id": skill_id}, {"_id": 0, "fen": 1}
    ):
        if p.get("fen"):
            seen_fens_for_skill.add(p["fen"])

    totals = {
        "games_scanned": 0,
        "positions_found": 0,
        "applied_inserted": 0,
        "missed_inserted": 0,
        "skipped_dupe_fen": 0,
        "skipped_per_game_cap": 0,
    }

    async for g in games_q:
        totals["games_scanned"] += 1
        gid = g.get("game_id")
        uid = g.get("user_id")
        if not gid or not uid:
            continue
        user_color_str = (g.get("user_color") or "white").lower()
        user_color = chess.WHITE if user_color_str == "white" else chess.BLACK

        try:
            results = list(_walk_game_for_skill(g.get("pgn") or "", user_color, detector))
        except Exception:
            continue

        # Per-game cap: at most one of each outcome.
        chosen_applied = None
        chosen_missed = None
        for r in results:
            totals["positions_found"] += 1
            if r["outcome"] == "applied" and chosen_applied is None:
                chosen_applied = r
            elif r["outcome"] == "missed" and chosen_missed is None:
                chosen_missed = r
            if chosen_applied and chosen_missed:
                break

        if chosen_applied is None and chosen_missed is None:
            continue

        user_rating = await _user_rating_for(db, uid)

        for r in (chosen_applied, chosen_missed):
            if r is None:
                continue
            fen = r["fen_before"]
            if fen in seen_fens_for_skill:
                totals["skipped_dupe_fen"] += 1
                continue

            best_san, cp_loss = await _engine_best_for_move(
                db, gid, r["move_number"], r["move_san"]
            )

            puzzle = {
                "fen": fen,
                "best_move_san": best_san or "",
                "skill_id": skill_id,
                "grading_strategy": "detector",
                "issue_type": "endgame_technique",
                "theme": "endgame",
                "difficulty": "intermediate",
                "opening_name": g.get("opening_name"),
                "opening_eco":  g.get("opening_eco"),
                "move_number":  r["move_number"],
                "user_color":   user_color_str,
                "shared_by":    uid,
                "source_game_id": gid,
                "source":       "community_skill_pool",
                "expected_outcome": r["outcome"],
                "description":  prompt,
                "cp_loss":      cp_loss,
                "attempts":     0,
                "solves":       0,
                "solve_rate":   0.0,
                "rating":       user_rating,
                "ratings":      [],
                "avg_rating":   0.0,
                "created_at":   datetime.now(timezone.utc),
                "approved":     True,
                "featured":     False,
            }
            if apply_changes:
                await db.community_puzzles.insert_one(puzzle)
            seen_fens_for_skill.add(fen)
            if r["outcome"] == "applied":
                totals["applied_inserted"] += 1
            else:
                totals["missed_inserted"] += 1

        if totals["games_scanned"] % 50 == 0:
            print(f"  scanned {totals['games_scanned']} games | "
                  f"applied+missed: {totals['applied_inserted']}/{totals['missed_inserted']}")

    print("\n=== TOTALS ===")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    print(f"  mode: {'APPLIED' if apply_changes else 'DRY-RUN (no writes)'}")


async def main_async(skill_id: str, apply_changes: bool, max_games: Optional[int]):
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL not set."); sys.exit(1)
    db_name = os.environ.get("DB_NAME") or "chess_coach"
    db = AsyncIOMotorClient(mongo_url)[db_name]
    await build_pool(db, skill_id, apply_changes, max_games)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--skill", default="endgame_rule_of_square",
                   help="skill_id (must have a concept_detector registered)")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--max-games", type=int, default=None)
    args = p.parse_args()
    asyncio.run(main_async(args.skill, args.apply, args.max_games))


if __name__ == "__main__":
    main()
