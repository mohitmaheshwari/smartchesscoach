"""Corrected prover bench. Three bugs in v1, all mine.

1. builder picked by `next(n for n in dir(mod))` - dir() is alphabetical, so
   trapped_piece was benched on build_trapped_piece_OPPORTUNITY_proof, a
   different question. Builders are now named explicitly.
2. destination_safety takes (board, move_evaluation: Dict, played, best). The
   4-arg TypeError fallback shifted every argument by one, so it could only
   ever return None. It scored 0.0% and is promoted in production with 149
   live fires. A zero needs a positive control.
3. The `played` move was an arbitrary legal move. Provers that gate on the
   PLAYED move (did the user hang something / allow a back rank) cannot be
   measured that way: a Lichess puzzle gives the solution, never a realistic
   blunder. So each prover is scored two ways:
      fixed  - one arbitrary played move (what v1 did)
      anyrep - does ANY legal played move make it fire?
   If anyrep is high where fixed is low, the bench was wrong, not the prover.

Read-only.
"""
import os, sys, asyncio, json, time, inspect, importlib
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

# module -> (explicit builder, lichess theme)
PROVERS = [
    ("fork_puzzle_proof", "build_fork_proof", "fork"),
    ("trapped_piece_puzzle_proof", "build_trapped_piece_proof", "trappedPiece"),
    ("trapped_piece_puzzle_proof", "build_trapped_piece_opportunity_proof", "trappedPiece"),
    ("discovered_attack_puzzle_proof", "build_discovered_attack_proof", "discoveredAttack"),
    ("back_rank_mate_puzzle_proof", "build_back_rank_mate_proof", "backRankMate"),
    ("deflection_puzzle_proof", "build_deflection_proof", "deflection"),
    ("attraction_puzzle_proof", "build_attraction_proof", "attraction"),
    ("clearance_puzzle_proof", "build_clearance_proof", "clearance"),
    ("interference_puzzle_proof", "build_interference_proof", "interference"),
    ("xray_attack_puzzle_proof", "build_xray_attack_proof", "xRayAttack"),
    ("removal_defender_puzzle_proof", "build_removal_defender_proof", "capturingDefender"),
    ("advanced_pawn_puzzle_proof", "build_advanced_pawn_proof", "advancedPawn"),
    ("defensive_move_puzzle_proof", "build_defensive_move_proof", "defensiveMove"),
    ("forced_mate_puzzle_proof", "build_forced_mate_proof", "mateIn2"),
    ("free_piece_puzzle_proof", "build_free_piece_proof", "hangingPiece"),
    ("piece_safety_puzzle_proof", "build_piece_safety_proof", "hangingPiece"),
    ("destination_safety_puzzle_proof", "build_destination_safety_proof", "hangingPiece"),
    ("aligned_tactic_puzzle_proof", "build_aligned_tactic_proof", "pin"),
]
CROSS = ["fork", "pin", "mateIn2", "trappedPiece"]
MAX_TRY = 45          # cap the any-played sweep so runtime stays sane
_cache = {}


async def sample(db, theme, n, exclude=None, lo=600, hi=1500):
    key = (theme, exclude, n)
    if key in _cache:
        return _cache[key]
    out, tries = [], 0
    while len(out) < n and tries < 10:
        tries += 1
        async for p in db.lichess_puzzles.aggregate([{"$sample": {"size": 5000}}]):
            th = p.get("themes")
            th = th.split() if isinstance(th, str) else th
            if not th or theme not in th:
                continue
            if exclude and exclude in th:
                continue
            try:
                r = int(p.get("rating") or 0)
            except Exception:
                r = 0
            if not (lo <= r <= hi):
                continue
            mv = p.get("moves")
            mv = mv.split() if isinstance(mv, str) else mv
            if not mv or len(mv) < 2 or not p.get("fen"):
                continue
            out.append({"fen": p["fen"], "moves": mv})
            if len(out) >= n:
                break
    _cache[key] = out
    return out


def make_caller(fn):
    """Bind a prover to its REAL signature instead of guessing."""
    names = list(inspect.signature(fn).parameters)
    if len(names) >= 2 and names[1] == "move_evaluation":
        def call(board, played, best, pv, cp):
            row = {"fen_before": board.fen(), "fen": board.fen(),
                   "move_uci": played, "best_move_uci": best,
                   "best_move": best, "cp_loss": cp}
            return fn(board, row, played, best)
        return call, "dict"
    if "pv_after_best" in names:
        return (lambda b, p, m, pv, cp: fn(b, p, m, pv, cp)), "pv"
    return (lambda b, p, m, pv, cp: fn(b, p, m, cp)), "4arg"


def setup(p):
    b = chess.Board(p["fen"])
    b.push(chess.Move.from_uci(p["moves"][0]))
    return b, p["moves"][1], p["moves"][2:]


def fires_fixed(call, p):
    try:
        b, best, pv = setup(p)
        played = next((m.uci() for m in b.legal_moves if m.uci() != best), None)
        return bool(played) and call(b, played, best, pv, 300) is not None
    except Exception:
        return False


def fires_any(call, p):
    try:
        b, best, pv = setup(p)
    except Exception:
        return False
    for i, m in enumerate(b.legal_moves):
        if i >= MAX_TRY:
            break
        if m.uci() == best:
            continue
        try:
            if call(b, m.uci(), best, pv, 300) is not None:
                return True
        except Exception:
            continue
    return False


async def main():
    n_rec = int(os.environ.get("RECALL_N", 120))
    n_x = int(os.environ.get("CROSS_N", 80))
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]

    print("%-38s %-16s %6s %7s  %s" % ("builder", "theme", "fixed", "anyplay", "cross-fire(fixed)"))
    print("-" * 104)
    res, t0 = {}, time.time()

    for mod_name, bname, theme in PROVERS:
        try:
            fn = getattr(importlib.import_module("services.%s" % mod_name), bname)
            call, shape = make_caller(fn)
        except Exception as e:
            print("%-38s %-16s  import/bind failed: %s" % (bname[:38], theme, str(e)[:34]))
            continue

        pz = await sample(db, theme, n_rec)
        if not pz:
            print("%-38s %-16s  no puzzles" % (bname[:38], theme))
            continue
        fixed = 100.0 * sum(1 for p in pz if fires_fixed(call, p)) / len(pz)
        anyp = 100.0 * sum(1 for p in pz if fires_any(call, p)) / len(pz)

        xf = {}
        for ct in CROSS:
            if ct == theme:
                continue
            q = await sample(db, ct, n_x, exclude=theme)
            if q:
                xf[ct] = round(100.0 * sum(1 for p in q if fires_fixed(call, p)) / len(q), 1)
            if len(xf) >= 2:
                break

        res[bname] = {"theme": theme, "fixed": round(fixed, 1), "any": round(anyp, 1),
                      "n": len(pz), "cross_fire": xf, "shape": shape, "module": mod_name}
        print("%-38s %-16s %5.1f%% %6.1f%%  %s"
              % (bname[:38], theme, fixed, anyp,
                 "  ".join("%s:%.0f%%" % (k, v) for k, v in xf.items())))

    print("\nelapsed %.0fs" % (time.time() - t0))
    with open("/tmp/bench_v2.json", "w") as f:
        json.dump(res, f, indent=1)

    print("\n=== played-move dependent? (anyplay much higher than fixed) ===")
    for k, v in sorted(res.items(), key=lambda kv: kv[1]["fixed"] - kv[1]["any"]):
        d = v["any"] - v["fixed"]
        if d >= 20:
            print("  %-38s fixed %5.1f%% -> anyplay %5.1f%%  (+%.0f) BENCH ARTEFACT"
                  % (k, v["fixed"], v["any"], d))

    print("\n=== CLEARS BAR on the played-independent reading (any>=85, cross<=5) ===")
    for k, v in sorted(res.items(), key=lambda kv: -kv[1]["any"]):
        if v["any"] >= 85 and all(x <= 5 for x in v["cross_fire"].values()):
            print("  %-38s %-16s any %5.1f%%  cross %s" % (k, v["theme"], v["any"], v["cross_fire"]))

asyncio.run(main())
