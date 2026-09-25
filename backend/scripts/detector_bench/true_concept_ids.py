"""The exact concept_id each prover emits, taken from a real fired bundle.

Half of them build concept_id at runtime, so grepping the source gives a
partial and partly wrong answer - I guessed "tactic.removal_defender" and the
source says "tactic.removal_of_defender". A registry row written against a
guessed id silently authorises nothing.

So: fire each prover on a Lichess puzzle of its own theme and read
bundle.detector.concept_id off the object. Also dumps the 64 real registry
rows through the API rather than a regex (my regex found 12 of 64).

Read-only.
"""
import os, sys, asyncio, json, inspect, importlib, collections
sys.path.insert(0, "/app/backend")
os.environ["DETECTOR_QUALITY_GATE_ENFORCED"] = "true"
import chess
from motor.motor_asyncio import AsyncIOMotorClient
from services.detector_quality import (
    explicit_authorizations, grade_for, is_authorized, QualitySurface)

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


def make_caller(fn):
    names = list(inspect.signature(fn).parameters)
    if len(names) >= 2 and names[1] == "move_evaluation":
        return lambda b, p, m, pv, cp: fn(
            b, {"fen_before": b.fen(), "move_uci": p, "best_move_uci": m, "cp_loss": cp}, p, m)
    if "pv_after_best" in names:
        return lambda b, p, m, pv, cp: fn(b, p, m, pv, cp)
    return lambda b, p, m, pv, cp: fn(b, p, m, cp)


async def sample(db, theme, n, lo=600, hi=1500):
    out, tries = [], 0
    while len(out) < n and tries < 8:
        tries += 1
        async for p in db.lichess_puzzles.aggregate([{"$sample": {"size": 5000}}]):
            th = p.get("themes")
            th = th.split() if isinstance(th, str) else th
            if not th or theme not in th:
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
    return out


async def main():
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]

    print("=== REGISTRY, via the API (64 rows) ===")
    reg = explicit_authorizations()
    by = collections.Counter()
    for k, a in sorted(reg.items()):
        g = a.grade.value if hasattr(a.grade, "value") else str(a.grade)
        by[g] += 1
    print("  grades: %s   total %d\n" % (dict(by), len(reg)))

    print("=== TRUE concept_id per prover, read off a fired bundle ===")
    print("%-40s %-38s %-9s %s" % ("builder", "concept_id (actual)", "grade", "captions?"))
    print("-" * 104)
    found = {}
    for mod, bname, theme in PROVERS:
        try:
            fn = getattr(importlib.import_module("services.%s" % mod), bname)
            call = make_caller(fn)
        except Exception as e:
            print("%-40s bind failed: %s" % (bname[:40], str(e)[:40]))
            continue
        pz = await sample(db, theme, 60)
        cid = None
        for p in pz:
            try:
                b = chess.Board(p["fen"])
                b.push(chess.Move.from_uci(p["moves"][0]))
                best = p["moves"][1]
            except Exception:
                continue
            for i, m in enumerate(b.legal_moves):
                if i > 40 or m.uci() == best:
                    continue
                try:
                    bundle = call(b, m.uci(), best, p["moves"][2:], 300)
                except Exception:
                    continue
                if bundle is not None:
                    det = getattr(bundle, "detector", None)
                    cid = getattr(det, "concept_id", None)
                    break
            if cid:
                break
        if not cid:
            print("%-40s %-38s %-9s %s" % (bname[:40], "(never fired in sample)", "-", "-"))
            continue
        g = grade_for(cid)
        g = g.value if hasattr(g, "value") else str(g)
        cap = is_authorized(cid, QualitySurface.CAPTION)
        found[bname] = {"concept_id": cid, "grade": g, "captions": cap,
                        "in_registry": cid in reg, "theme": theme, "module": mod}
        print("%-40s %-38s %-9s %s%s"
              % (bname[:40], cid, g, cap, "" if cid in reg else "   (no row)"))

    with open("/tmp/true_ids.json", "w") as f:
        json.dump(found, f, indent=1)
    silent = [v["concept_id"] for v in found.values() if not v["captions"]]
    print("\nprovers that CANNOT reach a caption today: %d of %d" % (len(silent), len(found)))
    print("wrote /tmp/true_ids.json")

asyncio.run(main())
