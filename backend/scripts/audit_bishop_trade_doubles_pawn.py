"""
Per-fire audit for OP_BISHOP_TRADE_DOUBLES_PAWN detector.

Phase 6 (Mohit signoff 2026-05-18): cross-opening structural-concession
detector. Fires when a bishop trade forces a pawn recapture that doubles
the opponent's pawns (the English / Nimzo / Vienna Bxc3 pattern).

Locked rule per [[per-fire-audit-pattern]] + [[audit-coverage-tracks-surface]]:
the detector must produce 0 geometric mismatches on a real-corpus pass
before being marked as board-verified.

Usage on prod server:
  docker exec chess-coach-backend python scripts/audit_bishop_trade_doubles_pawn.py

Manual review checklist per fire:
  - Did the player really trade a bishop for an enemy minor (knight/bishop)?
  - Does the recapture pawn come from a DIFFERENT file (so doubling
    actually happens)?
  - Are the enemy pawns on the capture-square's file now ≥2 after
    the recapture?
  - Was the captured square not already on a doubled file?
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
    _p_op_bishop_trade_doubles_pawn,
    _pawns_on_file,
)


_PIECE_TYPE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}


def _facts_from_move(m: dict, board_before: chess.Board) -> dict:
    """Reconstruct the minimal facts dict the detector needs. V5 move
    records don't store moving_piece_type / target_square / from_square /
    is_capture / captured_piece_type as flat fields — we derive them by
    parsing move_san against fen_before.
    """
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
            # Fill captured from board if record lacked it.
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
    """Re-derive the doubled-pawn geometry independently.

    Returns 'OK' or a short reason string for a mismatch.
    """
    cap_sq_name = ev.get("capture_square")
    bishop_from_name = ev.get("bishop_from_square")
    pawn_from_name = ev.get("recapture_pawn_from")
    file_letter = ev.get("doubled_pawn_file")
    enemy_pawns_after = ev.get("enemy_pawns_after_on_file")
    captured = ev.get("captured_piece_type")

    try:
        cap_sq = chess.parse_square(cap_sq_name)
        bishop_from = chess.parse_square(bishop_from_name)
        pawn_from = chess.parse_square(pawn_from_name)
    except (TypeError, ValueError) as e:
        return f"square parse failed: {e}"

    # 1. The bishop_from square must have a bishop of the moving side.
    bp = board_before.piece_at(bishop_from)
    if not bp or bp.piece_type != chess.BISHOP:
        return f"no bishop on {bishop_from_name}"
    if bp.color != board_before.turn:
        return f"bishop on {bishop_from_name} wrong color"

    # 2. The capture_square must have an enemy minor piece (knight/bishop).
    cap_piece = board_before.piece_at(cap_sq)
    if not cap_piece:
        return f"nothing on {cap_sq_name} to capture"
    if cap_piece.color == board_before.turn:
        return f"piece on {cap_sq_name} is own color"
    if cap_piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return f"piece on {cap_sq_name} is {cap_piece.symbol()}, not a minor piece"
    expected_captured = "knight" if cap_piece.piece_type == chess.KNIGHT else "bishop"
    if captured != expected_captured:
        return f"captured_piece_type mismatch: claim {captured}, board {expected_captured}"

    # 3. Pawn_from must have an enemy pawn.
    pp = board_before.piece_at(pawn_from)
    if not pp or pp.piece_type != chess.PAWN:
        return f"no pawn on {pawn_from_name}"
    if pp.color == board_before.turn:
        return f"pawn on {pawn_from_name} is own color (should be opp)"

    # 4. pawn_from must be on a DIFFERENT file from the capture square.
    if chess.square_file(pawn_from) == chess.square_file(cap_sq):
        return f"recapture pawn on same file as capture (no doubling)"

    # 5. Doubled-pawn file letter must match capture square's file.
    expected_file_letter = chess.FILE_NAMES[chess.square_file(cap_sq)]
    if file_letter != expected_file_letter:
        return f"file letter mismatch: claim {file_letter}, computed {expected_file_letter}"

    # 6. Replay: push played + recapture, count enemy pawns on cap file.
    try:
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError) as e:
        return f"played_san parse failed: {e}"
    if played_move.from_square != bishop_from or played_move.to_square != cap_sq:
        return "played move doesn't match bishop_from -> capture_sq"

    bcopy = board_before.copy()
    bcopy.push(played_move)
    # Find the recapture move from pawn_from to cap_sq.
    recapture = None
    for m in bcopy.legal_moves:
        if m.from_square == pawn_from and m.to_square == cap_sq:
            recapture = m
            break
    if recapture is None:
        return f"no legal pawn recapture from {pawn_from_name} to {cap_sq_name}"
    bcopy.push(recapture)

    enemy_color = not board_before.turn
    actual_count = _pawns_on_file(bcopy, chess.square_file(cap_sq), enemy_color)
    if actual_count != enemy_pawns_after:
        return f"enemy pawn count on file mismatch: claim {enemy_pawns_after}, computed {actual_count}"
    if actual_count < 2:
        return f"final pawn count {actual_count} < 2 (no doubling actually occurred)"

    # 7. Before the trade, file must NOT have already been doubled.
    pre_count = _pawns_on_file(board_before, chess.square_file(cap_sq), enemy_color)
    if pre_count >= 2:
        return f"file already had {pre_count} enemy pawns BEFORE trade — no new doubling"

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
                ev = _p_op_bishop_trade_doubles_pawn(facts, board)
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
    print(f"  OP_BISHOP_TRADE_DOUBLES_PAWN fires: {len(fires)}")
    print()

    ok_count = sum(1 for f in fires if f["verdict"] == "OK")
    bad_count = len(fires) - ok_count
    print(f"  Geometric verification: {ok_count} OK, {bad_count} mismatches")
    print()

    # Cap output to first 30 fires for readability; print summary tail.
    show_n = min(len(fires), 30)
    for i, f in enumerate(fires[:show_n], 1):
        marker = "[OK]" if f["verdict"] == "OK" else "[BAD]"
        print(f"  [{i}] {marker} game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
        print(f"      FEN:  {f['fen_before']}")
        ev = f["evidence"]
        print(
            f"      {ev.get('bishop_from_square')} x {ev.get('capture_square')} "
            f"({ev.get('captured_piece_type')}); recapture {ev.get('recapture_pawn_from')} "
            f"-> doubled pawns on {ev.get('doubled_pawn_file')}-file "
            f"(count {ev.get('enemy_pawns_after_on_file')})"
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
        # Print ALL bad ones for debugging.
        bad = [f for f in fires if f["verdict"] != "OK"]
        print("=" * 70)
        print(f"BAD fires ({len(bad)}):")
        for i, f in enumerate(bad, 1):
            print(f"  [{i}] game={f['game_id'][:8]} move={f['move_number']}.{f['move_san']}")
            print(f"      FEN: {f['fen_before']}")
            print(f"      VERDICT: {f['verdict']}")
        print()
        print(f"ABORT: {bad_count} geometric mismatches.")
        print("Do NOT mark OP_BISHOP_TRADE_DOUBLES_PAWN as board-verified until 0 mismatches.")
        sys.exit(1)
    print("=" * 70)
    print(f"All {len(fires)} fires passed geometric verification.")
    print()
    print("Audit scope COVERS:")
    print("  - Geometric: bishop of moving side on bishop_from, enemy minor")
    print("    on capture_sq, enemy pawn on recapture_pawn_from, pawn on a")
    print("    DIFFERENT file from capture (so doubling occurs), played move")
    print("    is BxN/BxB on capture_sq, final enemy pawn count on file >= 2,")
    print("    file was NOT already doubled pre-trade.")
    print("  - Pedagogical purity: STM eval bracket shown per fire (production")
    print("    detector drops STM > +300cp; losing kept per Mohit directive).")
    print()
    print("Audit scope does NOT cover:")
    print("  - Resolver routing (whether OP_BISHOP_TRADE_DOUBLES_PAWN actually")
    print("    anchors the caption vs being shadowed by higher-priority).")
    print("  - LLM Tier 1 polish output preserving protected entities.")
    print("  - 1200-test compliance of the rendered caption text.")
    print("  - Whether the trade was the engine's #1 move (engine_endorsement")
    print("    tracked but not gated as the fire condition).")


if __name__ == "__main__":
    asyncio.run(main())
