"""
snapshot_surface2_pwc.py — PWC end-to-end replay net (Mohit 2026-05-28).

Surface-1 (snapshot_surface1.py) covers the V5 base narrative.
Surface-2 (this script) replays REAL coach_sessions from MongoDB through
the central layer the way `live_v5_teaching` does in production, then
dumps per-move output so we can verify:

  - Pipeline runs cleanly end-to-end on real session data
  - Opening / named-trap detection fires when it should
  - No exceptions, no empty captions where R-rule should have rendered
  - Trap-recognition state machine advances correctly across moves
  - Central-layer facts populated as expected

Why this is needed (and why snapshot_pwc.py alone is not enough):
  - snapshot_pwc.py uses synthesised scenarios — good for unit-style
    regression, but cannot expose composition bugs that only surface
    when a real session walks through all 30-60 moves.
  - This script reads coach_sessions directly and walks the move_history
    through `build_move_teaching_decision`, threading state across moves
    via CrossMoveState, mirroring what `v5_teaching_decision_for_live_move`
    does live.

Usage (inside the backend container):
  python /app/backend/scripts/snapshot_surface2_pwc.py --tag today
  python /app/backend/scripts/snapshot_surface2_pwc.py --diff TAG_A TAG_B
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get(
    "MONGO_URL",
    "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
)
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

_SNAP_DIR = Path("/app/backend/scripts/_snapshots")

# Sessions with substantial move histories — picked to span opening/middle/endgame
SESSION_IDS: List[str] = [
    "34e4b433-3132-40c5-8b09-7dd7b0a7ddde",   # 32 moves, white
    "77822c0b-0275-491c-9058-15f92c7b7ee9",   # 22 moves, white
    "1b651022-03c2-469d-95d1-aeb6d7827a23",   # 100 moves, white
    "15e6bce7-52a6-4df5-b1a8-6c2c33e2bcd3",   # 16 moves, white
]


def _hash(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()[:12]


def _to_cp(v: Any) -> Optional[int]:
    """Convert session-stored pawn eval (e.g. 0.33) to centipawns (33)."""
    if v is None:
        return None
    try:
        return int(round(float(v) * 100))
    except Exception:
        return None


async def _capture(tag: str) -> int:
    from services.caption_pipeline import (
        build_move_teaching_decision,
        MoveInputs,
        CrossMoveState,
    )

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=8000)[DB_NAME]
    out: Dict[str, Any] = {}

    for sid in SESSION_IDS:
        s = await db.coach_sessions.find_one({"session_id": sid})
        if not s:
            out[sid] = {"error": "not found"}
            continue

        user_color = (s.get("user_color") or "white").lower()
        user_is_white = user_color == "white"
        move_history = s.get("move_history") or []

        rows: List[Dict[str, Any]] = []
        # Build live state mirroring live_v5_teaching's CrossMoveState.
        state = CrossMoveState(
            fired_principles=set(),
            fired_state_keys=set(),
            active_trap=None,
            active_trap_step_cursor=0,
            active_trap_setup_completed_by_user=False,
        )
        san_history: List[str] = []
        board = chess.Board()

        for idx, mv in enumerate(move_history):
            san = mv.get("move") or ""
            fen_before = mv.get("fen_before") or ""
            by = mv.get("by") or "player"
            is_best = bool(mv.get("is_best_move"))
            best = mv.get("best_move") or ""
            eb = _to_cp(mv.get("eval_before"))
            ea = _to_cp(mv.get("eval_after"))

            # Heuristic cp_loss: 0 if best, else |eval_swing| (rough).
            cp_loss = 0
            if not is_best and eb is not None and ea is not None:
                # Eval is white-POV; for black moves, swing flips sign.
                swing = (ea - eb)
                if not user_is_white if by == "player" else user_is_white:
                    swing = -swing
                cp_loss = max(0, -swing)  # negative for the mover = loss
                if cp_loss > 500:
                    cp_loss = 500  # cap clamping

            mover_is_user = (by == "player")
            mover_is_white = board.turn == chess.WHITE

            try:
                inputs = MoveInputs(
                    fen_before=fen_before,
                    played_san=san,
                    mover_is_user=mover_is_user,
                    mover_is_white=mover_is_white,
                    user_color=user_color,
                    full_move_number=board.fullmove_number,
                    move_history_san=list(san_history),
                    prev_move_san=(san_history[-1] if san_history else None),
                    best_move_san=best or None,
                    eval_before_cp=eb,
                    eval_after_cp=ea,
                    cp_loss=cp_loss,
                    pv_after_played=[],
                    pv_after_best=[],
                )
                d = build_move_teaching_decision(inputs, state)
                caption = (d.text.caption or "").strip() if d.text else ""
                rows.append({
                    "i": idx,
                    "fmn": board.fullmove_number,
                    "san": san,
                    "by": by,
                    "is_best": is_best,
                    "cp_loss": cp_loss,
                    "should_skip": bool(d.should_skip),
                    "caption": caption,
                    "caption_hash": _hash(caption),
                    "good_move_reason": (d.debug_facts or {}).get("good_move_reason"),
                    "primary_reason": (d.debug_facts or {}).get("primary_reason"),
                    "trap_active": (state.active_trap or {}).get("name") if state.active_trap else None,
                    "opening_name": (d.debug_facts or {}).get("opening_name"),
                    "opening_theory_name": (d.debug_facts or {}).get("opening_theory_name"),
                    "curriculum_deviation": bool((d.debug_facts or {}).get("curriculum_deviation_clause")),
                })
                # Apply explicit StateMutations dataclass fields (the
                # central layer returns these so callers can persist atomically).
                muts = getattr(d, "state_mutations", None)
                if muts is not None:
                    if muts.active_trap_cleared:
                        state.active_trap = None
                    elif muts.active_trap_after is not None:
                        state.active_trap = muts.active_trap_after
                    state.active_trap_step_cursor = int(muts.active_trap_step_cursor_after or 0)
                    state.active_trap_setup_completed_by_user = bool(
                        muts.active_trap_setup_completed_by_user_after
                    )
                    state.fired_principles |= set(muts.fired_principles_added or set())
                    state.fired_state_keys |= set(muts.fired_state_keys_added or set())
            except Exception as e:
                rows.append({
                    "i": idx, "fmn": board.fullmove_number, "san": san, "by": by,
                    "error": repr(e)[:200],
                })

            # Advance board
            try:
                board.push_san(san)
                san_history.append(san)
            except Exception as e:
                rows.append({"i": idx, "san": san, "push_error": repr(e)[:120]})
                break

        out[sid] = {
            "user_color": user_color,
            "n_moves": len(rows),
            "rows": rows,
        }

    _SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = _SNAP_DIR / f"surface2_pwc_{tag}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    n_moves = sum(v.get("n_moves", 0) for v in out.values() if isinstance(v, dict))
    print(f"[snapshot_surface2_pwc] wrote {path} | sessions={len(SESSION_IDS)} moves={n_moves}")
    return 0


def _diff(tag_a: str, tag_b: str) -> int:
    pa = _SNAP_DIR / f"surface2_pwc_{tag_a}.json"
    pb = _SNAP_DIR / f"surface2_pwc_{tag_b}.json"
    a = json.loads(pa.read_text(encoding="utf-8"))
    b = json.loads(pb.read_text(encoding="utf-8"))

    n_total = 0
    n_text = 0
    n_reason = 0
    changes: List[str] = []
    for sid in SESSION_IDS:
        ra = {(_m.get("i"), _m.get("san")): _m for _m in (a.get(sid, {}) or {}).get("rows", [])}
        rb = {(_m.get("i"), _m.get("san")): _m for _m in (b.get(sid, {}) or {}).get("rows", [])}
        for key in sorted(set(ra) | set(rb), key=lambda k: (k[0] or 0, str(k[1]))):
            ma, mb = ra.get(key, {}), rb.get(key, {})
            n_total += 1
            h_a, h_b = ma.get("caption_hash"), mb.get("caption_hash")
            gr_a, gr_b = ma.get("good_move_reason"), mb.get("good_move_reason")
            if h_a != h_b:
                n_text += 1
                changes.append(
                    f"\n{sid} i{key[0]} m{ma.get('fmn')} {key[1]} ({ma.get('by')})\n"
                    f"    A: {ma.get('caption','')!r}\n"
                    f"    B: {mb.get('caption','')!r}"
                )
            if gr_a != gr_b:
                n_reason += 1

    print(f"=== surface2_pwc diff {tag_a} -> {tag_b} ===")
    print(f"moves compared: {n_total}")
    print(f"  caption changed: {n_text}")
    print(f"  good_move_reason changed: {n_reason}")
    print("\n".join(changes[:60]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--diff", nargs=2, metavar=("TAG_A", "TAG_B"))
    args = ap.parse_args()
    if args.diff:
        return _diff(args.diff[0], args.diff[1])
    if args.tag:
        return asyncio.run(_capture(args.tag))
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
