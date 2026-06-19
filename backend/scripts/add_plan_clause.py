"""Proof: make distilled captions PLAN-AWARE by appending the engine's recommended
NEXT move (the plan) — computed with Stockfish at bake time (offline, cached), since
the stored PV is empty on quiet moves. Mirrors what Claude does ("...bring your knight
to f3 next"). Only the engine's choice is named -> verified by construction.

Appends to good/opp (non-mistake) distilled captions only. Env: PMONGO.
Usage: python scripts/add_plan_clause.py <game_id> [--apply]
"""
import os, sys, shutil
import pymongo, chess, chess.engine

SF = shutil.which("stockfish") or "/usr/games/stockfish"


def user_next_move(eng, fen_after, mover_is_user):
    """The USER's recommended next move from the position after the played move.
    opp just moved -> user is to move -> pv[0]. user just moved -> opp replies pv[0],
    user's move is pv[1]."""
    try:
        b = chess.Board(fen_after)
    except Exception:
        return None
    if b.is_game_over():
        return None
    try:
        info = eng.analyse(b, chess.engine.Limit(depth=14))
        pv = info.get("pv") or []
    except Exception:
        return None
    idx = 1 if mover_is_user else 0   # which ply in the PV is the user's next move
    if len(pv) <= idx:
        return None
    # convert to SAN by replaying
    bb = chess.Board(fen_after)
    san = None
    for i, mv in enumerate(pv[: idx + 1]):
        try:
            s = bb.san(mv)
        except Exception:
            return None
        if i == idx:
            san = s
        bb.push(mv)
    return san


def main():
    gid = sys.argv[1]; apply = "--apply" in sys.argv
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    ga = db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1})
    dd = (ga or {}).get("decryption_v5_data") or []
    eng = chess.engine.SimpleEngine.popen_uci(SF)
    added = 0
    try:
        for m in dd:
            rn = str(m.get("rule_name") or "")
            narr = (m.get("narrative") or "").strip()
            # only good/opp distilled captions (not mistakes, not opening names, not blanks)
            if not narr or not rn.startswith("distilled:"):
                continue
            lab = rn.split(":")[-1]
            if lab in ("one_move_blunder", "walked_into_tactic", "missed_free_material",
                       "allowed_mate", "missed_mate", "opening_knowledge") or "opening:" in rn:
                continue
            if "next move" in narr.lower():   # don't double-append
                continue
            nxt = user_next_move(eng, m.get("fen_after"), bool(m.get("is_user_move")))
            if not nxt:
                continue
            plan = f" A good next move is {nxt}."
            added += 1
            print(f"  {m.get('move_number')}:{m.get('move_san'):6} + plan {nxt}", flush=True)
            if apply:
                m["narrative"] = narr + plan
                m["caption"] = (m.get("caption") or narr) + plan
    finally:
        eng.quit()
    print(f"plan clauses added: {added}  apply={apply}", flush=True)
    if apply:
        db.game_analyses.update_one({"game_id": gid}, {"$set": {"decryption_v5_data": dd}})
        print("SAVED")


if __name__ == "__main__":
    main()
