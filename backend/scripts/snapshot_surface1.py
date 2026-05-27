"""
snapshot_surface1.py — PWC BASE-NARRATIVE regression net (Mohit 2026-05-27).

Captures the output of shared_coaching_v5.generate_move_coaching() — the
engine behind PWC's main per-move narrative (surface 1) — across a fixed
corpus of REAL analyzed games, one row per USER move.

Why this exists (and why it's not a dup of snapshot_pwc.py):
  - snapshot_pwc.py covers the central-layer surfaces: the flag-gated
    v5_teaching wedge, coach_move narration, and Socratic feedback.
  - This tool covers the ALWAYS-ON base narrative, which today runs on a
    SEPARATE engine (move_critique -> coaching_policy -> coaching_voice),
    NOT the central layer. See [[project_pwc_runs_second_coaching_engine]].
  - The approved "full replacement" (Mohit 2026-05-27) reroutes this base
    narrative through build_move_teaching_decision. That changes ~100% of
    PWC captions. THIS net is the before/after evidence: baseline the
    current critique-engine output, do the rewrite, diff, and present
    every changed caption for sign-off. Real games (not synthetic) so the
    diff reflects what users actually see.

Usage (inside the backend container):
  python /app/backend/scripts/snapshot_surface1.py --tag baseline_critique
  python /app/backend/scripts/snapshot_surface1.py --tag post_central
  python /app/backend/scripts/snapshot_surface1.py --diff baseline_critique post_central

Captured per user move (the fields downstream/frontend consume):
  severity, suppress, fundamental_violated, fundamental_label,
  socratic_question, socratic_hint, hide_best_move, has_candidate_moves,
  narrative (full text) + narrative_hash.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get(
    "MONGO_URL",
    "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
)
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

_SNAP_DIR = Path("/app/backend/scripts/_snapshots")

# Deterministic corpus — 20 analyzed games spanning openings/phases/ratings.
# Pinned game (game_692ab776c5b1) included for continuity with the probe.
CORPUS: List[str] = [
    "game_692ab776c5b1", "game_85bd0169aa4f", "game_b5d23694a803",
    "game_f2c022e03856", "game_ef9f422a062d", "game_74fdbd74c468",
    "game_4177951c757f", "game_bc41022831e0", "game_4c0f48f6cc0a",
    "game_8efcc1db5aa4", "game_94ea9cf7bc33", "game_ec4ba8b79b91",
    "game_665fd66c997a", "game_5e161a7440aa", "game_e9120f8eaa1d",
    "game_b19b724011a2", "game_efa6a7a5d0bf", "game_5da7dc72d514",
    "game_214f16ba655d", "game_8e1294767490",
]


def _fen4(fen: str) -> str:
    return " ".join(fen.split()[:4])


def _hash(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()[:12]


async def _capture(tag: str) -> int:
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    try:
        from services.game_decryption_v5_service import detect_phase
    except Exception:
        detect_phase = None

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=8000)[DB_NAME]
    out: Dict[str, Any] = {}

    for gid in CORPUS:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1, "user_color": 1})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            out[gid] = {"error": "not found"}
            continue
        pgn = game.get("pgn") or ""
        user_color = (game.get("user_color") or "white").lower()
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}

        try:
            pgn_game = chess.pgn.read_game(io.StringIO(pgn))
        except Exception as e:
            out[gid] = {"error": f"pgn parse: {e}"}
            continue
        if pgn_game is None:
            out[gid] = {"error": "empty pgn"}
            continue

        rows: List[Dict[str, Any]] = []
        board = pgn_game.board()
        history: List[str] = []
        user_is_white = (user_color == "white")
        for mv in pgn_game.mainline_moves():
            is_user = (board.turn == chess.WHITE) == user_is_white
            try:
                san = board.san(mv)
            except Exception:
                break
            if is_user:
                me = by_fen.get(_fen4(board.fen()))
                if me is not None:
                    cp_loss = int(me.get("cp_loss") or 0)
                    best = me.get("best_move")
                    pv_p = me.get("pv_after_played") or []
                    pv_b = me.get("pv_after_best") or []
                    fmn = board.fullmove_number
                    phase = "opening"
                    if detect_phase is not None:
                        try:
                            phase = detect_phase(board, fmn)
                        except Exception:
                            pass
                    # DB move_evaluations store evals in centipawns (white-POV);
                    # cp_loss is the same scale. Pass raw to eval_*_cp so the
                    # central narrative matches production fidelity.
                    _eb = me.get("eval_before")
                    _ea = me.get("eval_after")
                    try:
                        c = await generate_move_coaching(
                            board_before=board.copy(), move=mv, best_move_san=best,
                            pv_after_played=pv_p, pv_after_best=pv_b, cp_loss=cp_loss,
                            phase=phase, is_user_move=True,
                            context=CoachingContext.LIVE_AFTER_USER, user_color=user_color,
                            move_history_san=list(history),
                            eval_before_cp=int(_eb) if isinstance(_eb, (int, float)) else None,
                            eval_after_cp=int(_ea) if isinstance(_ea, (int, float)) else None,
                        )
                        narr = (getattr(c, "narrative", "") or "").strip()
                        rows.append({
                            "mv": fmn, "san": san, "cp_loss": cp_loss,
                            "severity": getattr(c, "severity", None),
                            "suppress": bool(getattr(c, "suppress", False)),
                            "fundamental_violated": getattr(c, "fundamental_violated", None),
                            "fundamental_label": getattr(c, "fundamental_label", None),
                            "socratic_question": getattr(c, "socratic_question", None),
                            "socratic_hint": getattr(c, "socratic_hint", None),
                            "hide_best_move": bool(getattr(c, "hide_best_move", False)),
                            "has_candidate_moves": bool(getattr(c, "candidate_moves", None)),
                            "narrative": narr,
                            "narrative_hash": _hash(narr),
                        })
                    except Exception as e:
                        rows.append({"mv": fmn, "san": san, "error": repr(e)[:160]})
            board.push(mv)
            history.append(san)
        out[gid] = {"user_color": user_color, "moves": rows}

    _SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = _SNAP_DIR / f"surface1_{tag}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    n_moves = sum(len(v.get("moves", [])) for v in out.values() if isinstance(v, dict))
    print(f"[snapshot_surface1] wrote {path} | games={len(CORPUS)} user_moves={n_moves}")
    return 0


def _diff(tag_a: str, tag_b: str) -> int:
    pa = _SNAP_DIR / f"surface1_{tag_a}.json"
    pb = _SNAP_DIR / f"surface1_{tag_b}.json"
    a = json.loads(pa.read_text(encoding="utf-8"))
    b = json.loads(pb.read_text(encoding="utf-8"))

    n_total = 0
    n_sev = 0
    n_supp = 0
    n_text = 0
    changes: List[str] = []
    for gid in CORPUS:
        ra = {(_m.get("mv"), _m.get("san")): _m for _m in (a.get(gid, {}) or {}).get("moves", [])}
        rb = {(_m.get("mv"), _m.get("san")): _m for _m in (b.get(gid, {}) or {}).get("moves", [])}
        for key in sorted(set(ra) | set(rb), key=lambda k: (k[0] or 0, str(k[1]))):
            ma = ra.get(key, {})
            mb = rb.get(key, {})
            n_total += 1
            sev_a, sev_b = ma.get("severity"), mb.get("severity")
            sup_a, sup_b = ma.get("suppress"), mb.get("suppress")
            h_a, h_b = ma.get("narrative_hash"), mb.get("narrative_hash")
            if sev_a != sev_b:
                n_sev += 1
            if sup_a != sup_b:
                n_supp += 1
            if h_a != h_b:
                n_text += 1
            if (sev_a != sev_b) or (sup_a != sup_b) or (h_a != h_b):
                changes.append(
                    f"\n{gid} m{key[0]} {key[1]}  sev {sev_a}->{sev_b}  supp {sup_a}->{sup_b}\n"
                    f"    A: {ma.get('narrative','')!r}\n"
                    f"    B: {mb.get('narrative','')!r}"
                )

    print(f"=== surface1 diff {tag_a} -> {tag_b} ===")
    print(f"user moves compared: {n_total}")
    print(f"  severity changed : {n_sev}")
    print(f"  suppress changed : {n_supp}")
    print(f"  narrative changed: {n_text}")
    print("\n".join(changes))
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
