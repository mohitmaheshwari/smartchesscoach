"""
Per-fire audit for OP_F2_F7_STRIKE detector.

Phase 6 (Mohit signoff 2026-05-18): cross-opening tactical-strike
detector. Fires when a capture on f7 (white attacker) or f2 (black
attacker) succeeds against a square defended only by the enemy king.

Locked rule per [[per-fire-audit-pattern]] + [[audit-coverage-tracks-surface]]:
the detector must produce 0 geometric mismatches on a real-corpus pass
before being marked as board-verified.

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_f2_f7_strike.py

Manual review checklist per fire:
  - Was the strike square f7 (white capturing) or f2 (black capturing)?
  - Was the strike square defended ONLY by the enemy king before the
    capture (no knight, no bishop, no other piece)?
  - Did the strike win material (SEE >= 0)?
  - Was this in opening or middlegame (not endgame)?
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
    _p_op_f2_f7_strike,
    static_exchange_eval,
    _see_for_played_move,
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
        if board_before.is_capture(played_move) and not captured_piece_type:
            cap = board_before.piece_at(played_move.to_square)
            if cap:
                captured_piece_type = _PIECE_TYPE_NAMES.get(cap.piece_type, "")
            is_capture_flag = True
        elif board_before.is_capture(played_move):
            is_capture_flag = True
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


def _verify_geometry(board_before: chess.Board, played_san: str, ev: dict) -> str:
    """Re-derive the f2/f7 strike geometry independently.

    Returns 'OK' or a short reason string for a mismatch.
    """
    strike_name = ev.get("strike_square")
    attacker_from_name = ev.get("attacker_from_square")
    king_sq_name = ev.get("enemy_king_square")
    claimed_see = ev.get("see_cp")
    claimed_attacker_piece = ev.get("attacker_piece_type")

    try:
        strike_sq = chess.parse_square(strike_name)
        attacker_from = chess.parse_square(attacker_from_name)
        king_sq = chess.parse_square(king_sq_name)
    except (TypeError, ValueError) as e:
        return f"square parse failed: {e}"

    us = board_before.turn
    them = not us

    # 1. Strike square is f7 if mover is white, f2 if mover is black.
    expected_strike = "f7" if us == chess.WHITE else "f2"
    if strike_name != expected_strike:
        return f"strike square wrong: claim {strike_name}, expected {expected_strike}"

    # 2. Attacker_from must have a piece of moving side.
    attacker_piece = board_before.piece_at(attacker_from)
    if not attacker_piece:
        return f"no piece on {attacker_from_name}"
    if attacker_piece.color != us:
        return f"piece on {attacker_from_name} wrong color"
    actual_attacker_piece_name = _PIECE_TYPE_NAMES[attacker_piece.piece_type]
    if claimed_attacker_piece and claimed_attacker_piece != actual_attacker_piece_name:
        return (
            f"attacker piece type mismatch: claim {claimed_attacker_piece}, "
            f"computed {actual_attacker_piece_name}"
        )

    # 3. Enemy king must be on the claimed square.
    actual_king_sq = board_before.king(them)
    if actual_king_sq != king_sq:
        return (
            f"enemy king square mismatch: claim {king_sq_name}, "
            f"computed {chess.square_name(actual_king_sq) if actual_king_sq is not None else 'None'}"
        )

    # 4. Defenders of strike_sq before the move must be ONLY the enemy king.
    defenders = list(board_before.attackers(them, strike_sq))
    king_defenders = [s for s in defenders if board_before.piece_at(s) and board_before.piece_at(s).piece_type == chess.KING]
    non_king_defenders = [s for s in defenders if board_before.piece_at(s) and board_before.piece_at(s).piece_type != chess.KING]
    if non_king_defenders:
        names = [chess.square_name(s) for s in non_king_defenders]
        return f"non-king defenders on {strike_name}: {names}"
    if not king_defenders:
        return f"no king defender on {strike_name}"

    # 5. Replay the played move and confirm it lands on strike_sq.
    try:
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError) as e:
        return f"played_san parse failed: {e}"
    if played_move.to_square != strike_sq:
        return f"played move doesn't capture on {strike_name}"
    if played_move.from_square != attacker_from:
        return f"played move from-square doesn't match claim"
    if not board_before.is_capture(played_move):
        return "played move not a capture"

    # 6. SEE must be non-negative.
    actual_see = _see_for_played_move(board_before, played_move)
    if actual_see is None:
        return "SEE returned None"
    if claimed_see is not None and actual_see != claimed_see:
        return f"SEE mismatch: claim {claimed_see}, computed {actual_see}"
    if actual_see < 0:
        return f"SEE negative ({actual_see}) — should have been filtered"

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
                ev = _p_op_f2_f7_strike(facts, board)
            except Exception as e:
                print(f"  DETECTOR CRASH on {a['game_id'][:8]} move {m.get('move_number')}: {e}")
                continue
            if not ev:
                continue
            verdict = _verify_geometry(board, m.get("move_san") or "", ev["evidence"])
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
    print(f"  OP_F2_F7_STRIKE fires:        {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    show_n = min(len(fires), 40)
    for i, f in enumerate(fires[:show_n], 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        ev = f["evidence"]
        print(
            f"      strike={ev.get('strike_square')} "
            f"attacker={ev.get('attacker_piece_type')} from {ev.get('attacker_from_square')} "
            f"king={ev.get('enemy_king_square')} SEE={ev.get('see_cp')}cp"
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
        print("Do NOT mark OP_F2_F7_STRIKE as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: strike sq is f7/f2 matched to mover color, attacker")
    print("    of moving side on attacker_from, enemy king on king_sq,")
    print("    strike sq defended only by enemy king pre-move, played move")
    print("    captures on strike_sq, SEE >= 0.")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp; losing kept per Mohit directive).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing.")
    print("  - LLM polish output.")
    print("  - 1200-test compliance of rendered caption text.")
    print("  - Pure-threat strikes (Bc4 eyes f7 without capturing) — v1 covers")
    print("    captures only; threat-only is a future v2.")


if __name__ == "__main__":
    asyncio.run(main())
