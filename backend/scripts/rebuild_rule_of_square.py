"""Wipe the rule_of_square backfill, then rerun against the
TIGHTENED detector (defender has only king + pawns).

Mohit 2026-06-01: the first backfill (source =
detector_backfill_2026_06_01) credited positions where the defender
still had Q/R/B/N on the board — the FEN
`Q7/6p1/2K5/1B2p1p1/5k2/3P4/8/8 b` was the smoking gun. The queen
was on the long diagonal but happened to be blocked in that exact
move, so the old "no non-king attacker on the path" check missed it.

This script:
  1. Strips every evidence entry tagged with the backfill source
     from rule_of_square (preserves anything written by the live
     detector / other sources).
  2. Subtracts those from seen / applied / wrong / correct counters.
  3. Re-runs the detector across the user's analyzed games and
     re-credits anything that still qualifies. New entries tagged
     with `detector_backfill_2026_06_01_v2` so we can audit later.

Idempotent. Dry-run by default.

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/rebuild_rule_of_square.py
    docker exec chess-coach-backend python /app/backend/scripts/rebuild_rule_of_square.py --user-id user_8b599930d7ef --apply
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

SKILL_ID = "endgame_rule_of_square"  # canonical skill_id; see backfill_rule_of_square.py note.
OLD_SOURCE = "detector_backfill_2026_06_01"
NEW_SOURCE = "detector_backfill_2026_06_01_v2"
GAMES_PER_USER = 200


def _walk_game(pgn: str, user_color: chess.Color):
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
                    "outcome": v,
                }
        try:
            board.push(mv)
        except Exception:
            return


async def rebuild_user(db, user_id: str, apply_changes: bool, verbose: bool = True):
    memory = await db.coach_memory.find_one({"user_id": user_id})
    if memory is None:
        if verbose:
            print(f"\nuser={user_id}  no coach_memory — skipping")
        return {"user_id": user_id, "removed": 0, "added": 0, "scanned": 0}

    skills = (memory.get("learning") or {}).get("skills") or []
    skill = next((s for s in skills if s.get("skill_id") == SKILL_ID), None)
    if skill is None:
        skill = {"skill_id": SKILL_ID, "seen": 0, "correct": 0, "applied": 0,
                 "wrong": 0, "evidence": [], "learned_at": None}
        skills.append(skill)

    # 1. Strip stale backfill evidence.
    evidence = skill.get("evidence") or []
    keep = [e for e in evidence if e.get("source") != OLD_SOURCE]
    stripped = [e for e in evidence if e.get("source") == OLD_SOURCE]
    removed_applied = sum(1 for e in stripped if e.get("outcome") == "applied")
    removed_wrong = sum(1 for e in stripped if e.get("outcome") == "missed")
    removed = len(stripped)
    skill["evidence"] = keep
    skill["seen"] = max(0, int(skill.get("seen", 0)) - removed)
    skill["applied"] = max(0, int(skill.get("applied", 0)) - removed_applied)
    skill["correct"] = max(0, int(skill.get("correct", 0)) - removed_applied)
    skill["wrong"] = max(0, int(skill.get("wrong", 0)) - removed_wrong)

    if verbose:
        print(f"\nuser={user_id}")
        print(f"  stripped {removed} stale entries ({removed_applied} applied, {removed_wrong} missed)")

    # 2. Re-scan analyzed games with the tightened detector.
    games = []
    async for g in db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}
    ).sort("end_time", -1).limit(GAMES_PER_USER):
        games.append(g)

    existing_keys = {(e.get("game_id"), e.get("move_number")) for e in skill["evidence"]}
    added = 0
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
                continue
            existing_keys.add(key)
            ev = {
                "game_id": gid,
                "move_number": r["move_number"],
                "move_san": r["move_san"],
                "fen_before": r["fen_before"],
                "outcome": r["outcome"],
                "source": NEW_SOURCE,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            skill["evidence"].append(ev)
            skill["seen"] = int(skill.get("seen", 0)) + 1
            if r["outcome"] == "applied":
                skill["applied"] = int(skill.get("applied", 0)) + 1
                skill["correct"] = int(skill.get("correct", 0)) + 1
            else:
                skill["wrong"] = int(skill.get("wrong", 0)) + 1
            added += 1
            if verbose:
                marker = "[APPLIED]" if r["outcome"] == "applied" else "[ missed ]"
                print(f"  {marker} game={gid[:24]} move {r['move_number']} {r['move_san']:>6}")

    if verbose:
        print(f"  -> {added} fresh entries with tightened detector")
        print(f"  -> totals after: seen={skill['seen']} applied={skill['applied']} "
              f"correct={skill['correct']} wrong={skill['wrong']}")

    if apply_changes and (removed > 0 or added > 0):
        # Cap evidence to last 50 to keep doc compact.
        skill["evidence"] = skill["evidence"][-50:]
        learning = memory.setdefault("learning", {})
        learning["skills"] = skills
        await db.coach_memory.update_one(
            {"_id": memory["_id"]},
            {"$set": {"learning.skills": learning["skills"]}}
        )
        if verbose:
            print(f"  -> WROTE coach_memory")

    return {"user_id": user_id, "removed": removed, "added": added, "scanned": len(games)}


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
        users = set()
        async for m in db.coach_memory.find(
            {"learning.skills.skill_id": SKILL_ID}, {"_id": 0, "user_id": 1}
        ).limit(10000):
            users.add(m["user_id"])
        users = sorted(users)
        print(f"Found {len(users)} users with endgame_rule_of_square skill entries.")

    totals = {"scanned": 0, "removed": 0, "added": 0}
    for uid in users:
        res = await rebuild_user(db, uid, apply_changes)
        totals["scanned"] += res["scanned"]
        totals["removed"] += res["removed"]
        totals["added"] += res["added"]

    print("\n=== TOTALS ===")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    print(f"  mode: {'APPLIED' if apply_changes else 'DRY-RUN (no writes)'}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--user-id", default=None)
    args = p.parse_args()
    asyncio.run(main_async(args.apply, args.user_id))


if __name__ == "__main__":
    main()
