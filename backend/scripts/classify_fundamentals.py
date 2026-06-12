"""Consolidated ENGINE-HARD fundamentals classifier (2026-06-12).

All detectors are PV/board-grounded (no LLM, no geometry hang-checker):
  allowed_mate/missed_mate (eval sentinel) | one_move_blunder/walked_into_tactic
  (pv_after_played material-loss depth) | missed_free_material (best move takes an
  UNDEFENDED enemy piece the played move ignored) | opening_knowledge (early-queen
  principle ONLY so far) | endgame_technique (queens-off phase).

Coverage on the 3 test users: 65/60/54% engine-hard; the rest DEFERS to Claude
(bad_trade, missed_tactic, conversion, king_safety, pawn_structure, piece_activity).
KNOWN PARTIAL: opening_knowledge = early-queen only (same-piece-twice / no-castle /
off-book need move-history+book). missed_free_material undefended-check ignores x-ray.
Run: python3 scripts/classify_fundamentals.py"""
import os, asyncio, chess
from collections import Counter
from motor.motor_asyncio import AsyncIOMotorClient
VAL={chess.PAWN:100,chess.KNIGHT:300,chess.BISHOP:300,chess.ROOK:500,chess.QUEEN:900}
def upov(x,uc): return None if x is None else (x if uc=="white" else -x)
def uci_of(m):
    u=m.get("move_uci") or m.get("uci")
    if u: return u
    try: return chess.Board(m.get("fen_before","")).parse_san(m.get("move","")).uci()
    except: return ""
def push_any(b,mv):
    for fn in (b.parse_san, lambda x: chess.Move.from_uci(x)):
        try: b.push(fn(mv)); return True
        except: pass
    return False
def pv_material(m):
    fb=m.get("fen_before",""); pv=m.get("pv_after_played") or []
    if not fb or not pv: return None
    try:
        b=chess.Board(fb); uc=b.turn; u=m.get("move_uci") or b.parse_san(m.get("move","")).uci()
        b.push(chess.Move.from_uci(u))
    except: return None
    um=lambda bb: sum(VAL[pt]*len(bb.pieces(pt,uc)) for pt in VAL)
    start=um(b); mats=[]
    for mv in pv[:6]:
        if not push_any(b,mv): break
        mats.append(um(b))
    if not mats or mats[-1]>=start-100: return None
    depth=next((i for i,v in enumerate(mats,1) if v<=start-200),None) or next((i for i,v in enumerate(mats,1) if v<=start-100),99)
    return "one_move_blunder" if depth<=2 else "walked_into_tactic"
def missed_free(m):
    best=m.get("best_move") or ""
    if "x" not in best: return False
    try:
        b=chess.Board(m.get("fen_before",""))
        bm=b.parse_san(best); cap=b.piece_at(bm.to_square)
        if not cap: return False
        if (m.get("move") or "")==best: return False
        return len(b.attackers(cap.color,bm.to_square))==0   # undefended enemy piece = free
    except: return False
def early_queen(m):
    san=m.get("move") or ""; mn=m.get("move_number") or 99
    return san.startswith("Q") and mn<=6 and "x" not in san
def classify(m,uc):
    ueb=upov(m.get("eval_before"),uc); uea=upov(m.get("eval_after"),uc)
    if uea is not None and uea<=-9000: return "allowed_mate"
    if ueb is not None and ueb>=9000 and (uea is None or uea<9000): return "missed_mate"
    pm=pv_material(m)
    if pm: return pm
    if missed_free(m): return "missed_free_material"
    if early_queen(m): return "opening_knowledge"
    try:
        b=chess.Board(m.get("fen_before","")); q=len(b.pieces(chess.QUEEN,chess.WHITE))+len(b.pieces(chess.QUEEN,chess.BLACK))
        npc=sum(len(b.pieces(pt,c)) for pt in (chess.ROOK,chess.BISHOP,chess.KNIGHT) for c in (chess.WHITE,chess.BLACK))
        if q==0 and npc<=6: return "endgame_technique"
    except: pass
    return "(defer to Claude)"
async def main():
    db=AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    users={"shobhit":"user_e9acb79dfc26","mohit":"user_8b599930d7ef","parth":"user_d35b37459e10"}
    res={}
    for label,uid in users.items():
        d=Counter()
        gids=[(g["game_id"],(g.get("user_color") or "white").lower()) async for g in db.games.find({"user_id":uid,"is_analyzed":True},{"_id":0,"game_id":1,"user_color":1})]
        for gid,uc in gids:
            an=await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis.move_evaluations":1})
            for m in (an or {}).get("stockfish_analysis",{}).get("move_evaluations") or []:
                cl=m.get("cp_loss"); fb=m.get("fen_before","")
                if cl is None or cl<100 or not fb: continue
                iu=m.get("is_user_move")
                if iu is None: iu=(fb.split(" ")[1]=="w")==(uc=="white")
                if not iu: continue
                d[classify(m,uc)]+=1
        res[label]=d
    order=["one_move_blunder","walked_into_tactic","missed_free_material","missed_mate","allowed_mate","opening_knowledge","endgame_technique","(defer to Claude)"]
    print(f"{'category':22}{'shobhit':>11}{'mohit':>11}{'parth':>11}")
    for c in order:
        r=[res[l].get(c,0) for l in users]; t=[sum(res[l].values()) for l in users]
        print(f"{c:22}"+"".join(f"{r[i]:>6}({100*r[i]//max(t[i],1):>2}%)" for i in range(3)))
    print(f"{'TOTAL':22}"+"".join(f"{sum(res[l].values()):>11}" for l in users))
    eh=[sum(v for k,v in res[l].items() if k!='(defer to Claude)') for l in users]
    print(f"{'engine-hard covered':22}"+"".join(f"{100*eh[i]//max(sum(res[l].values()),1):>10}%" for i,l in enumerate(users)))
asyncio.run(main())
