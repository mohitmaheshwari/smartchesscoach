"""pwc_play_transcript.py — experience PWC as a USER. Replay a real analyzed game
and render the FULL coaching stream, ply by ply, exactly in the order a user sees
it: coach-move card, your-move card, socratic prompts, fundamentals, plan. The
point is to FEEL the flow (cadence / continuity / voice), not grade captions.
"""
from __future__ import annotations
import os, sys, io, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient
MONGO=os.environ.get("MONGO_URL"); DB=os.environ.get("DB_NAME","chess_coach")
GAME=os.environ.get("GAME_ID"); MAXPLY=int(os.environ.get("MAXPLY","30"))

def _f4(f): return " ".join(f.split()[:4])

async def main():
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    from services.live_v5_teaching import coach_move_narration_for_live_move
    try: from services.game_decryption_v5_service import detect_phase
    except Exception: detect_phase=None
    db=AsyncIOMotorClient(MONGO,serverSelectionTimeoutMS=15000)[DB]
    q={"is_analyzed":True}
    if GAME: q={"game_id":GAME}
    # pick a game with a reasonable number of moves
    g=None
    async for cand in db.games.find(q,{"_id":0,"game_id":1,"pgn":1,"user_color":1}).limit(40):
        a=await db.game_analyses.find_one({"game_id":cand["game_id"]},{"_id":0,"stockfish_analysis":1})
        if a and len((a.get("stockfish_analysis") or {}).get("move_evaluations") or [])>=8:
            g=cand; g["_an"]=a; break
    if not g: print("no game"); return
    uc=(g.get("user_color") or "white").lower(); uw=(uc=="white")
    mes=(g["_an"].get("stockfish_analysis") or {}).get("move_evaluations") or []
    by={_f4(m.get("fen_before","")):m for m in mes if m.get("fen_before")}
    pg=chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
    print(f"GAME {g['game_id']}  | you play {uc.upper()}  (rendered with current code)\n"+"="*72)
    print("[ TODAY'S GOAL banner ]  (session-level, shown the whole game)")
    print("   Today, before each move, ask: what is my opponent threatening?\n")
    b=pg.board(); hist=[]; ply=0
    for mv in pg.mainline_moves():
        if ply>=MAXPLY: break
        ply+=1
        isu=(b.turn==chess.WHITE)==uw
        try: san=b.san(mv)
        except Exception: break
        me=by.get(_f4(b.fen())) or {}
        cp=int(me.get("cp_loss") or 0); ph="opening"
        if detect_phase:
            try: ph=detect_phase(b,b.fullmove_number)
            except Exception: pass
        _eb,_ea=me.get("eval_before"),me.get("eval_after")
        if isu:
            try:
                c=await generate_move_coaching(board_before=b.copy(),move=mv,best_move_san=me.get("best_move"),
                    pv_after_played=me.get("pv_after_played") or [],pv_after_best=me.get("pv_after_best") or [],
                    cp_loss=cp,phase=ph,is_user_move=True,context=CoachingContext.LIVE_AFTER_USER,user_color=uc,
                    move_history_san=list(hist),eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,move_evaluations=mes)
                dot={"good":"GREEN","brilliant":"CYAN","inaccuracy":"YELLOW","mistake":"ORANGE","blunder":"RED","silent":"--"}.get(c.severity,c.severity)
                print(f"--- ply {ply}: YOU played {san}   [{dot} dot]")
                if c.suppress or not (c.narrative or "").strip():
                    print("      (card: nothing — silent)")
                else:
                    print(f"      YOUR MOVE card: {c.narrative}")
                    if getattr(c,'socratic_question',None): print(f"        ? {c.socratic_question}")
                    if getattr(c,'socratic_hint',None): print(f"        hint: {c.socratic_hint}")
                    if getattr(c,'focus_plan',None): print(f"        plan: {c.focus_plan}")
                    if getattr(c,'your_plan_now',None): print(f"        your plan now: {c.your_plan_now}")
                    if getattr(c,'transferable_learning',None): print(f"        takeaway: {c.transferable_learning}")
            except Exception as e:
                print(f"--- ply {ply}: YOU {san}  [ERR {e}]")
        else:
            try:
                ce=coach_move_narration_for_live_move(fen_before=b.fen(),played_san=san,user_color=uc,
                    move_history_san=list(hist),full_move_number=b.fullmove_number,
                    eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,best_move_san=me.get("best_move"))
                print(f"--- ply {ply}: COACH played {san}")
                if ce:
                    lbl=ce.get("v2_label") or "Coach played"
                    print(f"      COACH card [{lbl}]: {ce.get('explanation','')}")
                    if ce.get("hint_for_user"): print(f"        ? {ce['hint_for_user']}")
                    opp=ce.get("opponent_opportunity")
                    if opp and opp.get("message"): print(f"        can you see it: {opp['message']}")
                else:
                    print("      (coach card: nothing)")
            except Exception as e:
                print(f"--- ply {ply}: COACH {san}  [ERR {e}]")
        b.push(mv); hist.append(san)
    print("\n"+"="*72+"\n(transcript end)")

if __name__=="__main__":
    asyncio.run(main()); sys.stdout.flush()
    import os as _o; _o._exit(0)
