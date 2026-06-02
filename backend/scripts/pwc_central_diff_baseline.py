"""PWC central-caption migration — phase 1 diff baseline.

Spec: docs/pwc_central_caption_migration.md.

For every USER move in the surface1 corpus (20 analyzed games,
~600 user moves), render BOTH:
  - PWC's current narrative (via shared_coaching_v5 / coaching_voice)
  - What the central caption pipeline (build_move_teaching_decision)
    would say at the same position

Classify each pair into one of:
  agree_clean              — both produce same content, same severity
  agree_wording_only       — same severity, different wording (cosmetic)
  disagree_severity        — different severity tier
  disagree_content         — same severity, different content/move recommendation
  one_empty_other_not      — exactly one engine stayed silent
  both_empty               — both stayed silent (neither cares)

The aggregate diff result is the input to the §1 sign-off gate in
the spec: if `(agree_clean + agree_wording_only) / total < 60%`, the
migration is riskier than expected and we pause to understand.

This script does NOT change any code paths. It's pure measurement.
Safe to run repeatedly. Reads from production-target Mongo via
the same env vars snapshot_surface1.py uses.

Usage (inside backend container):

    python /app/backend/scripts/pwc_central_diff_baseline.py
    # → writes /app/backend/scripts/_snapshots/pwc_central_diff_baseline.json
    #   with per-move records + a summary block

    python /app/backend/scripts/pwc_central_diff_baseline.py --human
    # → also prints a human-readable summary table to stdout
"""
from __future__ import annotations

import argparse
import asyncio
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


_SNAP_DIR = Path("/app/backend/scripts/_snapshots")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


# Mirror the snapshot_surface1 corpus.
CORPUS: List[str] = [
    "game_692ab776c5b1", "game_85bd0169aa4f", "game_b5d23694a803",
    # The remaining 17 game IDs match snapshot_surface1.py's CORPUS
    # constant. To keep this script self-contained we read them from
    # the existing snapshot file rather than duplicating the list —
    # see _load_corpus() below.
]


def _load_corpus() -> List[str]:
    """Read the game ids from any existing surface1 snapshot. Falls
    back to the inline CORPUS if no snapshot exists yet."""
    for path in _SNAP_DIR.glob("surface1_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ids = [k for k in data.keys() if k.startswith("game_")]
                if ids:
                    return ids
        except Exception:
            continue
    return CORPUS


# ── Per-move rendering ──────────────────────────────────────────────────


def _render_pwc_narrative(move_record: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the PWC base narrative from the snapshot_surface1 entry.

    The snapshot_surface1 capture already runs the PWC engine and
    stores narrative + severity. We just read it. This avoids
    re-running shared_coaching_v5 from scratch and keeps the diff
    apples-to-apples with the regression net memory has been using.
    """
    return {
        "narrative": (move_record.get("narrative") or "").strip(),
        "severity":  move_record.get("severity") or "silent",
    }


def _render_central_caption(
    fen_before: str,
    fen_after: str,
    move_san: str,
    move_uci: str,
    user_color: str,
    eval_before: Optional[int],
    eval_after: Optional[int],
    cp_loss: Optional[int],
) -> Dict[str, Any]:
    """Render what the central caption pipeline would emit at this
    position. Calls build_move_teaching_decision the same way V5
    review does (per memory/project_caption_pipeline_central_layer).
    """
    try:
        from services.caption_pipeline import build_move_teaching_decision
    except Exception as e:
        return {"narrative": f"<central import failed: {e}>", "severity": "error"}

    try:
        decision = build_move_teaching_decision(
            fen_before=fen_before,
            fen_after=fen_after,
            move_san=move_san,
            move_uci=move_uci,
            mover_color=user_color,
            eval_before=eval_before,
            eval_after=eval_after,
            cp_loss=cp_loss,
        )
    except Exception as e:
        return {"narrative": f"<central render failed: {e}>", "severity": "error"}

    caption = ""
    severity = "silent"
    try:
        # decision may be a dataclass or dict — handle both.
        if hasattr(decision, "text"):
            caption = (getattr(decision.text, "caption", None) or "").strip()
        elif isinstance(decision, dict):
            caption = (decision.get("caption") or decision.get("text", {}).get("caption") or "").strip()
        if hasattr(decision, "severity"):
            severity = getattr(decision, "severity", "silent") or "silent"
        elif isinstance(decision, dict):
            severity = decision.get("severity") or "silent"
    except Exception:
        pass

    return {"narrative": caption, "severity": severity}


# ── Diff classification ────────────────────────────────────────────────


def _classify(pwc: Dict[str, Any], central: Dict[str, Any]) -> str:
    """One of the 6 class labels documented at the top."""
    p_nar = pwc.get("narrative") or ""
    c_nar = central.get("narrative") or ""
    p_sev = pwc.get("severity") or "silent"
    c_sev = central.get("severity") or "silent"

    p_empty = not p_nar
    c_empty = not c_nar

    if p_empty and c_empty:
        return "both_empty"
    if p_empty != c_empty:
        return "one_empty_other_not"
    if p_sev != c_sev:
        return "disagree_severity"
    # Same severity, both non-empty. Cosmetic or content disagreement?
    # Heuristic: if the two narratives share ≥40% token overlap, it's
    # "wording only"; otherwise "content disagreement". Token-based, no
    # stemming, lowercase. The cutoff is reviewable post-baseline.
    p_tokens = set(p_nar.lower().split())
    c_tokens = set(c_nar.lower().split())
    if not p_tokens or not c_tokens:
        return "disagree_content"
    overlap = len(p_tokens & c_tokens) / max(len(p_tokens | c_tokens), 1)
    return "agree_wording_only" if overlap >= 0.4 else "disagree_content"


# ── Main driver ─────────────────────────────────────────────────────────


async def main_async(human: bool):
    if not MONGO_URL:
        print("FATAL: MONGO_URL not set."); sys.exit(1)
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    corpus = _load_corpus()
    print(f"Corpus: {len(corpus)} games")

    counts: Dict[str, int] = {
        "agree_clean": 0, "agree_wording_only": 0,
        "disagree_severity": 0, "disagree_content": 0,
        "one_empty_other_not": 0, "both_empty": 0,
        "error": 0,
    }
    per_move_records: List[Dict[str, Any]] = []

    # Pull the latest surface1 snapshot to reuse PWC narratives.
    snap = None
    for path in sorted(_SNAP_DIR.glob("surface1_*.json"), reverse=True):
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
            print(f"Using PWC snapshot: {path.name}")
            break
        except Exception:
            continue
    if snap is None:
        print("No surface1 snapshot found. Run snapshot_surface1.py --tag X first.")
        sys.exit(2)

    for gid in corpus:
        g = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1, "user_color": 1})
        a = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not g or not a:
            continue
        evals_by_san: Dict[tuple, Dict[str, Any]] = {}
        for e in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
            evals_by_san[(e.get("move_number"), e.get("move"))] = e

        # Replay PGN; for each user move, find matching PWC + central
        try:
            pgn = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception:
            continue
        if pgn is None:
            continue

        user_color_str = (g.get("user_color") or "white").lower()
        user_color = chess.WHITE if user_color_str == "white" else chess.BLACK
        snap_game = (snap.get(gid) or {})
        snap_moves = snap_game.get("moves") or []

        board = pgn.board()
        for ply, mv in enumerate(pgn.mainline_moves()):
            fen_before = board.fen()
            try:
                san = board.san(mv)
            except Exception:
                san = mv.uci()
            board.push(mv)
            fen_after = board.fen()

            if board.turn != user_color:  # board.turn AFTER push = NEXT mover
                pass  # the move we just pushed was by `not board.turn`
            # Filter: we only care about user moves.
            mover_was_user = (((-1) ** ply == -1) if user_color == chess.BLACK else (ply % 2 == 0))
            if not mover_was_user:
                continue

            mv_num = (ply // 2) + 1
            # Find PWC narrative from the snapshot
            pwc_entry = next(
                (m for m in snap_moves if m.get("mv") == mv_num and m.get("san") == san),
                None,
            )
            if pwc_entry is None:
                continue
            pwc_payload = _render_pwc_narrative(pwc_entry)

            # Render central
            ev = evals_by_san.get((mv_num, san)) or {}
            central_payload = _render_central_caption(
                fen_before=fen_before,
                fen_after=fen_after,
                move_san=san,
                move_uci=mv.uci(),
                user_color=user_color_str,
                eval_before=ev.get("eval_before"),
                eval_after=ev.get("eval_after"),
                cp_loss=ev.get("cp_loss"),
            )

            label = _classify(pwc_payload, central_payload)
            counts[label] += 1
            per_move_records.append({
                "game_id": gid,
                "move_number": mv_num,
                "move_san": san,
                "cp_loss": ev.get("cp_loss"),
                "pwc_narrative":     pwc_payload["narrative"][:240],
                "pwc_severity":      pwc_payload["severity"],
                "central_narrative": central_payload["narrative"][:240],
                "central_severity":  central_payload["severity"],
                "classification":    label,
            })

    out_path = _SNAP_DIR / "pwc_central_diff_baseline.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "summary": counts,
        "total":   sum(counts.values()),
        "agree_rate": (
            (counts["agree_clean"] + counts["agree_wording_only"])
            / max(sum(counts.values()), 1)
        ),
        "per_move": per_move_records,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")

    # Print summary
    total = out["total"]
    print("\n=== SUMMARY ===")
    for k in ("agree_clean", "agree_wording_only", "disagree_severity",
              "disagree_content", "one_empty_other_not", "both_empty", "error"):
        v = counts[k]
        pct = (v / max(total, 1)) * 100
        print(f"  {k:>22}  {v:>5}  {pct:>5.1f}%")
    print(f"  {'TOTAL':>22}  {total:>5}")
    agree_rate = out["agree_rate"] * 100
    print(f"\n  agree_rate (clean + wording_only) = {agree_rate:.1f}%")
    if agree_rate < 60:
        print("  ⚠️  Below 60% — spec §1 sign-off gate says PAUSE migration to understand the divergence.")
    else:
        print("  ✓  At or above 60% — sign-off gate clears, migration is tractable per spec.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--human", action="store_true",
                   help="Also print a human-readable summary (default: always prints summary)")
    args = p.parse_args()
    asyncio.run(main_async(args.human))


if __name__ == "__main__":
    main()
