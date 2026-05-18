"""
Per-fire audit for END_ROOK_BEHIND_PASSER detector.

Phase 4 (Mohit signoff 2026-05-16): Tarrasch's rule, single-passer-only.

Locked rule per [[per-fire-audit-pattern]] + [[audit-coverage-tracks-surface]]:
the detector must produce 0 geometric mismatches on a real-corpus pass
before being marked as board-verified. AND each surviving fire must be
manually reviewed for pedagogical purity (is this a genuine Tarrasch
teaching moment, or technically true but practically irrelevant?).

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_rook_behind_passer.py

Manual review checklist per fire:
  - Is there genuinely a single passer on the board?
  - Is the engine-best rook move REALLY a rook lift to the file
    behind the passer?
  - Was the played move defensible for non-Tarrasch reasons?
  - Would a 1200 player learn something portable from this caption?
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess
from motor.motor_asyncio import AsyncIOMotorClient

from services.caption_facts import (
    _p_end_rook_behind_passer,
    _passed_pawn_behind_squares,
    _own_passed_pawns,
)


def _facts_from_move(m: dict) -> dict:
    return {
        "phase":             m.get("phase"),
        "cp_loss":           m.get("cp_loss") or 0,
        "best_move_san":     m.get("best_move_san") or "",
        "played_san":        m.get("move_san") or "",
        "moving_piece_color": "white" if m.get("is_white") else "black",
        "eval_before_cp":    m.get("eval_before"),
    }


def _verify_geometry(board: chess.Board, ev: dict) -> str:
    """Re-derive the Tarrasch geometry and report whether it holds.
    Returns 'OK' or a short reason string for a mismatch.
    """
    passer_name = ev.get("passer_square")
    passer_color_name = ev.get("passer_color")
    rook_from_name = ev.get("rook_square_played")
    rook_to_name = ev.get("rook_target_square")
    claimed_perspective = ev.get("perspective")

    try:
        passer_sq = chess.parse_square(passer_name)
        rook_from = chess.parse_square(rook_from_name)
        rook_to = chess.parse_square(rook_to_name)
    except (TypeError, ValueError) as e:
        return f"square parse failed: {e}"

    passer_color = chess.WHITE if passer_color_name == "white" else chess.BLACK

    # 1. There must be a pawn of the claimed color on passer_sq.
    p = board.piece_at(passer_sq)
    if not p or p.piece_type != chess.PAWN:
        return f"no pawn on {passer_name}"
    if p.color != passer_color:
        return f"{passer_name} pawn color mismatch (claimed {passer_color_name})"

    # 2. There must be EXACTLY ONE passer on the board.
    all_passers = []
    for color in (chess.WHITE, chess.BLACK):
        all_passers.extend(_own_passed_pawns(board, color))
    if len(all_passers) != 1:
        return f"expected single passer, found {len(all_passers)}"
    if all_passers[0] != passer_sq:
        return (
            f"single-passer mismatch: claim {passer_name}, "
            f"computed {chess.square_name(all_passers[0])}"
        )

    # 3. Rook-from square must contain a rook of the moving side.
    rook_piece = board.piece_at(rook_from)
    if not rook_piece or rook_piece.piece_type != chess.ROOK:
        return f"no rook on {rook_from_name}"
    if rook_piece.color != board.turn:
        return f"rook on {rook_from_name} is wrong color"

    # 4. Target must be on the same file as the passer AND on the
    #    behind side relative to the pawn's origin.
    if chess.square_file(rook_to) != chess.square_file(passer_sq):
        return f"target {rook_to_name} not on passer's file"
    behind = _passed_pawn_behind_squares(passer_sq, passer_color)
    if rook_to not in behind:
        return f"target {rook_to_name} not on the BEHIND side of passer"

    # 5. Perspective claim should match (supporting if own passer).
    expected_perspective = "supporting" if rook_piece.color == passer_color else "restraining"
    if claimed_perspective != expected_perspective:
        return (
            f"perspective mismatch: claim {claimed_perspective}, "
            f"computed {expected_perspective}"
        )

    return "OK"


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    total_games = 0
    games_with_v5 = 0
    moves_checked = 0
    fires = []

    async for a in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1, "user_id": 1},
    ):
        total_games += 1
        moves = a.get("decryption_v5_data") or []
        if not moves:
            continue
        games_with_v5 += 1
        for m in moves:
            if m.get("phase") not in ("endgame", "middlegame"):
                continue
            fen_before = m.get("fen_before")
            if not fen_before:
                continue
            try:
                board = chess.Board(fen_before)
            except Exception:
                continue
            moves_checked += 1
            facts = _facts_from_move(m)
            try:
                ev = _p_end_rook_behind_passer(facts, board)
            except Exception as e:
                print(f"  DETECTOR CRASH on {a['game_id'][:8]} move {m.get('move_number')}: {e}")
                continue
            if not ev:
                continue
            verdict = _verify_geometry(board, ev["evidence"])
            eb_white_pov = m.get("eval_before")
            stm_eb = None
            if eb_white_pov is not None:
                stm_eb = eb_white_pov if m.get("is_white") else -eb_white_pov
            fires.append({
                "game_id":     a["game_id"],
                "move_number": m.get("move_number"),
                "move_san":    m.get("move_san"),
                "fen_before":  fen_before,
                "evidence":    ev["evidence"],
                "verdict":     verdict,
                "stm_eval_before": stm_eb,
            })

    print("Audit complete.")
    print(f"  Games scanned:                {total_games}")
    print(f"  Games with V5 data:           {games_with_v5}")
    print(f"  Endgame/middlegame moves chk: {moves_checked}")
    print(f"  END_ROOK_BEHIND_PASSER fires: {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    for i, f in enumerate(fires, 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        print(
            f"      passer={f['evidence'].get('passer_square')}({f['evidence'].get('passer_color')}) "
            f"rook {f['evidence'].get('rook_square_played')} → "
            f"{f['evidence'].get('rook_target_square')} "
            f"({f['evidence'].get('perspective')})"
        )
        eb = f.get("stm_eval_before")
        if eb is not None:
            label = "balanced" if abs(eb) <= 300 else ("losing" if eb < 0 else "winning")
            print(f"      stm_eval_before: {eb:+d}cp ({label})")
        if f["verdict"] != "OK":
            print(f"      VERDICT: {f['verdict']}")
        print()

    if bad_count > 0:
        print("=" * 70)
        print(f"ABORT: {bad_count} geometric mismatches.")
        print("Do NOT mark END_ROOK_BEHIND_PASSER as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: single passer on board, pawn on claimed square,")
    print("    rook of moving side on claimed from-square, target on same")
    print("    file as passer, target on BEHIND side, perspective matches")
    print("    own-vs-opp passer correctly.")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp; losing kept per Mohit directive).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing (whether END_ROOK_BEHIND_PASSER actually")
    print("    anchors the caption vs being shadowed).")
    print("  - LLM Tier 1 polish output preserving protected entities.")
    print("  - 1200-test compliance of the rendered caption text.")
    print("  - Whether the played move was defensible for non-Tarrasch")
    print("    reasons (manual review).")


if __name__ == "__main__":
    asyncio.run(main())
