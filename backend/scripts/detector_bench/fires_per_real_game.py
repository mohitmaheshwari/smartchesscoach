"""How often do the UNWIRED provers fire in real 600-1500 games?

Lichess recall says a prover is correct when the motif is present. It says
nothing about how often the motif is present in this product's games. Recorded
lesson (project_detector_coverage_inverts_priority): promoted discovered_attack
fires on 1.8% of games while simple_hang at 45.6% sat in shadow. Measure
fires/game BEFORE spending review time.

These seven have 92.5-100% Lichess recall and zero production callers. This
ranks them by how much coaching they would actually add.

Positive control: build_fork_proof is already wired and known to fire, so it
must come back non-zero. A wall of zeros is then a finding, not a broken probe.

Read-only.
"""
import os, sys, asyncio, collections, json, inspect, importlib
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

UNWIRED = [
    ("interference_puzzle_proof", "build_interference_proof"),
    ("advanced_pawn_puzzle_proof", "build_advanced_pawn_proof"),
    ("xray_attack_puzzle_proof", "build_xray_attack_proof"),
    ("deflection_puzzle_proof", "build_deflection_proof"),
    ("clearance_puzzle_proof", "build_clearance_proof"),
    ("attraction_puzzle_proof", "build_attraction_proof"),
    ("trapped_piece_puzzle_proof", "build_trapped_piece_opportunity_proof"),
    ("fork_puzzle_proof", "build_fork_proof"),          # positive control, wired
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
    for mod, bname in UNWIRED:
        try:
            callers[bname] = make_caller(getattr(importlib.import_module("services.%s" % mod), bname))
        except Exception as e:
            print("bind failed %s: %s" % (bname, str(e)[:50]))

    games = 0
    moves = 0
    fires = collections.Counter()
    games_with = collections.Counter()

    cur = db.game_analyses.find({}, {"_id": 0, "game_id": 1, "stockfish_analysis": 1}).limit(limit)
    async for a in cur:
        sf = a.get("stockfish_analysis") or {}
        evs = sf.get("move_evaluations") or []
        if not evs:
            continue
        games += 1
        seen = set()
        for ev in evs:
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
            if cp < 100:
                continue
            moves += 1
            pv = ev.get("pv_after_best") or ev.get("best_line") or []
            for bname, call in callers.items():
                try:
                    if call(board, played, best, pv, cp) is not None:
                        fires[bname] += 1
                        seen.add(bname)
                except Exception:
                    continue
        for b in seen:
            games_with[b] += 1

    print("games with evaluations : %d" % games)
    print("user moves >=100cp loss: %d\n" % moves)
    print("%-42s %8s %10s %12s" % ("prover (all unwired but the control)", "fires", "fires/game", "% of games"))
    print("-" * 78)
    for bname in sorted(callers, key=lambda b: -games_with[b]):
        tag = "  <- CONTROL (wired)" if bname == "build_fork_proof" else ""
        print("%-42s %8d %10.2f %11.1f%%%s"
              % (bname, fires[bname], fires[bname] / max(games, 1),
                 100.0 * games_with[bname] / max(games, 1), tag))

    with open("/tmp/fires_per_game.json", "w") as f:
        json.dump({"games": games, "moves": moves,
                   "fires": dict(fires), "games_with": dict(games_with)}, f, indent=1)

asyncio.run(main())
