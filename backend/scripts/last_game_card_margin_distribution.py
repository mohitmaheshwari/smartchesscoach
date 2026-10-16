"""How big is the gap between the two players' mean cp loss, normally?

`card_from_review` says "You were the sharper player" whenever his mean is
lower by ANY amount. On the game it first fired on the margin was 11.9cp --
and he had been objectively losing by nearly five pawns at move 30 -- which
looked like a sentence resting on noise, so a minimum margin was drafted.

Measured first, over his 40 most recent games (2026-10-16):

    |margin|  median 22.8cp   mean 31.5cp
    |margin| < 10cp:  0/40 =  0%
    |margin| < 15cp:  6/40 = 15%
    the lower-mean player won 36/40 = 90%   (no threshold at all)
    the lower-mean player won 24/26 = 92%   (margin >= 20cp)
    the lower-mean player won 12/14 = 86%   (margin >= 30cp)

The threshold was dropped. There is no mass near zero to protect against,
and raising the bar does not buy agreement with the result -- it only makes
the card silent on games where the claim is already right nine times in ten.

Re-run this before changing how `sharper` is decided.
"""
import asyncio
import os
import statistics
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

from services.both_sides_review import review_both_sides

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"user_id": {"$regex": "8b599930d7ef"}}, {"_id": 0, "user_id": 1})
    cur = db.games.find(
        {
            "user_id": user["user_id"],
            "platform": {"$ne": "coach"},
            "pgn": {"$nin": [None, ""]},
            "played_at_utc": {"$ne": None},
        },
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "result": 1, "termination": 1},
        sort=[("played_at_utc", -1)],
    ).limit(N)

    rows = []
    async for g in cur:
        r = review_both_sides(g.get("pgn"), str(g.get("user_color")))
        if not r:
            continue
        colour = str(g.get("user_color"))
        res = str(g.get("result") or "")
        won = (res == "1-0" and colour == "white") or (res == "0-1" and colour == "black")
        rows.append(
            {
                "margin": round(r["his_mean_cp"] - r["their_mean_cp"], 1),
                "won": won,
                "term": str(g.get("termination") or ""),
            }
        )
        print(f"  {len(rows):>3} {g['game_id'][:8]} margin={rows[-1]['margin']:>7} won={won}", flush=True)

    m = [abs(x["margin"]) for x in rows]
    m.sort()
    print(f"\nGames reviewed: {len(rows)}")
    print(f"|margin| median {statistics.median(m)}  mean {round(statistics.mean(m),1)}")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q}: {m[min(len(m)-1, int(len(m)*q/100))]}")
    for band in (5, 10, 15, 20, 30, 50):
        n = sum(1 for x in m if x < band)
        print(f"  |margin| < {band:>3}cp: {n}/{len(m)} = {round(100*n/len(m))}%")

    # Does the lower mean actually track the result? If "sharper" never
    # agrees with who won, the sentence is describing noise.
    for band in (0, 10, 20, 30):
        sub = [x for x in rows if abs(x["margin"]) >= band]
        agree = sum(1 for x in sub if (x["margin"] < 0) == x["won"])
        if sub:
            print(f"  margin>={band:>3}cp: lower-mean player won {agree}/{len(sub)} = {round(100*agree/len(sub))}%")


asyncio.run(main())
