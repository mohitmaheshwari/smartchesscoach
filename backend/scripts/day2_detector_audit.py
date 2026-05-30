"""Day 2 audit: detector fire counts + verifier-recovery rate from the
live game_analyses corpus.

The game_analyses collection already has move_evaluations with
eval_before/eval_after/cp_loss/best_move_san/pv_after_played/
pv_after_best fields populated by analysis_worker at depth 20. We
re-run the central caption pipeline on every (fen, played, engine info)
triple and capture:

  1. Per-rule fire counts
  2. Per-detector fire counts (principle / shape pattern)
  3. Per-rule verifier-recovery counts (how often Phase 1 + Phase 2
     verifier caught a hallucination from each rule)
  4. Sample (fen, played_san, caption, rule) for top-N detectors for
     human inspection

Run from container:
    docker exec chess-coach-backend python /app/backend/scripts/day2_detector_audit.py \\
        --games 200 --out /tmp/day2_audit.json

Mohit "Day 2 — terminal up" 2026-05-30. Lays the groundwork for Day 3
(cull / tighten the bottom quartile by precision).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

from services.caption_pipeline import (
    build_move_teaching_decision, MoveInputs, CrossMoveState
)


async def run(max_games: int, out_path: Path, sample_per_detector: int = 10):
    mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
    db_name = os.environ.get("DB_NAME") or "chess_coach"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Pull recent analyzed games
    games_meta: Dict[str, Dict[str, Any]] = {}
    cursor = db.games.find(
        {"is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1, "user_id": 1}
    ).sort("end_time", -1).limit(max_games)
    async for g in cursor:
        games_meta[g["game_id"]] = g
    print(f"Sampling {len(games_meta)} analyzed games")

    rule_fires: Counter = Counter()
    detector_fires: Counter = Counter()
    verifier_fails: Counter = Counter()
    samples_by_detector: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    total_moves = 0
    total_recovered = 0
    total_skipped = 0
    start = time.time()

    for gi, (gid, gm) in enumerate(games_meta.items()):
        user_color = gm.get("user_color") or "white"
        ga = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )
        if not ga:
            continue
        moves = (ga.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not moves:
            continue

        # mover_is_user heuristic: alternating based on user_color +
        # whose turn it is in fen_before.
        for mv in moves:
            fen_before = mv.get("fen_before") or ""
            played_san = mv.get("move") or ""
            best_san = mv.get("best_move") or None
            eval_before = mv.get("eval_before")
            eval_after = mv.get("eval_after")
            cp_loss = mv.get("cp_loss") or 0
            pv_after_played = mv.get("pv_after_played") or []
            pv_after_best = mv.get("pv_after_best") or []
            full_move_number = mv.get("move_number") or 1
            # mover_is_user: turn-to-move BEFORE this move matches user_color
            if not fen_before or not played_san:
                total_skipped += 1
                continue
            try:
                turn_field = fen_before.split()[1]
                turn_color = "white" if turn_field == "w" else "black"
            except Exception:
                total_skipped += 1
                continue
            mover_is_user = (turn_color == user_color)
            mover_is_white = (turn_color == "white")

            inp = MoveInputs(
                fen_before=fen_before,
                played_san=played_san,
                mover_is_user=mover_is_user,
                mover_is_white=mover_is_white,
                user_color=user_color,
                full_move_number=int(full_move_number),
                move_history_san=[],
                best_move_san=best_san,
                eval_before_cp=int(eval_before) if eval_before is not None else None,
                eval_after_cp=int(eval_after) if eval_after is not None else None,
                cp_loss=int(cp_loss),
                pv_after_played=list(pv_after_played),
                pv_after_best=list(pv_after_best),
                user_rating=1400,
            )
            try:
                dec = build_move_teaching_decision(inp, CrossMoveState())
            except Exception:
                total_skipped += 1
                continue

            total_moves += 1
            caption = (dec.text.caption if dec.text else "") or ""
            rule = (dec.text.rule_name if dec.text else "") or ""

            rule_fires[rule] += 1

            if "R_VERIFIER_RECOVERY" in rule:
                total_recovered += 1
                prev_rule = rule.split("→")[0] if "→" in rule else rule.split("->")[0]
                verifier_fails[prev_rule] += 1

            pid = dec.teaching_meta.principle_id_used if dec.teaching_meta else None
            sp_id = dec.teaching_meta.shape_pattern_id if dec.teaching_meta else None

            for key in [f"principle:{pid}" if pid else None,
                        f"shape:{sp_id}" if sp_id else None]:
                if not key:
                    continue
                detector_fires[key] += 1
                if len(samples_by_detector[key]) < sample_per_detector:
                    samples_by_detector[key].append({
                        "game_id": gid,
                        "fen": fen_before,
                        "played": played_san,
                        "best": best_san,
                        "cp_loss": int(cp_loss),
                        "rule": rule,
                        "caption": caption,
                    })

        if (gi + 1) % 25 == 0:
            elapsed = time.time() - start
            rate = total_moves / max(elapsed, 1e-6)
            print(f"  {gi+1}/{len(games_meta)} games | "
                  f"{total_moves} moves | {rate:.0f} moves/s | "
                  f"{total_recovered} recoveries ({100*total_recovered/max(total_moves,1):.2f}%)")

    elapsed = time.time() - start
    report = {
        "summary": {
            "total_games": len(games_meta),
            "total_moves": total_moves,
            "skipped_moves": total_skipped,
            "total_recovered_by_verifier": total_recovered,
            "recovery_rate_pct": round(100 * total_recovered / max(total_moves, 1), 3),
            "elapsed_seconds": round(elapsed, 1),
        },
        "top_rules": rule_fires.most_common(30),
        "top_detectors": detector_fires.most_common(30),
        "verifier_fails_per_rule": dict(verifier_fails.most_common(30)),
        "samples_by_detector": {k: v for k, v in
                                samples_by_detector.items()
                                if detector_fires[k] >= 5},
    }

    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport: {out_path}")
    print(f"\n=== Top 15 rules ===")
    for r, n in rule_fires.most_common(15):
        print(f"  {n:6d}  {r}")
    print(f"\n=== Top 15 detectors ===")
    for d, n in detector_fires.most_common(15):
        print(f"  {n:6d}  {d}")
    print(f"\n=== Top verifier-fail rules ===")
    for r, n in verifier_fails.most_common(15):
        print(f"  {n:4d}  (rule that was recovered FROM): {r}")
    print(f"\n=== Recovery rate: {total_recovered}/{total_moves} "
          f"= {100*total_recovered/max(total_moves,1):.3f}% ===")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--out", default="/tmp/day2_audit.json")
    p.add_argument("--sample", type=int, default=10)
    args = p.parse_args()
    asyncio.run(run(args.games, Path(args.out), args.sample))


if __name__ == "__main__":
    main()
