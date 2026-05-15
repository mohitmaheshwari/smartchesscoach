"""
ONE-OFF audit: pull the FENs for every move Parth flagged as a detector
false positive, re-run the detectors against those positions, and print
a verification report.

Per the locked rule reference_per_fire_audit_pattern:
  data → detector → frequency audit → per-fire geometric verifier → scrub

This is the per-fire geometric verifier step. It loads each flagged
position, re-runs the relevant detector (shape pattern or principle),
and prints the geometry so we can manually verify whether the detector
fired correctly.

Targets the 4 detector false-positive bugs flagged in feedback round on
game 1b196a4f-cc41-434b-9d11-112acad2906b:
  - Back-Rank Trap on Qd4 (move 31)
  - Skewer on Qxd2 (move 14)
  - Pin on Bxf3 (move 12)
  - Free Pawn on d4 (move 11)

Run:
    docker exec -it chess-coach-backend python scripts/audit_parth_flags.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Move-number + SAN keys from Parth's flagged bugs on this game
FLAGGED = [
    ("Qd4", 31, "Back-Rank Trap"),
    ("Qxd2", 14, "Skewer"),
    ("Bxf3", 12, "Pin"),
    ("d4", 11, "Free Pawn"),
]
GAME_ID = "1b196a4f-cc41-434b-9d11-112acad2906b"


def board_summary(fen: str) -> str:
    """Print piece placement summary for manual verification."""
    board = chess.Board(fen)
    lines = [f"  FEN: {fen}"]
    lines.append(f"  Turn: {'white' if board.turn else 'black'}")
    lines.append(f"  White king: {chess.square_name(board.king(chess.WHITE)) if board.king(chess.WHITE) else '?'}")
    lines.append(f"  Black king: {chess.square_name(board.king(chess.BLACK)) if board.king(chess.BLACK) else '?'}")
    # List all pieces
    white_pieces, black_pieces = [], []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p:
            continue
        s = f"{p.symbol()}{chess.square_name(sq)}"
        if p.color == chess.WHITE:
            white_pieces.append(s)
        else:
            black_pieces.append(s)
    lines.append(f"  White: {' '.join(white_pieces)}")
    lines.append(f"  Black: {' '.join(black_pieces)}")
    return "\n".join(lines)


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    analysis = await db.game_analyses.find_one(
        {"game_id": GAME_ID},
        {"_id": 0, "decryption_v5_data": 1},
    )
    if not analysis:
        print(f"No analysis for {GAME_ID}")
        return

    moves = analysis.get("decryption_v5_data") or []

    for flagged_san, flagged_mn, flagged_pattern in FLAGGED:
        # Find the matching move record
        target = None
        for m in moves:
            if m.get("move_number") == flagged_mn and m.get("move_san") == flagged_san:
                target = m
                break
        if not target:
            print(f"\n══════════════════════════════════════════════════════════════")
            print(f"  {flagged_mn}. {flagged_san}  pattern: {flagged_pattern}")
            print(f"  ⚠ MOVE NOT FOUND in decryption_v5_data — flagged data may be wrong")
            continue

        print(f"\n══════════════════════════════════════════════════════════════")
        print(f"  Move {flagged_mn}. {flagged_san}  (Parth flagged: '{flagged_pattern}')")
        print(f"══════════════════════════════════════════════════════════════")

        # Print position context — BEFORE the move (what the detector saw)
        fen_before = target.get("fen_before", "")
        fen_after = target.get("fen_after", "")

        print(f"\n  POSITION BEFORE THE MOVE (this is what the detector sees):")
        print(board_summary(fen_before))

        print(f"\n  POSITION AFTER THE MOVE:")
        print(board_summary(fen_after))

        # What the detector actually emitted
        sp_name = target.get("shape_pattern_name")
        sp_targets = target.get("shape_pattern_targets") or []
        sp_mover = target.get("shape_pattern_mover")
        sp_exec = target.get("shape_pattern_executing_move")
        principles_violated = [
            p.get("principle_id")
            for p in (target.get("caption_facts_principles_violated") or [])
            if p
        ]
        print(f"\n  WHAT FIRED:")
        print(f"    shape_pattern_name      : {sp_name}")
        print(f"    shape_pattern_mover     : {sp_mover}")
        print(f"    shape_pattern_targets   : {sp_targets}")
        print(f"    shape_pattern_executing : {sp_exec}")
        print(f"    principles_violated     : {principles_violated}")
        print(f"    severity                : {target.get('severity')}")
        print(f"    cp_loss                 : {target.get('cp_loss')}")
        print(f"    best_move_san           : {target.get('best_move_san')}")
        print(f"    primary_reason          : {target.get('caption_facts_primary_reason')}")

        # Also surface the existing rendered caption + LLM caption
        print(f"\n  TEXT EMITTED:")
        print(f"    deterministic caption: {target.get('caption') or '(empty)'}")
        print(f"    caption_llm          : {target.get('caption_llm') or '(empty / not backfilled)'}")
        print(f"    principle_cue        : {target.get('principle_cue') or '(empty)'}")


if __name__ == "__main__":
    asyncio.run(main())
