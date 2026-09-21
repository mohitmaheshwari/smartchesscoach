"""Gold loop: the hand-walked puzzles must fire, AND name the right squares.

A recall percentage says a detector fired; it does not say it fired for the
right reason. These 13 deflection and 12 attraction puzzles were walked move
by move by hand before either proof was written, and the guard / target /
sacrifice square printed here was written down from the board first. If a
change makes one of them stop firing, or start naming a different square,
that is a regression even when the aggregate recall goes up.

9OVqg is Mohit's own hand-verified example and must report
guard=rook@c5 -> f5 abandoning c8.

    python backend/scripts/check_deflection_attraction_gold.py
"""
import asyncio, os, sys, chess
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from scripts.measure_deflection_attraction_detectors import prep, SYNTHETIC_CP_LOSS
from services.deflection_puzzle_proof import build_deflection_proof
from services.attraction_puzzle_proof import build_attraction_proof

DEFL = ["002Mm","004LZ","0068B","0088O","00AoZ","00DcC","00J1Y","00L76",
        "00PZo","00TFd","00TLz","00Zit","9OVqg"]
ATTR = ["001w5","003mh","006wz","00BrZ","00DBg","00Kq4","00PUc","00W5B",
        "00aDl","00d9q","00ouE","00rzv"]

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=30000)[
        os.environ.get("DB_NAME", "chess_coach")]
    for label, ids, builder, keys in (
        ("DEFLECTION", DEFL, build_deflection_proof,
         ("guard_piece", "guard_square", "guard_forced_to", "target_square",
          "target_piece", "payoff_move")),
        ("ATTRACTION", ATTR, build_attraction_proof,
         ("sacrifice_square", "attracted_piece", "attracted_from",
          "punished_by", "payoff_move")),
    ):
        print(f"\n=== {label} gold ===")
        ok = 0
        for pid in ids:
            p = await db.lichess_puzzles.find_one({"puzzle_id": pid})
            if not p:
                p = await db.lichess_puzzles.find_one({"_id": pid})
            if not p:
                print(f"  {pid:<7} NOT IN DB")
                continue
            ready = prep(p)
            if not ready:
                print(f"  {pid:<7} UNPREPPABLE")
                continue
            b, played, best, pv = ready
            bundle = builder(b, played, best, pv, SYNTHETIC_CP_LOSS)
            if bundle is None or not bundle.verifier.verified:
                print(f"  {pid:<7} NO FIRE   best={best} pv={pv} themes={sorted(p.get('themes') or [])}")
                continue
            f = bundle.verifier.facts[0]
            ok += 1
            print(f"  {pid:<7} FIRE  " + "  ".join(f"{k}={f.get(k)}" for k in keys))
        print(f"  -> {ok}/{len(ids)}")

asyncio.run(main())
