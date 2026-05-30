"""Day 4: replay Parth's 30-item feedback dump through the current
pipeline + compare to original. For each item: rebuild MoveInputs from
the dump's position, render via build_move_teaching_decision, output
old vs new caption + classification.

Designed to run with the dump JSON copied alongside, e.g.:
    docker exec chess-coach-backend python /app/backend/scripts/day4_replay_parth_dump.py \\
        --dump /tmp/parth_dump.json --out /tmp/day4_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.caption_pipeline import (
    build_move_teaching_decision, MoveInputs, CrossMoveState
)


def replay(dump_path: Path, out_path: Path):
    items = json.loads(dump_path.read_text(encoding="utf-8"))
    print(f"Replaying {len(items)} items from {dump_path}")

    results: List[Dict[str, Any]] = []
    pipeline_silenced = 0
    pipeline_changed = 0
    pipeline_kept = 0

    for fb in items:
        fid = fb.get("feedback_id")
        pos = fb.get("position", {}) or {}
        fen = pos.get("fen") or ""
        played = pos.get("move_san") or ""
        severity_label = (fb.get("severity") or "").lower()
        old_caption = (fb.get("coaching_text_flagged") or "").strip()
        issue = (fb.get("issue") or "").strip()
        cpl = int(pos.get("cp_loss") or 0)
        eval_before = pos.get("eval_before")
        eval_after = pos.get("eval_after")
        best_move = pos.get("best_move")

        # Derive user side from severity ('opp_' prefix means opponent moved)
        is_opp = severity_label.startswith("opp_") or severity_label == "context"

        if not fen or not played:
            results.append({
                "feedback_id": fid,
                "skipped": True,
                "reason": "missing fen or played",
            })
            continue

        try:
            board = chess.Board(fen)
            mv = board.parse_san(played)
            turn = "white" if board.turn == chess.WHITE else "black"
            mover_is_white = (board.turn == chess.WHITE)
            user_color = ("black" if turn == "white" else "white") if is_opp else turn
            mover_is_user = not is_opp
        except Exception as e:
            results.append({
                "feedback_id": fid,
                "skipped": True,
                "reason": f"parse error: {e}",
            })
            continue

        inp = MoveInputs(
            fen_before=fen,
            played_san=played,
            mover_is_user=mover_is_user,
            mover_is_white=mover_is_white,
            user_color=user_color,
            full_move_number=int(pos.get("move_number") or 1),
            move_history_san=[],  # empty — we don't have the full game history
            best_move_san=best_move,
            eval_before_cp=int(eval_before) if eval_before is not None else None,
            eval_after_cp=int(eval_after) if eval_after is not None else None,
            cp_loss=cpl,
            pv_after_played=[],
            pv_after_best=[best_move] if best_move else [],
            user_rating=1400,
        )
        try:
            dec = build_move_teaching_decision(inp, CrossMoveState())
        except Exception as e:
            results.append({
                "feedback_id": fid,
                "skipped": True,
                "reason": f"pipeline error: {e}",
            })
            continue

        new_caption = (dec.text.caption if dec.text else "") or ""
        new_rule = (dec.text.rule_name if dec.text else "") or ""
        recovered = "R_VERIFIER_RECOVERY" in new_rule

        # Classify outcome
        if not new_caption:
            kind = "silent"
            pipeline_silenced += 1
        elif new_caption.strip().lower() != old_caption.strip().lower():
            kind = "changed"
            pipeline_changed += 1
        else:
            kind = "unchanged"
            pipeline_kept += 1

        results.append({
            "feedback_id": fid,
            "played": played,
            "cpl": cpl,
            "severity": severity_label,
            "issue": issue,
            "old_caption": old_caption,
            "new_caption": new_caption,
            "new_rule": new_rule,
            "recovered": recovered,
            "kind": kind,
        })

    summary = {
        "total": len(items),
        "kept_same": pipeline_kept,
        "changed": pipeline_changed,
        "silenced": pipeline_silenced,
    }
    out_path.write_text(json.dumps({"summary": summary, "items": results},
                                    indent=2, ensure_ascii=False))
    print(f"\nReport: {out_path}")
    print("=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()
    print("=== PER ITEM ===")
    for r in results:
        fid = r.get("feedback_id")
        if r.get("skipped"):
            print(f"  [SKIP] {fid}: {r.get('reason')}")
            continue
        marker = {"silent": "[SLNT]", "changed": "[CHGD]", "unchanged": "[SAME]"}.get(r["kind"], "[????]")
        rec = " [REC]" if r.get("recovered") else ""
        print(f"  {marker}{rec} {fid} {r['played']} cpl={r['cpl']}")
        print(f"        OLD: {r['old_caption'][:150]}")
        print(f"        NEW: {r['new_caption'][:150]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dump", required=True)
    p.add_argument("--out", default="/tmp/day4_report.json")
    args = p.parse_args()
    replay(Path(args.dump), Path(args.out))


if __name__ == "__main__":
    main()
