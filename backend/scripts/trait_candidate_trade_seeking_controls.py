"""trade_seeking passed its first three tests. Two controls before believing it.

  r = 0.71 stability, spread 0.156, and r = +0.14 against error rate.

CONTROL 1 -- THE RISING BAR
    A real but noise-limited measure gets MORE stable as the minimum sample
    rises, the way conversion climbed 0.41 -> 0.72 in behaviour_profile. A
    non-trait stays flat or bounces. This is the test that separated a weak
    trait from no trait at all.

CONTROL 2 -- IS IT RATING?
    The error-rate control already came back near zero, but rating is the
    other face of strength and is stored separately. If trade-taking is just
    what stronger players do, r(rate, rating) will say so.

CONTROL 3 -- DOES IT SURVIVE THE CONDITIONS?
    "Consistent across periods, opponents, openings and time controls." The
    cheapest version: does a player keep their rate across DIFFERENT time
    controls? A disposition should; an artefact of one pool should not.

Read-only.
"""
import asyncio
import collections
import math
import os
import re
import statistics
import sys

import chess

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
BATCH = 40
LEVEL_CP = 100
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
TC_TAG = re.compile(r'\[TimeControl "([^"]+)"\]')


def offered_trades(board):
    out = []
    legal = list(board.legal_moves)
    if len(legal) < 2:
        return out
    for move in legal:
        if not board.is_capture(move) or board.is_en_passant(move):
            continue
        attacker = board.piece_at(move.from_square)
        victim = board.piece_at(move.to_square)
        if attacker is None or victim is None:
            continue
        a, v = VALUE.get(attacker.piece_type), VALUE.get(victim.piece_type)
        if a is None or v is None or abs(a - v) > 1:
            continue
        after = board.copy()
        after.push(move)
        if not after.attackers(not board.turn, move.to_square):
            continue
        out.append(move)
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "played_at_utc": {"$ne": None}}},
        {"$sample": {"size": N_GAMES}},
        {"$project": {"_id": 0, "game_id": 1, "user_id": 1, "played_at_utc": 1,
                      "user_rating": 1, "pgn": 1}},
    ]):
        games.append(g)
    meta = {g["game_id"]: g for g in games}

    per_game = collections.defaultdict(dict)
    ids = list(meta)
    for i in range(0, len(ids), BATCH):
        async for a in db.game_analyses.find(
            {"game_id": {"$in": ids[i:i + BATCH]}},
            {"_id": 0, "game_id": 1, "user_id": 1,
             "stockfish_analysis.move_evaluations.fen_before": 1,
             "stockfish_analysis.move_evaluations.move": 1,
             "stockfish_analysis.move_evaluations.eval_before": 1,
             "stockfish_analysis.move_evaluations.is_opponent_move": 1},
        ):
            offers = taken = 0
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if m.get("is_opponent_move"):
                    continue
                ev, fen, san = m.get("eval_before"), m.get("fen_before"), m.get("move")
                if ev is None or not fen or not san or abs(ev) >= LEVEL_CP:
                    continue
                try:
                    board = chess.Board(fen)
                except Exception:
                    continue
                available = offered_trades(board)
                if not available:
                    continue
                offers += 1
                try:
                    if board.parse_san(san) in available:
                        taken += 1
                except Exception:
                    pass
            if offers:
                per_game[a.get("user_id")][a["game_id"]] = (offers, taken)

    print("games sampled: %d; players with any offers: %d\n" % (len(games), len(per_game)))

    # ---- CONTROL 1: the rising bar --------------------------------------
    print("=" * 74)
    print("CONTROL 1 -- does stability CLIMB as the minimum sample rises?")
    print("=" * 74)
    for bar in (10, 20, 40, 80, 120):
        firsts, seconds = [], []
        for uid, rows in per_game.items():
            when = {gid: str(meta[gid].get("played_at_utc") or "") for gid in rows if gid in meta}
            ordered = sorted((g for g in rows if g in when), key=lambda g: when[g])
            if len(ordered) < 6:
                continue
            mid = len(ordered) // 2
            a_o = sum(rows[g][0] for g in ordered[:mid])
            a_t = sum(rows[g][1] for g in ordered[:mid])
            b_o = sum(rows[g][0] for g in ordered[mid:])
            b_t = sum(rows[g][1] for g in ordered[mid:])
            if a_o >= bar and b_o >= bar:
                firsts.append(a_t / a_o)
                seconds.append(b_t / b_o)
        r = pearson(firsts, seconds) if len(firsts) >= 3 else float("nan")
        print("   >= %3d offers per half : r = %5.2f   (%d players)" % (bar, r, len(firsts)))
    print("   climbing  -> real, the early reading was noise")
    print("   flat/bouncy -> not a trait (comeback was 0.12/0.07/0.00/0.14)")

    # ---- CONTROL 2: is it rating? ---------------------------------------
    print()
    print("=" * 74)
    print("CONTROL 2 -- is trade-taking just what stronger players do?")
    print("=" * 74)
    xs, ys = [], []
    for uid, rows in per_game.items():
        o = sum(v[0] for v in rows.values())
        t = sum(v[1] for v in rows.values())
        if o < 30:
            continue
        ratings = [meta[g].get("user_rating") for g in rows if g in meta and meta[g].get("user_rating")]
        ratings = [float(r) for r in ratings if str(r).replace(".", "").isdigit()]
        if len(ratings) < 3:
            continue
        xs.append(t / o)
        ys.append(statistics.median(ratings))
    if len(xs) >= 3:
        print("   r(trade rate, rating) = %+.2f over %d players" % (pearson(xs, ys), len(xs)))
        print("   rating range %d to %d" % (int(min(ys)), int(max(ys))))
    else:
        print("   not enough players carry a rating")

    # ---- CONTROL 3: across time controls --------------------------------
    print()
    print("=" * 74)
    print("CONTROL 3 -- does a player hold their rate across time controls?")
    print("=" * 74)
    pairs = []
    for uid, rows in per_game.items():
        buckets = collections.defaultdict(lambda: [0, 0])
        for gid, (o, t) in rows.items():
            pgn = (meta.get(gid) or {}).get("pgn") or ""
            found = TC_TAG.search(pgn)
            tc = found.group(1) if found else "?"
            base = tc.split("+")[0]
            try:
                secs = int(base)
            except Exception:
                continue
            key = "fast" if secs <= 300 else "slow"
            buckets[key][0] += o
            buckets[key][1] += t
        if (buckets["fast"][0] >= 25 and buckets["slow"][0] >= 25):
            pairs.append((buckets["fast"][1] / buckets["fast"][0],
                          buckets["slow"][1] / buckets["slow"][0]))
    if len(pairs) >= 3:
        r = pearson([p[0] for p in pairs], [p[1] for p in pairs])
        diffs = [abs(a - b) for a, b in pairs]
        print("   r(fast, slow) = %+.2f over %d players" % (r, len(pairs)))
        print("   median gap between a player's fast and slow rate: %.3f" % statistics.median(diffs))
        print("   a disposition travels; an artefact of one pool does not")
    else:
        print("   only %d players have both a fast and a slow sample" % len(pairs))


asyncio.run(main())
