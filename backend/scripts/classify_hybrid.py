"""HYBRID category classifier (VALIDATED approach, 2026-06-11).

Engine-hard fires ONLY where validated reliable (allowed_mate/missed_mate 100%,
clean self-hang via _played_move_hangs_piece, queens-off endgame); everything
else ABSTAINS and defers to the Claude gateway gold — never a forced wrong guess.
Mirrors services/narrator_fallback.py (same pattern for captions).

Coverage on the 3 test users: ~52-54% engine-hard (beginner/moderate), 35% (1900);
rest -> Claude. one_move_blunder (hang-checker) still needs a direct gold spot-check.
Env: LLM_API_BASE/LLM_API_KEY (gateway). Run: python3 scripts/classify_hybrid.py"""
import os, time, json, re, asyncio, requests, chess
from collections import Counter, defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
import sys; sys.path.insert(0,"/app/backend")
from analysis_interpreter import _played_move_hangs_piece
BASE=os.environ["LLM_API_BASE"].rstrip("/"); KEY=os.environ["LLM_API_KEY"]
H={"Authorization":f"Bearer {KEY}","ngrok-skip-browser-warning":"1","Content-Type":"application/json"}
def upov(x,uc): return None if x is None else (x if uc=="white" else -x)
def uci_of(m):
    u=m.get("move_uci") or m.get("uci")
    if u: return u
    fb=m.get("fen_before",""); san=m.get("move","")
    try: return chess.Board(fb).parse_san(san).uci()
    except: return ""
def engine_hard_confident(m,uc):
    """Return a category ONLY when verified-reliable; else None = ABSTAIN -> Claude."""
    ueb=upov(m.get("eval_before"),uc); uea=upov(m.get("eval_after"),uc)
    if uea is not None and uea<=-9000: return "allowed_mate"          # 100% validated
    if ueb is not None and ueb>=9000 and (uea is None or uea<9000): return "missed_mate"  # 100%
    fb=m.get("fen_before",""); u=uci_of(m)
    if fb and u:
        try:
            if _played_move_hangs_piece(fb,u): return "one_move_blunder"  # clean immediate hang
        except: pass
    try:
        b=chess.Board(fb); q=len(b.pieces(chess.QUEEN,chess.WHITE))+len(b.pieces(chess.QUEEN,chess.BLACK))
        npc=sum(len(b.pieces(pt,c)) for pt in (chess.ROOK,chess.BISHOP,chess.KNIGHT) for c in (chess.WHITE,chess.BLACK))
        if q==0 and npc<=6: return "endgame_technique"   # 83% validated
    except: pass
    return None
PROMPT="""Classify this chess MISTAKE into ONE category (600-1500 coaching app).
FEN: {fen}\nSide that moved: {side}\nMove played: {move} (cp loss {cp})\nEngine best move: {best}\nLine after PLAYED move: {pvp}\nLine after BEST move: {pvb}
Categories: allowed_mate; one_move_blunder; walked_into_tactic; bad_trade; missed_mate; missed_tactic; missed_free_material; conversion; king_safety; endgame_technique; calculation_depth; ignore_threat; pawn_structure; piece_activity; opening_knowledge.
Reply ONLY JSON: {{"category":"<exact>","why":"<=10 words"}}"""
def ask(q):
    r=requests.post(f"{BASE}/ask",headers=H,json={"question":q,"provider":"claude","timeout_seconds":60},timeout=20); r.raise_for_status(); tid=r.json()["task_id"]
    for _ in range(30):
        t=requests.get(f"{BASE}/tasks/{tid}",headers=H,timeout=15).json()
        if t.get("status")=="done": return (t.get("answer") or "").strip()
        if t.get("status") in ("error","timeout"): return None
        time.sleep(3)
def parse(a):
    if not a: return None
    mm=re.search(r'\{.*\}',a,re.S)
    try: return json.loads(mm.group(0)).get("category") if mm else None
    except: return None
def pvs(x): x=x or []; return " ".join(str(i) for i in x)[:80] if isinstance(x,list) else str(x)[:80]
async def main():
    db=AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    users={"shobhit":"user_e9acb79dfc26","mohit":"user_8b599930d7ef","parth":"user_d35b37459e10"}
    print("=== COVERAGE: engine-hard confident vs defer-to-Claude (full corpus, instant) ===")
    defer_samples=[]
    for label,uid in users.items():
        eh=Counter(); defer=0; n=0
        gids=[(g["game_id"],(g.get("user_color") or "white").lower()) async for g in db.games.find({"user_id":uid,"is_analyzed":True},{"_id":0,"game_id":1,"user_color":1})]
        for gid,uc in gids:
            an=await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis.move_evaluations":1})
            for m in (an or {}).get("stockfish_analysis",{}).get("move_evaluations") or []:
                cl=m.get("cp_loss"); fb=m.get("fen_before","")
                if cl is None or cl<100 or not fb: continue
                iu=m.get("is_user_move")
                if iu is None: iu=(fb.split(" ")[1]=="w")==(uc=="white")
                if not iu: continue
                n+=1; c=engine_hard_confident(m,uc)
                if c: eh[c]+=1
                else:
                    defer+=1
                    if len(defer_samples)<15 and label=="mohit": defer_samples.append((m,uc))
        conf=sum(eh.values())
        print(f"  {label:8} n={n:4} | engine-hard confident: {conf:4} ({100*conf/max(n,1):2.0f}%) {dict(eh)} | DEFER->Claude: {defer} ({100*defer/max(n,1):2.0f}%)")
    print("\n=== DEMO: Claude handles 15 deferred (abstained) moves ===")
    for m,uc in defer_samples:
        fb=m["fen_before"]; side="white" if fb.split(" ")[1]=="w" else "black"
        g=parse(ask(PROMPT.format(fen=fb,side=side,move=m.get("move"),cp=m.get("cp_loss"),best=m.get("best_move") or "?",pvp=pvs(m.get("pv_after_played")),pvb=pvs(m.get("pv_after_best")))))
        print(f"  deferred {m.get('move'):6} cp{m.get('cp_loss'):5} -> Claude: {g}",flush=True)
asyncio.run(main())
