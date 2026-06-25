"""Dump FULL PWC mistake captions (cp>=120) + old-regex flags, for hand-judging."""
from __future__ import annotations
import os, sys, io, re, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient
MONGO=os.environ.get("MONGO_URL"); DB=os.environ.get("DB_NAME","chess_coach")
LIMIT_GAMES=int(os.environ.get("LIMIT_GAMES","80")); WANT=int(os.environ.get("WANT","50"))
def _f4(f): return " ".join(f.split()[:4])
def rxbad(c): return int(bool(re.search(r"(loses to \S+|lets \S+ (win|capture)|allows \S+ (fork|forking|pin|skew)|walks into \S+|drops the \w+|\bhangs\b|win your \w+ on|forking your|losing material|loses material|it drops the|away from defending|\bpassive\b|\btrapped\b|undefend|weaken)", c, re.I)))
def rxbet(c):
    m=re.search(r"was (?:the )?(?:better|stronger)\b\s*[—-]\s*(.*?)(?:\.|$)", c)
    if not m: return 0
    t=m.group(1).lower()
    if re.search(r"only slows|already (in trouble|losing)|problem started|has lost|too late", t): return 0
    return int(len(t.split())>=3)
async def main():
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    try: from services.game_decryption_v5_service import detect_phase
    except Exception: detect_phase=None
    db=AsyncIOMotorClient(MONGO,serverSelectionTimeoutMS=15000)[DB]
    games=await db.games.find({"is_analyzed":True},{"_id":0,"game_id":1,"pgn":1,"user_color":1}).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)
    shown=0
    for g in games:
        if shown>=WANT: break
        gid=g["game_id"]; uc=(g.get("user_color") or "white").lower()
        a=await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis":1})
        if not a: continue
        mes=(a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by={_f4(m.get("fen_before","")):m for m in mes if m.get("fen_before")}
        try: pg=chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception: continue
        if pg is None: continue
        b=pg.board(); hist=[]; uw=(uc=="white")
        for mv in pg.mainline_moves():
            if shown>=WANT: break
            isu=(b.turn==chess.WHITE)==uw
            try: san=b.san(mv)
            except Exception: break
            me=by.get(_f4(b.fen()))
            if me is None or not isu or int(me.get("cp_loss") or 0)<120:
                b.push(mv); hist.append(san); continue
            cp=int(me.get("cp_loss") or 0); ph="opening"
            if detect_phase:
                try: ph=detect_phase(b,b.fullmove_number)
                except Exception: pass
            _eb,_ea=me.get("eval_before"),me.get("eval_after")
            try:
                c=await generate_move_coaching(board_before=b.copy(),move=mv,best_move_san=me.get("best_move"),
                    pv_after_played=me.get("pv_after_played") or [],pv_after_best=me.get("pv_after_best") or [],
                    cp_loss=cp,phase=ph,is_user_move=True,context=CoachingContext.LIVE_AFTER_USER,user_color=uc,
                    move_history_san=list(hist),eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,move_evaluations=mes)
                narr=(getattr(c,"narrative","") or "").strip()
            except Exception: narr=""
            if narr:
                shown+=1
                print(f"#{shown:02d} cp{cp} {san}->{me.get('best_move')} [rx bad={rxbad(narr)} bet={rxbet(narr)}]  {narr}")
            b.push(mv); hist.append(san)
    print(f"\n(shown {shown})")
if __name__=="__main__":
    asyncio.run(main()); sys.stdout.flush()
    import os as _o; _o._exit(0)
