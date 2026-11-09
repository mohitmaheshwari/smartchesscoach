"""Recompute thinking scores that were stored before the game had move times.

The patience habit is measured only when the analysis carries think-time
(services/thinking_score.py, MIN_TIMED_MOVES_FOR_PATIENCE). On 2026-11-09
think-times were restored to analyses whose PGN had no clocks when they were
scored (scripts/refetch_lichess_clocks.py, backfill_move_think_time.py), so
their stored score still says "patience unmeasured". data_freshness only
fills scores that are missing, never stale ones.

It also finds the old format. Scores written before 2026-09 have no
`measured_habits`: that scorer gave 100 to habits it never observed, which
the current one reports as unmeasured. 14,988 of them sat in the same
histories as current-format scores, so every trend compared two formulas
(measured 2026-11-09; in a 1,500-score sample, all 468 drops of more than
five points came from those habits or later scorer fixes).

This recomputes, with the worker's own inputs, every old-format score, and
every current-format score that lacks patience while its analysis now has
enough timed moves. Dry-run by default.

    python scripts/recompute_thinking_scores.py
    python scripts/recompute_thinking_scores.py --write --undo-file /root/x.json
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pymongo import MongoClient  # noqa: E402
from services.thinking_score import (  # noqa: E402
    MIN_TIMED_MOVES_FOR_PATIENCE, calculate_game_thinking_scores)

BATCH = 200


def main(args):
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")]
    q = {"measured_habits": {"$ne": "patience"}}
    if args.user_id:
        q["user_id"] = args.user_id
    docs = list(db.thinking_scores.find(q, {"_id": 0, "user_id": 1, "game_id": 1,
                                            "measured_habits": 1}))
    c = Counter(scores_without_patience=len(docs))
    undo, delta = [], Counter()
    for i in range(0, len(docs), BATCH):
        chunk = docs[i:i + BATCH]
        keys = {(d["game_id"], d["user_id"]) for d in chunk}
        timed = {}
        for a in db.game_analyses.find(
                {"game_id": {"$in": [k[0] for k in keys]}},
                {"_id": 0, "game_id": 1, "user_id": 1,
                 "stockfish_analysis.move_evaluations.time_spent_seconds": 1}):
            evs = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
            n = sum(1 for m in evs if m.get("time_spent_seconds") is not None)
            timed[(a["game_id"], a.get("user_id"))] = n
        for d in chunk:
            key = (d["game_id"], d["user_id"])
            old_format = "measured_habits" not in d
            if key not in timed:
                c["no_analysis"] += 1
                continue
            if not old_format and timed[key] < MIN_TIMED_MOVES_FOR_PATIENCE:
                c["current_format_still_untimed"] += 1  # recomputing changes nothing
                continue
            a = db.game_analyses.find_one({"game_id": key[0], "user_id": key[1]},
                                          {"_id": 0, "stockfish_analysis.move_evaluations": 1})
            g = db.games.find_one({"game_id": key[0]}, {"_id": 0, "user_color": 1})
            evs = ((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
            # The worker's exact inputs (analysis_worker PHASE 6).
            scores = calculate_game_thinking_scores(
                {"game_id": key[0], "move_evaluations": evs, "critical_moments": []},
                (g or {}).get("user_color") or "white")
            scores["user_id"], scores["game_id"] = key[1], key[0]
            if not old_format and "patience" not in (scores.get("measured_habits") or []):
                c["recomputed_still_no_patience"] += 1
                continue
            c["to_update"] += 1
            if old_format:
                c["old_format_score"] += 1
            old = db.thinking_scores.find_one({"user_id": key[1], "game_id": key[0]}, {"_id": 0})
            if old and old.get("overall_score") is not None and scores.get("overall_score") is not None:
                diff = scores["overall_score"] - old["overall_score"]
                delta["down >5" if diff < -5 else "up >5" if diff > 5 else "within 5"] += 1
            if args.write:
                undo.append(old)
                db.thinking_scores.update_one({"user_id": key[1], "game_id": key[0]},
                                              {"$set": scores})
                c["written"] += 1
    if args.write:
        Path(args.undo_file).write_text(json.dumps(undo, default=str))
    print(json.dumps({"mode": "write" if args.write else "dry_run", **c,
                      "overall_score_change": dict(delta)}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--user-id", default="")
    p.add_argument("--undo-file", default="")
    a = p.parse_args()
    if a.write and not a.undo_file:
        sys.exit("--write needs --undo-file")
    main(a)
