"""Rebuild the stored move rows of games whose analysis lists both sides' moves
with no is_opponent_move flag (257 Play-with-Coach games, April-September 2026).

The deriver used to treat every unflagged move as the child's, and the writers
key rows by (game_id, move_number), so each row held whichever side's move came
last: for a White child, the opponent's move. The deriver now reads the side to
move from fen_before (is_users_move); this script re-derives only those games
and replaces each row with the child's own move.

Undo lines (the full old rows of each game) go to stdout, so run it with stdout
redirected to a file on the HOST; progress goes to stderr.

    # dry run
    docker exec -w /app/backend -e PYTHONPATH=/app/backend chess-coach-backend \
        python scripts/repair_two_sided_observations.py > /dev/null
    # apply
    docker exec ... python scripts/repair_two_sided_observations.py --apply \
        > /root/backfill_undo/two_sided_undo.jsonl 2> /root/research/two_sided.log
    # undo
    docker exec -i ... python scripts/repair_two_sided_observations.py --undo - \
        < /root/backfill_undo/two_sided_undo.jsonl
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

from bson import json_util  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import DeleteOne, InsertOne, UpdateOne  # noqa: E402
from services.move_observation_deriver import derive_observations_for_game, is_users_move  # noqa: E402


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def two_sided(moves, user_color):
    """True when some unflagged move belongs to the other side."""
    return any(not m.get("is_opponent_move") and not is_users_move(m, user_color) for m in moves)


async def undo(db, fh):
    n = 0
    for line in fh:
        r = json_util.loads(line)
        await db.move_observations.delete_many({"game_id": r["game_id"]})
        if r["rows"]:
            await db.move_observations.insert_many(r["rows"])
        n += 1
    log(f"restored {n} games")


async def run(args):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    if args.undo:
        fh = sys.stdin if args.undo == "-" else open(args.undo, encoding="utf-8")
        return await undo(db, fh)

    colors = {}
    async for g in db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "user_id": 1, "user_color": 1}):
        colors[g["game_id"]] = g
    targets = []
    async for a in db.game_analyses.find({}, {"_id": 0, "game_id": 1,
                                              "stockfish_analysis.move_evaluations.is_opponent_move": 1,
                                              "stockfish_analysis.move_evaluations.fen_before": 1}):
        g = colors.get(a["game_id"])
        mev = ((a.get("stockfish_analysis") or {}).get("move_evaluations")) or []
        if g and g.get("user_color") in ("white", "black") and two_sided(mev, g["user_color"]):
            targets.append(a["game_id"])
    log(f"{len(targets)} games list both sides without a flag; {'APPLY' if args.apply else 'DRY RUN'}")

    stats = Counter()
    extra_fields = Counter()
    for gid in targets:
        g = await db.games.find_one({"game_id": gid}, {"_id": 0, "game_id": 1, "user_id": 1,
                                                       "user_color": 1, "pgn": 1})
        a = await db.game_analyses.find_one({"game_id": gid}, {
            "_id": 0, "user_id": 1, "stockfish_analysis": 1, "decryption_v5_data": 1, "opening_deviation": 1})
        if a.get("user_id") not in (None, g["user_id"]):
            stats["skipped_owner"] += 1
            continue
        obs = derive_observations_for_game(
            stockfish_analysis=a.get("stockfish_analysis") or {}, game_id=gid, user_id=g["user_id"],
            user_color=g["user_color"], decryption_v5_data=a.get("decryption_v5_data"),
            derived_at=datetime.now(timezone.utc), pgn=g.get("pgn"),
            opening_deviation=a.get("opening_deviation"))
        keys = [o["move_number"] for o in obs]
        if len(keys) != len(set(keys)):
            stats["skipped_duplicate_move_numbers"] += 1
            log("duplicate move numbers after the fix", gid)
            continue
        old_rows = await db.move_observations.find({"game_id": gid}, {"_id": 0}).to_list(None)
        old_by_mn = {r.get("move_number"): r for r in old_rows}
        new_by_mn = {o["move_number"]: o for o in obs}
        ops = []
        for mn, o in new_by_mn.items():
            old = old_by_mn.get(mn)
            if old is None:
                stats["inserted"] += 1
                ops.append(InsertOne(o))
                continue
            stats["moved_to_child_move" if old.get("move_san") != o.get("move_san") else "same_move_rewritten"] += 1
            for f in set(old) - set(o) - {"labels_rederived_at"}:
                extra_fields[f] += 1
            ops.append(UpdateOne({"game_id": gid, "move_number": mn},
                                 {"$set": o, "$unset": {"labels_rederived_at": ""}}))
        for mn in set(old_by_mn) - set(new_by_mn):
            stats["deleted_no_child_move"] += 1
            ops.append(DeleteOne({"game_id": gid, "move_number": mn}))
        stats["games"] += 1
        if args.apply and ops:
            print(json_util.dumps({"game_id": gid, "rows": old_rows}), flush=True)
            await db.move_observations.bulk_write(ops, ordered=False)
    log(json.dumps({"stats": stats, "old_fields_not_rewritten": extra_fields}, default=str))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--undo", help="restore from this undo file ('-' = stdin)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
