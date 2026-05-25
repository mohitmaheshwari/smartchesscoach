"""verify_tier_b.py — confirm Tier B fixes landed in stored captions."""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    db = client["chess_coach"]
    checks = [
        ("game_85bd0169aa4f", 5, "Qd8",  "Q3-prior  queen retreat (v81/v91)"),
        ("game_85bd0169aa4f", 17, "h5",  "Q4 severity tier (cp=87)"),
        ("game_85bd0169aa4f", 24, "Rb3", "Q1 Rb3 winning-pos softening"),
        ("game_b5d23694a803", 7, "Bd7",  "Q3-prior Bd7 same-piece-twice"),
        ("game_f2c022e03856", 3, "h6",   "Q5 prophylactic h6"),
        ("game_f2c022e03856", 4, "d3",   "Q3 d3 strongest no longer claimed"),
    ]
    for gid, mvn, expected, label in checks:
        g = await db.game_analyses.find_one({"game_id": gid})
        moves = g.get("decryption_v5_data") or []
        m = next((mm for mm in moves if mm.get("move_number") == mvn and mm.get("move_san") == expected), None)
        if not m:
            print(f"[{label}] m{mvn} {expected} not found")
            continue
        sev = m.get("severity")
        sp = m.get("severity_practical")
        sc = m.get("severity_canonical")
        sb = m.get("mover_state_before")
        sa = m.get("mover_state_after")
        sw = m.get("stayed_winning")
        rn = m.get("rule_name")
        cap = (m.get("caption") or "").strip()[:220]
        print(f"[{label}]")
        print(f"  m{mvn} {expected} sev={sev} practical={sp} canonical={sc}")
        print(f"  state {sb}->{sa} stayed_winning={sw}")
        print(f"  rule={rn}")
        print(f"  cap: {cap}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
