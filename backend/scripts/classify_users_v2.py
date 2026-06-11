"""V2 taxonomy PROTOTYPE — classify a user's mistakes into the locked
fundamentals-first categories (docs/move_classification_from_gold_scope.md S8b).

Engine-hard derivation from mistake_classifier + eval/mate sentinels. Standalone
validation tool, NOT yet wired into the live cognitive_gap pipeline.

KNOWN GAPS (flagged, not silent): bad_trade + missed_free_material not yet
detected (fall into other buckets); opening_knowledge uses a crude move<=8
heuristic (should be book-based); walked_into_tactic needs FP validation.
Run: python3 scripts/classify_users_v2.py
import os, asyncio, chess
from collections import Counter, defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
import sys; sys.path.insert(0,"/app/backend")
from mistake_classifier import classify_mistake

MATE=3000
def upov(x,uc): return None if x is None else (x if uc=="white" else -x)

def phase(fb):
    b=chess.Board(fb)
    q=len(b.pieces(chess.QUEEN,chess.WHITE))+len(b.pieces(chess.QUEEN,chess.BLACK))
    np=sum(len(b.pieces(pt,c)) for pt in (chess.ROOK,chess.BISHOP,chess.KNIGHT) for c in (chess.WHITE,chess.BLACK))
    return ("endgame" if (q==0 and np<=6) else "mid"), q

def derive(move, uc):
    fb=move.get("fen_before") or ""; fa=move.get("fen_after") or ""
    san=move.get("move") or ""; best=move.get("best_move") or ""
    ueb=upov(move.get("eval_before"),uc); uea=upov(move.get("eval_after"),uc)
    mate=move.get("mate_info") or {}
    # MATE family (eval sentinel + mate_info)
    if (uea is not None and uea<=-MATE): return "allowed_mate"
    if (ueb is not None and ueb>=MATE and (uea is None or uea<MATE)): return "missed_mate"
    # tactic classifier
    mt=None
    try:
        c=classify_mistake(fb,fa,san,best,ueb if ueb is not None else 0,uea if uea is not None else 0,uc,move.get("move_number",0),move.get("threat"),move.get("pv_after_played"))
        mt=c.mistake_type.value
    except Exception: mt=None
    if mt in ("hanging_piece","material_blunder","ignored_threat"): return "one_move_blunder"
    if mt in ("walked_into_fork","walked_into_pin","walked_into_skewer","walked_into_discovered_attack"): return "walked_into_tactic"
    if mt in ("missed_fork","missed_pin","missed_skewer","missed_discovered_attack","missed_overloaded_defender","missed_winning_tactic"): return "missed_tactic"
    if mt in ("blunder_when_ahead","failed_conversion"): return "conversion"
    # conversion by eval (was winning, slipped)
    if ueb is not None and uea is not None and ueb>=300 and uea<=50: return "conversion"
    # king safety (queens on) vs endgame
    ph,q=phase(fb)
    if mt=="king_safety_error": return "endgame_technique" if ph=="endgame" else "king_safety"
    if ph=="endgame": return "endgame_technique"
    if (move.get("move_number") or 99)<=8: return "opening_knowledge"
    return "positional_residue"   # piece_activity/pawn_structure/calc -> needs LLM

async def main():
    db=AsyncIOMotorClient(os.environ["MONGO_URL"],serverSelectionTimeoutMS=8000)[os.environ["DB_NAME"]]
    users={"shobhit(learning)":"user_e9acb79dfc26","mohit(moderate)":"user_8b599930d7ef","parth(1900)":"user_d35b37459e10"}
    import time
    for label,uid in users.items():
        dist=Counter(); n=0; t0=time.time()
        gids=[(g["game_id"],(g.get("user_color") or "white").lower()) async for g in db.games.find({"user_id":uid,"is_analyzed":True},{"_id":0,"game_id":1,"user_color":1})]
        for gid,uc in gids:
            an=await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis.move_evaluations":1})
            for m in (an or {}).get("stockfish_analysis",{}).get("move_evaluations") or []:
                cl=m.get("cp_loss")
                if cl is None or cl<100: continue
                fb=m.get("fen_before","")
                iu=m.get("is_user_move")
                if iu is None and fb: iu=(fb.split(" ")[1]=="w")==(uc=="white")
                if not iu or not fb: continue
                try: cat=derive(m,uc)
                except Exception: cat="ERR"
                dist[cat]+=1; n+=1
        el=time.time()-t0
        print(f"\n=== {label}: {n} mistakes classified in {el:.0f}s ({1000*el/max(n,1):.0f}ms/move) ===")
        for c,k in dist.most_common():
            print(f"  {k:>5} ({100*k/max(n,1):4.1f}%)  {c}")
        resid=dist.get("positional_residue",0)
        print(f"  --> engine-hard decided: {100*(n-resid)/max(n,1):.0f}%  | LLM-needed residue: {100*resid/max(n,1):.0f}%")
asyncio.run(main())
