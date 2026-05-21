"""Caption claim verifier — mechanically checks specific claims in
V5 captions against the position they reference.

Most captions make CONCRETE CLAIMS that can be falsified:
  - "wins the {piece} on {square}" — piece must actually exist there after PV
  - "would have led to mate in {N} moves" — PV must end in mate within N
  - "Opponent's strongest reply: {san}" — must match Stockfish's actual #1
  - "{best_move_san} clears the line — your {piece} comes through to
    attack {square}" — slider must actually have a line to that square
  - curriculum: position must actually be in the claimed opening tree

This script:
  1. Walks every captioned user move in the recent 500 games
  2. For each, applies mechanical verifiers
  3. Emits a JSON report of suspect captions (with reason)

Mohit-driven overnight task (2026-05-21): "find out games that don't
have the right caption, run FEN, find out why they were not caught."

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/caption_verifier.py --sample 500
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient


_STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
_PIECE_NAME_TO_TYPE = {
    "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
    "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING,
}
_PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}


# ────────────────────────────────────────────────────────────────────
# Claim extractors — pull verifiable claims from caption text
# ────────────────────────────────────────────────────────────────────


def _extract_piece_capture_claim(caption: str) -> Optional[Dict[str, str]]:
    """Match 'wins the {piece} on {square}'. Returns
    {piece, square, move} or None."""
    m = re.search(
        r"(\b[A-Z][a-h1-8x+#=]+\b) wins the (pawn|knight|bishop|rook|queen) on ([a-h][1-8])",
        caption,
    )
    if not m:
        return None
    return {"move": m.group(1), "piece": m.group(2), "square": m.group(3)}


def _extract_mate_claim(caption: str) -> Optional[Dict[str, Any]]:
    m = re.search(
        r"(\b[A-Z][a-h1-8x+#=]+\b) would have led to mate in (\d+) moves",
        caption,
    )
    if not m:
        return None
    return {"move": m.group(1), "ply": int(m.group(2))}


def _extract_opp_reply_claim(caption: str) -> Optional[Dict[str, str]]:
    m = re.search(r"Opponent's strongest reply: ([A-Za-z0-9+#=-]+)", caption)
    if not m:
        return None
    return {"reply": m.group(1)}


def _extract_clearance_claim(caption: str) -> Optional[Dict[str, str]]:
    m = re.search(
        r"(\b[A-Z][a-h1-8x+#=]+\b) clears the line — your (queen|rook|bishop) comes through to attack ([a-h][1-8])",
        caption,
    )
    if not m:
        return None
    return {"move": m.group(1), "piece": m.group(2), "square": m.group(3)}


# ────────────────────────────────────────────────────────────────────
# Verifiers — mechanically check each claim
# ────────────────────────────────────────────────────────────────────


def verify_piece_capture(
    fen_before: str,
    best_move_san: Optional[str],
    pv_after_best: List[str],
    claim: Dict[str, str],
    eval_before_cp: Optional[int],
    user_color: str,
) -> Optional[str]:
    """Walk the PV; return None if claim verifies, else a one-line
    reason."""
    if not best_move_san or best_move_san != claim["move"]:
        return f"claim names {claim['move']!r} but stored best_move is {best_move_san!r}"
    try:
        board = chess.Board(fen_before)
        bm = board.parse_san(best_move_san)
        board.push(bm)
    except Exception:
        return "fen_before / best_move_san unparseable"

    target_piece_type = _PIECE_NAME_TO_TYPE.get(claim["piece"])
    target_square = chess.parse_square(claim["square"])

    # Walk the PV looking for a user-side capture of the named piece
    # on the named square.
    is_user_white = (user_color or "").lower() == "white"
    is_user_move = False  # after best_move, opp is to move
    pv_ucis = pv_after_best or []
    for ply, san in enumerate(pv_ucis[:10]):
        try:
            mv = board.parse_san(san)
        except Exception:
            break
        is_user_move = (ply % 2 == 1)  # PV is opp, user, opp, user
        if is_user_move and board.is_capture(mv) and mv.to_square == target_square:
            captured = board.piece_at(target_square)
            if captured and captured.piece_type == target_piece_type:
                return None  # claim verified
        board.push(mv)

    # If we never saw the capture, the claim is wrong.
    return f"PV doesn't show user capturing {claim['piece']} on {claim['square']}"


def verify_mate_claim(
    fen_before: str,
    best_move_san: Optional[str],
    pv_after_best: List[str],
    claim: Dict[str, Any],
) -> Optional[str]:
    if not best_move_san or best_move_san != claim["move"]:
        return f"claim names {claim['move']!r} but stored best_move is {best_move_san!r}"
    try:
        board = chess.Board(fen_before)
        board.push_san(best_move_san)
    except Exception:
        return "fen_before / best_move_san unparseable"
    for san in (pv_after_best or [])[: claim["ply"] * 2]:
        try:
            board.push_san(san)
        except Exception:
            return f"PV unparseable at {san!r}"
    if board.is_checkmate():
        return None
    return f"PV doesn't actually end in mate by ply {claim['ply'] * 2}"


def verify_opp_reply(
    fen_before: str,
    played_san: str,
    claim: Dict[str, str],
    pv_after_played: List[str],
) -> Optional[str]:
    if not pv_after_played:
        return None  # nothing to verify against; not a false claim per se
    first_pv = pv_after_played[0] if pv_after_played else None
    if first_pv != claim["reply"]:
        return f"caption names {claim['reply']!r}; pv_after_played[0]={first_pv!r}"
    return None


def verify_clearance(
    fen_before: str,
    best_move_san: Optional[str],
    claim: Dict[str, str],
    user_color: str,
) -> Optional[str]:
    """Verify that after best_move, the user's named piece-type has a
    legal line to the named square."""
    if not best_move_san or best_move_san != claim["move"]:
        return f"claim names {claim['move']!r} but stored best_move is {best_move_san!r}"
    try:
        board = chess.Board(fen_before)
        board.push_san(best_move_san)
    except Exception:
        return "fen_before / best_move_san unparseable"

    target_piece_type = _PIECE_NAME_TO_TYPE.get(claim["piece"])
    if not target_piece_type:
        return f"unknown piece {claim['piece']!r}"
    target_square = chess.parse_square(claim["square"])
    user_color_chess = chess.WHITE if (user_color or "").lower() == "white" else chess.BLACK

    # After best_move, opp is to move. We're checking whether the
    # USER has a piece (of the named type) that can attack the target
    # square in the resulting position.
    for sq in board.pieces(target_piece_type, user_color_chess):
        attacks = board.attacks(sq)
        if target_square in attacks:
            return None  # piece can attack the square; claim verified
    return f"user has no {claim['piece']} attacking {claim['square']} after {best_move_san}"


# ────────────────────────────────────────────────────────────────────
# Main loop
# ────────────────────────────────────────────────────────────────────


async def verify(sample_size: int, out_path: str) -> Dict[str, Any]:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Pull recently-analyzed games with v5 data.
    cursor = (db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": None}},
        {"_id": 0, "game_id": 1, "user_id": 1, "decryption_v5_data": 1,
         "decryption_v5_version": 1, "stockfish_analysis": 1},
    ).sort("created_at", -1).limit(sample_size))

    suspects: List[Dict[str, Any]] = []
    counters = Counter()
    total = 0

    async for g in cursor:
        gid = g.get("game_id") or ""
        v5_data = g.get("decryption_v5_data") or []
        sa = g.get("stockfish_analysis") or {}
        move_evals = sa.get("move_evaluations") or sa.get("moves") or []
        user_color = None
        # Find user_color from games doc
        gd = await db.games.find_one({"game_id": gid}, {"_id": 0, "user_color": 1})
        if gd:
            user_color = gd.get("user_color")
        user_color = (user_color or "white").lower()

        for m in v5_data:
            if not m.get("is_user_move"):
                continue
            caption = m.get("caption") or ""
            if not caption:
                continue
            total += 1
            move_number = m.get("move_number")
            fen_before = m.get("fen_before") or ""
            played_san = m.get("move_san") or ""
            best_move_san = m.get("best_move_san") or ""

            # Try to find the matching eval entry for pv_after_best
            pv_after_best = []
            pv_after_played = []
            eval_before_cp = None
            for ev in move_evals:
                if (ev.get("move_number") == move_number
                        and ev.get("move") == played_san):
                    pv_after_best = ev.get("pv_after_best") or []
                    pv_after_played = ev.get("pv_after_played") or []
                    eb = ev.get("eval_before")
                    if isinstance(eb, (int, float)):
                        eval_before_cp = int(round(eb * 100)) if abs(eb) < 100 else int(round(eb))
                    break

            sample_record = {
                "game_id": gid[:12],
                "move_number": move_number,
                "move_san": played_san,
                "fen_before": fen_before,
                "best_move_san": best_move_san,
                "caption": caption,
                "user_color": user_color,
                "cp_loss": m.get("cp_loss"),
            }

            # 1. piece_capture claim
            pc = _extract_piece_capture_claim(caption)
            if pc:
                reason = verify_piece_capture(
                    fen_before, best_move_san, pv_after_best, pc,
                    eval_before_cp, user_color,
                )
                if reason:
                    counters["piece_capture_fail"] += 1
                    suspects.append({
                        **sample_record,
                        "verifier": "piece_capture",
                        "claim": pc,
                        "reason": reason,
                    })

            # 2. mate claim
            mc = _extract_mate_claim(caption)
            if mc:
                reason = verify_mate_claim(
                    fen_before, best_move_san, pv_after_best, mc,
                )
                if reason:
                    counters["mate_fail"] += 1
                    suspects.append({
                        **sample_record,
                        "verifier": "mate",
                        "claim": mc,
                        "reason": reason,
                    })

            # 3. opp_reply claim
            orc = _extract_opp_reply_claim(caption)
            if orc:
                reason = verify_opp_reply(
                    fen_before, played_san, orc, pv_after_played,
                )
                if reason:
                    counters["opp_reply_fail"] += 1
                    suspects.append({
                        **sample_record,
                        "verifier": "opp_reply",
                        "claim": orc,
                        "reason": reason,
                    })

            # 4. clearance claim
            cc = _extract_clearance_claim(caption)
            if cc:
                reason = verify_clearance(
                    fen_before, best_move_san, cc, user_color,
                )
                if reason:
                    counters["clearance_fail"] += 1
                    suspects.append({
                        **sample_record,
                        "verifier": "clearance",
                        "claim": cc,
                        "reason": reason,
                    })

    out = {
        "sample_size": sample_size,
        "total_captioned_moves": total,
        "suspect_count": len(suspects),
        "counters": dict(counters),
        "suspects": suspects,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=500)
    parser.add_argument("--out", default="/tmp/caption_verifier_report.json")
    args = parser.parse_args()
    out = asyncio.run(verify(args.sample, args.out))
    print(f"Captioned moves checked: {out['total_captioned_moves']}")
    print(f"Suspect captions: {out['suspect_count']}")
    print(f"By verifier: {out['counters']}")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
