"""PV-deepen the gold corpus (2026-06-16). For every gold position, run deep Stockfish to get
the full best-line + post-played refutation line + mate length, and cache them in
db.gold_deep_pv (keyed by game_id+move_number). This unblocks the DEEP situations
(missed_mate / walked_into_tactic / missed_tactic) so distilled templates can name the
specific tactic instead of the stored-truncated-PV vagueness.

Env: MONGO_URL (direct prod ok), DB_NAME. No LLM. Stockfish at /usr/games/stockfish.
"""
import os, sys, time, chess, chess.engine
from pymongo import MongoClient

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=30000)[os.environ["DB_NAME"]]
TIME = float(os.environ.get("SF_TIME", "1.3"))


def sans(board, moves, k=8):
    out = []
    b = board.copy()
    for mv in moves[:k]:
        try:
            out.append(b.san(mv)); b.push(mv)
        except Exception:
            break
    return out


def main():
    golds = list(db.gold_captions.find({"created_by": {"$in": ["gold_shobhit", "gold_mohit", "gold_parth"]}, "gold_caption": {"$ne": None}}, {"_id": 0, "game_id": 1, "move_number": 1, "move_san": 1, "fen_before": 1}))
    # de-dup by (game_id, move_number) and skip already-deepened
    seen = set()
    todo = []
    done = {(d["game_id"], d["move_number"]) for d in db.gold_deep_pv.find({}, {"_id": 0, "game_id": 1, "move_number": 1})} if "gold_deep_pv" in db.list_collection_names() else set()
    for g in golds:
        key = (g["game_id"], g.get("move_number"))
        if key in seen or key in done or not g.get("fen_before"):
            continue
        seen.add(key); todo.append(g)
    print(f"to deepen: {len(todo)} (skipping {len(done)} already done)", flush=True)
    eng = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    n = 0
    for g in todo:
        fb = g["fen_before"]
        rec = {"game_id": g["game_id"], "move_number": g.get("move_number"), "move_san": g.get("move_san"),
               "deep_pv_best": [], "deep_mate_n": None, "deep_pv_played": []}
        try:
            b = chess.Board(fb)
            info = eng.analyse(b, chess.engine.Limit(time=TIME))
            rec["deep_pv_best"] = sans(b, info.get("pv") or [])
            sc = info["score"].pov(b.turn)
            if sc.is_mate() and sc.mate() and sc.mate() > 0:
                rec["deep_mate_n"] = sc.mate()
            b2 = chess.Board(fb)
            try:
                b2.push_san(g.get("move_san") or "")
                info2 = eng.analyse(b2, chess.engine.Limit(time=TIME))
                rec["deep_pv_played"] = sans(b2, info2.get("pv") or [])
            except Exception:
                pass
        except Exception as e:
            rec["err"] = str(e)[:40]
        db.gold_deep_pv.update_one({"game_id": rec["game_id"], "move_number": rec["move_number"]}, {"$set": rec}, upsert=True)
        n += 1
        if n % 25 == 0:
            print(f"  deepened {n}/{len(todo)}", flush=True)
    eng.quit()
    mates = db.gold_deep_pv.count_documents({"deep_mate_n": {"$ne": None}})
    print(f"DONE. deepened {n}; total gold_deep_pv now {db.gold_deep_pv.count_documents({})}; with forced-mate {mates}", flush=True)


main()
