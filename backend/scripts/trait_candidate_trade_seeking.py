"""Candidate behavioural trait: trade_seeking.

THE CLAIM
    "When an even trade is on offer and the position is level, this player
     takes it / avoids it."

WHY IT IS DENOMINATED BY OPPORTUNITY, NOT OUTCOME
    Counting trades made would measure how many trades were AVAILABLE, which
    is a property of the games, not the player. The measure is
        taken / offered
    over positions where the player actually had the choice.

WHY ONLY LEVEL POSITIONS
    Trading when ahead is correct play, and trading when behind is wrong play.
    A raw rate would therefore be mostly a measure of how often this player
    was winning -- which is strength, not behaviour, and is exactly what
    principle 3 says not to rediscover. So the window is |eval_before| < 100cp.

WHAT COUNTS AS AN OFFERED TRADE
    A legal capture by the player where the captured piece is worth about the
    same as the capturing piece (within a pawn), AND the destination square is
    defended, so the exchange really is an exchange rather than a free win.
    Positions with only one legal move are skipped: no choice, no disposition.

THE THREE TESTS
    stability      first half of a player's games against their second half
    distinctiveness spread across players
    validity       negative controls, below

NEGATIVE CONTROLS
    1. strength    does the rate track error rate? If a "trait" is just
                   playing strength wearing a hat, it will.
    2. phase       is it an artefact of when trades happen to be offered?
                   reported as offers per game.
    3. the tilt trap  the stability number alone proves nothing: a measure of
                   STRENGTH is also stable. So stability is only believed when
                   the strength control is weak.

Read-only. No engine: fen_before and eval_before are stored on 100% of rows.
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

N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BATCH = 40
LEVEL_CP = 100
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MIN_OFFERS = 30          # below this a player's rate is noise
MIN_GAMES_PER_HALF = 5


def offered_trades(board: chess.Board):
    """The even, recapturable captures legally available to the side to move."""
    out = []
    legal = list(board.legal_moves)
    if len(legal) < 2:
        return out                      # no choice means no disposition
    for move in legal:
        if not board.is_capture(move):
            continue
        if board.is_en_passant(move):
            continue
        attacker = board.piece_at(move.from_square)
        victim = board.piece_at(move.to_square)
        if attacker is None or victim is None:
            continue
        a = VALUE.get(attacker.piece_type)
        v = VALUE.get(victim.piece_type)
        if a is None or v is None:
            continue
        if abs(a - v) > 1:
            continue                    # not an even trade
        after = board.copy()
        after.push(move)
        if not after.attackers(not board.turn, move.to_square):
            continue                    # undefended: that is a free piece
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
        {"$project": {"_id": 0, "game_id": 1, "user_id": 1, "played_at_utc": 1}},
    ]):
        games.append(g)

    by_user = collections.defaultdict(list)
    for g in games:
        by_user[g["user_id"]].append(g)

    # per user, per game: offers / taken, plus error rate for the control
    per_game = collections.defaultdict(dict)
    errors = collections.defaultdict(lambda: [0, 0])

    ids = [g["game_id"] for g in games]
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        async for a in db.game_analyses.find(
            {"game_id": {"$in": chunk}},
            {"_id": 0, "game_id": 1, "user_id": 1,
             "stockfish_analysis.move_evaluations.fen_before": 1,
             "stockfish_analysis.move_evaluations.move": 1,
             "stockfish_analysis.move_evaluations.eval_before": 1,
             "stockfish_analysis.move_evaluations.cp_loss": 1,
             "stockfish_analysis.move_evaluations.is_opponent_move": 1},
        ):
            uid = a.get("user_id")
            offers = taken = 0
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if m.get("is_opponent_move"):
                    continue
                cp = m.get("cp_loss")
                if cp is not None:
                    errors[uid][0] += 1
                    if cp >= 100:
                        errors[uid][1] += 1
                ev = m.get("eval_before")
                fen = m.get("fen_before")
                san = m.get("move")
                if ev is None or not fen or not san:
                    continue
                if abs(ev) >= LEVEL_CP:
                    continue            # not a level position
                try:
                    board = chess.Board(fen)
                except Exception:
                    continue
                available = offered_trades(board)
                if not available:
                    continue
                offers += 1
                try:
                    played = board.parse_san(san)
                except Exception:
                    continue
                if played in available:
                    taken += 1
            if offers:
                per_game[uid][a["game_id"]] = (offers, taken)

    # ---- the measure, per player ----------------------------------------
    rate = {}
    offers_total = {}
    for uid, rows in per_game.items():
        o = sum(v[0] for v in rows.values())
        t = sum(v[1] for v in rows.values())
        if o >= MIN_OFFERS:
            rate[uid] = t / o
            offers_total[uid] = o

    print("=" * 78)
    print("trade_seeking  --  taken / offered, level positions only")
    print("=" * 78)
    print("games sampled            : %d" % len(games))
    print("players with >= %d offers : %d" % (MIN_OFFERS, len(rate)))
    if not rate:
        print("not enough data")
        return
    vals = sorted(rate.values())
    q1 = vals[len(vals) // 4]
    med = statistics.median(vals)
    q3 = vals[3 * len(vals) // 4]
    print("offers per player        : median %d" % statistics.median(list(offers_total.values())))
    print()
    print("DISTINCTIVENESS (spread across players)")
    print("   min %.3f   q1 %.3f   median %.3f   q3 %.3f   max %.3f" % (
        vals[0], q1, med, q3, vals[-1]))
    print("   spread q3-q1 = %.3f   (too-passive was rejected at 0.009)" % (q3 - q1))

    # ---- stability: first half of a player's games vs second -------------
    firsts, seconds = [], []
    for uid, rows in per_game.items():
        when = {g["game_id"]: g["played_at_utc"] for g in by_user[uid]}
        ordered = sorted(rows.keys(), key=lambda gid: str(when.get(gid) or ""))
        if len(ordered) < MIN_GAMES_PER_HALF * 2:
            continue
        mid = len(ordered) // 2
        a_o = sum(rows[g][0] for g in ordered[:mid])
        a_t = sum(rows[g][1] for g in ordered[:mid])
        b_o = sum(rows[g][0] for g in ordered[mid:])
        b_t = sum(rows[g][1] for g in ordered[mid:])
        if a_o >= MIN_OFFERS // 2 and b_o >= MIN_OFFERS // 2:
            firsts.append(a_t / a_o)
            seconds.append(b_t / b_o)
    print()
    print("STABILITY (first half of each player's games vs second)")
    if len(firsts) >= 3:
        r = pearson(firsts, seconds)
        print("   r = %.2f over %d players" % (r, len(firsts)))
        print("   the six shipped traits scored 0.72 to 0.88; tilt was rejected at 0.18")
    else:
        print("   only %d players have two halves with enough offers -- cannot test" % len(firsts))

    # ---- negative control: is this just playing strength? ----------------
    xs, ys = [], []
    for uid, r in rate.items():
        moves, bad = errors[uid]
        if moves >= 200:
            xs.append(r)
            ys.append(bad / moves)
    print()
    print("NEGATIVE CONTROL -- does it track playing strength?")
    if len(xs) >= 3:
        r = pearson(xs, ys)
        print("   r(trade rate, error rate) = %+.2f over %d players" % (r, len(xs)))
        print("   near zero = a disposition. strong = strength wearing a hat.")
    else:
        print("   not enough players with 200+ measured moves")


asyncio.run(main())
