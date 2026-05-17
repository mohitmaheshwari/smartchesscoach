"""
Per-fire audit for END_RULE_OF_SQUARE detector.

Locked rule (per `feedback_audit_coverage_tracks_surface` + Mohit
signoff on the endgame principles backlog): the detector must produce
0 false positives on a real-corpus pass before being marked as
board-verified.

This script walks every analyzed game in MongoDB, reconstructs the
caption_facts shape from each move record's `decryption_v5_data`
entry, runs `_p_end_rule_of_square` on every endgame move, and prints
each fire with the FEN, the evidence, and a one-line geometric
verification check.

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_rule_of_square.py

The output is meant to be read by hand. Each fire should be checked
against the FEN manually:
  - Is there genuinely a passed pawn on `pawn_square`?
  - Is the king on `king_square_played` really outside the square?
  - Is the engine's recommended `king_should_move_to` really inside?
  - Was the played move genuinely a worse choice for stopping the pawn?

If any fire is a false positive, do NOT mark the detector verified.
Tighten the gate, re-audit.
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
    _p_end_rule_of_square,
    _king_inside_pawn_square,
    _pawn_distance_to_promote,
    _own_passed_pawns,
)


def _facts_from_move(m: dict) -> dict:
    """Reconstruct the minimal facts dict the detector needs from a
    `decryption_v5_data` move record. Only fields _p_end_rule_of_square
    reads are included.

    `eval_before_cp` is the white-POV eval stored by the V5 generator
    (the detector flips per-side internally). Field is named
    `eval_before` in the V5 record but the detector parameter name is
    `eval_before_cp` — keep both aligned.
    """
    return {
        "phase":             m.get("phase"),
        "cp_loss":           m.get("cp_loss") or 0,
        "best_move_san":     m.get("best_move_san") or "",
        "played_san":        m.get("move_san") or "",
        "moving_piece_color": "white" if m.get("is_white") else "black",
        "eval_before_cp":    m.get("eval_before"),
    }


def _verify_geometry(board: chess.Board, ev: dict) -> str:
    """Re-derive the geometric claim and report whether it holds.
    Returns 'OK' or a short reason string for a mismatch.
    """
    pawn_sq_name = ev.get("pawn_square")
    pawn_color_name = ev.get("pawn_color")
    promo_name = ev.get("promotion_square")
    king_played_name = ev.get("king_square_played")
    king_target_name = ev.get("king_should_move_to")
    pawn_dist = ev.get("pawn_distance")
    king_dist_before = ev.get("king_distance_before")
    king_dist_after = ev.get("king_distance_after_best")

    try:
        pawn_sq = chess.parse_square(pawn_sq_name)
        promo_sq = chess.parse_square(promo_name)
        king_played = chess.parse_square(king_played_name)
        king_target = chess.parse_square(king_target_name)
    except Exception as e:
        return f"square parse failed: {e}"

    pawn_color = chess.WHITE if pawn_color_name == "white" else chess.BLACK

    # Check: there is genuinely a pawn of the claimed color on pawn_sq
    p = board.piece_at(pawn_sq)
    if not p:
        return f"no piece on {pawn_sq_name}"
    if p.piece_type != chess.PAWN:
        return f"{pawn_sq_name} is not a pawn (it's a {chess.piece_name(p.piece_type)})"
    if p.color != pawn_color:
        return f"{pawn_sq_name} pawn color mismatch (claimed {pawn_color_name})"

    # Check: that pawn is actually passed
    passed = _own_passed_pawns(board, pawn_color)
    if pawn_sq not in passed:
        return f"{pawn_sq_name} pawn is NOT passed in this position"

    # Check: distances are consistent
    expected_pawn_dist = _pawn_distance_to_promote(pawn_sq, pawn_color)
    if expected_pawn_dist != pawn_dist:
        return f"pawn_distance mismatch: claim {pawn_dist}, computed {expected_pawn_dist}"

    expected_king_dist_before = chess.square_distance(king_played, promo_sq)
    if expected_king_dist_before != king_dist_before:
        return (f"king_distance_before mismatch: claim {king_dist_before}, "
                f"computed {expected_king_dist_before}")

    expected_king_dist_after = chess.square_distance(king_target, promo_sq)
    if expected_king_dist_after != king_dist_after:
        return (f"king_distance_after_best mismatch: claim {king_dist_after}, "
                f"computed {expected_king_dist_after}")

    # Check: king IS outside before, INSIDE after
    if king_dist_before <= pawn_dist:
        return f"king already inside square before move (claim of 'outside' is false)"
    if king_dist_after > pawn_dist:
        return f"king STILL outside square after best move (best move doesn't catch)"

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
            if m.get("phase") != "endgame":
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
                ev = _p_end_rule_of_square(facts, board)
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

    print(f"Audit complete.")
    print(f"  Games scanned:       {total_games}")
    print(f"  Games with V5 data:  {games_with_v5}")
    print(f"  Endgame moves checked: {moves_checked}")
    print(f"  RULE_OF_SQUARE fires: {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    for i, f in enumerate(fires, 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        print(f"      pawn={f['evidence'].get('pawn_square')}({f['evidence'].get('pawn_color')}) "
              f"king {f['evidence'].get('king_square_played')} → "
              f"{f['evidence'].get('king_should_move_to')} "
              f"(dist {f['evidence'].get('king_distance_before')}→{f['evidence'].get('king_distance_after_best')}, "
              f"pawn_dist {f['evidence'].get('pawn_distance')})")
        # Pedagogical purity scope clause (per [[audit-coverage-tracks-surface]]):
        # show STM eval-before so the reviewer can see where each fire
        # sits in the eval bracket. Production gate drops STM > +300cp.
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
        print("Do NOT mark END_RULE_OF_SQUARE as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: passed pawn real, distances consistent, king-outside-")
    print("    before/inside-after-best.")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp via Pass 4 gate added 2026-05-17).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing (whether END_RULE_OF_SQUARE actually anchors")
    print("    the caption vs being shadowed by a higher-priority principle).")
    print("  - LLM Tier 1 polish output preserving protected entities.")
    print("  - 1200-test compliance of the rendered caption text.")


if __name__ == "__main__":
    asyncio.run(main())
