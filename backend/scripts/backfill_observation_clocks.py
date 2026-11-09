"""Fill the four clock fields on move_observations the worker wrote without them.

The worker derived observations without the game's PGN
(services/analysis_completion_evidence._prepare, fixed 2026-11-09), so every
observation it wrote has time_spent_seconds / time_left_seconds / time_flag /
time_flag_severity empty. The clocks are in the PGN.

This re-runs the one deriver (derive_observations_for_game) with the PGN, in
memory, and $sets ONLY those four fields on rows where time_left_seconds is
empty. Every other field on the row is left as it is. Dry-run by default.

    python scripts/backfill_observation_clocks.py
    python scripts/backfill_observation_clocks.py --write --undo-file /tmp/x.json
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pymongo import MongoClient, UpdateOne  # noqa: E402
from services.move_observation_deriver import derive_observations_for_game  # noqa: E402

FIELDS = ("time_spent_seconds", "time_left_seconds", "time_flag", "time_flag_severity")


def main(args):
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")]
    q = {"time_left_seconds": None}
    if args.user_id:
        q["user_id"] = args.user_id
    pairs = db.move_observations.distinct("game_id", q) if args.user_id else None
    if pairs is None:
        pairs = [r["_id"] for r in db.move_observations.aggregate(
            [{"$match": q}, {"$group": {"_id": "$game_id"}}], allowDiskUse=True)]
    if args.limit:
        pairs = pairs[: args.limit]

    c = Counter(games=len(pairs))
    undo = []
    for gid in pairs:
        game = db.games.find_one({"game_id": gid}, {"_id": 0, "game_id": 1, "user_id": 1,
                                                    "user_color": 1, "pgn": 1})
        if not game or "%clk" not in (game.get("pgn") or ""):
            c["game_has_no_clock"] += 1
            continue
        if game.get("user_color") not in ("white", "black"):
            c["no_user_color"] += 1
            continue
        analysis = db.game_analyses.find_one(
            {"game_id": gid, "user_id": game["user_id"]},
            {"_id": 0, "stockfish_analysis.move_evaluations": 1,
             "stockfish_analysis.opponent_move_evaluations": 1})
        if not analysis:
            c["no_analysis"] += 1
            continue
        obs = derive_observations_for_game(
            stockfish_analysis=analysis.get("stockfish_analysis") or {},
            game_id=gid, user_id=game["user_id"], user_color=game["user_color"],
            pgn=game["pgn"])
        ops = []
        for o in obs:
            if o.get("time_left_seconds") is None:
                continue
            key = {"user_id": o["user_id"], "game_id": gid, "move_number": o["move_number"],
                   "time_left_seconds": None}
            ops.append(UpdateOne(key, {"$set": {f: o.get(f) for f in FIELDS}}))
            undo.append([o["user_id"], gid, o["move_number"]])
        c["games_with_clock"] += 1
        c["rows_to_fill"] += len(ops)
        if args.write and ops:
            res = db.move_observations.bulk_write(ops, ordered=False)
            c["rows_written"] += res.modified_count
    if args.write and args.undo_file:
        Path(args.undo_file).write_text(json.dumps(undo))
    print(json.dumps({"mode": "write" if args.write else "dry_run", **c}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--user-id", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--undo-file", default="")
    a = p.parse_args()
    if a.write and not a.undo_file:
        sys.exit("--write needs --undo-file")
    main(a)
