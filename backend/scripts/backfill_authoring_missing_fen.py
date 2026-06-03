"""Backfill FEN for the 7 authoring submissions persisted with empty fen.

Mohit 2026-06-03 — discovered while draining the authoring queue. All 7
no-FEN records are from a 35-minute window on 2026-05-15, same game
(1b196a4f-cc41-434b), submitted via GameDecryptionV5. The frontend dialog
used to send `fen: context.fen || ""` and the backend Pydantic model had
`fen: str` (which accepts ""). Both layers are now tightened; this script
patches the historical rows by replaying the game's PGN to each move number.

Dry-run by default. Pass --apply to write.
"""

import argparse
import asyncio
import os
import sys

import chess
import chess.pgn
from io import StringIO
from motor.motor_asyncio import AsyncIOMotorClient


async def main(apply: bool) -> int:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    cursor = db.move_feedback.find(
        {
            "is_authoring_submission": True,
            "$or": [{"fen": None}, {"fen": ""}, {"fen": {"$exists": False}}],
        },
        {"_id": 0, "feedback_id": 1, "game_id": 1, "move_number": 1, "move_san": 1},
    )
    rows = [r async for r in cursor]
    if not rows:
        print("Nothing to backfill — no authoring submissions with empty fen.")
        return 0

    # Cache PGNs per game_id so we don't reparse for every move
    pgn_cache: dict[str, str] = {}
    patched = 0
    skipped = 0

    for row in rows:
        fid = row["feedback_id"]
        gid = row.get("game_id")
        mn = row.get("move_number")
        san = row.get("move_san")
        if not (gid and mn and san):
            print(f"SKIP {fid} — missing game_id/move_number/move_san")
            skipped += 1
            continue

        if gid not in pgn_cache:
            game_doc = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1})
            if not game_doc or not game_doc.get("pgn"):
                print(f"SKIP {fid} — game {gid} has no PGN")
                skipped += 1
                pgn_cache[gid] = ""
                continue
            pgn_cache[gid] = game_doc["pgn"]

        pgn_text = pgn_cache[gid]
        if not pgn_text:
            skipped += 1
            continue

        game = chess.pgn.read_game(StringIO(pgn_text))
        if game is None:
            print(f"SKIP {fid} — PGN unparseable for game {gid}")
            skipped += 1
            continue

        board = game.board()
        target_fen = None
        # full move number `mn` + SAN — find the position BEFORE that move was played
        for ply, move in enumerate(game.mainline_moves(), start=1):
            full_move = (ply + 1) // 2  # 1,1,2,2,3,3,...
            move_san_here = board.san(move)
            if full_move == mn and move_san_here == san:
                target_fen = board.fen()
                break
            board.push(move)

        if not target_fen:
            print(f"SKIP {fid} — could not locate m{mn} {san} in game {gid}")
            skipped += 1
            continue

        if apply:
            await db.move_feedback.update_one(
                {"feedback_id": fid},
                {"$set": {"fen": target_fen, "fen_backfilled_at": "2026-06-03", "fen_backfill_source": "pgn_replay"}},
            )
        print(f"{'APPLY' if apply else 'DRY  '} {fid} m{mn} {san} → {target_fen[:40]}...")
        patched += 1

    print()
    print(f"Done. {patched} patched, {skipped} skipped. {'WROTE TO DB.' if apply else 'Dry-run only; rerun with --apply to commit.'}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Commit changes (default is dry-run)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.apply)))
