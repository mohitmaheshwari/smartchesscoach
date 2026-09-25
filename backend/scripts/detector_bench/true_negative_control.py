"""The control my whole bench was missing: positions with NO tactic.

clearance fires on 47.0% of real games - as often as fork. A clearance
sacrifice does not occur in half of all 600-1500 games. That is not a find,
it is a smell.

Recall against a themed puzzle set cannot catch this. Cross-fire against fork
and pin cannot either: a detector that fires on everything scores high recall
and can still look clean against two specific themes. The quality lock asks
for ">=20 true negative/non-opportunity cases" precisely here.

True negatives used: real user moves the engine scored at <30cp loss. The user
played essentially the best move, so there was no missed tactic to find. Any
fire there is a false positive.

A prover that fires on good moves as often as on blunders is measuring
"a position exists", not a motif.

Read-only.
"""
import os, sys, asyncio, collections, json, inspect, importlib
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

PROVERS = [
    ("clearance_puzzle_proof", "build_clearance_proof"),
    ("trapped_piece_puzzle_proof", "build_trapped_piece_opportunity_proof"),
    ("advanced_pawn_puzzle_proof", "build_advanced_pawn_proof"),
    ("xray_attack_puzzle_proof", "build_xray_attack_proof"),
    ("deflection_puzzle_proof", "build_deflection_proof"),
    ("interference_puzzle_proof", "build_interference_proof"),
    ("attraction_puzzle_proof", "build_attraction_proof"),
    ("fork_puzzle_proof", "build_fork_proof"),   # wired control
]


def make_caller(fn):
    names = list(inspect.signature(fn).parameters)
    if len(names) >= 2 and names[1] == "move_evaluation":
        return lambda b, p, m, pv, cp: fn(
            b, {"fen_before": b.fen(), "move_uci": p, "best_move_uci": m, "cp_loss": cp}, p, m)
    if "pv_after_best" in names:
        return lambda b, p, m, pv, cp: fn(b, p, m, pv, cp)
    return lambda b, p, m, pv, cp: fn(b, p, m, cp)


async def main():
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]
    limit = int(os.environ.get("GAMES", 400))

    callers = {}
    for mod, bname in PROVERS:
        try:
            callers[bname] = make_caller(getattr(importlib.import_module("services.%s" % mod), bname))
        except Exception as e:
            print("bind failed %s: %s" % (bname, str(e)[:40]))

    blunder = collections.Counter()   # cp_loss >= 100  (opportunity)
    quiet = collections.Counter()     # cp_loss <  30   (true negative)
    n_bl = n_q = 0

    cur = db.game_analyses.find({}, {"_id": 0, "stockfish_analysis": 1}).limit(limit)
    async for a in cur:
        for ev in (a.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if ev.get("is_opponent_move"):
                continue
            fen = ev.get("fen_before") or ev.get("fen")
            played = ev.get("move_uci") or ev.get("played_move_uci")
            best = ev.get("best_move_uci") or ev.get("best_move")
            cp = ev.get("cp_loss")
            if not (fen and played and best) or cp is None:
                continue
            try:
                board = chess.Board(fen)
                cp = int(cp)
            except Exception:
                continue
            pv = ev.get("pv_after_best") or ev.get("best_line") or []
            if cp >= 100:
                bucket, n = blunder, "bl"
            elif cp < 30:
                bucket, n = quiet, "q"
            else:
                continue
            if n == "bl":
                n_bl += 1
            else:
                n_q += 1
            for bname, call in callers.items():
                try:
                    # a quiet move IS the best move; feed the real cp so the
                    # prover's own loss gate decides, do not fake 300
                    if call(board, played, best, pv, cp) is not None:
                        bucket[bname] += 1
                except Exception:
                    continue

    print("opportunity moves (cp_loss >= 100): %d" % n_bl)
    print("TRUE NEGATIVE moves (cp_loss < 30): %d\n" % n_q)
    print("%-42s %12s %14s %10s" % ("prover", "fires/blunder", "fires/QUIET", "ratio"))
    print("-" * 82)
    rows = []
    for bname in callers:
        rb = 100.0 * blunder[bname] / max(n_bl, 1)
        rq = 100.0 * quiet[bname] / max(n_q, 1)
        ratio = (rb / rq) if rq > 0 else float("inf")
        rows.append((ratio, bname, rb, rq))
    for ratio, bname, rb, rq in sorted(rows, reverse=True):
        r = "inf" if ratio == float("inf") else "%.1fx" % ratio
        flag = ""
        if rq > 5:
            flag = "   <- fires on GOOD moves"
        print("%-42s %11.1f%% %13.1f%% %10s%s" % (bname, rb, rq, r, flag))

    print("\nratio = how much more often it fires on a real mistake than on a")
    print("good move. Near 1.0x means the prover is not discriminating at all.")

    with open("/tmp/true_negatives.json", "w") as f:
        json.dump({"n_blunder": n_bl, "n_quiet": n_q,
                   "blunder": dict(blunder), "quiet": dict(quiet)}, f, indent=1)

asyncio.run(main())
