"""Is the clearance the LESSON, or scenery further down the engine line?

clearance fires on 47.0% of real games - as often as the wired fork detector.
A clearance sacrifice does not occur in half of all 600-1500 games, so the
question is what those fires are.

`_locate_clearance` walks EVERY initiator ply of the stored line, not just the
best move, and records `clearance_ply_in_line`. That is the discriminator and
it is already in the data:

  ply 0  -> the best move IS the clearance. "You missed a clearance" is a
            licensed claim about the move the user actually got wrong.
  ply >0 -> the clearance happens later in a line the user never reached. The
            mistake was the first move; the clearance is downstream scenery.
            Naming it teaches the wrong thing.

Also recorded per fire, because they change the reading:
  - was the clearance move itself a capture? then "win material" is the lesson
  - through vs onto the vacated square (captions must not swap these)
  - how far apart the clearance and its follow-up are

Maths only, no vocabulary checks. Read-only. Writes a review packet.
"""
import os, sys, asyncio, collections, json, inspect, importlib
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    from services.clearance_puzzle_proof import build_clearance_proof
    try:
        from services.clearance_puzzle_proof import CLEARANCE_QUALITY_ID, CLEARANCE_CONCEPT_ID
        print("quality_id=%s  concept_id=%s\n" % (CLEARANCE_QUALITY_ID, CLEARANCE_CONCEPT_ID))
    except Exception:
        pass

    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]
    limit = int(os.environ.get("GAMES", 400))

    ply = collections.Counter()
    kind = collections.Counter()
    capture_clear = collections.Counter()
    gap = collections.Counter()
    samples = []
    fires = 0

    cur = db.game_analyses.find({}, {"_id": 0, "game_id": 1, "stockfish_analysis": 1}).limit(limit)
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
            if cp < 100:
                continue
            pv = ev.get("pv_after_best") or ev.get("best_line") or []
            try:
                bundle = build_clearance_proof(board, played, best, pv, cp)
            except Exception:
                continue
            if bundle is None:
                continue
            fires += 1
            f = (bundle.detector.facts or [{}])[0]
            p = f.get("clearance_ply_in_line")
            ply[p] += 1
            kind["through" if f.get("through") else "onto"] += 1
            d = f.get("follow_up_ply_in_line")
            if isinstance(p, int) and isinstance(d, int):
                gap[d - p] += 1

            # was the clearance move itself a capture? replay to its ply
            is_cap = None
            try:
                b2 = chess.Board(fen)
                line = [best] + [str(x) for x in pv]
                for i, u in enumerate(line):
                    mv = chess.Move.from_uci(u)
                    if i == p:
                        is_cap = b2.is_capture(mv)
                        break
                    b2.push(mv)
            except Exception:
                pass
            capture_clear[str(is_cap)] += 1

            if len(samples) < 60:
                samples.append({
                    "game_id": a.get("game_id"), "fen_before": fen,
                    "played": played, "best": best, "cp_loss": cp,
                    "clearance_ply": p, "immediate": f.get("clearance_is_immediate"),
                    "follow_up_ply": d, "vacated": f.get("vacated_square"),
                    "clearing_piece": f.get("clearing_piece"),
                    "follow_up_piece": f.get("follow_up_piece"),
                    "through": f.get("through"),
                    "clearance_move_is_capture": is_cap,
                })

    print("clearance fires on user blunders: %d\n" % fires)
    print("=== clearance_ply_in_line (0 = the best move IS the clearance) ===")
    for k in sorted(ply, key=lambda x: (x is None, x)):
        n = ply[k]
        mark = "  <- LICENSED: the missed move itself" if k == 0 else "  <- scenery: user never reached this ply"
        print("  ply %-5s %5d  %5.1f%%%s" % (k, n, 100.0 * n / max(fires, 1), mark))

    imm = ply.get(0, 0)
    print("\n  LICENSED (ply 0): %d / %d = %.1f%%" % (imm, fires, 100.0 * imm / max(fires, 1)))
    print("  scenery  (ply>0): %d / %d = %.1f%%" % (fires - imm, fires, 100.0 * (fires - imm) / max(fires, 1)))

    print("\n=== was the clearance move itself a capture? ===")
    for k, n in capture_clear.most_common():
        print("  %-8s %5d  %5.1f%%" % (k, n, 100.0 * n / max(fires, 1)))
    print("\n=== geometry kind ===")
    for k, n in kind.most_common():
        print("  %-8s %5d  %5.1f%%" % (k, n, 100.0 * n / max(fires, 1)))
    print("\n=== plies between clearance and its follow-up ===")
    for k in sorted(gap):
        print("  +%-3d %5d  %5.1f%%" % (k, gap[k], 100.0 * gap[k] / max(fires, 1)))

    with open("/tmp/clearance_review.json", "w") as fh:
        json.dump({"fires": fires, "ply": {str(k): v for k, v in ply.items()},
                   "capture": dict(capture_clear), "kind": dict(kind),
                   "gap": {str(k): v for k, v in gap.items()},
                   "samples": samples}, fh, indent=1)
    print("\nwrote /tmp/clearance_review.json (%d samples for human review)" % len(samples))

asyncio.run(main())
