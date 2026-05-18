"""
Per-fire audit for OP_TRAPPED_KNIGHT detector.

Phase 6 (Mohit signoff 2026-05-18): cross-opening piece-mobility
detector. Fires when the side-to-move has a knight whose every legal
destination is unsafe (SEE-losing for the moving side).

Locked rule per [[per-fire-audit-pattern]] + [[audit-coverage-tracks-surface]]:
the detector must produce 0 geometric mismatches on a real-corpus pass
before being marked as board-verified.

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_trapped_knight.py

Manual review checklist per fire:
  - Does the side-to-move actually have a knight on the claimed square?
  - Does the knight have at least one legal destination (otherwise it's
    pinned, different lesson)?
  - Is EVERY destination's opp-SEE > 50cp (knight would be lost)?
  - Is there at least one enemy attacker on the knight's current square?
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
    _p_op_trapped_knight,
    static_exchange_eval,
)


_PIECE_TYPE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}


def _facts_from_move(m: dict, board_before: chess.Board) -> dict:
    played_san = m.get("move_san") or ""
    moving_piece_type = ""
    captured_piece_type = m.get("captured_piece_type") or ""
    is_capture_flag = bool(captured_piece_type)
    target_sq_name = ""
    from_sq_name = ""
    try:
        played_move = board_before.parse_san(played_san)
        piece = board_before.piece_at(played_move.from_square)
        if piece:
            moving_piece_type = _PIECE_TYPE_NAMES.get(piece.piece_type, "")
        target_sq_name = chess.square_name(played_move.to_square)
        from_sq_name = chess.square_name(played_move.from_square)
        if board_before.is_capture(played_move):
            is_capture_flag = True
            if not captured_piece_type:
                cap = board_before.piece_at(played_move.to_square)
                if cap:
                    captured_piece_type = _PIECE_TYPE_NAMES.get(cap.piece_type, "")
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        pass

    return {
        "phase":               m.get("phase"),
        "cp_loss":             m.get("cp_loss") or 0,
        "best_move_san":       m.get("best_move_san") or "",
        "played_san":          played_san,
        "moving_piece_color":  "white" if m.get("is_white") else "black",
        "moving_piece_type":   moving_piece_type,
        "captured_piece_type": captured_piece_type,
        "is_capture":          is_capture_flag,
        "is_check":            bool(m.get("is_check")),
        "target_square":       target_sq_name,
        "from_square":         from_sq_name,
        "eval_before_cp":      m.get("eval_before"),
        "mover_is_user":       m.get("is_user_move"),
    }


def _verify_geometry(board_before: chess.Board, ev: dict) -> str:
    """Re-derive the trapped-knight geometry independently.

    Returns 'OK' or a short reason string for a mismatch.
    """
    knight_name = ev.get("trapped_knight_square")
    knight_color_name = ev.get("knight_color")
    claimed_dest_count = ev.get("legal_destination_count")
    claimed_attackers = ev.get("enemy_attacker_squares") or []

    try:
        knight_sq = chess.parse_square(knight_name)
    except (TypeError, ValueError) as e:
        return f"square parse failed: {e}"

    us = board_before.turn
    them = not us
    expected_color_name = "white" if us == chess.WHITE else "black"
    if knight_color_name != expected_color_name:
        return f"knight color mismatch: claim {knight_color_name}, expected {expected_color_name}"

    # 1. Knight of moving side must be on knight_sq.
    p = board_before.piece_at(knight_sq)
    if not p or p.piece_type != chess.KNIGHT:
        return f"no knight on {knight_name}"
    if p.color != us:
        return f"knight on {knight_name} wrong color"

    # 2. Re-enumerate legal destinations from knight_sq.
    legal_dests = []
    for m in board_before.legal_moves:
        if m.from_square == knight_sq:
            legal_dests.append(m.to_square)
    if not legal_dests:
        return "knight has zero legal moves (should be skipped — pinned)"
    if len(legal_dests) != claimed_dest_count:
        return (
            f"legal destination count mismatch: claim {claimed_dest_count}, "
            f"computed {len(legal_dests)}"
        )

    # 3. EVERY destination must be SEE-unsafe (opp_SEE > 50).
    for dest in legal_dests:
        sim_move = None
        for m in board_before.legal_moves:
            if m.from_square == knight_sq and m.to_square == dest:
                sim_move = m
                break
        if sim_move is None:
            return f"could not re-locate legal move to {chess.square_name(dest)}"
        bcopy = board_before.copy()
        bcopy.push(sim_move)
        opp_see = static_exchange_eval(bcopy, dest, them)
        if opp_see <= 50:
            return (
                f"destination {chess.square_name(dest)} is actually safe "
                f"(opp_SEE={opp_see}cp <= 50)"
            )

    # 4. At least one enemy attacker on knight_sq.
    actual_attackers = list(board_before.attackers(them, knight_sq))
    if not actual_attackers:
        return f"no enemy attackers on {knight_name}"

    actual_attacker_names = sorted([chess.square_name(s) for s in actual_attackers])
    claimed_sorted = sorted(claimed_attackers)
    if actual_attacker_names != claimed_sorted:
        return (
            f"attacker square mismatch: claim {claimed_sorted}, "
            f"computed {actual_attacker_names}"
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
            if m.get("phase") not in ("opening", "middlegame"):
                continue
            fen_before = m.get("fen_before")
            if not fen_before:
                continue
            try:
                board = chess.Board(fen_before)
            except Exception:
                continue
            moves_checked += 1
            facts = _facts_from_move(m, board)
            try:
                ev = _p_op_trapped_knight(facts, board)
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
    print(f"  Opening/middlegame moves chk: {moves_checked}")
    print(f"  OP_TRAPPED_KNIGHT fires:      {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    show_n = min(len(fires), 30)
    for i, f in enumerate(fires[:show_n], 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        ev = f["evidence"]
        print(
            f"      trapped knight={ev.get('trapped_knight_square')} "
            f"({ev.get('knight_color')}); dests={ev.get('legal_destination_count')}; "
            f"enemy attackers={ev.get('enemy_attacker_squares')}"
        )
        eb = f.get("stm_eval_before")
        if eb is not None:
            label = "balanced" if abs(eb) <= 300 else ("losing" if eb < 0 else "winning")
            print(f"      stm_eval_before: {eb:+d}cp ({label})")
        if f["verdict"] != "OK":
            print(f"      VERDICT: {f['verdict']}")
        print()
    if len(fires) > show_n:
        print(f"  ... ({len(fires) - show_n} more fires not printed)")
        print()

    if bad_count > 0:
        bad = [f for f in fires if f["verdict"] != "OK"]
        print("=" * 70)
        print(f"BAD fires ({len(bad)}):")
        for i, f in enumerate(bad, 1):
            print(f"  [{i}] game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
            print(f"      FEN: {f['fen_before']}")
            print(f"      VERDICT: {f['verdict']}")
        print()
        print(f"ABORT: {bad_count} geometric mismatches.")
        print("Do NOT mark OP_TRAPPED_KNIGHT as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: knight of moving side on claimed square, knight")
    print("    has at least one legal destination, EVERY destination's")
    print("    opp_SEE > 50cp (knight would be lost), at least one enemy")
    print("    attacker on knight's current square, attacker squares match.")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing.")
    print("  - Whether the engine's best move actually rescues the knight")
    print("    (engine_endorsement is informational, not gated as fire cond).")
    print("  - Trapped opponent knights (v1 covers own knight only; the")
    print("    'win their knight' surface is left to TAC_HANGING_PIECE).")
    print("  - 1200-test compliance of rendered caption text.")


if __name__ == "__main__":
    asyncio.run(main())
