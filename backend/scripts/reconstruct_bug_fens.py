"""
Reconstruct FENs for bug entries that have empty FEN.

Many of Parth's lab-page bugs (GameDecryptionV5) come with game_id +
move_number + move_san but no FEN. The audit can't run without FEN, so
we pre-process: load each game's PGN, replay to the matching move,
capture FEN BEFORE the move (so engine analysis evaluates the played
move's consequences).

Output: a new JSON file with `position.fen` populated where possible.
The original file is left untouched.

Usage:
    docker exec chess-coach-backend python scripts/reconstruct_bug_fens.py \\
        --in scripts/parth_bugs_2026-05-09.json \\
        --out scripts/parth_bugs_2026-05-09_with_fen.json
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _replay_to_move(
    pgn_text: str, target_move_number: int, target_move_san: str
) -> Optional[str]:
    """Replay PGN until the move at (target_move_number, target_move_san).
    Return FEN BEFORE that move is played, so an engine evaluating the
    position would be evaluating what the player faced.

    Returns None if PGN doesn't parse, or no move matches.
    """
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return None
    if game is None:
        return None

    board = game.board()
    target_san_norm = (target_move_san or "").rstrip("!?+#")

    for move in game.mainline_moves():
        # Compute move metadata BEFORE pushing.
        try:
            move_san = board.san(move)
        except Exception:
            return None
        current_full_move = board.fullmove_number

        san_norm = move_san.rstrip("!?+#")

        if (
            current_full_move == target_move_number
            and san_norm == target_san_norm
        ):
            return board.fen()

        try:
            board.push(move)
        except Exception:
            return None

    # No exact match — fall back to "first move at this move_number"
    # if san match was the issue (san can vary slightly across notations).
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        board = game.board()
        for move in game.mainline_moves():
            if board.fullmove_number == target_move_number:
                return board.fen()
            board.push(move)
    except Exception:
        pass
    return None


async def reconstruct(args):
    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    n_total = 0
    n_already_had = 0
    n_no_game_id = 0
    n_game_not_found = 0
    n_no_pgn = 0
    n_no_match = 0
    n_filled = 0

    # Cache PGNs per game_id to avoid re-querying.
    pgn_cache: Dict[str, Optional[str]] = {}

    for bug in bugs:
        n_total += 1
        position = bug.get("position") or {}
        fen = (position.get("fen") or "").strip()
        if fen:
            n_already_had += 1
            continue

        ctx = bug.get("context") or {}
        game_id = ctx.get("game_id")
        move_number = position.get("move_number")
        move_san = position.get("move_san") or ""

        if not game_id or not move_number:
            n_no_game_id += 1
            continue

        if game_id not in pgn_cache:
            game_doc = await db.games.find_one(
                {"game_id": game_id}, {"_id": 0, "pgn": 1}
            )
            pgn_cache[game_id] = (game_doc or {}).get("pgn") if game_doc else None

        pgn = pgn_cache[game_id]
        if pgn is None:
            n_game_not_found += 1
            continue
        if not pgn:
            n_no_pgn += 1
            continue

        new_fen = _replay_to_move(pgn, int(move_number), move_san)
        if new_fen is None:
            n_no_match += 1
            continue

        position["fen"] = new_fen
        bug["position"] = position
        n_filled += 1

    client.close()

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("=" * 70)
    print(f"FEN reconstruction: {in_path.name} -> {out_path.name}")
    print("=" * 70)
    print(f"  total bugs:                {n_total}")
    print(f"  already had FEN:           {n_already_had}")
    print(f"  filled in this run:        {n_filled}")
    print(f"  skipped (no game_id):      {n_no_game_id}")
    print(f"  skipped (game not found):  {n_game_not_found}")
    print(f"  skipped (no pgn):          {n_no_pgn}")
    print(f"  skipped (no move match):   {n_no_match}")
    print()
    print(f"Output written. Run the audit with:")
    print(f"  docker exec chess-coach-backend python scripts/content_correctness_audit.py \\")
    print(f"    --bug-file {out_path} --engine")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="input bug JSON")
    p.add_argument("--out", dest="out_path", required=True, help="output bug JSON with FENs filled in")
    asyncio.run(reconstruct(p.parse_args()))
