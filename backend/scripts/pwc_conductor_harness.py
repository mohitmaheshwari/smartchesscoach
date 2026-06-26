"""pwc_conductor_harness.py — score PWC live behavior against the Coach Conductor laws
(docs/pwc_coach_conductor_scope.md). Replays real games through the live path and measures:
  LAW 1 (no quiz): count of coach outputs that ASK a question.
  LAW 3 (engine-true): per-FEN verifier violations across all rendered captions.
  THREAD: count of personalized pattern callbacks (decision-tagged conductor_thread).
Also dumps one transcript so we can read the FELT experience. Run baseline now; re-run after
each build step and watch quizzes->0, false->0, threads->firing.
"""
from __future__ import annotations
import os, sys, io, re, asyncio, collections
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient
MONGO=os.environ.get("MONGO_URL"); DB=os.environ.get("DB_NAME","chess_coach")
LIMIT_GAMES=int(os.environ.get("LIMIT_GAMES","40"))
TRANSCRIPT_GAME=int(os.environ.get("TRANSCRIPT_GAME","0"))  # which game index to print full

def _f4(f): return " ".join(f.split()[:4])

# LAW 1 — does this text ASK the player something (a quiz)?
_QUIZ_RX = re.compile(
    r"\?|"
    r"\b(can you see|do you see|what(?:'s| is| does| would| are)|"
    r"how will you|which of your|have you (?:castled|developed)|"
    r"are your|are you contesting|guess|count the|how many escape)\b", re.I)
def is_quiz(text): return bool(text and _QUIZ_RX.search(text))

async def main():
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    from services.live_v5_teaching import coach_move_narration_for_live_move
    from services.narrator_claim_verifier import verify_caption
    try: from services.game_decryption_v5_service import detect_phase
    except Exception: detect_phase=None
    db=AsyncIOMotorClient(MONGO,serverSelectionTimeoutMS=20000)[DB]
    games=await db.games.find({"is_analyzed":True},{"_id":0,"game_id":1,"pgn":1,"user_color":1,"user_id":1}).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)

    S={"moves":0,"coach_cards":0,"user_cards":0,"quiz_user":0,"quiz_coach":0,
       "quiz_hint":0,"quiz_opp":0,"false":0,"threads":0}
    quiz_samples=[]; transcript=[]
    gi=-1
    for g in games:
        gi+=1
        gid=g["game_id"]; uc=(g.get("user_color") or "white").lower(); uw=(uc=="white")
        a=await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis":1})
        if not a: continue
        mes=(a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by={_f4(m.get("fen_before","")):m for m in mes if m.get("fen_before")}
        try: pg=chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception: continue
        if pg is None: continue
        b=pg.board(); hist=[]; ply=0
        for mv in pg.mainline_moves():
            if ply>=30 and gi!=TRANSCRIPT_GAME: break
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
            bafter=b.copy(); bafter.push(mv)
            vfacts={"move_san":san,"fen_before":b.fen(),"fen_after":bafter.fen(),
                    "is_user_move":isu,"cp_loss":abs(cp),"best_move_san":me.get("best_move"),
                    "pv_after_played":me.get("pv_after_played") or [],"pv_after_best":me.get("pv_after_best") or []}
            S["moves"]+=1
            if isu:
                try:
                    c=await generate_move_coaching(board_before=b.copy(),move=mv,best_move_san=me.get("best_move"),
                        pv_after_played=me.get("pv_after_played") or [],pv_after_best=me.get("pv_after_best") or [],
                        cp_loss=cp,phase=ph,is_user_move=True,context=CoachingContext.LIVE_AFTER_USER,user_color=uc,
                        move_history_san=list(hist),eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                        eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,move_evaluations=mes)
                    narr=(getattr(c,"narrative","") or "").strip()
                    sq=getattr(c,"socratic_question",None) or ""
                    if getattr(c,"conductor_thread",None): S["threads"]+=1
                except Exception: narr=""; sq=""
                if narr:
                    S["user_cards"]+=1
                    if is_quiz(narr) or is_quiz(sq):
                        S["quiz_user"]+=1
                        if len(quiz_samples)<14: quiz_samples.append(f"[U] {san}: {narr[:80]}{(' || ?:'+sq) if sq else ''}")
                    try:
                        if verify_caption(narr,vfacts): S["false"]+=1
                    except Exception: pass
                    if gi==TRANSCRIPT_GAME: transcript.append(f"  you {san}: {narr}"+(f"\n      ? {sq}" if sq else ""))
            else:
                try:
                    ce=coach_move_narration_for_live_move(fen_before=b.fen(),played_san=san,user_color=uc,
                        move_history_san=list(hist),full_move_number=b.fullmove_number,
                        eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                        eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,best_move_san=me.get("best_move"))
                except Exception: ce=None
                if ce:
                    S["coach_cards"]+=1
                    expl=ce.get("explanation","") or ""; hint=ce.get("hint_for_user","") or ""
                    opp=(ce.get("opponent_opportunity") or {}).get("message","") if ce.get("opponent_opportunity") else ""
                    if is_quiz(expl): S["quiz_coach"]+=1
                    if hint: S["quiz_hint"]+=1
                    if opp: S["quiz_opp"]+=1
                    if (is_quiz(expl) or hint) and len(quiz_samples)<14:
                        quiz_samples.append(f"[C] {san}: {expl[:60]} || hint: {hint[:50]}")
                    try:
                        if verify_caption(expl,vfacts): S["false"]+=1
                    except Exception: pass
                    if gi==TRANSCRIPT_GAME: transcript.append(f"  COACH {san}: {expl}"+(f"\n      ? {hint}" if hint else "")+(f"\n      can-you-see: {opp}" if opp else ""))
            b.push(mv); hist.append(san)

    pct=lambda a,bn: f"{round(100*a/bn)}%" if bn else "-"
    print("="*68); print("COACH CONDUCTOR HARNESS — BASELINE SCORECARD"); print("="*68)
    print(f"moves rendered: {S['moves']}  (user cards {S['user_cards']}, coach cards {S['coach_cards']})")
    print(f"\nLAW 1 — NO QUIZ  (target: 0 everywhere)")
    print(f"   user-move quiz captions : {S['quiz_user']}  ({pct(S['quiz_user'],S['user_cards'])})")
    print(f"   coach-move quiz explain : {S['quiz_coach']} ({pct(S['quiz_coach'],S['coach_cards'])})")
    print(f"   coach hint_for_user ?   : {S['quiz_hint']}  ({pct(S['quiz_hint'],S['coach_cards'])})  <- Socratic questions")
    print(f"   'can you see it' callouts: {S['quiz_opp']} ({pct(S['quiz_opp'],S['coach_cards'])})")
    print(f"\nLAW 3 — ENGINE-TRUE  (target: 0)")
    print(f"   false claims (verifier) : {S['false']}")
    print(f"\nTHREAD — personalized pattern callbacks  (target: fires on player-weak motifs)")
    print(f"   conductor threads fired : {S['threads']}")
    print(f"\n--- quiz samples (what must be removed/converted) ---")
    for s in quiz_samples: print("  "+s)
    if transcript:
        print(f"\n--- FULL TRANSCRIPT (game index {TRANSCRIPT_GAME}) — read the FEEL ---")
        for t in transcript[:40]: print(t)

if __name__=="__main__":
    asyncio.run(main()); sys.stdout.flush()
    import os as _o; _o._exit(0)
