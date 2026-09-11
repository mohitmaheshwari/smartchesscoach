"""
Why did this player's rating move? Attribute it, or admit we cannot
===================================================================


A rating gain has at least four possible causes:
  1. the player actually improved
  2. the opponent pool got weaker
  3. opponents played badly (NOT the same as being rated lower)
  4. variance -- a random walk with drift; +/-100 over a few hundred games
     needs no cause at all

We can measure 1 (own cp_loss) and 2 (opponent_rating). We CANNOT measure 3:
only 3 of 14,806 analyses contain an opponent move, so half of every game is
discarded. 4 is estimated here as the spread among players whose own accuracy
did not move.

"unexplained" is a legitimate verdict and is reported as such rather than
being resolved into a story.

Reference run, 2026-09-11 (18 users with >=200 analysed games):
  * the noise floor is enormous. Among players whose own blunder rate did
    NOT materially change, rating moves ranged -110 to +279. Anything
    inside that band needs no explanation at all.
  * 7 of 18 came back "unexplained" and were left that way.
  * an earlier version of this script labelled 5 users "stronger
    opponents". That inverted cause and effect: opponent rating RISES
    because the player climbed and matchmaking followed. Rising opponent
    rating is a consequence of the gain, not a competing explanation for
    it, so it is no longer reported as a cause of a GAIN.
  * the pool-change verdicts that remain are the falling ones, and they
    are weak: see scripts/opponent_blunder_pilot.py, which evaluated both
    sides of real games and found opponents blundering LESS, not more.

    docker exec chess-coach-backend python scripts/rating_change_attribution.py
"""
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from services.game_dates import game_played_at

MIN_GAMES = 200
BLUNDER_CP = 150
# What counts as a real move rather than noise. Set from the observed spread,
# not from taste: see the noise-floor block printed at the end.
ACC_MATERIAL_PCT = 8.0
POOL_MATERIAL_ELO = 40.0


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return sum(xs) / len(xs) if xs else None


async def half_stats(db, rows):
    ids = [g["game_id"] for _, g in rows if g.get("game_id")]
    blunders = 0
    async for d in db.game_analyses.find(
        {"game_id": {"$in": ids}}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}
    ):
        for m in (d.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if m.get("is_opponent_move"):
                continue
            if int(m.get("cp_loss") or 0) >= BLUNDER_CP:
                blunders += 1
    n = max(1, len(rows))
    wins = 0
    for _, g in rows:
        res, colour = str(g.get("result") or ""), str(g.get("user_color") or "")
        white = colour.lower().startswith("w")
        if (res == "1-0" and white) or (res == "0-1" and not white):
            wins += 1
    return {
        "blunders_per_game": blunders / n,
        "win_pct": wins / n * 100,
        "rating": mean([g.get("user_rating") for _, g in rows]),
        "opponent": mean([g.get("opponent_rating") for _, g in rows]),
        "games": n,
    }


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ.get("DB_NAME", "chess_coach")]

    counts = Counter()
    async for g in db.games.find({"is_analyzed": True}, {"_id": 0, "user_id": 1}):
        counts[g.get("user_id")] += 1
    cohort = [u for u, n in counts.items() if n >= MIN_GAMES]

    rows_out = []
    for uid in cohort:
        games = await db.games.find(
            {"user_id": uid, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "date_played": 1, "date_played_iso": 1,
             "user_rating": 1, "opponent_rating": 1, "result": 1, "user_color": 1},
        ).to_list(length=None)
        dated = [(w, g) for g in games if (w := game_played_at(g))]
        if len(dated) < 120:
            continue
        dated.sort(key=lambda p: p[0])
        h = len(dated) // 2
        early = await half_stats(db, dated[:h])
        late = await half_stats(db, dated[h:])
        if not (early["rating"] and late["rating"]):
            continue

        d_rating = late["rating"] - early["rating"]
        d_acc = ((late["blunders_per_game"] - early["blunders_per_game"])
                 / early["blunders_per_game"] * 100) if early["blunders_per_game"] else 0.0
        d_pool = ((late["opponent"] - early["opponent"])
                  if (early["opponent"] and late["opponent"]) else None)
        d_win = late["win_pct"] - early["win_pct"]

        improved = d_acc <= -ACC_MATERIAL_PCT
        degraded = d_acc >= ACC_MATERIAL_PCT
        pool_weaker = d_pool is not None and d_pool <= -POOL_MATERIAL_ELO
        pool_stronger = d_pool is not None and d_pool >= POOL_MATERIAL_ELO

        if improved and not pool_weaker:
            verdict = "played better"
        elif degraded and not pool_stronger:
            verdict = "played worse"
        elif pool_weaker and not improved:
            verdict = "weaker opponents"
        elif pool_stronger and not degraded:
            verdict = "stronger opponents"
        else:
            verdict = "unexplained"
        rows_out.append((uid, len(dated), d_rating, d_acc, d_pool, d_win, verdict))

    print(f"{'user':22}{'games':>7}{'d_rating':>10}{'d_acc%':>9}{'d_pool':>9}{'d_win%':>9}  verdict")
    for uid, n, dr, da, dp, dw, v in sorted(rows_out, key=lambda r: -r[2]):
        pool = f"{dp:+.0f}" if dp is not None else "n/a"
        print(f"{uid[:20]:22}{n:7}{dr:+10.0f}{da:+8.1f}%{pool:>9}{dw:+8.1f}%  {v}")

    print("\n=== noise floor ===")
    flat = [r for r in rows_out if abs(r[3]) < ACC_MATERIAL_PCT]
    if flat:
        drs = sorted(r[2] for r in flat)
        print(f"  players whose accuracy did NOT materially change: {len(flat)}")
        print(f"  their rating changes ranged {drs[0]:+.0f} to {drs[-1]:+.0f} "
              f"(median {drs[len(drs)//2]:+.0f})")
        print("  => a rating move inside that band needs no explanation.")
    print("\nverdicts:", dict(Counter(r[6] for r in rows_out)))
    print("\nNOT MEASURABLE: whether opponents actually PLAYED worse. Only 3 of "
          "14,806 analyses contain an opponent move, so opponent rating is the "
          "only available proxy, and it cannot see a 1200 having a bad day.")


if __name__ == "__main__":
    asyncio.run(main())
