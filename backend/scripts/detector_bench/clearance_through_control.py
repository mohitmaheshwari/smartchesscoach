"""Is `through` reachable at all, or silently dead?

All 310 clearance fires on real games came back `onto`, none `through`. The
detector's own docstring documents 7 of its 12 reference puzzles as through:

  00AhO through c8 | 00Pc8 through e5 | 00aCb through e4 | 01EUl through d4
  01LlS through e4 | 01f0q through e4 | 01gA2 through f8 (knowingly refused)

So the positive control is written down. Run the CURRENT code on those exact
puzzles. If `through` never appears there either, it is a bug, not a
distribution difference, and a third of the motif is unreachable.

Read-only.
"""
import os, sys, asyncio
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

DOCUMENTED = {
    "00Aae": "onto b8", "00AhO": "through c8", "00M92": "onto h4",
    "00PHg": "onto a8", "00Pc8": "through e5", "00Yy4": "onto h5",
    "00aCb": "through e4", "00oYS": "onto c1", "01EUl": "through d4",
    "01LlS": "through e4", "01f0q": "through e4", "01gA2": "through f8 (refused)",
}


async def main():
    from services.clearance_puzzle_proof import build_clearance_proof
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]

    print("%-8s %-22s %-10s %-8s %s" % ("puzzle", "documented", "fires?", "through", "vacated"))
    print("-" * 74)
    n_through = n_fire = 0
    for pid, doc in DOCUMENTED.items():
        row = await db.lichess_puzzles.find_one(
            {"$or": [{"puzzle_id": pid}, {"PuzzleId": pid}, {"_id": pid}, {"id": pid}]})
        if not row:
            print("%-8s %-22s %-10s %-8s %s" % (pid, doc, "NOT FOUND", "-", "-"))
            continue
        mv = row.get("moves")
        mv = mv.split() if isinstance(mv, str) else mv
        fen = row.get("fen") or row.get("FEN")
        if not mv or not fen or len(mv) < 2:
            print("%-8s %-22s %-10s" % (pid, doc, "BAD ROW"))
            continue
        try:
            b = chess.Board(fen)
            b.push(chess.Move.from_uci(mv[0]))
            best = mv[1]
        except Exception as e:
            print("%-8s %-22s setup failed %s" % (pid, doc, str(e)[:24]))
            continue

        got = None
        for i, m in enumerate(b.legal_moves):
            if i > 45 or m.uci() == best:
                continue
            try:
                bundle = build_clearance_proof(b, m.uci(), best, mv[2:], 300)
            except Exception:
                continue
            if bundle is not None:
                got = (bundle.detector.facts or [{}])[0]
                break
        if got is None:
            print("%-8s %-22s %-10s %-8s %s" % (pid, doc, "no", "-", "-"))
            continue
        n_fire += 1
        thr = bool(got.get("through"))
        n_through += 1 if thr else 0
        print("%-8s %-22s %-10s %-8s %s" % (pid, doc, "YES", thr, got.get("vacated_square")))

    print("\nfired on %d of %d documented puzzles; `through` True on %d"
          % (n_fire, len(DOCUMENTED), n_through))
    if n_fire and n_through == 0:
        print("\n>>> `through` is DEAD: it never returns True even on the puzzles the")
        print(">>> module documents as through-cases. Not a distribution difference.")
    elif n_through:
        print("\n>>> `through` works here, so the 0/310 on real games is distributional.")

asyncio.run(main())
