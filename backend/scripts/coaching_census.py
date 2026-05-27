"""Coaching-text producer CENSUS HARNESS (Mohit 2026-05-27).

Proves, by RUNTIME OBSERVATION rather than inspection, exactly which
backend functions execute when coaching text is produced for a move —
for both the REVIEW surface (generate_game_decryption_v5) and the PWC
move-coaching surface (generate_move_coaching + the live_v5_teaching
central-layer entry points).

Why observation, not grep: a static census can miss a producer. This
harness installs sys.settrace and records EVERY backend function that
actually runs in each coaching path. Anything that produces text must
run, so it is captured. It also flags whenever llm_service.call_llm
executes — that is the complete LLM-in-coaching signal.

Output: a per-surface registry of executed functions, with the LLM
flag. Review the registry to classify producers; wire the
allowlist-diff mode into CI so the set stays provably complete.

Usage (inside the backend container):
    docker exec chess-coach-backend python /app/backend/scripts/coaching_census.py
    docker exec chess-coach-backend python /app/backend/scripts/coaching_census.py --json
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Dict, Set, Tuple

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get(
    "MONGO_URL",
    "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
)
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

PINNED_GAME = "game_692ab776c5b1"

# Only record functions defined under the backend tree (exclude vendored
# libs + bytecode caches). This keeps the census to OUR code.
_BACKEND_MARKER = os.sep + "backend" + os.sep


class Tracer:
    """sys.settrace global tracer. Records (relpath, funcname) for every
    'call' event in backend-owned code, into the active surface bucket,
    and flips an LLM flag whenever llm_service.call_llm enters."""

    def __init__(self) -> None:
        self.surface: str = ""
        self.seen: Dict[str, Set[Tuple[str, str]]] = {}
        self.llm_hit: Dict[str, bool] = {}

    def start(self, surface: str) -> None:
        self.surface = surface
        self.seen.setdefault(surface, set())
        self.llm_hit.setdefault(surface, False)
        sys.settrace(self._trace)

    def stop(self) -> None:
        sys.settrace(None)

    def _trace(self, frame, event, arg):
        if event != "call":
            return None
        co = frame.f_code
        fn = co.co_filename
        if _BACKEND_MARKER not in fn or ".venv" in fn or "__pycache__" in fn:
            return None
        # Normalise to a backend-relative path.
        rel = fn.split(_BACKEND_MARKER, 1)[-1].replace(os.sep, "/")
        name = co.co_name
        self.seen[self.surface].add((rel, name))
        # llm_service.call_llm is THE single chokepoint for LLM text
        # (injected call_llm_func variants call it too).
        if name == "call_llm" and rel.endswith("llm_service.py"):
            self.llm_hit[self.surface] = True
        return None


# Coaching modules — used only to HIGHLIGHT likely producers in the
# report (the census records everything; this just sorts signal first).
_COACHING_HINT = (
    "caption_pipeline", "caption_rules", "caption_renderer", "caption_templates",
    "shared_coaching_v5", "coach_commentary", "live_v5_teaching",
    "v5_llm_narrator", "v5_llm_polish", "llm_caption_generator",
    "pv_tactical_analyzer", "coaching_library", "move_comparison",
    "game_decryption_v5_service", "decryption_voice", "shape_detectors",
    "board_state_describer", "best_move_tactic_detector", "pattern_catalog",
)


def _is_coaching(rel: str) -> bool:
    return any(h in rel for h in _COACHING_HINT)


async def main(as_json: bool) -> int:
    tracer = Tracer()
    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=8000)[DB_NAME]

    # ─── Fetch the pinned game for both surfaces ──────────────────
    game = await db.games.find_one({"game_id": PINNED_GAME}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": PINNED_GAME}, {"_id": 0})
    if not game or not analysis:
        print(f"ERROR: pinned game {PINNED_GAME} not found")
        return 2
    pgn = game.get("pgn", "")
    user_color = game.get("user_color", "white")
    move_evals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []

    # ─── SURFACE 1: REVIEW (full per-move decryption pipeline) ────
    from services.game_decryption_v5_service import generate_game_decryption_v5
    tracer.start("review")
    try:
        await generate_game_decryption_v5(
            pgn, user_color, move_evals, game.get("user_id") or "", db,
            game_id=PINNED_GAME,
        )
    finally:
        tracer.stop()

    # ─── SURFACE 2: PWC move coaching (the live entry points) ─────
    # Use a representative mistake position from the same game.
    rec = next(
        (m for m in (analysis.get("decryption_v5_data") or [])
         if m.get("is_user_move") and m.get("move_san")),
        None,
    )
    if rec:
        from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
        from services.live_v5_teaching import (
            v5_teaching_decision_for_live_move,
            socratic_feedback_for_live_move,
            coach_move_narration_for_live_move,
        )
        import chess
        fen = rec["fen_before"]
        san = rec["move_san"]
        board = chess.Board(fen)
        try:
            mv = board.parse_san(san)
        except Exception:
            mv = None

        tracer.start("pwc")
        try:
            if mv is not None:
                try:
                    await generate_move_coaching(
                        board_before=board, move=mv,
                        best_move_san=rec.get("best_move_san"),
                        pv_after_played=rec.get("pv_after_played") or [],
                        pv_after_best=rec.get("pv_after_best") or [],
                        cp_loss=int(rec.get("cp_loss") or 0),
                        phase=rec.get("phase", "middlegame"),
                        is_user_move=True,
                        context=CoachingContext.LIVE_AFTER_USER,
                        user_color=user_color,
                    )
                except Exception as e:
                    print(f"[pwc] generate_move_coaching note: {e}")
            user_doc = {"feature_flags": {"pwc_v5_teaching": {"enabled": True}}, "color_played": user_color}
            session_doc = {"user_id": "census", "user_color": user_color}
            try:
                v5_teaching_decision_for_live_move(
                    fen_before=fen, played_san=san, best_move_san=rec.get("best_move_san"),
                    eval_before_cp=rec.get("eval_before"), eval_after_cp=rec.get("eval_after"),
                    cp_loss=int(rec.get("cp_loss") or 0),
                    pv_after_played=rec.get("pv_after_played") or [],
                    pv_after_best=rec.get("pv_after_best") or [],
                    move_history_san=[], full_move_number=rec.get("move_number"),
                    mover_is_user=True, user_doc=user_doc, session_doc=session_doc,
                )
            except Exception as e:
                print(f"[pwc] v5_teaching note: {e}")
            try:
                socratic_feedback_for_live_move(
                    fen_before=fen, played_san=san, user_color=user_color,
                    severity="blunder", fundamental_violated="hanging_pieces",
                    coach_intent=None, phase="middlegame",
                    cp_loss=int(rec.get("cp_loss") or 0), user_rating=1200,
                )
            except Exception as e:
                print(f"[pwc] socratic note: {e}")
            try:
                coach_move_narration_for_live_move(
                    fen_before=fen, played_san=san, user_color=user_color,
                    move_history_san=[], full_move_number=rec.get("move_number"),
                    v2_context={"v2": True, "teaching_goal": "threat_awareness"},
                )
            except Exception as e:
                print(f"[pwc] coach_narration note: {e}")
        finally:
            tracer.stop()

    # ─── REPORT ───────────────────────────────────────────────────
    if as_json:
        import json
        out = {
            s: {
                "llm_executed": tracer.llm_hit.get(s, False),
                "coaching_producers": sorted(
                    f"{r}::{n}" for (r, n) in tracer.seen.get(s, set()) if _is_coaching(r)
                ),
                "total_backend_fns": len(tracer.seen.get(s, set())),
            }
            for s in ("review", "pwc")
        }
        print(json.dumps(out, indent=2))
        return 0

    for s in ("review", "pwc"):
        seen = tracer.seen.get(s, set())
        coaching = sorted({r for (r, n) in seen if _is_coaching(r)})
        print("=" * 70)
        print(f"SURFACE: {s}   |   backend fns executed: {len(seen)}   |   "
              f"LLM call_llm executed: {tracer.llm_hit.get(s, False)}")
        print("-" * 70)
        print("coaching-relevant MODULES that ran (each = a producer to classify):")
        for mod in coaching:
            fns = sorted(n for (r, n) in seen if r == mod)
            print(f"  {mod}")
            print(f"      fns: {', '.join(fns)}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.json)))
