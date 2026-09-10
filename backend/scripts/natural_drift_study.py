"""
Do players improve on their own, without ChessGuru?
===================================================

The control arm. Without it no improvement claim this product ever makes is
interpretable: a coached 15% reduction means nothing if unaided players
improve 15% anyway.

Run it read-only, server-side:

    docker cp backend/scripts/natural_drift_study.py chess-coach-backend:/app/backend/
    docker exec chess-coach-backend python scripts/natural_drift_study.py

Method: for every user with enough analysed games, split their own history in
half chronologically and compare the per-game rate of each cognitive_gap
between the halves. Rating and opponent rating are printed alongside so a
"improvement" that is really a change of opponent pool is visible rather than
hidden.

Findings as of 2026-09-10 are written up in
docs/natural_improvement_baseline.md. Headline: nothing moves more than 5%,
and roughly half of users move in each direction -- the signature of noise.
These patterns are sticky, which is the strongest evidence available that
there is something for a coach to do.

KNOWN LIMITS, deliberately not hidden:
  * fixed 150cp blunder threshold, while the product grades rating-aware
  * halves split by game COUNT, so the two windows are not equal durations
  * per-game rates, not per-opportunity, so longer games look worse
  * 18 users, with between-user spread from -21% to +24%
"""

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from services.game_dates import game_played_at

BLUNDER_CP = 150
DEFAULT_MIN_GAMES = 200
DEFAULT_MIN_WINDOW = 60


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else None


async def _half_rates(db, rows, blunder_cp):
    """Per-game rate of each cognitive_gap over one window of games."""
    game_ids = [g.get("game_id") for _, g in rows if g.get("game_id")]
    gap_counts = Counter()
    cursor = db.game_analyses.find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1},
    )
    async for doc in cursor:
        moves = (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []
        for move in moves:
            if move.get("is_opponent_move"):
                continue
            if int(move.get("cp_loss") or 0) >= blunder_cp:
                gap_counts[str(move.get("cognitive_gap") or "unlabelled")] += 1
    games = max(1, len(rows))
    return {gap: count / games for gap, count in gap_counts.items()}


async def run(db, min_games, min_window, blunder_cp):
    counts = Counter()
    async for game in db.games.find({"is_analyzed": True}, {"_id": 0, "user_id": 1}):
        counts[game.get("user_id")] += 1
    cohort = [uid for uid, n in counts.items() if n >= min_games]
    print(f"cohort: {len(cohort)} users with >= {min_games} analysed games")
    print(f"blunder threshold: {blunder_cp}cp\n")

    movement = defaultdict(list)
    summaries = []
    undated_total = 0

    for uid in cohort:
        games = await db.games.find(
            {"user_id": uid, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "date_played": 1, "date_played_iso": 1,
             "user_rating": 1, "opponent_rating": 1},
        ).to_list(length=None)
        dated = []
        for game in games:
            when = game_played_at(game)
            if when is None:
                undated_total += 1
                continue
            dated.append((when, game))
        if len(dated) < min_window * 2:
            continue
        dated.sort(key=lambda pair: pair[0])
        split = len(dated) // 2
        early, late = dated[:split], dated[split:]

        rates = {
            "early": await _half_rates(db, early, blunder_cp),
            "late": await _half_rates(db, late, blunder_cp),
        }
        summaries.append({
            "user": uid,
            "games": len(dated),
            "rating": (_mean([g.get("user_rating") for _, g in early]),
                       _mean([g.get("user_rating") for _, g in late])),
            "opponent": (_mean([g.get("opponent_rating") for _, g in early]),
                         _mean([g.get("opponent_rating") for _, g in late])),
            "total": (sum(rates["early"].values()), sum(rates["late"].values())),
        })
        for gap in set(rates["early"]) | set(rates["late"]):
            e = rates["early"].get(gap, 0.0)
            l = rates["late"].get(gap, 0.0)
            if e + l > 0:
                movement[gap].append((e, l))

    print(f"games skipped for an unusable play date: {undated_total}\n")
    print("=== per-user blunder rate, first half vs second half ===")
    header = f"{'user':22}{'games':>7}{'early':>8}{'late':>8}{'chg%':>8}{'rating':>14}{'opponent':>14}"
    print(header)
    fell = 0
    for s in sorted(summaries, key=lambda x: -x["games"]):
        e, l = s["total"]
        change = ((l - e) / e * 100) if e else 0.0
        fell += change < 0
        rating = (f"{s['rating'][0]:.0f}->{s['rating'][1]:.0f}"
                  if all(s["rating"]) else "n/a")
        opponent = (f"{s['opponent'][0]:.0f}->{s['opponent'][1]:.0f}"
                    if all(s["opponent"]) else "n/a")
        print(f"{s['user'][:20]:22}{s['games']:7}{e:8.2f}{l:8.2f}{change:+7.1f}%"
              f"{rating:>14}{opponent:>14}")
    print(f"\nusers whose blunder rate fell: {fell} of {len(summaries)}")

    print("\n=== natural drift per pattern (mean across users) ===")
    print(f"{'pattern':26}{'users':>7}{'early':>8}{'late':>8}{'chg%':>9}{'improved':>11}")
    rows = []
    for gap, entries in movement.items():
        if len(entries) < 5:
            continue
        e = sum(x[0] for x in entries) / len(entries)
        l = sum(x[1] for x in entries) / len(entries)
        change = ((l - e) / e * 100) if e else 0.0
        improved = sum(1 for x in entries if x[1] < x[0])
        rows.append((gap, len(entries), e, l, change, improved))
    for gap, n, e, l, change, improved in sorted(rows, key=lambda r: r[4]):
        print(f"{gap:26}{n:7}{e:8.2f}{l:8.2f}{change:+8.1f}%{improved:>7}/{n:<4}")
    print("\nA pattern near 0% with roughly half the users in each direction is "
          "noise, not improvement.")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-games", type=int, default=DEFAULT_MIN_GAMES)
    parser.add_argument("--min-window", type=int, default=DEFAULT_MIN_WINDOW)
    parser.add_argument("--blunder-cp", type=int, default=BLUNDER_CP)
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    await run(db, args.min_games, args.min_window, args.blunder_cp)


if __name__ == "__main__":
    asyncio.run(main())
