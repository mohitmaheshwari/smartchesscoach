"""Control 3 at full power: does trade_seeking travel across time controls?

The 4,000-game sample left only 13 players with both a fast and a slow
sample, which cannot carry the conclusion. So this does not sample: it finds
every user who HAS both kinds of game and processes all of their games.

The time control comes from the PGN's [TimeControl] tag, extracted in the
query, because games.time_control mixes the platform's category ("rapid")
with the real control ("900+10") in one field and grouping on it groups on
two things at once.

Also reports what user_rating actually contains, because control 2 ran over a
range of 202 to 2171 and 202 is not a chess rating.

Read-only. Batched, projected, nothing large held.
"""
import asyncio
import collections
import math
import os
import statistics
import sys

import chess

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

LEVEL_CP = 100
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MIN_GAMES_PER_BUCKET = 12
MIN_OFFERS_PER_BUCKET = 25
BATCH = 40


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
    if len(xs) < 3:
        return float("nan")
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def bucket_of(tc):
    base = str(tc or "").split("+")[0]
    try:
        secs = int(base)
    except Exception:
        return None
    if secs <= 300:
        return "fast"
    if secs >= 600:
        return "slow"
    return None            # 5-10 min is neither; keep the ends clean


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]

    # --- who has both kinds of game, from the PGN tag ---------------------
    print("finding users with both a fast and a slow sample...", flush=True)
    per_user = collections.defaultdict(lambda: collections.defaultdict(list))
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$project": {
            "_id": 0, "game_id": 1, "user_id": 1,
            "tc": {"$regexFind": {"input": "$pgn", "regex": r'\[TimeControl "([^"]+)"\]'}},
        }},
    ], allowDiskUse=True):
        found = g.get("tc") or {}
        captures = found.get("captures") or []
        tc = captures[0] if captures else None
        b = bucket_of(tc)
        if b:
            per_user[g["user_id"]][b].append(g["game_id"])

    eligible = {u: d for u, d in per_user.items()
                if len(d.get("fast", [])) >= MIN_GAMES_PER_BUCKET
                and len(d.get("slow", [])) >= MIN_GAMES_PER_BUCKET}
    print("users with >= %d games in BOTH buckets: %d" % (MIN_GAMES_PER_BUCKET, len(eligible)))
    wanted = {}
    for uid, d in eligible.items():
        for b in ("fast", "slow"):
            for gid in d[b]:
                wanted[gid] = (uid, b)
    print("games to process: %d\n" % len(wanted), flush=True)

    # --- measure ----------------------------------------------------------
    tally = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    ids = list(wanted)
    done = 0
    for i in range(0, len(ids), BATCH):
        async for a in db.game_analyses.find(
            {"game_id": {"$in": ids[i:i + BATCH]}},
            {"_id": 0, "game_id": 1,
             "stockfish_analysis.move_evaluations.fen_before": 1,
             "stockfish_analysis.move_evaluations.move": 1,
             "stockfish_analysis.move_evaluations.eval_before": 1,
             "stockfish_analysis.move_evaluations.is_opponent_move": 1},
        ):
            uid, b = wanted.get(a["game_id"], (None, None))
            if uid is None:
                continue
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
                tally[uid][b][0] += 1
                try:
                    if board.parse_san(san) in available:
                        tally[uid][b][1] += 1
                except Exception:
                    pass
        done += BATCH
        if done % 800 == 0:
            print("   ...%d games" % min(done, len(ids)), flush=True)

    pairs = []
    for uid, d in tally.items():
        f, s = d.get("fast", [0, 0]), d.get("slow", [0, 0])
        if f[0] >= MIN_OFFERS_PER_BUCKET and s[0] >= MIN_OFFERS_PER_BUCKET:
            pairs.append((f[1] / f[0], s[1] / s[0], f[0], s[0]))

    print()
    print("=" * 74)
    print("CONTROL 3 (full corpus) -- does the rate travel across time controls?")
    print("=" * 74)
    print("players with >= %d offers in BOTH buckets: %d" % (MIN_OFFERS_PER_BUCKET, len(pairs)))
    if len(pairs) >= 3:
        r = pearson([p[0] for p in pairs], [p[1] for p in pairs])
        gaps = [abs(p[0] - p[1]) for p in pairs]
        print("   r(fast, slow)      = %+.2f" % r)
        print("   median |fast-slow| = %.3f" % statistics.median(gaps))
        print("   the spread ACROSS players was 0.156, so a gap well under that")
        print("   means a player keeps their own level in both pools")
        fast = [p[0] for p in pairs]
        slow = [p[1] for p in pairs]
        print("   median rate fast %.3f vs slow %.3f  (a systematic shift would"
              % (statistics.median(fast), statistics.median(slow)))
        print("   mean trading is clock management, not preference)")
    else:
        print("   still too few players")

    # --- what does user_rating actually hold? ------------------------------
    print()
    print("=" * 74)
    print("ASIDE -- what user_rating contains (control 2 ran 202 to 2171)")
    print("=" * 74)
    vals = []
    async for g in db.games.find({"is_analyzed": True, "user_rating": {"$ne": None}},
                                 {"_id": 0, "user_rating": 1}).limit(20000):
        try:
            vals.append(float(g["user_rating"]))
        except Exception:
            pass
    if vals:
        vals.sort()
        under = sum(1 for v in vals if v < 400)
        over = sum(1 for v in vals if v > 3000)
        print("   rows %d | min %.0f | p10 %.0f | median %.0f | p90 %.0f | max %.0f"
              % (len(vals), vals[0], vals[len(vals) // 10], statistics.median(vals),
                 vals[9 * len(vals) // 10], vals[-1]))
        print("   below 400 (not a real rating): %d = %.1f%%" % (under, 100 * under / len(vals)))
        print("   above 3000: %d" % over)


asyncio.run(main())
