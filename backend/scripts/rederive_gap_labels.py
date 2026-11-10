"""Re-derive the stored gap labels (missed_pattern / subtype / severity) after a
classifier fix that did not change the observation schema version.

Why this exists: backfill_move_observations.py rewrites a row only when its
schema or destination-safety fact version is old. A classifier fix such as
5374d0f6 (gap evals read from the mover's side) changes labels without
changing either version, so that script sees every row as current.

This script re-runs the real deriver on stored analyses and writes only the
three label fields, only where they differ. Every change is recorded in an
undo file first.

    # dry run, Black games (the 5374d0f6 fix), and the White negative control
    python scripts/rederive_gap_labels.py --color black
    python scripts/rederive_gap_labels.py --color white --limit 300

    python scripts/rederive_gap_labels.py --color black --apply \
        --undo-file /app/backend/rederive_undo_black.jsonl

Undo: python scripts/rederive_gap_labels.py --undo /app/backend/rederive_undo_black.jsonl
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import UpdateOne  # noqa: E402
from services.move_observation_deriver import derive_observations_for_game  # noqa: E402

FIELDS = ("missed_pattern", "subtype", "severity")
BATCH = 50


def label(row):
    return tuple(row.get(f) for f in FIELDS)


async def undo(db, path):
    ops = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            ops.append(UpdateOne({"game_id": r["game_id"], "move_number": r["move_number"]},
                                 {"$set": r["old"]}))
    for i in range(0, len(ops), 1000):
        await db.move_observations.bulk_write(ops[i:i + 1000], ordered=False)
    print(f"restored {len(ops)} rows from {path}")


async def run(args):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    if args.undo:
        return await undo(db, args.undo)
    if args.apply and not args.undo_file:
        raise SystemExit("--apply needs --undo-file")

    games = await db.games.find({"user_color": args.color, "is_analyzed": True},
                                {"_id": 0, "game_id": 1, "user_id": 1, "user_color": 1, "pgn": 1}
                                ).to_list(None)
    if args.limit:
        games = games[:args.limit]
    print(f"{len(games)} analysed {args.color} games; {'APPLY' if args.apply else 'DRY RUN'}")

    changes = Counter()
    examples = []
    stats = Counter()
    undo_fh = open(args.undo_file, "a", encoding="utf-8") if args.apply else None
    for i in range(0, len(games), BATCH):
        chunk = {g["game_id"]: g for g in games[i:i + BATCH]}
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": list(chunk)}},
            {"_id": 0, "game_id": 1, "user_id": 1, "stockfish_analysis.move_evaluations": 1,
             "decryption_v5_data": 1, "opening_deviation": 1}).to_list(None)
        stored = await db.move_observations.find(
            {"game_id": {"$in": list(chunk)}},
            {"_id": 0, "game_id": 1, "move_number": 1, "user_id": 1, **{f: 1 for f in FIELDS}}
        ).to_list(None)
        by_key = {(r["game_id"], r.get("move_number")): r for r in stored}
        ops = []
        for a in analyses:
            g = chunk.get(a["game_id"])
            sf = a.get("stockfish_analysis") or {}
            if not g or not sf.get("move_evaluations") or a.get("user_id") not in (None, g["user_id"]):
                stats["skipped"] += 1
                continue
            try:
                obs = derive_observations_for_game(
                    stockfish_analysis=sf, game_id=g["game_id"], user_id=g["user_id"],
                    user_color=g["user_color"], decryption_v5_data=a.get("decryption_v5_data"),
                    derived_at=datetime.now(timezone.utc), pgn=g.get("pgn"),
                    opening_deviation=a.get("opening_deviation"))
            except Exception as exc:  # report, never hide
                stats["derive_error"] += 1
                if stats["derive_error"] <= 5:
                    print("derive error", g["game_id"], type(exc).__name__, str(exc)[:120])
                continue
            stats["games"] += 1
            for o in obs or []:
                old = by_key.get((o["game_id"], o.get("move_number")))
                if not old or old.get("user_id") != g["user_id"]:
                    stats["no_stored_row"] += 1
                    continue
                stats["rows"] += 1
                if label(old) == label(o):
                    continue
                changes[(label(old)[:2], label(o)[:2])] += 1
                if len(examples) < 12:
                    examples.append({"game_id": o["game_id"], "move": o.get("move_san"),
                                     "fen": o.get("fen_before"), "old": label(old), "new": label(o)})
                new_vals = {f: o.get(f) for f in FIELDS}
                if undo_fh:
                    undo_fh.write(json.dumps({"game_id": o["game_id"], "move_number": o["move_number"],
                                              "old": {f: old.get(f) for f in FIELDS},
                                              "new": new_vals}, default=str) + "\n")
                ops.append(UpdateOne({"game_id": o["game_id"], "move_number": o["move_number"]},
                                     {"$set": {**new_vals, "labels_rederived_at": datetime.now(timezone.utc)}}))
        if args.apply and ops:
            undo_fh.flush()
            await db.move_observations.bulk_write(ops, ordered=False)
        if (i // BATCH) % 20 == 0:
            print(f"  {i + len(chunk)} games, {sum(changes.values())} label changes", flush=True)
    if undo_fh:
        undo_fh.close()
    print(json.dumps({"stats": stats, "changed_rows": sum(changes.values())}, default=str))
    for (old, new), n in changes.most_common(25):
        print(f"{n:6d}  {old} -> {new}")
    for e in examples:
        print(json.dumps(e, default=str))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--color", choices=("white", "black"), default="black")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--undo-file")
    p.add_argument("--undo", help="restore the old labels from this undo file")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
