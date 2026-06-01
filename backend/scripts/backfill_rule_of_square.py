"""Backfill rule_of_the_square applied/missed evidence from analyzed
games using the WIDENED detector (see services/concept_detectors/
rule_of_the_square.py, 2026-06-01).

Rationale (Mohit 2026-06-01): the original detector required pure
K+P vs K, which fires 0 times on intermediate+ users' games. After
widening to the broader passed-pawn-race definition, the detector
catches real applications that were never credited. Run this script
once to retroactively credit those.

Safety:
  - Dry-run by default. Pass --apply to commit writes.
  - Idempotent: each evidence entry is keyed by (game_id, move_number)
    and skipped if already present.
  - Scoped to a single user with --user-id, OR all users with --all.

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/backfill_rule_of_square.py
    docker exec chess-coach-backend python /app/backend/scripts/backfill_rule_of_square.py --user-id user_8b599930d7ef --apply
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

from services.concept_detectors.rule_of_the_square import (
    detect_rule_of_the_square_application,
)

SKILL_ID = "endgame_rule_of_square"  # canonical skill_id (see skill_tree.json + concept_detectors/registry.py). "rule_of_square" is the content_ref, not the skill_id; using it here was the original bug — migrate-only script applied 2026-06-01.
GAMES_PER_USER = 200  # cap to avoid runaway scans


def _walk_game(pgn: str, user_color: chess.Color):
    """Yield (move_number, move_san, fen_before, verdict) for any move
    where the widened detector returns a non-None verdict.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return
    board = game.board()
    for ply, mv in enumerate(game.mainline_moves()):
        if board.turn == user_color:
            try:
                v = detect_rule_of_the_square_application(board, mv, user_color)
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
                    "fen_before": board.fen(),
                    "outcome": v,  # "applied" or "missed"
                }
        try:
            board.push(mv)
        except Exception:
            return


async def _ensure_skill_entry(memory, skill_id: str):
    """Return (skills_list, skill_dict) — creates the skill entry if missing."""
    learning = memory.get("learning") or {}
    skills = learning.get("skills") or []
    skill = next((s for s in skills if s.get("skill_id") == skill_id), None)
    if skill is None:
        skill = {
            "skill_id": skill_id,
            "seen": 0,
            "correct": 0,
            "applied": 0,
            "wrong": 0,
            "evidence": [],
            "learned_at": None,
        }
        skills.append(skill)
    return skills, skill


async def backfill_user(db, user_id: str, apply_changes: bool, verbose: bool = True):
    games = []
    async for g in db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}
    ).sort("end_time", -1).limit(GAMES_PER_USER):
        games.append(g)

    if verbose:
        print(f"\nuser={user_id}  scanning {len(games)} games...")
    if not games:
        return {"user_id": user_id, "scanned": 0, "added": 0, "skipped_dupe": 0}

    memory = await db.coach_memory.find_one({"user_id": user_id})
    if memory is None:
        if verbose:
            print(f"  no coach_memory for {user_id} — skipping")
        return {"user_id": user_id, "scanned": len(games), "added": 0, "skipped_dupe": 0, "no_memory": True}

    skills, skill = await _ensure_skill_entry(memory, SKILL_ID)
    existing_keys = {
        (e.get("game_id"), e.get("move_number"))
        for e in (skill.get("evidence") or [])
    }

    added = 0
    skipped_dupe = 0
    for g in games:
        gid = g.get("game_id")
        pgn = g.get("pgn") or ""
        if not pgn:
            continue
        user_color_str = (g.get("user_color") or "white").lower()
        user_color = chess.WHITE if user_color_str == "white" else chess.BLACK
        try:
            results = list(_walk_game(pgn, user_color))
        except Exception:
            continue
        for r in results:
            key = (gid, r["move_number"])
            if key in existing_keys:
                skipped_dupe += 1
                continue
            existing_keys.add(key)
            ev = {
                "game_id": gid,
                "move_number": r["move_number"],
                "move_san": r["move_san"],
                "fen_before": r["fen_before"],
                "outcome": r["outcome"],
                "source": "detector_backfill_2026_06_01",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            skill.setdefault("evidence", []).append(ev)
            skill["seen"] = int(skill.get("seen", 0)) + 1
            if r["outcome"] == "applied":
                skill["applied"] = int(skill.get("applied", 0)) + 1
                skill["correct"] = int(skill.get("correct", 0)) + 1
            else:
                skill["wrong"] = int(skill.get("wrong", 0)) + 1
            added += 1
            if verbose:
                marker = "[APPLIED]" if r["outcome"] == "applied" else "[ missed ]"
                print(f"  {marker} game={gid[:24]} move {r['move_number']} {r['move_san']:>6} "
                      f"({user_color_str})")

    if verbose:
        print(f"  -> {added} new evidence entries, {skipped_dupe} skipped as dupes")
        print(f"  -> skill totals after: seen={skill['seen']} applied={skill['applied']} "
              f"correct={skill['correct']} wrong={skill['wrong']}")

    if apply_changes and added > 0:
        memory_id = memory.get("_id")
        # Cap evidence length to avoid runaway doc growth.
        skill["evidence"] = skill["evidence"][-50:]
        learning = memory.setdefault("learning", {})
        learning["skills"] = skills
        await db.coach_memory.update_one(
            {"_id": memory_id},
            {"$set": {"learning.skills": learning["skills"]}}
        )
        if verbose:
            print(f"  -> WROTE to coach_memory")

    return {
        "user_id": user_id, "scanned": len(games),
        "added": added, "skipped_dupe": skipped_dupe,
    }


async def main_async(apply_changes: bool, user_id: Optional[str]):
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL not set."); sys.exit(1)
    db_name = os.environ.get("DB_NAME") or "chess_coach"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if user_id:
        users = [user_id]
    else:
        # All users with at least one analyzed game
        users = set()
        async for g in db.games.find({"is_analyzed": True}, {"_id": 0, "user_id": 1}).limit(10000):
            users.add(g["user_id"])
        users = sorted(users)
        print(f"Found {len(users)} users with analyzed games.")

    totals = {"scanned": 0, "added": 0, "skipped_dupe": 0}
    for uid in users:
        res = await backfill_user(db, uid, apply_changes)
        totals["scanned"] += res["scanned"]
        totals["added"] += res["added"]
        totals["skipped_dupe"] += res["skipped_dupe"]

    print("\n=== TOTALS ===")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    print(f"  mode: {'APPLIED' if apply_changes else 'DRY-RUN (no writes)'}")
    if not apply_changes:
        print("\nRe-run with --apply to commit.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Actually write to mongo. Without this flag, dry-run only.")
    p.add_argument("--user-id", default=None,
                   help="Scope to one user. Without this, runs over all users.")
    args = p.parse_args()
    asyncio.run(main_async(args.apply, args.user_id))


if __name__ == "__main__":
    main()
