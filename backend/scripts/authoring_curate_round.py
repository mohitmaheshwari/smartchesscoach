"""Curate next batch of games for Parth (the reviewer) to author on.

Pulls analyzed games with V5 decryption ready, owned by NON-Parth users, not
yet authored on, that have meaningful blunder/mistake content. Caps at 3 per
owner so the batch is diverse. Default batch size 25, override with --n.

Writes a JSON snapshot + prints a Markdown list of URLs ready to paste to
Parth.
"""
import argparse
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

PARTH_UIDS = ["user_2bfd0958600e", "user_d35b37459e10"]
DEFAULT_BASE_URL = "https://chessguru.ai"


async def main(n: int, max_per_owner: int, base_url: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    authored_gids = set(await db.move_feedback.distinct("game_id", {"is_authoring_submission": True}))
    print(f"Already-authored game_ids: {len(authored_gids)}")

    pipeline = [
        {"$match": {
            "decryption_v5_data": {"$exists": True, "$type": "array"},
            "user_id": {"$nin": PARTH_UIDS},
        }},
        {"$project": {
            "_id": 0,
            "game_id": 1,
            "user_id": 1,
            "blunders": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$eq": ["$$this.severity", "blunder"]},
            }}},
            "mistakes": {"$size": {"$filter": {
                "input": "$decryption_v5_data",
                "cond": {"$eq": ["$$this.severity", "mistake"]},
            }}},
        }},
        {"$match": {"$expr": {"$gte": [{"$add": ["$blunders", "$mistakes"]}, 3]}}},
        {"$sort": {"blunders": -1, "mistakes": -1}},
        {"$limit": 1500},
    ]
    rows = [r async for r in db.game_analyses.aggregate(pipeline)]
    print(f"Pool (v5 + non-Parth + ≥3 mistakes/blunders): {len(rows)}")

    per_owner: dict[str, int] = {}
    pick = []
    for r in rows:
        gid = r["game_id"]
        if gid in authored_gids:
            continue
        u = r["user_id"]
        if per_owner.get(u, 0) >= max_per_owner:
            continue
        g = await db.games.find_one(
            {"game_id": gid},
            {"_id": 0, "opening_name": 1, "user_color": 1, "result": 1, "rating_at_game": 1, "platform": 1},
        )
        if not g:
            continue
        pick.append({
            "game_id": gid,
            "user_id": u,
            "blunders": r["blunders"],
            "mistakes": r["mistakes"],
            "opening": g.get("opening_name"),
            "user_color": g.get("user_color"),
            "result": g.get("result"),
            "rating": g.get("rating_at_game"),
            "platform": g.get("platform"),
            "url": f"{base_url}/game/{gid}",
        })
        per_owner[u] = per_owner.get(u, 0) + 1
        if len(pick) >= n:
            break

    print(f"Selected {len(pick)} games across {len(per_owner)} distinct owners")
    print()
    print(f'{"#":>2}  {"game_id":<38}  {"B":>2} {"M":>2} {"color":<5} {"rating":<6} {"opening":<32}  owner')
    print("-" * 120)
    for i, r in enumerate(pick, 1):
        print(
            f"{i:>2}  {r['game_id']:<38}  "
            f"{r['blunders']:>2} {r['mistakes']:>2} "
            f"{(r.get('user_color') or '?')[:5]:<5} "
            f"{str(r.get('rating') or '?'):<6} "
            f"{(r.get('opening') or '?')[:32]:<32}  "
            f"…{r['user_id'][-6:]}"
        )
    print()

    out_path = "/app/backend/scripts/_snapshots/authoring_round2_candidates.json"
    with open(out_path, "w") as f:
        json.dump(pick, f, indent=2, default=str)
    print(f"Saved → {out_path}")

    # Also print a paste-ready Markdown list
    print()
    print("--- paste-ready list for Parth ---")
    for i, r in enumerate(pick, 1):
        line = f"{i}. [{(r.get('opening') or 'Game')[:48]}]({r['url']}) — {r['blunders']} blunders, {r['mistakes']} mistakes"
        print(line)

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--max-per-owner", type=int, default=3)
    ap.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.n, args.max_per_owner, args.base_url)))
