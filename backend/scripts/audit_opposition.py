"""
Per-fire audit for END_OPPOSITION detector.

Locked rule (per [[per-fire-audit-pattern]] + [[audit-coverage-tracks-surface]]):
the detector must produce 0 geometric mismatches on a real-corpus
pass before being marked as board-verified. AND each surviving
fire must be manually reviewed for pedagogical purity (is this a
genuine Opposition teaching moment, or technically true but
practically irrelevant?).

This script walks every analyzed game in MongoDB, reconstructs the
caption_facts shape from each move record's `decryption_v5_data`
entry, runs `_p_end_opposition` on every endgame move, and prints
each fire with the FEN, the evidence, and a one-line geometric
verification check.

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_opposition.py

Manual review checklist per fire:
  - Is your king genuinely outside opposition before the move?
  - Does the engine-best king move REALLY land on an opposition square?
  - Did the played move have any reasonable alternative justification?
  - Would a 1200 player learn something portable from this caption?

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
    _p_end_opposition,
    _kings_in_opposition,
)


def _facts_from_move(m: dict) -> dict:
    """Reconstruct the minimal facts dict the detector needs from a
    `decryption_v5_data` move record. eval_before is fed as the
    white-POV eval (the detector flips per-side internally).
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
    """Re-derive the opposition geometry and report whether it holds.
    Returns 'OK' or a short reason string for a mismatch.
    """
    your_king_name = ev.get("your_king_square")
    their_king_name = ev.get("their_king_square")
    target_name = ev.get("your_king_should_move_to")
    claimed_kind = ev.get("opposition_kind")

    try:
        your_king = chess.parse_square(your_king_name)
        their_king = chess.parse_square(their_king_name)
        target = chess.parse_square(target_name)
    except (TypeError, ValueError) as e:
        return f"square parse failed: {e}"

    # Check: your king is genuinely on the claimed square.
    yk_piece = board.piece_at(your_king)
    if not yk_piece or yk_piece.piece_type != chess.KING:
        return f"no king on {your_king_name}"

    # Check: their king is genuinely on the claimed square.
    tk_piece = board.piece_at(their_king)
    if not tk_piece or tk_piece.piece_type != chess.KING:
        return f"no king on {their_king_name}"
    if yk_piece.color == tk_piece.color:
        return f"both kings claimed same color"

    # Check: kings should NOT already be in opposition before the move.
    if _kings_in_opposition(your_king, their_king):
        return f"kings already in opposition shape before move"

    # Check: best-move target lands in opposition.
    computed_kind = _kings_in_opposition(target, their_king)
    if not computed_kind:
        return f"target {target_name} not in opposition with {their_king_name}"
    if claimed_kind and computed_kind != claimed_kind:
        return f"opposition_kind mismatch: claimed {claimed_kind}, computed {computed_kind}"

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
                ev = _p_end_opposition(facts, board)
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
    print(f"  Games scanned:        {total_games}")
    print(f"  Games with V5 data:   {games_with_v5}")
    print(f"  Endgame moves checked: {moves_checked}")
    print(f"  END_OPPOSITION fires: {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    for i, f in enumerate(fires, 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        print(f"      your_king={f['evidence'].get('your_king_square')} → "
              f"{f['evidence'].get('your_king_should_move_to')} "
              f"(faces theirs on {f['evidence'].get('their_king_square')}, "
              f"{f['evidence'].get('opposition_kind')} opposition)")
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
        print("Do NOT mark END_OPPOSITION as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: both kings present and on claimed squares,")
    print("    kings not already in opposition before the move,")
    print("    best-move target lands in opposition shape (direct/distant/diagonal).")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing (whether END_OPPOSITION actually anchors the")
    print("    caption vs being shadowed by a higher-priority principle).")
    print("  - LLM Tier 1 polish output preserving protected entities.")
    print("  - 1200-test compliance of the rendered caption text.")
    print("  - Whether the played move was defensible for non-opposition reasons.")


if __name__ == "__main__":
    asyncio.run(main())
